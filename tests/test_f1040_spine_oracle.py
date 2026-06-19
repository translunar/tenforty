"""Penny-parity gate: native 1040 spine vs XLSX oracle, 2025.

For each battery scenario, runs both the native spine path
(_compute_1040_pipeline) and the XLSX oracle (_compute_1040_via_workbook)
on the same effective scenario and asserts penny-exact equality across
PARITY_KEYS.

ROUTING GUARD: Every battery scenario must route to the NATIVE spine, not
fall back to the oracle. Each subTest asserts _scenario_in_spine_scope is
True before comparing — a fallback comparison would be workbook-vs-workbook
and would prove nothing about the native implementation.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import BATTERY
from tests.helpers import REPO_ROOT, needs_libreoffice

# Keys asserted penny-exact between native and oracle paths.
# f8949 box keys are excluded (raw workbook outputs, not in scope here).
# total_payments is withholding-only (no estimated payments in the battery).
PARITY_KEYS = (
    "agi",
    "total_income",
    "standard_deduction",
    "total_deductions",
    "taxable_income",
    "taxable_income_before_qbi_deduction",
    "total_tax",
    "total_payments",
    "overpaid",
    "net_capital_gain",
)


@needs_libreoffice
class SpineParity2025Tests(unittest.TestCase):
    @pytest.mark.oracle
    def test_native_matches_workbook_pennywise(self):
        for name, build in BATTERY:
            with self.subTest(scenario=name):
                scenario = build()
                with tempfile.TemporaryDirectory() as tmp:
                    orch = ReturnOrchestrator(
                        spreadsheets_dir=REPO_ROOT / "spreadsheets",
                        work_dir=Path(tmp),
                    )
                    eff, _ = orch._build_effective_scenario(scenario)

                    # ROUTING GUARD: confirm native spine is taken, not fallback.
                    self.assertTrue(
                        orch._scenario_in_spine_scope(eff),
                        f"{name}: scenario did NOT route native — "
                        f"_scenario_in_spine_scope returned False. "
                        f"Parity comparison would be workbook-vs-workbook. "
                        f"Fix the battery scenario (increase income to clear "
                        f"the EIC gate, or use single filing status).",
                    )

                    native = orch._compute_1040_pipeline(eff)
                    oracle = orch._compute_1040_via_workbook(eff)

                for key in PARITY_KEYS:
                    self.assertEqual(
                        native[key],
                        oracle[key],
                        f"{name}: {key} native={native[key]!r} oracle={oracle[key]!r}",
                    )


if __name__ == "__main__":
    unittest.main()
