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
    _flatten_1099_b(scenario, flat)

    _reject_unhandled(scenario)

    return flat


def _reject_unhandled(scenario: Scenario) -> None:
    """Reserved hook for future form types that cannot yet be flattened.

    Currently a no-op: every modeled form type has an explicit flattener.
    When a new unhandled form type is added to the Scenario schema, raise
    NotImplementedError here so callers fail loudly rather than silently
    dropping data.
    """
    return


def _flatten_config(scenario: Scenario, flat: dict[str, object]) -> None:
    config = scenario.config

    status_key = _FILING_STATUS_KEYS.get(config.filing_status)
    if status_key:
        flat[status_key] = "X"

    parts = config.birthdate.split("-")
    flat["birthdate_year"] = int(parts[0])
    flat["birthdate_month"] = int(parts[1])
    flat["birthdate_day"] = int(parts[2])

    # SALT refund tax-benefit-rule worksheet inputs. Only populate the
    # SALT worksheet cells when a state refund actually exists — setting
    # the filing-status checkboxes when no refund is present can cause
    # formula cascade issues (the worksheet's conditional logic short-
    # circuits differently when the checkboxes are pre-set).
    has_state_refund = any(
        g.state_tax_refund for g in scenario.form1099_g
    )
    if has_state_refund:
        # Prior-year itemized deduction amount (Sch 1, Line 1 (SALT)
        # worksheet cell J45).
        if (config.prior_year_itemized
                and config.prior_year_itemized_deduction_amount):
            flat["prior_year_itemized_deduction"] = (
                config.prior_year_itemized_deduction_amount
            )

        # The SALT worksheet has its own filing-status checkboxes
        # (P6/P8/P10/P12/P14) NOT linked to the main 1040 named ranges.
        salt_status_key = {
            "single": "salt_filing_status_single",
            "married_jointly": "salt_filing_status_mfj",
            "married_separately": "salt_filing_status_mfs",
            "head_of_household": "salt_filing_status_hoh",
            "qualifying_widow": "salt_filing_status_qw",
        }.get(config.filing_status)
        if salt_status_key:
            flat[salt_status_key] = "X"


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

    # 8582 Part IV slot A: Sch E Part I net income/loss for first rental
    # property (v1 scope: single property). Income and loss are separate
    # positive-amount cells on the form (columns N and R).
    if scenario.rental_properties:
        prop = scenario.rental_properties[0]
        total_expenses = sum(
            getattr(prop, attr) for attr, _ in _RENTAL_EXPENSE_FIELDS
        )
        net = prop.rents_received - total_expenses
        if net > 0:
            flat["sche_8582_net_income"] = round(net)
        elif net < 0:
            flat["sche_8582_net_loss"] = round(-net)


# Form 8949 box routing.
# Short-term (Part I):  A = 1099-B + basis reported; B = 1099-B + basis not reported.
# Long-term  (Part II): D = 1099-B + basis reported; E = 1099-B + basis not reported.
# Boxes C / F ("no 1099-B received") are out of scope: Form1099B represents
# a received 1099-B by definition.
_BOX_KEYS = {
    (True,  True):  "box_a",
    (True,  False): "box_b",
    (False, True):  "box_d",
    (False, False): "box_e",
}

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
            # acknowledges_no_more_than_four_k1s=False raises at compute time.
            break
        letter = _K1_ROW_LETTERS[i]
        for attr, key in _K1_FIELD_KEYS:
            value = getattr(k1, attr)
            if value:
                flat[f"k1_{letter}_{key}"] = value
        # Entity-type checkbox (mutually exclusive):
        flat[f"k1_{letter}_entity_type_{k1.entity_type.value}"] = "X"

        # Aggregate K-1 income fields into the passive/nonpassive columns
        # that Sch E Part II expects (columns g-k on the form). Ordinary
        # business income + net rental + royalties + other income are summed
        # per row; the total is routed to passive or nonpassive based on
        # material_participation.
        total_row = round(
            k1.ordinary_business_income
            + k1.net_rental_real_estate + k1.other_net_rental
            + k1.royalties + k1.other_income,
        )
        if k1.material_participation:
            if total_row >= 0:
                flat[f"k1_{letter}_nonpassive_income"] = total_row
            else:
                flat[f"k1_{letter}_nonpassive_loss"] = -total_row
        else:
            if total_row >= 0:
                flat[f"k1_{letter}_passive_income"] = total_row
            else:
                flat[f"k1_{letter}_passive_loss"] = -total_row

        # 8582 Part IV slots B-E: K-1 passive rental real estate income/loss.
        # Only passive K-1s (material_participation=False) with net_rental_real_estate
        # contribute to 8582 Part IV. Income and loss are separate positive-amount
        # cells (columns N and R); prior-year carryforward goes in column V.
        if not k1.material_participation and k1.net_rental_real_estate:
            nre = k1.net_rental_real_estate
            if nre > 0:
                flat[f"k1_{letter}_8582_net_income"] = round(nre)
            else:
                flat[f"k1_{letter}_8582_net_loss"] = round(-nre)
        if not k1.material_participation and k1.prior_year_passive_loss_carryforward:
            flat[f"k1_{letter}_8582_prior_year_loss"] = round(
                k1.prior_year_passive_loss_carryforward
            )


def _flatten_1099_b(scenario: Scenario, flat: dict[str, object]) -> None:
    """Populate per-lot 8949 row slots, enumerated 1..N per subsection box."""
    box_counters: dict[str, int] = {}
    for lot in scenario.form1099_b:
        box = _BOX_KEYS[(lot.short_term, lot.basis_reported_to_irs)]
        idx = box_counters.get(box, 0) + 1
        box_counters[box] = idx
        # Mark the box checkbox the first time we see a lot for this box.
        if idx == 1:
            flat[f"f8949_{box}_checkbox"] = "X"
        prefix = f"f8949_{box}_lot_{idx}"
        flat[f"{prefix}_description"] = lot.description
        flat[f"{prefix}_date_acquired"] = lot.date_acquired
        flat[f"{prefix}_date_sold"] = lot.date_sold
        flat[f"{prefix}_proceeds"] = lot.proceeds
        flat[f"{prefix}_basis"] = lot.cost_basis
        # Wash sale (code W) wins over other basis adjustment (code O);
        # combined adjustments on a single lot are caught at compute-time.
        if lot.wash_sale_loss_disallowed:
            flat[f"{prefix}_adjustment_code"] = "W"
            flat[f"{prefix}_adjustment_amount"] = lot.wash_sale_loss_disallowed
        elif lot.other_basis_adjustment:
            flat[f"{prefix}_adjustment_code"] = "O"
            flat[f"{prefix}_adjustment_amount"] = lot.other_basis_adjustment
        # 28%-rate / §1250 tags propagate for Sch D to aggregate; not
        # separate XLS inputs of their own.
        if lot.is_28_rate_collectible:
            flat[f"{prefix}_is_28_rate"] = "X"
        if lot.is_section_1250:
            flat[f"{prefix}_is_section_1250"] = "X"


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
