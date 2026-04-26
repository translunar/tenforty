"""Unit tests for ReturnOrchestrator.compute_corporate."""

import dataclasses
import datetime
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.models import (
    AccountingMethod,
    Address,
    EntityType,
    FilingStatus,
    K1AllocationEntity,
    K1AllocationShareholder,
    Scenario,
    SCorpDeductions,
    SCorpIncome,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpShareholder,
    ScheduleK1,
    TaxReturnConfig,
)
from tenforty.oracle.flattener import flatten_scenario
from tenforty.orchestrator import (
    ReturnOrchestrator,
    _flatten_k1_party,
    _make_k1_from_1120s_allocation,
)

from tests._scorp_fixtures import _make_v1_scenario, _scorp_attestation_defaults
from tests.helpers import scope_out_attestation_defaults


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
    """Tests emit-time PDF rendering in isolation from the compute pipeline;
    injects custom `results` dicts to drive PDF formatting without re-running
    the corporate waterfall. Calls `_emit_pdfs_internal` directly because the
    public `emit_pdfs` guard rejects S-corp scenarios (forcing
    `run_full_return`), and `run_full_return` would re-run the corp pipeline
    rather than honor the injected results.

    The sibling non-S-corp test (`test_emit_pdfs_skips_1120s_when_no_s_corp_return`)
    stays on the public `emit_pdfs` API since the guard does not fire for
    scenarios with `s_corp_return = None`.
    """

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
        paths = self.orch._emit_pdfs_internal(
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
        # Behavioral non-dedup check: rebuild the same effective_scenario
        # the orchestrator constructs internally, flatten it the way the
        # 1040 workbook sees it, and count distinct K-1 rows in the flat
        # input dict. Each K-1 occupies one of the lettered row slots
        # (k1_a_*, k1_b_*, …), so counting `*_entity_name` keys yields
        # the number of K-1 rows the workbook will actually read.
        extra_k1s = [
            _make_k1_from_1120s_allocation(a)
            for a in out["f1120s_sch_k1_allocations"]
        ]
        effective = dataclasses.replace(
            s, schedule_k1s=list(s.schedule_k1s) + extra_k1s,
        )
        flat = flatten_scenario(effective)
        k1_row_entity_keys = [
            k for k in flat
            if k.startswith("k1_") and k.endswith("_entity_name")
        ]
        self.assertEqual(
            len(k1_row_entity_keys), 2,
            "v1 contract: user K-1 + computed K-1 both flow to 1040 as "
            "two distinct flat-input rows; if dedup is later added, this "
            "test must change explicitly.",
        )


class EmitCorporatePdfsAggregationTests(unittest.TestCase):
    """Tests emit-time PDF rendering in isolation from the compute pipeline;
    injects custom `results` dicts to drive PDF formatting without re-running
    the corporate waterfall. Calls `_emit_pdfs_internal` directly because the
    public `emit_pdfs` guard rejects S-corp scenarios (forcing
    `run_full_return`), and `run_full_return` would re-run the corp pipeline
    rather than honor the injected results.

    This class specifically tests aggregation+derivation rendering with
    non-zero injected values.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _read_field(self, pdf_path: Path, full_field_key: str) -> str | None:
        """Read back a single PDF field value by its full dotted-path key.

        pypdf's get_form_text_fields() returns short leaf names; get_fields()
        returns the full hierarchical path and preserves the /V (value) entry.
        """
        reader = PdfReader(str(pdf_path))
        all_fields = reader.get_fields() or {}
        field = all_fields.get(full_field_key)
        if field is None:
            return None
        return field.get("/V")

    def _emit(self, extra_results: dict) -> Path:
        """Render 1120-S PDF with the given extra_results injected and return
        the output path."""
        s = _make_v1_scenario()
        out_dir = Path(self._tmp.name) / "out"
        # Provide a minimal results dict that satisfies _emit_pdfs_internal (K-1
        # allocations key must exist; its value can be empty for this test).
        results = {"f1120s_sch_k1_allocations": [], **extra_results}
        paths = self.orch._emit_pdfs_internal(scenario=s, results=results, output_dir=out_dir)
        return paths["1120s"]

    def test_aggregation_line_24a_sums_estimated_payments_and_prior_year(self):
        """Line 24a renders as the sum of estimated tax payments + prior-year
        overpayment credited (100 + 200 = 300)."""
        pdf = self._emit({
            "f1120s_estimated_tax_payments": 100,
            "f1120s_prior_year_overpayment_credited": 200,
        })
        self.assertEqual(
            self._read_field(pdf, "topmostSubform[0].Page1[0].f1_44[0]"),
            "300",
        )

    def test_aggregation_line_23c_sums_total_tax_and_453_interest(self):
        """Line 23c renders as total_tax + interest_on_453_deferred (300 + 400 = 700)."""
        pdf = self._emit({
            "f1120s_total_tax": 300,
            "f1120s_interest_on_453_deferred": 400,
        })
        self.assertEqual(
            self._read_field(pdf, "topmostSubform[0].Page1[0].f1_43[0]"),
            "700",
        )

    def test_derivation_line_28b_renders_overpayment_minus_credited(self):
        """Line 28b renders as overpayment − credited_to_next_year (500 − 200 = 300)."""
        pdf = self._emit({
            "f1120s_overpayment": 500,
            "f1120s_credited_to_next_year": 200,
        })
        self.assertEqual(
            self._read_field(pdf, "topmostSubform[0].Page1[0].f1_53[0]"),
            "300",
        )

    def test_all_three_cells_with_distinct_nonzero_values(self):
        """All three previously-blank cells render correct values in a single pass."""
        pdf = self._emit({
            "f1120s_estimated_tax_payments": 100,
            "f1120s_prior_year_overpayment_credited": 200,
            "f1120s_total_tax": 300,
            "f1120s_interest_on_453_deferred": 400,
            "f1120s_overpayment": 500,
            "f1120s_credited_to_next_year": 200,
        })
        self.assertEqual(self._read_field(pdf, "topmostSubform[0].Page1[0].f1_44[0]"), "300")
        self.assertEqual(self._read_field(pdf, "topmostSubform[0].Page1[0].f1_43[0]"), "700")
        self.assertEqual(self._read_field(pdf, "topmostSubform[0].Page1[0].f1_53[0]"), "300")


class K1AddressBlockFormatTests(unittest.TestCase):
    """Tests emit-time PDF rendering in isolation from the compute pipeline;
    injects custom `results` dicts to drive PDF formatting without re-running
    the corporate waterfall. Calls `_emit_pdfs_internal` directly because the
    public `emit_pdfs` guard rejects S-corp scenarios (forcing
    `run_full_return`), and `run_full_return` would re-run the corp pipeline
    rather than honor the injected results.

    This class specifically tests the K-1 entity name+address combined-cell
    rendering.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_entity_name_and_address_field_format_in_k1_pdf(self):
        """The entity name+address block in Part I field B of the K-1 PDF is
        formatted as 'name\\nstreet\\ncity, state zip'."""
        entity_address = Address(
            street="123 Test Lane",
            city="Sample City",
            state="CA",
            zip_code="94000",
        )
        shareholder_address = Address(
            street="456 Shareholder Rd",
            city="Investor Town",
            state="NY",
            zip_code="10001",
        )
        attestations = {**scope_out_attestation_defaults(), **_scorp_attestation_defaults()}
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status=FilingStatus.SINGLE,
                birthdate="01-01-1980", state="EX",
                first_name="Taxpayer", last_name="A", ssn="000-00-0000",
                **attestations,
            ),
            s_corp_return=SCorpReturn(
                name="Example S-Corp Inc.",
                ein="00-0000000",
                address=entity_address,
                date_incorporated=datetime.date(2020, 1, 1),
                s_election_effective_date=datetime.date(2020, 1, 1),
                total_assets=50000.0,
                income=SCorpIncome(
                    gross_receipts=100000.0,
                    returns_and_allowances=0.0,
                    cogs_aggregate=0.0,
                    net_gain_loss_4797=0.0,
                    other_income=0.0,
                ),
                deductions=SCorpDeductions(
                    compensation_of_officers=30000.0,
                    salaries_wages=0.0,
                    repairs_maintenance=0.0,
                    bad_debts=0.0,
                    rents=0.0,
                    taxes_licenses=0.0,
                    interest=0.0,
                    depreciation=0.0,
                    depletion=0.0,
                    advertising=0.0,
                    pension_profit_sharing_plans=0.0,
                    employee_benefits=0.0,
                    other_deductions=0.0,
                ),
                schedule_b_answers=SCorpScheduleBAnswers(
                    accounting_method=AccountingMethod.CASH,
                    business_activity_code="541990",
                    business_activity_description="Services",
                    product_or_service="Consulting",
                    any_c_corp_subsidiaries=False,
                    has_any_foreign_shareholders=False,
                    owns_foreign_entity=False,
                ),
                shareholders=[
                    SCorpShareholder(
                        name="Taxpayer A",
                        ssn_or_ein="000-00-0000",
                        address=shareholder_address,
                        ownership_percentage=100.0,
                    ),
                ],
            ),
        )
        corp_results = self.orch.compute_corporate(scenario)
        out_dir = Path(self._tmp.name) / "out"
        paths = self.orch._emit_pdfs_internal(
            scenario=scenario,
            results={**corp_results},
            output_dir=out_dir,
        )
        self.assertIn("1120s_k1_1", paths)
        reader = PdfReader(str(paths["1120s_k1_1"]))
        all_fields = reader.get_fields() or {}
        field = all_fields.get("topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]")
        self.assertIsNotNone(field, "K-1 entity name+address field not found in PDF")
        self.assertEqual(
            field.get("/V"),
            "Example S-Corp Inc.\n123 Test Lane\nSample City, CA 94000",
        )


