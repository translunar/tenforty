# tests/test_f1040_hoh_lines.py
"""Form 1040 head-of-household lines driven by ``config.head_of_household``:

- the filing-status line "If you checked the HOH or QW/QSS box, enter the
  child's name if the qualifying person is a child but not your dependent",
  every year 2021-2025 (``hoh_qualifying_child_name``);
- the 2025 box "Check if your filing status is MFS or HOH and you lived apart
  from your spouse for the last 6 months of 2025, or you are legally
  separated ..." (``hoh_lived_apart_from_spouse``), with TY2025 married-but-
  legally-separated refusing (the end-of-year household fact is not captured).

The IRS templates carry no /TU, so field identity is geometry (each year's
own widget /Rect against its own printed words, ``pdftotext -bbox``) plus a
fill-and-render ink check. All identities are synthetic.
"""
import dataclasses
import subprocess
import tempfile
import unittest
import unittest.mock
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import orchestrator as orch_mod
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f1040_spine
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import (
    FilingStatus,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    LivedTogetherPeriod,
    SeparationDecreeKind,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params
from tests._pdf_pixels import checked_widgets, dark_pixels_in_rect, widget_rect
from tests.fixtures.spine_battery import _battery_config, build_wages_only
from tests.helpers import CA_SCOPE_OUT_FIELDS

REPO_ROOT = Path(__file__).parent.parent
YEARS = (2021, 2022, 2023, 2024, 2025)
HOH = FilingStatus.HEAD_OF_HOUSEHOLD
CHILD = "hoh_qualifying_child_name"
BOX = "hoh_lived_apart_from_spouse"


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"


def _words(pdf: Path):
    """Page-1 words as (text, x0, y0, x1, y1) in PDF points."""
    xml = subprocess.run(
        ["pdftotext", "-bbox", "-f", "1", "-l", "1", str(pdf), "-"],
        check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(xml)
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    page = root.find(".//x:page", ns)
    height = float(page.get("height"))
    return [((w.text or ""), float(w.get("xMin")), height - float(w.get("yMax")),
             float(w.get("xMax")), height - float(w.get("yMin")))
            for w in page.findall("x:word", ns)]


def _clause_tokens(year: int):
    """(If-token, dependent-token) of the child-name clause on page 1:
    "If you checked the HOH ... child but not your dependent"."""
    words = _words(_template(year))
    texts = [w[0] for w in words]
    ifs = [i for i in range(len(texts) - 4)
           if texts[i] == "If" and texts[i + 1:i + 4] == ["you", "checked", "the"]
           and texts[i + 4] == "HOH"]
    deps = [i for i in range(2, len(texts))
            if texts[i].startswith("dependent") and texts[i - 1] == "your"
            and texts[i - 2] in ("not", "isn't", "isn’t")
            and "child" in texts[max(0, i - 6):i]]
    assert len(ifs) == 1 and len(deps) == 1, (year, ifs, deps)
    return words[ifs[0]], words[deps[0]]


def _lived_apart_caption(year: int):
    """The "Check if your filing status is MFS or HOH" token run's first word."""
    words = _words(_template(year))
    texts = [w[0] for w in words]
    hits = [i for i in range(len(texts) - 7)
            if texts[i:i + 8] == ["Check", "if", "your", "filing", "status",
                                  "is", "MFS", "or"]]
    assert len(hits) == 1, hits
    return words[hits[0]]


def _qp(year: int, **over) -> HohQualifyingPerson:
    fields = dict(
        first_name="Example", last_name="Child", ssn="000000005",
        birthdate=f"{year - 10}-03-07",
        relationship=HohRelationship.CHILD_OR_STEPCHILD,
        full_time_student=None, permanently_disabled=None,
        gross_income=0.0, days_lived_with_you=365,
        claimed_as_dependent=False)
    fields.update(over)
    return HohQualifyingPerson(**fields)


def _facts(year: int, marital=HohMaritalStatus.UNMARRIED, **over):
    periods = ()
    if marital is HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR:
        periods = (LivedTogetherPeriod(start=f"{year}-01-01",
                                       end=f"{year}-02-15"),)
    fields = dict(marital_status=marital, qualifying_person=_qp(year),
                  lived_with_spouse_periods=periods)
    fields.update(over)
    return HeadOfHouseholdFacts(**fields)


def _config(year: int, status: FilingStatus, facts=None):
    over = {}
    if status is FilingStatus.MARRIED_FILING_SEPARATELY:
        over = dict(spouse_first_name="Example", spouse_last_name="Spouse",
                    spouse_ssn="000-00-0002")
    return _battery_config(year, status, head_of_household=facts, **over)


def _fill(year: int, values: dict, out: Path) -> Path:
    return PdfFiller().fill(
        template_path=_template(year), output_path=out,
        field_mapping=Pdf1040.get_mapping(year), values=values,
        checkbox_states=Pdf1040.get_checkbox_states(year))


def _v_overlap(rect, lo, hi) -> float:
    return min(rect[3], hi) - max(rect[1], lo)


class ChildNameGeometryTests(unittest.TestCase):
    """The mapped widget is the box the printed clause points at: on the
    clause's last row or the row just below it, right of "dependent"
    (2021-2024) or inside the clause's column (2025)."""

    def test_child_name_widget_sits_at_the_clause_every_year(self):
        for year in YEARS:
            with self.subTest(year=year):
                path = Pdf1040.get_mapping(year)[CHILD]
                page, rect = widget_rect(_template(year), path)
                self.assertEqual(page, 0)
                if_tok, dep = _clause_tokens(year)
                baseline = dep[2]
                self.assertGreater(_v_overlap(rect, baseline - 14, dep[4]), 0)
                if year <= 2024:
                    self.assertGreaterEqual(rect[0], dep[3])
                    self.assertGreater(_v_overlap(rect, dep[2], dep[4]), 0)
                else:
                    self.assertGreaterEqual(rect[0], if_tok[1])
                    # The row below the clause's last line, not beside it.
                    self.assertLessEqual(rect[3], baseline + 1)

    def test_2025_child_name_is_not_the_mfs_spouse_name_box(self):
        # 2025 prints the MFS "full name here" box on the same band, LEFT of
        # the HoH clause's column.
        path = Pdf1040.get_mapping(2025)[CHILD]
        _p, rect = widget_rect(_template(2025), path)
        _p, mfs = widget_rect(
            _template(2025),
            "topmostSubform[0].Page1[0].Checkbox_ReadOrder[0].f1_28[0]")
        self.assertGreater(rect[0], mfs[2])


class ChildNameInkTests(unittest.TestCase):

    def test_child_name_reads_back_and_prints_ink(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            with self.subTest(year=year):
                path = Pdf1040.get_mapping(year)[CHILD]
                out = _fill(year, {CHILD: "Example Child"},
                            tmp / f"f1040_{year}.pdf")
                fields = PdfReader(str(out)).get_fields()
                self.assertEqual(str(fields[path].get("/V")), "Example Child")
                page, rect = widget_rect(out, path)
                self.assertGreater(
                    dark_pixels_in_rect(out, page, rect, inset=1.0), 8)


class ChildNameNoCollisionTests(unittest.TestCase):

    def test_child_name_path_has_exactly_one_key(self):
        for year in YEARS:
            with self.subTest(year=year):
                mapping = Pdf1040.get_mapping(year)
                path = mapping[CHILD]
                self.assertEqual(
                    [k for k, v in mapping.items() if v == path], [CHILD])

    def test_lived_apart_box_has_exactly_one_key(self):
        mapping = Pdf1040.get_mapping(2025)
        path = mapping[BOX]
        self.assertEqual([k for k, v in mapping.items() if v == path], [BOX])
        for year in (2021, 2022, 2023, 2024):
            with self.subTest(year=year):
                self.assertNotIn(BOX, Pdf1040.get_mapping(year))


class HeaderValuesHohTests(unittest.TestCase):

    def test_hoh_with_block_carries_the_child_name(self):
        for year in YEARS:
            with self.subTest(year=year):
                out = f1040_spine.header_values(
                    _config(year, HOH, _facts(year)))
                self.assertEqual(out[CHILD], "Example Child")

    def test_other_statuses_with_a_stray_block_refuse(self):
        # A directly built config carrying a stray block (the loader refuses
        # it): the federal header refuses it too, naming the cause.
        for year in YEARS:
            for status in (FilingStatus.SINGLE,
                           FilingStatus.MARRIED_FILING_JOINTLY,
                           FilingStatus.MARRIED_FILING_SEPARATELY):
                with self.subTest(year=year, status=status):
                    with self.assertRaises(ValueError) as cm:
                        f1040_spine.header_values(
                            _config(year, status, _facts(year)))
                    msg = str(cm.exception)
                    self.assertIn("has a `head_of_household` block", msg)
                    self.assertIn(f"`filing_status` is `{status.value}`", msg)

    def test_other_statuses_without_a_block_carry_neither_key(self):
        for year in YEARS:
            for status in (FilingStatus.SINGLE,
                           FilingStatus.MARRIED_FILING_JOINTLY,
                           FilingStatus.MARRIED_FILING_SEPARATELY):
                with self.subTest(year=year, status=status):
                    out = f1040_spine.header_values(_config(year, status))
                    self.assertNotIn(CHILD, out)
                    self.assertNotIn(BOX, out)

    def test_hoh_lines_keys_follow_the_status_not_the_block(self):
        # _hoh_lines' own status check, called directly with a stray block
        # (header_values refuses it first): only the status keeps the keys
        # out, so this negative is reachable.
        for year in YEARS:
            for status in (FilingStatus.SINGLE,
                           FilingStatus.MARRIED_FILING_JOINTLY,
                           FilingStatus.MARRIED_FILING_SEPARATELY):
                with self.subTest(year=year, status=status):
                    self.assertEqual(f1040_spine._hoh_lines(
                        _config(year, status, _facts(year))), {})
            with self.subTest(year=year, status=HOH):
                self.assertIn(CHILD, f1040_spine._hoh_lines(
                    _config(year, HOH, _facts(year))))

    def test_box_key_is_2025_only(self):
        for year in (2021, 2022, 2023, 2024):
            for marital in HohMaritalStatus:
                with self.subTest(year=year, marital=marital):
                    over = {}
                    if marital is HohMaritalStatus.DIVORCED_OR_LEGALLY_SEPARATED:
                        over = dict(separation_decree_kind=(
                            SeparationDecreeKind.LEGAL_SEPARATION))
                    out = f1040_spine.header_values(
                        _config(year, HOH, _facts(year, marital, **over)))
                    self.assertNotIn(BOX, out)
                    self.assertIn(CHILD, out)
        out = f1040_spine.header_values(_config(2025, HOH, _facts(2025)))
        self.assertIn(BOX, out)


class LivedApartBoxTests(unittest.TestCase):
    """2025: 1e and 1f check the box; 1a/1b/1c and 1d+divorce leave it off."""

    CASES = (
        ("1e", HohMaritalStatus.MARRIED_LIVED_APART_ALL_YEAR, {}, True),
        ("1f", HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR, {}, True),
        ("1d+divorce", HohMaritalStatus.DIVORCED_OR_LEGALLY_SEPARATED,
         dict(separation_decree_kind=SeparationDecreeKind.DIVORCE_OR_DISSOLUTION),
         False),
        ("1a", HohMaritalStatus.UNMARRIED, {}, False),
        ("1b", HohMaritalStatus.SURVIVING_SPOUSE, {}, False),
        ("1c", HohMaritalStatus.MARRIAGE_ANNULLED, {}, False),
    )

    def test_box_value_and_fill_per_marital_status(self):
        tmp = Path(tempfile.mkdtemp())
        path = Pdf1040.get_mapping(2025)[BOX]
        for label, marital, over, expected in self.CASES:
            with self.subTest(case=label):
                out = f1040_spine.header_values(
                    _config(2025, HOH, _facts(2025, marital, **over)))
                self.assertIs(out[BOX], expected)
                pdf = _fill(2025, {BOX: out[BOX]}, tmp / f"box_{label}.pdf")
                on = {n: s for _p, n, _r, s in checked_widgets(pdf)}
                page, rect = widget_rect(pdf, path)
                if expected:
                    self.assertEqual(on.get(path), "/1")
                    self.assertGreater(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 8)
                else:
                    self.assertNotIn(path, on)

    def test_box_sits_left_of_its_caption_on_its_row(self):
        path = Pdf1040.get_mapping(2025)[BOX]
        page, rect = widget_rect(_template(2025), path, on_state="/1")
        self.assertEqual(page, 0)
        check = _lived_apart_caption(2025)
        self.assertGreater(_v_overlap(rect, check[2], check[4]), 0)
        self.assertLessEqual(rect[2], check[1])
        self.assertLess(check[1] - rect[2], 12)
        self.assertEqual(Pdf1040.get_checkbox_states(2025)[BOX], "/1")


class LegalSeparation2025RefusalTests(unittest.TestCase):

    def _facts(self, year):
        return _facts(year, HohMaritalStatus.DIVORCED_OR_LEGALLY_SEPARATED,
                      separation_decree_kind=SeparationDecreeKind.LEGAL_SEPARATION)

    def test_ty2025_legal_separation_refuses(self):
        cfg = _config(2025, HOH, self._facts(2025))
        with self.assertRaises(NotImplementedError) as cm:
            f1040_spine.header_values(cfg)
        msg = str(cm.exception)
        self.assertIn("same household", msg)
        self.assertIn("by hand", msg)
        with self.assertRaises(NotImplementedError):
            f1040_spine.refuse_ty2025_legal_separation(cfg)

    def test_2024_legal_separation_does_not_refuse(self):
        cfg = _config(2024, HOH, self._facts(2024))
        f1040_spine.refuse_ty2025_legal_separation(cfg)
        out = f1040_spine.header_values(cfg)
        self.assertNotIn(BOX, out)

    def test_ty2025_divorce_does_not_refuse(self):
        cfg = _config(2025, HOH, _facts(
            2025, HohMaritalStatus.DIVORCED_OR_LEGALLY_SEPARATED,
            separation_decree_kind=SeparationDecreeKind.DIVORCE_OR_DISSOLUTION))
        f1040_spine.refuse_ty2025_legal_separation(cfg)

    def test_refused_emit_writes_no_federal_pdf(self):
        base = build_wages_only(2025, HOH)
        scenario = dataclasses.replace(base, config=dataclasses.replace(
            base.config, head_of_household=self._facts(2025)))
        tmp = Path(tempfile.mkdtemp())
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=tmp / "work")
        out = tmp / "out"
        with unittest.mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook path reached")):
            self.assertTrue(orch._scenario_in_spine_scope(scenario))
            with self.assertRaises(NotImplementedError):
                orch.run_full_return(scenario, out)
        self.assertEqual(sorted(out.glob("*.pdf")) if out.exists() else [], [])


class HohLinesBothPathsTests(unittest.TestCase):
    """The child-name key reaches the 1040 on the native spine AND on the
    workbook path's header merge (shared header_values). The workbook engine
    is patched: no LibreOffice."""

    def _scenario(self, year):
        base = build_wages_only(year, HOH)
        return dataclasses.replace(base, config=dataclasses.replace(
            base.config, head_of_household=_facts(year)))

    def test_native_compute_carries_the_child_name(self):
        year = 2024
        scenario = self._scenario(year)
        ceilings = load_federal_params(year).eic_income_ceiling
        self.assertGreater(sum(w.wages for w in scenario.w2s), ceilings[1])
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=Path(tempfile.mkdtemp()))
        with unittest.mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook path reached")):
            self.assertTrue(orch._scenario_in_spine_scope(scenario))
            results = orch.compute_federal(scenario)
        self.assertEqual(results[CHILD], "Example Child")

    def test_workbook_header_merge_carries_the_child_name(self):
        year = 2024
        scenario = self._scenario(year)
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=Path(tempfile.mkdtemp()))
        with unittest.mock.patch.object(orch.engine, "compute",
                                        return_value={}) as engine, \
                unittest.mock.patch.object(orch_mod.form_1040, "compute",
                                           return_value={}):
            results = orch._compute_1040_via_workbook(scenario)
        engine.assert_called_once()
        self.assertEqual(results[CHILD], "Example Child")


