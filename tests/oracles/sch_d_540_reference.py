"""CA FTB Schedule D (540) reference oracle (TY2025).

Produces the federal↔California capital-gain delta that flows to
Schedule CA (540) Part I line 7.

### Design

California taxes capital gains at ordinary rates — there is no
short-term / long-term bifurcation on Schedule D (540). The form's
arithmetic is:

    line 4   = total CA gains (sum of col (e) amounts on lines 1, 2, 3)
    line 5   = total CA losses (sum of col (d) amounts on lines 1, 2)
    line 6   = CA capital loss carryover from prior year
    line 7   = line 5 + line 6                    (total losses w/ carryover)
    line 8   = line 4 − line 7                    (net gain or loss)
    line 9   = smaller of |line 8| or $3k/$1.5k   (if line 8 is a loss)
    line 10  = federal Form 1040 line 7a          (scalar pass-through)
    line 11  = line 8 (if gain) or −line 9 (if loss)
    line 12a = line 10 − line 11  if line 10 > line 11 (→ Sch CA col B subtraction)
    line 12b = line 11 − line 10  if line 11 > line 10 (→ Sch CA col C addition)

Per-transaction CA gain/loss amounts fold basis differences, §1202 /
§1045 QSBS denial, §1400Z-2 OZ denial, §1221 patent-is-capital-for-CA
treatment, and depreciation-method non-conformity into ``Transaction
.ca_gain_or_loss`` directly. The oracle does not recompute any of those
per-transaction; the caller supplies the CA-recognized amount.

### Output contract

``compute_sch_d_540(inp: SchD540Input) -> dict`` returns:

- ``schd_540_line_<N>_<semantic>`` — per-line intermediate values
  mirroring the 2025 form face.
- ``schd_540_ca_fed_delta_to_sch_ca_line_7`` — signed float. Positive =
  CA recognizes more gain than federal (Sch CA col C addition).
  Negative = CA recognizes less gain than federal (Sch CA col B
  subtraction). Zero = identity case. Consumed by the CA 540 oracle
  (branch ``oracle/ca-540-reference``) on
  ``SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions`` (if
  negative, take absolute value) or col C additions (if positive).
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Loss deduction cap per Sch D (540) line 9 — matches federal §1211(b).
# ---------------------------------------------------------------------------
_MAX_CAPITAL_LOSS_DEDUCTION_SEPARATE = 1_500.0
_MAX_CAPITAL_LOSS_DEDUCTION_OTHER = 3_000.0

_MFS_FILING_STATUS = "married_filing_separately"


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Transaction:
    """A single CA-side capital-asset disposition.

    `ca_gain_or_loss` is the signed CA-recognized net for this
    transaction: positive = gain (flows to col (e) on line 1), negative
    = loss (flows to col (d) on line 1). Basis differences, §1202 /
    §1045 QSBS denial, §1400Z-2 OZ denial, §1221 patent-is-capital,
    depreciation-method non-conformity — all folded into this amount by
    the caller. The oracle does not recompute basis or federal
    exclusions per-transaction.
    """
    description: str
    ca_gain_or_loss: float


@dataclass(frozen=True)
class SchD540Input:
    """Top-level input for the Schedule D (540) oracle.

    ``federal_1040_line_7a_capital_gain`` is the taxpayer's federal
    aggregate capital gain as reported on Form 1040 line 7a — the
    oracle does NOT recompute it from transactions. Differences between
    the federal aggregate and the CA-side sum of ``ca_gain_or_loss``
    values are what produce the line-12a/12b delta.
    """
    filing_status: str
    transactions: tuple[Transaction, ...]
    ca_capital_loss_carryover: float
    federal_1040_line_7a_capital_gain: float


# ---------------------------------------------------------------------------
# Main compute
# ---------------------------------------------------------------------------
def _loss_deduction_cap(filing_status: str) -> float:
    """Line 9 cap: $1,500 for MFS, $3,000 otherwise."""
    # SOURCE: 2025 Sch D (540) form face line 9 — "$3,000 ($1,500 if
    # married/RDP filing separately)". Conforms to IRC §1211(b).
    if filing_status == _MFS_FILING_STATUS:
        return _MAX_CAPITAL_LOSS_DEDUCTION_SEPARATE
    return _MAX_CAPITAL_LOSS_DEDUCTION_OTHER


def compute_sch_d_540(inp: SchD540Input) -> dict:
    """Compute Schedule D (540) lines 4-12 and the integration delta."""
    # SOURCE: 2025 Sch D (540) form face, lines 1-12. Each transaction
    # supplies a signed CA-recognized gain/loss; the oracle aggregates
    # them into the form's column-(e) (gains) and column-(d) (losses)
    # totals.
    line_4_total_gains = 0.0
    line_5_total_losses = 0.0
    for t in inp.transactions:
        if t.ca_gain_or_loss >= 0.0:
            line_4_total_gains += t.ca_gain_or_loss
        else:
            line_5_total_losses += -t.ca_gain_or_loss

    line_6_carryover = inp.ca_capital_loss_carryover
    line_7_total_losses_with_carryover = line_5_total_losses + line_6_carryover
    line_8_net = line_4_total_gains - line_7_total_losses_with_carryover

    # Line 9: smaller of |line 8| or filing-status cap, only if line 8
    # is a loss. Produces the deductible loss magnitude.
    if line_8_net < 0.0:
        line_9_bounded_loss = min(
            -line_8_net, _loss_deduction_cap(inp.filing_status)
        )
    else:
        line_9_bounded_loss = 0.0

    line_10_federal = inp.federal_1040_line_7a_capital_gain

    # Line 11: CA-side amount to compare against federal line 10.
    # Form face: "Enter the California gain from line 8 or (loss) from
    # line 9". In plain English: if line 8 is a gain, use line 8; if
    # line 8 is a loss, use -line 9 (the bounded loss, signed).
    if line_8_net >= 0.0:
        line_11_ca = line_8_net
    else:
        line_11_ca = -line_9_bounded_loss

    # Lines 12a / 12b: mutually-exclusive directional differences.
    # 12a > 0 → Sch CA col B subtraction (fed recognized more).
    # 12b > 0 → Sch CA col C addition (CA recognized more).
    if line_10_federal > line_11_ca:
        line_12a = line_10_federal - line_11_ca
        line_12b = 0.0
    elif line_11_ca > line_10_federal:
        line_12a = 0.0
        line_12b = line_11_ca - line_10_federal
    else:
        line_12a = 0.0
        line_12b = 0.0

    # Signed integration delta. Convention: positive = CA > fed
    # (addition on Sch CA col C), negative = fed > CA (subtraction on
    # col B), zero = identity.
    delta = line_11_ca - line_10_federal

    return {
        "schd_540_line_4_total_gains": line_4_total_gains,
        "schd_540_line_5_total_losses": line_5_total_losses,
        "schd_540_line_6_ca_carryover_from_prior_year": line_6_carryover,
        "schd_540_line_7_total_losses_with_carryover": line_7_total_losses_with_carryover,
        "schd_540_line_8_net_gain_or_loss": line_8_net,
        "schd_540_line_9_bounded_loss_deduction": line_9_bounded_loss,
        "schd_540_line_10_federal_1040_line_7a": line_10_federal,
        "schd_540_line_11_ca_gain_or_loss": line_11_ca,
        "schd_540_line_12a_subtraction_col_b": line_12a,
        "schd_540_line_12b_addition_col_c": line_12b,
        "schd_540_ca_fed_delta_to_sch_ca_line_7": delta,
    }
