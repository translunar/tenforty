"""The Schedule C declaration validates against each year's own inventory,
covers every computation key, and its anchors locate their fields
(emit-verification protocol step 4).

The declaration is inert until graduation: registration and the pending
removal land together, so this test reads the module directly, not the
registry.
"""
import dataclasses
import unittest
from pathlib import Path

from tenforty.declarations import sch_c
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.validate import validate
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.verification import anchors as anchor_eval
from tenforty.verification.checks import check_placement
from tenforty.verification.fill import fill_spec_for
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "sch_c")

# The computation's Schedule C output keys (names only; the source-
# enumerated v2 list of the delta round).
OUTPUT_KEYS = frozenset({
    "sch_c_expense_advertising", "sch_c_expense_deductible_meals",
    "sch_c_expense_insurance", "sch_c_expense_legal_professional",
    "sch_c_expense_office_expense", "sch_c_expense_other_expenses",
    "sch_c_expense_rent_lease", "sch_c_expense_supplies",
    "sch_c_expense_taxes_licenses", "sch_c_expense_travel",
    "sch_c_expense_utilities", "sch_c_expense_wages",
    "sch_c_line_1_gross_receipts", "sch_c_line_3_net_receipts",
    "sch_c_line_5_gross_profit", "sch_c_line_7_gross_income",
    "sch_c_line_13_depreciation", "sch_c_line_28_total_expenses",
    "sch_c_line_29_tentative_profit", "sch_c_line_31_net_profit",
    "sch_c_line_32a_all_investment_at_risk",
    "sch_c_line_48_total_other_expenses", "sch_c_line_a_description",
    "sch_c_line_b_business_code", "sch_c_line_f_cash_method",
    "sch_c_line_g_material_participation",
    "sch_c_part_v_row_1_amount", "sch_c_part_v_row_1_description",
    "taxpayer_name", "taxpayer_ssn",
})
# Part V row 1 has no anchor yet (no below-a-heading relation exists); its
# inventory exemption excludes it from placement (ADDENDUM 3, ruling b1).
_UNLOCATED = {("Part V", "row1(description)"), ("Part V", "row1(amount)")}


class SchCDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_c.DECLARATIONS), list(YEARS))
        for year in YEARS:
            with self.subTest(year=year):
                decl = sch_c.DECLARATIONS[year]
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_c.DECLARATIONS[year])
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_still_pending(self):
        # Graduation (registration + unpending) is a later, separate lane.
        self.assertIn(FORM, PENDING_DECLARATIONS)


class SchCKeyCoverageTests(unittest.TestCase):
    """Bound lines plus not_printed account for every output key, every
    year, and nothing else is bound."""

    def test_every_output_key_is_bound_or_not_printed(self):
        for year in YEARS:
            decl = sch_c.DECLARATIONS[year]
            bound = {ln.key for ln in decl.lines if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound | set(decl.not_printed), OUTPUT_KEYS)
                self.assertEqual(bound & set(decl.not_printed), set())

    def test_header_keys_are_presentation_only(self):
        for year in YEARS:
            with self.subTest(year=year):
                np = sch_c.DECLARATIONS[year].not_printed
                self.assertEqual(sorted(np), ["taxpayer_name", "taxpayer_ssn"])
                for reason in np.values():
                    self.assertTrue(reason.startswith("presentation-only:"))


class SchCPlacementTests(unittest.TestCase):
    """The harness's own placement check (check_placement: each bound line's
    field where its explicit or default anchor says) on each year's
    official template. Part V row 1 is excluded by its inventory exemption
    inside check_placement itself."""

    def test_every_bound_line_is_placed(self):
        for year in YEARS:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"
            findings = check_placement(
                template, sch_c.DECLARATIONS[year], fill_spec_for(PdfSchC, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_part_v_row_1_has_no_anchor_yet(self):
        for year in YEARS:
            for ln in sch_c.DECLARATIONS[year].lines:
                if ln.line_id in _UNLOCATED:
                    with self.subTest(year=year, line=ln.line):
                        self.assertIsNone(ln.anchor)


class CheckboxAnchorRectTests(unittest.TestCase):
    """A checkbox-printed key's explicit anchor is verified against the
    widget's rectangle (ruling b3): the bool key resolves through the
    mapping (and its checkbox state) to the box, and check_placement
    evaluates the anchor on that box."""

    def _placement_lines(self, year, decl):
        template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"
        return {f.line for f in check_placement(
            template, decl, fill_spec_for(PdfSchC, year))}

    def test_line_f_places_on_its_cash_box(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertNotIn("F", self._placement_lines(
                    year, sch_c.DECLARATIONS[year]))

    def test_line_f_anchored_to_the_accrual_box_is_refused(self):
        # Negative space: the Accrual box's own label does not locate the
        # Cash box.
        for year in YEARS:
            decl = sch_c.DECLARATIONS[year]
            lines = tuple(
                dataclasses.replace(ln, anchor=NearLabel(
                    "Accrual", LabelRelation.LEFT_OF)) if ln.line == "F" else ln
                for ln in decl.lines)
            with self.subTest(year=year):
                self.assertIn("F", self._placement_lines(
                    year, dataclasses.replace(decl, lines=lines)))

    def _anchor(self, year, line):
        return next(ln.anchor for ln in sch_c.DECLARATIONS[year].lines
                    if ln.line == line)

    def test_line_g_and_32a_anchors_reject_their_neighbouring_box(self):
        # Negative space: G's anchor does not locate the No box beside it;
        # 32a's caption does not locate 32b's box one row down.
        neighbour = {"G": "topmostSubform[0].Page1[0].c1_2[1]",
                     "32a": "topmostSubform[0].Page1[0].c1_7[1]"}
        for year in YEARS:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"
            for line, other_box in neighbour.items():
                with self.subTest(year=year, line=line):
                    self.assertIsNotNone(anchor_eval.evaluate(
                        self._anchor(year, line), other_box, template))


if __name__ == "__main__":
    unittest.main()
