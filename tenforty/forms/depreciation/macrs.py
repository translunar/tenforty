"""MACRS depreciation — per-asset per-year deduction.

Dispatches on convention → table lookup → percentage × basis → IRS
rounding. Year-stable; uses the hand-keyed tables in tables.py
(cell-verified against table_generator.py under @pytest.mark.oracle).

V1 scope:
  - half-year convention  → TABLE_A_1 (3/5/7/10/15/20-year)
  - mid-month convention  → TABLE_A_6 (27.5-year) or TABLE_A_7a (39-year)
  - mid-quarter           → NotImplementedError (add when first Q4-heavy
                            scenario appears)
  - dispositions          → NotImplementedError (mid-year disposition
                            proration scoped out of v1)
"""

from tenforty.forms.depreciation.tables import TABLE_A_1, TABLE_A_6, TABLE_A_7a
from tenforty.models import DepreciableAsset
from tenforty.rounding import irs_round


def macrs_deduction(asset: DepreciableAsset, tax_year: int) -> int:
    """Return the MACRS deduction (IRS-rounded whole dollars) for ``asset``
    in ``tax_year``.

    Zero when the asset was not yet placed in service, or the recovery
    period has elapsed. NotImplementedError for v1 scope-outs
    (dispositions, mid-quarter).
    """
    if asset.disposed is not None:
        raise NotImplementedError(
            "disposition proration not supported in v1 "
            f"(asset {asset.description!r} disposed {asset.disposed.isoformat()})"
        )

    recovery_year = tax_year - asset.date_placed_in_service.year + 1
    if recovery_year < 1:
        return 0

    pct = _lookup_percentage(asset, recovery_year)
    return irs_round(asset.basis * pct)


def _lookup_percentage(asset: DepreciableAsset, recovery_year: int) -> float:
    """Return the MACRS percentage for this asset in ``recovery_year``.

    Raises NotImplementedError when the class/convention combination
    has no table in v1 (Law 2: never silently zero a deduction for an
    asset the module doesn't know how to depreciate). Returns 0.0 when
    the class IS mapped but ``recovery_year`` is past the end of the
    published schedule — a legitimate 0 (the asset is fully depreciated).
    """
    conv = asset.convention
    cls = asset.recovery_class
    if conv == "half-year":
        rows = TABLE_A_1.get(cls)
        if rows is None:
            raise NotImplementedError(
                f"MACRS table missing for class={cls!r} convention={conv!r}. "
                "v1 supports 3/5/7/10/15/20-year classes under half-year. "
                "Add the table to forms.depreciation.tables (and the "
                "generator) before depreciating this asset."
            )
        return rows.get(recovery_year, 0.0)
    if conv == "mid-month":
        month = asset.date_placed_in_service.month
        if cls == "27.5-year":
            return TABLE_A_6["27.5-year"].get(recovery_year, {}).get(month, 0.0)
        if cls == "39-year":
            return TABLE_A_7a["39-year"].get(recovery_year, {}).get(month, 0.0)
        raise NotImplementedError(
            f"MACRS table missing for class={cls!r} convention={conv!r}. "
            "Mid-month convention is only valid for real property "
            "(27.5-year residential rental, 39-year nonresidential). "
            "Refusing to silently zero the deduction."
        )
    if conv == "mid-quarter":
        raise NotImplementedError(
            "mid-quarter convention not supported in v1 "
            "(add TABLE_A_4/A_5 to forms.depreciation.tables + generator)"
        )
    raise ValueError(f"Unknown MACRS convention: {conv!r}")
