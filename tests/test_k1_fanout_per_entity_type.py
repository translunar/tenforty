"""Per-entity-type K-1 fan-out validated against the hand-coded oracle."""

import unittest

import pytest

from tenforty.forms import sch_b as form_sch_b
from tenforty.forms import sch_d as form_sch_d
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import ScheduleK1
from tests.oracles import k1_reference

from tests.helpers import make_k1_scenario


def _supported_k1(entity_type: str, **overrides) -> ScheduleK1:
    """Shape for s_corp / partnership K-1 — box 1 is OBI."""
    defaults = dict(
        entity_name=f"Fake {entity_type} Inc",
        entity_ein="00-0000000",
        entity_type=entity_type,
        material_participation=True,
        ordinary_business_income=40_000.0,
        interest_income=200.0,
        ordinary_dividends=150.0,
        qualified_dividends=120.0,
        net_short_term_capital_gain=100.0,
        net_long_term_capital_gain=500.0,
        qbi_amount=40_000.0,
    )
    defaults.update(overrides)
    return ScheduleK1(**defaults)


@pytest.mark.oracle
class K1SupportedEntityFanoutTests(unittest.TestCase):
    """s_corp and partnership K-1s route correctly through all four forms."""

    def _check_supported_entity(self, entity_type: str):
        k1 = _supported_k1(entity_type)
        s = make_k1_scenario()
        s.schedule_k1s = [k1]
        part_ii_fields, fanout = form_sch_e_part_ii.compute(s, upstream={})
        sch_b = form_sch_b.compute(
            s, upstream={"k1_fanout": fanout, "f1040": {}},
        )
        sch_d = form_sch_d.compute(
            s, upstream={"k1_fanout": fanout},
        )

        expected = k1_reference.k1_to_expected_outputs(k1)
        row = expected["sch_e_part_ii_row"]
        self.assertEqual(
            part_ii_fields["sch_e_part_ii_row_a_nonpassive_income"],
            round(row["nonpassive_income"]),
        )
        self.assertEqual(
            part_ii_fields["sch_e_part_ii_row_a_passive_income"],
            round(row["passive_income"]),
        )

        sch_b_adds = expected["sch_b_additions"]
        sch_b_interest_from_k1 = sum(
            p["amount"] for p in sch_b.get("interest_payers", [])
            if p["payer"] == k1.entity_name
        )
        sch_b_dividends_from_k1 = sum(
            p["amount"] for p in sch_b.get("dividend_payers", [])
            if p["payer"] == k1.entity_name
        )
        self.assertEqual(sch_b_interest_from_k1, sch_b_adds["interest"])
        self.assertEqual(sch_b_dividends_from_k1, sch_b_adds["ordinary_dividends"])

        sch_d_adds = expected["sch_d_additions"]
        self.assertEqual(
            round(sum(fanout.sch_d_short_term_additions)),
            round(sch_d_adds["short_term"]),
        )
        self.assertEqual(
            round(sum(fanout.sch_d_long_term_additions)),
            round(sch_d_adds["long_term"]),
        )

        self.assertEqual(
            round(fanout.qbi_aggregate),
            round(expected["qbi_amount"]),
        )

    def test_s_corp(self):
        self._check_supported_entity("s_corp")

    def test_partnership(self):
        self._check_supported_entity("partnership")


class EstateTrustIsRejectedTests(unittest.TestCase):
    """1041 K-1 income is out of Plan D's scope (Sch E Part III)."""

    def test_estate_trust_raises_even_with_valid_interest_routing(self):
        """Even a correctly-shaped 1041 K-1 (box 1 in interest_income,
        not ordinary_business_income) is rejected by compute, because
        Sch E Part III is not implemented in Plan D."""
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake Trust",
            entity_ein="00-0000000",
            entity_type="estate_trust",
            material_participation=True,
            interest_income=2_000.0,
            ordinary_business_income=0.0,
        )]
        with self.assertRaisesRegex(NotImplementedError, "Sch E Part III"):
            form_sch_e_part_ii.compute(s, upstream={})


if __name__ == "__main__":
    unittest.main()
