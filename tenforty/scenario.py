import dataclasses
import datetime
import difflib
from pathlib import Path

import pypdf
import yaml

from tenforty import attestations as _attestations
from tenforty.attestations import validate_load_time
from tenforty.ca_divergences import (
    materialize_user_divergence,
    resolve_divergence_id,
)
from tenforty.params.federal import load as load_federal_params
from tenforty.filing.statement_other_deductions import (
    other_deductions_footing_problem,
)
from tenforty.models import (
    OtherDeductionComponent,
    validate_sche_1099_answers,
    validate_third_party_designee,
    validate_tax_year_dates,
    validate_unclaimed_property,
    AccountingMethod,
    Address,
    CA540Return,
    DepreciableAsset,
    DepreciationOverride,
    EicEligibility,
    EicPersonFacts,
    parse_filing_status,
    EntityType,
    FilingStatus,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    LivedTogetherPeriod,
    SeparationDecreeKind,
    Form1095A,
    Form3115,
    Form3115Asset,
    Form1095AMonth,
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    ItemizedDeductions,
    RentalProperty,
    SCorpCAInputs,
    SCorpDeductions,
    SCorpIncome,
    SCorpPayments,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpScopeOuts,
    SCorpShareholder,
    Scenario,
    ScheduleCBusiness,
    ScheduleK1,
    SourceDocument,
    TaxReturnConfig,
    VoluntaryContribution,
    W2,
    _MONTH_KEYS,
)

_FORM_REGISTRY: dict[str, tuple[type, str]] = {
    "w2s": (W2, "w2s"),
    "form1099_int": (Form1099INT, "form1099_int"),
    "form1099_div": (Form1099DIV, "form1099_div"),
    "form1099_b": (Form1099B, "form1099_b"),
    "form1099_g": (Form1099G, "form1099_g"),
    "form1098s": (Form1098, "form1098s"),
    "schedule_k1s": (ScheduleK1, "schedule_k1s"),
}

# Activities that can hold nested `depreciable_assets:` / a
# `depreciation_override:` block. Built by `_load_depreciation_activity`
# rather than a bare `model_cls(**item)` so the nested mappings become models
# and unknown nested keys fail closed.
_DEPRECIATION_ACTIVITY_REGISTRY: dict[str, type] = {
    "rental_properties": RentalProperty,
    "schedule_c_businesses": ScheduleCBusiness,
}

_KNOWN_DEPRECIABLE_ASSET_KEYS: frozenset[str] = frozenset({
    "description", "date_placed_in_service", "basis", "recovery_class",
    "disposed", "prior_depreciation", "no_bonus_or_section_179_history",
    "acknowledges_prior_depreciation_as_stated",
    "convention", "quarter",
})
_REQUIRED_DEPRECIABLE_ASSET_KEYS: tuple[str, ...] = (
    "description", "date_placed_in_service", "basis", "recovery_class")
_KNOWN_DEPRECIATION_OVERRIDE_KEYS: frozenset[str] = frozenset(
    {"amount", "restates_engine_amount", "acknowledgment"})
_REQUIRED_DEPRECIATION_OVERRIDE_KEYS: tuple[str, ...] = (
    "amount", "restates_engine_amount")

# Amount fields on ScheduleCBusiness that are carried through verbatim (never
# computed or clamped): gross receipts, every Part II expense category, and the
# UNMODELED-feature amount fields. A negative value on any of them is refused at
# load rather than silently corrected to 0 -- mirroring the estimated-tax and
# SE-health negative-amount refusals below. `description` (str) and
# `statutory_employee` (bool) are not amounts and are excluded.
_SCHEDULE_C_AMOUNT_FIELDS: tuple[str, ...] = (
    "gross_receipts",
    "advertising", "insurance", "legal_professional", "office_expense",
    "rent_lease", "supplies", "taxes_licenses", "travel", "deductible_meals",
    "utilities", "wages", "other_expenses",
    "cost_of_goods_sold", "inventory", "depreciation", "home_office",
    "vehicle_expenses", "depletion", "returns_and_allowances",
)

# Every top-level YAML key the loader recognizes. The loader is fail-closed:
# any key outside this set raises rather than being silently dropped (a
# dropped `itemized_deductions:` block is how a filed-return reconciliation
# first surfaced this gap — a typo must not vanish without a sound).
_MID_QUARTER_ACK_KEY = (
    "acknowledges_no_personal_property_behind_stated_depreciation")

_LISTED_PROPERTY_ACK_KEY = "acknowledges_no_listed_property"
_SCHEDULE_3_ACK_KEY = "acknowledges_schedule_3_not_produced"

_KNOWN_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"config", "s_corp_return", "ca540", "itemized_deductions", "form_1095a",
     _attestations.FORM_3115_KEY,
     _MID_QUARTER_ACK_KEY, _LISTED_PROPERTY_ACK_KEY, _SCHEDULE_3_ACK_KEY,
     "positions", "eic_eligibility"}
    | set(_FORM_REGISTRY) | set(_DEPRECIATION_ACTIVITY_REGISTRY)
)

# Keys recognized inside the form_1095a block and inside each month row.
_KNOWN_FORM_1095A_KEYS: frozenset[str] = frozenset(
    {"months", "received_unemployment_2021", "tax_exempt_interest"})
_KNOWN_FORM_1095A_MONTH_KEYS: frozenset[str] = frozenset(
    {"premium", "slcsp", "aptc"})


def _coerce_date(value) -> datetime.date:
    """PyYAML returns `datetime.date` for unquoted ISO dates and `str`
    for quoted ones; normalize both to `datetime.date`."""
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def _load_positions(data):
    """The top-level `positions:` block. An empty `positions:` (YAML null)
    means no elections; every other value goes to the Scenario as written,
    where anything but a mapping of slug to choice is refused."""
    raw = data.get("positions", {})
    return {} if raw is None else raw


def _load_stated_bool(value, where: str) -> bool:
    """A stated true/false. Strings are refused, never coerced: a quoted
    "no" is truthy."""
    if not isinstance(value, bool):
        raise ValueError(f"{where} must be true or false; got {value!r}")
    return value


def _load_stated_number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a number; got {value!r}")
    return float(value)


def _load_stated_int(value, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} must be a whole number; got {value!r}")
    return value


def _load_stated_text(value, where: str) -> str:
    """A stated text cell, printed exactly as written. Only a string is
    accepted: an unquoted YAML scalar that looks like a number has already
    been rewritten by the time it arrives (`00.11` is 0.11, `57.00` is 57.0,
    `0115550100` is an octal integer), so it is refused, never stringified."""
    if not isinstance(value, str):
        raise ValueError(
            f"{where} must be quoted text; got {value!r}. YAML reads an "
            f"unquoted number as a number and drops its leading and trailing "
            f"zeros (00.11 loads as 0.11), so put the value in quotes.")
    return value


def _load_stated_date(value, where: str) -> datetime.date:
    try:
        return _coerce_date(value)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"{where} must be a date (YYYY-MM-DD); got {value!r}") from e


_FORM_3115_COLUMN_LOADERS = {
    bool: _load_stated_bool,
    int: _load_stated_int,
    float: _load_stated_number,
    str: _load_stated_text,
    datetime.date: _load_stated_date,
}
# Fields whose statement may be an explicit null (see Form3115).
_FORM_3115_NULLABLE: frozenset[str] = frozenset({
    "principal_business_activity_code",
    "lived_in_residential_rental_before_renting",
})
_FORM_3115_FIELD_TYPES: dict[str, type] = {
    "year_of_change": int, "designated_change_number": int,
    "section_481a_adjustment": float,
    "tax_year_begins": datetime.date, "tax_year_ends": datetime.date,
    "principal_business_activity_code": str, "contact_person": str,
    "contact_phone": str, "applicant_type": str, "type_of_change": str,
}
_FORM_3115_ASSET_FIELD_TYPES: dict[str, type] = {
    "date_placed_in_service": datetime.date,
    "unadjusted_basis": float, "depreciation_claimed_present_method": float,
    "special_depreciation_allowance_claimed": bool,
}


def _load_form_3115_fields(
        data: dict, keys, types: dict, default: type, where: str) -> dict:
    out = {}
    for key in keys:
        value = data[key]
        if value is None and key in _FORM_3115_NULLABLE:
            out[key] = None
            continue
        loader = _FORM_3115_COLUMN_LOADERS[types.get(key, default)]
        out[key] = loader(value, f"{where}.{key}")
    return out


def _load_form_3115(data) -> Form3115 | None:
    """Build Form3115 from the `form_3115:` block. Shape -- a mapping, no
    unknown key, no missing key, `assets` a list of mappings -- is the parse
    ledger's (`attestations._FORM_3115_REFUSALS`), which has already run;
    this types each stated value, refusing rather than coercing."""
    if data is None:
        return None
    block_keys = [
        k for k in _attestations.FORM_3115_BLOCK_KEYS if k != "assets"]
    fields = _load_form_3115_fields(
        data, block_keys, _FORM_3115_FIELD_TYPES, bool, "form_3115")
    assets = tuple(
        Form3115Asset(**_load_form_3115_fields(
            row, _attestations.FORM_3115_ASSET_KEYS,
            _FORM_3115_ASSET_FIELD_TYPES, str, f"form_3115.assets[{i}]"))
        for i, row in enumerate(data["assets"]))
    return Form3115(**fields, assets=assets)


def _load_depreciable_asset(data, where: str) -> DepreciableAsset:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be a mapping; got {data!r}")
    unknown = set(data) - _KNOWN_DEPRECIABLE_ASSET_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in {where}: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_DEPRECIABLE_ASSET_KEYS)}")
    missing = [k for k in _REQUIRED_DEPRECIABLE_ASSET_KEYS if k not in data]
    if missing:
        raise ValueError(f"{where} is missing {missing}")
    disposed = data.get("disposed")
    prior = data.get("prior_depreciation")
    history = data.get("no_bonus_or_section_179_history")
    # Carried as stated; whether the values are usable, and whether this
    # asset may state them at all, is the refusal ledger's business.
    convention = data.get("convention")
    if convention is not None and not isinstance(convention, str):
        raise ValueError(
            f"{where}.convention must be text; got {convention!r}")
    quarter = data.get("quarter")
    if quarter is not None and (
            isinstance(quarter, bool) or not isinstance(quarter, int)):
        raise ValueError(
            f"{where}.quarter must be a whole number; got {quarter!r}")
    return DepreciableAsset(
        description=str(data["description"]),
        date_placed_in_service=_coerce_date(data["date_placed_in_service"]),
        basis=_load_stated_number(data["basis"], f"{where}.basis"),
        recovery_class=str(data["recovery_class"]),
        disposed=None if disposed is None else _coerce_date(disposed),
        prior_depreciation=(
            None if prior is None else _load_stated_number(
                prior, f"{where}.prior_depreciation")),
        no_bonus_or_section_179_history=(
            None if history is None else _load_stated_bool(
                history, f"{where}.no_bonus_or_section_179_history")),
        acknowledges_prior_depreciation_as_stated=_load_stated_bool(
            data.get("acknowledges_prior_depreciation_as_stated", False),
            f"{where}.acknowledges_prior_depreciation_as_stated"),
        convention=convention,
        quarter=quarter,
    )


