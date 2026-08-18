"""Form 4868 (Automatic Extension) compute.

Folds in the balance-due helper formerly at tenforty/filing/balance_due.py.
The 4868 line 6 balance due is clamped at zero: if payments >= tax, the
form reports no balance due (even for a refund case).

LINE 4 IS 1040 LINE 24. Not line 16, not line 18. The form's own instruction
(`pdfs/federal/2025/f4868.pdf`, heading "Line 4—Estimate of Total Tax
Liability for 2025") reads, verbatim:

    Enter on line 4 the total tax liability you expect to report on your
    2025:
    • Form 1040, 1040-SR, or 1040-NR, line 24; or
    • Form 1040-SS, Part I, line 7.
    If you expect this amount to be zero, enter -0-.

This module used to read `f1040["total_tax"]` RAW and use it for THREE
outputs: `estimated_total_tax` (line 4), `balance_due` (line 6) and
`voucher_amount` — the figure the filer actually pays. `total_tax` means 1040
LINE 16 on every path, so all three left out Schedule 2 in full. The error
direction is UNDERSTATEMENT: the filer is told to send less than they will
owe, which is the penalty-and-interest direction.
"""

# The F1040 OUTPUT key carrying the workbook's harvested 1040 line 24.
#
# THIS COMMENT USED TO WARN AGAINST CONFUSING IT WITH `total_tax_liability`,
# the *pdf_1040* field key for the same 1040 line, and said that key had no
# producer on either path, that line 24 printed blank on every emitted 1040,
# and that wiring it was a separate task. All of that is now out of date:
#
#   - `total_tax_liability` NO LONGER EXISTS. The duplicate pair was resolved
#     by renaming the PDF-mapping key to `tax_liability_line24` — this same
#     name — in every year block of `mappings/pdf_1040.py`. Pinned by
#     tests/test_1040_tax_band_native_producers.py::
#     Line24KeyNameReconciliationTests.
#   - Line 24 is PRODUCED ON BOTH PATHS, not blank. `Pdf1040.get_derivations`
#     fills the line-24 box by calling `total_tax_liability_line_24` below,
#     which harvests this key on the workbook path and composes on the native
#     one.
#
# WHAT REMAINS TRUE, and is the reason this constant still exists: this key is
# a WORKBOOK HARVEST and nothing else. It is deliberately NOT a native spine
# output key, because its PRESENCE is the discriminator that tells the two
# compute paths apart — here, and in `tests/invariants.py`. Publishing it from
# the spine would route native returns down the harvest branch and turn an
# independent-oracle comparison into a self-comparison. See
# `mappings/pdf_1040.py::Pdf1040.get_derivations` for the full argument and
# tests/test_1040_tax_band_native_producers.py::
# NativeResultsMustNotCarryTheLine24KeyTests for the assertion that holds it.
_LINE_24_KEY = "tax_liability_line24"


def compose_line_24(
    *,
    line_16: float,
    schedule_2_part_i: float,
    nonrefundable_credits: float,
    schedule_2_part_ii: float,
) -> float:
    """Build IRS Form 1040 line 24 (total tax) from its four parts.

    The vendor workbook's own arithmetic, verified in all five shipped
    workbooks (2021-2025) and pinned per-year by
    `tests/test_f1040_mapping.py::TestF1040TotalTaxLiabilityLine24`. Quoting
    the 2025 cells; the other four years are the same formulas at different
    addresses:

        AL102 (line 22) = IF(<override>, ..., MAX(0, SUM(Tax, -AL101)))
        AL103 (line 23) = TotalOtherTaxes
        AL104 (line 24) = SUM(AL102, AL103)

    where `Tax` is line 18 (line 16 + Schedule 2 Part I) and AL101 is line 21
    (total nonrefundable credits).

    THE ZERO FLOOR SITS ON (line 18 - credits) AND NOTHING ELSE. Schedule 2
    Part II is added AFTER it, never inside it. Applying the floor to the
    whole sum instead is wrong exactly when credits exceed line 18, and it
    errs by UNDERSTATING — it would swallow a Part II tax the filer genuinely
    owes, on a payment voucher. Order matters here; do not "simplify" it into
    a single max().
    """
    line_18 = line_16 + schedule_2_part_i
    line_22 = max(0, line_18 - nonrefundable_credits)
    return line_22 + schedule_2_part_ii


