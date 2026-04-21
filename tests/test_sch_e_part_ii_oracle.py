"""Cross-check forms.sch_e_part_ii against the hand-coded K-1 reference.

Imports ``tests.oracles.k1_reference`` (present on this branch via an
earlier cherry-pick). Uses only the module's documented public API
— the oracle source is not viewed by the implementer.
"""

import unittest

import pytest

from tenforty.forms import sch_e_part_ii
from tenforty.models import ScheduleK1
from tests.oracles import k1_reference

from tests.helpers import make_k1_scenario


@pytest.mark.oracle
class SchEPartIIOracleTests(unittest.TestCase):
    def _assert_row_matches(self, letter: str, k1: ScheduleK1, got: dict):
        expected = k1_reference.k1_to_expected_outputs(k1)
        row = expected["sch_e_part_ii_row"]
        self.assertEqual(
            got[f"sch_e_part_ii_row_{letter}_nonpassive_income"],
            round(row["nonpassive_income"]),
        )
        self.assertEqual(
            got[f"sch_e_part_ii_row_{letter}_nonpassive_loss"],
            round(row["nonpassive_loss"]),
        )
        self.assertEqual(
            got[f"sch_e_part_ii_row_{letter}_passive_income"],
            round(row["passive_income"]),
        )
        self.assertEqual(
            got[f"sch_e_part_ii_row_{letter}_passive_loss"],
            round(row["passive_loss"]),
        )

    def test_scorp_active_matches_oracle(self):
        k1 = ScheduleK1(
            entity_name="Fake S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
        )
        s = make_k1_scenario()
        s.schedule_k1s = [k1]
        got, _ = sch_e_part_ii.compute(s, upstream={})
        self._assert_row_matches("a", k1, got)

    def test_partnership_passive_matches_oracle(self):
        k1 = ScheduleK1(
            entity_name="Example LLC",
            entity_ein="00-0000000",
            entity_type="partnership",
            material_participation=False,
            net_rental_real_estate=-3_000.0,
            prior_year_passive_loss_carryforward=2_000.0,
        )
        s = make_k1_scenario()
        s.schedule_k1s = [k1]
        got, _ = sch_e_part_ii.compute(s, upstream={})
        self._assert_row_matches("a", k1, got)