def _load_depreciation_override(data, where: str) -> DepreciationOverride:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be a mapping; got {data!r}")
    unknown = set(data) - _KNOWN_DEPRECIATION_OVERRIDE_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in {where}: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_DEPRECIATION_OVERRIDE_KEYS)}")
    missing = [
        k for k in _REQUIRED_DEPRECIATION_OVERRIDE_KEYS if k not in data]
    if missing:
        raise ValueError(f"{where} is missing {missing}")
    return DepreciationOverride(
        amount=_load_stated_number(data["amount"], f"{where}.amount"),
        restates_engine_amount=_load_stated_number(
            data["restates_engine_amount"],
            f"{where}.restates_engine_amount"),
        acknowledgment=_load_stated_bool(
            data.get("acknowledgment", False), f"{where}.acknowledgment"),
    )


def _load_depreciation_activity(model_cls: type, item: dict, where: str):
    """Build a RentalProperty / ScheduleCBusiness, turning its nested
    `depreciable_assets` and `depreciation_override` mappings into models."""
    fields = dict(item)
    raw_assets = fields.pop("depreciable_assets", None) or []
    if not isinstance(raw_assets, list):
        raise ValueError(
            f"{where}.depreciable_assets must be a list; got {raw_assets!r}")
    assets = [
        _load_depreciable_asset(a, f"{where}.depreciable_assets[{i}]")
        for i, a in enumerate(raw_assets)]
    raw_override = fields.pop("depreciation_override", None)
    override = (
        None if raw_override is None else _load_depreciation_override(
            raw_override, f"{where}.depreciation_override"))
    ack_key = "acknowledges_depreciation_stated_outside_macrs"
    if ack_key in fields:
        fields[ack_key] = _load_stated_bool(
            fields[ack_key], f"{where}.{ack_key}")
    # ScheduleCBusiness is frozen and holds a tuple; RentalProperty a list.
    container = tuple if model_cls is ScheduleCBusiness else list
    return model_cls(
        **fields, depreciable_assets=container(assets),
        depreciation_override=override)


def _load_address(data: dict) -> Address:
    return Address(
        street=data["street"],
        city=data["city"],
        state=data["state"],
        zip_code=data["zip_code"],
    )


# The three pre-redesign Schedule B booleans. Their names did not match the
# questions they were wired to (line 3, 4a, 4b), so they are REMOVED rather than
# aliased: a scenario that still carries one must fail loudly, never be ignored.
_RETIRED_SCHEDULE_B_KEYS: dict[str, str] = {
    "has_any_foreign_shareholders":
        "shareholder_disregarded_entity_trust_estate_or_nominee (line 3)",
    "any_c_corp_subsidiaries":
        "owns_20pct_stock_of_any_corporation (line 4a)",
    "owns_foreign_entity":
        "owns_20pct_interest_in_partnership_or_trust (line 4b)",
}

# Optional Yes/No answer fields (None/absent = unstated), by dataclass name.
_SCHEDULE_B_BOOL_FIELDS: tuple[str, ...] = (
    "shareholder_disregarded_entity_trust_estate_or_nominee",
    "owns_20pct_stock_of_any_corporation",
    "owns_20pct_interest_in_partnership_or_trust",
    "restricted_stock_outstanding",
    "stock_options_or_warrants_outstanding",
    "filed_form_8918",
    "issued_oid_debt_instruments",
    "section_163j_election",
    "form_8990_conditions_met",
    "receipts_and_assets_under_250k",
    "nonshareholder_debt_canceled",
    "qsub_election_terminated",
    "payments_requiring_1099s",
    "filed_required_1099s",
    "qualified_opportunity_fund",
    "digital_asset_transactions",
)


def _load_schedule_b_answers(data: dict) -> SCorpScheduleBAnswers:
    retired = sorted(k for k in _RETIRED_SCHEDULE_B_KEYS if k in data)
    if retired:
        raise ValueError(
            "s_corp_return.schedule_b_answers carries retired key(s) "
            + ", ".join(retired) + ". Those three booleans were wired to "
            "Schedule B lines 3, 4a and 4b under names that did not match the "
            "questions, so they no longer exist. Replace: "
            + "; ".join(f"{k} -> {_RETIRED_SCHEDULE_B_KEYS[k]}"
                        for k in retired) + ".")
    answers: dict[str, object] = {}
    for name in _SCHEDULE_B_BOOL_FIELDS:
        value = data.get(name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(
                f"s_corp_return.schedule_b_answers.{name} must be true, false, "
                f"or null (unstated); got {value!r}")
        answers[name] = value
    built_in_gain = data.get("net_unrealized_built_in_gain")
    if built_in_gain is not None:
        if isinstance(built_in_gain, bool) or not isinstance(
                built_in_gain, (int, float)):
            raise ValueError(
                "s_corp_return.schedule_b_answers.net_unrealized_built_in_gain "
                f"must be a number or null (blank); got {built_in_gain!r}")
        built_in_gain = float(built_in_gain)
    return SCorpScheduleBAnswers(
        accounting_method=AccountingMethod(data["accounting_method"]),
        business_activity_code=data["business_activity_code"],
        business_activity_description=data["business_activity_description"],
        product_or_service=data["product_or_service"],
        net_unrealized_built_in_gain=built_in_gain,
        **answers,
    )


def _load_income(data: dict) -> SCorpIncome:
    return SCorpIncome(
        gross_receipts=float(data["gross_receipts"]),
        returns_and_allowances=float(data["returns_and_allowances"]),
        cogs_aggregate=float(data["cogs_aggregate"]),
        net_gain_loss_4797=float(data["net_gain_loss_4797"]),
        other_income=float(data["other_income"]),
    )


_KNOWN_OTHER_DEDUCTION_COMPONENT_KEYS: frozenset[str] = frozenset(
    {"description", "amount"})


def _load_other_deductions_components(
        data, other_deductions: float) -> list[OtherDeductionComponent]:
    """Parse ``s_corp_return.deductions.other_deductions_components``
    fail-closed, and enforce the footing rule against ``other_deductions``."""
    where = "s_corp_return.deductions.other_deductions_components"
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{where} must be a list of "
                         f"{{description, amount}} rows; got {data!r}")
    comps: list[OtherDeductionComponent] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(f"{where}[{i}] must be a mapping; got {row!r}")
        unknown = set(row) - _KNOWN_OTHER_DEDUCTION_COMPONENT_KEYS
        if unknown:
            raise ValueError(
                f"Unknown key(s) in {where}[{i}]: {sorted(unknown)}. "
                f"Known keys: {sorted(_KNOWN_OTHER_DEDUCTION_COMPONENT_KEYS)}")
        missing = _KNOWN_OTHER_DEDUCTION_COMPONENT_KEYS - set(row)
        if missing:
            raise ValueError(f"{where}[{i}] is missing {sorted(missing)}")
        desc, amount = row["description"], row["amount"]
        if not isinstance(desc, str) or not desc.strip():
            raise ValueError(
                f"{where}[{i}].description must be a non-blank string")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError(
                f"{where}[{i}].amount must be a number; got {amount!r}")
        comps.append(OtherDeductionComponent(desc.strip(), float(amount)))
    problem = other_deductions_footing_problem(comps, other_deductions)
    if problem:
        raise ValueError(problem)
    return comps


def _load_deductions(data: dict) -> SCorpDeductions:
    other = float(data["other_deductions"])
    return SCorpDeductions(
        compensation_of_officers=float(data["compensation_of_officers"]),
        salaries_wages=float(data["salaries_wages"]),
        repairs_maintenance=float(data["repairs_maintenance"]),
        bad_debts=float(data["bad_debts"]),
        rents=float(data["rents"]),
        taxes_licenses=float(data["taxes_licenses"]),
        interest=float(data["interest"]),
        depreciation=float(data["depreciation"]),
        depletion=float(data["depletion"]),
        advertising=float(data["advertising"]),
        pension_profit_sharing_plans=float(data["pension_profit_sharing_plans"]),
        employee_benefits=float(data["employee_benefits"]),
        other_deductions=other,
        energy_efficient_buildings_deduction=float(
            data.get("energy_efficient_buildings_deduction", 0.0)),
        other_deductions_components=_load_other_deductions_components(
            data.get("other_deductions_components"), other),
    )


def _load_scope_outs(data: dict) -> SCorpScopeOuts:
    return SCorpScopeOuts(
        net_passive_income_tax=float(data.get("net_passive_income_tax", 0.0)),
        built_in_gains_tax=float(data.get("built_in_gains_tax", 0.0)),
        interest_on_453_deferred=float(data.get("interest_on_453_deferred", 0.0)),
    )


def _load_payments(data: dict) -> SCorpPayments:
    return SCorpPayments(
        estimated_tax_payments=float(data.get("estimated_tax_payments", 0.0)),
        prior_year_overpayment_credited=float(
            data.get("prior_year_overpayment_credited", 0.0)
        ),
        tax_deposited_with_7004=float(data.get("tax_deposited_with_7004", 0.0)),
        credit_for_federal_excise_tax=float(
            data.get("credit_for_federal_excise_tax", 0.0)
        ),
        refundable_credits=float(data.get("refundable_credits", 0.0)),
    )


_KNOWN_SCORP_CA_KEYS: frozenset[str] = frozenset({
    "first_year", "estimated_tax_payments", "prior_year_overpayment_applied",
    "state_tax_deducted_federally", "depreciation_adjustment",
    "apportionment_ca_only", "under_irs_audit", "information_returns_filed",
    "state_of_incorporation", "country_of_incorporation",
    "corporation_number", "max_shareholders", "date_business_began_in_ca",
    "water_edge_basis", "includes_qsubs", "included_reportable_transaction",
    "filed_federal_schedule_m3", "ftb_3544_attached",
    "inactive_business", "discuss_with_preparer",
    "filed_unclaimed_property_report",
    "unclaimed_property_report_date", "unclaimed_property_amount_remitted",
})


_INFORMATION_RETURNS_ANSWERS = ("yes", "no", "not_applicable")


def _load_optional_bool(value, name: str) -> bool | None:
    """A stated Yes/No answer (None/absent = unstated). Strings are refused,
    not coerced: "no" is truthy."""
    if value is not None and not isinstance(value, bool):
        raise ValueError(
            f"{name} (under s_corp_return) must be true, false, or null "
            f"(unstated); got {value!r}")
    return value


def _load_state_abbreviation(value) -> str | None:
    if value is None:
        return None
    if not (isinstance(value, str) and len(value) == 2 and value.isalpha()):
        raise ValueError(
            "s_corp_return.ca.state_of_incorporation must be a two-letter "
            f"abbreviation or null (unstated); got {value!r}")
    return value.upper()


def _load_information_returns_filed(value) -> str | None:
    if value is not None and value not in _INFORMATION_RETURNS_ANSWERS:
        raise ValueError(
            "s_corp_return.ca.information_returns_filed must be one of "
            f"{list(_INFORMATION_RETURNS_ANSWERS)} or null (unstated); "
            f"got {value!r}")
    return value


