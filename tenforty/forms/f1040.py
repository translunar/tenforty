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


# --- The workbook's refusal channel -----------------------------------------
#
# The vendor sheet does not only COMPUTE. It DETECTS incomplete input and says
# so, writing a plain-English diagnostic into the `Deduction` named range and
# refusing to stand behind the figures below it. Harvesting those figures
# without reading the diagnostic is reading a REFUSAL as data, and that is what
# this guard stops.
#
# WHAT THE SHEET ACTUALLY DOES DIFFERS BY BRANCH — do not over-generalize this,
# and see the per-branch note below. On the `Birthday_Needed` and
# `FilingStatusError` branches it BLANKS `Tax_SubTotal` (Form 1040 LINE 16,
# tenforty's `total_tax`) outright. On the two remaining FILING-STATUS branches
# it leaves line 16 computing but zeroes line 12, so line 16 is derived from a
# base the sheet itself flagged as unusable. On `Manual Override` it does
# NEITHER: lines 12 and 16 both compute exactly as they would on a clean
# return, and we refuse because we cannot tell what that sheet state means —
# not because the figures are known to be tainted. Refusing is right in all
# five cases; only the reason differs.
#
# `Deduction` is the line-12 CAPTION cell, and it is NEVER EMPTY. Its IF-chain
# has ELEVEN branches — five diagnostics and six ordinary labels — so "refuse on
# any non-empty string" would refuse every return ever computed. The refusal
# rule is therefore an ALLOWLIST OF LABELS, which is what fail-closed means for
# a cell of this shape: anything that is not a known label refuses, including a
# string nobody here has seen before. Refusing only on strings we recognise
# would reproduce, at smaller scale, the original defect — the sheet says
# something and we decide it is not worth listening to.
#
# THE FIVE DIAGNOSTIC BRANCHES (verbatim, identical in all five workbooks),
# with what each one actually does to the figures:
#   "Manual Override"           <- a hand-entered override cell tenforty never
#                                  writes. It is a DIFFERENT CELL EACH YEAR, so
#                                  listing them per year rather than as a slash
#                                  run is what makes a missing year visible:
#                                    2021 AM46   (caption `'1040'!$AJ$51`)
#                                    2022 AM56   (caption `'1040'!$AJ$58`)
#                                    2023 AN62   (caption `'1040'!$AK$64`)
#                                    2024 AN65   (caption `'1040'!$AK$67`)
#                                    2025 AX78   (caption `'1040'!$AU$91`)
#                                  Lines 12 and 16 BOTH still compute; see the
#                                  note below on why the caption does not even
#                                  establish that line 12 was overridden.
#   "Filing status error."      <- FilingStatusError (NumFileStatusBoxes>1).
#                                  BLANKS `Tax_SubTotal`; zeroes line 12.
#   "Birthdate(s) needed."      <- Birthday_Needed.
#                                  BLANKS `Tax_SubTotal`; zeroes line 12.
#   "Filing status error or invalid spouse input."  <- $AL$9/$AV$10/$BF$12.
#                                  Zeroes line 12 only; line 16 still computes.
#   "Filing status not indicated."  <- NumFileStatusBoxes=0.
#                                  Zeroes line 12 only; line 16 still computes.
# Only the middle two appear in `Tax_SubTotal`'s own guard
# (`IF(OR(Birthday_Needed,FilingStatusError),"", ...)`); the `Deductions`
# (plural, line-12 AMOUNT) guard is wider and covers four of the five. So the
# caption is the widest signal available and the right thing to key on.
# "Manual Override" is UNREACHABLE — tenforty never writes the override cells —
# but it is deliberately NOT special-cased, for the reason above. Note also
# that the caption's override cell is NOT the amount's override cell: 2022
# (`'1040'!$AC$58`) and 2023 (`'1040'!$AD$64`) give `Deductions` no override
# arm at all, and the three years that have one read a DIFFERENT cell from the
# caption (2021 AM48 vs AM46, 2024 AN67 vs AN65, 2025 AX91 vs AX78). So a
# "Manual Override" caption is evidence about an unrecognised sheet state, not
# evidence that the line-12 AMOUNT was overridden.
#
# THE SIX LABEL BRANCHES, which must NOT refuse (seven strings — one branch is
# worded differently in 2025 than in 2021-2024). Matched by EQUALITY after
# normalization, except the two marked PREFIX:
#   "Standard Deduction"
#   "Standard deduction plus net qualified disaster losses\non Sch. A, Line 16."
#   "Schedule A"
#   "See Standard \n Deduction Chart\n at right  →"        PREFIX (2021-2024)
#   "See Standard \n Deduction Calculation\n at right  →"  PREFIX (2025)
#   "Line 12a - Standard Deduction for Dependents"
#   "Deduction is $0 due to spouse itemizing or dual-status alien."
#
# WHY EQUALITY, AND WHY THE TWO EXCEPTIONS ARE EXCEPTIONS. A short prefix is a
# hole in a fail-closed allowlist: matching on the prefix "schedule a" would
# silently wave through a future vendor diagnostic like "Schedule A required —
# attach…", re-opening this very defect on a narrower surface. Equality closes
# that: anything the vendor rewords or extends refuses loudly. The two
# "See Standard …" labels are the only ones that cannot use equality, because
# they alone carry a trailing "  →" — a non-ASCII glyph after a doubled space,
# assembled in-sheet from CHAR(10)s — and I cannot verify what the LibreOffice
# recalc round-trip does to those bytes without launching soffice. Their
# prefixes stop BEFORE the arrow and are long and specific ("see standard
# deduction chart" / "… calculation"), so the hole is confined to a rewording
# that keeps that entire phrase as its opening. Normalization (whitespace
# collapsed, casefolded) is applied to both arms, which is what lets the
# CHAR(10)-joined disaster-loss label match by equality at all.
#
# No diagnostic branch equals or is prefixed by any label branch, so the
# allowlist cannot swallow a known refusal.
#
# `Schedule2_Tax` (line 17) is NOT gated by `Birthday_Needed` — its blank is
# definitional and IS coerced to 0 below. That contrast is the whole rule:
# coerce when the CELL ITSELF defines blank as zero; refuse when some
# diagnostic upstream declined to answer.
_DEDUCTION_DIAGNOSTIC_KEY = "deduction_diagnostic"

