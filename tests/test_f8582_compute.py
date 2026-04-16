"""Form 8582 passive activity loss compute tests."""

import unittest

from tenforty.models import FilingStatus, RentalProperty, ScheduleK1
from tenforty.forms import f8582
from tenforty.forms import sch_e as form_sch_e
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii

from tests.helpers import make_k1_scenario


def _passive_k1_loss(name: str, loss: float, carryforward: float = 0.0) -> ScheduleK1:
    return ScheduleK1(
        entity_name=name,
        entity_ein="00-0000000",
        entity_type="partnership",
        material_participation=False,
        net_rental_real_estate=-abs(loss),
        prior_year_passive_loss_carryforward=carryforward,
    )


def _run(s, magi):
    part_ii = form_sch_e_part_ii.compute(s, upstream={})
    sch_e = form_sch_e.compute(s, upstream={"f1040": {}})
    return f8582.compute(s, upstream={
        "f1040": {"magi": magi},
        "sch_e": sch_e,
        "_k1_fanout": part_ii["_k1_fanout"],
    })


class F8582SpecialAllowanceSingleTests(unittest.TestCase):
    def setUp(self):
        self.s = make_k1_scenario()
        self.s.config.filing_status = FilingStatus.SINGLE
        self.s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=10_000.0, mortgage_interest=20_000.0,
        )]

    def test_magi_under_100k_full_25k(self):
        out = _run(self.s, magi=80_000)
        self.assertEqual(out["f8582_special_allowance"], 25_000)

    def test_magi_125k_half_phaseout(self):
        out = _run(self.s, magi=125_000)
        self.assertEqual(out["f8582_special_allowance"], 12_500)

    def test_magi_over_150k_zero(self):
        out = _run(self.s, magi=160_000)
        self.assertEqual(out["f8582_special_allowance"], 0)


class F8582SpecialAllowanceMFSTests(unittest.TestCase):
    def _mfs_scenario(self, lived_with_spouse: bool):
        s = make_k1_scenario()
        s.config.filing_status = FilingStatus.MARRIED_SEPARATELY
        s.config.mfs_lived_with_spouse_any_time = lived_with_spouse
        s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=10_000.0, mortgage_interest=20_000.0,
        )]
        return s

    def test_mfs_apart_full_year_full_12_5k_under_50k(self):
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=40_000)
        self.assertEqual(out["f8582_special_allowance"], 12_500)

    def test_mfs_apart_phaseout_band(self):
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=62_500)
        self.assertEqual(out["f8582_special_allowance"], 6_250)

    def test_mfs_apart_over_75k_zero(self):
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=80_000)
        self.assertEqual(out["f8582_special_allowance"], 0)

    def test_mfs_lived_with_spouse_zero_regardless_of_magi(self):
        s = self._mfs_scenario(lived_with_spouse=True)
        out = _run(s, magi=40_000)
        self.assertEqual(out["f8582_special_allowance"], 0)


class F8582AllowedLossTests(unittest.TestCase):
    def test_allowed_equals_income_plus_allowance(self):
        s = make_k1_scenario()
        s.schedule_k1s = [_passive_k1_loss("Example LLC", 30_000.0)]
        s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=5_000.0, mortgage_interest=2_000.0,
        )]
        out = _run(s, magi=80_000)
        self.assertEqual(out["f8582_line_11_allowed_loss"], 28_000)

    def test_per_activity_carryforward_prorated(self):
        s = make_k1_scenario()
        s.schedule_k1s = [
            _passive_k1_loss("Example LLC A", 10_000.0),
            _passive_k1_loss("Example LLC B", 40_000.0),
        ]
        out = _run(s, magi=80_000)
        carryforwards = {c["entity_name"]: c["suspended_amount"]
                         for c in out["per_activity_carryforwards"]}
        self.assertEqual(carryforwards["Example LLC A"], 5_000)
        self.assertEqual(carryforwards["Example LLC B"], 20_000)


if __name__ == "__main__":
    unittest.main()
