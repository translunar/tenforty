"""Unit tests for ReturnOrchestrator.compute_corporate."""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator

from tests._scorp_fixtures import _make_v1_scenario


class ComputeCorporateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_empty_dict_when_no_s_corp_return(self):
        s = _make_v1_scenario()
        s.s_corp_return = None
        out = self.orch.compute_corporate(s)
        self.assertEqual(out, {})

    def test_returns_f1120s_compute_output_when_s_corp_return_set(self):
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out = self.orch.compute_corporate(s)
        self.assertEqual(out["f1120s_ordinary_business_income"], 70000.0)
        self.assertIn("f1120s_sch_k1_allocations", out)
        self.assertEqual(len(out["f1120s_sch_k1_allocations"]), 1)
