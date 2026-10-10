"""Form 8962 line 26 as PRINTED.

Instructions for Form 8962, Line 26: "If line 24 is greater than line 25,
subtract line 25 from line 24 and enter the result on line 26. ... If line 24
is equal to line 25, enter -0- on line 26 and skip lines 27 through 29." and,
under Line 27: "If line 25 is greater than line 24, leave line 26 blank".

The spine's ``f8962_line_26_net_ptc`` stays a number in every case (it is an
addend of total payments); the PRINTED cell is a separate key so a repayment
return no longer prints 0 on line 26.

Every PDF assertion names the line-26 widget by its literal path.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms.f8962 import compute
from tenforty.models import (
    Form1095A, Form1095AMonth, Scenario, TaxReturnConfig, W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.f8962 import F8962Params
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

_YEARS = (2021, 2022, 2023, 2024, 2025)

# Literal widget paths (same on every year's f8962 template).
_LINE_24 = "topmostSubform[0].Page1[0].f1_91[0]"
_LINE_25 = "topmostSubform[0].Page1[0].f1_92[0]"
_LINE_26 = "topmostSubform[0].Page1[0].f1_93[0]"


def _params() -> F8962Params:
    return F8962Params(
        year=2024,
        fpl_single_48=10_000,
        applicable_figures={100: 0.0, 133: 0.0, 150: 0.0, 200: 0.02,
                            250: 0.04, 300: 0.06, 400: 0.085, 500: 0.085},
        applicable_figure_floor_pct=100,
        applicable_figure_ceiling_pct=500,
        repayment_caps_single=((200, 350), (300, 900), (400, 1500)),
        unemployment_rule=False,
        line5_400_boundary_inclusive=False,
    )


def _year_block(premium: float, slcsp: float, aptc: float) -> Form1095A:
    return Form1095A(months=tuple(
        Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc)
        for _ in range(12)))


class Line26PrintedComputeTests(unittest.TestCase):
    """MAGI 25,000 on a 10,000 FPL -> 250% -> figure .04 -> line 8a 1,000.
    Annual method: 11(e) = min(12*250, 12*300 - 1000) = 2,600 = line 24."""

    def test_line_24_greater_prints_the_difference(self):
        r = compute(_year_block(250.0, 300.0, 200.0), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 2400))
        self.assertEqual(r["f8962_line_26_printed"], 200)
        self.assertEqual(r["f8962_line_26_net_ptc"], 200)

    def test_line_24_equal_to_line_25_prints_zero(self):
        # 12 months of APTC summing to exactly line 24: 11 x 216 + 224 = 2,600.
        months = [Form1095AMonth(premium=250.0, slcsp=300.0, aptc=216.0)
                  for _ in range(11)]
        months.append(Form1095AMonth(premium=250.0, slcsp=300.0, aptc=224.0))
        r = compute(Form1095A(months=tuple(months)), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 2600))
        self.assertIsNotNone(r["f8962_line_26_printed"])
        self.assertEqual(r["f8962_line_26_printed"], 0)
        self.assertEqual(r["f8962_line_26_net_ptc"], 0)

    def test_line_25_greater_leaves_line_26_blank(self):
        r = compute(_year_block(250.0, 300.0, 300.0), 25_000.0, 2024, _params())
        self.assertEqual((r["f8962_line_24"], r["f8962_line_25"]), (2600, 3600))
        self.assertIn("f8962_line_26_printed", r)
        self.assertIsNone(r["f8962_line_26_printed"])
        # The spine's addend stays a number: it is summed into total payments.
        self.assertEqual(r["f8962_line_26_net_ptc"], 0)


def _scenario(year: int, block: Form1095A) -> Scenario:
    wages = 40_000
    return Scenario(
        config=TaxReturnConfig(
            digital_assets=False, year=year, filing_status="single",
            birthdate="1990-06-15", state="TX",
            acknowledges_no_source_documents=True,
            **scope_out_attestation_defaults(),
        ),
        w2s=[W2(
            employer="Acme Corp", wages=wages, federal_tax_withheld=4_000,
            ss_wages=wages, ss_tax_withheld=round(wages * 0.062),
            medicare_wages=wages, medicare_tax_withheld=round(wages * 0.0145),
        )],
        form_1095a=block,
    )


class Line26EmittedCellTests(unittest.TestCase):
    """The real emit path, every supported year: compute -> emit spec ->
    rendered PDF, read back at the literal line-26 widget."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _emit(self, year: int, block: Form1095A, tag: str):
        scenario = _scenario(year, block)
        results = self.orch.compute_federal(scenario)
        specs = self.orch._federal_individual_emit_specs(scenario, results)
        (spec,) = [s for s in specs if s.name == "8962"]
        out_dir = self.tmp / f"{year}_{tag}"
        out_dir.mkdir()
        path = self.orch._render_federal_spec(PdfFiller(), spec, out_dir)
        fields = PdfReader(str(path)).get_fields() or {}
        read = {p: ("" if f.get("/V") is None else str(f.get("/V")))
                for p, f in fields.items()}
        return results, read

    def _line_24(self, year: int) -> int:
        results = self.orch.compute_federal(
            _scenario(year, _year_block(500.0, 500.0, 0.0)))
        return results["f8962_line_24"]

    def test_repayment_return_leaves_line_26_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                results, read = self._emit(
                    year, _year_block(500.0, 500.0, 500.0), "repay")
                self.assertGreater(
                    results["f8962_line_25"], results["f8962_line_24"])
                self.assertEqual(read[_LINE_25], "6000")
                self.assertEqual(read[_LINE_26], "")

    def test_net_credit_return_prints_the_difference(self):
        for year in _YEARS:
            with self.subTest(year=year):
                results, read = self._emit(
                    year, _year_block(500.0, 500.0, 100.0), "net")
                line_24 = results["f8962_line_24"]
                self.assertGreater(line_24, 1200)
                self.assertEqual(read[_LINE_24], str(line_24))
                self.assertEqual(read[_LINE_25], "1200")
                self.assertEqual(read[_LINE_26], str(line_24 - 1200))

    def test_equal_lines_print_zero(self):
        for year in _YEARS:
            with self.subTest(year=year):
                line_24 = self._line_24(year)
                self.assertGreater(line_24, 0)
                each = line_24 // 12
                months = [Form1095AMonth(premium=500.0, slcsp=500.0,
                                         aptc=float(each)) for _ in range(11)]
                months.append(Form1095AMonth(
                    premium=500.0, slcsp=500.0,
                    aptc=float(line_24 - 11 * each)))
                results, read = self._emit(
                    year, Form1095A(months=tuple(months)), "equal")
                self.assertEqual(
                    results["f8962_line_24"], results["f8962_line_25"])
                self.assertEqual(read[_LINE_26], "0")


if __name__ == "__main__":
    unittest.main()
