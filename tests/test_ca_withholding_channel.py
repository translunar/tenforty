"""Structural pin for the CA W-2 withholding channel (Form 540 line 71).

Drives the orchestrator CA compute core (``_compute_ca_results``, the
``scenario.ca540`` path — NOT the separate-CA-YAML path) on the permanent
``_make_ca_withholding_scenario`` fixture and pins three structural facts:

  1. The orchestrator sums ``scenario.w2s`` box-17 withholding where
     ``state == "CA"`` into ``f540_line71_ca_withholding``.
  2. That withholding NETS against the balance: the same scenario with zero
     CA withholding owes exactly the withholding amount MORE.
  3. The ``state == "CA"`` comparison is a real FILTER, not just a sum: an
     attributed NON-CA W-2 (state="NY") alongside a CA W-2 contributes
     NOTHING to line 71 (``CAWithholdingChannelTest.
     test_non_ca_state_withholding_excluded_from_line_71``).

Also covers the orchestrator guard's REFUSAL branch
(``CAWithholdingOrchestratorGuardRefusalTest``): on the separate-CA-YAML
``run_full_california_return`` path, ``scenario.ca540`` is None so
``Scenario.__post_init__``'s refusal guard never fires, making
``_compute_ca_results``'s own loop the SOLE attribution enforcement for
that path.

All structural assertions are identities/deltas/exceptions — no golden
dollar value — so the pins survive any future re-tune of the CA tax/
exemption parameters.

COVERAGE DIVISION: this module GUARDS THE ORCHESTRATOR SUMMATION/FILTER
half — the ``scenario.w2s``-where-``state == "CA"`` sum (and its filter and
refusal guard) that WIRE-2 added. The cross-check
(``test_ca_540_withholding_cross_check``) drives ``f540.compute`` directly
and BYPASSES that summation, so it CANNOT catch a regression in the filter;
conversely it guards the balance-chain half (line 71 → line 78 →
refund/owe) against an independent oracle, which this module does not. Two
named halves of one chain, no gap between them.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.models import W2
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import (
    _make_ca_v1_smoke_scenario,
    _make_ca_withholding_scenario,
    _write_ca_yaml,
)


REPO_ROOT = Path(__file__).parent.parent

_CA_WITHHOLDING = 4_000


class CAWithholdingChannelTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _compute(self, scenario):
        """Run the orchestrator CA compute core on the scenario.ca540 path."""
        federal = self.orch.compute_federal(scenario)
        return self.orch._compute_ca_results(scenario, scenario.ca540, federal)

    def test_line_71_summed_and_netted_from_ca_w2(self):
        with_wh = _make_ca_withholding_scenario(
            state_tax_withheld=float(_CA_WITHHOLDING)
        )
        zero_wh = _make_ca_withholding_scenario(state_tax_withheld=0.0)

        result = self._compute(with_wh)
        zero_result = self._compute(zero_wh)

        # (1) The CA-attributed W-2 box-17 withholding lands on line 71.
        self.assertEqual(result["f540_line71_ca_withholding"], _CA_WITHHOLDING)
        self.assertEqual(zero_result["f540_line71_ca_withholding"], 0)

        # (2) Withholding nets against the balance: the zero-withholding twin
        # (identical income → identical tax, exemption, everything else) owes
        # exactly _CA_WITHHOLDING more. Proves line 71 flows into
        # total_liability with the correct sign and magnitude.
        self.assertEqual(
            result["f540_total_liability"],
            zero_result["f540_total_liability"] - _CA_WITHHOLDING,
        )

    def test_non_ca_state_withholding_excluded_from_line_71(self):
        """FILTER half of the pin's docstring claim: the orchestrator's
        ``state == "CA"`` comparison must EXCLUDE an attributed non-CA W-2's
        withholding from line 71, not just sum every W-2 unconditionally. A
        mutation that drops the state filter (summing ALL scenario.w2s)
        would still pass ``test_line_71_summed_and_netted_from_ca_w2`` above
        because every W-2 there is already state="CA" -- this test is the
        one that catches it.

        The NY W-2 is ATTRIBUTED (state="NY", not None), so it passes both
        refusal guards cleanly; it must simply never reach line 71.
        """
        ca_scenario = _make_ca_withholding_scenario(
            state_tax_withheld=float(_CA_WITHHOLDING)
        )
        ca_w2 = ca_scenario.w2s[0]
        ny_w2 = dataclasses.replace(
            ca_w2,
            employer="New York Employer LLC",
            state="NY",
            state_tax_withheld=1_500.0,
        )
        both_states = dataclasses.replace(ca_scenario, w2s=[ca_w2, ny_w2])

        result = self._compute(both_states)

        # Line 71 is ONLY the CA W-2's withholding -- the NY amount is
        # excluded, not summed in.
        self.assertEqual(result["f540_line71_ca_withholding"], _CA_WITHHOLDING)


class CAWithholdingOrchestratorGuardRefusalTest(unittest.TestCase):
    """Covers the orchestrator guard's REFUSAL branch in
    ``_compute_ca_results`` (~orchestrator.py:1470) on the separate-CA-YAML
    ``run_full_california_return`` path.

    That path builds its ``Scenario`` with ``ca540=None`` (CA data comes
    from the sibling CA YAML instead), so ``Scenario.__post_init__``'s own
    refusal guard -- which only runs ``if self.ca540 is not None`` -- never
    fires. ``_compute_ca_results``'s loop is therefore the SOLE attribution
    enforcement for this path; this test drives exactly that path with an
    unattributed withholding W-2 and asserts the guard actually refuses.
    """

    def test_unattributed_withholding_w2_raises_on_separate_ca_yaml_path(self):
        base = _make_ca_v1_smoke_scenario()
        stateless_w2 = W2(
            employer="Stateless Employer LLC",
            wages=50_000.0,
            federal_tax_withheld=5_000.0,
            ss_wages=50_000.0,
            ss_tax_withheld=3_100.0,
            medicare_wages=50_000.0,
            medicare_tax_withheld=725.0,
            state_wages=50_000.0,
            state_tax_withheld=1_000.0,
            state=None,
        )
        # ca540=None drives the separate-CA-YAML path: run_full_california_
        # return sources CA data from ca_yaml_path below, so
        # Scenario.__post_init__'s guard (which requires ca540 is not None)
        # never fires here -- only _compute_ca_results's own loop can catch
        # this unattributed W-2.
        scenario = dataclasses.replace(base, w2s=[stateless_w2], ca540=None)
        tmp_dir = Path(tempfile.mkdtemp())
        ca_yaml_path = _write_ca_yaml(
            {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0}}, tmp_dir=tmp_dir,
        )
        output_dir = Path(tempfile.mkdtemp())
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work",
        )
        with self.assertRaises(ValueError) as ctx:
            orch.run_full_california_return(
                scenario=scenario,
                ca_yaml_path=ca_yaml_path,
                output_dir=output_dir,
            )
        self.assertIn("Stateless Employer LLC", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
