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
    _, fanout = form_sch_e_part_ii.compute(s, upstream={})
    sch_e = form_sch_e.compute(s, upstream={"f1040": {}})
    return f8582.compute(s, upstream={
        "f1040": {"magi": magi},
        "sch_e": sch_e,
        "k1_fanout": fanout,
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


def _rentals_at(*addresses: str) -> list[RentalProperty]:
    return [RentalProperty(
        address=address, property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=0.0) for address in addresses]


def _run_with_line_21s(addresses, line_21s):
    """Form 8582 over rentals whose printed Schedule E line 21s are handed
    in directly, one per column in order."""
    s = make_k1_scenario()
    s.schedule_k1s = []
    s.rental_properties = _rentals_at(*addresses)
    return f8582.compute(s, upstream={
        "f1040": {"magi": 50_000},
        "sch_e": {f"sch_e_property_{letter}_income_loss": net
                  for letter, net in zip("abc", line_21s)},
    })


class EveryRentalColumnIsAPassiveActivityTests(unittest.TestCase):
    def test_lines_1a_and_1b_take_each_column_separately(self):
        out = _run_with_line_21s(
            ("100 Example Street", "200 Example Street",
             "300 Example Street"), (8_000, -4_000, 4_000))
        # Not the netted 8,000 / 0.
        self.assertEqual(out["f8582_line_1a_activities_with_income"], 12_000)
        self.assertEqual(out["f8582_line_1b_activities_with_loss"], 4_000)

    def test_two_rentals_sharing_an_address_are_two_activities(self):
        out = _run_with_line_21s(
            ("100 Example Street", "100 Example Street"), (-3_000, -2_000))
        self.assertEqual(out["f8582_line_1b_activities_with_loss"], 5_000)

    def test_a_single_rental_result_is_unchanged(self):
        out = _run_with_line_21s(("100 Example Street",), (-4_000,))
        self.assertEqual(out["f8582_line_1a_activities_with_income"], 0)
        self.assertEqual(out["f8582_line_1b_activities_with_loss"], 4_000)


class MissingColumnLine21Tests(unittest.TestCase):
    """A Schedule E result that carries some columns' line 21 but not
    another's is a wiring fault: Form 8582 raises, it does not read zero."""

    _ADDRESSES = ("100 Example Street", "200 Example Street",
                  "300 Example Street")

    def _compute(self, sch_e: dict) -> dict:
        s = make_k1_scenario()
        s.schedule_k1s = []
        s.rental_properties = _rentals_at(*self._ADDRESSES)
        return f8582.compute(s, upstream={
            "f1040": {"magi": 50_000}, "sch_e": sch_e})

    def test_a_column_without_its_line_21_key_raises(self):
        with self.assertRaises(KeyError) as cm:
            self._compute({
                "sch_e_property_a_income_loss": 8_000,
                "sch_e_property_c_income_loss": 4_000,
            })
        message = cm.exception.args[0]
        self.assertIn("Form 8582", message)
        self.assertIn("'sch_e_property_b_income_loss'", message)
        self.assertIn("'200 Example Street'", message)

    def test_the_same_upstream_with_every_column_computes(self):
        # Twin: the missing key supplied, nothing else changed.
        out = self._compute({
            "sch_e_property_a_income_loss": 8_000,
            "sch_e_property_b_income_loss": -4_000,
            "sch_e_property_c_income_loss": 4_000,
        })
        self.assertEqual(out["f8582_line_1a_activities_with_income"], 12_000)
        self.assertEqual(out["f8582_line_1b_activities_with_loss"], 4_000)


if __name__ == "__main__":
    unittest.main()
