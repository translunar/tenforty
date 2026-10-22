"""Earned income credit, ZERO qualifying children (Form 1040 line 27a) —
the childless-EITC leg.

The year's Form 1040 instructions are the procedure: the Step 2 investment
income test, the Step 4 age test, Step 5's earned income, and Worksheet A
(no self-employment) or B (self-employment) to read the credit off the
published EIC Table (tenforty.eic_table — the table is the method; the
params formula only cross-checks it). Pure: no I/O beyond the table asset.

Eligibility FACTS (main home, SSN, dependency, nonresident alien) are not
read here yet; the eic_eligibility block feeds them in a later step. Until
then the caller must not route a return here except from tests.
"""
import dataclasses
import datetime

from tenforty.eic_table import eic_from_table
from tenforty.models import FilingStatus, Scenario, parse_filing_status
from tenforty.params.federal import FederalParams
from tenforty.rounding import irs_round

_STATUS_KEY = {
    FilingStatus.SINGLE: FilingStatus.SINGLE.value,
    FilingStatus.MARRIED_FILING_JOINTLY:
        FilingStatus.MARRIED_FILING_JOINTLY.value,
}
# Schedule SE's own threshold: net earnings under it file no Schedule SE,
# so Worksheet B takes Part 2 (Schedule C line 31) instead of Part 1.
_SE_FILING_THRESHOLD = 400


@dataclasses.dataclass(frozen=True)
class Determination:
    eligible: bool
    reason: str | None   # slug when not eligible
    rule: str            # where the year's instructions decide it

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def meets_age_test(config, year: int, params: FederalParams) -> bool:
    """Step 4 question 2: the taxpayer — or, on a joint return, either
    spouse — attained ``eic_min_age`` and had not attained ``eic_max_age``
    by the end of the year. Stated as the instructions state it, by birth
    date: born before January 2 of (year - min_age + 1) and, where there is
    an upper bound, after December 31 of (year - max_age)."""
    born_before = datetime.date(year - params.eic_min_age + 1, 1, 2)
    born_after = (None if params.eic_max_age is None
                  else datetime.date(year - params.eic_max_age, 12, 31))

    def meets(value: str) -> bool:
        born = datetime.date.fromisoformat(value)
        return born < born_before and (born_after is None or born > born_after)

    people = [config.birthdate]
    if parse_filing_status(config.filing_status) is (
            FilingStatus.MARRIED_FILING_JOINTLY):
        if not config.spouse_birthdate:
            raise ValueError("the EIC age test on a married_filing_jointly "
                             "return needs `spouse_birthdate`")
        people.append(config.spouse_birthdate)
    return any(meets(p) for p in people)


def investment_income(scenario: Scenario, spine: dict) -> int:
    """Step 2: Form 1040 lines 2a + 2b + 3b + 7a (7a: 0 if a loss). Line 2a
    is read from the 1099-INTs: the native spine does not carry it."""
    tax_exempt = sum(f.tax_exempt_interest for f in scenario.form1099_int)
    line_7 = spine.get("capital_gain_loss") or 0
    return irs_round(tax_exempt + (spine.get("taxable_interest") or 0)
                     + (spine.get("ordinary_dividends") or 0)
                     + max(0, line_7))


def earned_income(scenario: Scenario, spine: dict,
                  schedule_results: dict) -> tuple[int, str]:
    """(earned income, worksheet "A" | "B"). Step 5: line 1z wages (no
    Medicaid-waiver or combat-pay input exists, so neither adjusts it).
    Self-employment takes Worksheet B: Part 1 (filing Schedule SE) is
    line 3 less line 13 (lines 4b/5a are unmodeled: 0); Part 2 (not required
    to file it) is Schedule C line 31, a loss included."""
    wages = spine.get("wages") or 0
    businesses = scenario.schedule_c_businesses
    if not businesses:
        return irs_round(wages), "A"
    # Part 3 (statutory employees) is unreachable: forms/sch_c.py refuses a
    # statutory_employee business before any credit is figured.
    sch_se = schedule_results.get("sch_se") or {}
    net_earnings = sch_se.get("sch_se_line_4c_net_earnings") or 0
    if net_earnings >= _SE_FILING_THRESHOLD:
        self_employment = (sch_se["sch_se_line_3_net_profit"]
                           - sch_se["sch_se_line_13_half_deduction"])
    else:
        self_employment = (schedule_results.get("sch_c") or {}).get(
            "sch_c_line_31_net_profit_total", 0)
    return irs_round(self_employment + wages), "B"


def compute_eic(scenario: Scenario, spine: dict, params: FederalParams,
                schedule_results: dict) -> dict:
    """Line 27a for a childless SINGLE or MFJ filer, with the determination
    and the worksheet intermediates."""
    year = scenario.config.year
    status = parse_filing_status(scenario.config.filing_status)
    if status not in _STATUS_KEY:
        raise ValueError(f"compute_eic covers single and "
                         f"married_filing_jointly only; got {status.value}")
    key = _STATUS_KEY[status]
    earned, worksheet = earned_income(scenario, spine, schedule_results)
    invest = investment_income(scenario, spine)
    agi = irs_round(spine["agi"])
    out = {"eic_earned_income": earned, "eic_investment_income": invest,
           "eic_worksheet": worksheet, "eic_table_earned": None,
           "eic_table_agi": None}

    def result(credit: int, determination: Determination) -> dict:
        return {**out, "eic": credit,
                "eic_determination": determination.as_dict()}

    if invest > params.eic_investment_income_limit:
        return result(0, Determination(
            False, "investment_income_over_limit", "Step 2, question 2"))
    if not meets_age_test(scenario.config, year, params):
        return result(0, Determination(False, "age_test_not_met",
                                       "Step 4, question 2"))
    if earned < params.eic_min_earned_income:
        return result(0, Determination(False, "no_earned_income",
                                       f"Worksheet {worksheet}, earned income"))
    table_earned = eic_from_table(earned, year, status)
    out["eic_table_earned"] = table_earned
    credit = table_earned
    if agi != earned and agi >= params.eic_phaseout_threshold[key]:
        out["eic_table_agi"] = eic_from_table(agi, year, status)
        credit = min(table_earned, out["eic_table_agi"])
    if credit == 0:
        return result(0, Determination(
            False, "credit_is_zero", f"Worksheet {worksheet}, credit line"))
    return result(credit, Determination(True, None,
                                        f"Worksheet {worksheet}"))
