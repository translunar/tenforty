"""The one door: each activity's depreciation, resolved from one source.

Every reader of an activity's depreciation (Schedule E line 18, Schedule C
line 13, the excess-business-loss guard, the routing estimates, the workbook
flattener, the CA divergence trigger) goes through `resolve`. There is no
second read path to the raw fields.

Modes, per activity:
  none              no depreciation
  stated            the activity's stated scalar, acknowledged as coming from
                    outside tenforty's MACRS model
  assets            the sum of per-asset MACRS table amounts
  assets-overridden asset mode with a value-pinned `depreciation_override`:
                    the override amount is USED, the engine's own figure is
                    still computed and reported beside it

Refusals are refusal-ledger entries (tenforty.attestations). `resolve` runs
the ledger over the one activity it was handed, so a caller that bypassed the
loader and the orchestrator still fails closed, with the ledger's own text.

One fact `resolve` cannot work out from an activity is supplied by every
caller: the RETURN's answer to the mid-quarter 40% test (`mid_quarter`,
from `mid_quarter_applies` over the whole scenario). It has no default.
"""

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

from tenforty.attestations import (
    depreciation_activities, enforce_scoped_refusals,
    has_unattested_bonus_history, stated_convention_problem,
)
from tenforty.forms.depreciation.macrs import (
    asset_convention, macrs_deduction, method_for, require_answer,
)
from tenforty.models import (
    PERSONAL_PROPERTY_CLASSES, SUPPORTED_RECOVERY_CLASSES, DepreciableAsset,
    RentalProperty, ScheduleCBusiness,
)
from tenforty.rounding import irs_round

MODE_NONE = "none"
MODE_STATED = "stated"
MODE_ASSETS = "assets"
MODE_ASSETS_OVERRIDDEN = "assets-overridden"


@dataclass(frozen=True)
class AssetDepreciation:
    """One asset's current-year row (what Form 4562 consumes)."""
    description: str
    recovery_class: str
    convention: str
    # 1-4 under the mid-quarter convention, else None.
    quarter: int | None
    method: str
    date_placed_in_service: date
    basis: float
    amount: int
    placed_this_year: bool
    # What the table alone gives; differs from `amount` only when the basis
    # ceiling bound.
    table_amount: int = 0
    basis_ceiling_bound: bool = False


@dataclass(frozen=True)
class ResolvedDepreciation:
    # What the forms use. Stated mode carries the scalar as stated (readers
    # round it where they print it); asset mode is whole dollars.
    amount: float
    mode: str
    # The engine's own computed figure; None outside asset mode.
    engine_amount: int | None
    per_asset: tuple[AssetDepreciation, ...]


def is_computable(asset: DepreciableAsset, tax_year: int) -> bool:
    """False for an asset another ledger entry already refuses outright (no
    table for its class, disposed, or a prior-year asset with no usable
    stated convention) -- the engine has no figure for it."""
    if (asset.recovery_class not in SUPPORTED_RECOVERY_CLASSES
            or asset.disposed is not None):
        return False
    if (asset.recovery_class in PERSONAL_PROPERTY_CLASSES
            and asset.date_placed_in_service.year < tax_year):
        return (asset.convention is not None
                and stated_convention_problem(asset) is None)
    return True


def _capped(table: int, basis: float, taken: int) -> int:
    """The BASIS CEILING: a year's deduction is the table amount, but never
    more than the basis left after what was taken before, and never below
    zero. Lifetime depreciation therefore never exceeds basis.

    It is asymmetric by ruling. Each year's table amount is rounded on its
    own, so a lifetime of them can land a dollar over basis (trimmed here,
    in the last year) or a dollar under (NOT topped up: the table amount
    stands and the residual is documented behaviour)."""
    return min(table, max(0, irs_round(basis) - taken))


def reconstruct_prior_depreciation(
        asset: DepreciableAsset, tax_year: int, *, mid_quarter: bool) -> int:
    """What the MACRS tables give for every year before ``tax_year``, under
    the asset's convention, each year held to the basis ceiling."""
    require_answer(mid_quarter)
    taken = 0
    for year in range(asset.date_placed_in_service.year, tax_year):
        taken += _capped(
            macrs_deduction(
                asset, year, return_year=tax_year, mid_quarter=mid_quarter),
            asset.basis, taken)
    return taken


