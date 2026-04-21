"""Tests for sch_e_part_ii.compute's new tuple return."""

import unittest

from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import (
    EntityType, K1FanoutActivity, K1FanoutData, PayerAmount, ScheduleK1,
)
from tests.helpers import make_simple_scenario


class TestComputeReturnShape(unittest.TestCase):
    def test_compute_returns_tuple_of_dict_and_k1fanoutdata(self) -> None:
        scenario = make_simple_scenario()
        scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
                entity_type=EntityType.S_CORP,
                material_participation=True,
                ordinary_business_income=50000.0, qbi_amount=50000.0,
            ),
        ]
        scenario.config.acknowledges_unlimited_at_risk = True
        scenario.config.basis_tracked_externally = True
        scenario.config.acknowledges_no_k1_credits = True
        result = form_sch_e_part_ii.compute(scenario, upstream={})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        fields, fanout = result
        self.assertIsInstance(fields, dict)
        self.assertIsInstance(fanout, K1FanoutData)
        self.assertEqual(fanout.qbi_aggregate, 50000.0)
        self.assertNotIn("_k1_fanout", fields)

    def test_passive_k1_produces_k1fanoutactivity(self) -> None:
        scenario = make_simple_scenario()
        scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Passive LP", entity_ein="00-0000000",
                entity_type=EntityType.PARTNERSHIP,
                material_participation=False,
                ordinary_business_income=-2000.0,
                prior_year_passive_loss_carryforward=500.0,
            ),
        ]
        scenario.config.acknowledges_unlimited_at_risk = True
        scenario.config.basis_tracked_externally = True
        scenario.config.acknowledges_no_k1_credits = True
        _, fanout = form_sch_e_part_ii.compute(scenario, upstream={})
        self.assertEqual(len(fanout.passive_activities), 1)
        a = fanout.passive_activities[0]
        self.assertIsInstance(a, K1FanoutActivity)
        self.assertEqual(a.entity_name, "Passive LP")
        self.assertEqual(a.entity_type, EntityType.PARTNERSHIP)
        self.assertEqual(a.income, 0)
        self.assertEqual(a.loss, 2000)
        self.assertEqual(a.prior_carryforward, 500)

    def test_payer_amount_for_k1_interest(self) -> None:
        scenario = make_simple_scenario()
        scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Int Source LP", entity_ein="00-0000000",
                entity_type=EntityType.PARTNERSHIP,
                material_participation=True,
                interest_income=250.0,
            ),
        ]
        scenario.config.acknowledges_unlimited_at_risk = True
        scenario.config.basis_tracked_externally = True
        scenario.config.acknowledges_no_k1_credits = True
        _, fanout = form_sch_e_part_ii.compute(scenario, upstream={})
        self.assertEqual(len(fanout.sch_b_interest_additions), 1)
        pa = fanout.sch_b_interest_additions[0]
        self.assertIsInstance(pa, PayerAmount)
        self.assertEqual(pa.payer, "Int Source LP")
        self.assertEqual(pa.amount, 250.0)


class TestK1RowTotalHelper(unittest.TestCase):
    """`_k1_row_total` aggregates the Sch E Part II row-total components
    (ordinary business income + net rental + royalties + other income) after
    IRS rounding per component. Extraction target of SP1-N7."""

    def test_helper_matches_inline_expression(self) -> None:
        from tenforty.forms.sch_e_part_ii import _k1_row_total
        from tenforty.models import EntityType, ScheduleK1
        from tenforty.rounding import irs_round
        k1 = ScheduleK1(
            entity_name="X", entity_ein="00-0000000",
            entity_type=EntityType.S_CORP, material_participation=True,
            ordinary_business_income=1234.56,
            net_rental_real_estate=100.40, other_net_rental=50.10,
            royalties=200.49, other_income=10.01,
        )
        expected = (
            irs_round(1234.56)
            + irs_round(100.40 + 50.10)
            + irs_round(200.49)
            + irs_round(10.01)
        )
        self.assertEqual(expected, _k1_row_total(k1))

    def test_helper_zero_on_empty_k1(self) -> None:
        from tenforty.forms.sch_e_part_ii import _k1_row_total
        from tenforty.models import EntityType, ScheduleK1
        k1 = ScheduleK1(
            entity_name="X", entity_ein="00-0000000",
            entity_type=EntityType.S_CORP, material_participation=True,
        )
        self.assertEqual(0.0, _k1_row_total(k1))
