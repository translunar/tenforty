# tenforty/params/california/__init__.py
"""Per-year California tax parameters. The only thing that differs by year.

Year-agnostic Form 540 logic reads everything from CaliforniaParams; there
are no `if year ==` branches in the math. Adding a year = adding one yNNNN
module and declaring the year in tenforty/years.py.

All status-keyed dicts use FilingStatus.value strings, matching the
FederalParams convention.
"""
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class CaliforniaParams:
    year: int
    standard_deduction: dict[str, int]
    exemption_credit: dict[str, int]
    dependent_exemption_amount: int
    # Form 540 line 32 gate: federal AGI above this triggers the
    # exemption-credit phaseout; v1 raises NotImplementedError there.
    # This same threshold ALSO gates the Schedule CA Part II itemized-deduction
    # AGI limitation (Sch CA line 29): the two are printed as the same figure
    # on the 2024–2025 CA tax booklet (verified coincident via the params
    # attestation), so the existing f540 NotImplementedError scopes out the
    # line-29 reduction too. If FTB ever decouples them, this field must split
    # into separate exemption-phaseout and itemized-limitation thresholds.
    agi_phaseout_threshold: int
    # (threshold_inclusive, marginal_rate_at_or_above_threshold) entries
    # walked by forms.f540._walk_rate_schedule.
    rate_schedule: dict[str, tuple[tuple[int, float], ...]]
    renter_credit_agi_threshold: dict[str, int]
    renter_credit_amount: dict[str, int]


def load(year: int) -> CaliforniaParams:
    supported = (year_manifest.CALIFORNIA_YEARS
                 + year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS)
    if year not in supported:
        # NotImplementedError (not ValueError) preserves the long-standing
        # forms.f540 contract that callers and tests rely on.
        raise NotImplementedError(
            f"CA Form 540 not implemented for tax year {year} "
            f"(supported CA tax years: {year_manifest.describe(supported)})."
        )
    module = importlib.import_module(f"tenforty.params.california.y{year}")
    return module.PARAMS
