# tenforty/params/california/__init__.py
"""Per-year California tax parameters. The only thing that differs by year.

Year-agnostic Form 540 logic reads everything from CaliforniaParams; there
are no `if year ==` branches in the math. Adding a year = adding one yNNNN
module and declaring the year in tenforty/years.py.

All status-keyed dicts use FilingStatus.value strings, matching the
FederalParams convention.
"""
import datetime
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class CaliforniaParams:
    year: int
    standard_deduction: dict[str, int]
    exemption_credit: dict[str, int]
    dependent_exemption_amount: int
    # Form 540 line 32 gate, per filing status: federal AGI above the
    # status's threshold triggers the exemption-credit phaseout; v1 raises
    # NotImplementedError there.
    # This same threshold ALSO gates the Schedule CA Part II itemized-deduction
    # AGI limitation (Sch CA line 29): the two are printed as the same figure
    # on the 2024–2025 CA tax booklet (verified coincident via the params
    # attestation), so the existing f540 NotImplementedError scopes out the
    # line-29 reduction too. If FTB ever decouples them, this field must split
    # into separate exemption-phaseout and itemized-limitation thresholds.
    agi_phaseout_threshold: dict[str, int]
    # (threshold_inclusive, marginal_rate_at_or_above_threshold) entries
    # walked by forms.f540._walk_rate_schedule.
    rate_schedule: dict[str, tuple[tuple[int, float], ...]]
    renter_credit_agi_threshold: dict[str, int]
    renter_credit_amount: dict[str, int]
    # Form 540 senior exemption: the credit per qualifying senior. None =
    # pending transcription (age-65-params).
    senior_exemption_credit: int | None
    # Exclusive age cutoff for the tax year: a person born strictly before
    # this date qualifies. None = pending transcription.
    senior_born_before: datetime.date | None
    # Form 540 line 31: taxable income (line 19) at or below this amount
    # takes its tax from the Tax Table; above it, from the Tax Rate
    # Schedules. INCLUSIVE ceiling, one amount for every filing status.
    tax_table_taxable_income_ceiling: int

    def for_status(self, status: "FilingStatus | str") -> "StatusView":
        """Projection of these params onto one filing status. Per-status
        fields (PER_STATUS_CALIFORNIA_FIELDS) read that status's column, raising
        UnsupportedStatusError when it is missing; other fields pass
        through."""
        from tenforty.params.status_view import StatusView
        return StatusView(self, status, PER_STATUS_CALIFORNIA_FIELDS)


# Every CaliforniaParams field whose value is a dict keyed by FilingStatus
# value strings (see PER_STATUS_FEDERAL_FIELDS; same gate, same registry test).
PER_STATUS_CALIFORNIA_FIELDS: tuple[str, ...] = (
    "standard_deduction",
    "exemption_credit",
    "agi_phaseout_threshold",
    "rate_schedule",
    "renter_credit_agi_threshold",
    "renter_credit_amount",
)


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