def prior_depreciation_mismatch(
        asset: DepreciableAsset, tax_year: int, *,
        mid_quarter: bool) -> tuple[int, int] | None:
    """``(stated, reconstructed)`` when the asset's stated prior depreciation
    differs from the table reconstruction and is not acknowledged; else None."""
    require_answer(mid_quarter)
    if asset.prior_depreciation is None:
        return None
    if asset.acknowledges_prior_depreciation_as_stated:
        return None
    stated = irs_round(asset.prior_depreciation)
    reconstructed = reconstruct_prior_depreciation(
        asset, tax_year, mid_quarter=mid_quarter)
    return None if stated == reconstructed else (stated, reconstructed)


def asset_amount(asset: DepreciableAsset, tax_year: int, *,
                 mid_quarter: bool) -> tuple[int, int]:
    """``(amount, table amount)`` for one asset in ``tax_year``.

    The amount is the table amount held to the basis ceiling (`_capped`):
    min(table amount, basis - depreciation already taken), never below zero.

    "Already taken" is the table reconstruction of the earlier years. On the
    ACKNOWLEDGED-MISMATCH path (a stated prior that differs from that
    reconstruction, accepted via `acknowledges_prior_depreciation_as_stated`)
    it is the stated prior instead, so a history that ran ahead of the
    tables cannot depreciate the asset past its basis.

    Nothing tops UP: a history that ran behind the tables leaves basis
    unrecovered when the table runs out, and the remedy is a change of
    accounting method (Form 3115), which tenforty does not prepare."""
    table = macrs_deduction(
        asset, tax_year, return_year=tax_year, mid_quarter=mid_quarter)
    if (asset.acknowledges_prior_depreciation_as_stated
            and asset.prior_depreciation is not None):
        taken = irs_round(asset.prior_depreciation)
    else:
        taken = reconstruct_prior_depreciation(
            asset, tax_year, mid_quarter=mid_quarter)
    return _capped(table, asset.basis, taken), table


def engine_amount(activity, tax_year: int, *, mid_quarter: bool) -> int:
    """The engine's own figure for an asset-mode activity."""
    require_answer(mid_quarter)
    return sum(
        asset_amount(a, tax_year, mid_quarter=mid_quarter)[0]
        for a in activity.depreciable_assets)


def placed_this_year(activity, tax_year: int) -> list[DepreciableAsset]:
    return [a for a in activity.depreciable_assets
            if a.date_placed_in_service.year == tax_year]


def _one_activity_scenario(activity, tax_year: int, mid_quarter: bool):
    """A scenario-shaped view holding only ``activity``, for running the
    ledger on a direct call. Unindexed: refusal text names the activity
    without a position, since a lone activity has none to report.

    It CARRIES the return's 40% answer: that is a whole-return question,
    and re-deriving it from this one activity would answer a different one
    (see `mid_quarter_applies`)."""
    if isinstance(activity, RentalProperty):
        rentals, businesses = [activity], []
    elif isinstance(activity, ScheduleCBusiness):
        rentals, businesses = [], [activity]
    else:
        raise TypeError(
            f"resolve() takes a RentalProperty or ScheduleCBusiness; got "
            f"{type(activity).__name__}")
    return SimpleNamespace(
        rental_properties=rentals, schedule_c_businesses=businesses,
        config=SimpleNamespace(year=tax_year), unindexed_activities=True,
        mid_quarter=mid_quarter)


def resolve(activity, tax_year: int, *,
            mid_quarter: bool) -> ResolvedDepreciation:
    """Resolve one activity's depreciation for ``tax_year``.

    ``mid_quarter`` is the RETURN's 40% answer (`mid_quarter_applies` over
    the whole scenario), supplied by the caller: one activity cannot answer
    a taxpayer-wide test. It decides the convention of personal property
    placed in service this year and nothing else."""
    require_answer(mid_quarter)
    enforce_scoped_refusals(
        _one_activity_scenario(activity, tax_year, mid_quarter), "load",
        single_activity=True)

    assets = activity.depreciable_assets
    if not assets:
        if activity.depreciation:
            return ResolvedDepreciation(
                amount=activity.depreciation, mode=MODE_STATED,
                engine_amount=None, per_asset=())
        return ResolvedDepreciation(
            amount=0, mode=MODE_NONE, engine_amount=None, per_asset=())

    rows = []
    for a in assets:
        amount, table = asset_amount(a, tax_year, mid_quarter=mid_quarter)
        convention, quarter = asset_convention(
            a, return_year=tax_year, mid_quarter=mid_quarter)
        rows.append(AssetDepreciation(
            description=a.description,
            recovery_class=a.recovery_class,
            convention=convention,
            quarter=quarter,
            method=method_for(a.recovery_class),
            date_placed_in_service=a.date_placed_in_service,
            basis=a.basis,
            amount=amount,
            placed_this_year=a.date_placed_in_service.year == tax_year,
            table_amount=table,
            basis_ceiling_bound=amount != table,
        ))
    rows = tuple(rows)
    engine = sum(row.amount for row in rows)
    override = activity.depreciation_override
    if override is not None:
        return ResolvedDepreciation(
            amount=override.amount, mode=MODE_ASSETS_OVERRIDDEN,
            engine_amount=engine, per_asset=rows)
    return ResolvedDepreciation(
        amount=engine, mode=MODE_ASSETS, engine_amount=engine, per_asset=rows)


