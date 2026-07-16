"""Static structure tests for the Schedule D PDF field mapping."""

import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_d import PdfSchD
from tests.helpers import REPO_ROOT

SCH_D_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040sd.pdf"
)

_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040sd.pdf"

_REQUIRED_SCALARS = (
    "taxpayer_name", "taxpayer_ssn",
    "sch_d_line_1a_proceeds", "sch_d_line_1a_basis", "sch_d_line_1a_gain",
    "sch_d_line_7_net_short",
    "sch_d_line_8a_proceeds", "sch_d_line_8a_basis", "sch_d_line_8a_gain",
    "sch_d_line_15_net_long",
    "sch_d_line_16_total",
)


class PdfSchDStructureTests(unittest.TestCase):
    def test_2025_has_summary_scalars(self):
        m = PdfSchD.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_SCALARS:
            self.assertIn(k, scalars, f"missing scalar: {k}")

    def test_2025_repeaters_is_empty(self):
        m = PdfSchD.get_mapping(2025)
        self.assertEqual(m.get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_D_TEMPLATE.exists():
            self.skipTest(f"Sch D template not available at {SCH_D_TEMPLATE}")
        reader = PdfReader(str(SCH_D_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in PdfSchD.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040sd.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(PdfSchD.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchD mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule D"):
            PdfSchD.get_mapping(1999)


class TestPdfSchDFullLineGrid(unittest.TestCase):
    """Verify the full Part I / Part II line grid plus page-2 lines 18/19."""

    def test_all_new_lines_present(self) -> None:
        m = PdfSchD.get_mapping(2025)
        for line, kind in [
            ("1b", "proceeds"), ("1b", "basis"), ("1b", "gain"),
            ("2",  "proceeds"), ("2",  "basis"), ("2",  "gain"),
            ("3",  "proceeds"), ("3",  "basis"), ("3",  "gain"),
            ("4",  "gain"),
            ("5",  "net_short_k1"),
            ("6",  "loss_carryover"),
            ("8b", "proceeds"), ("8b", "basis"), ("8b", "gain"),
            ("9",  "proceeds"), ("9",  "basis"), ("9",  "gain"),
            ("10", "proceeds"), ("10", "basis"), ("10", "gain"),
            ("11", "gain"),
            ("12", "net_long_k1"),
            ("13", "cap_gain_dist"),
            ("14", "loss_carryover"),
        ]:
            self.assertIn(f"sch_d_line_{line}_{kind}", m["scalars"])
        self.assertIn("sch_d_unrecap_1250", m["scalars"])
        self.assertIn("sch_d_28_rate_gain", m["scalars"])


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule D template not present")
class PdfSchD2021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule D template via PdfFiller with distinctive
    values, then read the cells back directly with pypdf — no soffice.

    The lines-18/19 placement test is the regression that would have caught
    the historically-swapped-key-name bug: the compute stores the
    unrecaptured-§1250 dollars under the key
    ``sch_d_unrecap_1250`` and the 28%-rate dollars under
    ``sch_d_28_rate_gain``, but on the form itself line 18's box is
    ``f2_02`` and line 19's box is ``f2_03``. So the unrecap-1250 amount must
    land in ``f2_03`` (form line 19) and the 28%-rate amount must land in
    ``f2_02`` (form line 18). The merged 2022-2025 mappings route these
    backwards (a known, separately-tracked swap bug); this test locks in the
    corrected 2021 placement and must never be "fixed" to match the merged
    years.
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        scalars = PdfSchD.get_mapping(2021)["scalars"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040sd_2021.pdf"
            PdfFiller().fill(
                template_path=_TEMPLATE_2021,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            return {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }

    def test_lines_18_19_placement_is_content_correct(self):
        # Distinct sentinels so a swap is unambiguous either way.
        values = {
            "sch_d_unrecap_1250": 1250,
            "sch_d_28_rate_gain": 2800,
        }
        read = self._fill_and_read(values)
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].f2_03[0]"), "1250",
            "unrecap-§1250 sentinel (1250) must land in f2_03 "
            "(the form's line-19 box)",
        )
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].f2_02[0]"), "2800",
            "28%-rate sentinel (2800) must land in f2_02 "
            "(the form's line-18 box)",
        )

    def test_representative_scalar_subset_round_trips(self):
        scalars = PdfSchD.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct SchD Filer",
            "taxpayer_ssn": "111-00-2021",
            "sch_d_line_16_total": 44_444,
            "sch_d_line_1a_proceeds": 10_001,
            "sch_d_line_1a_basis": 10_002,
            "sch_d_line_1a_gain": 10_003,
            "sch_d_line_8a_proceeds": 80_001,
            "sch_d_line_8a_basis": 80_002,
            "sch_d_line_8a_gain": 80_003,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))


