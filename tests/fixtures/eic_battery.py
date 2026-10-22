"""Earned income credit battery: scenario INPUTS only, no expected amounts
(exact values are pinned from the oracle run, not transcribed here).

Single filer, no dependents, one W-2. Wages are placed relative to the
no-child ceiling the spine-routing gate reads (params eic_income_ceiling[0]),
never a hard-coded threshold.
All identities and amounts are fully synthetic.
"""
from collections.abc import Callable

from tenforty.models import Scenario
from tenforty.params.federal import load as load_params
from tests.fixtures.spine_battery import _battery_config, _w2

YEAR = 2024
PLATEAU_WAGES = 9000.0  # the confirmed non-footing shape (line 33 932, 27 blank)


def _ceiling(year: int) -> int:
    return load_params(year).eic_income_ceiling[0]


def _single_w2(year: int, wages: float) -> Scenario:
    return Scenario(
        config=_battery_config(year),
        w2s=[_w2(year, "Synthetic Employer EIC", wages,
                 federal_tax_withheld=300.0)])


def build_plateau(year: int) -> Scenario:
    # Full no-child credit; routes to the workbook.
    return _single_w2(year, PLATEAU_WAGES)


def build_phase_out(year: int) -> Scenario:
    # Midway from the plateau wages to the ceiling: a partial credit.
    return _single_w2(year, float(round((PLATEAU_WAGES + _ceiling(year)) / 2)))


def build_over_ceiling(year: int) -> Scenario:
    # Above the gate's ceiling: routes to the native spine (no EIC math).
    return _single_w2(year, float(_ceiling(year) + 1000))


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "plateau": build_plateau,
    "phase-out": build_phase_out,
    "over-ceiling": build_over_ceiling,
}


# --- Native childless-EIC battery registry (childless-EITC spec §10.4) ------
#
# The grid gates (tests/test_eic_grid_gates.py) read these. Rows are placed
# relative to the year's attested EIC params, so a (year, status) has no rows
# until its params land; a declared cell without them is a red gate.

_UNSET = object()

_EIC_KINDS_EVERY_CELL: tuple[str, ...] = (
    "plateau",
    "phase_in",
    "phase_out",
    "just_under_ceiling",
    "over_ceiling",
    "agi_over_earned",            # interest pushes AGI into the phase-out
    "investment_at_limit",
    "investment_over_limit",      # one table bin over
    "age_lower_bound_in",
    "age_lower_bound_out",
    "sch_c_worksheet_b",
    "sch_c_net_loss",
    "fact_ssn_not_valid",
    "fact_nonresident_alien",
    "fact_main_home_not_in_us",
    "fact_qualifying_child_of_another",
    "fact_claimable_as_dependent",
)
_EIC_KINDS_UPPER_AGE: tuple[str, ...] = (
    "age_upper_bound_in", "age_upper_bound_out")
_EIC_KINDS_MFJ: tuple[str, ...] = ("mfj_one_spouse_in_age_band",)


def required_eic_kinds(year: int, status: str) -> tuple[str, ...]:
    """Battery kinds a declared (year, status) must carry. The upper-age
    pair is required unless the year's params state there is no upper bound
    (``eic_max_age`` explicitly None); absent params require it."""
    kinds = _EIC_KINDS_EVERY_CELL
    if getattr(load_params(year), "eic_max_age", _UNSET) is not None:
        kinds += _EIC_KINDS_UPPER_AGE
    if status == "married_filing_jointly":
        kinds += _EIC_KINDS_MFJ
    return kinds


# (year, status) -> {kind: builder}. Empty until a cell's params land.
EIC_ROWS: dict[tuple[int, str], dict[str, Callable[[int], Scenario]]] = {}


def battery_for(year: int, status: str) -> dict[str, Callable[[int], Scenario]]:
    return EIC_ROWS.get((year, status), {})


# Refusal keys every year with a declared EIC cell must reach through
# load_scenario (spec §2 Out, §4, §5.5, §5.6). Year-scoped keys apply only to
# their year.
EIC_REFUSALS_EVERY_YEAR: tuple[str, ...] = (
    "eic_eligibility_missing",
    "prior_eic_disallowance_8862",
    "worksheet_1_rental",
    "worksheet_1_k1",
    "statutory_employee",
    "k1_self_employment_earnings",
    "year_scoped_eic_fact",
)
EIC_REFUSALS_BY_YEAR: dict[int, tuple[str, ...]] = {
    2021: ("arpa_youth_age_18", "specified_student_2021_missing"),
}


def required_eic_refusals(year: int) -> tuple[str, ...]:
    return EIC_REFUSALS_EVERY_YEAR + EIC_REFUSALS_BY_YEAR.get(year, ())


# refusal key -> {year: scenario YAML path} reaching it through load_scenario.
EIC_REFUSAL_FIXTURES: dict[str, dict[int, str]] = {}
