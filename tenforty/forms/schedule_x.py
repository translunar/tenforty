"""California Schedule X ("Explanation of Amended Return Changes") assembler.

Pure functions — no year branches, no orchestrator import. Consumes an
as-filed CA results dict (the original 540, keyed by ``f540_*`` result-dict
names), an already-computed corrected CA results dict (the amended 540), and
an :class:`AmendmentCase` for the narrative + original-overpayment context.
Produces the Schedule X Part I line values (Task 6 handles the per-year PDF
field paths; this assembler is YEAR-AGNOSTIC — it emits compute-keys).

FORM SHAPE (transcribed from the probed Schedule X, TY2021-2025 — identical
line arithmetic across all five years; see
``docs/plans/amended-returns-probe-tables.md``, "CA Schedule X"):

Schedule X is NOT a three-column A/B/C grid like the federal 1040-X. It is a
single balance RECONCILIATION between the amended return and the original
return:

  L1  Amount you owe, as shown on the AMENDED return      <- corrected f540
  L2  Overpaid tax, as shown on the ORIGINAL return       <- AmendmentCase
  L3  = L1 + L2
  L4  Refund, as shown on the AMENDED return              <- corrected f540
  L5  Tax paid with ORIGINAL return + additional after    <- ca_filed f540
  L6  = L4 + L5
  L7  AMOUNT YOU OWE           = L3 - L6  (when L3 > L6)
  L8a Penalties     L8b Interest     L8c = L8a + L8b
  L9  Refund subtotal          = L6 - L3  (when L6 > L3)
  L10 Amount of L9 applied to next-year estimated tax
  L11 REFUND                   = L9 - L10

SOURCING
--------
The "amended return" figures (L1, L4) come from the CORRECTED f540 run's net
``f540_total_liability`` (sign convention: positive = amount owed after CA
payments; negative = overpaid/refund). L1 = max(0, corrected TL); L4 =
max(0, -corrected TL).

L2 (original overpayment) = ``case.ca_original_refund_received +
case.ca_original_refund_applied`` — RULING: Schedule X line 2 wants what the
ORIGINAL return SHOWED as overpaid (the full original overpayment the filer
either received or applied forward), the direct analogue of federal 1040-X
line 18. It is genuine post-filing money movement, not a recomputable figure,
so it rides the AmendmentCase and FAILS CLOSED if unstated (see
``_require_ca_case_context``).

L5 (tax paid with the original return) = max(0, filed ``f540_total_liability``)
— the balance due the filer paid with the ORIGINAL return, sourced from the
as-filed values (Column A). This is the assembler's REQUIRED_CA_FILED_KEYS
consumer.

L8a/L8b (penalties/interest) and L10 (applied to next-year estimates) are
post-filing / not computed by tenforty's f540 — emitted 0 (unsourced),
mirroring the federal tail's unsourced lines.

NET INVARIANT: L7 - L11 == corrected f540_total_liability - filed
f540_total_liability (the true additional owed / refund), given the
consistency constraint that the case's stated original overpayment equals the
filed return's overpayment.

OUT-OF-SCOPE GUARD: if the FILED CA return carried a nonzero amount on a
Form 540 line tenforty's f540 does not compute, the corrected run cannot
faithfully reproduce the reconciliation — refuse (OutOfScopeAmendmentError)
rather than silently drop it. See ``_OUT_OF_SCOPE_CA_FILED_KEYS``.
"""

from tenforty.amendment import MissingFiledValueError, OutOfScopeAmendmentError
from tenforty.models import AmendmentCase
from tenforty.rounding import irs_round

# ca_filed source keys the assembler consumes. Every one must be present in
# the filed dict — a missing one is a MissingFiledValueError, never defaulted.
# f540_total_liability is the original return's net position (signed): its
# positive part is Schedule X line 5 (tax paid with the original return).
REQUIRED_CA_FILED_KEYS: tuple[str, ...] = ("f540_total_liability",)

# CA Form 540 lines tenforty's f540 does NOT compute. If the FILED CA return
# carries a nonzero value under any of these, the corrected run cannot
# reproduce that piece of the reconciliation, so refuse rather than emit a
# wrong balance. Key NAMES are the filed-schema labels for these out-of-model
# lines (not tax figures). Each is an existing tenforty CA scope-out.
_OUT_OF_SCOPE_CA_FILED_KEYS: dict[str, str] = {
    "f540_other_state_tax_credit":
        "other state tax credit (Schedule S) — scoped out "
        "(acknowledges_no_other_state_tax_credit)",
    "f540_amt":
        "CA alternative minimum tax (Schedule P) — scoped out "
        "(acknowledges_no_ca_amt_preferences)",
    "f540_withholding":
        "CA income tax withheld (Form 540 line 71) — f540 models estimated "
        "payments only, with no withholding channel",
}


def _require_ca_filed_keys(filed: dict) -> None:
    """Every REQUIRED_CA_FILED_KEYS member must be present. Never substitute a
    default for a missing as-filed figure."""
    missing = [k for k in REQUIRED_CA_FILED_KEYS if k not in filed]
    if missing:
        raise MissingFiledValueError(
            f"CA filed-values dict is missing required key(s): {sorted(missing)}. "
            f"Refusing to substitute a default — supply the as-filed figure "
            f"for each of {list(REQUIRED_CA_FILED_KEYS)}."
        )


