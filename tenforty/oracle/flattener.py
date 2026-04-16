from tenforty.models import Scenario

_FILING_STATUS_KEYS = {
    "single": "filing_status_single",
    "married_jointly": "filing_status_married_jointly",
    "married_separately": "filing_status_married_separately",
    "head_of_household": "filing_status_head_of_household",
    "qualifying_widow": "filing_status_qualifying_widow",
}


def flatten_scenario(scenario: Scenario) -> dict[str, object]:
    """Convert a Scenario into a flat dict of input keys to values."""
    flat: dict[str, object] = {}

    _flatten_config(scenario, flat)
    _flatten_w2s(scenario, flat)
    _flatten_1099_int(scenario, flat)
    _flatten_1099_div(scenario, flat)
    _flatten_1099g(scenario, flat)
    _flatten_1098s(scenario, flat)
    _flatten_rental_properties(scenario, flat)
    _flatten_k1s(scenario, flat)

    _reject_unhandled(scenario)

    return flat


def _reject_unhandled(scenario: Scenario) -> None:
    """Raise NotImplementedError if the scenario has data we can't flatten yet."""
    if scenario.form1099_b:
        raise NotImplementedError(
            f"1099-B flattening not yet implemented "
            f"({len(scenario.form1099_b)} transaction(s) would be silently dropped)"
        )


def _flatten_config(scenario: Scenario, flat: dict[str, object]) -> None:
    config = scenario.config

    status_key = _FILING_STATUS_KEYS.get(config.filing_status)
    if status_key:
        flat[status_key] = "X"

    parts = config.birthdate.split("-")
    flat["birthdate_year"] = int(parts[0])
    flat["birthdate_month"] = int(parts[1])
    flat["birthdate_day"] = int(parts[2])


def _flatten_w2s(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, w2 in enumerate(scenario.w2s, start=1):
        flat[f"w2_wages_{i}"] = w2.wages
        flat[f"w2_fed_withheld_{i}"] = w2.federal_tax_withheld
        flat[f"w2_ss_wages_{i}"] = w2.ss_wages
        flat[f"w2_ss_withheld_{i}"] = w2.ss_tax_withheld
        flat[f"w2_medicare_wages_{i}"] = w2.medicare_wages
        flat[f"w2_medicare_withheld_{i}"] = w2.medicare_tax_withheld
        if w2.state_wages:
            flat[f"w2_state_wages_{i}"] = w2.state_wages
        if w2.state_tax_withheld:
            flat[f"w2_state_withheld_{i}"] = w2.state_tax_withheld


def _flatten_1099_int(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, form in enumerate(scenario.form1099_int, start=1):
        flat[f"interest_{i}"] = form.interest


def _flatten_1099_div(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, form in enumerate(scenario.form1099_div, start=1):
        flat[f"ordinary_dividends_{i}"] = form.ordinary_dividends
        flat[f"qualified_dividends_{i}"] = form.qualified_dividends
        if form.capital_gain_distributions:
            flat[f"capital_gain_distributions_{i}"] = form.capital_gain_distributions


def _flatten_1098s(scenario: Scenario, flat: dict[str, object]) -> None:
    total_mortgage = 0.0
    total_property_tax = 0.0
    for form in scenario.form1098s:
        total_mortgage += form.mortgage_interest
        total_property_tax += form.property_tax
    if total_mortgage:
        flat["mortgage_interest"] = total_mortgage
    if total_property_tax:
        flat["property_tax"] = total_property_tax


_RENTAL_PROPERTY_LETTERS = "abcdefgh"

_RENTAL_EXPENSE_FIELDS = [
    ("advertising", "sche_advertising"),
    ("auto_and_travel", "sche_auto_and_travel"),
    ("cleaning_and_maintenance", "sche_cleaning_and_maintenance"),
    ("commissions", "sche_commissions"),
    ("insurance", "sche_insurance"),
    ("legal_and_professional_fees", "sche_legal_and_professional_fees"),
    ("management_fees", "sche_management_fees"),
    ("mortgage_interest", "sche_mortgage_interest"),
    ("other_interest", "sche_other_interest"),
    ("repairs", "sche_repairs"),
    ("supplies", "sche_supplies"),
    ("taxes", "sche_taxes"),
    ("utilities", "sche_utilities"),
    ("depreciation", "sche_depreciation"),
    ("other_expenses", "sche_other_expenses"),
]


def _flatten_rental_properties(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, prop in enumerate(scenario.rental_properties):
        letter = _RENTAL_PROPERTY_LETTERS[i]
        flat[f"sche_property_type_{letter}"] = prop.property_type
        flat[f"sche_fair_rental_days_{letter}"] = prop.fair_rental_days
        flat[f"sche_personal_use_days_{letter}"] = prop.personal_use_days
        flat[f"sche_rents_{letter}"] = prop.rents_received

        for attr, key_prefix in _RENTAL_EXPENSE_FIELDS:
            value = getattr(prop, attr)
            if value:
                flat[f"{key_prefix}_{letter}"] = value


_K1_ROW_LETTERS = "abcd"
_K1_FIELD_KEYS = (
    ("entity_name", "entity_name"),
    ("entity_ein", "entity_ein"),
    ("ordinary_business_income", "ordinary_business_income"),
    ("net_rental_real_estate", "net_rental_real_estate"),
    ("other_net_rental", "other_net_rental"),
    ("interest_income", "interest_income"),
    ("ordinary_dividends", "ordinary_dividends"),
    ("qualified_dividends", "qualified_dividends"),
    ("royalties", "royalties"),
    ("net_short_term_capital_gain", "net_short_term_capital_gain"),
    ("net_long_term_capital_gain", "net_long_term_capital_gain"),
    ("other_income", "other_income"),
    ("qbi_amount", "qbi_amount"),
)


def _flatten_k1s(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, k1 in enumerate(scenario.schedule_k1s):
        if i >= len(_K1_ROW_LETTERS):
            # The >4 case is gated by acknowledges_no_more_than_four_k1s.
            # Compute-time enforcement (Task 3) raises if ack is False.
            break
        letter = _K1_ROW_LETTERS[i]
        for attr, key in _K1_FIELD_KEYS:
            value = getattr(k1, attr)
            if value:
                flat[f"k1_{letter}_{key}"] = value
        # Entity-type checkbox (mutually exclusive):
        flat[f"k1_{letter}_entity_type_{k1.entity_type}"] = "X"


def _flatten_1099g(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, g in enumerate(scenario.form1099_g, start=1):
        if g.unemployment_compensation:
            flat[f"g_unemployment_{i}"] = g.unemployment_compensation
        if g.state_tax_refund:
            flat[f"g_state_refund_{i}"] = g.state_tax_refund
        if g.federal_tax_withheld:
            flat[f"g_fed_withheld_{i}"] = g.federal_tax_withheld
        if g.rtaa_payments:
            flat[f"g_rtaa_{i}"] = g.rtaa_payments
        if g.taxable_grants:
            flat[f"g_taxable_grants_{i}"] = g.taxable_grants
        if g.agriculture_payments:
            flat[f"g_ag_{i}"] = g.agriculture_payments
        if g.market_gain:
            flat[f"g_market_gain_{i}"] = g.market_gain
