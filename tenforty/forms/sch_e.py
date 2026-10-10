"""Schedule E — Supplemental Income and Loss.

v1 scope: single rental property (slot A on Page 1). Property slots B
and C exist on the form but are not populated by v1. Page 2 (K-1
flow-throughs) is out of scope.

Per-expense amounts for property A come from the scenario's
``RentalProperty`` (they're user inputs, not computed values — the
oracle workbook consumes them rather than exposing them as named
ranges). The exception is line 18 (depreciation), which comes from the
depreciation resolver: the property's asset list, or its stated amount.
Lines 20 (total expenses) and 21 (income/loss) are summed
locally here, as are the page totals on lines 23a/23c/23d/23e and 24. Line 26 (page total) comes from the oracle via
``f1040['sche_line26']`` and is cross-checked against the locally-summed
line 21 for the single-property case.
"""

import logging

from tenforty.forms.depreciation.resolver import mid_quarter_years, resolve
from tenforty.models import RentalProperty, Scenario
from tenforty.rounding import irs_round

log = logging.getLogger(__name__)


_EXPENSE_FIELDS = (
    ("advertising", "sch_e_property_a_advertising"),
    ("auto_and_travel", "sch_e_property_a_auto_and_travel"),
    ("cleaning_and_maintenance", "sch_e_property_a_cleaning_and_maintenance"),
    ("commissions", "sch_e_property_a_commissions"),
    ("insurance", "sch_e_property_a_insurance"),
    ("legal_and_professional_fees", "sch_e_property_a_legal_and_professional_fees"),
    ("management_fees", "sch_e_property_a_management_fees"),
    ("mortgage_interest", "sch_e_property_a_mortgage_interest"),
    ("other_interest", "sch_e_property_a_other_interest"),
    ("repairs", "sch_e_property_a_repairs"),
    ("supplies", "sch_e_property_a_supplies"),
    ("taxes", "sch_e_property_a_taxes"),
    ("utilities", "sch_e_property_a_utilities"),
    ("other_expenses", "sch_e_property_a_other_expenses"),
)
# Line 18 (depreciation) is deliberately NOT in the tuple above: it is not a
# raw field read. It comes from the depreciation resolver -- the one door --
# through `_line_18`, which every function below uses.
_LINE_18_KEY = "sch_e_property_a_depreciation"


def _line_18(rp: RentalProperty, tax_year: int, *,
             mid_quarter_years: frozenset[int]) -> float:
    """The property's depreciation as resolved for ``tax_year`` (the stated
    scalar as stated, or the asset-mode / overridden figure)."""
    return resolve(rp, tax_year, mid_quarter_years=mid_quarter_years).amount


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream.get("f1040", {})
    result: dict = {**scenario.config.pdf_header()}
    if not scenario.rental_properties:
        return result

    rp = scenario.rental_properties[0]
    result.update(_property_a_fields(
        rp, scenario.config.year,
        mid_quarter_years=mid_quarter_years(scenario)))

    # printed-chain ruling (SE line 12 lineage), 2026-10-04: line 26 is
    # arithmetic over printed line 21 (single property in v1), so it is the
    # printed-chain total -- NOT the workbook's cents-carried figure rounded
    # independently, which can differ by $1 from what the page's own lines
    # sum to. The oracle value is kept only as a cross-check.
    result.update(_totals_block(result))
    local_total = result["sch_e_property_a_income_loss"]
    line_26_oracle = f1040.get("sche_line26")
    if line_26_oracle is not None and irs_round(line_26_oracle) != local_total:
        log.warning(
            "Sch E line 26 oracle total %s diverges from the printed-chain "
            "line 21 %s; using the printed-chain value.",
            irs_round(line_26_oracle), local_total,
        )
    result["sch_e_line_26_total"] = local_total
    return result


# Lines 23a/23c/23d/23e: "Total of all amounts reported on line N for all
# ... properties". (total key, the printed per-property line it totals.)
_LINE_23_TOTALS = (
    ("sch_e_line_23a_total_rents", "sch_e_property_a_rents"),
    ("sch_e_line_23c_total_mortgage_interest",
     "sch_e_property_a_mortgage_interest"),
    ("sch_e_line_23d_total_depreciation", _LINE_18_KEY),
    ("sch_e_line_23e_total_expenses", "sch_e_property_a_total_expenses"),
)