def _load_scorp_ca(data: dict | None) -> SCorpCAInputs | None:
    """Parse the optional ``s_corp_return.ca`` block fail-closed: an unknown
    key raises ValueError (mirroring the top-level loader) rather than being
    silently dropped, and non-100%-CA apportionment raises at load (v1 scope)."""
    if data is None:
        return None
    unknown = set(data) - _KNOWN_SCORP_CA_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in s_corp_return.ca: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_SCORP_CA_KEYS)}")
    required = (
        "first_year", "estimated_tax_payments",
        "prior_year_overpayment_applied", "state_tax_deducted_federally",
        "depreciation_adjustment", "apportionment_ca_only",
    )
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(
            f"CA S-corp inputs missing required key(s): {sorted(missing)}")
    inputs = SCorpCAInputs(
        first_year=bool(data["first_year"]),
        estimated_tax_payments=float(data["estimated_tax_payments"]),
        prior_year_overpayment_applied=float(
            data["prior_year_overpayment_applied"]),
        state_tax_deducted_federally=float(data["state_tax_deducted_federally"]),
        depreciation_adjustment=float(data["depreciation_adjustment"]),
        apportionment_ca_only=bool(data["apportionment_ca_only"]),
        under_irs_audit=_load_optional_bool(
            data.get("under_irs_audit"), "under_irs_audit"),
        information_returns_filed=_load_information_returns_filed(
            data.get("information_returns_filed")),
        state_of_incorporation=_load_state_abbreviation(
            data.get("state_of_incorporation")),
        max_shareholders=_load_positive_int(
            data.get("max_shareholders"), "max_shareholders"),
        date_business_began_in_ca=_load_optional_date(
            data.get("date_business_began_in_ca"), "date_business_began_in_ca"),
        water_edge_basis=_load_optional_bool(
            data.get("water_edge_basis"), "water_edge_basis"),
        includes_qsubs=_load_optional_bool(
            data.get("includes_qsubs"), "includes_qsubs"),
        included_reportable_transaction=_load_optional_bool(
            data.get("included_reportable_transaction"),
            "included_reportable_transaction"),
        filed_federal_schedule_m3=_load_optional_bool(
            data.get("filed_federal_schedule_m3"), "filed_federal_schedule_m3"),
        ftb_3544_attached=_load_optional_bool(
            data.get("ftb_3544_attached"), "ftb_3544_attached"),
        inactive_business=_load_optional_bool(
            data.get("inactive_business"), "inactive_business"),
        discuss_with_preparer=_load_optional_bool(
            data.get("discuss_with_preparer"), "discuss_with_preparer"),
        filed_unclaimed_property_report=_load_optional_bool(
            data.get("filed_unclaimed_property_report"),
            "filed_unclaimed_property_report"),
        unclaimed_property_report_date=data.get("unclaimed_property_report_date"),
        unclaimed_property_amount_remitted=(
            None if data.get("unclaimed_property_amount_remitted") is None
            else data["unclaimed_property_amount_remitted"]),
        corporation_number=_load_corporation_number(
            data.get("corporation_number")),
        country_of_incorporation=_load_optional_text(
            data.get("country_of_incorporation"), "ca.country_of_incorporation"),
    )
    validate_unclaimed_property(inputs)
    if not inputs.apportionment_ca_only:
        raise ValueError(
            "CA S-corp v1 supports only 100% California apportionment "
            "(s_corp_return.ca.apportionment_ca_only must be true).")
    return inputs


_KNOWN_SCORP_KEYS: frozenset[str] = frozenset({
    "name", "ein", "address", "date_incorporated", "s_election_effective_date",
    "total_assets", "income", "deductions", "schedule_b_answers", "shareholders",
    "scope_outs", "payments", "ca", "amended_return", "irs_center",
    "total_shares_beginning", "total_shares_end",
    "distributions_to_shareholders", "officer_title",
    "discuss_with_preparer",
    "tax_year_beginning", "tax_year_ending", "electing_s_this_year", "final_return", "name_change", "address_change",
    "s_election_terminated",
})


_KNOWN_SHAREHOLDER_KEYS: frozenset[str] = frozenset({
    "name", "ssn_or_ein", "address", "ownership_percentage",
    "shares_beginning", "shares_end", "loans_beginning", "loans_end",
    "final_k1", "ca_resident", "ca_entity_type",
})

CA_K1_ENTITY_TYPES = (
    "individual", "estate_trust", "qualified_exempt_organization",
    "single_member_llc")


