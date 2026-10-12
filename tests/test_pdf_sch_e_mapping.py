"""Static structure tests for the Schedule E PDF field mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_e import PdfSchE
from tests.helpers import REPO_ROOT
from tests.test_sch_e_totals_and_line_27 import _widget_path

SCH_E_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040se.pdf"
)

_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040se.pdf"

_REQUIRED_SCALARS = (
    "taxpayer_name", "taxpayer_ssn",
    "sch_e_property_a_address",
    "sch_e_property_a_type_code",
    "sch_e_property_a_fair_rental_days",
    "sch_e_property_a_personal_use_days",
    "sch_e_property_a_rents",
    "sch_e_property_a_total_expenses",
    "sch_e_property_a_income_loss",
)

_REQUIRED_PART_II_SCALARS = (
    # Page 2 header
    "taxpayer_name_page2",
    "taxpayer_ssn_page2",
    # Per-row fields for all four K-1 rows
    "sch_e_part_ii_row_a_name",
    "sch_e_part_ii_row_a_ein",
    "sch_e_part_ii_row_a_entity_code",
    "sch_e_part_ii_row_a_passive_income",
    "sch_e_part_ii_row_a_passive_loss",
    "sch_e_part_ii_row_a_nonpassive_income",
    "sch_e_part_ii_row_a_nonpassive_loss",
    "sch_e_part_ii_row_b_name",
    "sch_e_part_ii_row_b_ein",
    "sch_e_part_ii_row_b_passive_income",
    "sch_e_part_ii_row_b_passive_loss",
    "sch_e_part_ii_row_b_nonpassive_income",
    "sch_e_part_ii_row_b_nonpassive_loss",
    "sch_e_part_ii_row_c_name",
    "sch_e_part_ii_row_c_ein",
    "sch_e_part_ii_row_c_passive_income",
    "sch_e_part_ii_row_c_passive_loss",
    "sch_e_part_ii_row_c_nonpassive_income",
    "sch_e_part_ii_row_c_nonpassive_loss",
    "sch_e_part_ii_row_d_name",
    "sch_e_part_ii_row_d_ein",
    "sch_e_part_ii_row_d_passive_income",
    "sch_e_part_ii_row_d_passive_loss",
    "sch_e_part_ii_row_d_nonpassive_income",
    "sch_e_part_ii_row_d_nonpassive_loss",
    # Line 29 column totals
    "sch_e_line_29a_total_passive_income",
    "sch_e_line_29a_total_nonpassive_income",
    "sch_e_line_29b_total_passive_loss",
    "sch_e_line_29b_total_nonpassive_loss",
    # Line 30, 31, 32 summary
    "sch_e_line_32_total_partnership_scorp",
    # Line 37 (estate/trust, always 0 in Plan D)
    "sch_e_line_37_total_estate_trust",
    # Line 41 (total income/(loss) grand total = line 26 + line 32)
    "sch_e_line_41_total_income",
)


class PdfSchEStructureTests(unittest.TestCase):
    def test_2025_has_property_a_scalars(self):
        m = PdfSchE.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_SCALARS:
            self.assertIn(k, scalars, f"missing scalar: {k}")

    def test_2025_has_empty_repeaters_v1(self):
        m = PdfSchE.get_mapping(2025)
        self.assertEqual(m.get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_E_TEMPLATE.exists():
            self.skipTest(f"Sch E template not available at {SCH_E_TEMPLATE}")
        reader = PdfReader(str(SCH_E_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in PdfSchE.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040se.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(PdfSchE.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchE mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule E"):
            PdfSchE.get_mapping(1999)


class PdfSchEPartIIStructureTests(unittest.TestCase):
    """Tests for Part II (K-1 / pass-through) scalars added for Plan D."""

    def test_2025_has_part_ii_scalars(self):
        m = PdfSchE.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_PART_II_SCALARS:
            self.assertIn(k, scalars, f"missing Part II scalar: {k}")

    def test_2025_every_part_ii_value_is_a_real_pdf_field(self):
        if not SCH_E_TEMPLATE.exists():
            self.skipTest(f"Sch E template not available at {SCH_E_TEMPLATE}")
        reader = PdfReader(str(SCH_E_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        m = PdfSchE.get_mapping(2025)
        for key in _REQUIRED_PART_II_SCALARS:
            pdf_field = m["scalars"].get(key)
            self.assertIsNotNone(pdf_field, f"key {key!r} not in scalars")
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040se.pdf",
            )

    def test_2025_scalar_values_are_unique_after_part_ii_extension(self):
        """All scalars (Part I + Part II) must map to distinct PDF fields."""
        values = list(PdfSchE.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchE mapping has duplicate PDF field targets after Part II extension",
        )


class TestPdfSchERowsSnapshot(unittest.TestCase):
    """Snapshot test for pdf_sch_e Part II row mapping (SP1-N9).

    Ensures the loop-based row generator emits the exact same PDF field names
    as the hand-written blocks so the refactor is bit-identical."""

    def test_row_a_through_d_fields(self) -> None:
        m = PdfSchE.get_mapping(2025)
        scalars = m["scalars"]
        expected = {
            # Row A
            "sch_e_part_ii_row_a_name":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].f2_3[0]",
            "sch_e_part_ii_row_a_entity_code":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].f2_4[0]",
            "sch_e_part_ii_row_a_ein":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].f2_5[0]",
            "sch_e_part_ii_row_a_passive_loss":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_15[0]",
            "sch_e_part_ii_row_a_passive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_16[0]",
            "sch_e_part_ii_row_a_nonpassive_loss":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_17[0]",
            "sch_e_part_ii_row_a_nonpassive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_19[0]",
            # Row D (spot-check stride)
            "sch_e_part_ii_row_d_name":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowD[0].f2_12[0]",
            "sch_e_part_ii_row_d_nonpassive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_34[0]",
        }
        for k, expected_value in expected.items():
            self.assertEqual(scalars.get(k), expected_value, f"field {k}")


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule E template not present")
class PdfSchE2021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule E template via PdfFiller with distinctive
    values, then read the cells back directly with pypdf — no soffice.

    Locks in the render-verified 2021 placements: row-A name in col (a)
    (f2_3) and EIN in col (d) (f2_5); the four LIVE line-29 totals
    (income-on-29a, loss-on-29b); and a Part I property row amount. If any
    value fails to land at its mapped path the test fails loudly — it must
    never be weakened to match the merged-2022-2025 mapping (which carries a
    separately-tracked line-28 ein/entity-type mismapping bug).
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        scalars = PdfSchE.get_mapping(2021)["scalars"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040se_2021.pdf"
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

    def test_representative_subset_round_trips(self):
        scalars = PdfSchE.get_mapping(2021)["scalars"]
        values = {
            # Part II row-A name (col a → f2_3) + EIN (col d → f2_5)
            "sch_e_part_ii_row_a_name": "Distinct SchE K1 Entity",
            # Non-EIN-shaped sentinel so the personal-data denylist stays clean;
            # the col-(d) cell is a free-text field, so any token round-trips.
            "sch_e_part_ii_row_a_ein": "EIN-SENTINEL-COL-D",
            # The four LIVE line-29 totals (income-on-29a, loss-on-29b)
            "sch_e_line_29a_total_passive_income": 29_101,
            "sch_e_line_29a_total_nonpassive_income": 29_102,
            "sch_e_line_29b_total_passive_loss": 29_201,
            "sch_e_line_29b_total_nonpassive_loss": 29_202,
            # A Part I property-A row field
            "sch_e_property_a_rents": 33_333,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))

    def test_row_a_name_and_ein_land_in_cols_a_and_d(self):
        # Distinct sentinels so a col-a/col-d swap is unambiguous.
        values = {
            "sch_e_part_ii_row_a_name": "NAME-COL-A",
            "sch_e_part_ii_row_a_ein": "EIN-COL-D",
        }
        read = self._fill_and_read(values)
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_3[0]"),
            "NAME-COL-A",
            "row-A name must land in f2_3 (Line 28 col (a))",
        )
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_5[0]"),
            "EIN-COL-D",
            "row-A EIN must land in f2_5 (Line 28 col (d))",
        )


def _resolve_row_a_field_paths(template_path: Path) -> dict[str, str]:
    """Independently resolve the col-(b)/(c)/(d)/(e) PDF field paths for
    Schedule E Line 28 row A directly from the TEMPLATE's own AcroForm
    geometry (x-position) — NOT from the PdfSchE mapping under test. This
    is what lets the placement test below actually catch a mapping bug
    instead of asserting against itself (a tautology).

    IRS Schedule E Line 28 column order (confirmed via `pdftotext -layout`
    against pdfs/federal/2025/f1040se.pdf, page 2): (a) Name, (b) Enter P
    for partnership; S for S corporation, (c) Check if foreign partnership,
    (d) Employer identification number, (e) Check if basis computation is
    required, (f) Check if any amount is not at risk. On every year's
    template (2021-2025) the row's widgets sort left-to-right into exactly
    that column order, independent of the underlying field-name numbering
    (which differs by year / zero-padding), so a left-to-right sort of the
    row's own text/checkbox widgets recovers column identity without
    trusting any tenforty mapping.
    """
    reader = PdfReader(str(template_path))
    page = reader.pages[1]  # Page 2 (0-indexed) on every year 2021-2025
    texts: list[tuple[float, str]] = []
    checks: list[tuple[float, str]] = []
    for annot in page.get("/Annots") or []:
        obj = annot.get_object()
        chain = []
        cur = obj
        while cur is not None:
            t = cur.get("/T")
            if t:
                chain.append(str(t))
            parent = cur.get("/Parent")
            cur = parent.get_object() if parent is not None else None
        fq = ".".join(reversed(chain))
        # "Table_Line28a" matches both the 2021 "...28a-e[0]" and the
        # 2022-2025 "...28a-f[0]" containers, while excluding the separate
        # "Table_Line28g-k[0]" (passive/nonpassive columns) sub-table, which
        # also has a "RowA[0]".
        if "Table_Line28a" not in fq or "RowA[0]" not in fq:
            continue
        rect = obj.get("/Rect")
        if rect is None:
            continue
        x0 = float(rect[0])
        ft = obj.get("/FT")
        if ft == "/Tx":
            texts.append((x0, fq))
        elif ft == "/Btn":
            checks.append((x0, fq))
    texts.sort(key=lambda p: p[0])
    checks.sort(key=lambda p: p[0])
    assert len(texts) == 3, f"expected 3 text fields for row A, got {texts}"
    assert len(checks) == 3, f"expected 3 checkboxes for row A, got {checks}"
    return {
        "name": texts[0][1],              # col (a)
        "entity_code": texts[1][1],       # col (b) — "Enter P/S"
        "ein": texts[2][1],               # col (d)
        "foreign_checkbox": checks[0][1],  # col (c) — not modeled
        "basis_checkbox": checks[1][1],    # col (e) — not modeled
        "at_risk_checkbox": checks[2][1],  # col (f) — not modeled
    }


class PdfSchELine28PlacementTests(unittest.TestCase):
    """Fill each year's real Schedule E template via PdfFiller with a K-1
    row (entity_code="S", a synthetic EIN sentinel), read the cells back
    with pypdf, and confirm they land in the correct real column — resolved
    independently per-year from the template itself (see
    _resolve_row_a_field_paths), not from the mapping under test.

    Guards the merged-2022-2025 bug (EIN routed to col (b), the two
    unmodeled checkboxes wrongly filled from the entity-type booleans) and
    its 2021 counterpart (col (b) left entirely unmapped) across every
    supported year."""

    # Non-EIN-shaped sentinel so the personal-data denylist stays clean (see
    # the same idiom in PdfSchE2021EmitRoundTripTests above); the col-(d)
    # cell is a free-text field, so any token round-trips.
    _SENTINEL_EIN = "EIN-SENTINEL-COL-D"

    _YEARS = (2021, 2022, 2023, 2024, 2025)

    def _check_year(self, year: int) -> None:
        template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
        if not template.exists():
            self.skipTest(f"Sch E {year} template not available at {template}")
        paths = _resolve_row_a_field_paths(template)
        scalars = PdfSchE.get_mapping(year)["scalars"]
        values = {
            "sch_e_part_ii_row_a_name": "Placement Test Entity",
            "sch_e_part_ii_row_a_entity_code": "S",
            "sch_e_part_ii_row_a_ein": self._SENTINEL_EIN,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / f"f1040se_{year}_placement.pdf"
            PdfFiller().fill(
                template_path=template,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }

        self.assertEqual(
            read.get(paths["entity_code"]), "S",
            f"{year}: 'S' must land in col (b) 'Enter P/S' field "
            f"{paths['entity_code']!r}, got {read.get(paths['entity_code'])!r}",
        )
        self.assertEqual(
            read.get(paths["ein"]), self._SENTINEL_EIN,
            f"{year}: EIN sentinel must land in col (d) EIN field "
            f"{paths['ein']!r}, got {read.get(paths['ein'])!r}",
        )
        self.assertIn(
            read.get(paths["foreign_checkbox"]), (None, "", "/Off"),
            f"{year}: col (c) foreign-partnership checkbox "
            f"{paths['foreign_checkbox']!r} must stay unfilled (not modeled), "
            f"got {read.get(paths['foreign_checkbox'])!r}",
        )
        self.assertIn(
            read.get(paths["basis_checkbox"]), (None, "", "/Off"),
            f"{year}: col (e) basis-required checkbox "
            f"{paths['basis_checkbox']!r} must stay unfilled (not modeled), "
            f"got {read.get(paths['basis_checkbox'])!r}",
        )

    def test_2021(self):
        self._check_year(2021)

    def test_2022(self):
        self._check_year(2022)

    def test_2023(self):
        self._check_year(2023)

    def test_2024(self):
        self._check_year(2024)

    def test_2025(self):
        self._check_year(2025)



# ── Property columns A/B/C (page 1, lines 1a-22) ──────────────────────────
# A literal transcription of the widget table, typed here and NOT imported
# from the mapping under test: suffix -> (container on the 2022-2025
# templates, (column A leaf, column B leaf, column C leaf)).
_PAGE_1 = "topmostSubform[0].Page1[0]."
_COLUMN_CELLS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "address": ("Table_Line1a[0].Row{row}[0]", (3, 4, 5)),
    "type_code": ("Table_Line1b[0].Row{row}[0]", (6, 7, 8)),
    "fair_rental_days": ("Table_Line2[0].Row{row}[0]", (9, 11, 13)),
    "personal_use_days": ("Table_Line2[0].Row{row}[0]", (10, 12, 14)),
    "rents": ("Table_Income[0].Line3[0]", (16, 17, 18)),
    "advertising": ("Table_Expenses[0].Line5[0]", (22, 23, 24)),
    "auto_and_travel": ("Table_Expenses[0].Line6[0]", (25, 26, 27)),
    "cleaning_and_maintenance": ("Table_Expenses[0].Line7[0]", (28, 29, 30)),
    "commissions": ("Table_Expenses[0].Line8[0]", (31, 32, 33)),
    "insurance": ("Table_Expenses[0].Line9[0]", (34, 35, 36)),
    "legal_and_professional_fees":
        ("Table_Expenses[0].Line10[0]", (37, 38, 39)),
    "management_fees": ("Table_Expenses[0].Line11[0]", (40, 41, 42)),
    "mortgage_interest": ("Table_Expenses[0].Line12[0]", (43, 44, 45)),
    "other_interest": ("Table_Expenses[0].Line13[0]", (46, 47, 48)),
    "repairs": ("Table_Expenses[0].Line14[0]", (49, 50, 51)),
    "supplies": ("Table_Expenses[0].Line15[0]", (52, 53, 54)),
    "taxes": ("Table_Expenses[0].Line16[0]", (55, 56, 57)),
    "utilities": ("Table_Expenses[0].Line17[0]", (58, 59, 60)),
    "depreciation": ("Table_Expenses[0].Line18[0]", (61, 62, 63)),
    "other_expenses": ("Table_Expenses[0].Line19[0]", (65, 66, 67)),
    "total_expenses": ("Table_Expenses[0].Line20[0]", (68, 69, 70)),
    "income_loss": ("Table_Expenses[0].Line21[0]", (71, 72, 73)),
    "deductible_loss": ("Table_Expenses[0].Line22[0]", (74, 75, 76)),
}
# The 2021 template nests three of the containers differently.
_COLUMN_CONTAINERS_2021: dict[str, str] = {
    "address": "Line1[0].Table1a[0].Row{row}[0]",
    "type_code": "Line1[0].Table1b[0].Row{row}[0]",
    "rents": "Table_Income[0].Income[0].Line3[0]",
}
# The 2022 template zero-pads its single-digit text leaves.
_PADDED_LEAVES_2022: dict[int, str] = {
    3: "f1_03[0]", 4: "f1_04[0]", 5: "f1_05[0]", 6: "f1_06[0]",
    7: "f1_07[0]", 8: "f1_08[0]", 9: "f1_09[0]",
}
_COLUMN_YEARS = (2021, 2022, 2023, 2024, 2025)
_COLUMN_LETTERS = ("a", "b", "c")
# Rows that stack A/B/C top to bottom; every other suffix runs left to right.
_STACKED_SUFFIXES = (
    "address", "type_code", "fair_rental_days", "personal_use_days")


def _literal_column_path(year: int, suffix: str, column: int) -> str:
    container, leaves = _COLUMN_CELLS[suffix]
    if year == 2021:
        container = _COLUMN_CONTAINERS_2021.get(suffix, container)
    leaf = f"f1_{leaves[column]}[0]"
    if year == 2022:
        leaf = _PADDED_LEAVES_2022.get(leaves[column], leaf)
    return (_PAGE_1 + container.format(row="ABC"[column]) + "." + leaf)


class PropertyColumnMappingTests(unittest.TestCase):
    def test_columns_b_and_c_map_to_their_literal_widgets(self):
        for year in _COLUMN_YEARS:
            scalars = PdfSchE.get_mapping(year)["scalars"]
            for suffix in _COLUMN_CELLS:
                for column in (1, 2):
                    key = f"sch_e_property_{_COLUMN_LETTERS[column]}_{suffix}"
                    with self.subTest(year=year, key=key):
                        self.assertEqual(
                            scalars[key],
                            _literal_column_path(year, suffix, column))

    def test_column_a_paths_are_unchanged(self):
        for year in _COLUMN_YEARS:
            scalars = PdfSchE.get_mapping(year)["scalars"]
            for suffix in _COLUMN_CELLS:
                key = f"sch_e_property_a_{suffix}"
                with self.subTest(year=year, key=key):
                    self.assertEqual(
                        scalars[key], _literal_column_path(year, suffix, 0))

    def test_each_column_cell_sits_right_of_the_previous_on_the_same_row(self):
        for year in _COLUMN_YEARS:
            page = PdfReader(str(
                REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
            )).pages[0]
            rects = {_widget_path(a.get_object()):
                     [float(v) for v in a.get_object()["/Rect"]]
                     for a in page.get("/Annots", [])}
            for suffix in _COLUMN_CELLS:
                with self.subTest(year=year, suffix=suffix):
                    a, b, c = (
                        rects[_literal_column_path(year, suffix, column)]
                        for column in (0, 1, 2))
                    if suffix in _STACKED_SUFFIXES:
                        self.assertLess(abs(a[0] - b[0]), 1)
                        self.assertLess(abs(b[0] - c[0]), 1)
                        self.assertGreater(a[1], b[1])
                        self.assertGreater(b[1], c[1])
                    else:
                        self.assertLess(abs(a[1] - b[1]), 1)
                        self.assertLess(abs(b[1] - c[1]), 1)
                        self.assertLess(a[0], b[0])
                        self.assertLess(b[0], c[0])

    def test_every_mapped_path_exists_on_its_template_and_none_repeats(self):
        for year in _COLUMN_YEARS:
            with self.subTest(year=year):
                real = set((PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
                )).get_fields() or {}).keys())
                scalars = PdfSchE.get_mapping(year)["scalars"]
                for letter in _COLUMN_LETTERS:
                    for suffix in _COLUMN_CELLS:
                        self.assertIn(
                            f"sch_e_property_{letter}_{suffix}", scalars)
                missing = {k: p for k, p in scalars.items() if p not in real}
                self.assertEqual(missing, {})
                paths = list(scalars.values())
                self.assertEqual(len(paths), len(set(paths)))


if __name__ == "__main__":
    unittest.main()
