"""Form 1120-S line 19 'Other deductions (attach statement)' statement.

Synthetic data only. Covers: scenario loader (fail-closed, footing rule),
PDF-emit enforcement, the renderer, and packet placement."""
import dataclasses
import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.filing.statement_other_deductions import (
    render_other_deductions_statement,
)
from tenforty.models import OtherDeductionComponent
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.pdf_packet import FEDERAL_CORPORATE, classify_key, ordered_members
from tenforty.scenario import load_scenario
from tests._scorp_fixtures import _make_v1_scenario
from tests.test_scenario_scorp import _YAML_WITH_SCORP

_COMPS = [
    OtherDeductionComponent("Software subscriptions", 1200.4),
    OtherDeductionComponent("Bank fees", 300.4),
]  # rounds to 1200 + 300 = 1500


def _load(deductions_tail: str):
    marker = "other_deductions: 0.0\n"
    line = next(l for l in _YAML_WITH_SCORP.splitlines(True) if marker in l)
    indent = line[:len(line) - len(line.lstrip())]
    tail = "".join(indent + t.strip() + "\n" if not t.startswith("          ")
                   else indent + "  " + t.strip() + "\n"
                   for t in deductions_tail.splitlines())
    yaml_text = _YAML_WITH_SCORP.replace(line, tail)
    assert tail in yaml_text
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.yaml"
        p.write_text(yaml_text)
        return load_scenario(p)


def _with_components(other, comps):
    s = _make_v1_scenario(other_deductions=other)
    s.s_corp_return.deductions = dataclasses.replace(
        s.s_corp_return.deductions, other_deductions_components=list(comps))
    return s


class LoaderTests(unittest.TestCase):
    def test_components_load(self):
        s = _load(
            "        other_deductions: 1500.0\n"
            "        other_deductions_components:\n"
            "          - {description: Software, amount: 1200.0}\n"
            "          - {description: Fees, amount: 300.0}\n")
        comps = s.s_corp_return.deductions.other_deductions_components
        self.assertEqual([(c.description, c.amount) for c in comps],
                         [("Software", 1200.0), ("Fees", 300.0)])

    def test_default_is_empty(self):
        s = _load("        other_deductions: 0.0\n")
        self.assertEqual(s.s_corp_return.deductions.other_deductions_components, [])

    def test_unknown_component_key_refused(self):
        with self.assertRaises(ValueError):
            _load("        other_deductions: 10.0\n"
                  "        other_deductions_components:\n"
                  "          - {description: A, amount: 10.0, note: x}\n")

    def test_footing_mismatch_refused_naming_both_numbers(self):
        with self.assertRaises(ValueError) as cm:
            _load("        other_deductions: 1600.0\n"
                  "        other_deductions_components:\n"
                  "          - {description: A, amount: 1200.0}\n"
                  "          - {description: B, amount: 300.0}\n")
        self.assertIn("1500", str(cm.exception))
        self.assertIn("1600", str(cm.exception))

    def test_footing_uses_per_item_rounding(self):
        # 0.4 + 0.4 = 0.8 raw (rounds to 1) but per-item rounding gives 0.
        with self.assertRaises(ValueError):
            _load("        other_deductions: 1.0\n"
                  "        other_deductions_components:\n"
                  "          - {description: A, amount: 0.4}\n"
                  "          - {description: B, amount: 0.4}\n")

    def test_blank_description_refused(self):
        with self.assertRaises(ValueError):
            _load("        other_deductions: 10.0\n"
                  "        other_deductions_components:\n"
                  "          - {description: '', amount: 10.0}\n")

    def test_non_list_refused(self):
        with self.assertRaises(ValueError):
            _load("        other_deductions: 10.0\n"
                  "        other_deductions_components: 10.0\n")


class EmitEnforcementTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def test_emit_without_components_refused(self):
        s = _make_v1_scenario(other_deductions=1500.0)
        with self.assertRaises(ValueError) as cm:
            self.orch.run_full_return(s, Path(self._tmp.name) / "o")
        self.assertIn("other_deductions_components", str(cm.exception))
        self.assertIn("statement", str(cm.exception))

    def test_compute_only_stays_permissive(self):
        s = _make_v1_scenario(other_deductions=1500.0)
        from tenforty.forms import f1120s
        results = f1120s.compute(s, upstream={})
        self.assertEqual(results["f1120s_other_deductions"], 1500)

    def test_emit_with_footing_components_emits_statement(self):
        s = _with_components(1500.0, _COMPS)
        _r, emitted = self.orch.run_full_return(
            s, Path(self._tmp.name) / "o")
        key = "1120s_other_deductions_stmt"
        self.assertIn(key, emitted)
        text = pypdf.PdfReader(str(emitted[key])).pages[0].extract_text()
        self.assertIn("Software subscriptions", text)
        self.assertIn("1,500", text)

    def test_emit_with_non_footing_components_refused(self):
        s = _with_components(1600.0, _COMPS)
        with self.assertRaises(ValueError) as cm:
            self.orch.run_full_return(s, Path(self._tmp.name) / "o")
        self.assertIn("1500", str(cm.exception))
        self.assertIn("1600", str(cm.exception))

    def test_zero_other_deductions_emits_no_statement(self):
        s = _make_v1_scenario(other_deductions=0.0)
        _r, emitted = self.orch.run_full_return(s, Path(self._tmp.name) / "o")
        self.assertNotIn("1120s_other_deductions_stmt", emitted)


