"""The claimed-dependents refusal points a head-of-household filer at the
qualifying-person block.

Claimed dependents refuse on every path until 0.2.1 (gap 1). A
head-of-household filer whose qualifying person is ALSO listed in
`dependents` needs to know which fact to correct: the qualifying person
(`head_of_household.qualifying_person`) is separate from `dependents`, so a
child the filer is not claiming -- e.g. one whose exemption was released on
Form 8332 -- comes out of `dependents`, while a real claim must never be
deleted to get past the refusal. When `config.head_of_household` is present
the refusal carries that clause (spec §7; its closing remedy sentence is
dropped, ruling 2026-10-16, because the base message already ends with the
same remedy). The refusal still fires before any FTB 3532 work.

Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml

from tenforty.models import (
    CA540Return,
    FilingStatus,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
)
from tenforty.orchestrator import ReturnOrchestrator, refuse_dependents
from tests.fixtures.spine_battery import _w2, build_wages_only
from tests.helpers import CA_SCOPE_OUT_FIELDS, REPO_ROOT

_YEAR = 2025
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD
_REMEDY = "File this return by hand"
# The clause's substance (spec §7), sentence by sentence.
_CLAUSE_PARTS = (
    "Your head-of-household qualifying person "
    "(`head_of_household.qualifying_person`) is separate from `dependents`",
    "if you are NOT claiming that person as a dependent",
    "a child whose exemption you released to the other parent on Form 8332",
    "remove them from `dependents`; the qualifying person alone completes "
    "FTB 3532",
    "If you ARE claiming them, do not remove them to get past this refusal: "
    "the return would understate your credits.",
)
_CLAUSE_MARKER = "head_of_household.qualifying_person"


def _facts(year: int) -> HeadOfHouseholdFacts:
    return HeadOfHouseholdFacts(
        marital_status=HohMaritalStatus.UNMARRIED,
        qualifying_person=HohQualifyingPerson(
            first_name="Example", last_name="Child", ssn="000000005",
            birthdate=f"{year - 10}-03-07",
            relationship=HohRelationship.CHILD_OR_STEPCHILD,
            full_time_student=None, permanently_disabled=None,
            gross_income=0.0, days_lived_with_you=365))


def _scenario(status: FilingStatus, *, block: bool, wages: float | None = None,
              dependents=("Example Child",), year: int = _YEAR):
    """The battery wages-only row (native wage level), CA-resident, with the
    given dependents; `wages` overrides the W-2 for a workbook-routed
    variant."""
    base = build_wages_only(year, status)
    cfg = dataclasses.replace(
        base.config, dependents=list(dependents),
        head_of_household=_facts(year) if block else None,
        full_year_health_care_coverage=True,
        **{k: True for k in CA_SCOPE_OUT_FIELDS})
    scn = dataclasses.replace(
        base, config=cfg, ca540=CA540Return(interest_and_penalties=0.0))
    if wages is not None:
        scn = dataclasses.replace(scn, w2s=[_w2(
            year, "Synthetic Employer L", wages,
            federal_tax_withheld=float(round(wages / 10)))])
    return scn


def _never_the_workbook(*args, **kwargs):
    raise AssertionError("routed to the workbook path")


class _Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")
        patcher = unittest.mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=_never_the_workbook)
        patcher.start()
        self.addCleanup(patcher.stop)

    def refusal(self, call) -> str:
        with self.assertRaises(NotImplementedError) as ctx:
            call()
        message = str(ctx.exception)
        self.assertTrue(message.startswith("This return lists"), message)
        self.assertEqual(message.count(_REMEDY), 1, message)
        return message

    def assert_clause(self, message: str) -> None:
        for part in _CLAUSE_PARTS:
            self.assertIn(part, message)

    def assert_no_clause(self, message: str) -> None:
        self.assertNotIn(_CLAUSE_MARKER, message)
        self.assertNotIn("Form 8332", message)


class DependentsRefusalHohClauseTests(_Case):
    def test_pure_refusal_carries_the_clause_with_the_block(self):
        self.assert_clause(self.refusal(
            lambda: refuse_dependents(_scenario(_HOH, block=True))))

    def test_pure_refusal_has_no_clause_without_the_block(self):
        # Reachable negative space: the same refusal fires (dependents are
        # present) and only the block's absence keeps the clause out.
        for status, block in ((FilingStatus.SINGLE, False), (_HOH, False)):
            with self.subTest(status=status.value, block=block):
                self.assert_no_clause(self.refusal(
                    lambda: refuse_dependents(_scenario(status, block=block))))

    def test_native_routed_compute_and_emit_carry_the_clause(self):
        scn = _scenario(_HOH, block=True)
        eff, _ = self.orch._build_effective_scenario(scn)
        self.assertTrue(self.orch._scenario_in_spine_scope(eff))
        self.assert_clause(self.refusal(lambda: self.orch.compute_federal(scn)))
        out = self.tmp / "emit"
        self.assert_clause(self.refusal(
            lambda: self.orch.emit_pdfs(scn, {}, out)))
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_workbook_routed_compute_carries_the_clause(self):
        # Low wages: the EIC gate rules the return out of spine scope, yet the
        # path-neutral refusal fires before any routing.
        scn = _scenario(_HOH, block=True, wages=10_000.0)
        eff, _ = self.orch._build_effective_scenario(scn)
        self.assertFalse(self.orch._scenario_in_spine_scope(eff))
        self.assert_clause(self.refusal(lambda: self.orch.compute_federal(scn)))

    def test_single_with_dependents_refuses_without_the_clause(self):
        scn = _scenario(FilingStatus.SINGLE, block=False)
        self.assert_no_clause(self.refusal(
            lambda: self.orch.compute_federal(scn)))


class DependentsRefusalPrecedesFtb3532Tests(_Case):
    def test_full_ca_emit_raises_the_dependents_refusal_first(self):
        scn = _scenario(_HOH, block=True)
        ca_yaml = self.tmp / "ca.yaml"
        ca_yaml.write_text(yaml.safe_dump(
            {"ca540": {"interest_and_penalties": 0.0}}))
        out = self.tmp / "ca"
        message = self.refusal(lambda: self.orch.run_full_california_return(
            scenario=dataclasses.replace(scn, ca540=None),
            ca_yaml_path=ca_yaml, output_dir=out))
        self.assert_clause(message)
        # Not an FTB 3532 emit-gate message, and nothing written.
        self.assertNotIn("FTB 3532 cannot print", message)
        self.assertFalse(out.exists() and any(out.glob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
