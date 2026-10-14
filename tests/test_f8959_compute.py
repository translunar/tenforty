"""Form 8959 native-Python compute tests."""

import logging
import unittest

import ast
import dataclasses
import inspect
from unittest import mock

from tenforty import orchestrator
from tenforty.forms import f8959
from tenforty.forms.f8959 import compute
from tenforty.models import FilingStatus, W2
from tenforty.params.federal import load as load_federal
from tenforty.rounding import irs_round

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

    def _over_threshold(self, status):
        """300,000 of Medicare wages under ``status``; line 5 and line 18
        are measured against the status's params column."""
        threshold = load_federal(2025).for_status(status).addl_medicare_threshold
        wages = 300_000
        self.assertGreater(wages, threshold)
        scenario = make_simple_scenario()
        scenario.config.filing_status = status
        scenario.w2s = [_w2(wages)]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["f8959_line_5"], threshold)
        self.assertEqual(
            result["f8959_line_18"],
            irs_round((wages - threshold) * f8959._ADDITIONAL_MEDICARE_RATE))

    def test_mfj_threshold_from_params(self):
        self._over_threshold(FilingStatus.MARRIED_FILING_JOINTLY)

    def test_mfs_threshold_from_params(self):
        self._over_threshold(FilingStatus.MARRIED_FILING_SEPARATELY)


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


class F8959SingleSourceTests(unittest.TestCase):
    """The Additional Medicare threshold has one source: params, read
    through the status accessor, in both f8959 and the orchestrator's
    _should_emit_8959 fallback."""

    _SENTINEL = 123_457  # synthetic; not any year's threshold

    def test_threshold_comes_from_params(self):
        real = load_federal(2025)
        self.assertNotIn(self._SENTINEL, real.addl_medicare_threshold.values())
        fake = dataclasses.replace(real, addl_medicare_threshold={
            **real.addl_medicare_threshold,
            FilingStatus.MARRIED_FILING_JOINTLY.value: self._SENTINEL})

        def load(year):
            self.assertEqual(year, 2025)
            return fake

        scenario = make_simple_scenario()
        scenario.config.filing_status = FilingStatus.MARRIED_FILING_JOINTLY
        orch = orchestrator.ReturnOrchestrator.__new__(
            orchestrator.ReturnOrchestrator)
        with mock.patch("tenforty.params.federal.load", load), \
                mock.patch.object(f8959, "load_federal_params", load):
            scenario.w2s = [_w2(self._SENTINEL + 1_000)]
            self.assertEqual(
                compute(scenario, upstream={"f1040": {}})["f8959_line_5"],
                self._SENTINEL)
            self.assertTrue(orch._should_emit_8959(scenario, {}))
            scenario.w2s = [_w2(self._SENTINEL - 1_000)]
            self.assertFalse(orch._should_emit_8959(scenario, {}))

    def test_no_hardcoded_threshold_dict(self):
        def keyed_by_status(node):
            return (isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Attribute)
                and isinstance(k.value, ast.Name)
                and k.value.id == "FilingStatus" for k in node.keys)
                and all(isinstance(v, ast.Constant) and isinstance(v.value, int)
                        for v in node.values))

        for module in (f8959, orchestrator):
            with self.subTest(module=module.__name__):
                tree = ast.parse(inspect.getsource(module))
                found = [n.lineno for n in ast.walk(tree) if keyed_by_status(n)]
                self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