class EmitPdfsGuardTests(unittest.TestCase):
    """The public emit_pdfs API rejects S-corp scenarios so callers cannot
    silently produce a Sch E PDF that excludes the synthesized 1120-S K-1.
    Such callers must use run_full_return, which builds the effective
    scenario internally and feeds it to the unguarded internal emit path.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_emit_pdfs_raises_when_called_with_s_corp_scenario(self):
        s = _make_v1_scenario()
        out_dir = Path(self._tmp.name) / "out"
        with self.assertRaises(ValueError) as ctx:
            self.orch.emit_pdfs(scenario=s, results={}, output_dir=out_dir)
        # The message must guide the caller to the canonical entry point —
        # silent failure is exactly the regression class the guard prevents.
        msg = str(ctx.exception)
        self.assertIn("run_full_return", msg)
        self.assertIn("s_corp_return", msg)

    def test_emit_pdfs_works_normally_for_non_s_corp_scenario(self):
        """The guard fires only when scenario.s_corp_return is not None;
        the dominant non-S-corp path is unaffected.
        """
        s = _make_v1_scenario()
        s.s_corp_return = None
        out_dir = Path(self._tmp.name) / "out"
        paths = self.orch.emit_pdfs(scenario=s, results={}, output_dir=out_dir)
        # 1040 + 4868 are emitted unconditionally for any non-S-corp scenario.
        self.assertIn("1040", paths)
        self.assertIn("4868", paths)
        # And no 1120-S branch fires.
        self.assertNotIn("1120s", paths)


class BuildEffectiveScenarioTests(unittest.TestCase):
    """The _build_effective_scenario helper is the single source of truth
    for what the 1040 pipeline runs against. Both compute_federal and
    run_full_return depend on it producing identical effective scenarios
    for the same input — that contract is what prevents Sch E divergence
    between the numerical and PDF paths.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_unchanged_scenario_and_empty_corp_results_for_no_s_corp(self):
        s = _make_v1_scenario()
        s.s_corp_return = None
        effective, corp_results = self.orch._build_effective_scenario(s)
        self.assertEqual(corp_results, {})
        self.assertEqual(len(effective.schedule_k1s), len(s.schedule_k1s))

    def test_appends_synthesized_k1_for_s_corp_scenario(self):
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        original_k1_count = len(s.schedule_k1s)
        effective, corp_results = self.orch._build_effective_scenario(s)
        self.assertIn("f1120s_sch_k1_allocations", corp_results)
        self.assertEqual(len(corp_results["f1120s_sch_k1_allocations"]), 1)
        self.assertEqual(
            len(effective.schedule_k1s), original_k1_count + 1,
        )
        self.assertEqual(
            effective.schedule_k1s[-1].entity_name,
            "Example S-Corp Inc.",
        )
        # Caller's input was not mutated.
        self.assertEqual(len(s.schedule_k1s), original_k1_count)


