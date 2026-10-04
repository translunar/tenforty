"""Workbook-routed emit path: Form 8995 needs 1040 line 3a in its f1040 upstream.

`emit_pdfs` hands forms the compute_federal results as `upstream["f1040"]`. On
the workbook path those are the harvested OUTPUTS, so `qualified_dividends`
must be a harvested output (the workbook's `Qualified_Dividends` named range,
1040 line 3a) or f8995's fail-closed strict read raises. Fast tier: mocked
workbook results, no soffice."""
import unittest

import openpyxl

from tenforty.forms import f8995
from tenforty.mappings.f1040 import F1040
from tests.helpers import SPREADSHEETS_DIR
from tests.test_f8995_compute import _scenario_with_qbi

YEARS = (2021, 2022, 2023, 2024, 2025)


class WorkbookOutputsCarryQualifiedDividendsTests(unittest.TestCase):
    def test_output_mapped_and_named_range_resolves_every_year(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    F1040.get_outputs(year).get("qualified_dividends"),
                    "Qualified_Dividends")
                wb = openpyxl.load_workbook(
                    SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx",
                    read_only=False)
                try:
                    self.assertIn("Qualified_Dividends", wb.defined_names)
                    self.assertEqual(
                        len(list(wb.defined_names["Qualified_Dividends"]
                                 .destinations)), 1)
                finally:
                    wb.close()


class F8995OnWorkbookStyleUpstreamTests(unittest.TestCase):
    def _workbook_style(self, qualified_dividends):
        s, upstream = _scenario_with_qbi(taxable_income=100_000.0)
        s.config.acknowledges_qbi_below_threshold = False
        # Shape of the harvested workbook results: floats, with the line-3a
        # figure under `qualified_dividends`.
        f1040 = {k: v for k, v in upstream["f1040"].items()
                 if k != "qualified_dividends"}
        if qualified_dividends is not None:
            f1040["qualified_dividends"] = qualified_dividends
        upstream["f1040"] = f1040
        return s, upstream

    def test_line_12_reads_the_harvested_line_3a(self):
        s, upstream = self._workbook_style(250.0)
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_12_net_capital_gain"], 250)

    def test_missing_key_still_fails_closed(self):
        s, upstream = self._workbook_style(None)
        with self.assertRaises(KeyError):
            f8995.compute(s, upstream=upstream)


if __name__ == "__main__":
    unittest.main()
