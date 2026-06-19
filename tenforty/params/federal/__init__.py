"""Per-year federal tax parameters. The only thing that differs by year.

Year-agnostic spine/tax logic reads everything from FederalParams; there are
no `if year ==` branches in the math. Adding a year = adding one yNNNN module.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EicParams:
    """Earned Income Credit table parameters for a given number of children.

    Mirrors the IRS EIC Table spreadsheet structure (columns N-U of the
    EIC Table sheet in the 2025 workbook). The table uses the *midpoint*
    of each $50 income bracket to compute the per-row credit value —
    see ``compute_eic`` in ``forms.f1040_spine`` for the lookup logic.

    Attributes:
        max_credit:       Maximum EIC amount (row N3/O3/...).
        phase_in_end:     Earned income where credit reaches max_credit (N4/...).
        phase_out_start:  AGI/EI where phase-out begins (N5/...; single/HOH).
        phase_out_end:    AGI/EI where credit reaches 0 (N6/...; single/HOH).
        phase_out_start_mfj:  Phase-out start for MFJ (R5/...).
        phase_out_end_mfj:    Phase-out end for MFJ (R6/...).
    """
    max_credit: int
    phase_in_end: int
    phase_out_start: int       # single / HOH
    phase_out_end: int         # single / HOH
    phase_out_start_mfj: int
    phase_out_end_mfj: int


@dataclass(frozen=True)
class FederalParams:
    year: int
    standard_deduction: dict[str, int]
    ordinary_brackets: tuple[tuple[float, float], ...]  # (upper_bound, rate)
    qdcgt_breakpoints: dict[str, tuple[int, int]]        # (0%-top, 15%-top)
    addl_medicare_threshold: dict[str, int]
    qbi_threshold: dict[str, int]
    salt_cap: dict[str, int]
    # Earned Income Credit parameters keyed by number of qualifying children
    # (0, 1, 2, 3+). Key 3 covers "three or more children".
    eic_params: dict[int, "EicParams"] = None
    # EIC investment income limit (from the EIC worksheet, cell N58 in the 2025
    # workbook). If total investment income exceeds this amount, EIC is disallowed.
    eic_investment_income_limit: int = None


def load(year: int) -> FederalParams:
    if year == 2025:
        from tenforty.params.federal.y2025 import PARAMS
        return PARAMS
    raise ValueError(f"No federal parameters for year {year}")
