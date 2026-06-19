import math
import unittest

from tenforty.params.federal import load
from tenforty.models import FilingStatus


class FederalParamsTests(unittest.TestCase):
    def test_2025_single_structure_and_spot_values(self):
        p = load(2025)
        single = FilingStatus.SINGLE.value
        # 2025 standard deduction, single (IRS published).
        self.assertEqual(p.standard_deduction[single], 15_750)
        # QDCGT 0%/15% breakpoints, single (IRS published 2025).
        self.assertEqual(p.qdcgt_breakpoints[single], (48_350, 533_400))
        # Additional Medicare threshold, single.
        self.assertEqual(p.addl_medicare_threshold[single], 200_000)
        # Brackets ascend and terminate at infinity.
        bounds = [b for b, _ in p.ordinary_brackets]
        self.assertEqual(bounds, sorted(bounds))
        self.assertTrue(math.isinf(p.ordinary_brackets[-1][0]))

    def test_unknown_year_raises(self):
        with self.assertRaises(ValueError):
            load(1999)
