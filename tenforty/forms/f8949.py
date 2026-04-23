"""Form 8949 — Sales and Other Dispositions of Capital Assets.

Partitions ``scenario.form1099_b`` into two populations:

* **Aggregate-path lots** — Box A (short + basis-reported + no adjustments)
  and Box D (long + basis-reported + no adjustments). Per IRS instructions
  these lots are permitted to flow as an aggregate summary on Sch D
  lines 1a / 8a, bypassing Form 8949 entirely. They emit NO PDF row and
  are NOT included in any box-A/D subsection total.
* **8949-path lots** — everything else (Box B / Box E non-covered, and
  any lot with adjustments, 28%-rate, or §1250 tagging). These emit per-
  lot PDF rows, per-box subsection totals, and aggregate 28%-rate / §1250
  feeds.

Col (h) gain/loss = proceeds − basis + col (g) adjustment. Wash-sale
disallowed loss is positive in col (g) with code W. Other basis
adjustments are the user-supplied signed delta with code O.

Attestations (wash sale, other basis adj, 28% rate, §1250) are enforced
via the shared ``enforce_compute_time`` dispatcher in
``tenforty.attestations``; this module does not re-implement gate logic.
"""

from dataclasses import dataclass

from tenforty.attestations import enforce_compute_time
from tenforty.models import Form1099B, Scenario
from tenforty.rounding import irs_round
from tenforty.types import UpstreamState


@dataclass(frozen=True)
class Form8949Lot:
    box: str
    description: str
    date_acquired: str
    date_sold: str
    proceeds: int
    basis: int
    adjustment_code: str
    adjustment_amount: int
    gain: int
    is_28_rate: bool
    is_section_1250: bool


_BOX_KEYS = {
    (True,  True):  "a",
    (True,  False): "b",
    (False, True):  "d",
    (False, False): "e",
}


def compute(scenario: Scenario, upstream: UpstreamState) -> dict:
    enforce_compute_time(scenario)
    aggregate_lots, f8949_path_raw = _partition_lots(scenario.form1099_b)
    lots: list[Form8949Lot] = [_lot_from_1099b(raw) for raw in f8949_path_raw]
    result: dict = {
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }
    for letter in ("a", "b", "c", "d", "e", "f"):
        box_lots = [lot for lot in lots if lot.box == letter]
        for idx, lot in enumerate(box_lots, start=1):
            prefix = f"f8949_box_{letter}_row_{idx}"
            result[f"{prefix}_description"] = lot.description
            result[f"{prefix}_date_acquired"] = lot.date_acquired
            result[f"{prefix}_date_sold"] = lot.date_sold
            result[f"{prefix}_proceeds"] = lot.proceeds
            result[f"{prefix}_cost_basis"] = lot.basis
            result[f"{prefix}_adjustment_code"] = lot.adjustment_code
            result[f"{prefix}_adjustment_amount"] = lot.adjustment_amount
            result[f"{prefix}_gain_loss"] = lot.gain
        result[f"f8949_box_{letter}_total_proceeds"] = sum(lot.proceeds for lot in box_lots)
        result[f"f8949_box_{letter}_total_basis"] = sum(lot.basis for lot in box_lots)
        result[f"f8949_box_{letter}_total_adjustment"] = sum(
            lot.adjustment_amount for lot in box_lots
        )
        result[f"f8949_box_{letter}_total_gain"] = sum(lot.gain for lot in box_lots)
    short_agg = [raw for raw in aggregate_lots if raw.short_term]
    long_agg = [raw for raw in aggregate_lots if not raw.short_term]
    result["f8949_agg_short_proceeds"] = irs_round(sum(r.proceeds for r in short_agg))
    result["f8949_agg_short_basis"] = irs_round(sum(r.cost_basis for r in short_agg))
    result["f8949_agg_short_gain"] = (
        result["f8949_agg_short_proceeds"] - result["f8949_agg_short_basis"]
    )
    result["f8949_agg_long_proceeds"] = irs_round(sum(r.proceeds for r in long_agg))
    result["f8949_agg_long_basis"] = irs_round(sum(r.cost_basis for r in long_agg))
    result["f8949_agg_long_gain"] = (
        result["f8949_agg_long_proceeds"] - result["f8949_agg_long_basis"]
    )
    # Aggregate-path lots cannot carry adjustment-trigger flags by
    # construction (any flag would route the lot to the 8949-path),
    # so these aggregates are over the 8949-path population only.
    result["f8949_total_28_rate_gain"] = sum(lot.gain for lot in lots if lot.is_28_rate)
    result["f8949_total_unrecap_1250"] = sum(lot.gain for lot in lots if lot.is_section_1250)
    result["f8949_net_short_term"] = sum(
        lot.gain for lot in lots if lot.box in ("a", "b", "c")
    )
    result["f8949_net_long_term"] = sum(
        lot.gain for lot in lots if lot.box in ("d", "e", "f")
    )
    return result


def _partition_lots(
    raw_lots: list[Form1099B],
) -> tuple[list[Form1099B], list[Form1099B]]:
    aggregate: list[Form1099B] = []
    path_8949: list[Form1099B] = []
    for raw in raw_lots:
        is_agg = (raw.basis_reported_to_irs and not raw.has_adjustments)
        (aggregate if is_agg else path_8949).append(raw)
    return aggregate, path_8949


def _lot_from_1099b(raw: Form1099B) -> Form8949Lot:
    box = _BOX_KEYS[(raw.short_term, raw.basis_reported_to_irs)]
    if raw.wash_sale_loss_disallowed and raw.other_basis_adjustment:
        raise NotImplementedError(
            "A single 1099-B lot carries both wash_sale_loss_disallowed "
            "and other_basis_adjustment; Form 8949 col (f) accepts one "
            "code per row — split into two lots: one with wash-sale-only "
            "(code W) and one with the residual basis adjustment (code O)."
        )
    code = ""
    adj = 0
    if raw.wash_sale_loss_disallowed:
        code = "W"
        adj = irs_round(raw.wash_sale_loss_disallowed)
    elif raw.other_basis_adjustment:
        code = "O"
        adj = irs_round(raw.other_basis_adjustment)
    proceeds = irs_round(raw.proceeds)
    basis = irs_round(raw.cost_basis)
    gain = proceeds - basis + adj
    return Form8949Lot(
        box=box, description=raw.description,
        date_acquired=raw.date_acquired, date_sold=raw.date_sold,
        proceeds=proceeds, basis=basis,
        adjustment_code=code, adjustment_amount=adj, gain=gain,
        is_28_rate=raw.is_28_rate_collectible,
        is_section_1250=raw.is_section_1250,
    )
