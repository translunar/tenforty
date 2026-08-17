"""Fail-closed gate for the unmodeled prior-year capital-loss carryover.

A prior-year capital-loss carryover enters Schedule D at line 6 (short-term)
and line 14 (long-term). tenforty v1 models neither line and has no scenario
field for either amount, so `acknowledges_no_capital_loss_carryforward=False`
(a carryover EXISTS) must REFUSE rather than compute as if it were zero.

These tests are deliberately paranoid about the "guard that cannot fail"
failure mode: they assert the trigger predicate actually fires, that the
refusal text is non-empty, and that a real production compute entry point
(`sch_d.compute`) — not just the dispatcher — raises.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.attestations import _ATTESTATIONS, enforce_compute_time
from tenforty.forms import sch_d
from tenforty.models import Form1099B, K1FanoutData, Scenario
from tenforty.scenario import load_scenario
from tests.helpers import make_simple_scenario, scope_out_attestation_defaults

FIELD = "acknowledges_no_capital_loss_carryforward"


def _entry():
    return next(a for a in _ATTESTATIONS if a.field == FIELD)


class TestCapitalLossCarryforwardRegistryEntry(unittest.TestCase):
    def test_field_is_registered(self) -> None:
        self.assertIn(FIELD, {a.field for a in _ATTESTATIONS})

    def test_load_error_names_schedule_d_lines_6_and_14(self) -> None:
        load_error = _entry().load_error
        self.assertIn("line 6", load_error)
        self.assertIn("line 14", load_error)

    def test_compute_error_is_non_empty_and_explains_the_harm(self) -> None:
        """An `_always`-triggered gate whose compute_error is "" would raise
        NotImplementedError with an empty message — a refusal the user cannot
        act on. Several load-time-only entries in the registry legitimately
        carry compute_error="", so this is a real distinction, not a truism."""
        compute_error = _entry().compute_error
        self.assertTrue(compute_error.strip())
        self.assertIn("line 6", compute_error)
        self.assertIn("line 14", compute_error)
        self.assertIn("OVERSTATED", compute_error)

    def test_trigger_fires_for_a_scenario_with_no_capital_data_at_all(self) -> None:
        """The gate's subject leaves no trace in scenario data, so the trigger
        must fire unconditionally. This is the test that fails if the entry is
        ever changed to the `_never` sentinel used by the load-time-only
        entries: `_never` would make the False branch unreachable at compute."""
        bare = make_simple_scenario()
        self.assertEqual([], list(bare.form1099_b))
        self.assertEqual([], list(bare.schedule_k1s))
        self.assertIsNone(bare.s_corp_return)
        self.assertTrue(_entry().triggered_when(bare))

    def test_trigger_fires_for_a_scenario_with_capital_data(self) -> None:
        s = make_simple_scenario()
        s.form1099_b = [
            Form1099B(
                broker="Brokerage Inc", description="100 sh XYZ",
                date_acquired="2024-02-01", date_sold="2025-05-01",
                proceeds=5000.0, cost_basis=4000.0,
            ),
        ]
        self.assertTrue(_entry().triggered_when(s))


class TestCapitalLossCarryforwardLoadTime(unittest.TestCase):
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
        """Declaring it (either way) satisfies the load-time gate; the False
        branch is refused later, at compute, with a different exception type."""
        for declared in (True, False):
            with self.subTest(declared=declared):
                path = self._write_scenario_yaml({FIELD: declared})
                scenario = load_scenario(path)
                self.assertIs(getattr(scenario.config, FIELD), declared)


class TestCapitalLossCarryforwardComputeTime(unittest.TestCase):
    def _scenario(self, declared: bool | None) -> Scenario:
        s = make_simple_scenario()
        setattr(s.config, FIELD, declared)
        return s

    def test_dispatcher_refuses_when_false(self) -> None:
        with self.assertRaises(NotImplementedError) as ctx:
            enforce_compute_time(self._scenario(False))
        self.assertEqual(_entry().compute_error, str(ctx.exception))

    def test_dispatcher_proceeds_when_true(self) -> None:
        enforce_compute_time(self._scenario(True))  # no raise

    def test_sch_d_compute_refuses_when_false(self) -> None:
        """The production entry point, not just the dispatcher: `sch_d.compute`
        runs for every scenario on the 1040 pipeline, so this is the call that
        makes the refusal reachable for a return with no 1099-B and no K-1."""
        with self.assertRaises(NotImplementedError) as ctx:
            sch_d.compute(
                self._scenario(False),
                upstream={"k1_fanout": K1FanoutData.empty()},
            )
        self.assertIn("line 6", str(ctx.exception))
        self.assertIn("line 14", str(ctx.exception))

    def test_sch_d_compute_proceeds_when_true(self) -> None:
        result = sch_d.compute(
            self._scenario(True),
            upstream={"k1_fanout": K1FanoutData.empty()},
        )
        # Computes normally: a W-2-only return has no capital transactions,
        # so Sch D line 16 is zero and line 21 (the §1211(b) allowed loss)
        # is zero — reached only because the gate let compute through.
        self.assertEqual(0, result["sch_d_line_16_total"])
        self.assertEqual(0, result["sch_d_line_21_allowed_loss"])

    def test_sch_d_compute_still_refuses_with_capital_transactions(self) -> None:
        s = self._scenario(False)
        s.form1099_b = [
            Form1099B(
                broker="Brokerage Inc", description="100 sh XYZ",
                date_acquired="2024-02-01", date_sold="2025-05-01",
                proceeds=5000.0, cost_basis=9000.0,
            ),
        ]
        with self.assertRaises(NotImplementedError):
            sch_d.compute(s, upstream={"k1_fanout": K1FanoutData.empty()})


if __name__ == "__main__":
    unittest.main()