def _load_optional_text(value, name: str) -> str | None:
    """A stated free-text entry (None/absent = unstated)."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"s_corp_return.{name} must be a non-empty string or null "
            f"(unstated); got {value!r}")
    return value


def _load_stated_amount(sh: dict, key: str, *, non_negative: bool) -> float | None:
    """A stated shareholder figure (None/absent = unstated). Bools and strings
    are refused rather than coerced: a typo must not print a wrong face item."""
    value = sh.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"s_corp_return.{key} (or shareholders[].{key}) must be a number or null "
            f"(unstated); got {value!r}")
    if non_negative and value < 0:
        raise ValueError(
            f"s_corp_return.{key} (or shareholders[].{key}) must not be negative; "
            f"got {value!r}")
    return float(value)


def _load_tax_year_date(value, name: str):
    """A short-year header date: a YAML date or an ISO ``YYYY-MM-DD`` string.
    (mm/dd/yyyy strings are refused to keep one unambiguous input format.)"""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        raise ValueError(f"s_corp_return.{name} must be a date, not a datetime")
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(
        f"s_corp_return.{name} must be an ISO date (YYYY-MM-DD) or null; "
        f"got {value!r}")


def _load_distributions(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or value < 0:
        raise ValueError(
            "s_corp_return.distributions_to_shareholders must be a "
            f"non-negative number; got {value!r}")
    return float(value)


def _load_ca_entity_type(value) -> str | None:
    if value is not None and value not in CA_K1_ENTITY_TYPES:
        raise ValueError(
            "s_corp_return.shareholders[].ca_entity_type must be one of "
            f"{list(CA_K1_ENTITY_TYPES)} or null (unstated); got {value!r}")
    return value


def _load_positive_int(value, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            f"s_corp_return.ca.{name} must be a positive whole number or null "
            f"(unstated); got {value!r}")
    return value


def _load_optional_date(value, name: str):
    if value is None:
        return None
    try:
        return _coerce_date(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"s_corp_return.ca.{name} must be an ISO date (YYYY-MM-DD) or "
            f"null (unstated); got {value!r}") from None


def _load_corporation_number(value) -> str | None:
    """Digits only, as a STRING (a YAML integer would drop leading zeros)."""
    if value is None:
        return None
    if not (isinstance(value, str) and value.isdigit() and len(value) <= 12):
        raise ValueError(
            "s_corp_return.ca.corporation_number must be a string of 1-12 "
            "digits (7-digit CA corporation number or 12-digit Secretary of "
            f"State file number; quote it in YAML) or null; got {value!r}")
    return value


def _load_shareholder(sh: dict) -> SCorpShareholder:
    unknown = set(sh) - _KNOWN_SHAREHOLDER_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in s_corp_return.shareholders[]: "
            f"{sorted(unknown)}. Known keys: {sorted(_KNOWN_SHAREHOLDER_KEYS)}")
    final_k1 = sh.get("final_k1", False)
    if not isinstance(final_k1, bool):
        raise ValueError(
            "s_corp_return.shareholders[].final_k1 must be true or false; "
            f"got {final_k1!r}")
    return SCorpShareholder(
        name=sh["name"],
        ssn_or_ein=sh["ssn_or_ein"],
        address=_load_address(sh["address"]),
        ownership_percentage=float(sh["ownership_percentage"]),
        shares_beginning=_load_stated_amount(
            sh, "shares_beginning", non_negative=True),
        shares_end=_load_stated_amount(sh, "shares_end", non_negative=True),
        # A loan balance is a dollar amount; signed values are the filer's call.
        loans_beginning=_load_stated_amount(
            sh, "loans_beginning", non_negative=False),
        loans_end=_load_stated_amount(sh, "loans_end", non_negative=False),
        final_k1=final_k1,
        ca_resident=_load_optional_bool(sh.get("ca_resident"), "ca_resident"),
        ca_entity_type=_load_ca_entity_type(sh.get("ca_entity_type")),
    )


def _load_s_corp_return(data: dict | None) -> SCorpReturn | None:
    """Build SCorpReturn from a YAML-parsed dict. Each section uses an
    explicit-field-names loader (not `**` dict-spread) so a typoed YAML
    key fails with a clear `KeyError: <field>` rather than the implicit
    `TypeError: unexpected keyword argument` from dataclass construction.

    An unknown sibling key fails closed with ValueError (mirroring the
    top-level and ``s_corp_return.ca`` loaders) rather than being silently
    dropped — a typoed ``amend_return`` must not slip an unmarked return past."""
    if data is None:
        return None
    unknown = set(data) - _KNOWN_SCORP_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in s_corp_return: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_SCORP_KEYS)}")
    return SCorpReturn(
        name=data["name"],
        ein=data["ein"],
        address=_load_address(data["address"]),
        date_incorporated=_coerce_date(data["date_incorporated"]),
        s_election_effective_date=_coerce_date(data["s_election_effective_date"]),
        total_assets=float(data["total_assets"]),
        income=_load_income(data["income"]),
        deductions=_load_deductions(data["deductions"]),
        schedule_b_answers=_load_schedule_b_answers(data["schedule_b_answers"]),
        shareholders=[_load_shareholder(sh) for sh in data.get("shareholders", [])],
        scope_outs=_load_scope_outs(data.get("scope_outs", {})),
        payments=_load_payments(data.get("payments", {})),
        ca=_load_scorp_ca(data.get("ca")),
        amended_return=bool(data.get("amended_return", False)),
        irs_center=_load_optional_text(data.get("irs_center"), "irs_center"),
        officer_title=_load_optional_text(
            data.get("officer_title"), "officer_title"),
        discuss_with_preparer=_load_optional_bool(
            data.get("discuss_with_preparer"), "discuss_with_preparer"),
        tax_year_beginning=_load_tax_year_date(
            data.get("tax_year_beginning"), "tax_year_beginning"),
        tax_year_ending=_load_tax_year_date(
            data.get("tax_year_ending"), "tax_year_ending"),
        distributions_to_shareholders=_load_distributions(
            data.get("distributions_to_shareholders")),
        electing_s_this_year=_load_optional_bool(
            data.get("electing_s_this_year"), "electing_s_this_year"),
        final_return=_load_optional_bool(
            data.get("final_return"), "final_return"),
        name_change=_load_optional_bool(
            data.get("name_change"), "name_change"),
        address_change=_load_optional_bool(
            data.get("address_change"), "address_change"),
        s_election_terminated=_load_optional_bool(
            data.get("s_election_terminated"), "s_election_terminated"),
        total_shares_beginning=_load_stated_amount(
            data, "total_shares_beginning", non_negative=True),
        total_shares_end=_load_stated_amount(
            data, "total_shares_end", non_negative=True),
    )


def _load_voluntary_contribution(data: dict) -> VoluntaryContribution:
    return VoluntaryContribution(
        fund_code=data["fund_code"],
        amount=float(data["amount"]),
    )


# Keys recognized inside each id-keyed `divergences` entry (spec §2.2). The
# loader is fail-closed: an unknown key raises rather than silently dropping.
_KNOWN_DIVERGENCE_KEYS: frozenset[str] = frozenset({"id", "amount", "note", "direction"})


def _load_ca_divergence(data: dict, year: int) -> "CASchCAAdjustment":
    """Materialize ONE id-keyed scenario divergence against the ``year`` catalog.

    The user supplies only ``{id, amount, note?}`` (+ ``direction`` for BOTH
    rows); ``resolve_divergence_id`` + ``materialize_user_divergence`` pull the
    column/line/description from the catalog so a user row can never disagree
    with it. Unknown keys, an unknown id, a non-positive amount, and the
    direction-key rules all fail closed (see ``ca_divergences``)."""
    if not isinstance(data, dict) or "id" not in data:
        raise ValueError(
            "Each ca540.divergences entry must be a mapping with an `id` key "
            f"(id-keyed input; got {data!r})."
        )
    unknown = set(data) - _KNOWN_DIVERGENCE_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in ca540 divergence {data['id']!r}: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_DIVERGENCE_KEYS)}")
    if "amount" not in data:
        raise ValueError(
            f"ca540 divergence {data['id']!r} is missing required key `amount`.")
    entry = resolve_divergence_id(year, data["id"])
    adj = materialize_user_divergence(entry, float(data["amount"]), data.get("direction"))
    note = data.get("note")
    if note is not None:
        adj.note = note
    return adj


def _load_ca540(data: dict | None, year: int) -> CA540Return | None:
    if data is None:
        return None

    raw_divergences = data.get("divergences", [])
    seen_ids: set[str] = set()
    divergences: list["CASchCAAdjustment"] = []
    for d in raw_divergences:
        adj = _load_ca_divergence(d, year)
        if adj.catalog_id in seen_ids:
            raise ValueError(
                f"Duplicate ca540 divergence id {adj.catalog_id!r} in "
                f"`divergences` (each catalog id may appear at most once).")
        seen_ids.add(adj.catalog_id)
        divergences.append(adj)

    # Validate EVERY id in the `reviewed` list against the year's catalog too
    # (spec's both-lists requirement) — an unknown id raises with a suggestion.
    reviewed_ids = list(data.get("reviewed", []))
    for rid in reviewed_ids:
        resolve_divergence_id(year, rid)

    interest_and_penalties = data.get("interest_and_penalties")
    if interest_and_penalties is not None:
        interest_and_penalties = float(interest_and_penalties)
        if interest_and_penalties < 0:
            raise ValueError(
                "ca540 `interest_and_penalties` (Form 540 line 112) is "
                f"negative ({interest_and_penalties}). The amount is carried "
                "onto the form verbatim, so a negative value cannot be "
                "silently corrected to 0 — state 0 (filed and paid on time) "
                "or the amount owed.")

    return CA540Return(
        voluntary_contributions=[
            _load_voluntary_contribution(vc)
            for vc in data.get("voluntary_contributions", [])
        ],
        estimated_payments=float(data.get("estimated_payments", 0.0)),
        use_tax=float(data.get("use_tax", 0.0)),
        estimated_tax_penalty=float(data.get("estimated_tax_penalty", 0.0)),
        interest_and_penalties=interest_and_penalties,
        ptet_credit=float(data.get("ptet_credit", 0.0)),
        rrb_tier_1_2_amount=(
            float(data["rrb_tier_1_2_amount"])
            if data.get("rrb_tier_1_2_amount") is not None else None
        ),
        pfl_amount=(
            float(data["pfl_amount"])
            if data.get("pfl_amount") is not None else None
        ),
        divergences=divergences,
        reviewed_divergence_ids=tuple(reviewed_ids),
    )


def _load_form_1095a_month(key: str, data: dict) -> Form1095AMonth:
    unknown = set(data) - _KNOWN_FORM_1095A_MONTH_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in form_1095a.months.{key}: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_FORM_1095A_MONTH_KEYS)}")
    return Form1095AMonth(
        premium=float(data.get("premium", 0.0)),
        slcsp=float(data.get("slcsp", 0.0)),
        aptc=float(data.get("aptc", 0.0)),
    )


_EIC_PERSON_FACTS = tuple(
    f.name for f in dataclasses.fields(EicPersonFacts)
    if f.name != "specified_student_2021")
_EIC_BLOCK_KEYS = frozenset({
    "taxpayer", "spouse", "prior_eic_disallowance_requires_8862",
    "lookback_2019_earned_income"})
# Keys that exist only for tax year 2021 (the ARPA rules).
_EIC_2021_ONLY = ("specified_student_2021", "lookback_2019_earned_income")


def _refuse_unknown_eic_keys(keys, known, where: str) -> None:
    for key in sorted(set(keys) - set(known)):
        close = difflib.get_close_matches(key, sorted(known), n=1)
        hint = f" Did you mean {close[0]!r}?" if close else ""
        raise ValueError(
            f"Unknown key {key!r} in {where}.{hint} Known keys: "
            f"{sorted(known)}")


def _refuse_year_scoped_eic_key(key: str, where: str, year: int) -> None:
    if year != 2021:
        raise ValueError(
            f"year_scoped_eic_fact: {where}.{key} exists only for tax year "
            f"2021 (the American Rescue Plan's one-year earned income credit "
            f"rules); this return is for {year}. Remove it.")


def _load_eic_person(data, where: str, year: int) -> EicPersonFacts:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be a mapping of facts; got {data!r}")
    _refuse_unknown_eic_keys(
        data, _EIC_PERSON_FACTS + ("specified_student_2021",), where)
    missing = [k for k in _EIC_PERSON_FACTS if k not in data]
    if missing:
        raise ValueError(f"{where} is missing fact(s) {missing}: each is a "
                         f"true/false statement about this person.")
    facts = {k: _load_stated_bool(data[k], f"{where}.{k}")
             for k in _EIC_PERSON_FACTS}
    student = data.get("specified_student_2021")
    if "specified_student_2021" in data:
        _refuse_year_scoped_eic_key("specified_student_2021", where, year)
        if student is not None:
            student = _load_stated_bool(student, f"{where}.specified_student_2021")
    return EicPersonFacts(**facts, specified_student_2021=student)


def _load_eic_eligibility(data, config: TaxReturnConfig) -> EicEligibility | None:
    """The top-level `eic_eligibility:` block (childless-EITC spec §4).
    Fail-closed like `form_1095a`: unknown keys (with a did-you-mean),
    missing facts, non-boolean facts, a spouse on a non-joint return (or none
    on a joint one), and the 2021-only keys in any other year all refuse.
    Whether the block is REQUIRED is decided at compute time (forms/eic.py):
    only when the credit would be positive with every fact favorable."""
    if data is None:
        return None
    where = "eic_eligibility"
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be a mapping; got {data!r}")
    _refuse_unknown_eic_keys(data, _EIC_BLOCK_KEYS, where)
    joint = parse_filing_status(config.filing_status) is (
        FilingStatus.MARRIED_FILING_JOINTLY)
    if "taxpayer" not in data:
        raise ValueError(f"{where}.taxpayer is required.")
    if joint and "spouse" not in data:
        raise ValueError(f"{where}.spouse is required on a "
                         f"married_filing_jointly return.")
    if not joint and "spouse" in data:
        raise ValueError(f"{where}.spouse applies only to a "
                         f"married_filing_jointly return.")
    if "prior_eic_disallowance_requires_8862" not in data:
        raise ValueError(f"{where}.prior_eic_disallowance_requires_8862 is "
                         f"required (true/false).")
    lookback = data.get("lookback_2019_earned_income")
    if "lookback_2019_earned_income" in data:
        _refuse_year_scoped_eic_key("lookback_2019_earned_income", where,
                                    config.year)
        if lookback is not None:
            lookback = _load_stated_number(
                lookback, f"{where}.lookback_2019_earned_income")
    return EicEligibility(
        taxpayer=_load_eic_person(data["taxpayer"], f"{where}.taxpayer",
                                  config.year),
        spouse=(_load_eic_person(data["spouse"], f"{where}.spouse",
                                 config.year) if joint else None),
        prior_eic_disallowance_requires_8862=_load_stated_bool(
            data["prior_eic_disallowance_requires_8862"],
            f"{where}.prior_eic_disallowance_requires_8862"),
        lookback_2019_earned_income=lookback)


def _load_form_1095a(data: dict | None, config: TaxReturnConfig) -> Form1095A | None:
    """Build Form1095A from a YAML-parsed dict. Fail-closed like the other
    nested-mapping blocks (`s_corp_return`, `ca540`): unknown sibling keys,
    a `months` map missing any of the twelve jan..dec keys or carrying an
    extra key, and unknown keys inside a month row all raise ValueError
    rather than being silently dropped or defaulted.

    `received_unemployment_2021` is only meaningful for TY2021 (the
    American Rescue Plan's one-year suspension of excess-APTC repayment
    for filers who received unemployment compensation); asserting it True
    for any other year is a scenario-authoring error, not a valid input."""
    if data is None:
        return None
    unknown = set(data) - _KNOWN_FORM_1095A_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in form_1095a: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_FORM_1095A_KEYS)}")

    months_raw = data.get("months")
    if not isinstance(months_raw, dict):
        raise ValueError(
            f"form_1095a.months must be a mapping with keys "
            f"{list(_MONTH_KEYS)}, got {type(months_raw).__name__}")
    missing = [m for m in _MONTH_KEYS if m not in months_raw]
    if missing:
        raise ValueError(
            f"form_1095a.months is missing month(s): {missing}. "
            f"Required keys: {list(_MONTH_KEYS)}")
    extra = set(months_raw) - set(_MONTH_KEYS)
    if extra:
        raise ValueError(
            f"Unknown key(s) in form_1095a.months: {sorted(extra)}. "
            f"Known keys: {list(_MONTH_KEYS)}")

    months = tuple(
        _load_form_1095a_month(m, months_raw[m]) for m in _MONTH_KEYS)

    received_unemployment_2021 = bool(data.get("received_unemployment_2021", False))
    if received_unemployment_2021 and config.year != 2021:
        raise ValueError(
            f"form_1095a.received_unemployment_2021 is only valid for tax "
            f"year 2021 (the American Rescue Plan's one-year suspension of "
            f"excess-APTC repayment); scenario config.year is {config.year}.")

    return Form1095A(
        months=months,
        received_unemployment_2021=received_unemployment_2021,
        tax_exempt_interest=float(data.get("tax_exempt_interest", 0.0)),
    )


_SPOUSE_CONFIG_FIELDS: tuple[str, ...] = (
    "spouse_first_name", "spouse_middle_initial", "spouse_last_name",
    "spouse_ssn")

_NO_SPOUSE_STATUSES = frozenset({
    FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD})


def refuse_spouse_fields_without_spouse(cfg: TaxReturnConfig) -> None:
    """Refuse spouse identity fields on a Single or Head-of-Household scenario.

    Neither return has a spouse block, so a filled spouse field is a
    data-entry error (wrong status, or a stray spouse) that would otherwise be
    silently dropped. Pure decision over ``cfg``; whitespace counts as blank.
    """
    if cfg.filing_status not in _NO_SPOUSE_STATUSES:
        return
    filled = [f for f in _SPOUSE_CONFIG_FIELDS
              if str(getattr(cfg, f) or "").strip()]
    if filled:
        status = FilingStatus(cfg.filing_status).value
        raise ValueError(
            "Scenario config sets "
            + ", ".join(f"`{f}`" for f in filled)
            + f" but `filing_status` is `{status}`, which has no spouse on "
            "the return. Remove the spouse field(s), or set the filing status "
            "the household actually files (e.g. `married_filing_jointly`)."
        )


def validate_w2_owners(cfg: TaxReturnConfig, w2s: list[W2]) -> None:
    """Pure load-time check of each W-2's `owner` against the filing status
    (ruling R-excess-ss).

    A joint return's Social Security maximum is per spouse, so every W-2 of
    a MARRIED_FILING_JOINTLY scenario must say whose it is. On every other
    status `owner` is optional, but `"spouse"` is refused: no spouse W-2
    belongs on a return that is not joint, so it is a data-entry error."""
    status = FilingStatus(cfg.filing_status)
    for i, w2 in enumerate(w2s):
        if status is FilingStatus.MARRIED_FILING_JOINTLY and w2.owner is None:
            raise ValueError(
                f"W-2 #{i + 1} ('{w2.employer}') has no `owner`. `owner` "
                "(`taxpayer` or `spouse`) is required on every W-2 when "
                "`filing_status` is `married_filing_jointly`, because each "
                "spouse's Social Security withholding is checked against "
                "their own maximum.")
        if status is not FilingStatus.MARRIED_FILING_JOINTLY \
                and w2.owner == "spouse":
            raise ValueError(
                f"W-2 #{i + 1} ('{w2.employer}') sets `owner: spouse` but "
                f"`filing_status` is `{status.value}`, which is not a joint "
                "return, so no spouse W-2 belongs on it. Remove the W-2 or "
                "the `owner`, or correct the filing status.")


_SPOUSE_BIRTHDATE_REFUSED = frozenset({
    FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD})


def validate_spouse_birthdate(cfg: TaxReturnConfig) -> None:
    """Pure load-time check of `spouse_birthdate` against the filing status.

    MARRIED_FILING_JOINTLY requires it (the workbook oracle refuses a joint
    return without it); MARRIED_FILING_SEPARATELY accepts it without requiring
    it; SINGLE and HEAD_OF_HOUSEHOLD refuse a non-empty value, because a spouse
    field on an unmarried status is a data-entry error, not something to
    silently ignore. Any non-empty value must be a real ISO YYYY-MM-DD date."""
    value = cfg.spouse_birthdate
    status = cfg.filing_status
    if status in _SPOUSE_BIRTHDATE_REFUSED and value:
        raise ValueError(
            f"Scenario config field `spouse_birthdate` is set ({value!r}) but "
            f"`filing_status` is `{status.value}`, which has no spouse. "
            "Remove it, or correct the filing status.")
    if status is FilingStatus.MARRIED_FILING_JOINTLY and not value:
        raise ValueError(
            "Scenario config field `spouse_birthdate` (ISO YYYY-MM-DD) is "
            "required when `filing_status` is `married_filing_jointly`.")
    if value and not isinstance(value, str):
        # An unquoted YAML date arrives as datetime.date; refuse rather than
        # coerce, matching how `birthdate` is written (quoted) in fixtures.
        raise ValueError(
            "Scenario config field `spouse_birthdate` must be a quoted ISO "
            f"YYYY-MM-DD string; got {type(value).__name__} {value!r}.")
    if value:
        try:
            parsed = datetime.date.fromisoformat(value)
        except (TypeError, ValueError):
            parsed = None
        if parsed is None or parsed.isoformat() != value:
            raise ValueError(
                f"Scenario config field `spouse_birthdate` must be an ISO "
                f"YYYY-MM-DD date; got {value!r}.")


def validate_birthdate(cfg: TaxReturnConfig) -> None:
    """Pure load-time check that `birthdate` is a real, quoted ISO
    YYYY-MM-DD date. Every consumer (the 1040 age checkboxes, the workbook
    flattener's year/month/day split, the 540 date of birth) reads it as
    ISO; a month-day-year value must refuse here, not fail or be misread
    downstream. Mirrors `validate_spouse_birthdate`."""
    value = cfg.birthdate
    if not value:
        raise ValueError(
            "Scenario config field `birthdate` (ISO YYYY-MM-DD) is required.")
    if not isinstance(value, str):
        # An unquoted YAML date arrives as datetime.date; refuse rather than
        # coerce, matching `spouse_birthdate`.
        raise ValueError(
            "Scenario config field `birthdate` must be a quoted ISO "
            f"YYYY-MM-DD string; got {type(value).__name__} {value!r}.")
    try:
        parsed = datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None or parsed.isoformat() != value:
        raise ValueError(
            f"Scenario config field `birthdate` must be an ISO "
            f"YYYY-MM-DD date; got {value!r}.")


_HOH = "head_of_household"
_QP = f"{_HOH}.qualifying_person"
_PERIODS = f"{_HOH}.lived_with_spouse_periods"
_KNOWN_HOH_KEYS = frozenset({
    "marital_status", "lived_with_spouse_periods", "separation_decree_kind",
    "qualifying_person"})
_REQUIRED_QP_KEYS = (
    "first_name", "last_name", "ssn", "birthdate", "relationship",
    "gross_income", "days_lived_with_you")
_KNOWN_QP_KEYS = frozenset(_REQUIRED_QP_KEYS) | {
    "full_time_student", "permanently_disabled", "claimed_as_dependent"}
_KNOWN_PERIOD_KEYS = frozenset({"from", "to"})
_CLAIMED_AS_DEPENDENT_REQUIRED = (
    "`head_of_household.qualifying_person.claimed_as_dependent` is required "
    "(true or false): do you claim this person as your dependent on this "
    "return? Form 1040's head-of-household line names the qualifying person "
    "only when they are \"a child but not your dependent\", so tenforty "
    "must be told. Add it.")
_CLAIMED_AS_DEPENDENT_REFUSAL = (
    "`head_of_household.qualifying_person.claimed_as_dependent` is true: you "
    "claim your head-of-household qualifying person as a dependent on this "
    "return. tenforty does not prepare returns with claimed dependents yet: "
    "the Child Tax Credit / Credit for Other Dependents (Schedule 8812, Form "
    "1040 line 19) would not be computed, overstating your tax. If this "
    "person is NOT claimed as your dependent on this return -- for example, "
    "you released the claim to the other parent on Form 8332 -- set "
    "`claimed_as_dependent: false`. If they ARE your dependent, tenforty "
    "cannot prepare this return until the dependents release (tenforty "
    "0.2.1); file it by hand. There is no acknowledge-and-proceed.")
# FTB 3532 Part I line 1f has exactly two From/To slots, and no year's
# instructions mention a continuation statement.
_MAX_LIVED_TOGETHER_PERIODS = 2


def normalize_ssn_digits(value: str) -> str:
    """The 9 bare digits of an SSN/ITIN written `NNNNNNNNN` or `NNN-NN-NNNN`.
    Raises ValueError for anything else."""
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 9 and text.isdigit():
            return text
        parts = text.split("-")
        if ([len(p) for p in parts] == [3, 2, 4]
                and all(p.isdigit() for p in parts)):
            return "".join(parts)
    raise ValueError(
        f"SSN/ITIN {value!r} must be 9 digits, written NNNNNNNNN or "
        "NNN-NN-NNNN.")


def qp_is_19_or_older(qp: HohQualifyingPerson, year: int) -> bool:
    """FTB 3532 Part III line 3: "If your qualifying person is age 19 or older
    in <year>, go to line 3a." Read as tax_year - birth_year >= 19 (ruling
    spec §8 Q5). January-1 edge: under the convention that a person attains
    an age the day before the birthday, someone born January 1 of
    tax_year - 18 is already 19 on December 31 of the tax year; this
    birth-year reading treats them as 18."""
    return year - int(qp.birthdate[:4]) >= 19


def _refuse_unknown_keys(data: dict, known: frozenset, where: str) -> None:
    unknown = set(data) - known
    if unknown:
        raise ValueError(
            f"Unknown key(s) in `{where}`: {sorted(unknown)}. Known keys: "
            f"{sorted(known)}.")


def _load_hoh_mapping(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(
            f"`{where}` must be a mapping of keys to values; got {value!r}.")
    return value


def _load_hoh_enum(enum_cls, value, where: str, form_part: str):
    try:
        return enum_cls(value)
    except ValueError:
        raise ValueError(
            f"`{where}` is {value!r}, which is not one of "
            f"{[m.value for m in enum_cls]} ({form_part}). Use one of those "
            "values.") from None


def _load_hoh_date(value, where: str) -> str:
    if not isinstance(value, str):
        # An unquoted YAML date arrives as datetime.date; refuse rather than
        # coerce, the same way `birthdate` is loaded.
        raise ValueError(
            f"`{where}` must be a quoted ISO YYYY-MM-DD string; got "
            f"{type(value).__name__} {value!r}. Put the date in quotes.")
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != value:
        raise ValueError(
            f"`{where}` must be an ISO YYYY-MM-DD date; got {value!r}.")
    return value


def _load_hoh_answer(value, where: str) -> bool | None:
    return None if value is None else _load_stated_bool(value, f"`{where}`")


def _load_lived_together_periods(
        raw, marital_status: HohMaritalStatus, year: int,
) -> tuple[LivedTogetherPeriod, ...]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError(
            f"`{_PERIODS}` must be a list of {{from, to}} periods; got "
            f"{raw!r}.")
    together = HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR
    if marital_status is not together:
        if raw:
            raise ValueError(
                f"`{_PERIODS}` must be empty unless `marital_status` is "
                f"`{together.value}` (FTB 3532 Part I line 1f, the only line "
                f"that lists periods lived together); `marital_status` is "
                f"`{marital_status.value}`. Remove the periods, or correct "
                "the marital status.")
        return ()
    if not raw:
        raise ValueError(
            f"`{_PERIODS}` is required when `marital_status` is "
            f"`{together.value}`: FTB 3532 Part I line 1f lists the "
            "beginning and ending dates of each period you lived with your "
            "spouse. Add one or two {from, to} periods.")
    if len(raw) > _MAX_LIVED_TOGETHER_PERIODS:
        raise ValueError(
            f"`{_PERIODS}` lists {len(raw)} periods, but FTB 3532 Part I "
            "line 1f has exactly two From/To slots and no continuation "
            "statement, so at most two periods can be reported. This "
            "return cannot be completed on the form; file it by hand.")
    first_day = datetime.date(year, 1, 1)
    last_day = datetime.date(year, 12, 31)
    periods: list[tuple[datetime.date, datetime.date]] = []
    for i, item in enumerate(raw):
        where = f"{_PERIODS}[{i}]"
        item = _load_hoh_mapping(item, where)
        _refuse_unknown_keys(item, _KNOWN_PERIOD_KEYS, where)
        for key in ("from", "to"):
            if key not in item:
                raise ValueError(f"`{where}.{key}` is required.")
        start = datetime.date.fromisoformat(
            _load_hoh_date(item["from"], f"{where}.from"))
        end = datetime.date.fromisoformat(
            _load_hoh_date(item["to"], f"{where}.to"))
        if start > end:
            raise ValueError(
                f"`{where}`: `from` ({start}) is after its `to` ({end}). "
                "Swap the dates.")
        if start < first_day or end > last_day:
            raise ValueError(
                f"`{where}` ({start} to {end}) lies outside tax year {year}; "
                "FTB 3532 Part I line 1f reports only periods within the "
                "tax year.")
        if periods:
            prev_start, prev_end = periods[-1]
            if start < prev_start:
                raise ValueError(
                    f"`{_PERIODS}` is out of order: period {i} begins "
                    f"({start}) before period {i - 1} ({prev_start}). List "
                    "the periods in date order.")
            if start <= prev_end:
                raise ValueError(
                    f"`{_PERIODS}`: period {i} ({start} to {end}) and period "
                    f"{i - 1} ({prev_start} to {prev_end}) overlap. Merge "
                    "them into one period.")
        periods.append((start, end))
    return tuple(LivedTogetherPeriod(start=s.isoformat(), end=e.isoformat())
                 for s, e in periods)


def _load_qp_ssn(value) -> str:
    where = f"{_QP}.ssn"
    if isinstance(value, str) and value.strip().lower() == "died":
        raise ValueError(
            f"`{where}` is {value!r}. FTB 3532 accepts \"Died\" only for a "
            "person born and died in the year with no SSN, and then the "
            "filer must attach the birth and death certificates. tenforty "
            "cannot attach those certificates, so this return must be filed "
            "by hand.")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"`{where}` is blank. FTB 3532 Part III line 3 needs the "
            "qualifying person's SSN (or ITIN), and no year's form has an "
            "\"applied for\" entry; incomplete information can lose the "
            "head-of-household status. Enter the 9-digit SSN or ITIN, quoted.")
    try:
        return normalize_ssn_digits(value)
    except ValueError:
        raise ValueError(
            f"`{where}` is {value!r}; it must be 9 digits, written "
            "NNNNNNNNN or NNN-NN-NNNN (FTB 3532 Part III line 3).") from None


def _load_qualifying_person(raw, year: int) -> HohQualifyingPerson:
    data = _load_hoh_mapping(raw, _QP)
    _refuse_unknown_keys(data, _KNOWN_QP_KEYS, _QP)
    for key in _REQUIRED_QP_KEYS:
        if key not in data or data[key] is None:
            raise ValueError(
                f"`{_QP}.{key}` is required: FTB 3532 prints it (Part II for "
                "the relationship, Part III for the rest). Add it.")
    names = {}
    for key in ("first_name", "last_name"):
        where = f"{_QP}.{key}"
        text = _load_stated_text(data[key], f"`{where}`")
        if not text.strip():
            raise ValueError(
                f"`{where}` is blank; FTB 3532 Part III line 3 prints the "
                "qualifying person's first and last name. Fill it in.")
        names[key] = text.strip()
    ssn = _load_qp_ssn(data["ssn"])
    birthdate = _load_hoh_date(data["birthdate"], f"{_QP}.birthdate")
    if datetime.date.fromisoformat(birthdate) > datetime.date(year, 12, 31):
        raise ValueError(
            f"`{_QP}.birthdate` ({birthdate}) is after the end of tax year "
            f"{year}; a qualifying person must be born by 12/31/{year}. "
            "Correct the date or the tax year.")
    relationship = _load_hoh_enum(
        HohRelationship, data["relationship"], f"{_QP}.relationship",
        "FTB 3532 Part II, lines 2a-2e")
    gross_income = _load_stated_number(
        data["gross_income"], f"`{_QP}.gross_income`")
    if gross_income < 0:
        raise ValueError(
            f"`{_QP}.gross_income` ({gross_income:g}) must be >= 0 (FTB 3532 "
            "Part III line 4).")
    days = _load_stated_int(
        data["days_lived_with_you"], f"`{_QP}.days_lived_with_you`")
    days_in_year = (datetime.date(year, 12, 31)
                    - datetime.date(year, 1, 1)).days + 1
    if not 0 <= days <= days_in_year:
        raise ValueError(
            f"`{_QP}.days_lived_with_you` is {days}, but it must be between "
            f"0 and {days_in_year}, the number of days in tax year {year} "
            "(FTB 3532 Part III line 5).")
    answers = {
        key: _load_hoh_answer(data.get(key), f"{_QP}.{key}")
        for key in ("full_time_student", "permanently_disabled")}
    claimed = _load_hoh_answer(
        data.get("claimed_as_dependent"), f"{_QP}.claimed_as_dependent")
    if claimed is None:
        raise ValueError(_CLAIMED_AS_DEPENDENT_REQUIRED)
    person = HohQualifyingPerson(
        first_name=names["first_name"], last_name=names["last_name"],
        ssn=ssn, birthdate=birthdate, relationship=relationship,
        gross_income=gross_income, days_lived_with_you=days,
        claimed_as_dependent=claimed, **answers)
    lines = {"full_time_student": "3a", "permanently_disabled": "3b"}
    if qp_is_19_or_older(person, year):
        for key, value in answers.items():
            if value is None:
                raise ValueError(
                    f"`{_QP}.{key}` is required (true or false): the "
                    f"qualifying person is 19 or older in {year}, so FTB "
                    f"3532 Part III line {lines[key]} must be answered.")
    else:
        for key, value in answers.items():
            if value is not None:
                raise ValueError(
                    f"`{_QP}.{key}` must be null: the qualifying person is "
                    f"under 19 in {year}, and FTB 3532 Part III line 3 says "
                    f"\"If not, go to line 4\", so line {lines[key]} is "
                    "left blank. Remove the answer.")
    return person


def load_head_of_household(raw: dict, year: int) -> HeadOfHouseholdFacts:
    """Parse ``config.head_of_household`` (spec §4.1) into dataclasses,
    refusing what FTB 3532 could not print correctly: unknown keys and enum
    values, the line 1f periods (required iff 1f, at most two, inside the
    year, ordered, non-overlapping), the line 1d decree kind (required iff
    1d), blank names, an SSN that is not 9 digits (or "Died"), a birthdate
    after the year, a negative gross income, a day count outside the year,
    and lines 3a/3b answered iff the person is 19 or older (spec §4.3 rules
    1-4, 6-9 and 2b). Rules needing the rest of the config run in
    ``validate_head_of_household``."""
    data = _load_hoh_mapping(raw, _HOH)
    _refuse_unknown_keys(data, _KNOWN_HOH_KEYS, _HOH)
    if data.get("marital_status") is None:
        raise ValueError(
            f"`{_HOH}.marital_status` is required (FTB 3532 Part I). Add it.")
    marital_status = _load_hoh_enum(
        HohMaritalStatus, data["marital_status"], f"{_HOH}.marital_status",
        "FTB 3532 Part I, lines 1a-1f")
    if data.get("qualifying_person") is None:
        raise ValueError(
            f"`{_QP}` is required: FTB 3532 Parts II and III describe the "
            "person who qualifies you for head of household. Add it.")
    periods = _load_lived_together_periods(
        data.get("lived_with_spouse_periods"), marital_status, year)
    decree_raw = data.get("separation_decree_kind")
    divorced = HohMaritalStatus.DIVORCED_OR_LEGALLY_SEPARATED
    decree = None
    if marital_status is divorced:
        if decree_raw is None:
            raise ValueError(
                f"`{_HOH}.separation_decree_kind` is required when "
                f"`marital_status` is `{divorced.value}` (FTB 3532 Part I "
                "line 1d): set `divorce_or_dissolution` or "
                "`legal_separation`.")
        decree = _load_hoh_enum(
            SeparationDecreeKind, decree_raw,
            f"{_HOH}.separation_decree_kind", "FTB 3532 Part I line 1d")
    elif decree_raw is not None:
        raise ValueError(
            f"`{_HOH}.separation_decree_kind` is set, but it is only for "
            f"`marital_status: {divorced.value}` (FTB 3532 Part I line 1d); "
            f"`marital_status` is `{marital_status.value}`. Remove it, or "
            "correct the marital status.")
    return HeadOfHouseholdFacts(
        marital_status=marital_status,
        qualifying_person=_load_qualifying_person(
            data["qualifying_person"], year),
        lived_with_spouse_periods=periods,
        separation_decree_kind=decree)


# FTB 3532 Part II relationships that can make a qualifying child (2a-2c).
_QUALIFYING_CHILD_RELATIONSHIPS = frozenset({
    HohRelationship.CHILD_OR_STEPCHILD,
    HohRelationship.GRANDCHILD_SIBLING_NIECE_OR_NEPHEW,
    HohRelationship.ELIGIBLE_FOSTER_CHILD})
# "Considered unmarried" (FTB 3532 Part I line 1 instructions): the
# qualifying person is the filer's birth child, stepchild, adopted child, or
# eligible foster child (2a, 2c).
_CONSIDERED_UNMARRIED_RELATIONSHIPS = frozenset({
    HohRelationship.CHILD_OR_STEPCHILD, HohRelationship.ELIGIBLE_FOSTER_CHILD})
_MARRIED_STATUSES = frozenset({
    HohMaritalStatus.MARRIED_LIVED_APART_ALL_YEAR,
    HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR})


def qp_on_qualifying_child_path(qp: HohQualifyingPerson, year: int) -> bool:
    """Rule 13: the qualifying person is on the qualifying-child path: a
    Part II line 2a-2c relationship that meets the age test (FTB 3532 Part
    III line 3 instructions: "under 19 years of age or a full-time student
    under 24 years of age", or permanently and totally disabled at any age).
    The student branch's under-24 bound is enforced, with the same
    birth-year age reading as ``qp_is_19_or_older`` (tax_year - birth_year
    < 24)."""
    if qp.relationship not in _QUALIFYING_CHILD_RELATIONSHIPS:
        return False
    student_under_24 = (qp.full_time_student is True
                        and year - int(qp.birthdate[:4]) < 24)
    return (not qp_is_19_or_older(qp, year)
            or student_under_24
            or qp.permanently_disabled is True)


def _refuse_hoh_contradictions(cfg: TaxReturnConfig) -> None:
    """Rules 10-13 over a present head_of_household block."""
    facts = cfg.head_of_household
    qp = facts.qualifying_person
    year = cfg.year
    days_in_year = (datetime.date(year, 12, 31)
                    - datetime.date(year, 1, 1)).days + 1
    # FTB 3532 line 5 instructions: "In the event of a birth or death of
    # your qualifying person during the year, enter 365 days. Note: A year
    # is 365 days, a leap year is 366 days." Death is not captured; a birth
    # in the tax year is, so a born-in-year count short of the full year is
    # a face-of-form error, refused ahead of rule 10's threshold.
    birth_or_death_rule = (
        "FTB 3532 line 5 instructions: \"In the event of a birth or death of "
        "your qualifying person during the year, enter 365 days. Note: A "
        "year is 365 days, a leap year is 366 days.\"")
    if (int(qp.birthdate[:4]) == year
            and qp.days_lived_with_you != days_in_year):
        raise ValueError(
            f"`{_QP}.days_lived_with_you` is {qp.days_lived_with_you}, but "
            f"the qualifying person was born during {year} "
            f"({qp.birthdate}). {birth_or_death_rule} Correct the count: "
            f"enter {days_in_year} days per the FTB 3532 line 5 "
            "instructions.")
    # Rule 10. FTB 3532 line 5 instructions: "more than half the year is 183
    # days. (A leap year has 366 days, and more than half a leap year is 184
    # days.)" Face-of-form contradiction only; not an eligibility
    # determination (FTB Pub. 1540 counts a temporary absence as time lived
    # together, and the filer's day count is taken as stated).
    threshold = days_in_year // 2 + 1
    if not qp.days_lived_with_you >= threshold:
        raise ValueError(
            f"`{_QP}.days_lived_with_you` is {qp.days_lived_with_you}, but "
            "head of household requires the qualifying person to have lived "
            f"with you more than half the year: at least {threshold} days in "
            f"{year} (FTB 3532 line 5 instructions: \"more than half the "
            "year is 183 days\", 184 in a leap year; temporary absences "
            "count as time lived with you). If your qualifying person was "
            f"born or died during {year}, enter {days_in_year} days instead "
            f"({birth_or_death_rule}). As entered, FTB 3532 would show you "
            "do not qualify. Correct the count, or file under the status "
            "that applies.")
    # Rule 11. FTB 3532 line 5 instructions: if you "lived with your
    # spouse/RDP at any time during the last six months of the year, you
    # cannot qualify for the HOH filing status." The last six months begin
    # July 1. Face-of-form contradiction only; not an eligibility
    # determination (a spouse's temporary absence still counts as living
    # together, which no entry here can show).
    last_six_months = datetime.date(year, 7, 1)
    for i, period in enumerate(facts.lived_with_spouse_periods):
        if datetime.date.fromisoformat(period.end) >= last_six_months:
            raise ValueError(
                f"`{_PERIODS}[{i}]` ends {period.end}, on or after "
                f"07/01/{year}. FTB 3532 instructions: if you lived with "
                "your spouse at any time during the last six months of the "
                "year, you cannot qualify for the head-of-household filing "
                "status. As entered, FTB 3532 would show you do not qualify. "
                "Correct the dates, or file under the status that applies.")
    # Rule 12. FTB 3532 Part I line 1 instructions ("considered unmarried"):
    # "Your qualifying person is your birth child, stepchild, adopted child,
    # or eligible foster child." Face-of-form contradiction only; not an
    # eligibility determination.
    if (facts.marital_status in _MARRIED_STATUSES
            and qp.relationship not in _CONSIDERED_UNMARRIED_RELATIONSHIPS):
        raise ValueError(
            f"`{_QP}.relationship` is `{qp.relationship.value}`, but "
            f"`marital_status` is `{facts.marital_status.value}`. A married "
            "filer qualifies for head of household only as \"considered "
            "unmarried\", which requires the qualifying person to be your "
            "birth child, stepchild, adopted child, or eligible foster child "
            "(FTB 3532 Part I line 1 instructions; Part II line 2a or 2c). "
            "As entered, FTB 3532 would show you do not qualify. Correct "
            "the relationship or marital status, or file under the status "
            "that applies.")
    # Rule 13 (scope, ruling Q3). FTB 3532 Qualifications §B: a filer must be
    # entitled to the Dependent Exemption Credit for a qualifying relative,
    # who would then be a CA 540 line 10 dependent -- dependents are refused
    # until 0.2.1, so the qualifying-relative path is refused with them.
    if not qp_on_qualifying_child_path(qp, year):
        raise ValueError(
            f"The qualifying person (`{_QP}`: relationship "
            f"`{qp.relationship.value}`, born {qp.birthdate}) is not on the "
            "qualifying-child path: a Part II line 2a-2c relationship who is "
            f"under 19 in {year}, a full-time student under 24, or "
            "permanently and totally disabled. Anyone else can qualify you "
            "only as a qualifying relative, for whom California requires "
            "you to be entitled to the Dependent Exemption Credit -- and "
            "tenforty does not prepare returns with dependents yet. "
            "Qualifying relatives arrive with dependents support in 0.2.1; "
            "until then, file this return by hand.")


def validate_head_of_household(cfg: TaxReturnConfig) -> None:
    """Pure check of ``config.head_of_household`` against the rest of the
    config: required iff head of household (spec §4.2), the qualifying
    person is not claimed as a dependent (``claimed_as_dependent`` stated,
    and true refuses until 0.2.1), the qualifying person is not the filer
    (rule 5), no face-of-form contradiction of the
    status (rules 10-12), and the qualifying-child path only (rule 13,
    until 0.2.1). Called at load from
    ``_validate_scenario_config`` and re-used by the CA emit gate, so a
    directly built config is checked too."""
    status = FilingStatus(cfg.filing_status)
    facts = cfg.head_of_household
    if status is FilingStatus.HEAD_OF_HOUSEHOLD and facts is None:
        raise ValueError(
            "`filing_status` is `head_of_household`, but the scenario has no "
            "`head_of_household` block. Head of household needs a qualifying "
            "person, and California denies head-of-household status to a "
            "return that does not attach a completed FTB 3532 (Head of "
            "Household Filing Status Schedule). Add `config."
            "head_of_household` with `marital_status` and "
            "`qualifying_person` (first_name, last_name, ssn, birthdate, "
            "relationship, gross_income, days_lived_with_you).")
    if status is not FilingStatus.HEAD_OF_HOUSEHOLD and facts is not None:
        raise ValueError(
            "Scenario config has a `head_of_household` block, but "
            f"`filing_status` is `{status.value}`. The block describes a "
            "head-of-household qualifying person (FTB 3532) and belongs on "
            "no other return; a stray block usually means the filing status "
            "is wrong. Remove the block, or set `filing_status: "
            "head_of_household`.")
    if facts is None:
        return
    # claimed_as_dependent (Juno ruling, M3): required, and true is a
    # capability refusal -- wrong species, so it fires ahead of rule 5 and
    # the face-of-form rules 10-13.
    # Only False proceeds: a directly built config skips the loader's type
    # check, and a non-bool ("true", 1) must not print the 1040's "child but
    # not your dependent" line.
    claimed = facts.qualifying_person.claimed_as_dependent
    if claimed is None:
        raise ValueError(_CLAIMED_AS_DEPENDENT_REQUIRED)
    if claimed is True:
        raise NotImplementedError(_CLAIMED_AS_DEPENDENT_REFUSAL)
    if claimed is not False:
        raise ValueError(
            f"`{_QP}.claimed_as_dependent` must be true or false; got "
            f"{claimed!r}")
    # Rule 5 (FTB 3532 instructions, Part II line 2): "You may not claim
    # yourself ... as your qualifying person." The spouse case is unreachable:
    # head of household refuses spouse fields.
    # Compared digits-only: the federal 1040 prints a filer SSN of any shape
    # as its digits (f1040_spine._ssn_digits), so a space-separated filer
    # SSN equal to the qualifying person's must refuse too. Equality against
    # a filer SSN that is not 9 digits means nothing, so skip it; the emit
    # path still fails closed (FTB 3532 presentation refuses a filer SSN
    # that does not normalize).
    filer_digits = "".join(ch for ch in (cfg.ssn or "") if ch.isdigit())
    # Both sides: a directly built qualifying person keeps whatever SSN
    # shape it was given (the loader normalizes; a direct build does not).
    qp_digits = "".join(
        ch for ch in (facts.qualifying_person.ssn or "") if ch.isdigit())
    if len(filer_digits) == 9 and qp_digits == filer_digits:
        raise ValueError(
            f"`{_QP}.ssn` is the same as the filer's own SSN. You may not be "
            "your own qualifying person (FTB 3532 instructions, Part II line "
            "2). Enter the qualifying person's SSN.")
    _refuse_hoh_contradictions(cfg)


def _validate_scenario_config(cfg: TaxReturnConfig) -> None:
    """Enforce the load-time attestations via
    tenforty.attestations._ATTESTATIONS. Conditional fields (MFS / prior-year
    recovery) are validated separately because they depend on other config
    values, not on a trigger-predicate over the full scenario."""
    refuse_spouse_fields_without_spouse(cfg)
    validate_load_time(cfg)
    validate_sche_1099_answers(cfg)
    validate_third_party_designee(cfg)

    # has_foreign_accounts=True is an immediate NotImplementedError regardless
    # of trigger predicate — there is no scenario context that makes a foreign
    # account safe. Keep this eager raise here rather than in the table.
    if cfg.has_foreign_accounts is True:
        raise NotImplementedError(
            "Schedule B Part III / FBAR is not supported in tenforty v1. "
            "Returns for filers with foreign financial accounts cannot be "
            "produced by this version; support is tracked as a follow-up."
        )

    # Conditional fields — sibling-dependent, not table-driven.
    if cfg.filing_status == FilingStatus.MARRIED_FILING_SEPARATELY:
        if cfg.mfs_lived_with_spouse_any_time is None:
            raise ValueError(
                "Scenario config field `mfs_lived_with_spouse_any_time` is "
                "required when `filing_status` is `married_filing_separately`. Per IRC §469(i)(5), "
                "MFS filers who lived with a spouse at any time during the "
                "year have a $0 Form 8582 special allowance for rental real "
                "estate; MFS filers who lived apart the entire year have "
                "$12,500."
            )

    if cfg.prior_year_itemized:
        if cfg.prior_year_itemized_deduction_amount is None:
            raise ValueError(
                "Scenario config field `prior_year_itemized_deduction_amount` "
                "is required when `prior_year_itemized` is true. It is used "
                "by the state-refund tax-benefit-rule (Sch 1 line 1) to cap "
                "the taxable refund at the prior-year recovery amount."
            )
        if cfg.prior_year_standard_deduction_amount is None:
            raise ValueError(
                "Scenario config field `prior_year_standard_deduction_amount` "
                "is required when `prior_year_itemized` is true. It is used "
                "to compute the recovery limit."
            )
        if cfg.prior_year_salt_paid is None:
            raise ValueError(
                "Scenario config field `prior_year_salt_paid` is required when "
                "`prior_year_itemized` is true. It is the prior year's state & "
                "local taxes actually PAID (prior-year Schedule A line 5d, BEFORE "
                "the line-5e $10k cap) and drives the Sch 1 line-1 tax-benefit "
                "limitation (a refund is taxable only to the extent it lowered the "
                "capped SALT deduction)."
            )

    if cfg.prior_year_salt_paid is not None and cfg.prior_year_salt_paid < 0:
        raise ValueError("Scenario config field `prior_year_salt_paid` must be >= 0.")

    if cfg.estimated_tax_payments < 0:
        raise ValueError(
            "Scenario config field `estimated_tax_payments` must be >= 0. "
            "The filer's stated total federal estimated tax payments are "
            "carried through verbatim (never computed or clamped), so a "
            "negative value cannot be silently corrected to 0 — it is "
            "refused instead."
        )

    if cfg.charitable_cash_nonitemizer < 0:
        raise ValueError(
            "Scenario config field `charitable_cash_nonitemizer` must be "
            ">= 0. The filer's stated 2021 above-the-line non-itemizer "
            "cash-charitable contribution is carried through verbatim "
            "(never computed or clamped), so a negative value cannot be "
            "silently corrected to 0 — it is refused instead."
        )

    if cfg.self_employed_health_insurance_deduction < 0:
        raise ValueError(
            "Scenario config field `self_employed_health_insurance_deduction` "
            "must be >= 0. The filer's stated self-employed health-insurance "
            "deduction (Schedule 1 line 17) is carried through verbatim "
            "(never computed or clamped), so a negative value cannot be "
            "silently corrected to 0 — it is refused instead."
        )

    params = load_federal_params(cfg.year)
    if cfg.charitable_cash_nonitemizer and params.nonitemizer_charitable_cap is None:
        raise ValueError(
            "Scenario config field `charitable_cash_nonitemizer` is a 2021-only "
            "provision (the CARES/CAA above-the-line charitable deduction for "
            f"non-itemizers); it must be 0 for tax year {cfg.year}."
        )

    if cfg.charitable_cash_nonitemizer and cfg.filing_status is not FilingStatus.SINGLE:
        raise ValueError(
            "Scenario config field `charitable_cash_nonitemizer` (2021 line 12b) "
            "is certified in tenforty for SINGLE filers only. Non-single 12b "
            "exists in the IRS workbook but is NOT certified in tenforty (no "
            f"attested per-status cap), so filing_status={cfg.filing_status.value} "
            "with a nonzero amount is refused as an out-of-scope condition."
        )

    cap = params.nonitemizer_charitable_cap
    if cfg.charitable_cash_nonitemizer and cap is not None \
            and cfg.charitable_cash_nonitemizer > cap:
        raise ValueError(
            f"Scenario config field `charitable_cash_nonitemizer` "
            f"({cfg.charitable_cash_nonitemizer}) exceeds the 2021 single-filer "
            f"non-itemizer cap of ${cap}. The amount is carried verbatim or "
            f"refused, never silently capped."
        )

    validate_birthdate(cfg)
    validate_spouse_birthdate(cfg)
    validate_head_of_household(cfg)


def _load_source_documents(
    w2s: list[W2], base_dir: Path
) -> list[SourceDocument]:
    """Normalize `W2.pdf` declarations into routed SourceDocument records.

    Routing is a pure function of the W-2's own declared data: federal
    always; california iff CA-attributed state withholding exists. Never
    keyed on ca540 presence — the CA CLI path loads its YAML separately,
    and a california routing is inert unless CA forms are emitted.

    Fails closed naming the employer: missing file, unopenable PDF, or
    zero pages. Contents are never parsed.
    """
    docs: list[SourceDocument] = []
    for w2 in w2s:
        if not w2.pdf:
            continue
        raw = Path(w2.pdf).expanduser()
        resolved = raw if raw.is_absolute() else (base_dir / raw).resolve()
        if not resolved.exists():
            raise ValueError(
                f"Source document for W-2 '{w2.employer}' not found: "
                f"{w2.pdf!r} (resolved to {resolved})")
        try:
            num_pages = len(pypdf.PdfReader(str(resolved)).pages)
        except Exception as e:
            raise ValueError(
                f"Source document for W-2 '{w2.employer}' is not a readable "
                f"PDF: {resolved} ({e})") from e
        if num_pages < 1:
            raise ValueError(
                f"Source document for W-2 '{w2.employer}' has no pages: "
                f"{resolved}")
        packets: tuple[str, ...] = ("federal_individual",)
        if w2.state == "CA" and w2.state_tax_withheld > 0:
            packets = ("federal_individual", "california")
        docs.append(SourceDocument(path=resolved, kind="w2", packets=packets))
    return docs


def load_scenario(path: Path) -> Scenario:
    """Load a tax scenario from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Scenario YAML must be a mapping at the top level, got "
            f"{type(data).__name__}")

    # Before the unknown-key check: a retired shape gets its own migration
    # pointer from the ledger rather than a generic "unknown key".
    _attestations.enforce_scoped_refusals(data, "parse")

    unknown = set(data) - _KNOWN_TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(
            f"Unknown top-level key(s) in scenario YAML: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_TOP_LEVEL_KEYS)}")

    # The nested head_of_household block is parsed into dataclasses (with
    # the tax year its rules need) and passed in; the caller's mapping is
    # never mutated.
    config_data = dict(data["config"])
    hoh_raw = config_data.pop("head_of_household", None)
    config = TaxReturnConfig(**config_data)
    if hoh_raw is not None:
        config = dataclasses.replace(
            config, head_of_household=load_head_of_household(
                hoh_raw, config.year))
    _validate_scenario_config(config)

    form_data: dict[str, list] = {}
    for yaml_key, (model_cls, field_name) in _FORM_REGISTRY.items():
        items = data.get(yaml_key, [])
        form_data[field_name] = [model_cls(**item) for item in items]
    for yaml_key, model_cls in _DEPRECIATION_ACTIVITY_REGISTRY.items():
        form_data[yaml_key] = [
            _load_depreciation_activity(model_cls, item, f"{yaml_key}[{i}]")
            for i, item in enumerate(data.get(yaml_key) or [])]

    validate_w2_owners(config, form_data["w2s"])
    s_corp_return = _load_s_corp_return(data.get("s_corp_return"))
    if s_corp_return is not None:
        validate_tax_year_dates(s_corp_return, config.year)
    ca540 = _load_ca540(data.get("ca540"), config.year)
    itemized_raw = data.get("itemized_deductions")
    itemized_deductions = (
        ItemizedDeductions(**itemized_raw) if itemized_raw is not None else None)
    form_1095a = _load_form_1095a(data.get("form_1095a"), config)
    form_3115 = _load_form_3115(data.get(_attestations.FORM_3115_KEY))
    source_documents = _load_source_documents(form_data["w2s"], path.parent)
    mid_quarter_ack = data.get(_MID_QUARTER_ACK_KEY)
    if mid_quarter_ack is not None:
        mid_quarter_ack = _load_stated_bool(
            mid_quarter_ack, _MID_QUARTER_ACK_KEY)
    listed_property_ack = data.get(_LISTED_PROPERTY_ACK_KEY)
    if listed_property_ack is not None:
        listed_property_ack = _load_stated_bool(
            listed_property_ack, _LISTED_PROPERTY_ACK_KEY)
    schedule_3_ack = data.get(_SCHEDULE_3_ACK_KEY)
    if schedule_3_ack is not None:
        schedule_3_ack = _load_stated_bool(schedule_3_ack, _SCHEDULE_3_ACK_KEY)
    scenario = Scenario(
        config=config, s_corp_return=s_corp_return, ca540=ca540,
        acknowledges_no_listed_property=listed_property_ack,
        acknowledges_schedule_3_not_produced=schedule_3_ack,
        eic_eligibility=_load_eic_eligibility(
            data.get("eic_eligibility"), config),
        itemized_deductions=itemized_deductions, form_1095a=form_1095a,
        form_3115=form_3115,
        source_documents=source_documents,
        positions=_load_positions(data),
        acknowledges_no_personal_property_behind_stated_depreciation=(
            mid_quarter_ack),
        **form_data)
    _validate_schedule_k1s(scenario)
    _validate_schedule_c_businesses(scenario)
    _validate_charitable_itemizer(scenario)
    _attestations.enforce_scoped_refusals(scenario, "load")
    return scenario


