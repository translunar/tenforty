"""Form 8962 Part III (lines 27-29) as PRINTED.

Part III is "Repayment of Excess Advance Payment of the Premium Tax Credit".
The form reaches it from line 26 only one way. Line 26, as printed on every
year's form: "If line 24 is greater than line 25, subtract line 25 from line
24. Enter the difference here and on Schedule 3 (Form 1040), line 9. If line
24 equals line 25, enter -0-. Stop here. If line 25 is greater than line 24,
leave this line blank and continue to line 27".

So:
  line 25 > line 24   line 26 blank; lines 27, 28, 29 completed
  line 24 = line 25   line 26 is 0; STOP -- lines 27, 28, 29 blank
  line 24 > line 25   line 26 is the credit; lines 27, 28, 29 blank

The defect this pins shut: lines 27-29 printed in every case, so a return
with no excess advance payment showed 0 on line 27, the repayment-limitation
dollars on line 28 and 0 on line 29.

The numeric keys the rest of the return reads (``f8962_line_27``,
``f8962_line_28``, ``f8962_line_29_repayment``) are unchanged in every case;
the PRINTED cells are separate keys, as line 26 already is.

Every PDF assertion names its widget by literal path, anchored to each
year's blank template by `TemplateAnchorTests`.
"""

import unittest

from pypdf import PdfReader

from tenforty.forms.f8962 import compute
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.models import Form1095A, Form1095AMonth
from tests.helpers import REPO_ROOT
from tests.test_f4562_emit_gate import _widgets_by_printed_line
from tests.test_f8962_line_26_presentation import (
    Line26EmittedCellTests, _params, _year_block,
)

YEARS = (2021, 2022, 2023, 2024, 2025)

LINE_24 = "topmostSubform[0].Page1[0].f1_91[0]"
LINE_25 = "topmostSubform[0].Page1[0].f1_92[0]"
LINE_26 = "topmostSubform[0].Page1[0].f1_93[0]"
LINE_27 = "topmostSubform[0].Page1[0].f1_94[0]"
LINE_28 = "topmostSubform[0].Page1[0].f1_95[0]"
LINE_29 = "topmostSubform[0].Page1[0].f1_96[0]"
PART_III = (LINE_27, LINE_28, LINE_29)

LINE_26_RULE = (
    "If line 24 equals line 25, enter -0-. Stop here. If line 25 is greater "
    "than line 24, leave this line blank and continue to line 27")


def _template(year: int):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f8962.pdf"


class TemplateAnchorTests(unittest.TestCase):
    def test_each_literal_is_the_one_widget_on_its_printed_line(self):
        for year in YEARS:
            by_line = _widgets_by_printed_line(_template(year), page_index=0)
            for number, literal in (
                    ("24", LINE_24), ("25", LINE_25), ("26", LINE_26),
                    ("27", LINE_27), ("28", LINE_28), ("29", LINE_29)):
                with self.subTest(year=year, line=number):
                    self.assertEqual(by_line.get(number), [literal])

    def test_every_years_form_prints_the_stop_rule_on_line_26(self):
        for year in YEARS:
            with self.subTest(year=year):
                text = " ".join(
                    PdfReader(str(_template(year))).pages[0]
                    .extract_text().split())
                self.assertIn(LINE_26_RULE, text)
                self.assertIn(
                    "Part III Repayment of Excess Advance Payment of the "
                    "Premium Tax Credit", text)


def _equal_block() -> Form1095A:
    """Twelve months of APTC summing to exactly line 24 (2,600 under
    `_params`): 11 x 216 + 224."""
    months = [Form1095AMonth(premium=250.0, slcsp=300.0, aptc=216.0)
              for _ in range(11)]
    months.append(Form1095AMonth(premium=250.0, slcsp=300.0, aptc=224.0))
    return Form1095A(months=tuple(months))


PRINTED_KEYS = (
    "f8962_line_27_printed", "f8962_line_28_printed",
    "f8962_line_29_printed")


