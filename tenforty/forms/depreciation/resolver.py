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
"""

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

from tenforty.attestations import (
    depreciation_activities, enforce_scoped_refusals,
    has_unattested_bonus_history,
)
from tenforty.forms.depreciation.macrs import convention_for, macrs_deduction
from tenforty.models import (
    SUPPORTED_RECOVERY_CLASSES, DepreciableAsset, RentalProperty,
    ScheduleCBusiness,
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
    date_placed_in_service: date
    basis: float
    amount: int
    placed_this_year: bool


@dataclass(frozen=True)
class ResolvedDepreciation:
    # What the forms use. Stated mode carries the scalar as stated (readers
    # round it where they print it); asset mode is whole dollars.
    amount: float
    mode: str
    # The engine's own computed figure; None outside asset mode.
    engine_amount: int | None
    per_asset: tuple[AssetDepreciation, ...]


def is_computable(asset: DepreciableAsset) -> bool:
    """False for an asset another ledger entry already refuses outright (no
    table for its class, or disposed) -- the engine has no figure for it."""
    return (asset.recovery_class in SUPPORTED_RECOVERY_CLASSES
            and asset.disposed is None)


def reconstruct_prior_depreciation(
        asset: DepreciableAsset, tax_year: int) -> int:
    """What the MACRS tables give for every year before ``tax_year``."""
    return sum(
        macrs_deduction(asset, year)
        for year in range(asset.date_placed_in_service.year, tax_year))


def prior_depreciation_mismatch(
        asset: DepreciableAsset, tax_year: int) -> tuple[int, int] | None:
    """``(stated, reconstructed)`` when the asset's stated prior depreciation
    differs from the table reconstruction and is not acknowledged; else None."""
    if asset.prior_depreciation is None:
        return None
    if asset.acknowledges_prior_depreciation_as_stated:
        return None
    stated = irs_round(asset.prior_depreciation)
    reconstructed = reconstruct_prior_depreciation(asset, tax_year)
    return None if stated == reconstructed else (stated, reconstructed)


def engine_amount(activity, tax_year: int) -> int:
    """The engine's own figure for an asset-mode activity."""
    return sum(macrs_deduction(a, tax_year) for a in activity.depreciable_assets)


def placed_this_year(activity, tax_year: int) -> list[DepreciableAsset]:
    return [a for a in activity.depreciable_assets
            if a.date_placed_in_service.year == tax_year]


def _one_activity_scenario(activity, tax_year: int):
    """A scenario-shaped view holding only ``activity``, for running the
    ledger on a direct call. Unindexed: refusal text names the activity
    without a position, since a lone activity has none to report."""
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
        config=SimpleNamespace(year=tax_year), unindexed_activities=True)


def resolve(activity, tax_year: int) -> ResolvedDepreciation:
    """Resolve one activity's depreciation for ``tax_year``."""
    enforce_scoped_refusals(_one_activity_scenario(activity, tax_year), "load")

    assets = activity.depreciable_assets
    if not assets:
        if activity.depreciation:
            return ResolvedDepreciation(
                amount=activity.depreciation, mode=MODE_STATED,
                engine_amount=None, per_asset=())
        return ResolvedDepreciation(
            amount=0, mode=MODE_NONE, engine_amount=None, per_asset=())

    rows = tuple(
        AssetDepreciation(
            description=a.description,
            recovery_class=a.recovery_class,
            convention=convention_for(a.recovery_class),
            date_placed_in_service=a.date_placed_in_service,
            basis=a.basis,
            amount=macrs_deduction(a, tax_year),
            placed_this_year=a.date_placed_in_service.year == tax_year,
        ) for a in assets)
    engine = sum(row.amount for row in rows)
    override = activity.depreciation_override
    if override is not None:
        return ResolvedDepreciation(
            amount=override.amount, mode=MODE_ASSETS_OVERRIDDEN,
            engine_amount=engine, per_asset=rows)
    return ResolvedDepreciation(
        amount=engine, mode=MODE_ASSETS, engine_amount=engine, per_asset=rows)


# --- Recon surface ---------------------------------------------------------

RECON_PREFIX = "depreciation_recon_"
_RECON_SECTION_SLUGS = {
    "rental_properties": "rental", "schedule_c_businesses": "sch_c"}
RECON_FIELDS = ("activity", "mode", "engine_amount", "used_amount", "note")


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
        resolved = resolve(activity, year)
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
        tainted = [a.description for a in activity.depreciable_assets
                   if has_unattested_bonus_history(a)]
        if tainted:
            names = ", ".join(repr(name) for name in tainted)
            keys[prefix + "note"] = (
                f"engine figure includes {names} with unmodeled bonus / "
                f"section 179 history: the engine column here is a "
                f"staleness pin, not a claim of correctness")
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
