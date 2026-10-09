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

from tenforty.forms.depreciation.resolver import resolve
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


def _line_18(rp: RentalProperty, tax_year: int) -> float:
    """The property's depreciation as resolved for ``tax_year`` (the stated
    scalar as stated, or the asset-mode / overridden figure)."""
    return resolve(rp, tax_year).amount


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream.get("f1040", {})
    result: dict = {**scenario.config.pdf_header()}
    if not scenario.rental_properties:
        return result

    rp = scenario.rental_properties[0]
    result.update(_property_a_fields(rp, scenario.config.year))

    # printed-chain ruling (SE line 12 lineage), 2026-10-04: line 26 is
    # arithmetic over printed line 21 (single property in v1), so it is the
    # printed-chain total -- NOT the workbook's cents-carried figure rounded
    # independently, which can differ by $1 from what the page's own lines
    # sum to. The oracle value is kept only as a cross-check.
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


def _property_a_fields(rp: RentalProperty, tax_year: int) -> dict:
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
    depreciation = irs_round(_line_18(rp, tax_year))
    if depreciation:
        fields[_LINE_18_KEY] = depreciation
    total_expenses += depreciation
    fields["sch_e_property_a_total_expenses"] = total_expenses
    fields["sch_e_property_a_income_loss"] = (
        irs_round(rp.rents_received) - total_expenses
    )
    return fields


def printed_rental_net(rp: RentalProperty, tax_year: int) -> int:
    """One property's Schedule E line 21 (income or loss) exactly as the
    form prints it: rounded rents less the sum of the individually rounded
    expense lines. Consumed by the IRC §461(l) excess-business-loss guard
    (orchestrator.aggregate_business_losses)."""
    return _property_a_fields(rp, tax_year)["sch_e_property_a_income_loss"]


def has_any_net_loss(scenario: Scenario) -> bool:
    """True when any Sch E Part I rental runs a net loss.

    Iterates _EXPENSE_FIELDS so that adding or removing an expense line
    here keeps the predicate in sync without a second edit; line 18 comes
    from the resolver, as everywhere else."""
    tax_year = scenario.config.year
    for p in scenario.rental_properties:
        expense_total = sum(
            getattr(p, attr) for attr, _key in _EXPENSE_FIELDS
        ) + _line_18(p, tax_year)
        if p.rents_received < expense_total:
            return True
    return False