class RendererTests(unittest.TestCase):
    def _render(self, d, name="a.pdf", comps=_COMPS):
        return render_other_deductions_statement(
            entity_name="Example S-Corp Inc.", ein="00-0000000", year=2025,
            components=comps, output_path=Path(d) / name)

    def test_one_page_with_title_header_rows_and_total(self):
        with tempfile.TemporaryDirectory() as d:
            r = pypdf.PdfReader(str(self._render(d)))
            self.assertEqual(len(r.pages), 1)
            text = r.pages[0].extract_text()
            for needle in ("Form 1120-S, Line 19", "Other Deductions Statement",
                           "Example S-Corp Inc.", "00-0000000", "2025",
                           "Software subscriptions", "Bank fees",
                           "1,200", "300", "Total", "1,500"):
                self.assertIn(needle, text)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self._render(d, "a.pdf").read_bytes(),
                             self._render(d, "b.pdf").read_bytes())

    def test_empty_components_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                self._render(d, comps=[])


class CaEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def _ca(self, s):
        from tenforty.models import SCorpCAInputs
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        return s

    def test_ca_emit_without_components_refused(self):
        s = self._ca(_make_v1_scenario(other_deductions=1500.0))
        with self.assertRaises(ValueError) as cm:
            self.orch.run_full_california_scorp_return(
                s, Path(self._tmp.name) / "o")
        self.assertIn("other_deductions_components", str(cm.exception))

    def test_ca_emit_with_components_emits_ca_titled_statement(self):
        s = self._ca(_with_components(1500.0, _COMPS))
        _r, emitted = self.orch.run_full_california_scorp_return(
            s, Path(self._tmp.name) / "o")
        key = "f100s_other_deductions_stmt"
        self.assertIn(key, emitted)
        text = pypdf.PdfReader(str(emitted[key])).pages[0].extract_text()
        self.assertIn("Form 100S, Schedule F, Line 20", text)
        self.assertIn("Software subscriptions", text)
        self.assertIn("1,500", text)
        self.assertNotIn("1120-S", text)

    def test_ca_emit_zero_other_deductions_emits_none(self):
        s = self._ca(_make_v1_scenario(other_deductions=0.0))
        _r, emitted = self.orch.run_full_california_scorp_return(
            s, Path(self._tmp.name) / "o")
        self.assertNotIn("f100s_other_deductions_stmt", emitted)

    def test_ca_packet_places_statement_after_k1(self):
        from tenforty.pdf_packet import CALIFORNIA_CORPORATE
        self.assertEqual(classify_key("f100s_other_deductions_stmt"),
                         "california_corporate")
        emitted = {k: Path(f"/x/{k}.pdf") for k in (
            "f100s", "f100s_k1_1", "f100s_other_deductions_stmt")}
        names = [p.stem for p in ordered_members(emitted, CALIFORNIA_CORPORATE)]
        self.assertEqual(names, ["f100s", "f100s_k1_1",
                                 "f100s_other_deductions_stmt"])


class PacketTests(unittest.TestCase):
    def test_claimed_by_federal_corporate(self):
        self.assertEqual(classify_key("1120s_other_deductions_stmt"),
                         "federal_corporate")

    def test_placed_adjacent_after_qbi_statements(self):
        emitted = {k: Path(f"/x/{k}.pdf") for k in (
            "1120s", "1120s_k1_1", "1120s_k1_qbi_stmt_1",
            "1120s_other_deductions_stmt")}
        names = [p.stem for p in ordered_members(emitted, FEDERAL_CORPORATE)]
        self.assertEqual(names, ["1120s", "1120s_k1_1", "1120s_k1_qbi_stmt_1",
                                 "1120s_other_deductions_stmt"])


if __name__ == "__main__":
    unittest.main()
