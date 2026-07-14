"""Per-year Form 8962 (Premium Tax Credit) parameters. The only thing that
differs by year.

Year-agnostic PTC logic reads everything from F8962Params; there are no
`if year ==` branches in the math. Adding a year = adding one yNNNN module.
"""
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class F8962Params:
    year: int
    # Federal poverty line, household size 1, 48 contiguous states + DC, as
    # published in that year's Form 8962 instructions Table 1-1/1-2. Form
    # 8962 for tax year N uses the FPL guideline published in year N-1.
    fpl_single_48: int
    # Integer FPL percentage -> applicable figure, covering the full
    # published table domain for that year (Table 2).
    applicable_figures: dict[int, float]
    # The table's published domain edges: below floor uses the floor
    # figure, above ceiling uses the ceiling figure, per that year's
    # instructions.
    applicable_figure_floor_pct: int
    applicable_figure_ceiling_pct: int
    # FPL%-exclusive-upper-bound -> cap dollars, ascending, single filing
    # status. At >= 400% no cap applies (not represented as a band here).
    repayment_caps_single: tuple[tuple[int, int], ...]
    # True ONLY in y2021 (ARPA rule: household income treated as no more
    # than 133% of the FPL for the applicable figure, when unemployment
    # compensation was received during the year).
    unemployment_rule: bool


def load(year: int) -> F8962Params:
    if year not in year_manifest.amendable_federal_years():
        raise ValueError(
            f"No Form 8962 parameters for year {year} "
            f"(supported years: "
            f"{year_manifest.describe(year_manifest.amendable_federal_years())})"
        )
    module = importlib.import_module(f"tenforty.params.f8962.y{year}")
    return module.PARAMS
