"""CA Form 100S computed-total cells must PRINT: Side 1 line 8, Side 2 lines 13,
14 and 15, and line 45 (total amount due). The values are the form's own
arithmetic over lines the emit already prints, so each test also checks the
printed cell foots against the printed lines it totals (the partial-total
failure species: a total feeding a tax computation but missing on the page).

Fixture (synthetic): federal ordinary income 70,000; CA addbacks 1,000 (line 2)
and -500 (line 5) => line 8 = 70,500 (hard-coded below, not recomputed from the
implementation); tax 1.5% x 70,500 = 1,057.5 -> 1,058.

Line 45 is printed only when its arithmetic result is zero or more: with an
overpayment the form's "subtract line 41" yields a NEGATIVE number, and no FTB
instruction in the repo says how that is entered, so the cell is left blank
rather than invented (the refund prints on lines 41-43)."""
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


def _values(pdf):
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in (PdfReader(str(pdf)).get_fields() or {}).items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, estimated):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=estimated,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=1000.0,
            depreciation_adjustment=-500.0, apportionment_ca_only=True)
        out = Path(self._tmp.name) / f"t_{year}_{estimated}"
        self.orch.run_full_california_scorp_return(s, out)
        return _values(out / f"f100s_{year}.pdf")


class IncomeSideTotalTests(_EmitBase):
    def test_lines_8_13_14_15_print_and_foot(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year, estimated=200.0)
                # neighbours that already print (reachability / control)
                self.assertEqual(v[_n(year, "1031")], "70000")
                self.assertEqual(v[_n(year, "1032")], "1000")
                self.assertEqual(v[_n(year, "1035")], "-500")
                self.assertEqual(v[_n(year, "2012")], "70500")
                # the totals
                self.assertEqual(v[_n(year, "1038")], "70500")   # Side 1 L8
                self.assertEqual(v[_n(year, "2005")], "0")       # L13
                self.assertEqual(v[_n(year, "2006")], "70500")   # L14
                self.assertEqual(v[_n(year, "2007")], "70500")   # L15


class TotalAmountDueTests(_EmitBase):
    def test_line_45_prints_the_amount_due(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year, estimated=200.0)
                self.assertEqual(v[_n(year, "2014")], "1058")    # L21 tax
                self.assertEqual(v[_n(year, "2037")], "858")     # L40 due
                self.assertEqual(v[_n(year, "2046")], "858")     # L45

    def test_line_45_blank_when_the_result_is_negative(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = self._emit(year, estimated=2000.0)
                self.assertEqual(v[_n(year, "2038")], "942")     # L41 overpay
                self.assertIn(v[_n(year, "2046")], (None, ""))

    def test_line_45_zero_when_exactly_paid(self):
        v = self._emit(2025, estimated=1058.0)
        self.assertEqual(v[_n(2025, "2046")], "0")


if __name__ == "__main__":
    unittest.main()