def _totals_block(printed: dict) -> dict:
    """Lines 22, 23a-23e, 24 and 25, taken from the PRINTED property lines so
    the block foots to the page. Only property A is printed, so each total is
    property A's line.

    A total is absent exactly when its source line is (lines 12 and 18 print
    nothing at zero), and line 24 -- "Add positive amounts shown on line 21.
    Do not include any losses" -- is absent when line 21 is not positive.
    Line 23b (royalties, line 4) has no producer: nothing prints on line 4.
    """
    totals = {
        total_key: printed[line_key]
        for total_key, line_key in _LINE_23_TOTALS if line_key in printed
    }
    line_21 = printed["sch_e_property_a_income_loss"]
    if line_21 > 0:
        totals["sch_e_line_24_income"] = line_21
    if line_21 < 0:
        # Line 22 ("Deductible rental real estate loss after limitation, if
        # any, on Form 8582") is the whole line 21 loss. That is right only
        # when Form 8582 allows the whole loss -- and a return on which it
        # does not never prints: the passive_loss_limitation_not_applied
        # refusal stops it. Line 25 adds royalty losses from line 21 to the
        # line 22 losses; no royalty property is ever printed, so line 25 is
        # line 22. Both cells sit in preprinted parentheses: stored positive.
        totals["sch_e_property_a_deductible_loss"] = -line_21
        totals["sch_e_line_25_losses"] = -line_21
    return totals


def _property_a_fields(rp: RentalProperty, tax_year: int, *,
                       mid_quarter_years: frozenset[int]) -> dict:
    fields: dict = {
        "sch_e_property_a_address": rp.address,
        "sch_e_property_a_type_code": rp.property_type_code,
        "sch_e_property_a_fair_rental_days": rp.fair_rental_days,
        "sch_e_property_a_personal_use_days": rp.personal_use_days,
        "sch_e_property_a_rents": irs_round(rp.rents_received),
    }
    # printed-chain ruling (SE line 12 lineage), 2026-10-04: lines 5-19 are
    # entries (rounded individually); line 20 sums the ROUNDED lines and
    # line 21 = rounded line 3 rents - printed line 20, so the page foots.
    total_expenses = 0
    for attr, key in _EXPENSE_FIELDS:
        rounded = irs_round(getattr(rp, attr))
        if rounded:
            fields[key] = rounded
        total_expenses += rounded
    depreciation = irs_round(_line_18(rp, tax_year, mid_quarter_years=mid_quarter_years))
    if depreciation:
        fields[_LINE_18_KEY] = depreciation
    total_expenses += depreciation
    fields["sch_e_property_a_total_expenses"] = total_expenses
    fields["sch_e_property_a_income_loss"] = (
        irs_round(rp.rents_received) - total_expenses
    )
    return fields


def printed_rental_net(rp: RentalProperty, tax_year: int, *,
                       mid_quarter_years: frozenset[int]) -> int:
    """One property's Schedule E line 21 (income or loss) exactly as the
    form prints it: rounded rents less the sum of the individually rounded
    expense lines. Consumed by the IRC §461(l) excess-business-loss guard
    (orchestrator.aggregate_business_losses)."""
    return _property_a_fields(
        rp, tax_year, mid_quarter_years=mid_quarter_years)["sch_e_property_a_income_loss"]


def has_any_net_loss(scenario: Scenario) -> bool:
    """True when any Sch E Part I rental runs a net loss.

    Iterates _EXPENSE_FIELDS so that adding or removing an expense line
    here keeps the predicate in sync without a second edit; line 18 comes
    from the resolver, as everywhere else."""
    tax_year = scenario.config.year
    mq_years = mid_quarter_years(scenario)
    for p in scenario.rental_properties:
        expense_total = sum(
            getattr(p, attr) for attr, _key in _EXPENSE_FIELDS
        ) + _line_18(p, tax_year, mid_quarter_years=mq_years)
        if p.rents_received < expense_total:
            return True
    return False


