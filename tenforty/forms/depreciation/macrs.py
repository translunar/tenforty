"""MACRS depreciation — per-asset per-year deduction.

Class → computed convention → table lookup → percentage × basis → IRS
rounding. Year-stable; uses the tables in tables.py.

The convention is COMPUTED from the recovery class, never stated:
  - real property (27.5-year, 39-year) → mid-month, TABLE_A_6 / TABLE_A_7a
  - personal property (3/5/7/10/15/20-year) → half-year, TABLE_A_1
The mid-quarter convention has no tables here; whether it applies is a
taxpayer-wide question answered over the whole scenario, not per asset.

Refusals (a disposed asset, a class with no table) are refusal-ledger entries
in tenforty.attestations. This module raises THROUGH those entries when
called directly, so a caller that bypassed the loader still fails closed and
the ledger stays the single owner of the refusal text.
"""

from tenforty.attestations import raise_scoped_refusal
from tenforty.forms.depreciation.tables import TABLE_A_1, TABLE_A_6, TABLE_A_7a
from tenforty.models import (
    PERSONAL_PROPERTY_CLASSES, REAL_PROPERTY_CLASSES, DepreciableAsset,
)
from tenforty.rounding import irs_round

MID_MONTH = "mid-month"
HALF_YEAR = "half-year"

_REAL_PROPERTY_TABLES = {
    "27.5-year": TABLE_A_6["27.5-year"],
    "39-year": TABLE_A_7a["39-year"],
}


def convention_for(recovery_class: str, *, label: str = "asset") -> str:
    """The averaging convention a recovery class takes."""
    if recovery_class in REAL_PROPERTY_CLASSES:
        return MID_MONTH
    if recovery_class in PERSONAL_PROPERTY_CLASSES:
        return HALF_YEAR
    raise_scoped_refusal(
        "unknown_recovery_class",
        [f"{label} has recovery_class {recovery_class!r}"])


def macrs_deduction(asset: DepreciableAsset, tax_year: int) -> int:
    """The MACRS deduction (IRS-rounded whole dollars) for ``asset`` in
    ``tax_year``.

    Zero when the asset was not yet placed in service, or the recovery
    period has elapsed (the class IS mapped and the published schedule has
    run out — a legitimate 0, the asset is fully depreciated).
    """
    label = f"asset {asset.description!r}"
    if asset.disposed is not None:
        raise_scoped_refusal("asset_disposed", [label])
    convention = convention_for(asset.recovery_class, label=label)

    recovery_year = tax_year - asset.date_placed_in_service.year + 1
    if recovery_year < 1:
        return 0

    if convention == MID_MONTH:
        month = asset.date_placed_in_service.month
        pct = _REAL_PROPERTY_TABLES[asset.recovery_class].get(
            recovery_year, {}).get(month, 0.0)
    else:
        pct = TABLE_A_1[asset.recovery_class].get(recovery_year, 0.0)
    return irs_round(asset.basis * pct)
