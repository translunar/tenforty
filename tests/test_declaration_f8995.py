"""The Form 8995 declaration validates against each year's own inventory,
covers every computation key, binds the seam keys by meaning, and its anchors
locate their fields (emit-verification protocol step 4; adjudication
/private/tmp/pilot-packet-f8995).

The declaration is inert until graduation: registration and the pending
removal land together, so these tests read the module directly, not the
registry.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import f8995, propose, registry
from tenforty.declarations.anchors import (FieldRelation, LabelRelation,
                                           NearField, NearLabel)
from tenforty.declarations.model import expand
from tenforty.declarations.validate import exemptions_in_force, validate
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification import emit_manifest
from tenforty.verification.batteries import BATTERIES
from tenforty.verification.checks import check_placement
from tenforty.verification.coverage import coverage_cells
from tenforty.verification.fill import fill_spec_for
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "f8995")
S = ""

# The computation's Form 8995 output keys (names only; source-enumerated:
# /private/tmp/pilot-packet-f8995/output_keys_f8995.txt).
OUTPUT_KEYS = frozenset({
    "f8995_line_11_taxable_income", "f8995_line_12_net_capital_gain",
    "f8995_line_13_subtract", "f8995_line_14_income_limit",
    "f8995_line_15_qbi_deduction", "f8995_line_16_qbi_loss_carryforward",
    "f8995_line_1_qbi", "f8995_line_1i_name", "f8995_line_1i_tin",
    "f8995_line_2_total_qbi", "f8995_line_3_component",
    "f8995_line_3_prior_qbi_loss_carryforward", "f8995_line_4_reit_ptp",
    "f8995_line_4_total_qbi", "f8995_line_5_reit_ptp_component",
    "f8995_line_6_total_before_limit",
    "f8995_line_7_prior_reit_ptp_loss_carryforward",
    "f8995_line_8_total_reit_ptp", "taxpayer_name", "taxpayer_ssn",
})
# Printed line -> key, bound by meaning (the seam), every year.
SEAM = {
    "3": "f8995_line_3_prior_qbi_loss_carryforward",
    "4": "f8995_line_4_total_qbi",
    "5": "f8995_line_3_component",
    "6": "f8995_line_4_reit_ptp",
    "9": "f8995_line_5_reit_ptp_component",
    "10": "f8995_line_6_total_before_limit",
}
ROW_I = ("1i(a)", "1i(b)", "1i(c)")


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f8995.pdf"


def _lines(year):
    return {ln.line: ln for ln in f8995.DECLARATIONS[year].lines}


class F8995DeclarationValidatesTests(unittest.TestCase):

    def test_each_year_declared(self):
        self.assertEqual(sorted(f8995.DECLARATIONS), list(YEARS))
        for year in YEARS:
            with self.subTest(year=year):
                decl = f8995.DECLARATIONS[year]
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(f8995.DECLARATIONS[year],
                                    siblings=f8995.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_line_counts(self):
        # Adjudicated: 23 declared, 32 expanded (rows ii-v x 3 columns).
        for year in YEARS:
            decl = f8995.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertEqual(len(decl.lines), 23)
                self.assertEqual(len(expand(decl, {})), 32)

    def test_exactly_the_row_i_cells_are_inventory_exempt(self):
        # The inventory prints bare row ids (1i..1v), not the three cells.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    [line_id for line_id, _ in exemptions_in_force(
                        f8995.DECLARATIONS[year])],
                    [(S, cell) for cell in ROW_I])

    def test_still_pending(self):
        # Graduation (registration + unpending) is a later, separate lane.
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


class F8995KeyCoverageTests(unittest.TestCase):

    def test_every_output_key_is_bound_or_not_printed(self):
        for year in YEARS:
            decl = f8995.DECLARATIONS[year]
            bound = {ln.key for ln in expand(decl, {}) if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound | set(decl.not_printed), OUTPUT_KEYS)
                self.assertEqual(bound & set(decl.not_printed), set())

    def test_header_keys_are_presentation_only(self):
        for year in YEARS:
            np = f8995.DECLARATIONS[year].not_printed
            with self.subTest(year=year):
                self.assertEqual(set(np), {"taxpayer_name", "taxpayer_ssn"})
                for reason in np.values():
                    self.assertTrue(reason.startswith("presentation-only:"))


class F8995BindByMeaningTests(unittest.TestCase):

    def test_the_seam_keys_bind_their_printed_lines(self):
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                self.assertEqual({n: lines[n].key for n in SEAM}, SEAM)

    def test_row_i_binds_the_single_source_keys(self):
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                self.assertEqual(
                    [lines[cell].key for cell in ROW_I],
                    ["f8995_line_1i_name", "f8995_line_1i_tin",
                     "f8995_line_1_qbi"])


class F8995AdjudicatedTextTests(unittest.TestCase):

    def test_adjudicated_kinds(self):
        # Ruling 2: the caption row is text; ruling 3: the TIN cells are
        # text (an SSN or an EIN), never the "ssn" kind.
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                self.assertEqual(lines["1"].kind, "text")
                self.assertEqual(lines["1i(b)"].kind, "text")
                self.assertEqual(lines["1{i}(b)"].kind, "text")

    def test_cell_descriptions_are_the_paper_column_headings(self):
        # Ruling 5: verbatim paper column headings (pdftotext of the
        # templates prints "(a) Trade, business, or aggregation name", ...).
        headings = {"a": "(a) Trade, business, or aggregation name",
                    "b": "(b) Taxpayer identification number",
                    "c": "(c) Qualified business income or (loss)"}
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                for col, text in headings.items():
                    self.assertEqual(lines[f"1i({col})"].description, text)
                    self.assertEqual(lines["1{i}(" + col + ")"].description,
                                     text)

    def test_row_i_anchor_chain(self):
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                self.assertEqual(lines["1i(a)"].anchor,
                                 NearLabel("i", LabelRelation.RIGHT_OF))
                self.assertEqual(
                    lines["1i(b)"].anchor,
                    NearField("1i(a)", FieldRelation.SAME_ROW_RIGHT_OF))
                self.assertEqual(
                    lines["1i(c)"].anchor,
                    NearField("1i(b)", FieldRelation.SAME_ROW_RIGHT_OF))


class F8995ValueOnlyTests(unittest.TestCase):
    """R3 ruling: every bound line is value-only, grounded in the producer
    (forms/f8995.compute) and the paper line, never in battery
    observation."""

    def test_exactly_the_bound_lines_are_value_only(self):
        for year in YEARS:
            decl = f8995.DECLARATIONS[year]
            bound = sorted(ln.line for ln in decl.lines if ln.key)
            value_only = sorted(ln.line for ln in decl.lines
                                if ln.single_state == "value")
            with self.subTest(year=year):
                self.assertEqual(len(bound), 18)
                self.assertEqual(value_only, bound)

    def test_each_reason_cites_the_producer(self):
        # Amount lines also say a computed zero is a value (it prints).
        for year in YEARS:
            for ln in f8995.DECLARATIONS[year].lines:
                if not ln.key:
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertIn("forms/f8995.compute",
                                  ln.single_state_reason)
                    self.assertIn("_should_emit_8995",
                                  ln.single_state_reason)
                    if ln.kind == "amount":
                        self.assertIn("zero is a value",
                                      ln.single_state_reason)


class F8995PlacementTests(unittest.TestCase):

    def test_every_bound_line_is_placed(self):
        for year in YEARS:
            findings = check_placement(_template(year),
                                       f8995.DECLARATIONS[year],
                                       fill_spec_for(PdfF8995, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_explicit_phrases_print_exactly_once(self):
        for year in YEARS:
            words = anchor_eval._page_words(str(_template(year)), 0)
            for ln in f8995.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)


class F8995WitnessDiscrepancyTests(unittest.TestCase):
    """The documented witness discrepancies are exactly the stylesheet
    cross-check's raw findings: 16 per year, 17 in 2023."""

    def _raw(self, decl):
        return crosscheck_mod.crosscheck(
            decl, propose.stylesheet_lines("f8995", decl.key))

    def test_in_force_set_is_exactly_the_raw_findings(self):
        for year in YEARS:
            decl = f8995.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            in_force = crosscheck_mod.discrepancies_in_force(f8995, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in self._raw(decl)})
                self.assertEqual(len(in_force), 17 if year == 2023 else 16)

    def test_documented_discrepancies_leave_no_finding(self):
        for year in YEARS:
            decl = f8995.DECLARATIONS[year]
            findings = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("f8995", year),
                discrepancies=crosscheck_mod.discrepancies_in_force(
                    f8995, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_notes_suppress_nothing(self):
        # Line 15's "lesser" vs "smaller" draws no raw finding, so it is a
        # note, never a discrepancy entry.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertNotIn((S, "15"), crosscheck_mod.
                                 discrepancies_in_force(f8995, year))
        self.assertIn((S, "15"), f8995.WITNESS_NOTES)


