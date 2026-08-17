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
    "sch_1_line_10": "sch_1_line_10_total_additional_income",
    "sch_1_line_26": "sch_1_line_26_total_adjustments",
}

# NOT aliased: `schd_line16` -> `capital_gain_loss`.
#
# That alias copied the TRUE, UNCAPPED Schedule D line 16 total into
# `capital_gain_loss`, which pdf_1040 maps to 1040 line 7a. Line 7a is the
# IRC §1211(b)-CAPPED transfer from Schedule D line 21 ($3,000 / $1,500 MFS),
# so on any workbook-routed return with a net loss above the cap the emitted
# PDF printed the uncapped loss on line 7a while line 9 (total income) used
# the correctly capped figure — internally inconsistent.
#
# The workbook was right all along and we simply never read it: the
# `CapitalGains` named range holds the capped value in all five year
# workbooks, and is now wired as a first-class F1040 OUTPUT (mappings/f1040.py)
# instead of being back-filled from line 16 here. `schd_line16` REMAINS
# available under its own name — it is the real, uncapped line-16 total and has
# its own consumers (sch_d_540.py, __main__.py's summary, the e2e tests). This
# is the same capped/uncapped split the native spine already makes
# (f1040_spine.py emits `schd_line16` AND `capital_gain_loss` separately).
#
# BLANK/None: deliberately NOT normalized to 0, unlike _NUMERIC_SCH_1_KEYS
# below and the scoped `f8959_tax_total` coercion. The established contract for
# THIS key is that None means "leave 1040 line 7a blank": the native spine
# emits None on purpose when the value is zero (f1040_spine.py: "Omit (None)
# when zero so the PDF field stays blank for W-2-only scenarios"), filing/pdf.py
# skips None-valued fields, and sch_ca.compute's Col-A loop guards with a
# truthiness check (`if amount:`) before doing any arithmetic. So no consumer
# can TypeError on None, and coercing to 0 would instead PRINT "0" on line 7a
# for every W-2-only return and diverge from the native spine.
assert "capital_gain_loss" not in _ALIASES.values(), (
    "capital_gain_loss must come from the CapitalGains named range "
    "(F1040.OUTPUTS), not from an alias of the uncapped schd_line16"
)

assert not (set(_RENAMES) & set(_ALIASES)), (
    f"Keys appear in both _RENAMES and _ALIASES: "
    f"{set(_RENAMES) & set(_ALIASES)}"
)


# Numeric Sch 1 line keys whose underlying XLS cells may resolve to
# Python None (raw input cells, blank when no input given). Downstream
# consumers (Sch CA kernel auto-derive) do arithmetic on these values;
# None would TypeError. The rekey shim canonicalizes None -> 0 here so
# every consumer can rely on a numeric type.
_NUMERIC_SCH_1_KEYS: frozenset[str] = frozenset({
    "sch_1_line_1_taxable_refunds",
    "sch_1_line_3_business_income",
    "sch_1_line_4_other_gains",
    "sch_1_line_5_rental_re_royalty",
    "sch_1_line_6_farm_income",
    "sch_1_line_7_unemployment",
    # Both forms of line 10 and line 26 are aliased; coerce both so the
    # mirror invariant (short == long) holds even when the underlying
    # workbook cell returns None.
    "sch_1_line_10",
    "sch_1_line_10_total_additional_income",
    "sch_1_line_11_educator",
    "sch_1_line_13_hsa",
    "sch_1_line_15_se_tax",
    "sch_1_line_17_se_health",
    "sch_1_line_20_ira",
    "sch_1_line_21_student_loan_interest",
    "sch_1_line_26",
    "sch_1_line_26_total_adjustments",
})


def compute(raw_1040: dict, upstream: dict[str, dict]) -> dict:
    """Translate raw engine output into a PDF-ready 1040 result dict."""
    translated: dict = dict(raw_1040)

    for old, new in _RENAMES.items():
        if old in translated:
            translated[new] = translated.pop(old)

    for old, new in _ALIASES.items():
        if old in translated:
            translated[new] = translated[old]

    for key in _NUMERIC_SCH_1_KEYS:
        if translated.get(key) is None:
            translated[key] = 0

    # f8959_tax_total (Additional Medicare Tax, Sch 2 Part II line 11): the
    # workbook leaves cell F8959_Tax blank precisely when Additional Medicare
    # Tax does not apply, and the engine reads a blank cell as None; the native
    # spine always emits a number (f1040_spine.py; f8959_line_18 defaults to 0).
    # Normalize None -> 0 for parity so Sch 2 consumers (form_f1040x line 10)
    # get a number, not None. This mirrors the PTC money-key normalization in
    # orchestrator._compute_1040_via_workbook (f8962_net_ptc / f8962_repayment,
    # ~orchestrator.py:773); it lives HERE instead of that workbook shim because
    # f1040.compute is a native-testable pure dict transform. Scoped to this ONE
    # key — blank provably means zero here — NOT a general blank-coercion.
    if translated.get("f8959_tax_total") is None:
        translated["f8959_tax_total"] = 0

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
    # The helper key _qbi_deduction_1040 is consumed, normalized, and
    # re-emitted for key uniformity (below).
    qbi_deduction = translated.pop("_qbi_deduction_1040", None) or 0
    translated["taxable_income_before_qbi_deduction"] = (
        (translated.get("taxable_income") or 0) + qbi_deduction
    )

    # Line 14 = "Add lines 12(c) and 13". The WORKBOOK's total_deductions is
    # already 14-inclusive (= 12c + QBI), unlike the native spine's (12c only).
    # Normalize to the native 12c-exclusive semantics so line 14, line 12c
    # (2021), and 1040-X line 2 are all correct on the oracle path.
    translated["deductions_plus_qbi"] = translated.get("total_deductions") or 0
    translated["total_deductions"] = translated["deductions_plus_qbi"] - qbi_deduction
    translated["qbi_deduction"] = qbi_deduction
    # Re-emit _qbi_deduction_1040 (the oracle-facing name) with the NORMALIZED
    # value so this path matches the native spine, which always emits it
    # (f1040_spine.py). form_f1040x consumes it for 1040-X line 4a on BOTH
    # paths; using .get()-instead-of-pop would instead leave the RAW workbook
    # value — None when QBID_1040 is blank — diverging from the native 0.0
    # (the same path-split Bug #6 fixed under a different key). Re-emit keeps
    # the two paths uniform.
    translated["_qbi_deduction_1040"] = qbi_deduction

    # Form 1040 line 12 — the deduction actually applied (std or itemized).
    # The workbook exposes the standard amount (standard_deduction) and the
    # itemized total (schedule_a_total) separately; the larger is what the
    # filer takes. The line-12 PDF cell reads this (see pdf_1040 f2_02),
    # mirroring the native spine's `applied_deduction`.
    translated["applied_deduction"] = max(
        translated.get("standard_deduction") or 0,
        translated.get("schedule_a_total") or 0,
    )

    return translated
