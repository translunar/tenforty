"""Form 1120-S Schedule K pro-rata block under the professional-software
convention: a DETAIL line (input-driven amount) prints only when nonzero, while
computed results (line 1 ordinary income, line 18 reconciliation) always print,
even when 0. Plus the one real concept among sections 12-17, shareholder
distributions (line 16d / K-1 box 16 code D).

Cell table is written independently of the mapping module and was certified per
year from each template's caption rows: the Schedule K cell names SHIFT between
vintages (2021-2023 vs 2024-2025; line 12e exists only on 2024-2025; 12c/12d are
f3_23/f3_25 then f3_22/f3_24; 13a-13g and 15a-16f move up one field from 2024),
so nothing is copied across years. Type-text sub-cells and 17d stay blank.

Synthetic fixture only."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_P3 = "topmostSubform[0].Page3[0].f3_"
_P4 = "topmostSubform[0].Page4[0].f4_"
# line -> (field number on 2021-2023 forms, on 2024-2025 forms); None = no cell
_LINES = {
    "11": (19, 19), "12a": (20, 20), "12b": (21, 21), "12c": (23, 22),
    "12d": (25, 24), "12e": (None, 26),
    "13a": (26, 27), "13b": (27, 28), "13c": (28, 29), "13d": (30, 31),
    "13e": (32, 33), "13f": (33, 34), "13g": (35, 36),
    "15a": (36, 37), "15b": (37, 38), "15c": (38, 39), "15d": (39, 40),
    "15e": (40, 41), "15f": (41, 42),
    "16a": (42, 43), "16b": (43, 44), "16c": (44, 45), "16d": (45, 46),
    "16e": (46, 47), "16f": (47, 48),
}
_PAGE4 = {"17a": 1, "17b": 2, "17c": 3}   # same every year
_ALL = tuple(years.SCORP_FEDERAL_YEARS)
# K-1 box 16 first row (code cell, amount cell) per vintage
_K1_BOX16 = {y: ("f1_77", "f1_78") if y <= 2023 else ("f1_80", "f1_81")
             for y in _ALL}
_K1 = "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0]."


def _cell(year, line):
    if line in _PAGE4:
        return f"{_P4}{_PAGE4[line]}[0]"
    n = _LINES[line][0 if year <= 2023 else 1]
    return None if n is None else f"{_P3}{n}[0]"


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

    def _emit(self, year, distributions=None, pcts=None):
        s = _make_v1_scenario(shareholder_pcts=pcts)
        set_tax_year(s, year)
        if distributions is not None:
            s.s_corp_return.distributions_to_shareholders = distributions
        out = Path(self._tmp.name) / f"k_{year}_{distributions}_{pcts}"
        self.orch.run_full_federal_scorp_return(s, out)
        return out


class CellsSitOnTheirCaptionRowsTests(unittest.TestCase):
    """Independent proof the table above is right: each widget's row matches the
    printed line label on that year's own template."""

    def test_every_cell_is_on_its_caption_row(self):
        for year in _ALL:
            pdf = f"pdfs/federal/{year}/f1120s.pdf"
            reader = PdfReader(pdf)
            for line in list(_LINES) + list(_PAGE4):
                path = _cell(year, line)
                if path is None:
                    continue
                pg = 4 if line in _PAGE4 else 3
                page = reader.pages[pg - 1]
                H = float(page.mediabox.height)
                rect = None
                for a in page["/Annots"]:
                    a = a.get_object()
                    names, n = [], a
                    while n is not None:
                        if "/T" in n:
                            names.append(str(n["/T"]))
                        p = n.get("/Parent")
                        n = p.get_object() if p else None
                    if ".".join(reversed(names)) == path:
                        rect = [float(v) for v in a["/Rect"]]
                self.assertIsNotNone(rect, f"{year} {line} {path}")
                out = subprocess.run(
                    ["pdftotext", "-bbox", "-f", str(pg), "-l", str(pg), pdf,
                     "-"], capture_output=True, text=True).stdout
                labels = [
                    (float(x0), H - float(y1)) for x0, y1, w in re.findall(
                        r'xMin="([\d.]+)" yMin="[\d.]+" xMax="[\d.]+" '
                        r'yMax="([\d.]+)">([^<]*)<', out) if w == line
                ]
                # the printed right-margin line label of this caption row
                hits = [y for x, y in labels if 470 < x < 495
                        and abs(y - (rect[1] + 1)) <= 3]
                self.assertTrue(
                    hits, f"{year} line {line}: no printed label on {path}")


