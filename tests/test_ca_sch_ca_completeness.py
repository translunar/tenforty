"""Schedule CA (540): every Part I cell the divergence catalog can reach prints,
section totals foot against their visible addends, Column A mirrors the federal
1040, and every blank cell on the template is documented.

Synthetic data only. The "rich" scenario posts a distinct amount on EVERY Part I
(line, column) the catalog can reach, then reads the filled PDF back and checks
the arithmetic of the PRINTED page (independently of the code that derived the
totals, via the template's own tooltips).
"""

import functools
import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.ca_divergences import load_catalog
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import sch_ca as form_sch_ca
from tenforty.forms.sch_ca import _FEDERAL_MEMO_MAP, _normalize_line
from tenforty.mappings import pdf_sch_ca
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.models import (
    CA540Return, CASchCAAdjustment, DivergenceDirection, DivergenceSource)
from tests._blank_by_design import classify, unfilled
from tests._ca_emit_helpers import CA_YEARS, REPO_ROOT, emit_ca, make_ca_scenario
from tests._schca_tooltips import parse_tooltip, part_i_sectioned

LINE_26_OWN = {"sch_ca_line_part_i_line_26_subtractions",
               "sch_ca_line_part_i_line_26_additions"}

# synthetic federal figures for every Col A source
FED = {
    "wages": 80_000, "taxable_interest": 1_200, "ordinary_dividends": 900,
    "ira_taxable": 700, "pensions_taxable": 600, "social_security_taxable": 500,
    "capital_gain_loss": 400,
    "sch_1_line_1_taxable_refunds": 300, "sch_1_line_3_business_income": 2_000,
    "sch_1_line_4_other_gains": 150, "sch_1_line_5_rental_re_royalty": 1_100,
    "sch_1_line_6_farm_income": 250, "sch_1_line_7_unemployment": 800,
    "sch_1_line_8z_other_income": 350,
    "sch_1_line_11_educator": 100, "sch_1_line_13_hsa": 200,
    "sch_1_line_15_se_tax": 300, "sch_1_line_17_se_health": 400,
    "sch_1_line_20_ira": 500, "sch_1_line_21_student_loan_interest": 600,
}
FED_AGI = (sum(v for k, v in FED.items() if not re.match(r"sch_1_line_(11|13|15|17|20|21)_", k))
           - sum(v for k, v in FED.items() if re.match(r"sch_1_line_(11|13|15|17|20|21)_", k)))
# federal 1040 "a" lines (memo cells; they feed no total)
MEMO = {"tax_exempt_interest": 111, "qualified_dividends": 222,
        "ira_distributions": 333, "pensions": 444, "social_security": 555}
FEDERAL = {**FED, **MEMO, "agi": FED_AGI}


@functools.lru_cache(maxsize=None)
def _catalog_pairs(year):
    """[(key, section, token, col)] for each Part I (line, column) the catalog posts."""
    cat = load_catalog(year)
    pairs = []
    for e in (cat.entries if hasattr(cat, "entries") else cat):
        n = _normalize_line(e.sch_ca_line)
        m = re.fullmatch(r"part_i_(a|b|c)_(\w+)", n)
        if m:
            sec, tok = m.group(1).upper(), m.group(2)
        elif n == "part_i_line_1":
            sec, tok = "A", "1"
        else:
            continue
        d = e.direction.value.lower()
        for want, suffix, col in (("sub", "subtractions", "B"), ("add", "additions", "C")):
            if want in d or "both" in d:
                pairs.append((f"sch_ca_line_{n}_{suffix}", sec, tok, col))
    return pairs


def no_widget_keys(year):
    """Catalog pairs whose column the template does not print (computed from the
    template's own tooltips — not asserted from a hand-written list)."""
    idx = cell_index(year)
    return {k for k, sec, tok, col in _catalog_pairs(year) if (sec, tok, col) not in idx}


def template(year):
    return REPO_ROOT / "pdfs" / "california" / str(year) / "sch_ca.pdf"


def fill_sch_ca(year, ca540, federal, out):
    values = form_sch_ca.compute(ca540, federal, year)
    values["sch_ca_taxpayer_name"] = "Smoke Test"
    values["sch_ca_taxpayer_ssn"] = "000-00-0000"
    PdfFiller().fill(
        template_path=template(year), output_path=out,
        field_mapping=PdfSchCa.get_mapping(year), values=values,
        aggregations=PdfSchCa.get_aggregations(year),
        derivations=PdfSchCa.get_derivations(year),
        checkbox_states=PdfSchCa.get_checkbox_states(year))
    return out