class RunFullReturnTests(unittest.TestCase):
    """run_full_return is the canonical entry point: callers get both
    numerical results and emitted PDF paths, with the synthesized
    1120-S K-1 visible in the Sch E PDF — the M-2 contract.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_results_and_emitted_paths_tuple(self):
        s = _make_v1_scenario()
        out_dir = Path(self._tmp.name) / "out"
        results, emitted = self.orch.run_full_return(s, out_dir)
        self.assertIn("agi", results)
        self.assertIn("f1120s_ordinary_business_income", results)
        self.assertIn("1040", emitted)
        self.assertIn("4868", emitted)
        self.assertIn("1120s", emitted)
        self.assertIn("1120s_k1_1", emitted)
        for path in emitted.values():
            self.assertTrue(path.exists())

    def test_sch_e_pdf_includes_synthesized_1120s_k1(self):
        """M-2 contract: when the corp pipeline produces a K-1, the Sch E
        Part II PDF rendered by emit_pdfs must reflect that K-1 as a row.

        Failure mode this test guards: emit_pdfs sees the original
        scenario (no synthesized K-1), so Sch E renders blank or with
        only user-supplied K-1s — silently incomplete.
        """
        # This assertion catches the bug where _emit_pdfs_internal runs against
        # the original scenario (no synthesized K-1), so the S-corp's name
        # was missing from Sch E PDF. Post-fix, run_full_return passes
        # effective_scenario through to _emit_pdfs_internal, so the K-1
        # appears in the Part II row block.
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out_dir = Path(self._tmp.name) / "out"
        results, emitted = self.orch.run_full_return(s, out_dir)
        self.assertIn("sch_e", emitted)
        reader = PdfReader(str(emitted["sch_e"]))
        all_field_values = "\n".join(
            (f.get("/V") or "")
            for page in reader.pages
            for f in (page.get("/Annots") or [])
        )
        self.assertIn("Example S-Corp Inc.", all_field_values)

    def test_run_full_return_does_not_mutate_caller_scenario(self):
        s = _make_v1_scenario()
        original_k1_count = len(s.schedule_k1s)
        original_s_corp_return_repr = repr(s.s_corp_return)
        out_dir = Path(self._tmp.name) / "out"
        self.orch.run_full_return(s, out_dir)
        self.assertEqual(len(s.schedule_k1s), original_k1_count)
        self.assertEqual(repr(s.s_corp_return), original_s_corp_return_repr)
        self.orch.run_full_return(s, out_dir)
        self.assertEqual(len(s.schedule_k1s), original_k1_count)

    def test_run_full_return_works_for_non_s_corp_scenario(self):
        """Non-S-corp scenarios route through run_full_return cleanly."""
        s = _make_v1_scenario()
        s.s_corp_return = None
        out_dir = Path(self._tmp.name) / "out"
        results, emitted = self.orch.run_full_return(s, out_dir)
        f1120s_keys = [k for k in results if k.startswith("f1120s_")]
        self.assertEqual(f1120s_keys, [])
        self.assertNotIn("1120s", emitted)
        self.assertIn("1040", emitted)
        self.assertIn("4868", emitted)
