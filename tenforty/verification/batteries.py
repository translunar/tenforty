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


BATTERIES: tuple[BatteryRef, ...] = (
    BatteryRef("spine_battery", "tests.fixtures.spine_battery",
               _spine_scenarios, "run_full_return"),
    BatteryRef("sch_c_battery", "tests.fixtures.sch_c_battery",
               _sch_c_scenarios, "run_full_return"),
)
