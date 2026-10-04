"""Form 540 face: header identity, DOB, exemptions (lines 7-11), state wages
(line 12), the line-91 no-use-tax box, third-party designee "No", and the
per-page name/SSN headers — filled for every supported year.

All values are synthetic. Dollar expectations are derived from the year's CA
params (never from the code under test): 2024 single = 149 is pinned literally.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.forms import f540 as form_f540
from tenforty.mappings.pdf_f540 import (
    PdfF540, _ADJUSTMENT_LINES, _YEAR_PRESENTATION, _line_15)
from tenforty.models import CA540Return, FilingStatus
from tenforty.params import california as ca_params
from tests._ca_emit_helpers import CA_YEARS, emit_ca, make_ca_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect


def field_values(pdf_path) -> dict[str, str]:
    out = {}
    for name, f in PdfReader(str(pdf_path)).get_fields().items():
        v = f.get("/V")
        if v not in (None, "", "/Off"):
            out[name] = str(v)
    return out


def field_for(year: int, key: str) -> str:
    return PdfF540.get_mapping(year)[key]


class Emitted540Tests(unittest.TestCase):
    """End-to-end (scenario -> compute -> mapping -> fill) per year."""

    @classmethod
    def setUpClass(cls):
        cls.emits = {}
        for year in CA_YEARS:
            results, pdfs = emit_ca(make_ca_scenario(year))
            cls.emits[year] = (results, pdfs["f540"], field_values(pdfs["f540"]))

    def test_header_identity_and_dob(self):
        for year, (_, _, v) in self.emits.items():
            with self.subTest(year=year):
                for key, expected in (
                    ("f540_taxpayer_first_name", "Smoke"),
                    ("f540_taxpayer_last_name", "Test"),
                    ("f540_address_street", "1 Example Ave"),
                    ("f540_address_city", "Los Angeles"),
                    ("f540_address_state", "CA"),
                    ("f540_address_zip", "90001"),
                    ("f540_taxpayer_dob", "01/01/1980"),   # config birthdate 1980-01-01
                    ("f540_taxpayer_ssn", "000-00-0000"),
                ):
                    self.assertEqual(v.get(field_for(year, key)), expected, key)

    def test_line7_exemption_count_and_amount(self):
        for year, (_, _, v) in self.emits.items():
            with self.subTest(year=year):
                per_person = ca_params.load(year).exemption_credit["single"]
                self.assertEqual(v[field_for(year, "f540_line7_count")], "1")
                self.assertEqual(v[field_for(year, "f540_line7_amount")], str(per_person))
        # literal pin independent of the params module: 2024 single = $149
        self.assertEqual(
            self.emits[2024][2][field_for(2024, "f540_line7_amount")], "149")

    def test_line11_equals_line32_and_prints_149_for_2024_single(self):
        for year, (results, _, v) in self.emits.items():
            with self.subTest(year=year):
                line11 = v[field_for(year, "f540_line11_exemption_amount")]
                self.assertEqual(line11, v[field_for(year, "f540_exemption_credit")])
                self.assertEqual(line11, str(results["f540_exemption_credit"]))
        self.assertEqual(
            self.emits[2024][2][field_for(2024, "f540_line11_exemption_amount")], "149")

    def test_line12_state_wages_is_w2_box16_sum(self):
        # fixture W-2: wages 80,000 / box-16 state wages 80,000
        for year, (_, _, v) in self.emits.items():
            with self.subTest(year=year):
                self.assertEqual(v[field_for(year, "f540_line12_state_wages")], "80000")

    def test_line91_prints_explicit_zero_and_no_use_tax_box_checked(self):
        for year, (_, pdf, v) in self.emits.items():
            with self.subTest(year=year):
                self.assertEqual(v[field_for(year, "f540_use_tax")], "0")
                radio, token = _YEAR_PRESENTATION[year][7]
                self.assertEqual(v[radio], token)

    def test_third_party_designee_no_is_checked(self):
        for year, (_, _, v) in self.emits.items():
            with self.subTest(year=year):
                radio, token = _YEAR_PRESENTATION[year][8]
                self.assertEqual(v[radio], token)

    def test_per_page_name_and_ssn_headers(self):
        for year, (_, _, v) in self.emits.items():
            with self.subTest(year=year):
                prefix, _, _, _, _, names, ssns = _YEAR_PRESENTATION[year][:7]
                for f in names:
                    self.assertEqual(v[prefix + f], "Smoke Q Test")
                for f in ssns:
                    self.assertEqual(v[prefix + f], "000-00-0000")

    def test_lines_13_to_17_foot_on_the_page(self):
        for year, (results, _, v) in self.emits.items():
            with self.subTest(year=year):
                prefix = _YEAR_PRESENTATION[year][0]
                l14, l15, l16, _ = (prefix + n for n in _ADJUSTMENT_LINES[year])
                l13 = v[field_for(year, "f540_federal_agi")]
                l17 = v[field_for(year, "f540_ca_agi")]
                self.assertEqual(int(l13) - int(v[l14]), int(v[l15]))
                self.assertEqual(int(v[l15]) + int(v[l16]), int(l17))

    def test_line71_ca_withholding_prints(self):
        for year, (results, _, v) in self.emits.items():
            with self.subTest(year=year):
                self.assertEqual(results["f540_line71_ca_withholding"], 4000)
                self.assertEqual(v[field_for(year, "f540_line71_ca_withholding")], "4000")

    def test_all_new_cells_render_ink(self):
        """Pixels, not field state: each newly-filled cell shows ink."""
        for year, (_, pdf, v) in self.emits.items():
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                for key in ("f540_taxpayer_first_name", "f540_taxpayer_last_name",
                            "f540_address_street", "f540_address_city",
                            "f540_address_zip", "f540_taxpayer_dob",
                            "f540_line7_count", "f540_line7_amount",
                            "f540_line11_exemption_amount",
                            "f540_line12_state_wages"):
                    page, rect = widget_rect(pdf, mapping[key])
                    self.assertGreater(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 8, key)
                for radio, token in (_YEAR_PRESENTATION[year][7], _YEAR_PRESENTATION[year][8]):
                    page, rect = widget_rect(pdf, radio, token)
                    self.assertGreater(dark_pixels_in_rect(pdf, page, rect), 15, radio)


class Line15Tests(unittest.TestCase):
    def test_negative_line_15_is_in_parentheses(self):
        self.assertEqual(
            _line_15({"f540_federal_agi": 1000, "sch_ca_total_subtractions": 1500}), "(500)")
        self.assertEqual(
            _line_15({"f540_federal_agi": 1000, "sch_ca_total_subtractions": 400}), "600")


class RadioTokenGeometryTests(unittest.TestCase):
    """The opaque "/0" "/1" tokens are pinned to the printed labels by position:
    "No use tax is owed" is the LEFT box of the pair; designee "Yes" is left,
    "No" is right (2025 render crop confirms the labels)."""

    def test_no_use_tax_is_left_and_designee_no_is_right(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                pdf = Path(__file__).parent.parent / "pdfs" / "california" / str(year) / "f540.pdf"
                (use_radio, use_tok), (des_radio, des_tok) = (
                    _YEAR_PRESENTATION[year][7], _YEAR_PRESENTATION[year][8])
                rects = {}
                for page in PdfReader(str(pdf)).pages:
                    for a in page.get("/Annots", []) or []:
                        w = a.get_object()
                        parent = w.get("/Parent")
                        name = str(parent.get_object().get("/T")) if parent else str(w.get("/T"))
                        if name in (use_radio, des_radio):
                            for state in w["/AP"]["/N"]:
                                rects[(name, str(state))] = float(w["/Rect"][0])
                use_boxes = sorted((x, s) for (n, s), x in rects.items() if n == use_radio)
                des_boxes = sorted((x, s) for (n, s), x in rects.items() if n == des_radio)
                self.assertEqual(use_boxes[0][1], use_tok)      # left box
                self.assertEqual(des_boxes[-1][1], des_tok)     # right box


class PresentationKeysTests(unittest.TestCase):
    """presentation_keys across every filing status (MFJ/MFS cannot go through
    the workbook, so the pure function is exercised directly)."""

    def test_personal_exemption_count_and_amount_per_status(self):
        expected_count = {
            FilingStatus.SINGLE: 1, FilingStatus.MARRIED_SEPARATELY: 1,
            FilingStatus.HEAD_OF_HOUSEHOLD: 1,
            FilingStatus.MARRIED_JOINTLY: 2, FilingStatus.QUALIFYING_WIDOW: 2,
        }
        for year in CA_YEARS:
            single = ca_params.load(year).exemption_credit["single"]
            for fs, count in expected_count.items():
                with self.subTest(year=year, fs=fs.value):
                    cfg = make_ca_scenario(year, fs).config
                    keys = form_f540.presentation_keys(cfg, [], year)
                    self.assertEqual(keys["f540_line7_count"], count)
                    self.assertEqual(keys["f540_line7_amount"], count * single)
                    self.assertNotIn("f540_line10_count", keys)   # zero -> blank
                    self.assertNotIn("f540_line12_state_wages", keys)  # no W-2s

    def test_dependents_fill_line10_and_line11_matches_line32(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                cfg = make_ca_scenario(year, dependents=("Dep One", "Dep Two")).config
                keys = form_f540.presentation_keys(cfg, [], year)
                dep_amt = ca_params.load(year).dependent_exemption_amount
                self.assertEqual(keys["f540_line10_count"], 2)
                self.assertEqual(keys["f540_line10_amount"], 2 * dep_amt)
                compute = form_f540.compute(
                    year=year, filing_status=cfg.filing_status, federal_agi=80_000,
                    ca_agi=80_000, ca540=CA540Return(),
                    num_dependents=2)
                self.assertEqual(keys["f540_line11_exemption_amount"],
                                 compute["f540_exemption_credit"])

    def test_middle_initial_emitted_when_set_and_absent_when_empty(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                base = make_ca_scenario(year).config
                cfg = dataclasses.replace(base, middle_initial="Z")
                keys = form_f540.presentation_keys(cfg, [], year)
                self.assertEqual(keys["f540_taxpayer_middle_initial"], "Z")
                self.assertEqual(keys["f540_taxpayer_first_name"], "Smoke")
                # Control: the same call with the initial blanked drops the key.
                blank = dataclasses.replace(base, middle_initial="")
                self.assertNotIn("f540_taxpayer_middle_initial",
                                 form_f540.presentation_keys(blank, [], year))

    def test_dob_must_be_iso(self):
        cfg = dataclasses.replace(make_ca_scenario(2024).config, birthdate="01/01/1980")
        with self.assertRaises(ValueError):
            form_f540.presentation_keys(cfg, [], 2024)


if __name__ == "__main__":
    unittest.main()
