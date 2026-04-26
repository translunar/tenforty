"""Unit tests for ReturnOrchestrator.compute_corporate."""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import (
    Address,
    K1AllocationEntity,
    K1AllocationShareholder,
)
from tenforty.orchestrator import ReturnOrchestrator, _flatten_k1_party

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


class EmitCorporatePdfsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_emit_pdfs_produces_1120s_and_k1_when_s_corp_return_set(self):
        s = _make_v1_scenario()
        corp_results = self.orch.compute_corporate(s)
        out_dir = Path(self._tmp.name) / "out"
        paths = self.orch.emit_pdfs(
            scenario=s, results={**corp_results},
            output_dir=out_dir,
        )
        # Expect f1120s.pdf for the entity and f1120s_k1_<n>.pdf per
        # shareholder (1 shareholder in the v1-profile scenario).
        self.assertIn("1120s", paths)
        self.assertTrue(paths["1120s"].exists())
        self.assertIn("1120s_k1_1", paths)
        self.assertTrue(paths["1120s_k1_1"].exists())

    def test_emit_pdfs_skips_1120s_when_no_s_corp_return(self):
        s = _make_v1_scenario()
        s.s_corp_return = None
        out_dir = Path(self._tmp.name) / "out"
        paths = self.orch.emit_pdfs(scenario=s, results={}, output_dir=out_dir)
        self.assertNotIn("1120s", paths)


class FlattenK1PartyTests(unittest.TestCase):
    def test_entity_party_assembles_name_and_address_block(self):
        entity = K1AllocationEntity(
            name="Example S-Corp Inc.",
            ein="00-0000000",
            address=Address(
                street="1 Example Ave",
                city="Example City",
                state="EX",
                zip_code="00000",
            ),
        )
        flat = _flatten_k1_party("entity", entity)
        self.assertEqual(flat["entity_ein"], "00-0000000")
        self.assertEqual(
            flat["entity_name_and_address"],
            "Example S-Corp Inc.\n1 Example Ave\nExample City, EX 00000",
        )
        # The PDF cell is a single combined block; no separate sub-fields
        # for name/street/city/state/zip exist in the K-1 form.
        self.assertNotIn("entity_name", flat)
        self.assertNotIn("entity_address_street", flat)
        self.assertNotIn("entity_address_zip", flat)
        # Entity has no SSN field.
        self.assertNotIn("entity_ssn_or_ein", flat)

    def test_shareholder_party_uses_shareholder_prefix(self):
        shareholder = K1AllocationShareholder(
            name="Taxpayer A",
            ssn_or_ein="000-00-0000",
            address=Address(
                street="1 Example Ave",
                city="Example City",
                state="EX",
                zip_code="00000",
            ),
        )
        flat = _flatten_k1_party("shareholder", shareholder)
        self.assertEqual(flat["shareholder_ssn_or_ein"], "000-00-0000")
        self.assertEqual(
            flat["shareholder_name_and_address"],
            "Taxpayer A\n1 Example Ave\nExample City, EX 00000",
        )
        # Shareholder has no EIN field.
        self.assertNotIn("shareholder_ein", flat)
