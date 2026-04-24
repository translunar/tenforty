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
    "sche_line26": "other_income",
    "federal_withheld": "federal_withheld_w2",
    "additional_medicare_withheld": "federal_withheld_other",
}

# Keys that are aliased: both the original oracle key and the PDF-ready name
# are preserved in the result. This allows downstream consumers (tests,
# native math) to read either name without a second lookup.
_ALIASES: dict[str, str] = {
    "schd_line16": "capital_gain_loss",
}

assert not (set(_RENAMES) & set(_ALIASES)), (
    f"Keys appear in both _RENAMES and _ALIASES: "
    f"{set(_RENAMES) & set(_ALIASES)}"
)


def compute(raw_1040: dict, upstream: dict[str, dict]) -> dict:
    """Translate raw engine output into a PDF-ready 1040 result dict."""
    translated: dict = dict(raw_1040)

    for old, new in _RENAMES.items():
        if old in translated:
            translated[new] = translated.pop(old)

    for old, new in _ALIASES.items():
        if old in translated:
            translated[new] = translated[old]

    if "agi" in translated:
        translated["agi_page2"] = translated["agi"]

    translated["federal_withheld"] = (
        (translated.get("federal_withheld_w2") or 0)
        + (translated.get("federal_withheld_1099") or 0)
        + (translated.get("federal_withheld_other") or 0)
    )

    # f8582_line_11_oracle passes through unchanged (XLSX oracle value).

    # Derive taxable income before the QBI deduction (Form 8995 line 11).
    # There is no single named range for this value in the workbook; it is
    # computed here as taxable_income + the 1040-line-13 QBI deduction.
    # The helper key _qbi_deduction_1040 is consumed and removed.
    qbi_deduction = translated.pop("_qbi_deduction_1040", None) or 0
    translated["taxable_income_before_qbi_deduction"] = (
        (translated.get("taxable_income") or 0) + qbi_deduction
    )

    return translated
