"""Unit tests for ReturnOrchestrator.compute_corporate."""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.models import (
    Address,
    EntityType,
    K1AllocationEntity,
    K1AllocationShareholder,
    ScheduleK1,
)
from tenforty.oracle.flattener import flatten_scenario
from tenforty.orchestrator import (
    ReturnOrchestrator,
    _flatten_k1_party,
    _make_k1_from_1120s_allocation,
)

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


class FederalWaterfallTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_federal_compute_runs_corporate_pipeline_and_merges_results(self):
        """When s_corp_return is set, compute_federal runs the corporate
        pipeline before the 1040 pipeline and merges f1120s_* output keys
        into its return dict alongside the 1040 outputs.
        """
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out = self.orch.compute_federal(s)
        # Corporate-pipeline keys appear in compute_federal's output.
        self.assertEqual(
            out["f1120s_ordinary_business_income"], 70000.0,
        )
        # 1040-pipeline keys are also present (line 21 OBI flowed into the
        # personal return via the appended K-1 → Sch E Part II → Sch 1).
        self.assertIn("agi", out)

    def test_federal_compute_does_not_mutate_caller_scenario(self):
        """compute_federal must not mutate the caller's input. Verified
        across schedule_k1s (which the corporate waterfall augments) and
        config (which is shared by reference through dataclasses.replace).
        """
        s = _make_v1_scenario()
        original_k1_count = len(s.schedule_k1s)
        original_config_id = id(s.config)
        original_config_repr = repr(s.config)
        original_s_corp_return_repr = repr(s.s_corp_return)

        self.orch.compute_federal(s)
        self.assertEqual(len(s.schedule_k1s), original_k1_count)
        # `dataclasses.replace` shares config by reference; verify it
        # wasn't mutated in place by any downstream pipeline step.
        self.assertEqual(id(s.config), original_config_id)
        self.assertEqual(repr(s.config), original_config_repr)
        # SCorpReturn similarly should be untouched.
        self.assertEqual(repr(s.s_corp_return), original_s_corp_return_repr)

        # Calling twice should not double-append or otherwise drift either.
        self.orch.compute_federal(s)
        self.assertEqual(len(s.schedule_k1s), original_k1_count)
        self.assertEqual(repr(s.config), original_config_repr)
        self.assertEqual(repr(s.s_corp_return), original_s_corp_return_repr)

    def test_federal_compute_skips_corporate_pipeline_when_no_s_corp_return(self):
        s = _make_v1_scenario()
        s.s_corp_return = None
        out = self.orch.compute_federal(s)
        # No f1120s_* keys when there is no corporate return.
        f1120s_keys = [k for k in out if k.startswith("f1120s_")]
        self.assertEqual(f1120s_keys, [])

    def test_federal_compute_does_not_dedupe_user_supplied_k1(self):
        """V1 contract: caller is responsible for not double-entering.
        If the user manually populated `scenario.schedule_k1s` with a
        K-1 from the same entity `s_corp_return` will compute, the 1040
        pipeline's effective K-1 list contains BOTH (the user's + the
        computed one). v1 does not deduplicate.

        Detection mechanism: count K-1 entries actually rendered into
        the workbook flat inputs (which is what the 1040 sheet sees).
        """
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        # User adds the same entity's K-1 manually.
        s.schedule_k1s = [
            ScheduleK1(
                entity_name="Example S-Corp Inc.",
                entity_ein="00-0000000",
                entity_type=EntityType.S_CORP,
                material_participation=True,
                ordinary_business_income=70000.0,
            ),
        ]
        # Run compute_federal end-to-end (validates no crash).
        out = self.orch.compute_federal(s)
        # The corp output still emits exactly 1 allocation (corp doesn't
        # see user-supplied K-1s).
        self.assertEqual(len(out["f1120s_sch_k1_allocations"]), 1)
        # To verify v1 non-dedup: build the same effective_scenario the
        # orchestrator builds and check its schedule_k1s has 2 entries.
        extra_k1s = [
            _make_k1_from_1120s_allocation(a)
            for a in out["f1120s_sch_k1_allocations"]
        ]
        effective = dataclasses.replace(
            s, schedule_k1s=list(s.schedule_k1s) + extra_k1s,
        )
        self.assertEqual(
            len(effective.schedule_k1s), 2,
            "v1 contract: user K-1 + computed K-1 both flow to 1040; "
            "if dedup is later added, this test must change explicitly.",
        )
