"""Translation spec: F1040 engine outputs → Pdf1040 PDF field keys.

Maps engine result keys (named after XLS named ranges) to the key
namespace used by the Pdf1040 PDF mapping (named after 1040 form lines).
"""

from tenforty.result_translator import TranslationSpec

F1040_PDF_SPEC = TranslationSpec(
    renames={
        "interest_income": "taxable_interest",
        "dividend_income": "ordinary_dividends",
    },
    expansions={
        "agi": ["agi", "agi_page2"],
        "federal_withheld": ["federal_withheld", "federal_withheld_w2"],
    },
)
