"""MACRS depreciation — per-asset per-year deduction.

Class → convention → table lookup → percentage × basis → IRS rounding.
Year-stable; uses the tables in tables.py and, for the mid-quarter
convention, tenforty.params.macrs_mid_quarter.

Where an asset's convention comes from:
  - real property (27.5-year, 39-year) → mid-month, by statute
    (TABLE_A_6 / TABLE_A_7a);
  - personal property placed in service IN THE RETURN YEAR → computed:
    half-year (TABLE_A_1), or mid-quarter when the 40% test trips for the
    return. Whether it trips is a taxpayer-wide question answered once over
    the whole return (resolver.mid_quarter_applies); this module cannot
    answer it from one asset, so every caller supplies the answer --
    `mid_quarter` has no default. The quarter is the one the asset was
    placed in service in;
  - personal property placed in service in an EARLIER year → stated on the
    asset (`convention`, and `quarter` when mid-quarter). That year's 40%
    test ran over that year's placements, which this return's asset list
    does not hold, so it is never re-run here.

Refusals (a disposed asset, a class with no table, a prior-year asset with
no usable stated convention) are refusal-ledger entries in
tenforty.attestations. This module raises THROUGH those entries when called
directly, so a caller that bypassed the loader still fails closed and the
ledger stays the single owner of the refusal text.
"""

from datetime import date

from tenforty.attestations import (
    raise_scoped_refusal, stated_convention_problem,
)
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

# Depreciation method by class (Publication 946, Chart 1): the general
# depreciation system uses 200% declining balance for 3-, 5-, 7- and 10-year
# property, 150% declining balance for 15- and 20-year property, and
# straight line for residential rental and nonresidential real property.
# Spelled as the Form 4562 instructions spell them for column (f): "200 DB",
# "150 DB", "S/L".
_METHOD_BY_CLASS = {
    "3-year": "200 DB", "5-year": "200 DB", "7-year": "200 DB",
    "10-year": "200 DB", "15-year": "150 DB", "20-year": "150 DB",
    "27.5-year": "S/L", "39-year": "S/L",
}


def method_for(recovery_class: str, *, label: str = "asset") -> str:
    """The depreciation method label a recovery class takes."""
    method = _METHOD_BY_CLASS.get(recovery_class)
    if method is None:
        raise_scoped_refusal(
            "unknown_recovery_class",
            [f"{label} has recovery_class {recovery_class!r}"])
    return method


def placement_quarter(placed: date) -> int:
    """The quarter (1-4) of a calendar tax year a date falls in."""
    return (placed.month - 1) // 3 + 1


def convention_for(recovery_class: str, *, mid_quarter: bool,
                   label: str = "asset") -> str:
    """The averaging convention a recovery class takes in a placement year
    whose 40% answer is ``mid_quarter``; real property ignores it."""
    if recovery_class in REAL_PROPERTY_CLASSES:
        return MID_MONTH
    if recovery_class in PERSONAL_PROPERTY_CLASSES:
        return MID_QUARTER if mid_quarter else HALF_YEAR
    raise_scoped_refusal(
        "unknown_recovery_class",
        [f"{label} has recovery_class {recovery_class!r}"])


def asset_convention(asset: DepreciableAsset, *, return_year: int,
                     mid_quarter: bool,
                     label: str = "asset") -> tuple[str, int | None]:
    """``(convention, quarter)`` for ``asset`` on a return for
    ``return_year`` whose own 40% answer is ``mid_quarter``. The quarter is
    None unless the convention is mid-quarter."""
    if asset.recovery_class not in PERSONAL_PROPERTY_CLASSES:
        return convention_for(
            asset.recovery_class, mid_quarter=False, label=label), None
    if asset.date_placed_in_service.year >= return_year:
        # Placed this year: computed. A stated value here is refused at load
        # (`stated_convention`) and is not consulted.
        if mid_quarter:
            return MID_QUARTER, placement_quarter(asset.date_placed_in_service)
        return HALF_YEAR, None
    # Placed in an earlier year: stated, never re-derived.
    if asset.convention is None:
        raise_scoped_refusal("missing_prior_year_convention", [label])
    problem = stated_convention_problem(asset)
    if problem is not None:
        raise_scoped_refusal("invalid_stated_convention", [f"{label} {problem}"])
    if asset.convention == MID_QUARTER:
        return MID_QUARTER, asset.quarter
    return HALF_YEAR, None


def macrs_deduction(asset: DepreciableAsset, tax_year: int, *,
                    return_year: int, mid_quarter: bool) -> int:
    """The MACRS TABLE amount (IRS-rounded whole dollars) for ``asset`` in
    ``tax_year``, on a return for ``return_year`` whose own 40% answer is
    ``mid_quarter``. (``tax_year`` is earlier than ``return_year`` when a
    prior year is being reconstructed.)

    Zero when the asset was not yet placed in service, or the recovery
    period has elapsed (the class IS mapped and the published schedule has
    run out — a legitimate 0, the asset is fully depreciated).

    This is the table alone: the limit that keeps lifetime depreciation
    within basis is applied by the resolver, which knows what came before.
    """
    label = f"asset {asset.description!r}"
    if asset.disposed is not None:
        raise_scoped_refusal("asset_disposed", [label])
    convention, quarter = asset_convention(
        asset, return_year=return_year, mid_quarter=mid_quarter, label=label)

    recovery_year = tax_year - asset.date_placed_in_service.year + 1
    if recovery_year < 1:
        return 0

    if convention == MID_MONTH:
        month = asset.date_placed_in_service.month
        pct = _REAL_PROPERTY_TABLES[asset.recovery_class].get(
            recovery_year, {}).get(month, 0.0)
    elif convention == MID_QUARTER:
        # Read through the module at call time: the table is its one owner.
        table = macrs_mid_quarter.TABLES_BY_QUARTER[quarter]
        pct = table[_CLASS_YEARS[asset.recovery_class]].get(recovery_year, 0.0)
    else:
        pct = TABLE_A_1[asset.recovery_class].get(recovery_year, 0.0)
    return irs_round(asset.basis * pct)
