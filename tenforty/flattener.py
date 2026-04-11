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
    _flatten_1098s(scenario, flat)

    _reject_unhandled(scenario)

    return flat


def _reject_unhandled(scenario: Scenario) -> None:
    """Raise NotImplementedError if the scenario has data we can't flatten yet."""
    if scenario.form1099_b:
        raise NotImplementedError(
            f"1099-B flattening not yet implemented "
            f"({len(scenario.form1099_b)} transaction(s) would be silently dropped)"
        )
    if scenario.schedule_k1s:
        raise NotImplementedError(
            f"Schedule K-1 flattening not yet implemented "
            f"({len(scenario.schedule_k1s)} K-1(s) would be silently dropped)"
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
