from pathlib import Path

import yaml

from tenforty.models import (
    DepreciableAsset,
    EntityType,
    FilingStatus,
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    RentalProperty,
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


def _validate_scenario_config(cfg: TaxReturnConfig) -> None:
    """Enforce the scope-out attestations documented in Plan B (GH #11).

    Both `has_foreign_accounts` and `acknowledges_form_8949_unsupported` are
    required — scenarios MUST declare them explicitly as True or False.
    Additionally, `has_foreign_accounts=True` raises NotImplementedError
    immediately because Schedule B Part III / FBAR is not supported in v1.
    The `acknowledges_form_8949_unsupported=True` case is checked later in
    `forms.sch_d.compute` only if an 8949-required lot is actually encountered.
    """
    if cfg.has_foreign_accounts is None:
        raise ValueError(
            "Scenario config field `has_foreign_accounts` is required and must be "
            "either true or false. Schedule B Part III (Foreign Accounts and Trusts) "
            "is not implemented in tenforty v1; if any foreign financial account "
            "exists, this return will be INCORRECT and you may be legally required "
            "to file FinCEN Form 114 (FBAR). You must answer this question "
            "explicitly in every scenario."
        )
    if cfg.has_foreign_accounts is True:
        raise NotImplementedError(
            "Schedule B Part III / FBAR is not supported in tenforty v1. "
            "Returns for filers with foreign financial accounts cannot be produced "
            "by this version; support is tracked as a follow-up."
        )

    if cfg.acknowledges_sch_a_sales_tax_unsupported is None:
        raise ValueError(
            "Scenario config field `acknowledges_sch_a_sales_tax_unsupported` "
            "is required and must be either true or false. Schedule A line 5a "
            "offers a state-and-local INCOME TAX or GENERAL SALES TAX "
            "election; tenforty v1 implements only the income-tax path. For "
            "filers in no-state-income-tax states (TX, FL, WA, NV, SD, WY, "
            "AK, TN, NH) the sales-tax election is usually the correct "
            "choice and v1 cannot produce it. Set `false` if your state "
            "levies an income tax (the income-tax path is correct for you). "
            "Set `true` ONLY if you are in a no-income-tax state AND you "
            "have reviewed the consequences — v1 will then raise "
            "NotImplementedError from Sch A compute rather than silently "
            "overstating your deduction with an income-tax figure that is "
            "$0 or near-$0 in your state."
        )

    if cfg.acknowledges_form_8949_unsupported is None:
        raise ValueError(
            "Scenario config field `acknowledges_form_8949_unsupported` is required "
            "and must be either true or false. Form 8949 is not implemented in "
            "tenforty v1. Lots with uncovered basis, basis adjustments, or "
            "wash-sale reporting legally require Form 8949. Set `false` if all "
            "1099-B lots are covered-basis with no adjustments (Sch D summary "
            "path applies and the return is complete). Set `true` ONLY if you "
            "have reviewed any 8949-required lots and accept that they will be "
            "DROPPED from Sch D totals (a warning is logged per dropped lot so "
            "you can reconcile manually); your return will be INCOMPLETE for "
            "those lots until 8949 support lands."
        )

    # --- Plan D unconditional scope-out attestations (9) + prior_year_itemized ---
    if cfg.acknowledges_qbi_below_threshold is None:
        raise ValueError(
            "Scenario config field `acknowledges_qbi_below_threshold` is "
            "required and must be either true or false. Form 8995-A (full "
            "QBI) is not implemented in tenforty v1; if a K-1 carries QBI "
            "and taxable income exceeds the Rev. Proc. 2024-40 threshold "
            "(~$197,300 single / $394,600 MFJ), compute will raise "
            "NotImplementedError."
        )
    if cfg.acknowledges_unlimited_at_risk is None:
        raise ValueError(
            "Scenario config field `acknowledges_unlimited_at_risk` is "
            "required and must be either true or false. Form 6198 (at-risk "
            "limitations) is not implemented in tenforty v1; compute will "
            "raise NotImplementedError at Sch E Part II time if any K-1 is "
            "present and this attestation is False."
        )
    if cfg.basis_tracked_externally is None:
        raise ValueError(
            "Scenario config field `basis_tracked_externally` is required "
            "and must be either true or false. Shareholder/partner basis "
            "worksheets (Form 7203 for S-corps, partner basis worksheet "
            "for partnerships) are not implemented in tenforty v1; compute "
            "will raise NotImplementedError at Sch E Part II time if any "
            "K-1 is present and this attestation is False."
        )
    if cfg.acknowledges_no_partnership_se_earnings is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_partnership_se_earnings` "
            "is required and must be either true or false. Schedule SE is "
            "not implemented in tenforty v1; compute will raise "
            "NotImplementedError if a partnership K-1 carries nonzero "
            "partnership_self_employment_earnings and this attestation is "
            "False."
        )
    if cfg.acknowledges_no_section_1231_gain is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_section_1231_gain` is "
            "required and must be either true or false. Form 4797 (sales "
            "of business property) is not implemented in tenforty v1; "
            "compute will raise NotImplementedError if any K-1 carries "
            "nonzero section_1231_gain and this attestation is False."
        )
    if cfg.acknowledges_no_more_than_four_k1s is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_more_than_four_k1s` is "
            "required and must be either true or false. Schedule E Part II "
            "continuation sheets (for more than 4 K-1s) are not "
            "implemented in tenforty v1; compute will raise "
            "NotImplementedError if more than 4 K-1s are present and this "
            "attestation is False."
        )
    if cfg.acknowledges_no_k1_credits is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_k1_credits` is "
            "required and must be either true or false. K-1 box 13 "
            "(partnership) and box 15 (S-corp) credits are not "
            "implemented in tenforty v1; compute will raise "
            "NotImplementedError if this attestation is False and any K-1 "
            "is present."
        )
    if cfg.acknowledges_no_section_179 is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_section_179` is "
            "required and must be either true or false. The Section 179 "
            "deduction (Form 4562 Part I) flowing through from K-1s is "
            "not implemented in tenforty v1; compute will raise "
            "NotImplementedError if any K-1 carries nonzero "
            "section_179_deduction and this attestation is False."
        )
    if cfg.acknowledges_no_estate_trust_k1 is None:
        raise ValueError(
            "Scenario config field `acknowledges_no_estate_trust_k1` is "
            "required and must be either true or false. Schedule E Part "
            "III (estate and trust K-1 income) is not implemented in "
            "tenforty v1; compute will raise NotImplementedError if any "
            "K-1 has entity_type == 'estate_trust'. Declare this "
            "attestation even when no estate/trust K-1 is present."
        )
    if cfg.prior_year_itemized is None:
        raise ValueError(
            "Scenario config field `prior_year_itemized` is required and "
            "must be either true or false. It drives the 1099-G state-tax-"
            "refund tax-benefit-rule on Schedule 1 line 1: if the prior "
            "year used the standard deduction, the refund is not taxable; "
            "if itemized, it is taxable up to the recovery limit."
        )

    # --- Plan D conditional fields (validated only when sibling says yes) ---
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

    scenario = Scenario(config=config, **form_data)
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
