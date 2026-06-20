"""Penny-parity gate: native 1040 spine vs XLSX oracle, 2025 and 2024.

For each battery scenario, runs both the native spine path
(_compute_1040_pipeline) and the XLSX oracle (_compute_1040_via_workbook)
on the same effective scenario and asserts penny-exact equality across
PARITY_KEYS.

The 2024 class proves the year-seam: the SAME native spine, with 2024 params
swapped in, matches the 2024 workbook penny-for-penny.

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
from tests.fixtures.spine_battery import BATTERY, BATTERY_2024
from tests.helpers import REPO_ROOT, needs_libreoffice

# Keys asserted penny-exact between native and oracle paths.
# f8949 box keys are excluded (raw workbook outputs, not in scope here).
# total_payments is withholding-only (no estimated payments in the battery).
PARITY_KEYS = (
    "agi",
    "total_income",
    # NOTE: `standard_deduction` is intentionally NOT compared. It is an
    # ambiguous intermediate for itemizers — the workbook reports the standard
    # deduction amount *available* (always), while the native spine reports 0
    # when itemized deductions win (the standard deduction was not applied).
    # `total_deductions` below is the meaningful comparison: the std-or-itemized
    # deduction actually subtracted from AGI to reach taxable income. Asserting
    # parity on `standard_deduction` itself needs its own decision (the
    # native-vs-workbook Form 1040 line-12 representation for itemizers);
    # tracked separately.
    "total_deductions",
    "taxable_income",
    "taxable_income_before_qbi_deduction",
    "total_tax",
    "total_payments",
    "overpaid",
    "net_capital_gain",
    "schedule_a_total",
    "sch_a_line_5e_salt_capped",
)


def _run_parity_battery(test_case: unittest.TestCase, battery) -> None:
    """Run penny-parity check for every (name, builder) pair in battery.

    Shared logic for both the 2025 and 2024 parity test classes so that
    the routing guard and assertion loop are maintained in one place.
    """
    for name, build in battery:
        with test_case.subTest(scenario=name):
            scenario = build()
            with tempfile.TemporaryDirectory() as tmp:
                orch = ReturnOrchestrator(
                    spreadsheets_dir=REPO_ROOT / "spreadsheets",
                    work_dir=Path(tmp),
                )
                eff, _ = orch._build_effective_scenario(scenario)

                # ROUTING GUARD: confirm native spine is taken, not fallback.
                test_case.assertTrue(
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
                test_case.assertEqual(
                    native[key],
                    oracle[key],
                    f"{name}: {key} native={native[key]!r} oracle={oracle[key]!r}",
                )


@needs_libreoffice
class SpineParity2025Tests(unittest.TestCase):
    @pytest.mark.oracle
    def test_native_matches_workbook_pennywise(self):
        _run_parity_battery(self, BATTERY)


@needs_libreoffice
class SpineParity2024Tests(unittest.TestCase):
    """Year-seam proof: same native spine, 2024 params, matches 2024 workbook."""

    @pytest.mark.oracle
    def test_native_matches_workbook_pennywise(self):
        _run_parity_battery(self, BATTERY_2024)


if __name__ == "__main__":
    unittest.main()
