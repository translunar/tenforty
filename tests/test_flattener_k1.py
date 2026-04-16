"""Flattener dispatch tests for Schedule K-1."""

import unittest

from tenforty.models import ScheduleK1
from tenforty.oracle.flattener import flatten_scenario

from tests.helpers import make_simple_scenario


def _k1(**overrides) -> ScheduleK1:
    defaults = dict(
        entity_name="Fake S-Corp Inc",
        entity_ein="00-0000000",
        entity_type="s_corp",
        material_participation=True,
        ordinary_business_income=50_000.0,
    )
    defaults.update(overrides)
    return ScheduleK1(**defaults)


class FlattenK1Tests(unittest.TestCase):
    def test_k1_scorp_row_a(self):
        s = make_simple_scenario()
        s.schedule_k1s = [_k1()]
        flat = flatten_scenario(s)
        self.assertEqual(flat["k1_a_entity_name"], "Fake S-Corp Inc")
        self.assertEqual(flat["k1_a_entity_ein"], "00-0000000")
        self.assertEqual(flat["k1_a_ordinary_business_income"], 50_000.0)
        # s_corp entity-type box flagged:
        self.assertEqual(flat["k1_a_entity_type_s_corp"], "X")

    def test_k1_partnership_row_b(self):
        s = make_simple_scenario()
        s.schedule_k1s = [
            _k1(entity_type="s_corp"),
            _k1(entity_type="partnership", entity_name="Example LLC",
                ordinary_business_income=20_000.0),
        ]
        flat = flatten_scenario(s)
        self.assertEqual(flat["k1_b_entity_name"], "Example LLC")
        self.assertEqual(flat["k1_b_entity_type_partnership"], "X")

    def test_four_k1s_ok(self):
        s = make_simple_scenario()
        s.schedule_k1s = [_k1() for _ in range(4)]
        flat = flatten_scenario(s)
        self.assertIn("k1_d_entity_name", flat)


if __name__ == "__main__":
    unittest.main()
