"""Form 1120-S page 1 line 19 "Energy efficient commercial buildings deduction"
(Form 7205), present on the 2023-2025 forms only.

Like its sibling deduction lines it must print (0) and foot into total
deductions, but a NONZERO claim must refuse: a section 179D deduction cannot be
printed without the attached Form 7205, which tenforty does not produce.

Cells are certified per year by the printed "Energy efficient ..." caption row
(y 337 on 2023-2025) against widget Rects, independent of the mapping module:
2023 / 2024 f1_33 (line 19; "Other deductions" is f1_34, total deductions
f1_35), 2025 f1_37 (Other f1_38, total f1_39). The 2022 template has NO such
line, so its numbering must stay exactly as it was (Other deductions f1_33).

Synthetic fixture only."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.models import OtherDeductionComponent
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_P1 = "topmostSubform[0].Page1[0]."
# year -> (line 7 officers cell number, energy, other deductions, total)
_CELLS = {2023: (21, 33, 34, 35), 2024: (21, 33, 34, 35), 2025: (25, 37, 38, 39)}


def _fields(pdf):
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

    def _scenario(self, year):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.deductions.rents = 1200.0
        s.s_corp_return.deductions.other_deductions = 300.0
        # PDF emit requires the line 19 statement rows (they foot to 300).
        s.s_corp_return.deductions.other_deductions_components = [
            OtherDeductionComponent("Synthetic misc expense", 300.0)]
        return s

    def _emit(self, year, energy=None):
        s = self._scenario(year)
        if energy is not None:
            s.s_corp_return.deductions.energy_efficient_buildings_deduction = energy
        out = Path(self._tmp.name) / f"e_{year}_{energy}"
        self.orch.run_full_federal_scorp_return(s, out)
        return _fields(out / f"f1120s_{year}.pdf")


class ZeroPrintsAndFootsTests(_EmitBase):
    def test_line_19_prints_zero_and_total_deductions_foot(self):
        for year, (first, energy, other, total) in _CELLS.items():
            with self.subTest(year=year):
                v = self._emit(year)
                # siblings print (control), then the energy line itself
                self.assertEqual(v[f"{_P1}f1_{other}[0]"], "300")
                self.assertEqual(v[f"{_P1}f1_{energy}[0]"], "0")
                # lines 7..20 (first .. other), 13 cells incl. energy, sum to total
                printed = [int(v[f"{_P1}f1_{n}[0]"])
                           for n in range(first, other + 1)]
                self.assertEqual(len(printed), 14)
                self.assertEqual(sum(printed), int(v[f"{_P1}f1_{total}[0]"]))
                self.assertEqual(v[f"{_P1}f1_{total}[0]"], "31500")  # 30000+1200+300

    def test_explicit_zero_same_as_default(self):
        for year in _CELLS:
            with self.subTest(year=year):
                self.assertEqual(self._emit(year), self._emit(year, 0.0))


class NonzeroRefusedTests(_EmitBase):
    def test_nonzero_refused_naming_form_7205_every_year(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                with self.assertRaises((NotImplementedError, ValueError)) as cm:
                    self._emit(year, energy=1000.0)
                self.assertIn("7205", str(cm.exception))

    def test_nonzero_refused_at_compute_too(self):
        s = self._scenario(2025)
        s.s_corp_return.deductions.energy_efficient_buildings_deduction = 5.0
        with self.assertRaises((NotImplementedError, ValueError)):
            self.orch.compute_corporate(s)


class Year2022UntouchedTests(_EmitBase):
    def test_2022_has_no_energy_line_and_numbering_is_unchanged(self):
        v = self._emit(2022)
        # 2022: line 19 "Other deductions" is f1_33 and total deductions f1_34
        self.assertEqual(v[f"{_P1}f1_33[0]"], "300")
        self.assertEqual(v[f"{_P1}f1_34[0]"], "31500")


class LoaderTests(unittest.TestCase):
    def _load(self, value="absent"):
        data = _scenario_yaml_dict()
        if value != "absent":
            data["s_corp_return"]["deductions"][
                "energy_efficient_buildings_deduction"] = value
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return.deductions

    def test_absent_defaults_to_zero(self):
        self.assertEqual(self._load().energy_efficient_buildings_deduction, 0.0)

    def test_stated_value_loads_then_refuses_at_compute(self):
        self.assertEqual(
            self._load(0).energy_efficient_buildings_deduction, 0.0)
        self.assertEqual(
            self._load(250.5).energy_efficient_buildings_deduction, 250.5)


if __name__ == "__main__":
    unittest.main()
