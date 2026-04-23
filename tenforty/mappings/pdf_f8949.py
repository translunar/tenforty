"""PDF field mapping for IRS Form 8949 (Sales and Other Dispositions of
Capital Assets).

Scope: boxes A, B, D, E — the four boxes addressable by the current
Form1099B model. Boxes C/F (no-1099-B scenarios) and the TY2025-new
digital-asset boxes G/H/I/J/K/L are intentionally excluded.

Field paths are transcribed from the probe recorded in issue #22 T11a.

Architecture (TY2025): The PDF uses one shared repeater table per page
(11 rows × 8 columns, stride +8). The active box is selected by checking
exactly one checkbox per page. Multiple boxes require multiple physical
copies of the same page. Boxes A and B are both on page 1; boxes D and E
are both on page 2 — so box_a_rows and box_b_rows share the same PDF field
paths (likewise D and E share page-2 paths). The filler emits a separate
copy of the page for each box.
"""

_COL_NAMES: tuple[str, ...] = (
    "description",
    "date_acquired",
    "date_sold",
    "proceeds",
    "cost_basis",
    "adjustment_code",
    "adjustment_amount",
    "gain_loss",
)

# From T11a: base field number for row 1, col 0 on each page.
# Both pages start at 03 (f1_01 and f1_02 are the name/SSN scalars above
# the table; similarly for page 2).
_PAGE_ROW1_BASE: dict[int, int] = {1: 3, 2: 3}

_ROW_STRIDE: int = 8  # confirmed uniform across columns and rows in T11a

# From T11a: 11 data row slots per page (not 14 as the earlier brief assumed).
_ROWS_PER_PAGE: int = 11

_BOX_TO_PAGE: dict[str, int] = {"a": 1, "b": 1, "d": 2, "e": 2}

# From T11a: checkbox field index within c{page}_1[idx] for each in-scope box.
_BOX_CHECKBOX_IDX: dict[str, int] = {"a": 0, "b": 1, "d": 0, "e": 1}


def _row_mapping(box_letter: str, row_idx: int) -> dict[str, str]:
    """Build the eight PDF field paths for one data row.

    Boxes A/B share the page-1 table; D/E share the page-2 table. The
    same paths appear in both box_a_rows and box_b_rows (the filler
    emits separate physical copies, one per box, with the appropriate
    checkbox set).
    """
    page = _BOX_TO_PAGE[box_letter]
    base = _PAGE_ROW1_BASE[page] + (row_idx - 1) * _ROW_STRIDE
    prefix = (
        f"topmostSubform[0].Page{page}[0]"
        f".Table_Line1_Part{page}[0].Row{row_idx}[0]"
    )
    return {
        f"f8949_box_{box_letter}_row_{row_idx}_{col}":
            f"{prefix}.f{page}_{base + col_idx:02d}[0]"
        for col_idx, col in enumerate(_COL_NAMES)
    }


def _box_rows(box_letter: str) -> list[dict[str, str]]:
    return [_row_mapping(box_letter, r) for r in range(1, _ROWS_PER_PAGE + 1)]


def _build_scalars_2025() -> dict[str, str]:
    scalars: dict[str, str] = {
        # Header — page 1 (f1_01 = name, f1_02 = SSN per T11a)
        "taxpayer_name": "topmostSubform[0].Page1[0].f1_01[0]",
        "taxpayer_ssn":  "topmostSubform[0].Page1[0].f1_02[0]",
    }

    # Checkboxes — one per in-scope box
    for box, idx in _BOX_CHECKBOX_IDX.items():
        page = _BOX_TO_PAGE[box]
        scalars[f"f8949_box_{box}_checkbox"] = (
            f"topmostSubform[0].Page{page}[0].c{page}_1[{idx}]"
        )

    # Totals — page-level scalars (f1_91–f1_95 for page 1, f2_91–f2_95 for
    # page 2). Boxes sharing a page share the same totals paths; the filler
    # writes the totals once per physical copy of that page.
    _page1_totals = {
        "total_proceeds":   "topmostSubform[0].Page1[0].f1_91[0]",
        "total_basis":      "topmostSubform[0].Page1[0].f1_92[0]",
        "total_adjustment": "topmostSubform[0].Page1[0].f1_94[0]",
        "total_gain":       "topmostSubform[0].Page1[0].f1_95[0]",
    }
    _page2_totals = {
        "total_proceeds":   "topmostSubform[0].Page2[0].f2_91[0]",
        "total_basis":      "topmostSubform[0].Page2[0].f2_92[0]",
        "total_adjustment": "topmostSubform[0].Page2[0].f2_94[0]",
        "total_gain":       "topmostSubform[0].Page2[0].f2_95[0]",
    }
    _box_totals_source = {"a": _page1_totals, "b": _page1_totals,
                          "d": _page2_totals, "e": _page2_totals}

    for box, source in _box_totals_source.items():
        scalars[f"f8949_box_{box}_total_proceeds"]   = source["total_proceeds"]
        scalars[f"f8949_box_{box}_total_basis"]      = source["total_basis"]
        scalars[f"f8949_box_{box}_total_adjustment"] = source["total_adjustment"]
        scalars[f"f8949_box_{box}_total_gain"]       = source["total_gain"]

    return scalars


class PdfF8949:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": _build_scalars_2025(),
            "repeaters": {
                "box_a_rows": _box_rows("a"),
                "box_b_rows": _box_rows("b"),
                "box_d_rows": _box_rows("d"),
                "box_e_rows": _box_rows("e"),
            },
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Form 8949 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
