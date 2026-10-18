"""The Schedule 1 declaration validates against each year's own inventory,
covers every computation key, binds by meaning, and its anchors locate
their fields (emit-verification protocol step 4; adjudication
/private/tmp/pilot-packet-sch_1).

The declaration is inert until graduation: registration and the pending
removal land together, so these tests read the module directly, not the
registry.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry, sch_1
from tenforty.declarations.model import expand
from tenforty.declarations.validate import exemptions_in_force, validate
from tenforty.mappings.pdf_sch_1 import PdfSch1
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
FORM = ("federal", "sch_1")
P1, P2 = "Part I", "Part II"

# The computation's Schedule 1 output keys (names only; source-enumerated).
OUTPUT_KEYS = frozenset({
    "sch_1_line_10_total_additional_income", "sch_1_line_11_educator",
    "sch_1_line_13_hsa", "sch_1_line_15_se_tax", "sch_1_line_17_se_health",
    "sch_1_line_1_taxable_refunds", "sch_1_line_20_ira",
    "sch_1_line_21_student_loan_interest", "sch_1_line_26_total_adjustments",
    "sch_1_line_3_business_income", "sch_1_line_4_other_gains",
    "sch_1_line_5_rental_re_royalty", "sch_1_line_6_farm_income",
    "sch_1_line_7_unemployment", "sch_1_line_8z_other_income",
    "sch_1_line_8z_description", "sch_1_line_8z_statement_rows",
    "sch_1_line_9_total_other_income",
    "taxpayer_name", "taxpayer_ssn",
})
# Each non-header key binds the paper line its meaning names, every year.
BINDINGS = {
    (P1, "1"): "sch_1_line_1_taxable_refunds",
    (P1, "3"): "sch_1_line_3_business_income",
    (P1, "4"): "sch_1_line_4_other_gains",
    (P1, "5"): "sch_1_line_5_rental_re_royalty",
    (P1, "6"): "sch_1_line_6_farm_income",
    (P1, "7"): "sch_1_line_7_unemployment",
    (P1, "8z"): "sch_1_line_8z_other_income",
    (P1, "8z(type)"): "sch_1_line_8z_description",
    (P1, "9"): "sch_1_line_9_total_other_income",
    (P1, "10"): "sch_1_line_10_total_additional_income",
    (P2, "11"): "sch_1_line_11_educator",
    (P2, "13"): "sch_1_line_13_hsa",
    (P2, "15"): "sch_1_line_15_se_tax",
    (P2, "17"): "sch_1_line_17_se_health",
    (P2, "20"): "sch_1_line_20_ira",
    (P2, "21"): "sch_1_line_21_student_loan_interest",
    (P2, "26"): "sch_1_line_26_total_adjustments",
}
# Paper lines plus the 8z type write-in cell (declared as its own line).
LINE_COUNTS = {2021: 59, 2022: 64, 2023: 64, 2024: 65, 2025: 65}
# Two-state bound lines (team-lead R2): absent when no Form 1099-G type is
# nonzero, so the write-in and subtotal stay blank.
TWO_STATE = {(P1, "8z"), (P1, "8z(type)"), (P1, "9")}


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040s1.pdf"


def _lines(year):
    return {ln.line_id: ln for ln in sch_1.DECLARATIONS[year].lines}


class SchOneDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_1.DECLARATIONS), list(YEARS))
        for year in YEARS:
            with self.subTest(year=year):
                decl = sch_1.DECLARATIONS[year]
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_1.DECLARATIONS[year],
                                    siblings=sch_1.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_line_counts(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(len(sch_1.DECLARATIONS[year].lines),
                                 LINE_COUNTS[year])

    def test_each_year_is_its_full_table(self):
        # Each year is a derive() diff from the previous one; the diff must
        # reproduce that year's full table exactly (author A's technique).
        # derive() appends changed lines, so compare by line id.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    {ln.line_id: ln for ln in sch_1.DECLARATIONS[year].lines},
                    {ln.line_id: ln for ln in sch_1.full_table(year)})

    def test_still_pending(self):
        # Graduation (registration + unpending) is a later, separate lane.
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


class SchOneKeyCoverageTests(unittest.TestCase):
    def test_every_output_key_is_bound_or_not_printed(self):
        for year in YEARS:
            decl = sch_1.DECLARATIONS[year]
            bound = {ln.key for ln in decl.lines if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound | set(decl.not_printed), OUTPUT_KEYS)
                self.assertEqual(bound & set(decl.not_printed), set())

    def test_not_printed_keys(self):
        # The header keys are presentation-only; the 8z statement rows feed
        # the attached statement, never a Schedule 1 field.
        for year in YEARS:
            np = sch_1.DECLARATIONS[year].not_printed
            with self.subTest(year=year):
                self.assertEqual(sorted(np), [
                    "sch_1_line_8z_statement_rows", "taxpayer_name",
                    "taxpayer_ssn"])
                self.assertTrue(np["taxpayer_name"].startswith(
                    "presentation-only:"))
                self.assertTrue(np["taxpayer_ssn"].startswith(
                    "presentation-only:"))
                self.assertTrue(np["sch_1_line_8z_statement_rows"].startswith(
                    "intermediate:"))

    def test_each_key_binds_its_line_every_year(self):
        for year in YEARS:
            bound = {ln.line_id: ln.key for ln in sch_1.DECLARATIONS[year].lines
                     if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound, BINDINGS)


class SchOneAdjudicatedTests(unittest.TestCase):
    def test_2025_line_7_mef_is_the_amount_element(self):
        # Ruling 2: the 2025 stylesheet lists UnemploymentCompAmt.
        self.assertEqual(_lines(2025)[(P1, "7")].mef_element,
                         "UnemploymentCompAmt")

    def test_the_papers_own_typo_is_kept_on_8t(self):
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertIn("nonqualifed", _lines(year)[(P1, "8t")].description)

    def test_2022_cross_references_follow_the_paper(self):
        lines = _lines(2022)
        self.assertIn("line 8l", lines[(P2, "24b")].description)
        self.assertIn("line 8m", lines[(P2, "24c")].description)

    def test_19b_and_19c_are_exempt_only_while_the_inventory_lacks_them(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    sorted(line_id for line_id, _ in exemptions_in_force(
                        sch_1.DECLARATIONS[year])),
                    sorted([(P1, "8z(type)")] + (
                        [(P2, "19b"), (P2, "19c")] if year < 2024 else [])))


class SchOneValueOnlyTests(unittest.TestCase):
    def test_every_bound_line_but_8z_and_9_is_value_only(self):
        # The computation emits every non-header key on every Schedule 1
        # (zeros included) except the 8z amount, its type write-in and line
        # 9, which are absent when no 1099-G type is nonzero (R2), so they
        # are two-state.
        for year in YEARS:
            with self.subTest(year=year):
                for ln in sch_1.DECLARATIONS[year].lines:
                    if not ln.key:
                        continue
                    if ln.line_id in TWO_STATE:
                        self.assertIsNone(ln.single_state, ln.line)
                        continue
                    self.assertEqual(ln.single_state, "value", ln.line)
                    self.assertIn("unconditionally",
                                  ln.single_state_reason)


class SchOnePlacementTests(unittest.TestCase):
    def _findings(self, year):
        return check_placement(_template(year), sch_1.DECLARATIONS[year],
                               fill_spec_for(PdfSch1, year))

    def test_every_bound_line_is_placed(self):
        # Formerly the sch_1-8z-9-mapping-gap known finding on 8z: the
        # mapping now places 8z, its type write-in and line 9 every year.
        for year in YEARS:
            findings = self._findings(year)
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_the_8z_type_anchor_rejects_its_rowmates(self):
        # The write-in's anchor accepts its own field and rejects the
        # second description row and line 9. In 2022-2023 it also accepts
        # the 8z amount field (both overlap the caption row); a swap of the
        # two is still caught, because the amount's RIGHT_OF "8z" anchor
        # rejects the write-in field every year.
        root = {y: "form1[0]" if y < 2025 else "topmostSubform[0]"
                for y in YEARS}
        row_2 = {2021: "f1_28", 2022: "f1_33", 2023: "f1_33", 2024: "f1_35"}
        line_9 = {2021: "f1_30", 2022: "f1_35", 2023: "f1_35", 2024: "f1_37",
                  2025: "f1_37"}
        for year in YEARS:
            template = _template(year)
            page1 = f"{root[year]}.Page1[0]"
            mapping = PdfSch1.get_mapping(year)["scalars"]
            write_in = mapping["sch_1_line_8z_description"]
            amount = mapping["sch_1_line_8z_other_income"]
            lines = _lines(year)
            anchor = lines[(P1, "8z(type)")].anchor
            with self.subTest(year=year):
                self.assertIsNone(anchor_eval.evaluate(
                    anchor, write_in, template))
                self.assertIsNotNone(anchor_eval.evaluate(
                    anchor, f"{page1}.{line_9[year]}[0]", template))
                if year in row_2:
                    self.assertIsNotNone(anchor_eval.evaluate(
                        anchor, f"{page1}.Line8z_ReadOrder[0]."
                        f"{row_2[year]}[0]", template))
                self.assertIsNotNone(anchor_eval.evaluate(
                    lines[(P1, "8z")].anchor, write_in, template))
                self.assertIsNone(anchor_eval.evaluate(
                    lines[(P1, "8z")].anchor, amount, template))

    def test_wrapped_totals_use_the_default_anchor(self):
        # Ruling: 5 (2021), 10 and 26 have their box alone on its row, and
        # the default row label places them; no explicit anchor.
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                for line in ((P1, "5"), (P1, "10"), (P2, "26")):
                    self.assertIsNone(lines[line].anchor, line)

    def test_2025_line_7_anchor_rejects_the_amount_repaid_field(self):
        # 2025 line 7's row also holds the "amount repaid" entry. The default
        # row-label anchor would accept it (reachable negative space); the
        # declared RIGHT_OF box label accepts only the amount field.
        template = _template(2025)
        repaid = "topmostSubform[0].Page1[0].Line7_ReadOrder[0].f1_11[0]"
        line_7 = _lines(2025)[(P1, "7")]
        self.assertIsNotNone(line_7.anchor)
        self.assertIsNone(anchor_eval.evaluate(
            anchor_eval.default_anchor(line_7, False), repaid, template))
        self.assertIsNotNone(anchor_eval.evaluate(
            line_7.anchor, repaid, template))


class SchOneWitnessDiscrepancyTests(unittest.TestCase):
    """The documented witness discrepancies are exactly the stylesheet
    cross-check's raw findings, every year (the wired in-force pin)."""

    def _raw(self, decl):
        return crosscheck_mod.crosscheck(
            decl, propose.stylesheet_lines("sch_1", decl.key))

    def test_in_force_set_is_exactly_the_raw_findings(self):
        for year in YEARS:
            decl = sch_1.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            in_force = crosscheck_mod.discrepancies_in_force(sch_1, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in self._raw(decl)})

    def test_documented_discrepancies_leave_no_finding(self):
        for year in YEARS:
            decl = sch_1.DECLARATIONS[year]
            findings = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("sch_1", year),
                discrepancies=crosscheck_mod.discrepancies_in_force(
                    sch_1, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))