_DEDUCTION_LABELS: frozenset[str] = frozenset({
    "standard deduction",
    "standard deduction plus net qualified disaster losses "
    "on sch. a, line 16.",
    "schedule a",
    "line 12a - standard deduction for dependents",
    "deduction is $0 due to spouse itemizing or dual-status alien.",
})

# Prefix-matched ONLY because of the trailing "  →"; see above.
_DEDUCTION_LABEL_PREFIXES: tuple[str, ...] = (
    "see standard deduction chart",
    "see standard deduction calculation",
)

_REFUSAL = (
    "The 1040 workbook DECLINED to compute this return. Its `Deduction` named "
    "range — the Form 1040 line-12 caption cell — reads {diagnostic!r}, which "
    "is not one of the deduction-source captions it carries on a return the "
    "sheet was willing to compute. That is the sheet declining to stand behind "
    "the figures below line 12, so tenforty declines to emit them.\n"
    "\n"
    "WHAT THE SHEET DID depends on which diagnostic this is. On the "
    "`Birthday_Needed` and `FilingStatusError` branches it zeroes line 12 (the "
    "applied deduction) AND blanks `Tax_SubTotal` — Form 1040 LINE 16, "
    "tenforty's `total_tax` — which the engine reads as None; refusing is what "
    "keeps that blank from being read as zero, which would answer \"your tax "
    "is zero\" on a real return. On the two FILING-STATUS branches line 16 "
    "still computes, but off a line 12 the sheet has zeroed, so the number is "
    "derived from a base the sheet itself flagged. On `Manual Override` the "
    "sheet disturbs NEITHER line — lines 12 and 16 both compute normally, and "
    "the caption does not even establish that line 12 was overridden, because "
    "it tests a different cell from the one the line-12 amount reads (and in "
    "2022 and 2023 that amount has no override arm at all). We refuse there "
    "because we do not know what that sheet state means, NOT because those "
    "figures are known to be tainted: an unrecognised state is exactly when "
    "guessing is worst. In none of these cases are the figures ours to "
    "publish.\n"
    "\n"
    "CAUSE: for MARRIED_JOINTLY and MARRIED_SEPARATE — which is every return "
    "that reaches this refusal today — tenforty supplies no spouse birthdate "
    "at all, so the workbook's `Birthday_Needed` flag is unconditionally TRUE "
    "and this diagnostic always fires. REMEDY: the spouse-birthdate unit adds "
    "that input and lifts this refusal. There is no scenario-side workaround, "
    "and none is wanted: the figures at and below line 12 were never right for "
    "this population, so this refusal converts a silently WRONG return into a "
    "loudly REFUSED one. It does not make the return computable.\n"
    "\n"
    "ON THE TWO BLANKING BRANCHES this refusal ALSO protects lines 17 and 18, "
    "which that same blank corrupts WITHOUT their going blank themselves and "
    "so without any other signal that they are wrong. Form 6251 takes "
    "`Tax_SubTotal` as a SUM operand in EVERY year, 2021 through 2025; 2025 "
    "ADDITIONALLY routes it through "
    "`'6251'!M59 = IF(Tax_SubTotal=\"\",0,Tax_SubTotal)`, an explicit coercion "
    "ALONGSIDE its SUM-operand reference rather than a replacement for it. "
    "Both paths take the blank as 0; that understates regular tax and "
    "OVERSTATES the AMT, so line "
    "17 (`schedule2_tax`) harvests a wrong NONZERO number on an AMT-bearing "
    "return. Line 18 is worse: `Tax` is `SUM(Tax_SubTotal, <line-17 cell>)` "
    "and spreadsheet SUM() IGNORES text, so a refused line 16 is silently "
    "SKIPPED and line 18 prints a plausible number that omits its own line-16 "
    "component — a mislabeled partial total."
)


