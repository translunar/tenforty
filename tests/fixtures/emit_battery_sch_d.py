"""Schedule D emit battery (zero-lines audit, [R-ZL-5]): scenario INPUTS
only. The harness compares every emit against the real computation, so no
expected value is written here.

Covers the Schedule D lines no other battery drives nonzero: the Form 8949
path lines 1b and 8b (box A/D lots with an adjustment), lines 2 and 9 (box
B/E: basis not reported to the IRS), lines 5 and 12 (K-1 capital gains),
and line 13 (capital gain distributions). Every scenario carries a Form
1099-B lot so Schedule D attaches; K-1 capital gains or distributions
without one do not attach it today (defect D3, its own lane).

Lines 18 and 19 are deliberately NOT exercised here: a flagged lot prints
them but leaves the tax unchanged (defect D2), and a row would cement that.

Every scenario runs in every year 2021-2025. All identities and amounts
are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import (
    EntityType, FilingStatus, Form1099B, Form1099DIV, Scenario, ScheduleK1,
)
from tests.fixtures.spine_battery import build_wages_only

YEARS = (2021, 2022, 2023, 2024, 2025)
BROKER = "Example Brokerage"


def _lot(year, *, short_term, **kw):
    acquired = f"{year}-01-12" if short_term else f"{year - 3}-02-10"
    fields = dict(broker=BROKER, description="Example Index Fund",
                  date_acquired=acquired, date_sold=f"{year}-07-15",
                  proceeds=24_000.0, cost_basis=18_000.0,
                  short_term=short_term)
    fields.update(kw)
    return Form1099B(**fields)


def _base(year, **config):
    base = build_wages_only(year, FilingStatus.SINGLE)
    if config:
        base = dataclasses.replace(
            base, config=dataclasses.replace(base.config, **config))
    return base


def _box_a_d_adjusted(year):
    # Wash-sale adjusted lots go to Form 8949 boxes A/D (lines 1b, 8b).
    lots = [_lot(year, short_term=st, proceeds=17_000.0, cost_basis=18_000.0,
                 wash_sale_loss_disallowed=400.0) for st in (True, False)]
    return dataclasses.replace(
        _base(year, acknowledges_no_wash_sale_adjustments=True),
        form1099_b=lots)


def _box_b_e_basis_not_reported(year):
    lots = [_lot(year, short_term=st, basis_reported_to_irs=False)
            for st in (True, False)]
    return dataclasses.replace(_base(year), form1099_b=lots)


def _k1_capital_gains(year):
    k1 = ScheduleK1(
        entity_name="Example Ventures LP", entity_ein="00-0000000",
        entity_type=EntityType.PARTNERSHIP, material_participation=True,
        net_short_term_capital_gain=2_000.0,
        net_long_term_capital_gain=5_000.0)
    return dataclasses.replace(
        _base(year), schedule_k1s=[k1],
        form1099_b=[_lot(year, short_term=False)])


def _capital_gain_distributions(year):
    div = Form1099DIV(payer="Example Fund Co", ordinary_dividends=3_000.0,
                      qualified_dividends=2_000.0,
                      capital_gain_distributions=1_200.0)
    return dataclasses.replace(
        _base(year), form1099_div=[div],
        form1099_b=[_lot(year, short_term=False)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "box-a-d-adjusted": _box_a_d_adjusted,
    "box-b-e-basis-not-reported": _box_b_e_basis_not_reported,
    "k1-capital-gains": _k1_capital_gains,
    "capital-gain-distributions": _capital_gain_distributions,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
