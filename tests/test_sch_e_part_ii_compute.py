"""Schedule E Part II native compute tests."""

import unittest

from tenforty.forms import sch_e_part_ii
from tenforty.models import ScheduleK1

from tests.helpers import make_k1_scenario, make_simple_scenario


def _scorp_k1(**overrides) -> ScheduleK1:
    defaults = dict(
        entity_name="Fake S-Corp Inc",
        entity_ein="00-0000000",
        entity_type="s_corp",
        material_participation=True,
        ordinary_business_income=50_000.0,
    )
    defaults.update(overrides)
    return ScheduleK1(**defaults)


class GateTests(unittest.TestCase):
    """make_simple_scenario sets K-1 attestations to False, so any K-1 trips
    the gate. Used to exercise the gate itself."""

    def test_five_k1s_raises_when_not_acknowledged(self):
        s = make_simple_scenario()
        s.schedule_k1s = [_scorp_k1() for _ in range(5)]
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_no_more_than_four_k1s"
        ):
            sch_e_part_ii.compute(s, upstream={})

    def test_section_179_raises_when_not_acknowledged(self):
        s = make_k1_scenario()
        s.config.acknowledges_no_section_179 = False
        s.schedule_k1s = [_scorp_k1(section_179_deduction=1_000.0)]
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_no_section_179"
        ):
            sch_e_part_ii.compute(s, upstream={})

    def test_section_1231_raises_when_not_acknowledged(self):
        s = make_k1_scenario()
        s.config.acknowledges_no_section_1231_gain = False
        s.schedule_k1s = [_scorp_k1(section_1231_gain=5_000.0)]
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_no_section_1231_gain"
        ):
            sch_e_part_ii.compute(s, upstream={})

    def test_partnership_se_earnings_raises_when_not_acknowledged(self):
        s = make_k1_scenario()
        s.config.acknowledges_no_partnership_se_earnings = False
        s.schedule_k1s = [_scorp_k1(
            entity_type="partnership",
            entity_name="Example LLC",
            partnership_self_employment_earnings=10_000.0,
        )]
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_no_partnership_se_earnings"
        ):
            sch_e_part_ii.compute(s, upstream={})

    def test_estate_trust_k1_always_raises(self):
        """Estate/trust K-1 income goes on Sch E Part III — scoped out of
        Plan D. The attestation is 'I've read the docs', not 'please proceed'."""
        s = make_k1_scenario()
        # Even with acknowledges_no_estate_trust_k1=True, compute must raise
        # if an estate_trust K-1 is actually present.
        s.schedule_k1s = [_scorp_k1(
            entity_type="estate_trust",
            entity_name="Fake Trust",
            ordinary_business_income=0.0,
            interest_income=2_000.0,
        )]
        with self.assertRaisesRegex(
            NotImplementedError, "Sch E Part III"
        ):
            sch_e_part_ii.compute(s, upstream={})


class RowLayoutTests(unittest.TestCase):
    def test_one_scorp_active_row_a_nonpassive(self):
        s = make_k1_scenario()
        s.schedule_k1s = [_scorp_k1(ordinary_business_income=50_000.0)]
        out, _ = sch_e_part_ii.compute(s, upstream={})
        self.assertEqual(out["sch_e_part_ii_row_a_name"], "Fake S-Corp Inc")
        self.assertEqual(out["sch_e_part_ii_row_a_ein"], "00-0000000")
        self.assertEqual(out["sch_e_part_ii_row_a_entity_type_s_corp"], "X")
        self.assertEqual(out["sch_e_part_ii_row_a_nonpassive_income"], 50_000)
        self.assertEqual(out["sch_e_part_ii_row_a_passive_income"], 0)

    def test_partnership_passive_row_a_passive(self):
        s = make_k1_scenario()
        s.schedule_k1s = [_scorp_k1(
            entity_type="partnership",
            entity_name="Example LLC",
            material_participation=False,
            ordinary_business_income=10_000.0,
        )]
        out, _ = sch_e_part_ii.compute(s, upstream={})
        self.assertEqual(out["sch_e_part_ii_row_a_passive_income"], 10_000)
        self.assertEqual(out["sch_e_part_ii_row_a_nonpassive_income"], 0)


class FanoutTests(unittest.TestCase):
    def test_interest_and_qbi_in_fanout(self):
        s = make_k1_scenario()
        s.schedule_k1s = [_scorp_k1(
            interest_income=500.0,
            ordinary_dividends=250.0,
            qualified_dividends=200.0,
            qbi_amount=50_000.0,
        )]
        _, fan = sch_e_part_ii.compute(s, upstream={})
        self.assertEqual(len(fan.sch_b_interest_additions), 1)
        self.assertEqual(fan.sch_b_interest_additions[0].payer, "Fake S-Corp Inc")
        self.assertEqual(fan.sch_b_interest_additions[0].amount, 500.0)
        self.assertEqual(len(fan.sch_b_dividend_additions), 1)
        self.assertEqual(fan.sch_b_dividend_additions[0].payer, "Fake S-Corp Inc")
        self.assertEqual(fan.sch_b_dividend_additions[0].amount, 250.0)
        self.assertEqual(fan.qualified_dividends_aggregate, 200.0)
        self.assertEqual(fan.qbi_aggregate, 50_000.0)


if __name__ == "__main__":
    unittest.main()
