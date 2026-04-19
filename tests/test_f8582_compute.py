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
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=70000
        # so 8582 MAGI = 80000 < 100000 threshold → full $25k allowance.
        out = _run(self.s, magi=70_000)
        self.assertEqual(out["f8582_special_allowance"], 25_000)

    def test_magi_125k_half_phaseout(self):
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=115000
        # so 8582 MAGI = 125000 → allowance = 25000 - 0.5*(125000-100000) = 12500.
        out = _run(self.s, magi=115_000)
        self.assertEqual(out["f8582_special_allowance"], 12_500)

    def test_magi_over_150k_zero(self):
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=150000
        # so 8582 MAGI = 160000 >= 150000 phaseout → $0 allowance.
        out = _run(self.s, magi=150_000)
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
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=30000
        # so 8582 MAGI = 40000 < 50000 threshold → full $12.5k allowance.
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=30_000)
        self.assertEqual(out["f8582_special_allowance"], 12_500)

    def test_mfs_apart_phaseout_band(self):
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=52500
        # so 8582 MAGI = 62500 → allowance = 12500 - 0.5*(62500-50000) = 6250.
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=52_500)
        self.assertEqual(out["f8582_special_allowance"], 6_250)

    def test_mfs_apart_over_75k_zero(self):
        # Rental net loss = 10000. 8582 MAGI = agi + 10000. Pass agi=70000
        # so 8582 MAGI = 80000 >= 75000 phaseout → $0 allowance.
        s = self._mfs_scenario(lived_with_spouse=False)
        out = _run(s, magi=70_000)
        self.assertEqual(out["f8582_special_allowance"], 0)

    def test_mfs_lived_with_spouse_zero_regardless_of_magi(self):
        # Lived with spouse → $0 allowance regardless of MAGI.
        s = self._mfs_scenario(lived_with_spouse=True)
        out = _run(s, magi=30_000)
        self.assertEqual(out["f8582_special_allowance"], 0)


class F8582AllowedLossTests(unittest.TestCase):
    def test_allowed_equals_income_plus_allowance(self):
        # Rental net = +3000, K-1 loss = 30000. Net passive = 3000-30000 = -27000.
        # 8582 MAGI = agi - (-27000) = agi + 27000.
        # Pass agi=53000 so 8582 MAGI = 80000 < 100000 → allowance = 25000.
        # allowed = min(3000 + 25000, 30000) = min(28000, 30000) = 28000.
        s = make_k1_scenario()
        s.schedule_k1s = [_passive_k1_loss("Example LLC", 30_000.0)]
        s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=5_000.0, mortgage_interest=2_000.0,
        )]
        out = _run(s, magi=53_000)
        self.assertEqual(out["f8582_line_11_allowed_loss"], 28_000)

    def test_per_activity_carryforward_prorated(self):
        # Two K-1 losses: 10000 + 40000 = 50000. Net passive = -50000.
        # 8582 MAGI = agi + 50000. Pass agi=30000 so 8582 MAGI = 80000 < 100000
        # → allowance = 25000. allowed = min(0 + 25000, 50000) = 25000.
        # suspended = 25000. Prorated: A = 10k/50k * 25k = 5000, B = 20000.
        s = make_k1_scenario()
        s.schedule_k1s = [
            _passive_k1_loss("Example LLC A", 10_000.0),
            _passive_k1_loss("Example LLC B", 40_000.0),
        ]
        out = _run(s, magi=30_000)
        carryforwards = {c["entity_name"]: c["suspended_amount"]
                         for c in out["per_activity_carryforwards"]}
        self.assertEqual(carryforwards["Example LLC A"], 5_000)
        self.assertEqual(carryforwards["Example LLC B"], 20_000)


if __name__ == "__main__":
    unittest.main()