# --- The mid-quarter 40% test (taxpayer-wide) ------------------------------
#
# 26 U.S.C. 168(d)(3); Pub 946 "Which Convention Applies?". The rule text is
# transcribed in tests/test_mid_quarter_convention.py. The totals run over
# the whole return, and the statute's exclusions come out of BOTH of them.
#
# The test is run EXACTLY ONCE, over the property placed in service in the
# return year, and decides that property's convention. It is never run over
# an earlier year: this return's asset list is not that year's complete
# placements (anything since disposed of is gone from it), and a taxpayer-
# wide total taken over part of the taxpayer is a wrong total. A prior-year
# asset states the convention it took (macrs.asset_convention).

MID_QUARTER_THRESHOLD_PERCENT = 40
_LAST_THREE_MONTHS = (10, 11, 12)   # calendar tax year


def personal_property_placed_this_year(scenario) -> list:
    """``(label, asset)`` for every asset in the 40% test: personal property
    placed in service during the return year, across every activity.

    Real property is out of both totals (168(d)(3)(B)(i)). The remaining
    statutory exclusions cannot occur: a `disposed` asset and an asset in a
    class with no table both refuse at load, and are skipped here so this
    stays that other refusal's business."""
    year = scenario.config.year
    return [
        (label, asset)
        for _section, _index, label, activity in depreciation_activities(
            scenario)
        for asset in activity.depreciable_assets
        if asset.recovery_class in PERSONAL_PROPERTY_CLASSES
        and asset.disposed is None
        and asset.date_placed_in_service.year == year]


def mid_quarter_bases(scenario) -> tuple[float, float]:
    """``(last three months, entire year)`` aggregate bases for the 40%
    test, in dollars, FOR REPORTING. `basis` is used as stated: see the test
    module for why the publication's basis Caution is inert in this model.

    The test itself does not compare these floats: see
    `_mid_quarter_bases_in_cents`."""
    assets = [a for _label, a in personal_property_placed_this_year(scenario)]
    last_quarter = sum(
        a.basis for a in assets
        if a.date_placed_in_service.month in _LAST_THREE_MONTHS)
    return last_quarter, sum(a.basis for a in assets)


def _cents(amount: float) -> int:
    """A dollar amount as whole cents."""
    return round(amount * 100)


def _mid_quarter_bases_in_cents(scenario) -> tuple[int, int]:
    """``(last three months, entire year)`` aggregate bases in WHOLE CENTS:
    each asset's basis converted once, then summed as integers. The 40%
    test is decided on these. Binary floats cannot hold most cent amounts
    exactly, and "exactly 40%" is a comparison where the smallest error
    flips the answer (20,780.06 * 100 as a float is a hair over
    2,078,006)."""
    assets = [a for _label, a in personal_property_placed_this_year(scenario)]
    last_quarter = sum(
        _cents(a.basis) for a in assets
        if a.date_placed_in_service.month in _LAST_THREE_MONTHS)
    return last_quarter, sum(_cents(a.basis) for a in assets)


def mid_quarter_applies(scenario) -> bool:
    """The return's 40% answer: True when the last-three-months bases
    EXCEED 40% of the year's (strictly; no placements at all is False, and
    nothing is divided). Decided in integer cents, never on floats. Every
    reader of a depreciation figure passes this down to the engine.

    A one-activity view built by `resolve` carries the answer its caller
    supplied, and that answer is returned as-is: recomputing it from the
    lone activity would turn a taxpayer-wide test into a per-activity one."""
    if hasattr(scenario, "mid_quarter"):
        require_answer(scenario.mid_quarter)
        return scenario.mid_quarter
    last_quarter, year_total = _mid_quarter_bases_in_cents(scenario)
    return last_quarter * 100 > MID_QUARTER_THRESHOLD_PERCENT * year_total


