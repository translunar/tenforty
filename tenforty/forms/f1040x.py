"""Form 1040-X (Rev. December 2025) three-column assembler.

Pure functions — no year branches, no orchestrator import. Consumes an
as-filed results dict (Column A) and an already-computed corrected results
dict (Column C), both keyed by the ``f1040_spine`` result-dict names, plus
an :class:`AmendmentCase` for the narrative and original-overpayment context.
Produces the 1040-X line values (Task 7 handles orchestration + PDF fill).

Column convention (certified from the Dec-2025 render, per
``docs/plans/amended-returns-probe-tables.md``):
  A = Original amount (as filed)   C = Correct amount   B = Net change = C - A
The three-column grid applies to lines 1-15 ONLY; lines 16-23 are single
final-amount columns.

LINE DISPOSITION (Dec-2025 revision)
------------------------------------
Three-column, SOURCED from spine keys:
  L1  AGI                     <- agi
  L2  deductions              <- total_deductions
  L4a QBI deduction           <- _qbi_deduction_1040
  L5  taxable income          <- taxable_income
  L6  tax                     <- total_tax + f8962_repayment (Sch 2 Part I;
                                  the excess-APTC repayment, Sch 2 line 2, per
                                  "Include on line 6 the amount you reported on
                                  Schedule 2 (Form 1040), line 3")
  L7  nonrefundable credits   <- nonrefundable_credits (still guarded
                                  out-of-scope below; sourced explicitly so
                                  the printed L8 arithmetic holds)
  L10 other taxes             <- f8959_tax_total (Sch 2 Part II total other
                                  taxes; unmodeled Part II components, e.g.
                                  NIIT/SE tax, remain guarded via other_taxes)
  L12 withholding             <- federal_withheld
  L13 estimated tax payments  <- estimated_tax_payments (OPTIONAL, .get(...,
                                  0.0) on both columns — the federal spine's
                                  line-26 verbatim channel; old filed files
                                  that predate the spine wiring omit the key)
  L15 total payments          <- total_payments
Three-column, COMPUTED subtotal (on-form):
  L3  = L1 - L2   (per column)
  L8  = L6 - L7   (per column)
  L11 = L8 + L10  (per column; L9 is reserved/never filled)
Single-column, COMPUTED tail (see _tail):
  L16..L23 — keyed off the COMPUTED L11 column-C value (L8c + L10c), not a
  bare ``corrected["total_tax"]``, so the owed/refund tail stays consistent
  with the emitted L11.
SKIPPED — reserved:
  L9  "Reserved for future use" (shaded; fields exist but are never mapped).
INTENTIONALLY UNMAPPED (guarded out-of-scope — see _OUT_OF_SCOPE_FILED_KEYS):
  L4b Schedule 1-A (tips/overtime/car-loan-interest/seniors, TY2025)
  L7  nonrefundable credits (sourced as 0/0 in practice — a nonzero FILED
      value already refuses via the guard before this line is reached)
  L14 EIC
tenforty does not source these; the guard raises OutOfScopeAmendmentError if
the FILED return carried a nonzero value for one, rather than emitting a wrong
blank Column A.
"""

from tenforty.amendment import MissingFiledValueError, OutOfScopeAmendmentError
from tenforty.models import AmendmentCase
from tenforty.rounding import irs_round

# Column-A source keys the assembler consumes. Every one must be present in
# the filed dict (a missing one is a MissingFiledValueError — never defaulted).
REQUIRED_FILED_KEYS: tuple[str, ...] = (
    "agi",
    "total_deductions",
    "_qbi_deduction_1040",
    "taxable_income",
    "total_tax",
    "federal_withheld",
    "total_payments",
)

# Amount-bearing 1040-X lines tenforty does NOT source. If the FILED dict
# carries a nonzero value under any of these, refuse: a blank Column A would
# silently drop a real filed amount. Absent or zero -> proceed normally.
_OUT_OF_SCOPE_FILED_KEYS: dict[str, str] = {
    "schedule_1a_deduction": "line 4b (Schedule 1-A tips/overtime/car-loan/seniors)",
    "nonrefundable_credits": "line 7 (nonrefundable credits)",
    "other_taxes": "line 10 (other taxes)",
    "earned_income_credit": "line 14 (earned income credit)",
}


