"""Earned income credit battery: scenario INPUTS only, no expected amounts
(exact values are pinned from the oracle run, not transcribed here).

Single filer, no dependents, one W-2. Wages are placed relative to the
no-child ceiling the spine-routing gate reads (params eic_income_ceiling[0]),
never a hard-coded threshold.
All identities and amounts are fully synthetic.
"""
from collections.abc import Callable

import dataclasses

from tenforty.models import EicEligibility, EicPersonFacts, Scenario
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
# Refusals only a declared cell of this status can reach.
EIC_REFUSALS_BY_STATUS: dict[str, tuple[str, ...]] = {
    "married_filing_jointly": ("nonresident_alien_spouse_election",),
}


def required_eic_refusals(year: int,
                          statuses: tuple[str, ...]) -> tuple[str, ...]:
    keys = EIC_REFUSALS_EVERY_YEAR + EIC_REFUSALS_BY_YEAR.get(year, ())
    for status in statuses:
        keys += EIC_REFUSALS_BY_STATUS.get(status, ())
    return keys


# refusal key -> {year: scenario YAML path} reaching it through load_scenario.
_R = "tests/fixtures/eic_refusals"
EIC_REFUSAL_FIXTURES: dict[str, dict[int, str]] = {
    key: {year: f"{_R}/{key}_{year}.yaml" for year in (2024, 2025)}
    for key in ("eic_eligibility_missing", "prior_eic_disallowance_8862",
                "worksheet_1_rental", "worksheet_1_k1", "statutory_employee",
                "k1_self_employment_earnings", "year_scoped_eic_fact",
                "nonresident_alien_spouse_election")}


def favorable_person(**overrides) -> EicPersonFacts:
    """Every eligibility fact stated favorable, unless overridden."""
    return dataclasses.replace(EicPersonFacts(
        main_home_in_us_more_than_half_year=True,
        can_be_claimed_as_dependent=False,
        could_be_qualifying_child_of_another=False,
        ssn_valid_for_employment=True,
        nonresident_alien_any_part_of_year=False), **overrides)


def favorable_eligibility(status: str = "single",
                          **overrides) -> EicEligibility:
    """A complete, all-favorable eic_eligibility block for ``status``."""
    joint = status == "married_filing_jointly"
    return dataclasses.replace(EicEligibility(
        taxpayer=favorable_person(),
        spouse=favorable_person() if joint else None,
        prior_eic_disallowance_requires_8862=False), **overrides)


# --- (2025, single) rows: every required kind, placed off the attested
# params (never a typed-in threshold). Each row states a favorable block
# unless its kind is a fact row.

def _eic_row(year: int, wages: float, *, status: str = "single",
             birthdate: str | None = None, interest: float = 0.0,
             schedule_c=None, eligibility=None,
             **config_overrides) -> Scenario:
    from tenforty.models import Form1099INT, FilingStatus
    joint = status == "married_filing_jointly"
    config = _battery_config(year, FilingStatus(status), **config_overrides)
    if birthdate is not None:
        # On a joint return EITHER spouse meets the age test, so an age-bound
        # row places both spouses at the bound.
        config = dataclasses.replace(
            config, birthdate=birthdate,
            **({"spouse_birthdate": birthdate} if joint else {}))
    return Scenario(
        config=config,
        w2s=[_w2(year, "Synthetic Employer EIC", wages,
                 federal_tax_withheld=0.0,
                 owner="taxpayer" if joint else None)] if wages else [],
        form1099_int=([Form1099INT(payer="Example Bank", interest=interest)]
                      if interest else []),
        schedule_c_businesses=list(schedule_c or []),
        eic_eligibility=eligibility or favorable_eligibility(status))


def upper_age_window(year: int, status: str) -> tuple[int, int]:
    """Ruling R-S8-3: an upper-age row is an AGED filer (it checks the Form
    1040 age box), so at or under the Schedule R AGI limit tenforty refuses
    (credit for the elderly, not modeled) before any EIC is figured. The
    rows sit strictly between that limit (both spouses aged on a joint
    return) and the year's completed phaseout, where the credit is still
    figured. Both bounds are read from code/params, never typed in."""
    from tenforty.orchestrator import _SCHEDULE_R_AGI_LIMITS
    boxes = 2 if status == "married_filing_jointly" else 1
    return (_SCHEDULE_R_AGI_LIMITS[(status, boxes)],
            load_params(year).eic_completed_phaseout[status])


