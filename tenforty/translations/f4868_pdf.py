"""Translation spec: F4868 engine outputs → Pdf4868 PDF field keys.

Maps engine result keys (named after XLS named ranges) to the key
namespace used by the Pdf4868 PDF mapping (named after 4868 form lines).
Identity and address fields come from the Scenario config, not the engine.
"""

from tenforty.result_translator import TranslationSpec

F4868_PDF_SPEC = TranslationSpec(
    renames={
        "total_tax": "estimated_total_tax",
    },
    scenario_fields={
        "full_name": lambda s: f"{s.config.first_name} {s.config.last_name}".strip(),
        "ssn": lambda s: s.config.ssn,
        "spouse_ssn": lambda s: s.config.spouse_ssn,
        "address": lambda s: s.config.address,
        "address_city": lambda s: s.config.address_city,
        "address_state": lambda s: s.config.address_state,
        "address_zip": lambda s: s.config.address_zip,
    },
)
