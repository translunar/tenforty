"""Schedule CA (540) Part II on the printed page.

Emits an itemizing CA return for every supported year and reads the filled
Schedule CA back. Cells are located by the template's own tooltips
(tests/_schca_tooltips.part_ii_cells), independently of the mapping, so a
value in the wrong cell fails here even though the field exists.
"""

import dataclasses
import re
import unittest

from pypdf import PdfReader

from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.models import ItemizedDeductions, W2
from tenforty.params import california as ca_params
from tests._ca_emit_helpers import CA_YEARS, REPO_ROOT, emit_ca, make_ca_scenario
from tests._schca_tooltips import part_ii_cells

_SUFFIX = {"A": "col_a", "B": "subtractions", "C": "additions"}


def _template(year):
    return REPO_ROOT / "pdfs" / "california" / str(year) / "sch_ca.pdf"


def _key(token: str) -> str:
    """'5eB' -> 'sch_ca_line_part_ii_5e_subtractions'; '18' -> '..._18'."""
    if token[-1] in _SUFFIX:
        return f"sch_ca_line_part_ii_{token[:-1]}_{_SUFFIX[token[-1]]}"
    return f"sch_ca_line_part_ii_{token}"


def itemizing_scenario(year, **w2_overrides):
    """Single CA resident, one W-2 (wages 80,000; CA withholding 4,000), with
    medical above the 7.5% floor, state income tax paid outside the W-2,
    property tax, mortgage interest and cash charity."""
    scenario = make_ca_scenario(year)
    if w2_overrides:
        scenario = dataclasses.replace(
            scenario,
            w2s=[dataclasses.replace(scenario.w2s[0], **w2_overrides)])
    return dataclasses.replace(scenario, itemized_deductions=ItemizedDeductions(
        medical_expenses=20_000.0, state_income_tax=1_000.0,
        property_tax=6_000.0, mortgage_interest=4_000.0,
        charitable_contributions=2_500.0))


def _expected(year):
    """Printed Part II for itemizing_scenario. AGI 80,000 -> medical floor
    6,000. Line 5a is 4,000 withheld + 1,000 paid = 5,000; 5d is 11,000. The
    federal SALT cap is 10,000 through 2024 and 40,000 in 2025, so line 5e
    Col A (and the Col C add-back of the capped-off excess) differ in 2025."""
    capped = 10_000 if year <= 2024 else 11_000
    add_back = 11_000 - capped
    return {
        "1": 20_000, "2": 80_000, "3": 6_000, "4A": 14_000,
        "5aA": 5_000, "5aB": 5_000, "5bA": 6_000, "5dA": 11_000,
        "5eA": capped, "5eB": 5_000, "5eC": add_back,
        "7A": capped, "7B": 5_000, "7C": add_back,
        "8aA": 4_000, "8eA": 4_000, "10A": 4_000,
        "11A": 2_500, "14A": 2_500,
        "17A": 14_000 + capped + 4_000 + 2_500, "17B": 5_000, "17C": add_back,
        "18": 26_500, "26": 26_500, "28": 26_500, "29": 26_500, "30": 26_500,
    }


def _printed(pdf_path):
    return {name: (None if field.get("/V") in (None, "") else str(field.get("/V")))
            for name, field in PdfReader(str(pdf_path)).get_fields().items()}


class PartIIPrintsOnAnItemizedReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results, cls.printed, cls.f540 = {}, {}, {}
        for year in CA_YEARS:
            results, pdfs = emit_ca(itemizing_scenario(year))
            cls.results[year] = results
            cls.printed[year] = _printed(pdfs["sch_ca"])
            cls.f540[year] = _printed(pdfs["f540"])

    def test_scenario_is_federally_itemized_and_ca_itemized(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertEqual(self.results[year]["ca_itemized_total"], 26_500)
                self.assertEqual(self.results[year]["f540_deduction"], 26_500)

    def test_every_modeled_cell_prints_its_value(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))
            for token, value in _expected(year).items():
                with self.subTest(year=year, cell=token):
                    self.assertEqual(self.printed[year][cells[token]], str(value))

    def test_no_other_part_ii_cell_prints(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))
            expected = set(_expected(year))
            stray = {token: self.printed[year][field]
                     for token, field in cells.items()
                     if token not in expected
                     and self.printed[year][field] is not None}
            with self.subTest(year=year):
                self.assertEqual(stray, {})

    def test_the_page_foots_against_its_visible_cells(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))

            def v(token, year=year, cells=cells):
                # A line with no cell in this column (line 4 has no Col B)
                # contributes nothing, like a cell left blank.
                raw = self.printed[year].get(cells.get(token))
                return 0 if raw is None else int(raw)

            with self.subTest(year=year):
                self.assertEqual(v("4A"), max(0, v("1") - v("3")))
                self.assertEqual(v("5dA"), v("5aA") + v("5bA") + v("5cA"))
                for col in "ABC":
                    self.assertEqual(v("7" + col), v("5e" + col) + v("6" + col))
                    self.assertEqual(v("10" + col), v("8e" + col) + v("9" + col))
                    self.assertEqual(
                        v("17" + col),
                        v("4" + col) + v("7" + col) + v("10" + col)
                        + v("14" + col) + v("15" + col) + v("16" + col))
                self.assertEqual(v("8eA"), v("8aA") + v("8bA") + v("8cA"))
                self.assertEqual(v("14A"), v("11A") + v("12A") + v("13A"))
                self.assertEqual(v("18"), v("17A") - v("17B") + v("17C"))
                self.assertEqual(v("26"), v("18") + v("25"))
                self.assertEqual(v("28"), v("26"))
                self.assertEqual(v("29"), v("28"))

    def test_line_30_is_the_amount_on_form_540_line_18(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))
            line_18 = PdfF540.get_mapping(year)["f540_deduction"]
            with self.subTest(year=year):
                self.assertEqual(self.printed[year][cells["30"]],
                                 self.f540[year][line_18])
                self.assertEqual(self.f540[year][line_18], "26500")


class PartIIMappingCellsTests(unittest.TestCase):
    def test_part_ii_keys_map_to_the_cells_their_tooltips_name(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))
            mapping = PdfSchCa.get_mapping(year)
            placed = {k: v for k, v in mapping.items()
                      if k.startswith("sch_ca_line_part_ii_")}
            with self.subTest(year=year):
                self.assertEqual(
                    placed,
                    {_key(token): cells[token]
                     for token in _expected(year) if token != "30"}
                    | {_key("5cA"): cells["5cA"], _key("12A"): cells["12A"]})
                self.assertIn(cells["30"], PdfSchCa.get_derivations(year))

    def test_transit_sums_are_owned_as_suppressed(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertLessEqual(
                    {"sch_ca_part_ii_medical", "sch_ca_part_ii_taxes",
                     "sch_ca_part_ii_mortgage", "sch_ca_part_ii_charity",
                     "ca_itemized_total"},
                    PdfSchCa.get_suppressed(year))


class PartIIBlankOnAStandardDeductionReturnTests(unittest.TestCase):
    def test_no_part_ii_cell_prints(self):
        for year in CA_YEARS:
            _, pdfs = emit_ca(make_ca_scenario(year))
            printed = _printed(pdfs["sch_ca"])
            cells = part_ii_cells(_template(year))
            with self.subTest(year=year):
                self.assertEqual(
                    {t: printed[f] for t, f in cells.items()
                     if printed[f] is not None}, {})


class Line29LimitationIsRefusedTests(unittest.TestCase):
    """Line 29 prints line 28 unreduced. That is only right while federal AGI
    is at or under the line-29 threshold; above it the return must not emit."""

    def test_itemizer_above_the_threshold_is_refused(self):
        for year in CA_YEARS:
            wages = float(ca_params.load(year).agi_phaseout_threshold + 1_000)
            scenario = itemizing_scenario(
                year, wages=wages, ss_wages=wages, medicare_wages=wages,
                state_wages=wages)
            with self.subTest(year=year):
                with self.assertRaises(NotImplementedError):
                    emit_ca(scenario)

    def test_threshold_param_is_the_single_amount_printed_on_line_29(self):
        for year in CA_YEARS:
            cells = part_ii_cells(_template(year))
            tooltip = str(PdfReader(str(_template(year)))
                          .get_fields()[cells["29"]].get("/TU"))
            first_amount = re.search(r"\$([\d,]+)", tooltip)
            with self.subTest(year=year):
                self.assertRegex(tooltip, r"^Line 29\. .*Single")
                self.assertEqual(
                    int(first_amount.group(1).replace(",", "")),
                    ca_params.load(year).agi_phaseout_threshold)


if __name__ == "__main__":
    unittest.main()
