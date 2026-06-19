"""Per-year federal tax parameters. The only thing that differs by year.

Year-agnostic spine/tax logic reads everything from FederalParams; there are
no `if year ==` branches in the math. Adding a year = adding one yNNNN module.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FederalParams:
    year: int
    standard_deduction: dict[str, int]
    ordinary_brackets: tuple[tuple[float, float], ...]  # (upper_bound, rate)
    qdcgt_breakpoints: dict[str, tuple[int, int]]        # (0%-top, 15%-top)
    addl_medicare_threshold: dict[str, int]
    qbi_threshold: dict[str, int]
    salt_cap: dict[str, int]
    # EIC income ceilings (single/HOH phase-out end) keyed by number of
    # qualifying children (0, 1, 2, 3+; key 3 = "three or more"). Used ONLY as
    # a cheap scope-gate threshold in the orchestrator: a scenario with
    # positive earned income and AGI below the applicable ceiling MIGHT be
    # EIC-eligible and is routed to the workbook oracle (which computes the
    # actual credit). The native spine performs no EIC math.
    eic_income_ceiling: dict[int, int] = field(default_factory=dict)


def load(year: int) -> FederalParams:
    if year == 2025:
        from tenforty.params.federal.y2025 import PARAMS
        return PARAMS
    if year == 2024:
        from tenforty.params.federal.y2024 import PARAMS
        return PARAMS
    raise ValueError(f"No federal parameters for year {year}")
