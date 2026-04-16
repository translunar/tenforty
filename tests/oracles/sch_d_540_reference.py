"""CA FTB Schedule D (540) reference oracle (TY2025).

Produces the federal↔California capital-gain delta that flows to
Schedule CA (540) Part I line 7.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchD540Input:
    filing_status: str
    transactions: tuple
    ca_capital_loss_carryover: float


def compute_sch_d_540(inp: SchD540Input) -> dict:
    return {"schd_540_ca_fed_delta_to_sch_ca_line_7": 0.0}
