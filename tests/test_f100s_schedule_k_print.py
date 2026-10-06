"""CA Form 100S Side 6 Schedule K (corporate pro-rata items): columns (b)
"Amount from federal K (1120-S)", (c) "California Adjustment", (d) "Total
amounts using California law" (the form's own K-1 captions say (d) combines (b)
and (c)). For this S-corp profile only line 1 (ordinary business income) and
the line 19 reconciliation total carry amounts.

Fixture (synthetic): federal ordinary income 70,000; CA addbacks 1,000 and
-500 => (b) 70,000, (c) 500, (d) 70,500 (hard-coded). Line 19 cells are
2021-2024 6100/6101/6102 but 2025 6102/6103/6104 (2025 re-used 6100 for the
line 18e radio) — path existence cannot distinguish them, only position can."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year


def _n(year, bare):
    return bare if year <= 2023 else f"100S Form {bare}"


def _line19(year):
    return ("6102", "6103", "6104") if year == 2025 else (
        "6100", "6101", "6102")


def _values(pdf):
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in (PdfReader(str(pdf)).get_fields() or {}).items()}


class ScheduleKTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, addback=1000.0, depr=-500.0):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=addback,
            depreciation_adjustment=depr, apportionment_ca_only=True)
        out = Path(self._tmp.name) / f"k_{year}_{addback}_{depr}"
        self.orch.run_full_california_scorp_return(s, out)
        return _values(out / f"f100s_{year}.pdf")

    def test_line_1_columns_b_c_d_print_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year)
                self.assertEqual(v[_n(year, "1031")], "70000")  # control
                self.assertEqual(v[_n(year, "6001")], "70000")
                self.assertEqual(v[_n(year, "6002")], "500")
                self.assertEqual(v[_n(year, "6003")], "70500")

    def test_line_19_total_prints_in_that_years_own_cells(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year)
                b, c, d = (_n(year, n) for n in _line19(year))
                self.assertEqual((v[b], v[c], v[d]),
                                 ("70000", "500", "70500"))

    def test_2025_line_18e_radio_is_not_written_by_line_19(self):
        # 2025's 6100 is the line 18e Paid/Accrued radio: it must stay unset.
        v = self._emit(2025)
        self.assertIn(v[_n(2025, "6100 RB")], (None, "/Off"))

    def test_zero_adjustment_prints_zero_and_columns_foot(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year, addback=0.0, depr=0.0)
                self.assertEqual(
                    (v[_n(year, "6001")], v[_n(year, "6002")],
                     v[_n(year, "6003")]), ("70000", "0", "70000"))


if __name__ == "__main__":
    unittest.main()