def _page2_box_ordinal(field_path: str) -> int:
    """Extract the trailing page-2 field index from a Sch D box path, e.g.
    3 from ``...Page2[0].f2_03[0]`` (2024) or from ``...Page2[0].f2_3[0]``
    (2025). Used to identify box *position* independent of field-name
    padding scheme, and independent of which result key currently points
    at it (so it works even while the swap bug is present)."""
    m = re.search(r"f2_(\d+)\[0\]$", field_path)
    if not m:
        raise ValueError(f"cannot extract page-2 field ordinal from {field_path!r}")
    return int(m.group(1))


class PdfSchDMergedYearsPlacementTests(unittest.TestCase):
    """Fill each merged-year (2022-2025) Schedule D template via PdfFiller
    with distinctive sentinels, then read the cells back with pypdf.

    Box identity (which physical box is the line-18/28%-rate box vs. the
    line-19/unrecap box) is derived WITHOUT relying on the very key->box
    mapping under test (which is exactly what's swapped for 2022-2025).
    Instead:

    1. The *set* of two candidate box paths for a year is taken from that
       year's own mapping (the swap only cross-wires which key points to
       which box in the pair — it does not change the pair itself).
    2. Which member of the pair is the line-18 box vs. the line-19 box is
       decided by ordinal position (lower page-2 field index = line 18,
       appears first on the page; higher = line 19), using the SAME
       ordinal parity established by the 2021 reference block (verified
       there to be non-swapped) — never a hardcoded "f2_02"/"f2_03"
       literal, since 2025 uses non-padded field names (f2_2/f2_3).
    """

    _TEMPLATES = {
        2022: REPO_ROOT / "pdfs" / "federal" / "2022" / "f1040sd.pdf",
        2023: REPO_ROOT / "pdfs" / "federal" / "2023" / "f1040sd.pdf",
        2024: REPO_ROOT / "pdfs" / "federal" / "2024" / "f1040sd.pdf",
        2025: REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040sd.pdf",
    }

    def _fill_and_read(self, year: int, values: dict) -> dict[str, str]:
        scalars = PdfSchD.get_mapping(year)["scalars"]
        template = self._TEMPLATES[year]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / f"f1040sd_{year}.pdf"
            PdfFiller().fill(
                template_path=template,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            return {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }

    def test_lines_18_19_placement_is_content_correct(self):
        # Establish the ordinal parity from the 2021 reference block (the
        # known-correct routing): is the unrecap box the lower- or
        # higher-ordinal member of its pair?
        ref_scalars = PdfSchD.get_mapping(2021)["scalars"]
        ref_unrecap_ordinal = _page2_box_ordinal(
            ref_scalars["sch_d_unrecap_1250"]
        )
        ref_rate_28_ordinal = _page2_box_ordinal(
            ref_scalars["sch_d_28_rate_gain"]
        )
        self.assertNotEqual(ref_unrecap_ordinal, ref_rate_28_ordinal)
        unrecap_is_lower_ordinal = ref_unrecap_ordinal < ref_rate_28_ordinal

        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                if not self._TEMPLATES[year].exists():
                    self.skipTest(
                        f"Sch D template not available for {year}"
                    )
                scalars = PdfSchD.get_mapping(year)["scalars"]
                # The *pair* of candidate boxes is swap-invariant even
                # though which key currently targets which box is not.
                pair = sorted(
                    (
                        scalars["sch_d_unrecap_1250"],
                        scalars["sch_d_28_rate_gain"],
                    ),
                    key=_page2_box_ordinal,
                )
                lower_ordinal_box, higher_ordinal_box = pair
                if unrecap_is_lower_ordinal:
                    unrecap_box, rate_28_box = lower_ordinal_box, higher_ordinal_box
                else:
                    rate_28_box, unrecap_box = lower_ordinal_box, higher_ordinal_box

                values = {
                    "sch_d_unrecap_1250": 1111,
                    "sch_d_28_rate_gain": 2222,
                }
                read = self._fill_and_read(year, values)
                self.assertEqual(
                    read.get(unrecap_box), "1111",
                    f"{year}: unrecap-§1250 sentinel (1111) must land in "
                    f"{unrecap_box!r} (the form's line-19/unrecap box)",
                )
                self.assertEqual(
                    read.get(rate_28_box), "2222",
                    f"{year}: 28%-rate sentinel (2222) must land in "
                    f"{rate_28_box!r} (the form's line-18/28%-rate box)",
                )


if __name__ == "__main__":
    unittest.main()
