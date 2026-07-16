"""Penny-parity gate: native 1040 spine vs XLSX oracle, every workbook year in the manifest.

For each battery scenario, runs both the native spine path
(_compute_1040_pipeline) and the XLSX oracle (_compute_1040_via_workbook)
on the same effective scenario and asserts penny-exact equality across
PARITY_KEYS.

The 2024 sweep proves the year-seam: the SAME native spine, with 2024 params
swapped in, matches the 2024 workbook penny-for-penny.

ROUTING GUARD: Every battery scenario must route to the NATIVE spine, not
fall back to the oracle. Each subTest asserts _scenario_in_spine_scope is
True before comparing — a fallback comparison would be workbook-vs-workbook
and would prove nothing about the native implementation.

PARITY INVARIANT: a workbook year yields full penny-parity over its DECLARED
surface; exclusions are explicit, reasoned, and gated. Where a vendor workbook
structurally omits a form (e.g. the TY2021 workbook has no Form 8582 tab), that
form's keys are declared in F1040.WORKBOOK_KEY_EXCLUSIONS — surfaced here as
explicit skips-with-reason (never silently absent) and typo-guarded (every
excluded key must exist in another workbook year's map). No silent
half-support, in either direction.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.mappings.f1040 import F1040, WORKBOOK_KEY_EXCLUSIONS
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import battery_for
from tests.helpers import REPO_ROOT, needs_libreoffice
from tenforty import years as year_manifest

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
    # Form 1040 lines 13 and 14, made path-uniform by construction this branch
    # (qbi_deduction: native spine emit + oracle f1040.compute normalize;
    # deductions_plus_qbi = line 14 = 12c + QBI, both paths). Parity locks that
    # uniformity so lines 13/14 agree native-vs-workbook — materially exercised
    # by the qbi_k1_deduction battery scenario (QBI>0); for QBI=0 scenarios both
    # reduce to total_deductions (already compared above).
    "qbi_deduction",
    "deductions_plus_qbi",
    "total_tax",
    "total_payments",
    "overpaid",
    "net_capital_gain",
    "schedule_a_total",
    "sch_a_line_5e_salt_capped",
    # Form 8962 (Premium Tax Credit): net PTC (line 26) and excess-APTC
    # repayment (line 29). WP-Task 2 added these to F1040.OUTPUTS as
    # PTC_Net/PTC_Excess (named ranges, all workbook years); the native
    # spine already emits f8962_net_ptc/f8962_repayment. For non-PTC
    # battery scenarios (no Form 1095-A), both sides read 0: no 1095-A
    # means the flattener emits no 8962 keys, which leaves the workbook's
    # PTC cells blank. The engine reads a blank cell as None (not 0), so the
    # workbook-oracle path normalizes these two PTC money keys None -> 0
    # (see _compute_1040_via_workbook) — matching the native spine's
    # zero-PTC default. NOTE: `total_payments`/
    # `overpaid` above already exercise the PTC FLOW into the 1040 totals
    # (net PTC adds to payments, excess-APTC repayment adds to tax owed);
    # these two keys additionally check the PTC computation ITSELF, on the
    # native spine's own Form 8962 output, not just its downstream effect.
    "f8962_net_ptc",
    "f8962_repayment",
)


# Native-key -> oracle-key overrides for the parity comparison. Default is
# same-key. EXPLICIT exception: the native spine's `total_tax` is line-16-only
# (Schedule 2 joins `overpaid`, not `total_tax`; 1040-X line 6 composes from
# this line-16 base), but the workbook's production `total_tax` OUTPUT points at
# the `Tax` named range, which is SUM(Tax_SubTotal, Schedule2_Tax) — i.e.
# Schedule-2-INCLUSIVE, because its production consumer (the out-of-spine
# workbook-fallback path → Form 4868 balance-due) needs FULL liability. The two
# paths serve different consumers with different-but-correct semantics and are
# deliberately NOT unified. So parity on the line-16 quantity compares native
# `total_tax` against the workbook's separate line-16-only OUTPUT
# `total_tax_line16` (← the `Tax_SubTotal` named range). See
# tenforty/mappings/f1040.py's OUTPUTS entries for the mapping-side rationale.
_PARITY_ORACLE_KEY = {
    "total_tax": "total_tax_line16",
}


def _run_parity_battery(test_case: unittest.TestCase, battery, *, year=None) -> None:
    """Run penny-parity check for every (name, builder) pair in battery.

    Shared logic for the parity sweep over every workbook year so that
    the routing guard and assertion loop are maintained in one place.
    """
    for name, build in battery:
        with test_case.subTest(year=year, scenario=name):
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
                oracle_key = _PARITY_ORACLE_KEY.get(key, key)
                test_case.assertEqual(
                    native[key],
                    oracle[oracle_key],
                    f"{name}: {key} native={native[key]!r} "
                    f"oracle[{oracle_key}]={oracle[oracle_key]!r}",
                )


@needs_libreoffice
class SpineParityTests(unittest.TestCase):
    """One gate, every registered workbook year. Registering a new year's
    workbook in the manifest extends this gate to it automatically —
    the year-seam proof (same spine, swapped params, matches that year's
    workbook) runs for every year that has an oracle to match."""

    @pytest.mark.oracle
    def test_native_matches_every_workbook_pennywise(self):
        for year in year_manifest.WORKBOOK_YEARS:
            _run_parity_battery(self, battery_for(year), year=year)


class WorkbookKeyExclusionTests(unittest.TestCase):
    """The exclusion registry is READ here (fast, no soffice): excluded keys
    are surfaced as explicit skips-with-reason and typo-guarded. This keeps the
    parity invariant honest — a key leaves the compared surface only via a
    reasoned, gated entry, never by silently vanishing from a year's map."""

    def test_excluded_keys_are_surfaced_as_explicit_skips(self):
        # Never silently absent: every exclusion is reported (as a skip with
        # its reason) so a reader of the parity results sees exactly what is
        # NOT compared and why.
        if not WORKBOOK_KEY_EXCLUSIONS:
            self.skipTest("no workbook key exclusions declared")
        for (year, key), reason in sorted(WORKBOOK_KEY_EXCLUSIONS.items()):
            with self.subTest(year=year, key=key):
                self.skipTest(f"{year} {key} excluded from parity: {reason}")

    def test_every_excluded_key_exists_in_another_workbook_year(self):
        # Typo protection: an excluded key must be a REAL key — present in some
        # OTHER workbook year's INPUTS or OUTPUTS map. A misspelled exclusion
        # would otherwise silently exclude nothing (or mask a real key).
        for (year, key), reason in sorted(WORKBOOK_KEY_EXCLUSIONS.items()):
            with self.subTest(year=year, key=key):
                found = any(
                    key in F1040.INPUTS.get(other, {})
                    or key in F1040.OUTPUTS.get(other, {})
                    for other in year_manifest.WORKBOOK_YEARS
                    if other != year
                )
                self.assertTrue(
                    found,
                    f"excluded key {key!r} (year {year}) appears in NO other "
                    f"workbook year's map — likely a typo, or the last year "
                    f"that carried it was removed. Reason on file: {reason}",
                )

    def test_excluded_keys_absent_from_their_own_year_maps(self):
        # The other half of the invariant: an excluded key must actually be
        # GONE from its own year's maps (the wiring removed it), so the engine
        # never writes/reads it against the missing sheet.
        for (year, key) in sorted(WORKBOOK_KEY_EXCLUSIONS):
            with self.subTest(year=year, key=key):
                self.assertNotIn(key, F1040.INPUTS.get(year, {}))
                self.assertNotIn(key, F1040.OUTPUTS.get(year, {}))
                self.assertNotIn(key, F1040.SHEET_MAP.get(year, {}))


if __name__ == "__main__":
    unittest.main()