def _validate_charitable_itemizer(scenario) -> None:
    """12b is for NON-ITEMIZERS. Itemization is decided at compute time
    (Sch A total vs standard), so at load we can only see whether itemized
    inputs were SUPPLIED. Conservative refusal: a nonzero 12b amount together
    with a supplied itemized_deductions block is contradictory (a non-itemizer
    would not file Schedule A), and the workbook's DeductPlusCharity =
    SUM(Deductions, Charitable) would silently add 12b on top of itemized
    deductions. Refuse rather than risk a silently-wrong return. (Documented
    conservatism: a filer who supplies Sch A but would take the standard
    deduction must drop the Sch A inputs to claim 12b.)"""
    if scenario.config.charitable_cash_nonitemizer and scenario.itemized_deductions is not None:
        raise ValueError(
            "Scenario config field `charitable_cash_nonitemizer` (2021 line 12b) "
            "is for non-itemizers only, but this scenario supplies an "
            "`itemized_deductions` block. Refusing: 12b cannot be combined with "
            "itemized deductions (drop the itemized_deductions block to claim 12b)."
        )


def _validate_schedule_k1s(scenario: Scenario) -> None:
    """Enforce the per-entity box-number caller contract on ScheduleK1.

    1041 K-1 box 1 is interest income (routed to Sch B), not ordinary
    business income (Sch E Part II). Reject a mis-populated dataclass
    immediately rather than letting it silently land in the wrong column.
    """
    for k1 in scenario.schedule_k1s:
        if k1.entity_type == EntityType.ESTATE_TRUST and k1.ordinary_business_income != 0:
            raise ValueError(
                f"K-1 {k1.entity_name!r} has entity_type='estate_trust' but "
                f"nonzero ordinary_business_income={k1.ordinary_business_income}. "
                "Form 1041 K-1 box 1 is interest income — load it into "
                "`interest_income` instead. See ScheduleK1 docstring."
            )


def _validate_schedule_c_businesses(scenario: Scenario) -> None:
    """Refuse any NEGATIVE per-business Schedule C amount at load.

    Schedule C per-business amounts (gross receipts, every Part II expense
    category, and the unmodeled-feature amount fields) are carried through
    verbatim -- never computed or clamped -- so a negative amount cannot be
    silently corrected to 0; it is refused instead. Mirrors the
    estimated_tax_payments / self_employed_health_insurance_deduction refusals
    in `_validate_scenario_config`. `description` (str) and `statutory_employee`
    (bool) are not amounts and are excluded (see `_SCHEDULE_C_AMOUNT_FIELDS`)."""
    for idx, biz in enumerate(scenario.schedule_c_businesses):
        for field_name in _SCHEDULE_C_AMOUNT_FIELDS:
            if getattr(biz, field_name) < 0:
                raise ValueError(
                    f"Schedule C business #{idx} ({biz.description!r}) field "
                    f"`{field_name}` must be >= 0. Per-business Schedule C "
                    f"amounts are carried through verbatim (never computed or "
                    f"clamped), so a negative value cannot be silently "
                    f"corrected to 0 -- it is refused instead."
                )
