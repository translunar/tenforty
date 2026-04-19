"""Schedule E — Supplemental Income and Loss.

v1 scope: single rental property (slot A on Page 1). Property slots B
and C exist on the form but are not populated by v1. Page 2 (K-1
flow-throughs) is out of scope.

Per-expense amounts for property A come from the scenario's
``RentalProperty`` (they're user inputs, not computed values — the
oracle workbook consumes them rather than exposing them as named
ranges). Lines 20 (total expenses) and 21 (income/loss) are summed
locally here. Line 26 (page total) comes from the oracle via
``f1040['sche_line26']`` and is cross-checked against the locally-summed
line 21 for the single-property case.
"""

import logging

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
    ("depreciation", "sch_e_property_a_depreciation"),
    ("other_expenses", "sch_e_property_a_other_expenses"),
)


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream.get("f1040", {})
    result: dict = {
        "taxpayer_name": _format_taxpayer_name(scenario),
        "taxpayer_ssn": scenario.config.ssn,
    }
    if not scenario.rental_properties:
        return result

    rp = scenario.rental_properties[0]
    result.update(_property_a_fields(rp))

    local_total = result["sch_e_property_a_income_loss"]
    line_26_oracle = f1040.get("sche_line26")
    if line_26_oracle is not None:
        result["sch_e_line_26_total"] = irs_round(line_26_oracle)
        if result["sch_e_line_26_total"] != local_total:
            log.warning(
                "Sch E line 26 oracle total %s diverges from locally-summed "
                "single-property line 21 %s; using oracle value.",
                result["sch_e_line_26_total"], local_total,
            )
    else:
        result["sch_e_line_26_total"] = local_total
    return result


def _property_a_fields(rp: RentalProperty) -> dict:
    fields: dict = {
        "sch_e_property_a_address": rp.address,
        "sch_e_property_a_type_code": rp.property_type_code,
        "sch_e_property_a_fair_rental_days": rp.fair_rental_days,
        "sch_e_property_a_personal_use_days": rp.personal_use_days,
        "sch_e_property_a_rents": irs_round(rp.rents_received),
    }
    total_expenses = 0.0
    for attr, key in _EXPENSE_FIELDS:
        value = getattr(rp, attr)
        rounded = irs_round(value)
        if rounded:
            fields[key] = rounded
        total_expenses += value
    fields["sch_e_property_a_total_expenses"] = irs_round(total_expenses)
    fields["sch_e_property_a_income_loss"] = (
        irs_round(rp.rents_received) - irs_round(total_expenses)
    )
    return fields


def has_any_net_loss(scenario: Scenario) -> bool:
    """True when any Sch E Part I rental runs a net loss.

    Single-purpose helper for orchestrator predicates. Does not go
    through compute() — just sums the scenario's own fields.
    """
    for p in scenario.rental_properties:
        expense_fields = (
            p.advertising, p.auto_and_travel, p.cleaning_and_maintenance,
            p.commissions, p.insurance, p.legal_and_professional_fees,
            p.management_fees, p.mortgage_interest, p.other_interest,
            p.repairs, p.supplies, p.taxes, p.utilities, p.depreciation,
            p.other_expenses,
        )
        if p.rents_received < sum(expense_fields):
            return True
    return False


def _format_taxpayer_name(scenario: Scenario) -> str:
    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return f"{first} {last}".strip()
