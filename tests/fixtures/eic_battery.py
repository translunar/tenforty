"""Earned income credit battery: scenario INPUTS only, no expected amounts
(exact values are pinned from the oracle run, not transcribed here).

Single filer, no dependents, one W-2. Wages are placed relative to the
no-child ceiling the spine-routing gate reads (params eic_income_ceiling[0]),
never a hard-coded threshold.
All identities and amounts are fully synthetic.
"""
from collections.abc import Callable

from tenforty.models import Scenario
from tenforty.params.federal import load as load_params
from tests.fixtures.spine_battery import _battery_config, _w2

YEAR = 2024
PLATEAU_WAGES = 9000.0  # the confirmed non-footing shape (line 33 932, 27 blank)


def _ceiling(year: int) -> int:
    return load_params(year).eic_income_ceiling[0]


def _single_w2(year: int, wages: float) -> Scenario:
    return Scenario(
        config=_battery_config(year),
        w2s=[_w2(year, "Synthetic Employer EIC", wages,
                 federal_tax_withheld=300.0)])


def build_plateau(year: int) -> Scenario:
    # Full no-child credit; routes to the workbook.
    return _single_w2(year, PLATEAU_WAGES)


def build_phase_out(year: int) -> Scenario:
    # Midway from the plateau wages to the ceiling: a partial credit.
    return _single_w2(year, float(round((PLATEAU_WAGES + _ceiling(year)) / 2)))


def build_over_ceiling(year: int) -> Scenario:
    # Above the gate's ceiling: routes to the native spine (no EIC math).
    return _single_w2(year, float(_ceiling(year) + 1000))


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "plateau": build_plateau,
    "phase-out": build_phase_out,
    "over-ceiling": build_over_ceiling,
}
