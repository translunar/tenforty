"""Schedule E emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers the Schedule E cells no other battery row sets:

* property columns B and C (three rentals on one return);
* every per-column expense line 5-19 (each property states every expense);
* line 22 (the deductible rental loss, per column) and line 25 (losses),
  on returns whose rental losses Form 8582 allows in full (modified AGI
  under the special allowance's phase-out, losses inside it);
* the line A / line B Form 1099 answers in each stated combination
  (TY2022 on: TY2021 cannot print them, so the 2021 rows leave them
  unstated);
* Part II rows a-d with each of the four amount cells (passive income,
  passive loss, nonpassive income, nonpassive loss): four K-1s, one of
  each kind, rotated through the rows across four scenarios. The passive
  loss is smaller than the passive income, so Form 8582 allows it in full.
  The nonpassive loss is an S corporation's from TY2022, so the line 28
  column (e) basis-computation box prints; TY2021 maps no such box and
  refuses an S corporation loss, so the 2021 rows take it from a
  partnership instead.

Every scenario runs in every year 2021-2025. All identities and amounts are
fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import FilingStatus, RentalProperty, Scenario, ScheduleK1
from tests.fixtures.spine_battery import _battery_config, _w2

YEARS = (2021, 2022, 2023, 2024, 2025)
EIN = "00-0000000"


def _answers(year, payments, filed):
    """The line A / line B answers, stated only from TY2022 (the feature
    floor: a TY2021 Schedule E cannot print them)."""
    if year < 2022:
        return {}
    out = {"payments_requiring_1099s": payments}
    if filed is not None:
        out["filed_required_1099s"] = filed
    return out


def _rental(n, rents, personal_use_days=0, **expenses):
    return RentalProperty(
        address=f"{n} Synthetic Way", property_type=1,
        fair_rental_days=365 - personal_use_days,
        personal_use_days=personal_use_days, rents_received=rents,
        acknowledges_depreciation_stated_outside_macrs=True, **expenses)


def _every_expense(scale):
    """One amount on every expense line 5-19 (line 18 stated)."""
    return dict(
        advertising=100.0 * scale, auto_and_travel=110.0 * scale,
        cleaning_and_maintenance=120.0 * scale, commissions=130.0 * scale,
        insurance=140.0 * scale, legal_and_professional_fees=150.0 * scale,
        management_fees=160.0 * scale, mortgage_interest=170.0 * scale,
        other_interest=180.0 * scale, repairs=190.0 * scale,
        supplies=200.0 * scale, taxes=210.0 * scale, utilities=220.0 * scale,
        depreciation=230.0 * scale, other_expenses=240.0 * scale)


def _scenario(year, wages, *, answers=None, rentals=(), k1s=(), **config):
    return Scenario(
        config=_battery_config(year, **(answers or {}), **config),
        w2s=[_w2(year, employer="Synthetic Employer E", wages=wages,
                 federal_tax_withheld=round(wages * 0.12, 2))],
        rental_properties=list(rentals),
        schedule_k1s=list(k1s),
    )


def _three_rentals_every_expense(year):
    # Every column prints every line, personal-use days included; each
    # property nets income (line 24).
    return _scenario(
        year, 90_000.0, answers=_answers(year, True, True),
        rentals=[_rental(100 + i, 20_000.0 + 1_000.0 * i,
                         personal_use_days=3 + i, **_every_expense(1 + i))
                 for i in range(3)])


def _rental_losses_b_and_c(year):
    # Column A nets income; B and C net losses Form 8582 allows in full.
    return _scenario(
        year, 50_000.0, answers=_answers(year, True, False),
        rentals=[_rental(200, 18_000.0, mortgage_interest=6_000.0,
                         taxes=2_000.0, depreciation=3_000.0),
                 _rental(201, 8_000.0, mortgage_interest=7_000.0,
                         taxes=2_000.0, depreciation=2_500.0),
                 _rental(202, 6_000.0, mortgage_interest=5_500.0,
                         repairs=1_500.0, depreciation=2_000.0)])


def _rental_loss_a(year):
    # A single rental whose loss Form 8582 allows in full.
    return _scenario(
        year, 50_000.0, answers=_answers(year, False, None),
        rentals=[_rental(300, 9_000.0, mortgage_interest=8_000.0,
                         taxes=2_000.0, depreciation=3_000.0)])


_K1_CONFIG = dict(
    acknowledges_qbi_below_threshold=True,
    acknowledges_unlimited_at_risk=True,
    basis_tracked_externally=True,
    acknowledges_no_partnership_se_earnings=True,
    acknowledges_no_section_1231_gain=True,
    acknowledges_no_more_than_four_k1s=True,
    acknowledges_no_k1_credits=True,
    acknowledges_no_section_179=True,
    acknowledges_no_estate_trust_k1=True,
    acknowledges_form_7203_attached_separately=True,
)

# One K-1 of each Part II amount kind: (name, entity type, material
# participation, ordinary business income).
_K1_KINDS = (
    ("Synthetic Nonpassive Income Inc", "s_corp", True, 7_000.0),
    ("Synthetic Passive Income LP", "partnership", False, 6_000.0),
    ("Synthetic Passive Loss LP", "partnership", False, -2_000.0),
    ("Synthetic Nonpassive Loss Inc", "s_corp", True, -1_500.0),
)


def _k1_kinds(year):
    if year >= 2022:
        return _K1_KINDS
    return _K1_KINDS[:3] + (
        ("Synthetic Nonpassive Loss LP", "partnership", True, -1_500.0),)


def _k1_rotation(shift):
    def build(year):
        kinds = _k1_kinds(year)
        kinds = kinds[shift:] + kinds[:shift]
        return _scenario(
            year, 80_000.0, **_K1_CONFIG,
            k1s=[ScheduleK1(entity_name=name, entity_ein=EIN,
                            entity_type=etype, material_participation=mp,
                            ordinary_business_income=obi)
                 for name, etype, mp, obi in kinds])
    return build


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "three-rentals-every-expense": _three_rentals_every_expense,
    "rental-losses-b-and-c": _rental_losses_b_and_c,
    "rental-loss-a": _rental_loss_a,
    **{f"k1-rows-rotation-{shift}": _k1_rotation(shift)
       for shift in range(4)},
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
