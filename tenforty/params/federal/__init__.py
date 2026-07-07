"""Per-year federal tax parameters. The only thing that differs by year.

Year-agnostic spine/tax logic reads everything from FederalParams; there are
no `if year ==` branches in the math. Adding a year = adding one yNNNN module.
"""
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class FederalParams:
    year: int
    standard_deduction: dict[str, int]
    ordinary_brackets: tuple[tuple[float, float], ...]  # (upper_bound, rate)
    qdcgt_breakpoints: dict[str, tuple[int, int]]        # (0%-top, 15%-top)
    addl_medicare_threshold: dict[str, int]
    # SSA OASDI (Social Security) wage base for the year. Not used by the
    # spine's tax math (W-2s carry withheld amounts); used by fixtures to
    # generate year-correct synthetic W-2s.
    ss_wage_base: int
    qbi_threshold: dict[str, int]
    # SALT cap structure (replaces the removed scalar salt_cap field).
    # Keys are FilingStatus.value strings throughout.
    # salt_phaseout_threshold = None  →  flat cap, no income-based reduction.
    # salt_phaseout_threshold = int   →  MAGI above this triggers phaseout;
    #   forms.sch_a.compute raises NotImplementedError (phaseout math is
    #   scoped out of v1 — no in-scope filer exceeds $500k MAGI).
    salt_cap_starting: dict[str, int]
    salt_phaseout_threshold: int | None
    salt_phaseout_rate: float
    salt_cap_floor: dict[str, int]
    # Medical-expense AGI floor (Sch A line 3 = AGI × this).
    medical_agi_floor_pct: float
    # SALT cap that applied in the year a state refund originated (used by
    # Sch 1 tax-benefit-rule). A 2025 return looks back to 2024 ($10k/$5k);
    # a 2024 return looks back to 2023 (also $10k/$5k).
    prior_year_salt_cap: dict[str, int]
    # EIC income ceilings keyed by number of qualifying children (0, 1, 2, 3+).
    # Scope-gate threshold only; no EIC math in the native spine.
    eic_income_ceiling: dict[int, int]


def load(year: int) -> FederalParams:
    if year not in year_manifest.FEDERAL_YEARS:
        raise ValueError(
            f"No federal parameters for year {year} "
            f"(supported federal tax years: "
            f"{year_manifest.describe(year_manifest.FEDERAL_YEARS)})"
        )
    module = importlib.import_module(f"tenforty.params.federal.y{year}")
    return module.PARAMS