def workbook_refusal(harvested: dict) -> str | None:
    """Return a refusal message if the workbook declined to compute, else None.

    The decision, deliberately separated from `compute` and from any workbook
    run: it is a pure function of a harvested dict, so it is exercisable with
    an injected dict and therefore VISIBLE to the standard `-m "not oracle"`
    gate. The oracle tier is deselected by that invocation, so a guard
    reachable only through a real LibreOffice recalc is invisible to every gate
    this branch reports — which is precisely how the defect it guards survived.

    Passes when the key is ABSENT. That is required, not an oversight: a
    missing key is indistinguishable from a caller that does not harvest one,
    and a guard that fires unconditionally is indistinguishable from a broken
    pipeline. The harvest itself is pinned per-year by
    tests/test_f1040_mapping.py, which is what would catch a lost mapping.
    """
    diagnostic = harvested.get(_DEDUCTION_DIAGNOSTIC_KEY)
    if diagnostic is None:
        return None
    normalized = " ".join(str(diagnostic).split()).casefold()
    if not normalized:
        return None
    if normalized in _DEDUCTION_LABELS:
        return None
    if normalized.startswith(_DEDUCTION_LABEL_PREFIXES):
        return None
    return _REFUSAL.format(diagnostic=diagnostic)


def compute(raw_1040: dict, upstream: dict[str, dict]) -> dict:
    """Translate raw engine output into a PDF-ready 1040 result dict."""
    translated: dict = dict(raw_1040)

    # Listen to the workbook's refusal BEFORE translating anything. Sited here
    # for the same reason as the `schedule2_tax` normalization below: `compute`
    # is a pure dict transform with exactly one caller
    # (orchestrator._compute_1040_via_workbook) and no workbook dependency, so
    # the guard stays testable — and therefore gate-visible — without soffice.
    # The diagnostic is CONSUMED, not forwarded: it is a harvest-time control
    # value, not a result, and it is the one OUTPUT that holds a string, so
    # letting it travel onward would put a caption where every downstream
    # consumer expects money.
    refusal = workbook_refusal(translated)
    translated.pop(_DEDUCTION_DIAGNOSTIC_KEY, None)
    if refusal is not None:
        raise NotImplementedError(refusal)

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

    # schedule2_tax (1040 line 17 = Schedule 2 line 3, "Add lines 1z and 2"):
    # normalize a blank harvest to numeric 0 so line 17 prints "0" in all five
    # years. The `Schedule2_Tax` named range's formula DRIFTED between vendor
    # workbooks — 2021-2023 fall through to a plain `SUM(...)` (numeric 0 when
    # Part I is empty), 2024-2025 wrap the same sum in
    # `IF(SUM(...)>0, SUM(...), "")` and go blank instead. The engine reads a
    # blank cell as None and filing/pdf.py renders 0 but SKIPS None, so absent
    # this coercion an empty Schedule 2 Part I prints "0" on a 2023 1040 and
    # nothing on a 2024 one. We impose the convention on the read side rather
    # than let vendor formula drift reach a filed form.
    #
    # WHY THIS COERCION IS SAFE — both halves are load-bearing:
    #   1. The cell's OWN formula defines blank AS zero. `IF(SUM>0, SUM, "")`
    #      emits "" exactly where the sum is not positive, and the sum cannot
    #      go negative, so blank means exactly 0. Its two addends are line 1z
    #      and line 2. Line 2 is the Form 6251 AMT, non-negative by
    #      construction (the 6251 bottom line is `MAX(0, ...)`, and the `AMT`
    #      named range wraps it in `IF(<cell>="",0,<cell>)`; the row number
    #      DRIFTS by year — '6251'!M62 in 2021, M63 in 2022-2024, M64 in 2025
    #      — so match on the named range, not an address). Line 1z is a SUM of
    #      SEVEN operands, not two: the 8962 excess-APTC repayment plus six
    #      raw input cells ('Sch. 2'!Z15/Z18/Z19/Z23/Z29/Z32 — Schedule A
    #      (Form 8936) recapture, Form 4255 net-EPE recapture, and other
    #      additions to tax). All six are empty in the shipped workbooks and
    #      tenforty writes none of them; every one is an ADDITION to tax, and
    #      the excess-APTC repayment is a repayment amount, so none can be
    #      negative. The blank is not missing data — it is the vendor's way of
    #      WRITING zero, and normalizing recovers the cell's stated meaning.
    #   2. NO DIAGNOSTIC BLANKS THIS CELL. `Schedule2_Tax` ('Sch. 2'!AC13 in
    #      2021-23, 'Sch. 2'!AD35 in 2024-25) is not one of the five cells
    #      gated by the workbook's `Birthday_Needed` flag — those five all live
    #      on the '1040' sheet — so a blank here is never a REFUSAL in
    #      disguise, which is the only property this coercion depends on.
    #
    #      That is NOT the same as saying no diagnostic REACHES this cell.
    #      `Birthday_Needed` reaches it TRANSITIVELY through Form 6251:
    #      the 6251 regular-tax line takes `Tax_SubTotal` as an operand
    #      (`SUM(Tax_SubTotal, PTC_ExcessAdv, -...)` in 2021-2024; routed
    #      through '6251'!M59 = `IF(Tax_SubTotal="",0,Tax_SubTotal)` in 2025),
    #      and AMT = `MAX(0, tentative_minimum_tax - regular_tax)` feeds line
    #      2. So on an MFJ/MFS return WITH AMT, the `Birthday_Needed`-blanked
    #      `Tax_SubTotal` is summed as 0, understating regular tax, which
    #      OVERSTATES the AMT and makes line 17 harvest a WRONG NONZERO
    #      number. This coercion neither causes nor cures that — it only ever
    #      fires on a blank, and blank still means zero — but do not read
    #      point 2 as a guarantee that line 17's VALUE is trustworthy on
    #      MFJ/MFS. It guarantees only that its BLANK is not a refusal.
    #
    # THIS IS NOT A PRECEDENT FOR `None -> 0` ANYWHERE ELSE, and specifically
    # NOT for `total_tax` / `Tax_SubTotal`, which is the visually identical
    # coercion one line away in meaning and a serious defect. `Tax_SubTotal`
    # IS one of the five `Birthday_Needed`-gated cells, and that flag is
    # unconditionally TRUE for every MFJ/MFS return (tenforty has no
    # spouse-birthdate concept). Its blank therefore means "the workbook
    # REFUSED to compute your tax", and writing 0 there would silently answer
    # "your tax is zero" on a real return. `total_tax` is handled the opposite
    # way — refuse loudly at harvest, never coerce; that refusal is
    # `workbook_refusal` above, reading the diagnostic the sheet writes into
    # the `Deduction` named range whenever it blanks this cell. The two blocks
    # are a matched pair, not two opinions about blanks. The distinction is not
    # stylistic: the test for a blank is whether the CELL ITSELF defines blank
    # as zero (coerce) or whether some diagnostic upstream declined to answer
    # (refuse). Do not cite this block for a cell in the second category.
    #
    # Deliberately NOT extended to `tax_plus_schedule2` (1040 line 18, the
    # `Tax` named range) — and NOT because it might be blank. `Tax` is NEVER
    # blank: its else-arm is unconditionally `SUM(Tax_SubTotal, <line-17
    # cell>)`, and spreadsheet SUM() IGNORES text in referenced cells, so a
    # refused `Tax_SubTotal = ""` is silently SKIPPED rather than propagated
    # and `Tax` always evaluates to a number. That is the hazard: on the
    # workbook path today, every MFJ/MFS return makes line 18 a plausible
    # number that OMITS ITS OWN LINE-16 COMPONENT — a mislabeled partial
    # total, the exact species this unit exists to remove. `None` would have
    # been the safer failure; the workbook denies us even that. So a populated
    # line 18 is NOT evidence that line 18 is correct, and no normalization
    # here could make it so.
    if translated.get("schedule2_tax") is None:
        translated["schedule2_tax"] = 0

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
