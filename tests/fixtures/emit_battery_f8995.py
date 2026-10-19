"""Form 8995 emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers Form 8995 line 1's rows ii-v (Juno's per-source-rows ruling, phase
K): a return with five QBI sources (one Schedule C business and four S
corporation K-1s) fills rows i-v, and a two-source return prints rows i-ii
with iii-v blank. Every scenario runs in every year 2021-2025; amounts stay
far below every year's Form 8995 simplified-method threshold.

All identities and amounts are fully synthetic.
"""
from collections.abc import Callable

from tenforty.models import Scenario, ScheduleCBusiness, ScheduleK1
from tests.fixtures.spine_battery import _battery_config, _w2

YEARS = (2021, 2022, 2023, 2024, 2025)

_K1_ATTESTATIONS = dict(
    acknowledges_qbi_below_threshold=True,
    acknowledges_unlimited_at_risk=True,
    basis_tracked_externally=True,
    acknowledges_no_partnership_se_earnings=True,
    acknowledges_no_section_1231_gain=True,
    acknowledges_no_more_than_four_k1s=True,
    acknowledges_no_k1_credits=True,
    acknowledges_no_section_179=True,
    acknowledges_no_estate_trust_k1=True,
    prior_year_itemized=False,
)


def _k1(name, qbi):
    return ScheduleK1(entity_name=name, entity_ein="00-0000000",
                      entity_type="s_corp", material_participation=True,
                      ordinary_business_income=qbi, qbi_amount=qbi)


def _five_sources(year):
    return Scenario(
        config=_battery_config(year, **_K1_ATTESTATIONS),
        w2s=[_w2(year, employer="Example Employer", wages=60_000.0,
                 federal_tax_withheld=8_000.0)],
        schedule_c_businesses=[ScheduleCBusiness(
            description="Example Map Studio", gross_receipts=12_000.0,
            supplies=2_000.0)],
        schedule_k1s=[_k1("Example Orchard Inc", 3_000.0),
                      _k1("Example Foundry Inc", 2_000.0),
                      _k1("Example Ferry Inc", 1_500.0),
                      _k1("Example Loom Inc", 1_000.0)],
    )


def _two_k1_sources(year):
    return Scenario(
        config=_battery_config(year, **_K1_ATTESTATIONS),
        w2s=[_w2(year, employer="Example Employer", wages=60_000.0,
                 federal_tax_withheld=8_000.0)],
        schedule_k1s=[_k1("Example Orchard Inc", 4_000.0),
                      _k1("Example Foundry Inc", 2_500.0)],
    )


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "five-sources": _five_sources,
    "two-k1-sources": _two_k1_sources,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
