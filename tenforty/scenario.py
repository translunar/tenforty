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


def load_scenario(path: Path) -> Scenario:
    """Load a tax scenario from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    config = TaxReturnConfig(**data["config"])

    form_data: dict[str, list] = {}
    for yaml_key, (model_cls, field_name) in _FORM_REGISTRY.items():
        items = data.get(yaml_key, [])
        form_data[field_name] = [model_cls(**item) for item in items]

    return Scenario(config=config, **form_data)
