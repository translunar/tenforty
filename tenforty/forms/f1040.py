"""Form 1040 compute.

v1: consumes raw engine output from the reference XLSX (computed by the
orchestrator) and re-keys it to PDF-ready field names. A later plan will
port the 1040 math to native Python and make the XLSX oracle-only.

This module has no filesystem dependencies; the orchestrator owns engine
invocation and hands `compute` the raw result dict.
"""

_RENAMES: dict[str, str] = {
    "interest_income": "taxable_interest",
    "dividend_income": "ordinary_dividends",
    "schd_line16": "capital_gain_loss",
    "sche_line26": "other_income",
    "federal_withheld": "federal_withheld_w2",
    "additional_medicare_withheld": "federal_withheld_other",
}


def compute(raw_1040: dict, upstream: dict[str, dict]) -> dict:
    """Translate raw engine output into a PDF-ready 1040 result dict."""
    translated: dict = dict(raw_1040)

    for old, new in _RENAMES.items():
        if old in translated:
            translated[new] = translated.pop(old)

    if "agi" in translated:
        translated["agi_page2"] = translated["agi"]

    translated["federal_withheld"] = (
        (translated.get("federal_withheld_w2") or 0)
        + (translated.get("federal_withheld_1099") or 0)
        + (translated.get("federal_withheld_other") or 0)
    )

    # Derive taxable income before the QBI deduction (Form 8995 line 11).
    # There is no single named range for this value in the workbook; it is
    # computed here as taxable_income + the 1040-line-13 QBI deduction.
    # The helper key _qbi_deduction_1040 is consumed and removed.
    qbi_deduction = translated.pop("_qbi_deduction_1040", None) or 0
    translated["taxable_income_before_qbi_deduction"] = (
        (translated.get("taxable_income") or 0) + qbi_deduction
    )

    return translated
