"""PDF field mapping for IRS Form 8949 (Sales and Other Dispositions of
Capital Assets).

Scope: boxes A, B, D, E — the four boxes addressable by the current
Form1099B model. Boxes C/F (no-1099-B scenarios) and the TY2025-new
digital-asset boxes G/H/I/J/K/L are intentionally excluded.

Architecture: The PDF uses one shared repeater table per page. The active
box is selected by checking exactly one checkbox per page. Multiple boxes
require multiple physical copies of the same page. Boxes A and B are both on
page 1; boxes D and E are both on page 2 — so box_a_rows and box_b_rows share
the same PDF field paths (likewise D and E share page-2 paths). The filler
emits a separate copy of the page for each box.

Column order (a..h → base+0..base+7), row-1 base (+3) and row stride (+8)
are identical across years; only the Acrobat template's cosmetics differ:

  TY2025 (transcribed from the probe in issue #22 T11a, re-verified against
    the blank template): container ``Table_Line1_Part{page}``, 11 rows,
    zero-padded 2-digit field numbers (``f1_03``), header ``f1_01/f1_02``,
    totals at ``f{page}_91``.
  TY2024 (probe-verified against pdfs/federal/2024/f8949.pdf, both pages):
    single ``Table_Line1`` container per page, 14 rows, un-padded field
    numbers (``f1_3``), header ``f1_1/f1_2``, totals at ``f{page}_115``.

Per-year cosmetics live in the ``_Geometry`` records below; everything else
is shared. The fields-on-template gate re-checks every emitted path against
the real blank template on each run.
"""

import enum
from dataclasses import dataclass

from tenforty.mappings.registry import PdfFormMapping


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

# Base field number for row 1, col 0 on each page. Both pages start at 3
# (the header name/SSN scalars sit above the table); confirmed on both years.
_PAGE_ROW1_BASE: dict[int, int] = {1: 3, 2: 3}

_ROW_STRIDE: int = 8  # uniform across columns and rows on both years


class BoxLetter(str, enum.Enum):
    A = "a"
    B = "b"
    D = "d"
    E = "e"


@dataclass(frozen=True)
class _BoxSpec:
    page: int
    checkbox_idx: int


_BOX_SPECS: dict[BoxLetter, _BoxSpec] = {
    BoxLetter.A: _BoxSpec(page=1, checkbox_idx=0),
    BoxLetter.B: _BoxSpec(page=1, checkbox_idx=1),
    BoxLetter.D: _BoxSpec(page=2, checkbox_idx=0),
    BoxLetter.E: _BoxSpec(page=2, checkbox_idx=1),
}


@dataclass(frozen=True)
class _Geometry:
    """Per-year Acrobat-template cosmetics for one Form 8949 tax year.

    container: the repeater table's node under ``Page{page}[0]``; ``{page}``
        is substituted per page (TY2024's has no page suffix, so the
        substitution is a no-op there).
    rows_per_page: number of data-row slots the template exposes.
    pad: zero-pad width for the numeric part of ``f{page}_N`` field names
        (2 → ``f1_03``; 1 → ``f1_3``).
    totals_base: first of the five page-total field numbers; the totals row
        is proceeds=base, basis=base+1, (base+2 is the unused code column),
        adjustment=base+3, gain=base+4.
    """
    container: str
    rows_per_page: int
    pad: int
    totals_base: int


_GEOM: dict[int, _Geometry] = {
    2025: _Geometry(container="Table_Line1_Part{page}[0]", rows_per_page=11,
                    pad=2, totals_base=91),
    2024: _Geometry(container="Table_Line1[0]", rows_per_page=14,
                    pad=1, totals_base=115),
}


def _fnum(page: int, n: int, geom: _Geometry) -> str:
    """The ``f{page}_{N}`` field-name stem for a given page/number/year."""
    return f"f{page}_{n:0{geom.pad}d}"


def _row_mapping(box_letter: BoxLetter, row_idx: int,
                 geom: _Geometry) -> dict[str, str]:
    """Build the eight PDF field paths for one data row.

    Boxes A/B share the page-1 table; D/E share the page-2 table. The
    same paths appear in both box_a_rows and box_b_rows (the filler
    emits separate physical copies, one per box, with the appropriate
    checkbox set).
    """
    page = _BOX_SPECS[box_letter].page
    base = _PAGE_ROW1_BASE[page] + (row_idx - 1) * _ROW_STRIDE
    prefix = (
        f"topmostSubform[0].Page{page}[0]"
        f".{geom.container.format(page=page)}.Row{row_idx}[0]"
    )
    return {
        f"f8949_box_{box_letter.value}_row_{row_idx}_{col}":
            f"{prefix}.{_fnum(page, base + col_idx, geom)}[0]"
        for col_idx, col in enumerate(_COL_NAMES)
    }


def _box_rows(box_letter: BoxLetter, geom: _Geometry) -> list[dict[str, str]]:
    return [_row_mapping(box_letter, r, geom)
            for r in range(1, geom.rows_per_page + 1)]


def _build_scalars(geom: _Geometry) -> dict[str, str]:
    scalars: dict[str, str] = {
        # Header — page 1 (name, SSN sit above the page-1 table)
        "taxpayer_name": f"topmostSubform[0].Page1[0].{_fnum(1, 1, geom)}[0]",
        "taxpayer_ssn":  f"topmostSubform[0].Page1[0].{_fnum(1, 2, geom)}[0]",
    }

    # Checkboxes — one per in-scope box
    for letter, spec in _BOX_SPECS.items():
        scalars[f"f8949_box_{letter.value}_checkbox"] = (
            f"topmostSubform[0].Page{spec.page}[0]"
            f".c{spec.page}_1[{spec.checkbox_idx}]"
        )

    # Totals — page-level scalars. Boxes sharing a page share the same totals
    # paths; the filler writes the totals once per physical copy of that page.
    for letter, spec in _BOX_SPECS.items():
        p = spec.page
        base = geom.totals_base
        prefix = f"topmostSubform[0].Page{p}[0]"
        scalars[f"f8949_box_{letter.value}_total_proceeds"] = (
            f"{prefix}.{_fnum(p, base, geom)}[0]")
        scalars[f"f8949_box_{letter.value}_total_basis"] = (
            f"{prefix}.{_fnum(p, base + 1, geom)}[0]")
        scalars[f"f8949_box_{letter.value}_total_adjustment"] = (
            f"{prefix}.{_fnum(p, base + 3, geom)}[0]")
        scalars[f"f8949_box_{letter.value}_total_gain"] = (
            f"{prefix}.{_fnum(p, base + 4, geom)}[0]")

    return scalars


def _build_mapping(geom: _Geometry) -> dict:
    return {
        "scalars": _build_scalars(geom),
        "repeaters": {
            f"box_{letter.value}_rows": _box_rows(letter, geom)
            for letter in BoxLetter
        },
    }


class PdfF8949(PdfFormMapping[dict]):
    _FORM_NAME = "Form 8949"

    _MAPPINGS: dict[int, dict] = {
        year: _build_mapping(geom) for year, geom in _GEOM.items()
    }
