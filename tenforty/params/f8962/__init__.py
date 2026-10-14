"""Per-year Form 8962 (Premium Tax Credit) parameters. The only thing that
differs by year.

Year-agnostic PTC logic reads everything from F8962Params; there are no
`if year ==` branches in the math. Adding a year = adding one yNNNN module.

Per-status fields (PER_STATUS_F8962_FIELDS) are dicts keyed by
FilingStatus.value strings, read only through ``params.for_status(status)``
(fail-closed UnsupportedStatusError on a missing column). The FPL table is
keyed by tax-family size and read only through ``fpl_for_family_size``
(fail-closed FamilySizeNotSupportedError on a size the params cannot price).
"""
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class F8962Params:
    year: int
    # Federal poverty line by tax-family size, 48 contiguous states + DC, as
    # published in that year's Form 8962 instructions Table 1-1/1-2. Form
    # 8962 for tax year N uses the FPL guideline published in year N-1.
    # Keys are family sizes; a size absent here (and not covered by
    # fpl_48_additional_person) is refused by fpl_for_family_size, never
    # approximated.
    fpl_48_by_family_size: dict[int, int]
    # Integer FPL percentage -> applicable figure, covering the full
    # published table domain for that year (Table 2).
    applicable_figures: dict[int, float]
    # The table's published domain edges: below floor uses the floor
    # figure, above ceiling uses the ceiling figure, per that year's
    # instructions.
    applicable_figure_floor_pct: int
    applicable_figure_ceiling_pct: int
    # Line 28 repayment limitation, keyed by FilingStatus.value: each column
    # is FPL%-exclusive-upper-bound -> cap dollars, ascending. At >= 400% no
    # cap applies (not represented as a band here). Every status the table
    # covers is stored explicitly, even where the instructions group them; a
    # missing column raises UnsupportedStatusError via for_status.
    repayment_caps: dict[str, tuple[tuple[int, int], ...]]
    # True ONLY in y2021 (ARPA rule: household income treated as no more
    # than 133% of the FPL for the applicable figure, when unemployment
    # compensation was received during the year).
    unemployment_rule: bool
    # Selects which line-5 400%-FPL-boundary rule applies (Worksheet 2's
    # last step). Per-year worksheet phrasing differs at exactly 400%:
    #   2021: "Is the result 400 or more? Yes. Enter 401..." — INCLUSIVE
    #     (floored FPL% == 400 -> enter 401).
    #   2022-2025: "...more than 400% of the federal poverty line. Enter
    #     401..." — STRICT (only magi strictly > 4 * line 4 FPL -> enter
    #     401; magi == 4 * line 4 FPL leaves line 5 at 400).
    line5_400_boundary_inclusive: bool
    # The instructions' "for each additional person, add" amount for family
    # sizes beyond the largest one in fpl_48_by_family_size. None means not
    # yet transcribed: fpl_for_family_size then refuses every size outside
    # the table rather than extrapolate.
    fpl_48_additional_person: int | None = None

    def for_status(self, status: "FilingStatus | str") -> "StatusView":
        """Projection of these params onto one filing status. Per-status
        fields (PER_STATUS_F8962_FIELDS) read that status's column, raising
        UnsupportedStatusError when it is missing; other fields pass
        through."""
        from tenforty.params.status_view import StatusView
        return StatusView(self, status, PER_STATUS_F8962_FIELDS)


# Every F8962Params field whose value is a dict keyed by FilingStatus value
# strings (see PER_STATUS_FEDERAL_FIELDS; same completeness gate, same
# registry test).
PER_STATUS_F8962_FIELDS: tuple[str, ...] = (
    "repayment_caps",
)


class FamilySizeNotSupportedError(NotImplementedError):
    """The params cannot price the FPL for this tax-family size.

    Subclasses NotImplementedError so existing fail-closed refusal handling
    treats it as an unsupported-scope refusal."""

    def __init__(self, family_size: int, year: int) -> None:
        self.family_size = family_size
        self.year = year
        super().__init__(
            f"Form 8962 line 4: no federal poverty line for tax-family size "
            f"{family_size} in tax year {year} (F8962Params."
            f"fpl_48_by_family_size has no such size and "
            f"fpl_48_additional_person does not cover it); refusing rather "
            f"than compute a premium tax credit from the wrong poverty line")


def fpl_for_family_size(params: F8962Params, family_size: int) -> int:
    """Form 8962 line 4: the FPL for ``family_size``.

    A size in the published table is read directly. A size beyond the
    table's largest size is that entry plus fpl_48_additional_person per
    extra person, only when that amount is present. Anything else raises
    FamilySizeNotSupportedError."""
    if isinstance(family_size, bool) or not isinstance(family_size, int):
        raise TypeError(f"family_size must be an int, got {family_size!r}")
    if family_size < 1:
        raise ValueError(f"family_size must be >= 1, got {family_size}")
    table = params.fpl_48_by_family_size
    if family_size in table:
        return table[family_size]
    largest = max(table)
    if params.fpl_48_additional_person is not None and family_size > largest:
        return (table[largest]
                + (family_size - largest) * params.fpl_48_additional_person)
    raise FamilySizeNotSupportedError(family_size, params.year)


def load(year: int) -> F8962Params:
    if year not in year_manifest.amendable_federal_years():
        raise ValueError(
            f"No Form 8962 parameters for year {year} "
            f"(supported years: "
            f"{year_manifest.describe(year_manifest.amendable_federal_years())})"
        )
    module = importlib.import_module(f"tenforty.params.f8962.y{year}")
    return module.PARAMS