def stated_mode_activity_labels(scenario) -> list[str]:
    return [label for _section, _index, label, activity
            in depreciation_activities(scenario)
            if activity.depreciation and not activity.depreciable_assets]


# --- Recon surface ---------------------------------------------------------

RECON_PREFIX = "depreciation_recon_"
_RECON_SECTION_SLUGS = {
    "rental_properties": "rental", "schedule_c_businesses": "sch_c"}
RECON_FIELDS = (
    "activity", "mode", "engine_amount", "used_amount", "note",
    "basis_ceiling_bound")


def recon_keys(scenario) -> dict:
    """Result keys reconciling the engine's figure with the figure used, one
    group per ASSET-MODE activity (none for stated-mode or no-depreciation
    activities). Keys: ``depreciation_recon_{rental|sch_c}_{index}_{field}``
    for each field in `RECON_FIELDS` (`note` only when there is one). An
    overridden activity shows both figures, differing; every other
    asset-mode activity shows them equal."""
    keys: dict = {}
    year = scenario.config.year
    for section, index, label, activity in depreciation_activities(scenario):
        resolved = resolve(
            activity, year, mid_quarter=mid_quarter_applies(scenario))
        if resolved.mode not in (MODE_ASSETS, MODE_ASSETS_OVERRIDDEN):
            continue
        prefix = f"{RECON_PREFIX}{_RECON_SECTION_SLUGS[section]}_{index}_"
        keys[prefix + "activity"] = label
        keys[prefix + "mode"] = resolved.mode
        keys[prefix + "engine_amount"] = resolved.engine_amount
        keys[prefix + "used_amount"] = irs_round(resolved.amount)
        # Present only when an override lifted the bonus / section 179
        # history refusal for this activity (the ledger lets such an asset
        # load only under a valid override).
        notes = []
        tainted = [a.description for a in activity.depreciable_assets
                   if has_unattested_bonus_history(a)]
        if tainted:
            names = ", ".join(repr(name) for name in tainted)
            notes.append(
                f"engine figure includes {names} with unmodeled bonus / "
                f"section 179 history: the engine column here is a "
                f"staleness pin, not a claim of correctness")
        # Present only when the basis ceiling bound (see `asset_amount`).
        # Rows are in asset order. Two notes, because the cause differs: a
        # stated prior that ran ahead of the tables, or the tables' own
        # per-year rounding.
        capped = [
            (row, asset.acknowledges_prior_depreciation_as_stated
             and asset.prior_depreciation is not None)
            for row, asset in zip(
                resolved.per_asset, activity.depreciable_assets)
            if row.basis_ceiling_bound]
        if capped:
            keys[prefix + "basis_ceiling_bound"] = True

        def detail(rows):
            return ", ".join(
                f"{row.description!r} limited to its remaining basis of "
                f"{row.amount:,} (table amount {row.table_amount:,})"
                for row in rows)

        stated = [row for row, acknowledged in capped if acknowledged]
        if stated:
            notes.append(
                f"{detail(stated)}: the stated prior depreciation leaves "
                f"less basis than the table amount. A stated prior BELOW "
                f"the tables is not topped up and leaves basis unrecovered "
                f"when the table ends; correcting either history is a "
                f"change of accounting method (Form 3115), which tenforty "
                f"does not prepare")
        rounded = [row for row, acknowledged in capped if not acknowledged]
        if rounded:
            notes.append(
                f"{detail(rounded)}: each year's table amount is rounded to "
                f"whole dollars on its own, and the years already taken "
                f"leave less basis than this year's table amount. Lifetime "
                f"depreciation never exceeds basis")
        if notes:
            keys[prefix + "note"] = "; ".join(notes)
    return keys


def recon_groups(results) -> list[dict]:
    """The recon key groups in ``results``, one dict of `RECON_FIELDS` per
    activity, in key order."""
    groups: dict[str, dict] = {}
    for key in sorted(k for k in results if k.startswith(RECON_PREFIX)):
        for field_name in RECON_FIELDS:
            if key.endswith("_" + field_name):
                stem = key[: -len(field_name) - 1]
                groups.setdefault(stem, {})[field_name] = results[key]
                break
    return list(groups.values())
