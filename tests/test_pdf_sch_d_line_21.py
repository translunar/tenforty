"""Schedule D line 21 prints (team-lead ruling, sch_d-declaration lane
phase 2). Its field is mapped every year; the entry sits in PREPRINTED
parentheses ("21 (        )"), so the cell receives the loss's MAGNITUDE
through PdfSchD.presentation_values, the f8995 pattern: the fill (and so
the recorder and the value check) consumes the presented values, while
the compute key stays signed for its consumer. The key is loss-only, so a
gain year presents nothing for it.
"""
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_sch_d import PdfSchD
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_capital_loss_over_cap
from tests.helpers import REPO_ROOT

KEY = "sch_d_line_21_allowed_loss"
# The one unmapped page-2 widget satisfying line 21's declared anchor, per
# year (measured on each official template).
FIELDS = {
    2021: "topmostSubform[0].Page2[0].Line21_ReadOrder[0]"
          ".TagCorrectingSubform[0].f2_04[0]",
    2022: "topmostSubform[0].Page2[0].TagCorrectingSubform[0].f2_04[0]",
    2023: "topmostSubform[0].Page2[0].TagCorrectingSubform[0].f2_04[0]",
    2024: "topmostSubform[0].Page2[0].TagCorrectingSubform[0].f2_04[0]",
    2025: "topmostSubform[0].Page2[0].f2_4[0]",
}


class LineTwentyOneMappingTests(unittest.TestCase):
    def test_line_21_maps_its_field_every_year(self):
        for year, field in FIELDS.items():
            with self.subTest(year=year):
                self.assertEqual(
                    PdfSchD.get_mapping(year)["scalars"].get(KEY), field)


class LineTwentyOnePresentationTests(unittest.TestCase):
    def test_a_loss_presents_its_magnitude(self):
        presented = PdfSchD.presentation_values(
            {KEY: -3_000, "sch_d_line_16_total": -8_000})
        self.assertEqual(presented[KEY], 3_000)
        # Only line 21 sits in parentheses; line 16 stays signed.
        self.assertEqual(presented["sch_d_line_16_total"], -8_000)

    def test_a_gain_year_is_unchanged(self):
        # Loss-only key: absent on a gain, so nothing is presented for it.
        values = {"sch_d_line_16_total": 2_500}
        self.assertEqual(PdfSchD.presentation_values(values), values)

    def test_no_presented_line_21_is_negative(self):
        for loss in (-1, -1_500, -3_000):
            with self.subTest(loss=loss):
                self.assertGreater(
                    PdfSchD.presentation_values({KEY: loss})[KEY], 0)

    def test_the_input_is_not_mutated(self):
        values = {KEY: -3_000}
        PdfSchD.presentation_values(values)
        self.assertEqual(values[KEY], -3_000)


class LineTwentyOneEmitTests(unittest.TestCase):
    """A capped capital loss, native: Schedule D line 21 prints the
    allowed loss's magnitude inside its preprinted parentheses."""

    def test_the_emitted_line_21_is_the_allowed_loss_magnitude(self):
        for year in (2021, 2025):
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tempfile.mkdtemp()))
            with unittest.mock.patch.object(
                    ReturnOrchestrator, "_compute_1040_via_workbook",
                    side_effect=AssertionError("workbook path reached")):
                results, emitted = orch.run_full_return(
                    build_capital_loss_over_cap(year),
                    Path(tempfile.mkdtemp()))
            pdf = next(p for p in emitted.values()
                       if Path(p).name == f"f1040sd_{year}.pdf")
            printed = (PdfReader(str(pdf)).get_fields() or {})[
                FIELDS[year]].get("/V")
            # 1040 line 7(a) carries Schedule D line 21's allowed loss.
            allowed = results["capital_gain_loss"]
            with self.subTest(year=year):
                self.assertLess(allowed, 0)
                self.assertEqual(str(printed).replace(",", ""),
                                 str(abs(allowed)))


if __name__ == "__main__":
    unittest.main()