class FederalHohBackstopTests(unittest.TestCase):
    """The federal 1040 runs validate_head_of_household itself (via
    header_values, shared by compute, emit and 1040-X), so a directly built
    TaxReturnConfig -- which never passes the loader -- cannot compute or
    emit a head-of-household 1040 the loader would refuse. The workbook
    path is patched to fail: native throughout, no LibreOffice."""

    YEAR = 2025

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")
        patcher = unittest.mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=AssertionError("workbook path reached"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _scenario(self, facts):
        base = build_wages_only(self.YEAR, HOH)
        scenario = dataclasses.replace(base, config=dataclasses.replace(
            base.config, head_of_household=facts))
        self.assertTrue(self.orch._scenario_in_spine_scope(scenario))
        return scenario

    def _rule_10_violation(self):
        return _facts(self.YEAR, qualifying_person=_qp(
            self.YEAR, days_lived_with_you=100))

    def test_hoh_without_the_block_refuses_federal_compute(self):
        scenario = self._scenario(None)
        with self.assertRaises(ValueError) as cm:
            self.orch.compute_federal(scenario)
        self.assertIn("no `head_of_household` block", str(cm.exception))

    def test_rule_10_violation_refuses_federal_emit_writing_no_pdf(self):
        scenario = self._scenario(self._rule_10_violation())
        out = self.tmp / "out"
        with self.assertRaises(ValueError) as cm:
            self.orch.run_full_return(scenario, out)
        self.assertIn("more than half the year", str(cm.exception))
        self.assertEqual(sorted(out.glob("*.pdf")) if out.exists() else [], [])

    def test_rule_10_violation_still_refuses_on_the_ca_path(self):
        base = self._scenario(self._rule_10_violation())
        scenario = dataclasses.replace(base, config=dataclasses.replace(
            base.config, full_year_health_care_coverage=True,
            **{k: True for k in CA_SCOPE_OUT_FIELDS}))
        ca_yaml = self.tmp / "ca.yaml"
        ca_yaml.write_text(yaml.safe_dump(
            {"ca540": {"interest_and_penalties": 0.0}}))
        out = self.tmp / "ca"
        with self.assertRaises(ValueError) as cm:
            self.orch.run_full_california_return(
                scenario=scenario, ca_yaml_path=ca_yaml, output_dir=out)
        self.assertIn("more than half the year", str(cm.exception))
        self.assertEqual(sorted(out.glob("*")) if out.exists() else [], [])

    def test_claimed_dependent_refuses_federal_compute(self):
        # M3 through the federal backstop: a directly built config whose
        # qualifying person is claimed as a dependent.
        scenario = self._scenario(_facts(self.YEAR, qualifying_person=_qp(
            self.YEAR, claimed_as_dependent=True)))
        with self.assertRaises(NotImplementedError) as cm:
            self.orch.compute_federal(scenario)
        self.assertIn("Child Tax Credit", str(cm.exception))

    def test_non_boolean_claimed_as_dependent_refuses_the_federal_header(self):
        # A directly built config skips the loader's type check; the
        # backstop proceeds only on False.
        for value in ("true", 1, "false"):
            with self.subTest(value=value):
                cfg = _config(self.YEAR, HOH, _facts(
                    self.YEAR, qualifying_person=_qp(
                        self.YEAR, claimed_as_dependent=value)))
                with self.assertRaises(ValueError) as cm:
                    f1040_spine.header_values(cfg)
                self.assertIn("claimed_as_dependent", str(cm.exception))
                self.assertIn("true or false", str(cm.exception))

    def test_dashed_qp_ssn_equal_to_the_filers_refuses_the_federal_header(self):
        # Rule 5 compares digits on both sides: a directly built qualifying
        # person keeps whatever SSN shape it was given.
        cfg = dataclasses.replace(
            _config(self.YEAR, HOH, _facts(self.YEAR, qualifying_person=_qp(
                self.YEAR, ssn="000-00-0001"))),
            ssn="000-00-0001")
        with self.assertRaises(ValueError) as cm:
            f1040_spine.header_values(cfg)
        self.assertIn("same as the filer's own SSN", str(cm.exception))