def _require_filed_keys(filed: dict) -> None:
    """Re-raise the Task-1 guard: every REQUIRED_FILED_KEYS member must be
    present. Never substitute a default for a missing as-filed figure."""
    missing = [k for k in REQUIRED_FILED_KEYS if k not in filed]
    if missing:
        raise MissingFiledValueError(
            f"Filed-values dict is missing required key(s): {sorted(missing)}. "
            f"Refusing to substitute a default — supply the as-filed figure "
            f"for each of {list(REQUIRED_FILED_KEYS)}."
        )


def _guard_out_of_scope(filed: dict) -> None:
    """Refuse if the filed return carried an amount on a line we cannot source."""
    for key, label in _OUT_OF_SCOPE_FILED_KEYS.items():
        if filed.get(key):  # nonzero / truthy
            raise OutOfScopeAmendmentError(
                f"Filed return carries a nonzero value on {label} "
                f"(filed[{key!r}] = {filed[key]}); tenforty cannot source this "
                f"1040-X line, so it cannot faithfully reproduce Column A. "
                f"Refusing to emit a blank/zero that would drop the filed amount."
            )


def _guard_original_overpayment(filed: dict, case: AmendmentCase) -> None:
    """IF the filed dict carries an ``"overpaid"`` key (the original federal
    overpayment — NOT a REQUIRED_FILED_KEYS member, checked if-present only),
    machine-check that the case describes the SAME as-filed-or-as-last-adjusted
    snapshot: the case's stated original overpayment (line 18 = received +
    applied) must EXACTLY equal it. Absence of the key is fine (no check);
    contradiction is not. The tail's net-owed/refund invariant holds only under
    this equality — this converts it from a documented assumption to a machine
    check."""
    if "overpaid" not in filed:
        return
    stated = irs_round(case.original_refund_received + case.original_refund_applied)
    filed_overpay = filed["overpaid"]
    if stated != filed_overpay:
        raise ValueError(
            f"1040-X consistency: case states original overpayment {stated} "
            f"but the filed return shows {filed_overpay}. Filed values and the "
            f"amendment case must describe the same as-filed-or-as-last-adjusted "
            f"snapshot."
        )


def _triple(out: dict, line: str, a: float, c: float) -> None:
    """Emit an A/B/C triple with B = C - A (so A + B == C by construction)."""
    out[f"f1040x_line{line}_a"] = a
    out[f"f1040x_line{line}_b"] = c - a
    out[f"f1040x_line{line}_c"] = c


def assemble(filed: dict, corrected: dict, case: AmendmentCase) -> dict:
    """Assemble Form 1040-X line values from filed + corrected results dicts.

    ``filed`` supplies Column A (whole-dollar as-filed figures); ``corrected``
    supplies Column C (already rounded by the spine — trusted, not re-rounded);
    Column B is C - A. Lines 16-23 are single-column amounts derived per the
    form's printed arithmetic. ``case`` supplies the original-return overpayment
    (line 18), the Part II explanation, and the amended year.

    The tail's net-owed/refund invariant (line 20/22 tracking corrected total
    tax against original payments net of the original overpayment) HOLDS ONLY
    when the case's stated original overpayment equals the filed return's
    original overpayment; when the filed dict carries an ``"overpaid"`` key,
    ``_guard_original_overpayment`` makes that precondition a machine check
    rather than a documented assumption.
    """
    _require_filed_keys(filed)
    _guard_out_of_scope(filed)
    _guard_original_overpayment(filed, case)

    out: dict = {}

    # ----- Three-column grid (lines 1-15 we source) -----------------------
    # L1 AGI, L2 deductions.
    _triple(out, "1", filed["agi"], corrected["agi"])
    _triple(out, "2", filed["total_deductions"], corrected["total_deductions"])
    # L3 = L1 - L2 (on-form subtotal, per column). B = C - A holds by build.
    a3 = filed["agi"] - filed["total_deductions"]
    c3 = corrected["agi"] - corrected["total_deductions"]
    _triple(out, "3", a3, c3)
    # L4a QBI deduction.
    _triple(out, "4a", filed["_qbi_deduction_1040"], corrected["_qbi_deduction_1040"])
    # L5 taxable income.
    _triple(out, "5", filed["taxable_income"], corrected["taxable_income"])
    # L6 tax = 1040 line 16 tax + Schedule 2 Part I (excess-APTC repayment).
    a6 = filed["total_tax"] + filed.get("f8962_repayment", 0.0)
    c6 = corrected["total_tax"] + corrected.get("f8962_repayment", 0.0)
    _triple(out, "6", a6, c6)
    # L7 nonrefundable credits — still guarded out-of-scope (a nonzero FILED
    # value already refused above via _guard_out_of_scope); sourced
    # explicitly so the printed L8 arithmetic holds.
    a7 = filed.get("nonrefundable_credits", 0.0)
    c7 = corrected.get("nonrefundable_credits", 0.0)
    _triple(out, "7", a7, c7)
    # L8 = L6 - L7 (on-form subtotal, per column).
    a8 = a6 - a7
    c8 = c6 - c7
    _triple(out, "8", a8, c8)
    # L10 other taxes = Schedule 2 Part II total (f8959 Additional Medicare
    # Tax is the modeled component; unmodeled Part II components remain
    # guarded via the other_taxes filed key).
    a10 = filed.get("f8959_tax_total", 0.0)
    c10 = corrected.get("f8959_tax_total", 0.0)
    _triple(out, "10", a10, c10)
    # L11 = L8 + L9(reserved, never filled) + L10 (on-form subtotal).
    a11 = a8 + a10
    c11 = c8 + c10
    _triple(out, "11", a11, c11)
    # L12 withholding.
    _triple(out, "12", filed["federal_withheld"], corrected["federal_withheld"])
    # L13 estimated tax payments. OPTIONAL — .get(..., 0.0) on both columns,
    # mirroring the f8962_repayment pattern above: old filed files predate
    # this key (they predate the spine wiring the estimated-payments channel).
    _triple(
        out,
        "13",
        filed.get("estimated_tax_payments", 0.0),
        corrected.get("estimated_tax_payments", 0.0),
    )
    # L15 total payments.
    _triple(out, "15", filed["total_payments"], corrected["total_payments"])

    # ----- Single-column tail (lines 16-23) -------------------------------
    # Keyed off the COMPUTED L11 column-C value (c8 + c10), not a bare
    # corrected["total_tax"], so the owed/refund tail stays consistent with
    # the emitted L11.
    out.update(_tail(corrected, case, c11))

    # ----- Narrative / year (Part II + page-1 write-in) -------------------
    out["f1040x_explanation"] = case.explanation
    out["f1040x_amended_year"] = case.year
    return out


