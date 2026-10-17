"""Per-owner excess Social Security guard and W-2 `owner` discipline
(ruling R-excess-ss).

Each employer withholds Social Security tax up to the year's maximum
(``ss_wage_base`` times the employee rate). A person whose W-2s together
withheld more than that maximum is owed the excess back as a credit on
Schedule 3 line 11. tenforty does not compute that credit, so the
orchestrator refuses whenever any one owner's withholding exceeds the
maximum. On a joint return each spouse has their own maximum, so the
withholding is grouped by `W2.owner`. That owner field is required on every
W-2 of a married-filing-jointly scenario and refused as "spouse" anywhere
else.

The maximum is derived from params and the codebase's rate constant, never
written here. All identities and amounts are synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tenforty.models import FilingStatus, Scenario, W2
from tenforty.orchestrator import ReturnOrchestrator, ss_withholding_maximum
from tenforty.scenario import load_scenario
from tests.fixtures.spine_battery import _battery_config
from tests.helpers import REPO_ROOT

_YEAR = 2025
_S = FilingStatus.SINGLE
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD


def _w2_at_maximum(year, employer, owner=None, *, ss_tax_withheld=None):
    """A W-2 whose wages sit at the year's wage base, so its correct SS
    withholding is exactly the year's maximum."""
    from tenforty.params.federal import load as load_params
    base = float(load_params(year).ss_wage_base)
    maximum = ss_withholding_maximum(year)
    return W2(
        employer=employer, wages=base, federal_tax_withheld=0.0,
        ss_wages=base,
        ss_tax_withheld=maximum if ss_tax_withheld is None else ss_tax_withheld,
        medicare_wages=base, medicare_tax_withheld=0.0, owner=owner)


def _scenario(status, w2s):
    return Scenario(config=_battery_config(_YEAR, status), w2s=list(w2s))


