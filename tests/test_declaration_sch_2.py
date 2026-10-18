"""The Schedule 2 declaration validates against each year's own inventory,
covers every computation key, binds by meaning across the 2024 Part I
restructure, and its anchors locate their fields (emit-verification
protocol step 4; adjudication /private/tmp/pilot-packet-sch_2).

The declaration is inert until graduation: registration and the pending
removal land together, so these tests read the module directly, not the
registry.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry, sch_2
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import expand
from tenforty.declarations.validate import validate
from tenforty.mappings.pdf_sch_2 import PdfSch2
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
OLD_LAYOUT, NEW_LAYOUT = (2021, 2022, 2023), (2024, 2025)
FORM = ("federal", "sch_2")
P1, P2 = "Part I", "Part II"

# The computation's Schedule 2 output keys (names only; source-enumerated).
OUTPUT_KEYS = frozenset({
    "sch_2_line_11_additional_medicare_tax",
    "sch_2_line_1a_excess_aptc_repayment",
    "sch_2_line_1z_total_additions",
    "sch_2_line_21_total_other_taxes",
    "sch_2_line_2_excess_aptc_repayment",
    "sch_2_line_3_part_i_total",
    "sch_2_line_4_se_tax",
    "taxpayer_name",
    "taxpayer_ssn",
})
APTC_2 = "sch_2_line_2_excess_aptc_repayment"
APTC_1A = "sch_2_line_1a_excess_aptc_repayment"
TOTAL_1Z = "sch_2_line_1z_total_additions"


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040s2.pdf"


def _lines(year):
    return {ln.line_id: ln for ln in sch_2.DECLARATIONS[year].lines}


class SchTwoDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_2.DECLARATIONS), list(YEARS))
        for year in YEARS:
            with self.subTest(year=year):
                decl = sch_2.DECLARATIONS[year]
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_2.DECLARATIONS[year])
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_line_counts(self):
        # 39 printed lines 2021-2023; 47 from the 2024 Part I restructure.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(len(sch_2.DECLARATIONS[year].lines),
                                 39 if year in OLD_LAYOUT else 47)

    def test_still_pending(self):
        # Graduation (registration + unpending) is a later, separate lane.
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


class SchTwoKeyCoverageTests(unittest.TestCase):
    """Bound lines plus not_printed account for every output key, every
    year, and nothing else is bound."""

    def test_every_output_key_is_bound_or_not_printed(self):
        for year in YEARS:
            decl = sch_2.DECLARATIONS[year]
            bound = {ln.key for ln in decl.lines if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound | set(decl.not_printed), OUTPUT_KEYS)
                self.assertEqual(bound & set(decl.not_printed), set())

    def test_header_keys_are_presentation_only(self):
        for year in YEARS:
            np = sch_2.DECLARATIONS[year].not_printed
            with self.subTest(year=year):
                for key in ("taxpayer_name", "taxpayer_ssn"):
                    self.assertTrue(np[key].startswith("presentation-only:"))

    def test_other_layout_keys_are_other_year(self):
        # Adjudication ruling 1: each key whose line exists only in the
        # other Part I layout is not_printed with the "other-year:" tag.
        expected = {year: ({APTC_1A, TOTAL_1Z} if year in OLD_LAYOUT
                           else {APTC_2}) for year in YEARS}
        for year in YEARS:
            np = sch_2.DECLARATIONS[year].not_printed
            with self.subTest(year=year):
                self.assertEqual(
                    {k for k, r in np.items() if r.startswith("other-year:")},
                    expected[year])


class SchTwoBindByMeaningTests(unittest.TestCase):
    """The excess-APTC repayment moved from line 2 to line 1a in 2024, and
    line 2 became the alternative minimum tax: the line-2 key binds by
    meaning, never by name."""

    def test_the_line_2_key_binds_line_2_only_in_the_old_layout(self):
        for year in YEARS:
            lines = _lines(year)
            with self.subTest(year=year):
                self.assertEqual(lines[(P1, "2")].key,
                                 APTC_2 if year in OLD_LAYOUT else "")

    def test_the_aptc_repayment_binds_line_1a_from_2024(self):
        for year in NEW_LAYOUT:
            with self.subTest(year=year):
                self.assertEqual(_lines(year)[(P1, "1a")].key, APTC_1A)
                self.assertEqual(_lines(year)[(P1, "1z")].key, TOTAL_1Z)

    def test_new_layout_line_2_is_the_unserved_amt(self):
        for year in NEW_LAYOUT:
            line_2 = _lines(year)[(P1, "2")]
            with self.subTest(year=year):
                self.assertEqual(line_2.single_state, "nothing")
                self.assertIn("alternative minimum tax",
                              line_2.single_state_reason)


class SchTwoAdjudicatedTextTests(unittest.TestCase):
    def test_line_21_anchor_is_its_first_row_prefix(self):
        # Ruling 2: author B's phrase, which sits on line 21's first row in
        # every year (A's spans the 2021-2023 wrap).
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    _lines(year)[(P2, "21")].anchor,
                    NearLabel("Add lines 4, 7 through 16",
                              LabelRelation.AFTER_WRAPPED))

    def test_mef_union(self):
        # Ruling 3: author A's elements fill author B's Nones.
        for year in (2022, 2023):
            with self.subTest(year=year):
                self.assertEqual(_lines(year)[(P2, "17a")].mef_element,
                                 "TotalRecaptureOtherCreditsAmt")
        self.assertEqual(_lines(2025)[(P1, "1y")].mef_element,
                         "TotalOtherTaxAdditionsAmt")

    def test_descriptions_follow_the_paper(self):
        # Ruling 4: the paper-accurate variant (pdftotext of the template).
        for year in OLD_LAYOUT:
            with self.subTest(year=year, line="3"):
                self.assertEqual(
                    _lines(year)[(P1, "3")].description,
                    "Add lines 1 and 2. Enter here and on Form 1040, "
                    "1040-SR, or 1040-NR, line 17")
        self.assertTrue(_lines(2024)[(P1, "1e")].description.startswith(
            "Excessive payments (EP) from Form 4255. Check applicable box "
            "and enter amount. (i)"))
        self.assertTrue(_lines(2025)[(P1, "1e")].description.startswith(
            "Excessive payments (EPs) on gross EPE from Form 4255."))

    def test_line_21_sum_is_recorded_per_year(self):
        # The partial-total risk: line 21's sum varies by year (19 in for
        # 2021 and 2024-2025, out for 2022-2023), and the record says so.
        for year in YEARS:
            summed = sch_2.PARTIAL_TOTAL_RISKS[(P2, "21")][year]
            with self.subTest(year=year):
                self.assertEqual("19" in summed, year not in (2022, 2023))
                self.assertNotIn("20", summed)


class SchTwoValueOnlyTests(unittest.TestCase):
    def test_exactly_the_part_totals_are_value_only(self):
        # Lines 3 and 21 are emitted on every Schedule 2: no scenario can
        # leave them blank (the sch_c value-only precedent).
        for year in YEARS:
            lines = {ln.line: ln for ln in sch_2.DECLARATIONS[year].lines}
            with self.subTest(year=year):
                self.assertEqual(sorted(l for l, ln in lines.items()
                                        if ln.single_state == "value"),
                                 ["21", "3"])
                for line in ("3", "21"):
                    self.assertIn("zero is a value",
                                  lines[line].single_state_reason)


class SchTwoPlacementTests(unittest.TestCase):
    """The harness's own placement check on each year's official template."""

    def test_every_bound_line_is_placed(self):
        for year in YEARS:
            findings = check_placement(
                _template(year), sch_2.DECLARATIONS[year],
                fill_spec_for(PdfSch2, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_explicit_phrases_print_exactly_once(self):
        for year in YEARS:
            words = anchor_eval._page_words(str(_template(year)), 1)
            with self.subTest(year=year):
                self.assertEqual(len(anchor_eval._phrase_boxes(
                    words, "Add lines 4, 7 through 16")), 1)


class SchTwoWitnessDiscrepancyTests(unittest.TestCase):
    """The documented witness discrepancies are exactly the stylesheet
    cross-check's raw findings, every year (the wired in-force pin)."""

    def _raw(self, decl):
        return crosscheck_mod.crosscheck(
            decl, propose.stylesheet_lines("sch_2", decl.key))

    def test_in_force_set_is_exactly_the_raw_findings(self):
        for year in YEARS:
            decl = sch_2.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            in_force = crosscheck_mod.discrepancies_in_force(sch_2, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in self._raw(decl)})

    def test_documented_discrepancies_leave_no_finding(self):
        for year in YEARS:
            decl = sch_2.DECLARATIONS[year]
            findings = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("sch_2", year),
                discrepancies=crosscheck_mod.discrepancies_in_force(
                    sch_2, year))
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))


COVERED_BATTERIES = ("spine_battery", "sch_c_battery", "emit_battery_sch_se",
                     "emit_battery_sch_c")


def _sch_2_records():
    """(row id, RecordedForm) for every Schedule 2 the covered batteries emit
    natively (no expected values: the states are observed)."""
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
            if not any(f.startswith("federal/sch_2") for f in row["forms"]):
                continue
            out = Path(tempfile.mkdtemp()) / "out"
            records += [(rid, rec) for rec in emit_manifest.emit(
                battery, build(), out).record if rec.form == FORM]
    return records


class SchTwoCoverageTests(unittest.TestCase):
    """Coverage over this declaration (read directly; it is not registered
    until graduation): every cell is covered, every year."""

    @classmethod
    def setUpClass(cls):
        cls.records = _sch_2_records()

    def test_every_year_has_records(self):
        self.assertEqual(sorted({rec.key for _, rec in self.records}),
                         list(YEARS))

    def test_no_cell_is_uncovered(self):
        decls = [sch_2.DECLARATIONS[y] for y in YEARS]
        report = coverage_cells(self.records, decls)
        self.assertEqual(list(report.uncovered), [], "\n".join(
            map(str, report.uncovered)))


if __name__ == "__main__":
    unittest.main()