class DetailLinesBlankWhenZeroTests(_EmitBase):
    def test_every_inactive_detail_line_is_blank(self):
        for year in _ALL:
            with self.subTest(year=year):
                out = self._emit(year)
                v = _fields(out / f"f1120s_{year}.pdf")
                self.assertEqual(
                    v[f"{_P3}3[0]"], "70000")        # control: line 1 prints
                for line in list(_LINES) + list(_PAGE4):
                    cell = _cell(year, line)
                    if cell is None:
                        continue
                    self.assertIn(v[cell], (None, ""), f"{year} line {line}")
                # the other detail lines of sections 2-10 are blank too
                for n in (4, 7, 8, 9, 11, 12, 13, 16, 18):
                    self.assertIn(v[f"{_P3}{n}[0]"], (None, ""), f"f3_{n}")

    def test_computed_lines_1_and_18_print_even_when_zero(self):
        for year in _ALL:
            with self.subTest(year=year):
                s = _make_v1_scenario(gross_receipts=30000.0,
                                      compensation_of_officers=30000.0)
                set_tax_year(s, year)
                out = Path(self._tmp.name) / f"zero_obi_{year}"
                self.orch.run_full_federal_scorp_return(s, out)
                v = _fields(out / f"f1120s_{year}.pdf")
                self.assertEqual(v[f"{_P3}3[0]"], "0")      # line 1
                self.assertEqual(v[f"{_P4}4[0]"], "0")      # line 18

    def test_old_forms_have_no_12e_cell(self):
        for year in (2021, 2022, 2023):
            self.assertIsNone(_cell(year, "12e"))

    def test_line_18_foots_from_printed_cells_blanks_counting_as_zero(self):
        for year in _ALL:
            with self.subTest(year=year):
                v = _fields(self._emit(year) / f"f1120s_{year}.pdf")

                def amt(cell):
                    return int(v[cell] or 0) if cell else 0
                income = sum(amt(f"{_P3}{n}[0]") for n in (3, 4, 7, 8, 9,
                                                           11, 12, 13, 16, 18))
                deductions = sum(amt(_cell(year, l)) for l in (
                    "11", "12a", "12b", "12c", "12d", "12e", "16f"))
                self.assertEqual(
                    int(v[f"{_P4}4[0]"]), income - deductions)


class DistributionsTests(_EmitBase):
    def test_nonzero_distributions_print_on_16d_and_k1_box_16d(self):
        for year in _ALL:
            with self.subTest(year=year):
                out = self._emit(year, distributions=40000.0)
                v = _fields(out / f"f1120s_{year}.pdf")
                self.assertEqual(v[_cell(year, "16d")], "40000")
                # no other 16-line carries it
                for line in ("16a", "16b", "16c", "16e", "16f"):
                    self.assertIn(v[_cell(year, line)], (None, ""), line)
                k = _fields(out / f"f1120s_k1_1_{year}.pdf")
                code, amt = _K1_BOX16[year]
                self.assertEqual(k[_K1 + f"{code}[0]"], "D")
                self.assertEqual(k[_K1 + f"{amt}[0]"], "40000")

    def test_distributions_allocated_by_ownership(self):
        for year in (2022, 2025):
            with self.subTest(year=year):
                out = self._emit(year, distributions=40000.0,
                                 pcts=[60.0, 40.0])
                code, amt = _K1_BOX16[year]
                one = _fields(out / f"f1120s_k1_1_{year}.pdf")
                two = _fields(out / f"f1120s_k1_2_{year}.pdf")
                self.assertEqual(one[_K1 + f"{amt}[0]"], "24000")
                self.assertEqual(two[_K1 + f"{amt}[0]"], "16000")
                self.assertEqual(two[_K1 + f"{code}[0]"], "D")

    def test_distributions_do_not_change_line_18(self):
        for year in _ALL:
            with self.subTest(year=year):
                a = _fields(self._emit(year) / f"f1120s_{year}.pdf")
                b = _fields(self._emit(year, 40000.0) / f"f1120s_{year}.pdf")
                self.assertEqual(a[f"{_P4}4[0]"], b[f"{_P4}4[0]"])

    def test_zero_distributions_leave_k1_box_16_blank(self):
        for year in _ALL:
            with self.subTest(year=year):
                out = self._emit(year)
                k = _fields(out / f"f1120s_k1_1_{year}.pdf")
                code, amt = _K1_BOX16[year]
                self.assertIn(k[_K1 + f"{code}[0]"], (None, ""))
                self.assertIn(k[_K1 + f"{amt}[0]"], (None, ""))


class LoaderTests(unittest.TestCase):
    def _load(self, value="absent"):
        extra = None if value == "absent" else {
            "distributions_to_shareholders": value}
        data = _scenario_yaml_dict(extra_scorp=extra)
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return

    def test_default_zero_and_stated_loads(self):
        self.assertEqual(self._load().distributions_to_shareholders, 0.0)
        self.assertEqual(
            self._load(1250.5).distributions_to_shareholders, 1250.5)

    def test_bad_values_refused(self):
        self._load(10)  # reachability: key is known
        for bad in (-1, "lots", True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load(bad)


if __name__ == "__main__":
    unittest.main()
