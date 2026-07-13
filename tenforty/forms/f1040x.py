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
  L11 total tax               <- total_tax
  L12 withholding             <- federal_withheld
  L15 total payments          <- total_payments
Three-column, COMPUTED subtotal (on-form):
  L3  = L1 - L2  (per column)
Single-column, COMPUTED tail (see _tail):
  L16..L23
SKIPPED — reserved:
  L9  "Reserved for future use" (shaded; fields exist but are never mapped).
INTENTIONALLY UNMAPPED (guarded out-of-scope — see _OUT_OF_SCOPE_FILED_KEYS):
  L4b Schedule 1-A (tips/overtime/car-loan-interest/seniors, TY2025)
  L6  tax          L7  nonrefundable credits   L8  subtract 7 from 6
  L10 other taxes  L13 estimated payments      L14 EIC
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
    "estimated_payments": "line 13 (estimated tax payments)",
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
    """
    _require_filed_keys(filed)
    _guard_out_of_scope(filed)

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
    # L11 total tax.
    _triple(out, "11", filed["total_tax"], corrected["total_tax"])
    # L12 withholding.
    _triple(out, "12", filed["federal_withheld"], corrected["federal_withheld"])
    # L15 total payments.
    _triple(out, "15", filed["total_payments"], corrected["total_payments"])

    # ----- Single-column tail (lines 16-23) -------------------------------
    out.update(_tail(corrected, case))

    # ----- Narrative / year (Part II + page-1 write-in) -------------------
    out["f1040x_explanation"] = case.explanation
    out["f1040x_amended_year"] = case.year
    return out


def _tail(corrected: dict, case: AmendmentCase) -> dict:
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

    v1 sourcing: total_payments == federal_withheld (no estimated-payments
    channel), so L17 = corrected total_payments + L16; L16 and L23 are not
    sourced (0.0). L18 (original overpayment) = original_refund_received +
    original_refund_applied — the full overpayment the filer either received
    or applied forward on the original return.
    """
    line11_c = corrected["total_tax"]

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
