"""Translation spec: F1040 engine outputs → Pdf1040 PDF field keys.

Maps engine result keys (named after XLS named ranges) to the key
namespace used by the Pdf1040 PDF mapping (named after 1040 form lines).
"""

from tenforty.result_translator import TranslationSpec

F1040_PDF_SPEC = TranslationSpec(
    renames={
        "interest_income": "taxable_interest",
        "dividend_income": "ordinary_dividends",
        # Sch D line 16 = 1040 line 7 (capital gain or loss).
        "schd_line16": "capital_gain_loss",
        # Sch E line 26 flows via Sch 1 line 5 to Sch 1 line 10 to 1040 line 8.
        # Engine does not yet aggregate Schedule 1 line 10 — this rename works
        # for scenarios where Sch E is the only Sch 1 contributor. When other
        # Sch 1 income appears (unemployment, business, etc.) the engine must
        # grow a dedicated schedule_1_line_10 output.
        "sche_line26": "other_income",
        # Engine's federal_withheld is W-2 withholding only (25a). The 25d
        # total is computed in the orchestrator as 25a + 25b + 25c so that
        # other withholding sources (Form 8959, 1099, etc.) are included.
        "federal_withheld": "federal_withheld_w2",
        # Form 8959 Additional Medicare Tax withholding lands on 25c
        # ("other forms"). Correct only while Form 8959 is the sole 25c
        # contributor — e.g. a Schedule H household-employer payment would
        # also belong here and would need its own rename.
        "additional_medicare_withheld": "federal_withheld_other",
    },
    expansions={
        "agi": ["agi", "agi_page2"],
    },
)