def total_tax_liability_line_24(f1040: dict) -> float | None:
    """Return IRS Form 1040 line 24 for this return, or None if unknowable.

    THE TWO PATHS ARE HANDLED DIFFERENTLY, DELIBERATELY.

    WORKBOOK PATH — HARVEST. The workbook computes line 24 itself and exposes
    it as the `Tot_Tax` named range, present in all five shipped workbooks
    (see mappings/f1040.py). We take that number whole rather than rebuild it
    from the keys sitting beside it, for three reasons:
      1. it inherits what the workbook ACTUALLY computes, not what we
         remembered to add;
      2. it cannot drift as the vendor moves cells, because it resolves by
         name; and
      3. composition is where the arithmetic goes wrong — see the floor trap
         in `compose_line_24`.

    NATIVE PATH — COMPOSE, and knowingly INCOMPLETE. The native spine now
    exposes 1040 LINE 17 as `schedule2_tax` and LINE 18 as `tax_plus_schedule2`
    (both are spine output keys, and this function composes from the line-17
    total). It still exposes NO key for lines 22, 23 or 24 — line 24 is
    produced at the PDF layer by `Pdf1040.get_derivations`, which calls this
    function, and is deliberately not a spine key (see `_LINE_24_KEY` above).
    So line 24 is built here from the parts the spine does produce. Say it that
    way round and it stays true as the remaining lines land: the earlier
    version of this sentence claimed the spine exposed no line-17/18/22/23/24
    key at all, which stopped being true for 17 and 18 the moment they landed.
    What the composition CANNOT include, stated plainly so this
    function's name does not overclaim (a total that does not contain what its
    name promises is the defect species this module was fixed to remove):

      - AMT (Form 6251, Schedule 2 line 1). The native spine does not compute
        it — there is no Form 6251 anywhere in the native path. The sibling
        `acknowledges_no_federal_amt` attestation is the guard for this; it is
        NOT YET LANDED as of this writing (a sibling task in the same unit
        lands it). Do not build a second guard here — reference that one.
      - NIIT (Form 8960, Schedule 2 line 12). The native spine does not
        compute it. THE WORKBOOK DOES: `'8960'!N48 F8960_Tax` flows through
        Schedule 2 into `TotalOtherTaxes` and thence into `Tot_Tax`, and the
        8960 named ranges exist in all five workbooks. So the HARVESTED line 4
        correctly includes NIIT while this COMPOSED one cannot. That asymmetry
        is tracked as ticket (s). It is not a defect introduced here — it is
        the harvest being more complete than the composition, which is itself
        the argument for harvesting.

    What is NOT a silent gap:
      - Self-employment tax. There is no Schedule C surface at all
        (`sch_1.py` hardcodes `business_income_line_3 = 0` and
        `self_employment_tax_deduction_line_15 = 0`), and partnership SE
        earnings are gated by the `acknowledges_no_partnership_se_earnings`
        attestation, which genuinely raises: its `triggered_when` is
        `_has_partnership_se_earnings` (a real predicate, not the load-time
        `_never` sentinel), so `attestations.enforce_compute_time` raises
        NotImplementedError when a partnership K-1 carries nonzero SE earnings
        and the attestation is False.
      - Nonrefundable credits. The native spine models NONE — no Schedule 3
        Part I, no child tax credit, no line 19/20/21 producer anywhere — so
        `nonrefundable_credits` reads 0 on that path and line 22 reduces to
        line 18. Omitting credits OVERSTATES liability, which is the
        conservative direction on a payment voucher, but it is still an
        overstatement and is stated here rather than assumed away. The key is
        read from the result dict (the same name `f1040x.py` uses for its line
        7) so that whenever a producer appears, line 4 picks it up.

    NO SEPARATE DIAGNOSTIC GUARD ON THE HARVESTED KEY. The workbook's refusal
    channel (`forms/f1040.py::workbook_refusal`) fires at harvest time, before
    any harvested tax figure reaches this module, for every MFJ/MFS filer.
    A guard here would be redundant; do not add one.

    Returns None when line 16 is missing entirely, so that the single, named
    failure comes out of `compute_balance_due` rather than as a bare TypeError
    from `None + 0` here.
    """
    harvested = f1040.get(_LINE_24_KEY)
    if harvested is not None:
        return harvested

    line_16 = f1040.get("total_tax")
    if line_16 is None:
        return None
    return compose_line_24(
        line_16=line_16,
        # Schedule 2 Part I — 1040 line 17, THE TOTAL, not a component of it.
        #
        # This read `f8962_repayment` (the excess-APTC repayment) until the
        # spine gained a canonical line-17 key. The two are equal today — the
        # spine literally assigns `schedule2_tax = f8962_repayment`, because
        # the repayment is the only Part I component it models — so this is
        # not a bug fix. It removes a LATENT one: the day AMT (the other Part
        # I component) or anything else joins `schedule2_tax`, a line 24 built
        # from the component would UNDERSTATE, on a payment voucher, with
        # nothing pointing at the divergence. Prefer the total to a component
        # that merely equals it today.
        schedule_2_part_i=f1040.get("schedule2_tax") or 0,
        # 1040 line 21. No producer emits this today; see the docstring.
        nonrefundable_credits=f1040.get("nonrefundable_credits") or 0,
        # Schedule 2 Part II: Form 8959 Additional Medicare Tax. NIIT, the
        # other modeled-by-the-workbook Part II component, is unmodeled here.
        schedule_2_part_ii=f1040.get("f8959_tax_total") or 0,
    )


