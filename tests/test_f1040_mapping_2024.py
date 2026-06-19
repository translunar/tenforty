import unittest

from tenforty.mappings.f1040 import F1040


class F1040Mapping2024Tests(unittest.TestCase):
    def test_2024_outputs_cover_core_keys(self):
        out = F1040.OUTPUTS[2024]
        for key in ("agi", "taxable_income", "total_tax", "standard_deduction"):
            self.assertIn(key, out)
