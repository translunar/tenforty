from pathlib import Path

import yaml

from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
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
    "form1098s": (Form1098, "form1098s"),
    "schedule_k1s": (ScheduleK1, "schedule_k1s"),
    "rental_properties": (RentalProperty, "rental_properties"),
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

    return Scenario(config=config, **form_data)
