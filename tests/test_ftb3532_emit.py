# tests/test_ftb3532_emit.py
"""FTB 3532 emit: presentation keys, the CA emit gate, packet membership and
the amendment manifest.

California denies head-of-household status to a return that does not attach
a completed FTB 3532, so every HoH CA packet must carry it, and no other
packet may. The gate refuses (before any file is written) a HoH return with
no ``head_of_household`` block, a non-HoH return carrying one, and a 3532
payload missing any field the scenario's branch of the form requires.

Native throughout: every scenario is asserted in native-spine scope and the
workbook path is patched to fail, so no test can reach LibreOffice. Wages come
from the spine battery's HoH wages-only row and are asserted ABOVE the
one-child EIC ceiling read from params. All identities are synthetic.
"""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import pdf_packet
from tenforty.forms import ftb3532 as form_ftb3532
from tenforty.forms import f1040x as form_f1040x
from tenforty.mappings.pdf_ftb3532 import PdfFtb3532
from tenforty.models import (
    AmendmentCase,
    CA540Return,
    FilingStatus,
    Form1099INT,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    LivedTogetherPeriod,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params
from tests.fixtures.spine_battery import build_wages_only
from tests.helpers import CA_SCOPE_OUT_FIELDS

REPO_ROOT = Path(__file__).parent.parent
YEARS = (2021, 2022, 2023, 2024, 2025)
HOH = FilingStatus.HEAD_OF_HOUSEHOLD

# Every compute key the mapping lane consumes (plan, mapping-lane interface).
ALL_KEYS = frozenset({
    "ftb3532_header_name", "ftb3532_header_ssn", "ftb3532_marital_status",
    "ftb3532_period_1_from", "ftb3532_period_1_to",
    "ftb3532_period_2_from", "ftb3532_period_2_to",
    "ftb3532_relationship", "ftb3532_qp_first_name", "ftb3532_qp_last_name",
    "ftb3532_qp_ssn", "ftb3532_qp_dob", "ftb3532_line_3a", "ftb3532_line_3b",
    "ftb3532_line_4_gross_income", "ftb3532_line_5_days",
})
DEFAULT_KEYS = ALL_KEYS - {
    "ftb3532_period_1_from", "ftb3532_period_1_to",
    "ftb3532_period_2_from", "ftb3532_period_2_to",
    "ftb3532_line_3a", "ftb3532_line_3b",
}


def _qp(year: int, **over) -> HohQualifyingPerson:
    fields = dict(
        first_name="Example", last_name="Child", ssn="000000005",
        birthdate=f"{year - 10}-03-07",
        relationship=HohRelationship.CHILD_OR_STEPCHILD,
        full_time_student=None, permanently_disabled=None,
        gross_income=0.0, days_lived_with_you=365)
    fields.update(over)
    return HohQualifyingPerson(**fields)


def _facts(year: int, **over) -> HeadOfHouseholdFacts:
    fields = dict(marital_status=HohMaritalStatus.UNMARRIED,
                  qualifying_person=_qp(year))
    fields.update(over)
    return HeadOfHouseholdFacts(**fields)


def _ca_scenario(year: int, status: FilingStatus, facts=None, **cfg_over):
    """Battery wages-only row, CA-resident: every CA scope-out True,
    full-year coverage stated, line 112 stated as 0."""
    base = build_wages_only(year, status)
    cfg = dataclasses.replace(
        base.config, full_year_health_care_coverage=True,
        head_of_household=facts,
        **{k: True for k in CA_SCOPE_OUT_FIELDS}, **cfg_over)
    return dataclasses.replace(
        base, config=cfg, ca540=CA540Return(interest_and_penalties=0.0))


def _hoh_scenario(year: int, **cfg_over):
    return _ca_scenario(year, HOH, _facts(year), **cfg_over)


class _NativeEmitCase(unittest.TestCase):
    """Shared setup: a native-only orchestrator (the workbook path raises)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")
        patcher = unittest.mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=AssertionError("workbook path reached in a native test"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _assert_native(self, scenario):
        year = scenario.config.year
        ceilings = load_federal_params(year).eic_income_ceiling
        wages = sum(w.wages for w in scenario.w2s)
        self.assertGreater(wages, ceilings[1])
        self.assertTrue(self.orch._scenario_in_spine_scope(scenario))

    def _emit(self, scenario, out: Path):
        self._assert_native(scenario)
        ca_yaml = self.tmp / f"ca_{scenario.config.year}.yaml"
        ca_yaml.write_text(yaml.safe_dump(
            {"ca540": {"interest_and_penalties": 0.0}}))
        return self.orch.run_full_california_return(
            scenario=dataclasses.replace(scenario, ca540=None),
            ca_yaml_path=ca_yaml, output_dir=out)


class Ftb3532PresentationKeysTests(unittest.TestCase):

    def test_valid_default_keys(self):
        for year in YEARS:
            with self.subTest(year=year):
                cfg = _hoh_scenario(year).config
                keys = form_ftb3532.presentation_keys(cfg)
                self.assertEqual(set(keys), set(DEFAULT_KEYS))
                self.assertEqual(keys["ftb3532_header_name"], cfg.full_name)
                self.assertEqual(keys["ftb3532_header_ssn"], "000000000")
                self.assertEqual(keys["ftb3532_qp_ssn"], "000000005")
                self.assertEqual(keys["ftb3532_qp_dob"], f"03/07/{year - 10}")
                self.assertEqual(keys["ftb3532_marital_status"], "unmarried")
                self.assertEqual(keys["ftb3532_relationship"],
                                 "child_or_stepchild")
                self.assertEqual(keys["ftb3532_qp_first_name"], "Example")
                self.assertEqual(keys["ftb3532_qp_last_name"], "Child")
                self.assertEqual(keys["ftb3532_line_4_gross_income"], 0.0)
                self.assertEqual(keys["ftb3532_line_5_days"], 365)

    def test_lived_together_with_two_periods_yields_four_period_keys(self):
        year = 2024
        facts = _facts(
            year,
            marital_status=HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR,
            lived_with_spouse_periods=(
                LivedTogetherPeriod(start=f"{year}-01-01", end=f"{year}-02-15"),
                LivedTogetherPeriod(start=f"{year}-03-01", end=f"{year}-04-30")))
        cfg = dataclasses.replace(_hoh_scenario(year).config,
                                  head_of_household=facts)
        keys = form_ftb3532.presentation_keys(cfg)
        self.assertEqual(keys["ftb3532_marital_status"],
                         "married_lived_together_part_of_year")
        self.assertEqual(
            [keys[k] for k in ("ftb3532_period_1_from", "ftb3532_period_1_to",
                               "ftb3532_period_2_from", "ftb3532_period_2_to")],
            ["01/01/2024", "02/15/2024", "03/01/2024", "04/30/2024"])

    def test_one_period_yields_only_the_first_pair(self):
        year = 2023
        facts = _facts(
            year,
            marital_status=HohMaritalStatus.MARRIED_LIVED_TOGETHER_PART_OF_YEAR,
            lived_with_spouse_periods=(
                LivedTogetherPeriod(start=f"{year}-01-01", end=f"{year}-02-15"),))
        cfg = dataclasses.replace(_hoh_scenario(year).config,
                                  head_of_household=facts)
        keys = form_ftb3532.presentation_keys(cfg)
        self.assertIn("ftb3532_period_1_to", keys)
        self.assertNotIn("ftb3532_period_2_from", keys)
        self.assertNotIn("ftb3532_period_2_to", keys)

    def test_19_or_older_student_answers_3a_and_3b(self):
        for year in YEARS:
            with self.subTest(year=year):
                facts = _facts(year, qualifying_person=_qp(
                    year, birthdate=f"{year - 20}-05-01",
                    full_time_student=True, permanently_disabled=False))
                cfg = dataclasses.replace(_hoh_scenario(year).config,
                                          head_of_household=facts)
                keys = form_ftb3532.presentation_keys(cfg)
                self.assertIs(keys["ftb3532_line_3a"], True)
                self.assertIs(keys["ftb3532_line_3b"], False)

    def test_filer_ssn_that_does_not_normalize_refuses(self):
        cfg = dataclasses.replace(_hoh_scenario(2025).config, ssn="12345")
        with self.assertRaises(ValueError) as cm:
            form_ftb3532.presentation_keys(cfg)
        self.assertIn("FTB 3532", str(cm.exception))

    def test_dashed_ssns_normalize_to_nine_digits(self):
        year = 2021
        facts = _facts(year, qualifying_person=_qp(year, ssn="000-00-0005"))
        cfg = dataclasses.replace(_hoh_scenario(year).config,
                                  ssn="000-00-0001", head_of_household=facts)
        keys = form_ftb3532.presentation_keys(cfg)
        self.assertEqual(keys["ftb3532_header_ssn"], "000000001")
        self.assertEqual(keys["ftb3532_qp_ssn"], "000000005")

    def test_is_required_iff_head_of_household(self):
        single = _ca_scenario(2025, FilingStatus.SINGLE).config
        for status in (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY,
                       FilingStatus.MARRIED_FILING_SEPARATELY, HOH):
            with self.subTest(status=status):
                cfg = dataclasses.replace(single, filing_status=status.value)
                self.assertEqual(form_ftb3532.is_required(cfg), status is HOH)

    def test_non_hoh_config_yields_no_keys(self):
        cfg = _ca_scenario(2025, FilingStatus.SINGLE).config
        self.assertEqual(form_ftb3532.presentation_keys(cfg), {})


class Ftb3532EmitTests(_NativeEmitCase):

    def test_hoh_emit_writes_the_3532_last_in_the_ca_packet(self):
        for year in YEARS:
            with self.subTest(year=year):
                out = self.tmp / f"hoh_{year}"
                _results, pdfs = self._emit(_hoh_scenario(year), out)
                self.assertIn("ftb3532", pdfs)
                self.assertEqual(pdfs["ftb3532"], out / f"ftb3532_{year}.pdf")
                self.assertTrue(pdfs["ftb3532"].exists())
                combined = pdf_packet.assemble_all(pdfs, out, year)["california"]
                self.assertEqual(combined.name, f"f540_{year}_complete.pdf")
                members = pdf_packet.ordered_members(pdfs, pdf_packet.CALIFORNIA)
                self.assertEqual(members[-1], pdfs["ftb3532"])
                packet = PdfReader(str(combined))
                self.assertEqual(
                    len(packet.pages),
                    sum(len(PdfReader(str(p)).pages) for p in members))
                last = packet.pages[-1].extract_text() or ""
                self.assertIn("Head of Household Filing Status Schedule",
                              " ".join(last.split()))
                # The filled 3532 carries the scenario's identities.
                mapping = PdfFtb3532.get_mapping(year)
                fields = PdfReader(str(pdfs["ftb3532"])).get_fields()
                self.assertEqual(
                    str(fields[mapping["ftb3532_qp_ssn"]].get("/V")), "000000005")
                self.assertEqual(
                    str(fields[mapping["ftb3532_header_name"]].get("/V")),
                    "Example Filer")

    def test_single_and_mfj_emits_carry_no_3532(self):
        for status in (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY):
            for year in (2021, 2025):
                with self.subTest(status=status, year=year):
                    out = self.tmp / f"{status.value}_{year}"
                    _results, pdfs = self._emit(_ca_scenario(year, status), out)
                    self.assertIn("f540", pdfs)
                    self.assertNotIn("ftb3532", pdfs)
                    self.assertFalse((out / f"ftb3532_{year}.pdf").exists())


class Ftb3532GateRefusalTests(_NativeEmitCase):

    def _ca_results(self, scenario):
        fed = self.orch.compute_federal(scenario)
        return self.orch._compute_ca_results(scenario, scenario.ca540, fed)

    def test_refuses_before_any_file_written(self):
        year = 2025
        scenario = _ca_scenario(year, HOH, facts=None)
        out = self.tmp / "refused"
        with self.assertRaises(ValueError) as cm:
            self._emit(scenario, out)
        self.assertIn("FTB 3532", str(cm.exception))
        self.assertEqual(sorted(out.glob("*")) if out.exists() else [], [])

    def test_gate_itself_refuses_a_hoh_scenario_without_the_block(self):
        # The backstop inside _emit_ca_pdfs_internal, reached directly with a
        # complete CA results dict (as an internal caller could).
        year = 2024
        good = _hoh_scenario(year)
        results = self._ca_results(good)
        stripped = dataclasses.replace(
            good, config=dataclasses.replace(good.config,
                                             head_of_household=None))
        out = self.tmp / "gate"
        with self.assertRaises(ValueError) as cm:
            self.orch._emit_ca_pdfs_internal(stripped, results, out)
        self.assertIn("FTB 3532", str(cm.exception))
        self.assertEqual(sorted(out.glob("*")) if out.exists() else [], [])

    def test_single_config_with_a_block_refuses_the_same_way(self):
        year = 2025
        scenario = _ca_scenario(year, FilingStatus.SINGLE, facts=_facts(year))
        out = self.tmp / "stray"
        with self.assertRaises(ValueError) as cm:
            self._emit(scenario, out)
        self.assertIn("head_of_household", str(cm.exception))
        self.assertIn("FTB 3532", str(cm.exception))
        self.assertEqual(sorted(out.glob("*")) if out.exists() else [], [])
        # And the backstop, reached directly.
        single = _ca_scenario(year, FilingStatus.SINGLE)
        results = self._ca_results(single)
        stray = dataclasses.replace(
            single, config=dataclasses.replace(single.config,
                                               head_of_household=_facts(year)))
        out2 = self.tmp / "stray_gate"
        with self.assertRaises(ValueError):
            self.orch._emit_ca_pdfs_internal(stray, results, out2)
        self.assertEqual(sorted(out2.glob("*")) if out2.exists() else [], [])


class Ftb3532PostConditionTests(_NativeEmitCase):
    """The emit asserts the 3532 is present iff HoH in code, not only in
    tests: an emit table that lost its ftb3532 row cannot ship a HoH packet
    without the form."""

    def test_hoh_emit_without_the_table_row_refuses(self):
        from tenforty import orchestrator as orch_mod
        table = tuple(row for row in orch_mod._CA_FORMS_BY_BASENAME
                      if row[0] != "ftb3532")
        out = self.tmp / "postcondition"
        with unittest.mock.patch.object(
                orch_mod, "_CA_FORMS_BY_BASENAME", table):
            with self.assertRaises(AssertionError) as cm:
                self._emit(_hoh_scenario(2025), out)
        self.assertIn("FTB 3532", str(cm.exception))


class Ftb3532PayloadCompletenessTests(_NativeEmitCase):

    def test_missing_qp_ssn_refuses_naming_the_field(self):
        for year in YEARS:
            with self.subTest(year=year):
                real = form_ftb3532.presentation_keys

                def dropped(config):
                    keys = dict(real(config))
                    del keys["ftb3532_qp_ssn"]
                    return keys

                out = self.tmp / f"incomplete_{year}"
                with unittest.mock.patch.object(
                        form_ftb3532, "presentation_keys", side_effect=dropped):
                    with self.assertRaises(ValueError) as cm:
                        self._emit(_hoh_scenario(year), out)
                msg = str(cm.exception)
                self.assertIn("FTB 3532", msg)
                self.assertIn(PdfFtb3532.get_mapping(year)["ftb3532_qp_ssn"], msg)
                self.assertFalse((out / f"ftb3532_{year}.pdf").exists())
                # Refused before ANY file was written, not just the 3532.
                self.assertEqual(
                    sorted(out.glob("*")) if out.exists() else [], [])

    def test_missing_3b_answer_on_the_19_plus_branch_refuses(self):
        year = 2022
        facts = _facts(year, qualifying_person=_qp(
            year, birthdate=f"{year - 20}-05-01",
            full_time_student=True, permanently_disabled=False))
        real = form_ftb3532.presentation_keys

        def dropped(config):
            keys = dict(real(config))
            del keys["ftb3532_line_3b"]
            return keys

        out = self.tmp / "no3b"
        with unittest.mock.patch.object(
                form_ftb3532, "presentation_keys", side_effect=dropped):
            with self.assertRaises(ValueError) as cm:
                self._emit(_ca_scenario(year, HOH, facts), out)
        self.assertIn("1023 RB", str(cm.exception))
        self.assertFalse((out / f"ftb3532_{year}.pdf").exists())


class Ftb3532MaxLenFitTests(_NativeEmitCase):
    """Review Focus 2: dashed SSNs print as 9 digits and every emitted text
    value fits its widget's MaxLen, including the MaxLen-9 years."""

    def test_every_text_value_fits_and_ssns_are_nine_digits(self):
        for year in YEARS:
            with self.subTest(year=year):
                facts = _facts(year, qualifying_person=_qp(year, ssn="000-00-0005"))
                scenario = _ca_scenario(year, HOH, facts, ssn="000-00-0001")
                out = self.tmp / f"maxlen_{year}"
                _results, pdfs = self._emit(scenario, out)
                mapping = PdfFtb3532.get_mapping(year)
                fields = PdfReader(str(pdfs["ftb3532"])).get_fields()
                self.assertEqual(
                    str(fields[mapping["ftb3532_header_ssn"]].get("/V")),
                    "000000001")
                self.assertEqual(
                    str(fields[mapping["ftb3532_qp_ssn"]].get("/V")), "000000005")
                filled = 0
                for key, path in mapping.items():
                    value = fields[path].get("/V")
                    if value is None or str(value) == "":
                        continue
                    filled += 1
                    max_len = fields[path].get("/MaxLen")
                    if max_len is not None:
                        self.assertLessEqual(len(str(value)), int(max_len),
                                             (key, str(value)))
                self.assertGreaterEqual(filled, 8)


class Ftb3532AmendmentManifestTests(_NativeEmitCase):

    def test_amended_hoh_ca_packet_lists_the_3532(self):
        year = 2024
        base = _hoh_scenario(year)
        original = dataclasses.replace(base, form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=2_000.0)])
        amended = dataclasses.replace(original, form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=3_000.0)])
        self._assert_native(original)
        orig_fed = self.orch.compute_federal(original)
        filed_path = self.tmp / "federal_filed.yaml"
        filed_path.write_text(yaml.safe_dump(
            {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
        orig_ca = self.orch._compute_ca_results(
            original, original.ca540, orig_fed)
        ca_filed_path = self.tmp / "ca_filed.yaml"
        ca_filed_path.write_text(yaml.safe_dump(
            {"f540_total_liability": orig_ca["f540_total_liability"]}))
        case = AmendmentCase(
            year=year, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            original_tax_paid=0.0,
            ca_original_refund_received=max(
                0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0)
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)
        name = f"ftb3532_{year}.pdf"
        self.assertTrue((out / name).exists())
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertIn(name, by_name)
        self.assertEqual(by_name[name].reason, "complete amended return")
        self.assertIn(name, (out / "packet_manifest.txt").read_text())

    def test_amended_single_ca_packet_lists_no_3532(self):
        year = 2024
        base = _ca_scenario(year, FilingStatus.SINGLE)
        original = dataclasses.replace(base, form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=2_000.0)])
        amended = dataclasses.replace(original, form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=3_000.0)])
        orig_fed = self.orch.compute_federal(original)
        filed_path = self.tmp / "federal_filed.yaml"
        filed_path.write_text(yaml.safe_dump(
            {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
        orig_ca = self.orch._compute_ca_results(
            original, original.ca540, orig_fed)
        ca_filed_path = self.tmp / "ca_filed.yaml"
        ca_filed_path.write_text(yaml.safe_dump(
            {"f540_total_liability": orig_ca["f540_total_liability"]}))
        case = AmendmentCase(
            year=year, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            original_tax_paid=0.0,
            ca_original_refund_received=max(
                0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0)
        out = self.tmp / "packet_single"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)
        self.assertTrue((out / f"f540_amended_{year}.pdf").exists())
        names = {mf.filename for mf in manifest.mailed_files}
        self.assertNotIn(f"ftb3532_{year}.pdf", names)


class Ftb3532PacketPartitionTests(unittest.TestCase):

    def test_ftb3532_is_claimed_by_the_california_packet(self):
        self.assertEqual(pdf_packet.classify_key("ftb3532"), "california")

    def test_ftb3532_follows_schedule_d_540(self):
        keys = [m.key for m in pdf_packet.CALIFORNIA.members]
        self.assertEqual(keys[-1], "ftb3532")
        self.assertEqual(keys.index("ftb3532"), keys.index("sch_d_540") + 1)
