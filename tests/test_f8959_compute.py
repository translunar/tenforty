"""Form 8959 native-Python compute tests."""

import logging
import unittest

from tenforty.forms.f8959 import compute
from tenforty.models import FilingStatus, W2

from tests.helpers import make_simple_scenario


def _w2(medicare_wages: float, medicare_tax_withheld: float = 0.0) -> W2:
    return W2(
        employer="X",
        wages=medicare_wages,
        federal_tax_withheld=0.0,
        ss_wages=min(medicare_wages, 168600.0),
        ss_tax_withheld=0.0,
        medicare_wages=medicare_wages,
        medicare_tax_withheld=medicare_tax_withheld,
    )


class F8959HeaderTests(unittest.TestCase):
    def test_taxpayer_header_from_config(self):
        scenario = make_simple_scenario()
        scenario.config.first_name = "Alex"
        scenario.config.last_name = "Rivera"
        scenario.config.ssn = "000-12-3456"
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["taxpayer_name"], "Alex Rivera")
        self.assertEqual(result["taxpayer_ssn"], "000-12-3456")


class F8959BelowThresholdTests(unittest.TestCase):
    def test_single_filer_below_200k_owes_zero(self):
        scenario = make_simple_scenario()
        scenario.w2s = [_w2(150_000, medicare_tax_withheld=2175)]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["f8959_line_1"], 150000)
        self.assertEqual(result["f8959_line_5"], 200000)
        self.assertEqual(result["f8959_line_6"], 0)
        self.assertEqual(result["f8959_line_7"], 0)
        self.assertEqual(result["f8959_line_18"], 0)
        self.assertEqual(result["f8959_line_24"], 0)


class F8959AboveThresholdTests(unittest.TestCase):
    def test_single_filer_at_300k_owes_additional_medicare(self):
        scenario = make_simple_scenario()
        scenario.w2s = [_w2(300_000, medicare_tax_withheld=5200)]
        result = compute(scenario, upstream={"f1040": {}})
        # $100k above threshold × 0.9% = $900
        self.assertEqual(result["f8959_line_6"], 100000)
        self.assertEqual(result["f8959_line_7"], 900)
        self.assertEqual(result["f8959_line_18"], 900)
        # Line 21: 300k × 1.45% = 4350; line 22: 5200 − 4350 = 850; line 24: 850
        self.assertEqual(result["f8959_line_21"], 4350)
        self.assertEqual(result["f8959_line_22"], 850)
        self.assertEqual(result["f8959_line_24"], 850)

    def test_mfj_threshold_is_250k(self):
        scenario = make_simple_scenario()
        scenario.config.filing_status = FilingStatus.MARRIED_JOINTLY
        scenario.w2s = [_w2(300_000)]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["f8959_line_5"], 250000)
        # $50k above × 0.9% = $450
        self.assertEqual(result["f8959_line_18"], 450)

    def test_mfs_threshold_is_125k(self):
        scenario = make_simple_scenario()
        scenario.config.filing_status = FilingStatus.MARRIED_SEPARATELY
        scenario.w2s = [_w2(200_000)]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["f8959_line_5"], 125000)
        # $75k above × 0.9% = $675
        self.assertEqual(result["f8959_line_18"], 675)


class F8959MultipleEmployersTests(unittest.TestCase):
    def test_medicare_wages_summed_across_w2s(self):
        scenario = make_simple_scenario()
        scenario.w2s = [
            _w2(180_000, medicare_tax_withheld=2610),
            _w2(140_000, medicare_tax_withheld=2030),
        ]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["f8959_line_1"], 320000)
        self.assertEqual(result["f8959_line_19"], 4640)


class F8959OracleCrossCheckTests(unittest.TestCase):
    def test_line_18_matches_oracle_no_warning(self):
        scenario = make_simple_scenario()
        scenario.w2s = [_w2(300_000, medicare_tax_withheld=5200)]
        with self.assertNoLogs("tenforty.forms.f8959", level=logging.WARNING):
            compute(scenario, upstream={"f1040": {
                "f8959_tax_total": 900,
                "additional_medicare_withheld": 850,
            }})

    def test_line_18_divergence_logs_warning(self):
        scenario = make_simple_scenario()
        scenario.w2s = [_w2(300_000, medicare_tax_withheld=5200)]
        with self.assertLogs("tenforty.forms.f8959", level=logging.WARNING) as cm:
            compute(scenario, upstream={"f1040": {"f8959_tax_total": 999}})
        self.assertTrue(
            any("diverges" in r.getMessage() and "f8959_line_18" in r.getMessage()
                for r in cm.records),
            f"expected line 18 divergence warning; got {[r.getMessage() for r in cm.records]}",
        )


if __name__ == "__main__":
    unittest.main()
