"""Structural pin for the CA W-2 withholding channel (Form 540 line 71).

Drives the orchestrator CA compute core (``_compute_ca_results``, the
``scenario.ca540`` path — NOT the separate-CA-YAML path) on the permanent
``_make_ca_withholding_scenario`` fixture and pins two structural facts:

  1. The orchestrator sums ``scenario.w2s`` box-17 withholding where
     ``state == "CA"`` into ``f540_line71_ca_withholding``.
  2. That withholding NETS against the balance: the same scenario with zero
     CA withholding owes exactly the withholding amount MORE.

Both assertions are structural (an identity and a delta) — no golden dollar
value — so the pin survives any future re-tune of the CA tax/exemption
parameters.

COVERAGE DIVISION: this pin GUARDS THE ORCHESTRATOR SUMMATION/FILTER half —
the ``scenario.w2s``-where-``state == "CA"`` sum that WIRE-2 added. The
cross-check (``test_ca_540_withholding_cross_check``) drives ``f540.compute``
directly and BYPASSES that summation, so it CANNOT catch a regression in the
filter; conversely it guards the balance-chain half (line 71 → line 78 →
refund/owe) against an independent oracle, which this pin does not. Two named
halves of one chain, no gap between them.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_withholding_scenario


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


if __name__ == "__main__":
    unittest.main()
