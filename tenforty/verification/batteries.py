"""The battery modules the harness runs (spec §3.1, §3.2).

Each ``BatteryRef`` names a battery module, how to enumerate its scenarios
as ``(scenario name, tax year, zero-arg builder)``, and the public emit entry
point its scenarios go through. ``BATTERIES`` starts with the spine battery
and the Schedule C battery; later lanes add modules here.

The batteries live under ``tests/fixtures`` (they are test data), so the
enumerators import them lazily.
"""
import dataclasses
import functools
from collections.abc import Callable, Iterable


@dataclasses.dataclass(frozen=True)
class BatteryRef:
    name: str
    module: str
    scenarios: Callable[[], Iterable[tuple[str, int, Callable]]]
    entry_point: str


def _spine_scenarios():
    from tenforty import years
    from tenforty.models import FilingStatus
    from tests.fixtures import spine_battery
    for year in years.FEDERAL_YEARS:
        for status in (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY,
                       FilingStatus.HEAD_OF_HOUSEHOLD):
            for name, build in spine_battery.battery_for(year, status):
                yield name, year, build


def _sch_c_scenarios():
    from tests.fixtures import sch_c_battery
    for year in sch_c_battery.YEARS:
        for name in sch_c_battery.SCENARIOS:
            yield name, year, functools.partial(sch_c_battery.build, name, year)


def _sch_se_scenarios():
    from tests.fixtures import emit_battery_sch_se
    # A scenario may run in years of its own (the wage-base row runs every
    # year; the rest in YEARS): year-major, each scenario in its years.
    years = sorted({y for name in emit_battery_sch_se.SCENARIOS
                    for y in emit_battery_sch_se.years_for(name)})
    for year in years:
        for name in emit_battery_sch_se.SCENARIOS:
            if year in emit_battery_sch_se.years_for(name):
                yield name, year, functools.partial(
                    emit_battery_sch_se.build, name, year)


def _sch_c_emit_scenarios():
    from tests.fixtures import emit_battery_sch_c
    for year in emit_battery_sch_c.YEARS:
        for name in emit_battery_sch_c.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_sch_c.build, name, year)


def _sch_1_emit_scenarios():
    from tests.fixtures import emit_battery_sch_1
    for year in emit_battery_sch_1.YEARS:
        for name in emit_battery_sch_1.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_sch_1.build, name, year)
def _f8995_emit_scenarios():
    from tests.fixtures import emit_battery_f8995
    for year in emit_battery_f8995.YEARS:
        for name in emit_battery_f8995.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_f8995.build, name, year)


def _sch_e_emit_scenarios():
    from tests.fixtures import emit_battery_sch_e
    for year in emit_battery_sch_e.YEARS:
        for name in emit_battery_sch_e.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_sch_e.build, name, year)


def _sch_b_emit_scenarios():
    from tests.fixtures import emit_battery_sch_b
    for year in emit_battery_sch_b.YEARS:
        for name in emit_battery_sch_b.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_sch_b.build, name, year)


def _f8959_emit_scenarios():
    from tests.fixtures import emit_battery_f8959
    years = sorted({y for name in emit_battery_f8959.SCENARIOS
                    for y in emit_battery_f8959.years_for(name)})
    for year in years:
        for name in emit_battery_f8959.SCENARIOS:
            if year in emit_battery_f8959.years_for(name):
                yield name, year, functools.partial(
                    emit_battery_f8959.build, name, year)


def _sch_d_emit_scenarios():
    from tests.fixtures import emit_battery_sch_d
    for year in emit_battery_sch_d.YEARS:
        for name in emit_battery_sch_d.SCENARIOS:
            yield name, year, functools.partial(
                emit_battery_sch_d.build, name, year)


BATTERIES: tuple[BatteryRef, ...] = (
    BatteryRef("spine_battery", "tests.fixtures.spine_battery",
               _spine_scenarios, "run_full_return"),
    BatteryRef("sch_c_battery", "tests.fixtures.sch_c_battery",
               _sch_c_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_se", "tests.fixtures.emit_battery_sch_se",
               _sch_se_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_c", "tests.fixtures.emit_battery_sch_c",
               _sch_c_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_1", "tests.fixtures.emit_battery_sch_1",
               _sch_1_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_f8995", "tests.fixtures.emit_battery_f8995",
               _f8995_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_e", "tests.fixtures.emit_battery_sch_e",
               _sch_e_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_b", "tests.fixtures.emit_battery_sch_b",
               _sch_b_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_f8959", "tests.fixtures.emit_battery_f8959",
               _f8959_emit_scenarios, "run_full_return"),
    BatteryRef("emit_battery_sch_d", "tests.fixtures.emit_battery_sch_d",
               _sch_d_emit_scenarios, "run_full_return"),
)
