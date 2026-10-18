"""Form 8995 line 1: every business row i-v maps its three cells (Juno's
per-source-rows ruling, phase K). Field names from the per-year probe of
each official template: 2021-2024 share Table[0].Ln1A_Row1..Ln1E_Row5
(f1_3..f1_17); 2025 uses Table[0].Row1i..Row1v (f1_03..f1_17). Row i's
column (c) carries row i's own QBI (f8995_line_1i_qbi); the aggregate
f8995_line_1_qbi is line 2's feed and is not printed.
"""
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_f8995 import PdfF8995

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
ROWS = ("i", "ii", "iii", "iv", "v")
_T = "topmostSubform[0].Page1[0].Table[0]."


def _expected(year):
    out = {}
    for n, row in enumerate(ROWS):
        if year == 2025:
            group, cells = f"Row1{row}", [f"{3 * n + k:02d}" for k in (3, 4, 5)]
        else:
            group = f"Ln1{'ABCDE'[n]}_Row{n + 1}"
            cells = [str(3 * n + k) for k in (3, 4, 5)]
        for col, cell in zip(("name", "tin", "qbi"), cells):
            out[f"f8995_line_1{row}_{col}"] = f"{_T}{group}[0].f1_{cell}[0]"
    return out


class F8995RowMappingTests(unittest.TestCase):
    def test_every_row_maps_its_three_cells(self):
        for year in YEARS:
            scalars = PdfF8995.get_mapping(year)["scalars"]
            with self.subTest(year=year):
                self.assertEqual(
                    {k: v for k, v in scalars.items()
                     if k.startswith("f8995_line_1") and k[12:13] in "iv"},
                    _expected(year))

    def test_the_aggregate_is_not_printed(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertNotIn("f8995_line_1_qbi",
                                 PdfF8995.get_mapping(year)["scalars"])

    def test_every_mapped_cell_is_on_its_template(self):
        for year in YEARS:
            fields = PdfReader(str(REPO_ROOT / "pdfs" / "federal" / str(year)
                                   / "f8995.pdf")).get_fields() or {}
            with self.subTest(year=year):
                self.assertEqual(
                    [f for f in _expected(year).values() if f not in fields],
                    [])


if __name__ == "__main__":
    unittest.main()