def _tail(corrected: dict, case: AmendmentCase, line11_c: float) -> dict:
    """Lines 16-23, transcribed from the 1040-X printed arithmetic.

    Source: docs/plans/amended-returns-probe-tables.md, "Single-column lines
    16-23" table (Form 1040-X Rev. Dec 2025):
      L16 Total amount paid with extension / with original / after filing
      L17 Total payments  = (lines 12-15 col C) + L16
      L18 Overpayment on original return / as adjusted by IRS
      L19 Subtract L18 from L17
      L20 Amount you owe   = L11(col C) - L19   when L11c > L19
      L21 Overpaid on this return = L19 - L11(col C)   when L11c < L19
      L22 Amount of L21 refunded to you
      L23 Amount of L21 applied to next-year estimated tax

    total_payments now includes the estimated-payments channel (federal
    withholding + estimated tax payments + net PTC, per the spine wiring),
    and flows through here unchanged: L17 = corrected total_payments + L16.
    L16 and L23 are not sourced (0.0). L18 (original overpayment) =
    original_refund_received + original_refund_applied — the full
    overpayment the filer either received or applied forward on the
    original return.

    ``line11_c`` is the COMPUTED column-C L11 value from ``assemble`` (L8c +
    L10c = corrected total_tax + f8962_repayment - nonrefundable_credits +
    f8959_tax_total), passed in rather than recomputed here so the tail can
    never drift from the emitted L11.
    """
    line16 = 0.0  # amount paid with extension/original/after filing — unsourced
    line17 = irs_round(corrected["total_payments"] + line16)
    line18 = irs_round(case.original_refund_received + case.original_refund_applied)
    line19 = irs_round(line17 - line18)

    if line11_c > line19:
        line20 = irs_round(line11_c - line19)  # amount you owe
        line21 = 0
    else:
        line20 = 0
        line21 = irs_round(line19 - line11_c)  # overpaid on this return

    line23 = 0  # amount of L21 applied to next-year estimates — unsourced
    line22 = irs_round(line21 - line23)  # amount of L21 refunded to you

    return {
        "f1040x_line16": line16,
        "f1040x_line17": line17,
        "f1040x_line18": line18,
        "f1040x_line18_overpayment_on_original": line18,
        "f1040x_line19": line19,
        "f1040x_line20": line20,
        "f1040x_line20_amount_owed": line20,
        "f1040x_line21": line21,
        "f1040x_line22": line22,
        "f1040x_line22_refund": line22,
        "f1040x_line23": line23,
    }