class ExcessSocialSecurityGuardTests(unittest.TestCase):
    def setUp(self):
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work")
        self.maximum = ss_withholding_maximum(_YEAR)

    def _compute(self, scenario):
        return self.orch.compute_federal(scenario)

    def test_couple_each_under_the_cap_computes(self):
        scenario = _scenario(_MFJ, [
            _w2_at_maximum(_YEAR, "Synthetic Employer T", "taxpayer"),
            _w2_at_maximum(_YEAR, "Synthetic Employer S", "spouse")])
        # Reachability: the couple's combined withholding is over ONE
        # person's maximum, so a guard summing across owners would refuse.
        self.assertGreater(
            sum(w.ss_tax_withheld for w in scenario.w2s), self.maximum)
        results = self._compute(scenario)
        self.assertIn("total_tax", results)

    def test_one_owner_over_via_two_w2s_refuses_naming_schedule_3(self):
        scenario = _scenario(_MFJ, [
            _w2_at_maximum(_YEAR, "Synthetic Employer A", "taxpayer"),
            _w2_at_maximum(_YEAR, "Synthetic Employer B", "taxpayer"),
            _w2_at_maximum(_YEAR, "Synthetic Employer S", "spouse")])
        with self.assertRaisesRegex(
                NotImplementedError, r"(?s)taxpayer.*Schedule 3 line 11"):
            self._compute(scenario)

    def test_spouse_over_via_two_w2s_refuses_naming_the_spouse(self):
        scenario = _scenario(_MFJ, [
            _w2_at_maximum(_YEAR, "Synthetic Employer T", "taxpayer"),
            _w2_at_maximum(_YEAR, "Synthetic Employer A", "spouse"),
            _w2_at_maximum(_YEAR, "Synthetic Employer B", "spouse")])
        with self.assertRaisesRegex(
                NotImplementedError, r"(?s)spouse.*Schedule 3 line 11"):
            self._compute(scenario)

    def test_single_w2_at_the_maximum_never_trips_the_guard(self):
        scenario = _scenario(_S, [_w2_at_maximum(_YEAR, "Synthetic Employer")])
        results = self._compute(scenario)
        self.assertIn("total_tax", results)

    def test_single_filer_two_employers_over_the_maximum_refuses(self):
        scenario = _scenario(_S, [
            _w2_at_maximum(_YEAR, "Synthetic Employer A"),
            _w2_at_maximum(_YEAR, "Synthetic Employer B")])
        with self.assertRaisesRegex(
                NotImplementedError, r"(?s)taxpayer.*Schedule 3 line 11"):
            self._compute(scenario)

    def test_single_w2_over_withheld_by_its_employer_still_refuses(self):
        scenario = _scenario(_S, [_w2_at_maximum(
            _YEAR, "Synthetic Employer", ss_tax_withheld=self.maximum + 1)])
        with self.assertRaisesRegex(NotImplementedError,
                                    "Schedule 3 line 11"):
            self._compute(scenario)

    def _three_w2s_summing_to_the_maximum(self, *, extra_cents=0.0):
        # Amounts in cents whose left-to-right FLOAT sum overshoots the
        # maximum by a rounding residue while their cent total is exactly
        # the maximum (asserted below, so the case stays reachable).
        parts = [8634.37, 1989.96]
        parts.append(round(self.maximum - sum(parts) + extra_cents, 2))
        return parts

    def test_multi_w2_total_exactly_at_the_maximum_is_not_refused(self):
        parts = self._three_w2s_summing_to_the_maximum()
        float_total = 0.0
        for amount in parts:
            float_total += amount
        # Reachability: an unrounded comparison WOULD refuse this return.
        self.assertGreater(float_total, self.maximum)
        self.assertEqual(round(float_total, 2), self.maximum)
        scenario = _scenario(_S, [
            _w2_at_maximum(_YEAR, f"Synthetic Employer {i}",
                           ss_tax_withheld=amount)
            for i, amount in enumerate(parts)])
        self.orch._refuse_excess_social_security(scenario)   # no refusal

    def test_multi_w2_total_one_cent_over_the_maximum_refuses(self):
        parts = self._three_w2s_summing_to_the_maximum(extra_cents=0.01)
        scenario = _scenario(_S, [
            _w2_at_maximum(_YEAR, f"Synthetic Employer {i}",
                           ss_tax_withheld=amount)
            for i, amount in enumerate(parts)])
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch._refuse_excess_social_security(scenario)
        self.assertIn("Schedule 3 line 11", str(ctx.exception))

    def test_guard_runs_ahead_of_the_workbook_route(self):
        # MFS is not on the native grid, so this scenario would route to
        # the workbook; the refusal must come first.
        scenario = Scenario(
            config=dataclasses.replace(
                _battery_config(_YEAR, _S),
                filing_status=FilingStatus.MARRIED_FILING_SEPARATELY),
            w2s=[_w2_at_maximum(_YEAR, "Synthetic Employer A"),
                 _w2_at_maximum(_YEAR, "Synthetic Employer B")])
        with mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("routed to the workbook")):
            with self.assertRaisesRegex(NotImplementedError,
                                        "Schedule 3 line 11"):
                self._compute(scenario)

    # --- W2.owner discipline at load -------------------------------------

    def _yaml_with(self, filing_status, owners):
        """The mfj_simple fixture re-stated with the given status and one
        W-2 per entry of `owners` (None = the key omitted)."""
        data = yaml.safe_load(
            (REPO_ROOT / "tests" / "fixtures" / "mfj_simple.yaml").read_text())
        data["config"]["filing_status"] = filing_status.value
        if filing_status is not _MFJ:
            data["config"].pop("spouse_birthdate", None)
        if filing_status is _HOH:
            # Head of household requires its qualifying-person block (FTB
            # 3532); synthetic values.
            year = data["config"]["year"]
            data["config"]["head_of_household"] = {
                "marital_status": "unmarried",
                "qualifying_person": {
                    "first_name": "Example", "last_name": "Child",
                    "ssn": "000-00-0005", "birthdate": f"{year - 10}-03-07",
                    "relationship": "child_or_stepchild",
                    "gross_income": 0, "days_lived_with_you": 365,
                    "claimed_as_dependent": False}}
        template = data["w2s"][0]
        data["w2s"] = []
        for i, owner in enumerate(owners):
            w2 = {**template, "employer": f"Synthetic Employer {i}"}
            w2.pop("owner", None)
            if owner is not None:
                w2["owner"] = owner
            data["w2s"].append(w2)
        path = Path(tempfile.mkdtemp()) / "scenario.yaml"
        path.write_text(yaml.safe_dump(data))
        return path

    def test_mfj_w2_missing_owner_is_refused_at_load(self):
        path = self._yaml_with(_MFJ, ["taxpayer", None])
        with self.assertRaisesRegex(
                ValueError, r"(?s)`owner`.*married_filing_jointly"):
            load_scenario(path)

    def test_mfj_w2s_all_carrying_owner_load(self):
        scenario = load_scenario(self._yaml_with(_MFJ, ["taxpayer", "spouse"]))
        self.assertEqual([w.owner for w in scenario.w2s],
                         ["taxpayer", "spouse"])

    def test_spouse_owner_on_a_non_mfj_scenario_is_refused_at_load(self):
        for status in (_S, _HOH):
            with self.subTest(status=status):
                path = self._yaml_with(status, ["spouse"])
                with self.assertRaisesRegex(
                        ValueError, rf"(?s)`owner: spouse`.*{status.value}"):
                    load_scenario(path)

    def test_owner_stays_optional_on_a_non_mfj_scenario(self):
        for status in (_S, _HOH):
            with self.subTest(status=status):
                scenario = load_scenario(
                    self._yaml_with(status, [None, "taxpayer"]))
                self.assertEqual([w.owner for w in scenario.w2s],
                                 [None, "taxpayer"])
