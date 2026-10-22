"""Form 8959 emit battery (zero-lines audit, [R-ZL-5]): scenario INPUTS
only. The harness compares every emit against the real computation, so no
expected value is written here.

Covers the Form 8959 lines no other battery drives nonzero:

- lines 22 and 24: an employer that withheld the Additional Medicare Tax
  (0.9% of wages over $200,000) on top of the regular 1.45%. Every other
  battery W-2 withholds exactly 1.45%, so line 22 computes 0 by
  construction there.
- lines 8, 11, 12 and 13 (Part II): wages under the threshold plus
  Schedule C self-employment income that carries the total over it. Runs
  only in 2024 and 2025: the row must also stay on Form 8995's simple path
  (taxable income before the QBI deduction under the year's threshold),
  and in 2021-2023 that threshold plus the standard deduction is below the
  $200,000 that wages plus net SE earnings must exceed, so no single-filer
  shape reaches line 12 there without leaving the 8995 simple path.

All identities and amounts are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import Scenario, ScheduleCBusiness
from tests.fixtures.spine_battery import _battery_config, _w2

YEARS = (2021, 2022, 2023, 2024, 2025)
_PART_II_YEARS = (2024, 2025)
_ADDITIONAL_MEDICARE_THRESHOLD = 200_000.0  # single filer, IRC §3101(b)(2)


def _additional_medicare_withheld(year):
    wages = 300_000.0
    w2 = _w2(year, "Example Employer", wages, 70_000.0)
    w2 = dataclasses.replace(w2, medicare_tax_withheld=round(
        wages * 0.0145
        + (wages - _ADDITIONAL_MEDICARE_THRESHOLD) * 0.009, 2))
    return Scenario(config=_battery_config(year), w2s=[w2])


def _se_over_threshold(year):
    return Scenario(
        config=_battery_config(year),
        w2s=[_w2(year, "Example Employer", 100_000.0, 18_000.0)],
        schedule_c_businesses=[ScheduleCBusiness(
            description="Example Survey Studio", business_code="541990",
            gross_receipts=112_000.0, supplies=2_000.0)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "additional-medicare-withheld": _additional_medicare_withheld,
    "se-over-threshold": _se_over_threshold,
}


def years_for(name: str) -> tuple[int, ...]:
    return _PART_II_YEARS if name == "se-over-threshold" else YEARS


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