def compute_balance_due(
    total_tax: float | None, total_payments: float | None,
) -> float:
    """Compute 4868 line 6 balance due, floored at zero.

    `total_tax` is 1040 LINE 24 (the 4868's own line 4), not line 16 — see
    `total_tax_liability_line_24`. The parameter keeps its historic name for
    callers; the quantity it must be given is total tax LIABILITY.

    RETURNS A FLOAT, not an int — this was annotated `-> int` and that was
    wrong. The native path passes whole-dollar ints (the spine `irs_round`s its
    outputs) but the WORKBOOK path passes the harvested `Tot_Tax`, which the
    engine reads out of the sheet as a float, so the difference is a float too.
    NO ROUNDING IS APPLIED HERE, deliberately: whole-dollar rendering is the
    PDF layer's job and happens in exactly one place for every numeric field
    (`filing/pdf.py::PdfFiller._render_scalar`, via `irs_round`). Rounding here
    as well would put a second, independently-driftable rounding decision on
    the payment path, and would also diverge from how every other harvested
    money key is handled (`forms/f1040.py` passes them through as harvested).
    `int` remains acceptable to this annotation under PEP 484's numeric tower.

    A `None` `total_tax` RAISES. It used to be coerced with `total_tax or 0`,
    which answered "you owe nothing" on a return whose tax we failed to
    compute — on the one form whose line 6 the filer pays from. That is the
    fail-open disease in its worst location, so it is a hard error naming the
    missing input. (`f1040x.py` also refuses a None here, but only INCIDENTALLY
    — its line-6 arithmetic raises a bare TypeError from `None + float`. A
    deliberate, named error is strictly more useful; f1040x's posture is left
    as-is by ruling.)

    A `None` `total_payments` is still treated as 0, and that asymmetry is
    deliberate: the engine legitimately returns None for 1099/other
    withholding fields when they do not apply, and a missing payment
    OVERSTATES the balance due — the safe direction on a payment form.
    """
    if total_tax is None:
        raise ValueError(
            "Form 4868 line 6 (balance due) cannot be computed: `total_tax` "
            "is None. This value is IRS Form 1040 line 24, the total tax "
            "liability, and it is the figure the filer pays from — line 6 "
            "and the payment voucher both derive from it. It is None because "
            "the upstream 1040 compute emitted no `total_tax` (and no "
            "`tax_liability_line24`) for this return. Refusing rather than "
            "treating it as 0, which would tell the filer they owe nothing."
        )
    payments = total_payments or 0
    balance = total_tax - payments
    return balance if balance > 0 else 0


def compute(scenario, upstream: dict[str, dict]) -> dict:
    """Compute Form 4868 fields in PDF-ready shape.

    `scenario` supplies identity and address fields. `upstream["f1040"]`
    supplies the 1040 result dict; compute derives line 4 (total tax
    liability, 1040 line 24 — see `total_tax_liability_line_24`), line 6
    (balance due, floored at zero), and the payment voucher amount.
    """
    f1040 = upstream.get("f1040", {})
    config = scenario.config
    estimated_total_tax = total_tax_liability_line_24(f1040)
    # Raises on a missing line 24, BEFORE any field is emitted — a partially
    # filled 4868 is worse than none.
    balance = compute_balance_due(estimated_total_tax, f1040.get("total_payments"))
    return {
        "full_name": config.full_name,
        "ssn": config.ssn,
        "spouse_ssn": config.spouse_ssn,
        "address": config.address,
        "address_city": config.address_city,
        "address_state": config.address_state,
        "address_zip": config.address_zip,
        "estimated_total_tax": estimated_total_tax,
        # Line 5 — "Estimate of Total Payments". The instruction is 1040 line
        # 33 "(excluding Schedule 3, line 10)", i.e. excluding any amount
        # already paid with a request for extension. We apply NO such
        # exclusion, and are compliant VACUOUSLY rather than by design: the
        # spine's `total_payments` is federal_withheld + estimated_payments +
        # f8962_net_ptc, no extension-payment field exists on any scenario
        # model, and nothing tenforty writes reaches the workbook's Schedule 3
        # extension row (which is label-only). THE DAY an extension-payment
        # input is added, 1040 line 33 picks it up and this line silently
        # violates the instruction. That latent condition is pinned by
        # tests/test_f4868_compute.py::ExtensionPaymentFieldAbsenceTests, which
        # fails when such a field appears.
        "total_payments": f1040.get("total_payments", 0),
        "balance_due": balance,
        "amount_paying_with_extension": 0,
        "voucher_amount": balance,
    }
