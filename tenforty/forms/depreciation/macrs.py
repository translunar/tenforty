"""MACRS depreciation — per-asset per-year deduction.

Class → computed convention → table lookup → percentage × basis → IRS
rounding. Year-stable; uses the tables in tables.py and, for the mid-quarter
convention, tenforty.params.macrs_mid_quarter.

The convention is COMPUTED, never stated:
  - real property (27.5-year, 39-year) → mid-month, TABLE_A_6 / TABLE_A_7a
  - personal property (3/5/7/10/15/20-year) → half-year, TABLE_A_1, unless
    the asset's PLACEMENT YEAR is a mid-quarter year → mid-quarter, the
    table for the quarter the asset was placed in service
Whether a placement year is a mid-quarter year is a taxpayer-wide question
answered over the whole return (resolver.mid_quarter_years). This module
cannot answer it from one asset, so every caller must supply the answer:
`mid_quarter_years` has no default.

Refusals (a disposed asset, a class with no table) are refusal-ledger entries
in tenforty.attestations. This module raises THROUGH those entries when
called directly, so a caller that bypassed the loader still fails closed and
the ledger stays the single owner of the refusal text.
"""

from datetime import date

from tenforty.attestations import raise_scoped_refusal
from tenforty.forms.depreciation.tables import TABLE_A_1, TABLE_A_6, TABLE_A_7a
from tenforty.models import (
    PERSONAL_PROPERTY_CLASSES, REAL_PROPERTY_CLASSES, DepreciableAsset,
)
from tenforty.params import macrs_mid_quarter
from tenforty.rounding import irs_round

MID_MONTH = "mid-month"
HALF_YEAR = "half-year"
MID_QUARTER = "mid-quarter"

_REAL_PROPERTY_TABLES = {
    "27.5-year": TABLE_A_6["27.5-year"],
    "39-year": TABLE_A_7a["39-year"],
}

# Recovery-class label → the class key of the mid-quarter tables.
_CLASS_YEARS = {
    "3-year": 3, "5-year": 5, "7-year": 7,
    "10-year": 10, "15-year": 15, "20-year": 20,
}


def placement_quarter(placed: date) -> int:
    """The quarter (1-4) of a calendar tax year a date falls in."""
    return (placed.month - 1) // 3 + 1


def convention_for(recovery_class: str, *, mid_quarter: bool,
                   label: str = "asset") -> str:
    """The averaging convention a recovery class takes. ``mid_quarter`` says
    whether the placement year is a mid-quarter year; real property ignores
    it."""
    if recovery_class in REAL_PROPERTY_CLASSES:
        return MID_MONTH
    if recovery_class in PERSONAL_PROPERTY_CLASSES:
        return MID_QUARTER if mid_quarter else HALF_YEAR
    raise_scoped_refusal(
        "unknown_recovery_class",
        [f"{label} has recovery_class {recovery_class!r}"])


def asset_convention(asset: DepreciableAsset, *,
                     mid_quarter_years: frozenset[int],
                     label: str = "asset") -> str:
    """The convention ``asset`` takes, given the placement years in which
    the mid-quarter convention applies to the return."""
    return convention_for(
        asset.recovery_class,
        mid_quarter=asset.date_placed_in_service.year in mid_quarter_years,
        label=label)


def macrs_deduction(asset: DepreciableAsset, tax_year: int, *,
                    mid_quarter_years: frozenset[int]) -> int:
    """The MACRS deduction (IRS-rounded whole dollars) for ``asset`` in
    ``tax_year``.

    Zero when the asset was not yet placed in service, or the recovery
    period has elapsed (the class IS mapped and the published schedule has
    run out — a legitimate 0, the asset is fully depreciated).
    """
    label = f"asset {asset.description!r}"
    if asset.disposed is not None:
        raise_scoped_refusal("asset_disposed", [label])
    convention = asset_convention(
        asset, mid_quarter_years=mid_quarter_years, label=label)

    recovery_year = tax_year - asset.date_placed_in_service.year + 1
    if recovery_year < 1:
        return 0

    if convention == MID_MONTH:
        month = asset.date_placed_in_service.month
        pct = _REAL_PROPERTY_TABLES[asset.recovery_class].get(
            recovery_year, {}).get(month, 0.0)
    elif convention == MID_QUARTER:
        quarter = placement_quarter(asset.date_placed_in_service)
        # Read through the module at call time: the table is its one owner.
        table = macrs_mid_quarter.TABLES_BY_QUARTER[quarter]
        pct = table[_CLASS_YEARS[asset.recovery_class]].get(recovery_year, 0.0)
    else:
        pct = TABLE_A_1[asset.recovery_class].get(recovery_year, 0.0)
    return irs_round(asset.basis * pct)
