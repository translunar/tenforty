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
from tenforty.models import (
    EntityType,
    FilingStatus,
    Scenario,
    parse_filing_status,
)
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
    an upper bound, after December 31 of (year - max_age) — for 2025, born
    after December 31, 1960 and before January 2, 2001.

    Ruling R-T2: this IS the operative rule, not an integer age comparison.
    The statute says "has attained age 25 but not attained age 65 before the
    close of the taxable year"; read with the day-before-birthday
    convention, the two readings differ only on the Dec-31/Jan-1 boundary,
    and the IRS's published birth-date range governs. The independent
    attestation flagged that ambiguity; it was adjudicated, not resolved by
    picking whichever reading matched."""
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

    # The instructions' own order: Step 1 (AGI) before Step 2 (investment
    # income) and Step 4 (age); Step 5 question 3 (earned income).
    if agi >= params.eic_completed_phaseout[key]:
        return result(0, Determination(False, "agi_at_or_over_limit",
                                       "Step 1, question 1"))
    if earned >= params.eic_completed_phaseout[key]:
        return result(0, Determination(
            False, "earned_income_at_or_over_limit", "Step 5, question 3"))
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
    # The TENTATIVE credit (every eligibility fact assumed favorable) is
    # positive: only now do the Worksheet 1 shapes and the stated facts
    # matter (spec §4.1 trigger, §5.5).
    refuse_worksheet_1_shapes(scenario)
    denial = apply_eligibility_facts(scenario, status)
    if denial is not None:
        return result(0, denial)
    return result(credit, Determination(True, None,
                                        f"Worksheet {worksheet}"))


def refuse_worksheet_1_shapes(scenario: Scenario) -> None:
    """Pub. 596 Worksheet 1 investment income (rental, K-1, passive
    activity) is not modeled: refuse on a return whose credit would be
    positive. ORDER IS LOAD-BEARING (ruling on the step-5 plan): the K-1
    self-employment check runs before the any-K-1 check, or a K-1 with SE
    earnings would always name the broader cause and its own refusal would
    be unreachable."""
    if any(k1.entity_type == EntityType.PARTNERSHIP
           and k1.partnership_self_employment_earnings
           for k1 in scenario.schedule_k1s):
        raise NotImplementedError(
            "k1_self_employment_earnings: this return's earned income "
            "credit would include self-employment earnings from a "
            "partnership Schedule K-1 (box 14), which tenforty does not "
            "support for the credit.")
    if scenario.schedule_k1s:
        raise NotImplementedError(
            "worksheet_1_k1: this return has a Schedule K-1 and would "
            "qualify for the earned income credit. Its investment income "
            "then needs Publication 596 Worksheet 1, which tenforty does "
            "not support.")
    if scenario.rental_properties:
        raise NotImplementedError(
            "worksheet_1_rental: this return has rental property (Schedule "
            "E) and would qualify for the earned income credit. Its "
            "investment income then needs Publication 596 Worksheet 1, "
            "which tenforty does not support.")


def apply_eligibility_facts(scenario: Scenario,
                            status: FilingStatus) -> Determination | None:
    """The stated eic_eligibility facts, in the year's instructions' order
    and joint-return wording (2025 Form 1040 instructions, line 27a Steps 1
    and 4). None when every fact allows the credit; a Determination when
    one denies it; a refusal when the block is missing or a fact needs an
    input tenforty does not have."""
    block = scenario.eic_eligibility
    if block is None:
        raise NotImplementedError(
            "eic_eligibility_missing: this return would qualify for the "
            "earned income credit (line 27a) if every eligibility fact is "
            "favorable, so the top-level `eic_eligibility` block is "
            "required: taxpayer (and spouse on a joint return) facts "
            "main_home_in_us_more_than_half_year, can_be_claimed_as_dependent, "
            "could_be_qualifying_child_of_another, ssn_valid_for_employment, "
            "nonresident_alien_any_part_of_year; and "
            "prior_eic_disallowance_requires_8862.")
    if block.prior_eic_disallowance_requires_8862:
        raise NotImplementedError(
            "prior_eic_disallowance_8862: a prior earned income credit was "
            "reduced or disallowed, so Form 8862 must be attached to claim "
            "it; tenforty does not produce Form 8862.")
    joint = status is FilingStatus.MARRIED_FILING_JOINTLY
    people = [block.taxpayer] + ([block.spouse] if joint else [])
    # Step 1 Q2: "Do you, and your spouse if filing a joint return, have"
    # an SSN valid for EIC purposes — both spouses (ruling R-S5-2). Open item
    # O-E4: the 2025 text has NO one-spouse exception; re-verify per year as
    # each year's instructions land, never carry it forward.
    if not all(p.ssn_valid_for_employment for p in people):
        return Determination(False, "ssn_not_valid", "Step 1, question 2")
    # Step 1 Q4 / "Nonresident aliens" (Definitions and Special Rules): "If
    # you checked the box in the Filing Status section to treat a nonresident
    # alien or dual-status alien spouse as a U.S. resident for the entire
    # year, go to Step 2. Otherwise, stop." Ruling R-S5-3 (O-E2 closed as
    # fail-closed pending an input): a single filer stops; a joint return
    # cannot be decided without that election, so it refuses.
    if any(p.nonresident_alien_any_part_of_year for p in people):
        if joint:
            raise NotImplementedError(
                "nonresident_alien_spouse_election: a spouse on this joint "
                "return was a nonresident alien for part of the year. The "
                "earned income credit then turns on the filing-status "
                "election to treat a nonresident alien spouse as a U.S. "
                "resident for the entire year. That election exists in the "
                "law, but tenforty has no input for it, so this return "
                "cannot be computed.")
        return Determination(False, "nonresident_alien", "Step 1, question 4")
    # Step 4 Q3: "Was your main home, and your spouse's if filing a joint
    # return, in the United States for more than half" the year — the
    # spouse's home is included (ruling R-S5-2).
    if not all(p.main_home_in_us_more_than_half_year for p in people):
        return Determination(False, "main_home_not_in_us",
                             "Step 4, question 3")
    # Step 4 Q4: "Are you filing a joint return for 2025? Yes. Skip
    # questions 5 and 6". So on a joint return the qualifying-child-of-
    # another and claimable-dependent facts are deliberately unread — the
    # instructions' own skip, not a gap (ruling R-S5-2); the uniform schema
    # still carries the keys.
    if not joint:
        if block.taxpayer.could_be_qualifying_child_of_another:
            return Determination(False, "qualifying_child_of_another",
                                 "Step 4, question 5")
        if block.taxpayer.can_be_claimed_as_dependent:
            return Determination(False, "claimable_as_dependent",
                                 "Step 4, question 6")
    return None
