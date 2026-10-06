"""CA Form 100S Side 4 Schedule F (Computation of Trade or Business Income) must
print, so Side 1 line 1 ("from Schedule F, line 22") references a filled form.

Schedule F mirrors federal 1120-S page 1; every printed value is the federal
compute's own figure passed through (never recomputed on the CA side), and line
22 must equal Side 1 line 1. Lines the scenario cannot supply are asserted BLANK:
14a / 14b (the scenario carries only the federal balance, mapped to 14c) and
19a / 19b (the scenario has no travel-and-entertainment split; the amount rides
in line 20 other deductions).

Synthetic fixture: gross 120,000, returns 2,000, COGS 18,000, 4797 gain 3,000,
other income 7,000 => total income 110,000; deductions total 78,000 =>
ordinary income 32,000 (all hard-coded below)."""
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


_EXPECTED = {
    "4001": "120000", "4002": "2000", "4003": "118000", "4004": "18000",
    "4005": "100000", "4006": "3000", "4007": "7000", "4008": "110000",
    "4009": "30000", "4010": "20000", "4011": "1000", "4012": "200",
    "4013": "12000", "4014": "3300", "4015": "400", "4018 a": "2500",
    "4018 b": "100", "4019": "900", "4020": "1500", "4021": "2100",
    "4024": "4000", "4025": "78000", "4026": "32000",
}
_BLANK = ("4016", "4017", "4022", "4023")


def _values(pdf):
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in (PdfReader(str(pdf)).get_fields() or {}).items()}


class ScheduleFTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        r = s.s_corp_return
        inc, ded = r.income, r.deductions
        inc.gross_receipts, inc.returns_and_allowances = 120000.0, 2000.0
        inc.cogs_aggregate, inc.net_gain_loss_4797 = 18000.0, 3000.0
        inc.other_income = 7000.0
        ded.compensation_of_officers, ded.salaries_wages = 30000.0, 20000.0
        ded.repairs_maintenance, ded.bad_debts = 1000.0, 200.0
        ded.rents, ded.taxes_licenses, ded.interest = 12000.0, 3300.0, 400.0
        ded.depreciation, ded.depletion = 2500.0, 100.0
        ded.advertising, ded.pension_profit_sharing_plans = 900.0, 1500.0
        ded.employee_benefits, ded.other_deductions = 2100.0, 4000.0
        r.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        out = Path(self._tmp.name) / f"f_{year}"
        self.orch.run_full_california_scorp_return(s, out)
        return _values(out / f"f100s_{year}.pdf")

    def test_every_schedule_f_line_prints_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year)
                for num, want in _EXPECTED.items():
                    self.assertEqual(v[_n(year, num)], want, f"{year} {num}")

    def test_line_22_equals_side_1_line_1(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year)
                self.assertEqual(v[_n(year, "1031")], "32000")
                self.assertEqual(v[_n(year, "4026")], v[_n(year, "1031")])

    def test_lines_without_a_scenario_source_stay_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year)
                self.assertEqual(v[_n(year, "4026")], "32000")  # control
                for num in _BLANK:
                    self.assertIn(v[_n(year, num)], (None, ""), num)


if __name__ == "__main__":
    unittest.main()
