"""Structural test for pdf_sch_a mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_a import PdfSchA
from tests.helpers import REPO_ROOT


class PdfSchAMappingTests(unittest.TestCase):
    def test_has_expected_scalars_for_2025(self):
        s = PdfSchA.get_mapping(2025)["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "sch_a_line_1_medical_gross",
            "sch_a_line_4_medical_deductible",
            "sch_a_line_5a_state_income_tax",
            "sch_a_line_5b_property_tax",
            "sch_a_line_5e_salt_capped",
            "sch_a_line_7_taxes_total",
            "sch_a_line_8a_mortgage_interest",
            "sch_a_line_10_interest_total",
            "sch_a_line_11_charity_cash",
            "sch_a_line_14_charity_total",
            "sch_a_line_17_total",
        ):
            self.assertIn(k, s, f"missing scalar key: {k}")

    def test_has_empty_repeaters_in_v1(self):
        self.assertEqual(PdfSchA.get_mapping(2025)["repeaters"], {})

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022; the mapping
        # inherits the 2022 payload by reference.
        self.assertIs(PdfSchA.get_mapping(2021), PdfSchA.get_mapping(2022))


_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040sa.pdf"


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule A template not present")
class PdfSchA2021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule A template with distinctive values via the
    same mapping the orchestrator uses, then read the cells back — no soffice,
    the AcroForm is filled and re-read directly with pypdf."""

    def test_distinctive_values_round_trip(self):
        scalars = PdfSchA.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct SchA Filer",
            "taxpayer_ssn": "111-00-2021",
            "sch_a_line_1_medical_gross": 11_111,
            "sch_a_line_5b_property_tax": 22_222,
            "sch_a_line_8a_mortgage_interest": 33_333,
            "sch_a_line_17_total": 44_444,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040sa_2021.pdf"
            PdfFiller().fill(
                template_path=_TEMPLATE_2021,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))

    def test_unknown_year_raises(self):
        # 2023 is now supported (inherits 2024's identical field tree); use a
        # genuinely unsupported year to exercise the fail-closed path.
        with self.assertRaisesRegex(ValueError, "No Schedule A PDF mapping"):
            PdfSchA.get_mapping(1999)


def _widget_rects(template: Path) -> dict[str, tuple[float, float, float, float]]:
    """Fully-qualified field name -> widget /Rect (x0, y0, x1, y1)."""
    out = {}
    for page in PdfReader(str(template)).pages:
        for annot in page.get("/Annots") or []:
            widget = annot.get_object()
            parts, node = [], widget
            while node is not None:
                if "/T" in node:
                    parts.append(str(node["/T"]))
                parent = node.get("/Parent")
                node = parent.get_object() if parent is not None else None
            out[".".join(reversed(parts))] = tuple(
                float(v) for v in widget["/Rect"])
    return out


# Keys in printed top-to-bottom order. The far-right column carries the
# section results (4, 7, 10, 14, 15, 16, 17); every other money line sits in
# the inner amount column.
_MONEY_KEYS_IN_PAGE_ORDER = (
    "sch_a_line_1_medical_gross",
    "sch_a_line_2_agi",
    "sch_a_line_3_medical_floor",
    "sch_a_line_4_medical_deductible",
    "sch_a_line_5a_state_income_tax",
    "sch_a_line_5b_property_tax",
    "sch_a_line_5c_personal_property_tax",
    "sch_a_line_5d_salt_sum",
    "sch_a_line_5e_salt_capped",
    "sch_a_line_6_other_taxes",
    "sch_a_line_7_taxes_total",
    "sch_a_line_8a_mortgage_interest",
    "sch_a_line_10_interest_total",
    "sch_a_line_11_charity_cash",
    "sch_a_line_12_charity_noncash",
    "sch_a_line_14_charity_total",
    "sch_a_line_15_casualty",
    "sch_a_line_16_other",
    "sch_a_line_17_total",
)
_FAR_RIGHT_KEYS = frozenset({
    "sch_a_line_4_medical_deductible",
    "sch_a_line_7_taxes_total",
    "sch_a_line_10_interest_total",
    "sch_a_line_14_charity_total",
    "sch_a_line_15_casualty",
    "sch_a_line_16_other",
    "sch_a_line_17_total",
})


class PdfSchAAmountColumnGeometryTests(unittest.TestCase):
    """Every mapped money line must land in an AMOUNT box, in page order.

    The fields-on-template gate only proves a mapped name exists. Schedule A
    has wide write-in fields ("Other taxes. List type and amount", the line
    8b payee lines, the line 16 description lines) numbered in the same f1_NN
    sequence as the amount boxes, so a map carried over from a year with a
    different number of write-ins keeps every name valid while money prints
    into description areas and the amount boxes stay blank."""

    YEARS = (2021, 2022, 2023, 2024, 2025)

    def _rects_for(self, year):
        template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sa.pdf"
        rects = _widget_rects(template)
        scalars = PdfSchA.get_mapping(year)["scalars"]
        return {key: rects[scalars[key]] for key in _MONEY_KEYS_IN_PAGE_ORDER}

    def test_money_keys_sit_in_amount_columns(self):
        for year in self.YEARS:
            rects = self._rects_for(year)
            for key, (x0, _y0, x1, _y1) in rects.items():
                with self.subTest(year=year, key=key):
                    # Amount boxes are ~72pt wide; write-in fields are 140pt+.
                    self.assertLess(x1 - x0, 80, "not an amount-width box")
                    if key in _FAR_RIGHT_KEYS:
                        self.assertGreaterEqual(x0, 500)
                    elif key == "sch_a_line_2_agi":
                        # Line 2's box is inset left of the inner column.
                        self.assertLess(x0, 400)
                    else:
                        self.assertGreaterEqual(x0, 400)
                        self.assertLess(x0, 500)

    def test_money_keys_descend_the_page_in_line_order(self):
        for year in self.YEARS:
            rects = self._rects_for(year)
            tops = [rects[key][3] for key in _MONEY_KEYS_IN_PAGE_ORDER]
            for upper, lower, upper_top, lower_top in zip(
                    _MONEY_KEYS_IN_PAGE_ORDER, _MONEY_KEYS_IN_PAGE_ORDER[1:],
                    tops, tops[1:]):
                with self.subTest(year=year, upper=upper, lower=lower):
                    self.assertGreater(upper_top, lower_top)

    def test_no_two_money_keys_share_a_field(self):
        for year in self.YEARS:
            scalars = PdfSchA.get_mapping(year)["scalars"]
            paths = [scalars[key] for key in _MONEY_KEYS_IN_PAGE_ORDER]
            with self.subTest(year=year):
                self.assertEqual(len(paths), len(set(paths)))


if __name__ == "__main__":
    unittest.main()