COVERED_BATTERIES = tuple(b.name for b in BATTERIES)


def _sch_1_records():
    """(row id, RecordedForm) for every Schedule 1 the registered batteries
    emit natively (no expected values: the states are observed)."""
    manifest = emit_manifest.load_manifest()
    records = []
    for battery in BATTERIES:
        for name, year, build in battery.scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = manifest.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            if not any(f.startswith("federal/sch_1") for f in row["forms"]):
                continue
            out = Path(tempfile.mkdtemp()) / "out"
            records += [(rid, rec) for rec in emit_manifest.emit(
                battery, build(), out).record if rec.form == FORM]
    return records


class SchOneCoverageTests(unittest.TestCase):
    """Coverage over this declaration (read directly; it is not registered
    until graduation): every cell is covered, every year."""

    @classmethod
    def setUpClass(cls):
        cls.records = _sch_1_records()

    def test_every_year_has_records(self):
        self.assertEqual(sorted({rec.key for _, rec in self.records}),
                         list(YEARS))

    def test_no_cell_is_uncovered(self):
        # emit_battery_sch_1 carries the line 8z rows (one type, every
        # type, none) that cover 8z, its type write-in and line 9.
        decls = [sch_1.DECLARATIONS[y] for y in YEARS]
        report = coverage_cells(self.records, decls)
        self.assertEqual(list(report.uncovered), [], "\n".join(
            map(str, report.uncovered)))


if __name__ == "__main__":
    unittest.main()