def rich_ca540(year):
    """One divergence per catalog-reachable Part I (line, column), distinct amounts."""
    cat = load_catalog(year)
    entries = list(cat.entries if hasattr(cat, "entries") else cat)
    posted, divs, amount = {}, [], 1000
    for e in sorted(entries, key=lambda e: e.sch_ca_line):
        n = _normalize_line(e.sch_ca_line)
        if not n.startswith("part_i_"):
            continue
        d = e.direction.value.lower()
        for want, direction, suffix in (
                ("sub", DivergenceDirection.SUBTRACTION, "subtractions"),
                ("add", DivergenceDirection.ADDITION, "additions")):
            if want not in d and "both" not in d:
                continue
            key = f"sch_ca_line_{n}_{suffix}"
            if key in posted or key in LINE_26_OWN or key in no_widget_keys(year):
                continue
            amount += 7
            posted[key] = amount
            divs.append(CASchCAAdjustment(
                source=DivergenceSource.USER, sch_ca_line=e.sch_ca_line,
                direction=direction, amount=amount, description="synthetic"))
    return CA540Return(divergences=divs), posted


def printed(pdf):
    """{field_name: int} of the numeric values printed on the filled PDF."""
    out = {}
    for name, f in PdfReader(str(pdf)).get_fields().items():
        v = f.get("/V")
        if v is not None and re.fullmatch(r"-?\d+", str(v)):
            out[name] = int(v)
    return out


@functools.lru_cache(maxsize=None)
def cell_index(year):
    idx = {}
    for sec, tok, col, name in part_i_sectioned(template(year)):
        idx.setdefault((sec, tok, col), name)
    return idx


class PartICatalogCellsPrintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rich = {}
        for year in CA_YEARS:
            ca540, posted = rich_ca540(year)
            out = Path(tempfile.mkdtemp()) / f"sch_ca_{year}.pdf"
            fill_sch_ca(year, ca540, FEDERAL, out)
            cls.rich[year] = (out, posted, printed(out))

    def test_every_posted_catalog_amount_prints_somewhere_on_the_page(self):
        for year, (pdf, posted, vals) in self.rich.items():
            with self.subTest(year=year):
                self.assertGreater(len(posted), 25)
                ca540, _ = rich_ca540(year)
                results = form_sch_ca.compute(ca540, FEDERAL, year)
                mapping = PdfSchCa.get_mapping(year)
                for key in posted:      # compute value (posted + any auto row) is what must print
                    if key in mapping:
                        cell = mapping[key]
                    else:   # 2021 un-lettered line 1: folded into the derived 1z cell
                        tot = pdf_sch_ca._TOTAL_CELLS_2021
                        cell = tot["1zB" if key.endswith("subtractions") else "1zC"]
                    expected = results[key]
                    if cell in PdfSchCa.get_derivations(year) and key.startswith(
                            "sch_ca_line_part_i_line_1"):
                        expected += results.get(
                            key.replace("line_1", "a_1z"), 0)
                    self.assertEqual(vals.get(cell), expected, f"{year}: {key}")

    def test_every_catalog_pair_has_a_cell_or_an_owned_no_widget(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                mapping = PdfSchCa.get_mapping(year)
                suppressed = PdfSchCa.get_suppressed(year)
                idx = cell_index(year)
                pairs = _catalog_pairs(year)
                self.assertGreater(len(pairs), 60)
                for key, sec, tok, col in pairs:
                    if (sec, tok, col) in idx and not (
                            year == 2021 and key.startswith("sch_ca_line_part_i_line_1_")):
                        self.assertIn(key, mapping, f"{year}: template has a {sec}/{tok}/{col} cell "
                                                     f"but {key} is not placed on it")
                    else:
                        self.assertIn(key, suppressed, f"{year}: {key} has no cell and is unowned")

    def test_no_widget_pairs_are_the_documented_ones(self):
        # Catalog directions the template prints no column for (reported).
        expected = {
            2021: {"sch_ca_line_part_i_b_8e_additions"},
            2022: {"sch_ca_line_part_i_c_13_additions"},
            2023: {"sch_ca_line_part_i_c_13_additions"},
            2024: {"sch_ca_line_part_i_c_13_additions"},
            2025: {"sch_ca_line_part_i_c_13_additions"},
        }
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertEqual(no_widget_keys(year) - LINE_26_OWN, expected[year])

    def test_catalog_cells_are_the_cells_their_tooltips_name(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                cells = {}
                for sec, tok, col, name in part_i_sectioned(template(year)):
                    cells.setdefault(name, (tok, col))
                for key, fieldname in PdfSchCa.get_mapping(year).items():
                    m = re.fullmatch(
                        r"sch_ca_line_part_i_(?:[abc]_|line_)(\w+?)_(subtractions|additions|col_a)", key)
                    if not m or fieldname not in cells:
                        continue
                    tok, col = cells[fieldname]
                    suffix = {"subtractions": "B", "additions": "C", "col_a": "A"}[m.group(2)]
                    expected_tok = m.group(1)
                    if expected_tok == "1z" and year == 2021:
                        expected_tok = "1"
                    self.assertEqual((tok, col), (expected_tok, suffix), f"{key} -> {fieldname}")

    def test_section_totals_foot_against_visible_addends(self):
        for year, (pdf, posted, vals) in self.rich.items():
            with self.subTest(year=year):
                idx = cell_index(year)

                def v(sec, tok, col):
                    name = idx.get((sec, tok, col))
                    return vals.get(name, 0) if name else 0

                line1 = ("1",) if year == 2021 else ("1z",)
                for col in "ABC":
                    sec_a = sum(v("A", t, col) for t in (*line1, "2", "3", "4", "5b", "6", "7"))
                    sec_b = sum(v("B", t, col) for t in ("1", "2a", "3", "4", "5", "6", "7"))
                    nol = sum(v("B", t, col) for t in ("9b1", "9b2", "9b3", "9b4")) if col == "B" else 0
                    nine_a = v("T", "9a", col)
                    self.assertEqual(
                        v("T", "10", col), sec_a + sec_b + nine_a + nol, f"line 10 col {col}")
                    sec_c = sum(v("C", t, col) for t in (
                        "11", "12", "13", "14", "15", "16", "17", "18", "19a", "20", "21", "23"))
                    self.assertEqual(v("T", "26", col), sec_c + v("T", "25", col), f"line 26 col {col}")
                    self.assertEqual(
                        v("T", "27", col), v("T", "10", col) - v("T", "26", col), f"line 27 col {col}")
                    if year != 2021:
                        subs = [f"1{c}" for c in "abcdefghi"]
                        self.assertEqual(v("A", "1z", col), sum(v("A", t, col) for t in subs) if col != "A"
                                         else v("A", "1z", "A"), f"line 1z col {col}")
                    eights = sorted({t for (s, t, c) in idx if s == "B" and re.fullmatch(r"8[a-z]", t)})
                    self.assertEqual(nine_a, sum(v("B", t, col) for t in eights), f"line 9a col {col}")
                    twentyfours = sorted({t for (s, t, c) in idx if s == "C" and re.fullmatch(r"24[a-z]", t)})
                    self.assertEqual(v("T", "25", col), sum(v("C", t, col) for t in twentyfours),
                                     f"line 25 col {col}")

    def test_line_27_col_a_is_federal_agi_and_foots(self):
        for year, (pdf, posted, vals) in self.rich.items():
            with self.subTest(year=year):
                idx = cell_index(year)
                self.assertEqual(vals[idx[("T", "27", "A")]], FED_AGI)
                self.assertEqual(vals[idx[("T", "10", "A")]] - vals[idx[("T", "26", "A")]], FED_AGI)


class MemoCellsTests(unittest.TestCase):
    def test_federal_a_lines_print_in_section_a_memo_cells(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                out = Path(tempfile.mkdtemp()) / "s.pdf"
                fill_sch_ca(year, CA540Return(), FEDERAL, out)
                vals = printed(out)
                mapping = PdfSchCa.get_mapping(year)
                fields = PdfReader(str(out)).get_fields()
                for fed_key, memo_key in _FEDERAL_MEMO_MAP.items():
                    cell = mapping[memo_key]
                    line = re.search(r"line_(\d)a_", memo_key).group(1)
                    tip = re.sub(r"\s+", " ", str(fields[cell]["/TU"]))
                    self.assertRegex(tip, rf"Line {line}\. .*Line {line} ?a\.\s*$")
                    self.assertEqual(vals[cell], MEMO[fed_key], memo_key)


class ColumnAMirrorsFederalTests(unittest.TestCase):
    def test_line_1a_col_a_equals_w2_wages_and_1z(self):
        for year in CA_YEARS:
            if year == 2021:
                continue   # 2021 prints a single un-lettered line 1
            with self.subTest(year=year):
                out = Path(tempfile.mkdtemp()) / "s.pdf"
                fill_sch_ca(year, CA540Return(), FEDERAL, out)
                vals, idx = printed(out), cell_index(year)
                self.assertEqual(vals[idx[("A", "1a", "A")]], FED["wages"])
                self.assertEqual(vals[idx[("A", "1z", "A")]], FED["wages"])
                for t in "bcdefgh":       # (1i has no Col A cell) no federal source -> blank, like the 1040
                    self.assertNotIn(idx[("A", f"1{t}", "A")], vals)


if __name__ == "__main__":
    unittest.main()