def _rows(year: int, status: str) -> dict[str, Callable[[int], Scenario]]:
    import datetime
    from tenforty.models import ScheduleCBusiness
    p = load_params(year)
    begin = p.eic_phaseout_threshold[status]
    end = p.eic_completed_phaseout[status]
    plateau = p.eic_earned_income_amount + 100
    min_cut = datetime.date(year - p.eic_min_age + 1, 1, 2)
    max_cut = datetime.date(year - p.eic_max_age, 12, 31)
    day = datetime.timedelta(days=1)
    upper_age_wages = sum(upper_age_window(year, status)) // 2
    row = lambda *a, **k: _eic_row(*a, status=status, **k)  # noqa: E731
    fact = lambda **o: favorable_eligibility(  # noqa: E731
        status, taxpayer=favorable_person(**o))
    rows = {
        "plateau": lambda y: row(y, plateau),
        "phase_in": lambda y: row(y, p.eic_earned_income_amount // 2),
        "phase_out": lambda y: row(y, (begin + end) // 2),
        "just_under_ceiling": lambda y: row(y, end - 1),
        "over_ceiling": lambda y: row(y, end + 1000),
        # Earned income on the plateau; interest lifts AGI into the phaseout
        # while staying within the investment-income limit.
        "agi_over_earned": lambda y: row(
            y, plateau, interest=min(p.eic_investment_income_limit,
                                     (begin + end) // 2 - plateau)),
        # Low wages keep AGI under the ceiling beside the limit's interest.
        "investment_at_limit": lambda y: row(
            y, 2000, interest=p.eic_investment_income_limit),
        "investment_over_limit": lambda y: row(
            y, 2000, interest=p.eic_investment_income_limit + 1),
        "age_lower_bound_in": lambda y: row(
            y, plateau, birthdate=(min_cut - day).isoformat()),
        "age_lower_bound_out": lambda y: row(
            y, plateau, birthdate=min_cut.isoformat()),
        "age_upper_bound_in": lambda y: row(
            y, upper_age_wages, birthdate=(max_cut + day).isoformat()),
        "age_upper_bound_out": lambda y: row(
            y, upper_age_wages, birthdate=max_cut.isoformat()),
        "sch_c_worksheet_b": lambda y: row(y, 3000, schedule_c=[
            ScheduleCBusiness(description="Example Route",
                              gross_receipts=3000.0)]),
        # A loss answers Schedule C line 32: all investment at risk (32a).
        "sch_c_net_loss": lambda y: row(y, 6000, schedule_c=[
            ScheduleCBusiness(description="Example Route",
                              gross_receipts=0.0, supplies=500.0)],
            acknowledges_sch_c_all_investment_at_risk=True),
        "fact_ssn_not_valid": lambda y: row(
            y, plateau, eligibility=fact(ssn_valid_for_employment=False)),
        "fact_nonresident_alien": lambda y: row(
            y, plateau,
            eligibility=fact(nonresident_alien_any_part_of_year=True)),
        "fact_main_home_not_in_us": lambda y: row(
            y, plateau,
            eligibility=fact(main_home_in_us_more_than_half_year=False)),
        "fact_qualifying_child_of_another": lambda y: row(
            y, plateau,
            eligibility=fact(could_be_qualifying_child_of_another=True)),
        "fact_claimable_as_dependent": lambda y: row(
            y, plateau, eligibility=fact(can_be_claimed_as_dependent=True)),
    }
    # eic_min_earned_income at its boundary (not a required kind: the
    # coverage map's exerciser for that param, ruling R-S7-4). One dollar
    # under the minimum is no earned income at all.
    rows["earned_income_below_min"] = lambda y: row(
        y, float(p.eic_min_earned_income - 1))
    rows["earned_income_at_min"] = lambda y: row(
        y, float(p.eic_min_earned_income))
    if status == "married_filing_jointly":
        # Only the taxpayer under the lower bound: the spouse (the battery's
        # in-band birth date) satisfies the test for both.
        def one_spouse_in_band(y):
            scenario = row(y, plateau)
            return dataclasses.replace(scenario, config=dataclasses.replace(
                scenario.config, birthdate=min_cut.isoformat()))
        rows["mfj_one_spouse_in_age_band"] = one_spouse_in_band
    return rows


EIC_ROWS[(2025, "single")] = _rows(2025, "single")
# 2025 MFJ rows exist ahead of the cell's declaration (spec step 7: parity
# first, then the grid row).
EIC_ROWS[(2025, "married_filing_jointly")] = _rows(2025, "married_filing_jointly")
# 2024 rows (step 8) exist ahead of the cells' declaration: parity first.
EIC_ROWS[(2024, "single")] = _rows(2024, "single")
EIC_ROWS[(2024, "married_filing_jointly")] = _rows(2024, "married_filing_jointly")
