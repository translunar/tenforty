from collections.abc import Callable
from dataclasses import dataclass, field

from tenforty.models import Scenario


@dataclass
class TranslationSpec:
    """Defines how to translate engine output keys for a target form's PDF mapping.

    renames: one-to-one key translation (e.g., interest_income -> taxable_interest)
    expansions: one-to-many key expansion (e.g., agi -> [agi, agi_page2])
    scenario_fields: functions that extract values from the Scenario
                     (e.g., first_name -> lambda s: "John")
    """

    renames: dict[str, str] = field(default_factory=dict)
    expansions: dict[str, list[str]] = field(default_factory=dict)
    scenario_fields: dict[str, Callable[[Scenario], object]] = field(default_factory=dict)


class ResultTranslator:
    """Translates engine results into the key namespace expected by a PDF mapping."""

    def __init__(self, spec: TranslationSpec) -> None:
        self.spec = spec

    def translate(
        self,
        engine_results: dict[str, object],
        scenario: Scenario,
    ) -> dict[str, object]:
        result: dict[str, object] = {}

        # Start with scenario fields (lowest priority — engine overrides)
        for key, extractor in self.spec.scenario_fields.items():
            value = extractor(scenario)
            if value is not None:
                result[key] = value

        # Process engine results
        for key, value in engine_results.items():
            if value is None:
                continue

            if key in self.spec.expansions:
                for target_key in self.spec.expansions[key]:
                    result[target_key] = value
            elif key in self.spec.renames:
                result[self.spec.renames[key]] = value
            else:
                result[key] = value

        return result
