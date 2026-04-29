"""Schedule CA (540) generic compute kernel.

Routes a list of CASchCAAdjustment entries to their respective Sch CA
lines, sums into Col B (subtractions) and Col C (additions) per line,
and computes CA AGI = federal AGI - Σ subtractions + Σ additions.

Produces compute output keys:
- sch_ca_line_<normalized_line>_subtractions: per-line Col B sum
- sch_ca_line_<normalized_line>_additions: per-line Col C sum
- sch_ca_total_subtractions: Σ all Col B
- sch_ca_total_additions: Σ all Col C
- sch_ca_ca_agi: federal_agi - Σ subtractions + Σ additions
"""

from collections import defaultdict
from tenforty.models import CASchCAAdjustment, DivergenceDirection
from tenforty.rounding import irs_round


def _normalize_line(sch_ca_line: str) -> str:
    """Convert 'Part I §B 8z' style to 'part_i_b_8z' for compute key suffix."""
    return (sch_ca_line.lower()
            .replace("§", "")
            .replace(" ", "_")
            .strip("_"))


def compute(
    divergences: list[CASchCAAdjustment],
    federal_results: dict,
) -> dict:
    subtractions = defaultdict(float)
    additions = defaultdict(float)
    for adj in divergences:
        bucket = subtractions if adj.direction == DivergenceDirection.SUBTRACTION else additions
        bucket[adj.sch_ca_line] += adj.amount

    out = {}
    for line, amount in subtractions.items():
        key = f"sch_ca_line_{_normalize_line(line)}_subtractions"
        out[key] = irs_round(amount)
    for line, amount in additions.items():
        key = f"sch_ca_line_{_normalize_line(line)}_additions"
        out[key] = irs_round(amount)

    total_sub = sum(subtractions.values())
    total_add = sum(additions.values())
    out["sch_ca_total_subtractions"] = irs_round(total_sub)
    out["sch_ca_total_additions"] = irs_round(total_add)

    federal_agi = federal_results.get("agi", 0.0)
    out["sch_ca_ca_agi"] = irs_round(federal_agi - total_sub + total_add)
    return out
