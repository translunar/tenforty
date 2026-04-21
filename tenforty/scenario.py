from pathlib import Path

import yaml

from tenforty.attestations import validate_load_time
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
