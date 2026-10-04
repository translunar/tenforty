"""Schedule C verification battery: scenario INPUTS and the native per-line
extractor. Contains no expected tax values -- the extractor reports what the
native compute produced, line by printed line, for a separate comparison.

Absent lines stay ABSENT (never defaulted to zero) so a consumer needing
one fails loudly on the missing key; the single exception is Schedule 2, whose component lines are omitted
when zero by design (_ZERO_WHEN_ABSENT).

All identities and amounts are fully synthetic."""
from collections.abc import Callable

from tenforty.forms import sch_2 as form_sch_2
from tenforty.models import Scenario, ScheduleCBusiness, W2
from tenforty.rounding import irs_round
from tests.fixtures.spine_battery import _battery_config

YEARS = (2022, 2023, 2024, 2025)

# Scenario-years the native Form 8995 simple path refuses (taxable income
# above the threshold -> Form 8995-A needed).
REFUSING = frozenset({
    ("day-job-plus-consulting", 2022),
    ("base-maxed-day-job", 2022),
    ("base-maxed-day-job", 2023),
    ("base-maxed-day-job", 2024),
    ("base-maxed-day-job", 2025),
})
REFUSAL_TEXT = "Form 8995 simple-path threshold"


def _w2(employer: str, amount: float) -> W2:
    return W2(
        employer=employer, wages=amount, federal_tax_withheld=0.0,
        ss_wages=amount, ss_tax_withheld=0.0,
        medicare_wages=amount, medicare_tax_withheld=0.0,
    )


def _build(year: int, businesses: list[ScheduleCBusiness],
           w2s: list[W2] | None = None) -> Scenario:
    return Scenario(
        config=_battery_config(year),
        w2s=w2s or [],
        schedule_c_businesses=businesses,
    )


def _sole_trade_basic(year):
    return _build(year, [ScheduleCBusiness(
        description="Crestline Editing", gross_receipts=52_000.0,
        advertising=1_200.0, supplies=800.0, office_expense=500.0)])


def _two_trades(year):
    return _build(year, [
        ScheduleCBusiness(description="Harbor Tutoring",
                          gross_receipts=31_000.0, supplies=1_000.0),
        ScheduleCBusiness(description="Pinewood Crafts",
                          gross_receipts=14_500.0, utilities=500.0,
                          other_expenses=1_000.0),
    ])


def _day_job_plus_consulting(year):
    return _build(year, [ScheduleCBusiness(
        description="Juniper Analytics", gross_receipts=90_000.0,
        legal_professional=2_000.0, travel=3_000.0)],
        w2s=[_w2("Larkspur Systems", 105_000.0)])


def _base_maxed_day_job(year):
    return _build(year, [ScheduleCBusiness(
        description="Quartz Consulting", gross_receipts=45_000.0,
        insurance=1_000.0)],
        w2s=[_w2("Granite Peak Labs", 180_000.0)])


def _under_threshold_sideline(year):
    return _build(year, [ScheduleCBusiness(
        description="Side Bakes", gross_receipts=1_100.0, supplies=750.0)])


def _big_sole_trade(year):
    return _build(year, [ScheduleCBusiness(
        description="Meridian Design", gross_receipts=230_000.0,
        rent_lease=12_000.0, wages=25_000.0, taxes_licenses=3_000.0)])


