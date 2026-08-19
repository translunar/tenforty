"""Fail-closed gate for unmodeled federal alternative minimum tax.

Federal AMT (IRC §55) is computed on Form 6251 and enters the return at
Schedule 2 line 1, which flows to Form 1040 line 17, then 18, then 24. The
native compute path implements no Form 6251, so AMT is zero there by absence.
`acknowledges_no_federal_amt=False` (AMT may apply) must therefore REFUSE
rather than compute as if AMT were zero.

These tests are deliberately paranoid about the "guard that cannot fail"
failure mode: they assert the trigger predicate actually fires, that the
refusal text is non-empty and names the harm in the right DIRECTION, and that
a real production compute entry point — not just the dispatcher — raises.

Per the note on `tests.helpers._TEST_POSTURE_AFFIRMED`, every test here that
exercises the refusal sets the field False EXPLICITLY and asserts it took
effect first. None of them reach the gate through the suite-wide affirming
default.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.attestations import _ATTESTATIONS, _always, enforce_compute_time
from tenforty.forms import sch_d
from tenforty.models import K1FanoutData, Scenario
from tenforty.scenario import load_scenario
from tests.helpers import make_simple_scenario, scope_out_attestation_defaults

FIELD = "acknowledges_no_federal_amt"


def _entry():
    return next(a for a in _ATTESTATIONS if a.field == FIELD)


class FederalAmtRegistryEntryTests(unittest.TestCase):
    def test_field_is_registered(self) -> None:
        self.assertIn(FIELD, {a.field for a in _ATTESTATIONS})

    def test_trigger_is_the_always_sentinel(self) -> None:
        """The shape is a USER DECISION recorded on the registry entry, not a
        derived tax-law trigger. `_never` would make the False branch
        unreachable at compute time — the exact "wired but cannot fire"
        failure this file exists to rule out — and any narrower predicate
        would be the underived trigger that was deliberately not written."""
        self.assertIs(_always, _entry().triggered_when)

    def test_trigger_fires_for_a_scenario_with_no_amt_signal_at_all(self) -> None:
        bare = make_simple_scenario()
        self.assertEqual([], list(bare.form1099_b))
        self.assertEqual([], list(bare.schedule_k1s))
        self.assertIsNone(bare.s_corp_return)
        self.assertTrue(_entry().triggered_when(bare))

    def test_load_error_names_form_6251_and_the_lines_amt_reaches(self) -> None:
        load_error = _entry().load_error
        self.assertIn("6251", load_error)
        self.assertIn("line 17", load_error)

    def test_compute_error_names_the_gap_the_direction_and_the_alternative(
        self,
    ) -> None:
        """Three separate requirements, and the DIRECTION one is the reason
        this test is not a formality. AMT is an ADDITION to tax, so omitting
        it makes the computed tax too LOW — UNDERSTATED. The sibling
        capital-loss-carryforward gate drops a DEDUCTION and therefore
        OVERSTATES. The two read almost identically in prose ("we don't model
        X") and fail in OPPOSITE directions, and this message has to state the
        right one."""
        compute_error = _entry().compute_error
        self.assertTrue(compute_error.strip())
        # The gap.
        self.assertIn("6251", compute_error)
        # The direction.
        self.assertIn("UNDERSTATED", compute_error)
        # ...and the MECHANISM that makes that the right direction, so the
        # word is not just an unexplained label a future edit could flip.
        self.assertIn("ADDITION to tax", compute_error)
        # The alternative: the workbook path computes AMT, the native one
        # does not.
        self.assertIn("workbook", compute_error)
        self.assertIn("NATIVE", compute_error)


class FederalAmtLoadTimeTests(unittest.TestCase):
    def _write_scenario_yaml(self, config_extra: dict) -> Path:
        defaults = scope_out_attestation_defaults()
        defaults.pop(FIELD, None)
        body = {
            "config": {
                "year": 2025, "filing_status": "single",
                "birthdate": "1985-04-20", "state": "CA",
                "has_foreign_accounts": False,
                "prior_year_itemized": False,
                **defaults,
                **config_extra,
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        return path

    def test_scenario_omitting_the_attestation_fails_to_load(self) -> None:
        path = self._write_scenario_yaml({})
        with self.assertRaises(ValueError) as ctx:
            load_scenario(path)
        self.assertIn(FIELD, str(ctx.exception))

    def test_scenario_declaring_the_attestation_loads(self) -> None:
        """Declaring it either way satisfies the load-time gate; the False
        branch is refused later, at compute, with a different exception."""
        for declared in (True, False):
            with self.subTest(declared=declared):
                path = self._write_scenario_yaml({FIELD: declared})
                scenario = load_scenario(path)
                self.assertIs(declared, getattr(scenario.config, FIELD))


class FederalAmtComputeTimeTests(unittest.TestCase):
    def _scenario(self, declared: bool) -> Scenario:
        s = make_simple_scenario()
        setattr(s.config, FIELD, declared)
        if declared is False:
            # Precondition, per _TEST_POSTURE_AFFIRMED note (d): prove the
            # explicit False took effect rather than reaching the gate through
            # the suite-wide affirming default.
            self.assertFalse(getattr(s.config, FIELD))
        return s

    def test_dispatcher_refuses_when_false(self) -> None:
        with self.assertRaises(NotImplementedError) as ctx:
            enforce_compute_time(self._scenario(False))
        self.assertEqual(_entry().compute_error, str(ctx.exception))

    def test_dispatcher_proceeds_when_affirmed(self) -> None:
        enforce_compute_time(self._scenario(True))  # no raise

    def test_sch_d_compute_refuses_when_false(self) -> None:
        """A production entry point, not just the dispatcher. `sch_d.compute`
        runs for every scenario on the 1040 pipeline, so refusing there means
        the whole return refuses — including for a filer with no capital
        transactions and no other AMT-looking data."""
        s = self._scenario(False)
        with self.assertRaises(NotImplementedError) as ctx:
            sch_d.compute(s, upstream={"k1_fanout": K1FanoutData.empty()})
        self.assertIn("6251", str(ctx.exception))
        self.assertIn("UNDERSTATED", str(ctx.exception))

    def test_sch_d_compute_proceeds_when_affirmed(self) -> None:
        """The other half of the mutation pair: without this, a gate that
        refused unconditionally would also pass the test above."""
        result = sch_d.compute(
            self._scenario(True),
            upstream={"k1_fanout": K1FanoutData.empty()},
        )
        self.assertEqual(0, result["sch_d_line_16_total"])


if __name__ == "__main__":
    unittest.main()
