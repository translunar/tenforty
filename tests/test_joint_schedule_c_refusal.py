"""A joint return with Schedule C refuses: Schedule SE is per person.

Schedule SE coordinates each person's self-employment earnings with THAT
person's own Social Security wages (line 8a) against the wage base. tenforty
computes one Schedule SE and a Schedule C business has no owner, so on a
married-filing-jointly return a spouse's W-2 wages would consume the wage
base and silently understate the SE tax (and the half-SE deduction and QBI
that follow). The fix is fail-closed: refuse, before any Schedule C/SE math,
on both the compute and the emit path. Single and head-of-household returns
stay computable, and their line 8a is the filer's own Social Security wages.

Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import sch_se as form_sch_se
from tenforty.models import FilingStatus, ScheduleCBusiness, Scenario, W2
from tenforty.orchestrator import ReturnOrchestrator, refuse_joint_schedule_c
from tests.helpers import REPO_ROOT, hoh_facts, make_simple_scenario

_BIZ = ScheduleCBusiness(description="consult", gross_receipts=50_000.0)


def _w2(employer, ss_wages, owner=None):
    return W2(employer=employer, wages=ss_wages, federal_tax_withheld=1_000.0,
              ss_wages=ss_wages, ss_tax_withheld=round(ss_wages * 0.062, 2),
              medicare_wages=ss_wages,
              medicare_tax_withheld=round(ss_wages * 0.0145, 2), owner=owner)


def _scenario(status, w2s, businesses=(_BIZ,), year=2024,
              head_of_household=None):
    base = make_simple_scenario()
    extra = {}
    if status is FilingStatus.MARRIED_FILING_JOINTLY:
        extra = dict(spouse_first_name="Spouse", spouse_last_name="Example",
                     spouse_ssn="000-00-0002", spouse_birthdate="1990-03-07")
    config = dataclasses.replace(base.config, year=year, filing_status=status,
                                 head_of_household=head_of_household, **extra)
    return Scenario(config=config, w2s=list(w2s),
                    schedule_c_businesses=list(businesses))


def _joint():
    # The reproduced shape: the taxpayer's Schedule C, the spouse's W-2 at
    # the 2024 wage base.
    return _scenario(FilingStatus.MARRIED_FILING_JOINTLY, [
        _w2("Taxpayer Co", 20_000.0, "taxpayer"),
        _w2("Spouse Co", 168_600.0, "spouse")])


class JointScheduleCRefusalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _assert_names_both_causes(self, message):
        self.assertIn("married_filing_jointly", message)
        self.assertIn("Schedule SE is figured per person", message)
        self.assertIn("no owner field", message)
        self.assertIn("owner attribution", message)

    def test_pure_refusal_fires_only_for_joint_with_schedule_c(self):
        with self.assertRaises(NotImplementedError) as ctx:
            refuse_joint_schedule_c(_joint())
        self._assert_names_both_causes(str(ctx.exception))
        # Controls: a joint return without Schedule C, and every other status
        # with Schedule C, are not this refusal's business.
        refuse_joint_schedule_c(_scenario(
            FilingStatus.MARRIED_FILING_JOINTLY,
            [_w2("Taxpayer Co", 20_000.0, "taxpayer")], businesses=()))
        for status in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD,
                       FilingStatus.MARRIED_FILING_SEPARATELY):
            with self.subTest(status=status.value):
                refuse_joint_schedule_c(_scenario(
                    status, [_w2("Filer Co", 20_000.0)]))

    def test_compute_refuses_joint_schedule_c(self):
        scn = _joint()
        eff, _ = self.orch._build_effective_scenario(scn)
        self.assertTrue(self.orch._scenario_in_spine_scope(eff))  # native path
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scn)
        self._assert_names_both_causes(str(ctx.exception))

    def test_emit_refuses_joint_schedule_c_and_writes_nothing(self):
        out = self.tmp / "emit"
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.emit_pdfs(_joint(), {}, out)
        self._assert_names_both_causes(str(ctx.exception))
        self.assertEqual(list(out.glob("*.pdf")), [])

    def test_refuses_before_any_schedule_c_or_se_math(self):
        # The shared Schedule C/SE wiring refuses at its first line: neither
        # schedule computes on a joint return. (The joint refusal itself, not
        # the Schedule SE backstop below.)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch._compute_sch_c_and_se(_joint())
        self._assert_names_both_causes(str(ctx.exception))

    def test_schedule_se_never_reads_a_spouse_w2(self):
        # Backstop at the bug site: line 8a never silently sums a spouse's
        # W-2, whatever reaches Schedule SE.
        scn = _joint()
        with self.assertRaises(NotImplementedError) as ctx:
            form_sch_se.compute(scn, upstream={"sch_c": {
                "sch_c_line_31_net_profit_total": 50_000}})
        self.assertIn("spouse", str(ctx.exception))


class NonJointScheduleCComputesTests(unittest.TestCase):
    """Single and head of household with Schedule C still compute, and
    Schedule SE line 8a is the filer's own Social Security wages: the sum of
    the filer's W-2s, nothing else."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name) / "work")

    def test_line_8a_is_the_filers_own_ss_wages(self):
        for status in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD):
            with self.subTest(status=status.value):
                block = (hoh_facts(2024)
                         if status is FilingStatus.HEAD_OF_HOUSEHOLD else None)
                scn = _scenario(status, [_w2("First Co", 60_000.0),
                                         _w2("Second Co", 40_000.0, "taxpayer")],
                                head_of_household=block)
                eff, _ = self.orch._build_effective_scenario(scn)
                self.assertTrue(self.orch._scenario_in_spine_scope(eff))
                _, se = self.orch._compute_sch_c_and_se(eff)
                self.assertEqual(se["sch_se_line_8a_ss_wages_and_tips"], 100_000)
                self.assertEqual(se["sch_se_line_8d_wages_subject_to_ss"], 100_000)
                out = self.orch.compute_federal(scn)
                self.assertEqual(out["sch_1_line_3_business_income"], 50_000)


if __name__ == "__main__":
    unittest.main()
