import datetime
from pathlib import Path

import yaml

from tenforty.attestations import validate_load_time
from tenforty.models import (
    AccountingMethod,
    Address,
    DepreciableAsset,
    EntityType,
    FilingStatus,
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    RentalProperty,
    SCorpDeductions,
    SCorpIncome,
    SCorpPayments,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpScopeOuts,
    SCorpShareholder,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)

_FORM_REGISTRY: dict[str, tuple[type, str]] = {
    "w2s": (W2, "w2s"),
    "form1099_int": (Form1099INT, "form1099_int"),
    "form1099_div": (Form1099DIV, "form1099_div"),
    "form1099_b": (Form1099B, "form1099_b"),
    "form1099_g": (Form1099G, "form1099_g"),
    "form1098s": (Form1098, "form1098s"),
    "schedule_k1s": (ScheduleK1, "schedule_k1s"),
    "rental_properties": (RentalProperty, "rental_properties"),
    "depreciable_assets": (DepreciableAsset, "depreciable_assets"),
}


def _coerce_date(value) -> datetime.date:
    """PyYAML returns `datetime.date` for unquoted ISO dates and `str`
    for quoted ones; normalize both to `datetime.date`."""
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def _load_address(data: dict) -> Address:
    return Address(
        street=data["street"],
        city=data["city"],
        state=data["state"],
        zip_code=data["zip_code"],
    )


def _load_schedule_b_answers(data: dict) -> SCorpScheduleBAnswers:
    return SCorpScheduleBAnswers(
        accounting_method=AccountingMethod(data["accounting_method"]),
        business_activity_code=data["business_activity_code"],
        business_activity_description=data["business_activity_description"],
        product_or_service=data["product_or_service"],
        any_c_corp_subsidiaries=data["any_c_corp_subsidiaries"],
        has_any_foreign_shareholders=data["has_any_foreign_shareholders"],
        owns_foreign_entity=data["owns_foreign_entity"],
    )


def _load_income(data: dict) -> SCorpIncome:
    return SCorpIncome(
        gross_receipts=float(data["gross_receipts"]),
        returns_and_allowances=float(data["returns_and_allowances"]),
        cogs_aggregate=float(data["cogs_aggregate"]),
        net_gain_loss_4797=float(data["net_gain_loss_4797"]),
        other_income=float(data["other_income"]),
    )


def _load_deductions(data: dict) -> SCorpDeductions:
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
        other_deductions=float(data["other_deductions"]),
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


def _load_s_corp_return(data: dict | None) -> SCorpReturn | None:
    """Build SCorpReturn from a YAML-parsed dict. Each section uses an
    explicit-field-names loader (not `**` dict-spread) so a typoed YAML
    key fails with a clear `KeyError: <field>` rather than the implicit
    `TypeError: unexpected keyword argument` from dataclass construction."""
    if data is None:
        return None
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
        shareholders=[
            SCorpShareholder(
                name=sh["name"],
                ssn_or_ein=sh["ssn_or_ein"],
                address=_load_address(sh["address"]),
                ownership_percentage=float(sh["ownership_percentage"]),
            )
            for sh in data.get("shareholders", [])
        ],
        scope_outs=_load_scope_outs(data.get("scope_outs", {})),
        payments=_load_payments(data.get("payments", {})),
    )


def _validate_scenario_config(cfg: TaxReturnConfig) -> None:
    """Enforce the load-time attestations via
    tenforty.attestations._ATTESTATIONS. Conditional fields (MFS / prior-year
    recovery) are validated separately because they depend on other config
    values, not on a trigger-predicate over the full scenario."""
    validate_load_time(cfg)

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
    if cfg.filing_status == FilingStatus.MARRIED_SEPARATELY:
        if cfg.mfs_lived_with_spouse_any_time is None:
            raise ValueError(
                "Scenario config field `mfs_lived_with_spouse_any_time` is "
                "required when `filing_status` is `mfs`. Per IRC §469(i)(5), "
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


def load_scenario(path: Path) -> Scenario:
    """Load a tax scenario from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    config = TaxReturnConfig(**data["config"])
    _validate_scenario_config(config)

    form_data: dict[str, list] = {}
    for yaml_key, (model_cls, field_name) in _FORM_REGISTRY.items():
        items = data.get(yaml_key, [])
        form_data[field_name] = [model_cls(**item) for item in items]

    s_corp_return = _load_s_corp_return(data.get("s_corp_return"))
    scenario = Scenario(config=config, s_corp_return=s_corp_return, **form_data)
    _validate_schedule_k1s(scenario)
    return scenario


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
