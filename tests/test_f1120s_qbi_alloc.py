import unittest
from tenforty.forms import f1120s
from tenforty.models import SCorp199AInfo
from tests._scorp_fixtures import _make_v1_scenario


class QbiAllocationTests(unittest.TestCase):
    def _allocs(self, *, ownership, obi, section_199a=None):
        scen = _make_v1_scenario(
            shareholder_pcts=ownership, gross_receipts=obi, section_199a=section_199a,
        )
        return f1120s.compute(scen, upstream={})["f1120s_sch_k1_allocations"]

    def test_qbi_defaults_to_ordinary_business_income(self):
        # single 100% owner; box_17v_qbi tracks box_1 by default (no override)
        allocs = self._allocs(ownership=[100.0], obi=100_000.0)
        self.assertEqual(allocs[0].box_17v_qbi, allocs[0].box_1_ordinary_business_income)
        self.assertEqual(allocs[0].box_17v_w2_wages, 0.0)
        self.assertEqual(allocs[0].box_17v_ubia, 0.0)

    def test_qbi_override_replaces_default(self):
        allocs = self._allocs(
            ownership=[100.0], obi=100_000.0,
            section_199a=SCorp199AInfo(qbi_override=80_000.0, w2_wages=40_000.0, ubia=250_000.0),
        )
        self.assertEqual(allocs[0].box_17v_qbi, 80_000.0)
        self.assertEqual(allocs[0].box_17v_w2_wages, 40_000.0)
        self.assertEqual(allocs[0].box_17v_ubia, 250_000.0)

    def test_items_allocate_pro_rata(self):
        allocs = self._allocs(
            ownership=[60.0, 40.0], obi=100_000.0,
            section_199a=SCorp199AInfo(w2_wages=50_000.0, ubia=200_000.0),
        )
        self.assertAlmostEqual(allocs[0].box_17v_w2_wages, 30_000.0)
        self.assertAlmostEqual(allocs[1].box_17v_w2_wages, 20_000.0)
        self.assertAlmostEqual(allocs[0].box_17v_ubia, 120_000.0)
        self.assertAlmostEqual(allocs[1].box_17v_ubia, 80_000.0)

    def test_qbi_defaults_allocate_pro_rata_across_shareholders(self):
        # two shareholders, 60/40, no qbi_override: box_17v_qbi must track
        # each shareholder's own pro-rata share of Sch K line 1 (box 1),
        # not a single-owner default. Net ordinary business income here is
        # 100_000 gross receipts minus the fixture's 30_000 default
        # compensation-of-officers deduction = 70_000, split 60/40.
        allocs = self._allocs(ownership=[60.0, 40.0], obi=100_000.0)
        self.assertAlmostEqual(allocs[0].box_17v_qbi, allocs[0].box_1_ordinary_business_income)
        self.assertAlmostEqual(allocs[1].box_17v_qbi, allocs[1].box_1_ordinary_business_income)
        self.assertAlmostEqual(allocs[0].box_17v_qbi, 42_000.0)
        self.assertAlmostEqual(allocs[1].box_17v_qbi, 28_000.0)