class PartIIIPrintedComputeTests(unittest.TestCase):
    """MAGI 25,000 on a 10,000 FPL -> 250% -> line 24 = 2,600 and a 900
    repayment limitation (see the line 26 module for the derivation)."""

    def test_equal_lines_stop_before_part_iii(self):
        r = compute(_equal_block(), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 2600))
        for key in PRINTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, r)
                self.assertIsNone(r[key])
        # What the rest of the return reads is untouched.
        self.assertEqual(r["f8962_line_27"], 0)
        self.assertEqual(r["f8962_line_28"], 900)
        self.assertEqual(r["f8962_line_29_repayment"], 0)

    def test_a_net_credit_leaves_part_iii_blank(self):
        r = compute(_year_block(250.0, 300.0, 200.0), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 2400))
        for key in PRINTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, r)
                self.assertIsNone(r[key])
        self.assertEqual(r["f8962_line_27"], 0)
        self.assertEqual(r["f8962_line_28"], 900)
        self.assertEqual(r["f8962_line_29_repayment"], 0)

    def test_excess_advance_payment_completes_part_iii(self):
        """The twin: line 25 greater, so Part III prints its three lines."""
        r = compute(_year_block(250.0, 300.0, 300.0), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 3600))
        self.assertEqual(r["f8962_line_27_printed"], 1000)
        self.assertEqual(r["f8962_line_28_printed"], 900)
        self.assertEqual(r["f8962_line_29_printed"], 900)
        self.assertEqual(r["f8962_line_27"], 1000)
        self.assertEqual(r["f8962_line_28"], 900)
        self.assertEqual(r["f8962_line_29_repayment"], 900)

    def test_an_excess_of_one_dollar_completes_part_iii(self):
        """The boundary from the other side: 2,601 against 2,600."""
        months = list(_equal_block().months)
        months[-1] = Form1095AMonth(premium=250.0, slcsp=300.0, aptc=225.0)
        r = compute(Form1095A(months=tuple(months)), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 2601))
        self.assertEqual(r["f8962_line_27_printed"], 1)
        self.assertEqual(r["f8962_line_28_printed"], 900)
        self.assertEqual(r["f8962_line_29_printed"], 1)

    def test_uncapped_excess_prints_27_and_29_and_leaves_28_blank(self):
        """MAGI 45,000 -> 450% of the FPL: no repayment limitation."""
        r = compute(_year_block(250.0, 300.0, 300.0), 45_000.0, 2024, _params())
        self.assertGreater(r["f8962_line_25"], r["f8962_line_24"])
        self.assertIsNone(r["f8962_line_28"])
        self.assertEqual(r["f8962_line_27_printed"], r["f8962_line_27"])
        self.assertGreater(r["f8962_line_27_printed"], 0)
        self.assertIsNone(r["f8962_line_28_printed"])
        self.assertEqual(
            r["f8962_line_29_printed"], r["f8962_line_29_repayment"])


class MappingTests(unittest.TestCase):
    def test_part_iii_cells_bind_the_printed_keys(self):
        for year in YEARS:
            scalars = PdfF8962.get_mapping(year)["scalars"]
            with self.subTest(year=year):
                self.assertEqual(scalars.get("f8962_line_27_printed"), LINE_27)
                self.assertEqual(scalars.get("f8962_line_28_printed"), LINE_28)
                self.assertEqual(scalars.get("f8962_line_29_printed"), LINE_29)
                # The always-numeric keys reach no cell.
                for key in ("f8962_line_27", "f8962_line_28",
                            "f8962_line_29_repayment"):
                    self.assertNotIn(key, scalars)
                self.assertEqual(
                    sorted(k for k, path in scalars.items()
                           if path in PART_III),
                    sorted(PRINTED_KEYS))


class PartIIIEmittedCellTests(Line26EmittedCellTests):
    """The real emit path, every supported year, read back at the literal
    widgets. (Inherits the emit helpers; the inherited line 26 tests run
    here too.)"""

    def _equal(self, year: int) -> Form1095A:
        line_24 = self._line_24(year)
        self.assertGreater(line_24, 0)
        each = line_24 // 12
        months = [Form1095AMonth(premium=500.0, slcsp=500.0, aptc=float(each))
                  for _ in range(11)]
        months.append(Form1095AMonth(
            premium=500.0, slcsp=500.0, aptc=float(line_24 - 11 * each)))
        return Form1095A(months=tuple(months))

    def test_equal_lines_print_zero_on_26_and_nothing_in_part_iii(self):
        for year in YEARS:
            with self.subTest(year=year):
                results, read = self._emit(year, self._equal(year), "equal3")
                self.assertEqual(
                    results["f8962_line_24"], results["f8962_line_25"])
                # The return's own numbers are unchanged: no repayment.
                self.assertEqual(results["f8962_line_29_repayment"], 0)
                self.assertIsNotNone(results["f8962_line_28"])
                self.assertEqual(read[LINE_26], "0")
                for path in PART_III:
                    self.assertEqual(read[path], "", path)

    def test_net_credit_prints_nothing_in_part_iii(self):
        for year in YEARS:
            with self.subTest(year=year):
                results, read = self._emit(
                    year, _year_block(500.0, 500.0, 100.0), "net3")
                self.assertGreater(
                    results["f8962_line_24"], results["f8962_line_25"])
                self.assertIsNotNone(results["f8962_line_28"])
                self.assertEqual(
                    read[LINE_26],
                    str(results["f8962_line_24"] - results["f8962_line_25"]))
                for path in PART_III:
                    self.assertEqual(read[path], "", path)

    def test_excess_advance_payment_prints_all_of_part_iii(self):
        """The twin, so the fix cannot blank a real repayment."""
        for year in YEARS:
            with self.subTest(year=year):
                results, read = self._emit(
                    year, _year_block(500.0, 500.0, 500.0), "repay3")
                excess = results["f8962_line_25"] - results["f8962_line_24"]
                self.assertGreater(excess, 0)
                cap = results["f8962_line_28"]
                self.assertIsNotNone(cap)
                self.assertGreater(excess, cap)
                self.assertEqual(read[LINE_26], "")
                self.assertEqual(read[LINE_27], str(excess))
                self.assertEqual(read[LINE_28], str(cap))
                self.assertEqual(read[LINE_29], str(cap))
                self.assertEqual(results["f8962_line_29_repayment"], cap)


if __name__ == "__main__":
    unittest.main()