COVERED_BATTERIES = ("spine_battery", "sch_c_battery", "emit_battery_sch_se",
                     "emit_battery_sch_c")


def _f8995_records():
    """(row id, RecordedForm) for every Form 8995 the covered batteries emit
    natively (states observed, no expected values)."""
    manifest = emit_manifest.load_manifest()
    records = []
    for battery in BATTERIES:
        if battery.name not in COVERED_BATTERIES:
            continue
        for name, year, build in battery.scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = manifest.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            if not any(f.startswith("federal/f8995") for f in row["forms"]):
                continue
            out = Path(tempfile.mkdtemp()) / "out"
            records += [(rid, rec) for rec in emit_manifest.emit(
                battery, build(), out).record if rec.form == FORM]
    return records


class F8995CoverageTests(unittest.TestCase):
    """Coverage over this declaration (read directly; not registered until
    graduation) from the existing batteries: no new battery (R3)."""

    @classmethod
    def setUpClass(cls):
        cls.records = _f8995_records()

    def test_every_year_has_records(self):
        self.assertEqual(sorted({rec.key for _, rec in self.records}),
                         list(YEARS))

    def test_no_cell_is_uncovered(self):
        decls = [f8995.DECLARATIONS[y] for y in YEARS]
        report = coverage_cells(self.records, decls)
        self.assertEqual(list(report.uncovered), [], "\n".join(
            map(str, report.uncovered)))