def _qbi_interplay(year):
    return _build(year, [ScheduleCBusiness(
        description="Cedar Writing", gross_receipts=64_000.0,
        office_expense=1_500.0, deductible_meals=500.0)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "sole-trade-basic": _sole_trade_basic,
    "two-trades": _two_trades,
    "day-job-plus-consulting": _day_job_plus_consulting,
    "base-maxed-day-job": _base_maxed_day_job,
    "under-threshold-sideline": _under_threshold_sideline,
    "big-sole-trade": _big_sole_trade,
    "qbi-interplay": _qbi_interplay,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)


# form -> printed line -> native compute key. Some f8995 native keys sit one
# tier above their printed line (see the seam table in
# tenforty/mappings/pdf_f8995.py): printed 5 is f8995_line_3_component and
# printed 10 is f8995_line_6_total_before_limit.
LINE_KEYS = {
    "sch_c": {
        "1": "sch_c_line_1_gross_receipts",
        "3": "sch_c_line_3_net_receipts",
        "5": "sch_c_line_5_gross_profit",
        "7": "sch_c_line_7_gross_income",
        "28": "sch_c_line_28_total_expenses",
        "29": "sch_c_line_29_tentative_profit",
        "31": "sch_c_line_31_net_profit",
    },
    "sch_se": {
        "2": "sch_se_line_2_net_profit",
        "3": "sch_se_line_3_net_profit",
        "4a": "sch_se_line_4a_net_earnings",
        "4c": "sch_se_line_4c_net_earnings",
        "6": "sch_se_line_6_total_net_earnings",
        "7": "sch_se_line_7_ss_wage_base",
        "8a": "sch_se_line_8a_ss_wages_and_tips",
        "8d": "sch_se_line_8d_wages_subject_to_ss",
        "9": "sch_se_line_9_ss_earnings_remaining",
        "10": "sch_se_line_10_ss_portion",
        "11": "sch_se_line_11_medicare_portion",
        "12": "sch_se_line_12_se_tax",
        "13": "sch_se_line_13_half_deduction",
    },
    "sch_2": {
        "4": "sch_2_line_4_se_tax",
        "11": "sch_2_line_11_additional_medicare_tax",
        "21": "sch_2_line_21_total_other_taxes",
    },
    "sch_1": {
        "3": "sch_1_line_3_business_income",
        "15": "sch_1_line_15_se_tax",
    },
    "f8995": {
        "1": "f8995_line_1_qbi",
        "2": "f8995_line_2_total_qbi",
        "3": "f8995_line_3_prior_qbi_loss_carryforward",
        "4": "f8995_line_4_total_qbi",
        "5": "f8995_line_3_component",
        "10": "f8995_line_6_total_before_limit",
        "11": "f8995_line_11_taxable_income",
        "12": "f8995_line_12_net_capital_gain",
        "13": "f8995_line_13_subtract",
        "14": "f8995_line_14_income_limit",
        "15": "f8995_line_15_qbi_deduction",
    },
    "f1040": {"agi": "agi", "taxable_income": "taxable_income"},
}

# Schedule 2 omits a component line when it is zero; every other form's
# absent line must stay absent so the fixture fails loudly.
_ZERO_WHEN_ABSENT = frozenset({"sch_2"})


def _extract(form: str, results: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for line, key in LINE_KEYS[form].items():
        if key in results:
            out[line] = irs_round(results[key])
        elif form in _ZERO_WHEN_ABSENT:
            out[line] = 0
        # else: the line stays ABSENT (not zero) -- e.g. Schedule SE prints
        # lines 7-13 blank below the $400 floor. A consumer that needs the
        # line fails loudly on the missing key.
    return out


def native_lines(orch, scenario: Scenario) -> dict[str, dict[str, int]]:
    """Per-form, per-printed-line whole-dollar values from the native compute.

    Raises whatever the compute raises (a refusal is a NotImplementedError).
    Form keys: sch_c_1..sch_c_N (one per business), sch_se, sch_2, sch_1,
    f8995, f1040.
    """
    f1040 = orch.compute_federal(scenario)
    native, _fanout = orch._compute_native_schedules(scenario)
    lines: dict[str, dict[str, int]] = {}
    for n, business in enumerate(native["sch_c"]["sch_c_businesses"], start=1):
        lines[f"sch_c_{n}"] = _extract("sch_c", business)
    lines["sch_se"] = _extract("sch_se", native["sch_se"])
    sch_2 = form_sch_2.compute(scenario, {"f1040": f1040})
    lines["sch_2"] = _extract("sch_2", sch_2)
    lines["sch_1"] = _extract("sch_1", native["sch_1"])
    lines["f8995"] = _extract("f8995", native["f8995"])
    lines["f1040"] = _extract("f1040", f1040)
    return lines
