"""Per-year federal tax parameters. The only thing that differs by year.

Year-agnostic spine/tax logic reads everything from FederalParams; there are
no `if year ==` branches in the math. Adding a year = adding one yNNNN module.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FederalParams:
    year: int
    standard_deduction: dict[str, int]
    ordinary_brackets: tuple[tuple[float, float], ...]  # (upper_bound, rate)
    qdcgt_breakpoints: dict[str, tuple[int, int]]        # (0%-top, 15%-top)
    addl_medicare_threshold: dict[str, int]
    qbi_threshold: dict[str, int]
    salt_cap: dict[str, int]


def load(year: int) -> FederalParams:
    if year == 2025:
        from tenforty.params.federal.y2025 import PARAMS
        return PARAMS
    raise ValueError(f"No federal parameters for year {year}")