def _guard_out_of_scope(filed: dict) -> None:
    """Refuse if the filed CA return carried an amount on a line f540 cannot
    source (the corrected run could not reproduce it)."""
    for key, label in _OUT_OF_SCOPE_CA_FILED_KEYS.items():
        if filed.get(key):  # nonzero / truthy
            raise OutOfScopeAmendmentError(
                f"Filed CA return carries a nonzero value on {label} "
                f"(filed[{key!r}] = {filed[key]}); tenforty's f540 cannot "
                f"source this Schedule X input, so the corrected run cannot "
                f"faithfully reproduce the reconciliation. Refusing to emit a "
                f"balance that would silently drop the filed amount."
            )


def _require_ca_case_context(case: AmendmentCase) -> None:
    """Fail closed: a CA Schedule X needs the original-overpayment context
    (line 2 = received + applied). Those AmendmentCase fields default to None so
    a federal-only case loads without them, but assembling a CA amendment while
    either is None is refused — the filer must ASSERT the context (even 0), it
    is never inferred."""
    missing = [
        name
        for name in ("ca_original_refund_received", "ca_original_refund_applied")
        if getattr(case, name) is None
    ]
    if missing:
        raise ValueError(
            f"AmendmentCase is missing CA original-payment context: {missing}. "
            f"Schedule X line 2 (original overpayment) requires "
            f"ca_original_refund_received + ca_original_refund_applied to be "
            f"stated (assert 0 if there was none) — refusing to infer it."
        )


def _guard_ca_overpayment_matches_filed(filed: dict, case: AmendmentCase) -> None:
    """Machine-check that the case and the filed values describe the SAME
    as-filed-or-as-last-adjusted snapshot: the case's stated original
    overpayment (Schedule X line 2 = received + applied) must EXACTLY equal the
    filed return's original overpayment (the negative part of the signed filed
    net liability). The net-owed/refund invariant (L7 - L11 == corrected -
    filed) holds ONLY under this equality — this guard converts that from a
    documented assumption into a machine check. A filed OWED return (positive
    liability) has overpayment 0, forcing the stated overpayment to be 0."""
    stated = irs_round(
        case.ca_original_refund_received + case.ca_original_refund_applied)
    filed_overpay = irs_round(max(0.0, -filed["f540_total_liability"]))
    if stated != filed_overpay:
        raise ValueError(
            f"Schedule X consistency: case states original overpayment {stated} "
            f"but the filed return shows {filed_overpay}. Filed values and the "
            f"amendment case must describe the same as-filed-or-as-last-adjusted "
            f"snapshot."
        )


def assemble_ca(filed: dict, corrected: dict, case: AmendmentCase) -> dict:
    """Assemble CA Schedule X Part I line values from filed + corrected f540
    results dicts.

    ``filed`` supplies the ORIGINAL return's net position (Column A);
    ``corrected`` supplies the AMENDED return's net position (trusted — already
    rounded by the f540 compute); ``case`` supplies the original overpayment
    context (line 2) and the Part II explanation + taxable year.

    The net-owed/refund invariant (L7 - L11 == corrected - filed f540 net
    liability) HOLDS ONLY when the case's stated original overpayment equals
    the filed return's original overpayment; ``_guard_ca_overpayment_matches_filed``
    makes that precondition a machine check rather than a documented assumption.
    """
    _require_ca_filed_keys(filed)
    _guard_out_of_scope(filed)
    _require_ca_case_context(case)
    _guard_ca_overpayment_matches_filed(filed, case)

    corrected_tl = corrected["f540_total_liability"]
    filed_tl = filed["f540_total_liability"]

    # Amended-return figures (L1 owe, L4 refund) from the corrected net.
    line1 = irs_round(max(0.0, corrected_tl))
    line4 = irs_round(max(0.0, -corrected_tl))

    # Original-return figures: L2 overpayment from the case (received +
    # applied); L5 tax paid with the original return from the as-filed net.
    line2 = irs_round(
        case.ca_original_refund_received + case.ca_original_refund_applied)
    line5 = irs_round(max(0.0, filed_tl))

    # On-form subtotals (sums of the EMITTED whole-dollar lines, so the
    # printed arithmetic holds exactly on the emitted integers).
    line3 = line1 + line2
    line6 = line4 + line5

    # Penalties/interest (8a/8b) are post-filing, not computed — 0.
    line8a = 0
    line8b = 0
    line8c = line8a + line8b

    # Balance lines. Exactly one of L7 / L9 is nonzero.
    line7 = max(0, line3 - line6)   # AMOUNT YOU OWE
    line9 = max(0, line6 - line3)   # Refund subtotal
    line10 = 0                      # applied to next-year estimates — unsourced
    line11 = line9 - line10         # REFUND

    return {
        "schedule_x_line1": line1,
        "schedule_x_line2": line2,
        "schedule_x_line3": line3,
        "schedule_x_line4": line4,
        "schedule_x_line5": line5,
        "schedule_x_line6": line6,
        "schedule_x_line7": line7,
        "schedule_x_line7_amount_owed": line7,
        "schedule_x_line8a": line8a,
        "schedule_x_line8b": line8b,
        "schedule_x_line8c": line8c,
        "schedule_x_line9": line9,
        "schedule_x_line10": line10,
        "schedule_x_line11": line11,
        "schedule_x_line11_refund": line11,
        "schedule_x_explanation": case.explanation,
        "schedule_x_taxable_year": case.year,
    }
