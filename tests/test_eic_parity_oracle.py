"""Childless-EIC parity: native vs the workbook (oracle tier; spec §10.4).

For each (2025, status) battery row, the native result and the workbook's —
computed through the oracle-only answer adapter, which writes every EIC
answer from the scenario's facts (tests/eic_oracle_adapter.py) — agree to
the penny on line 27 (`eic`), line 32 and line 33. A row counts as evidence
only when the workbook's own status cells raise no "Please answer" prompt
(spec §10.3 item 2); the health constants are pinned on the fast tier
(tests/test_eic_workbook_health.py). Divergences go to adjudication, never
an allowlist.

Rows NOT compared here, each for a stated reason:
  * UPPER age-bound rows — awaiting the final ruling on the Jan-1
    upper-bound reading (R-S7-1i); in 2025 they refuse natively anyway (the
    Schedule 1-A seniors refusal). The LOWER-bound rows are compared: both
    readings agree there (R-S7-1i);
  * rows that refuse natively (no native value to compare);
  * Schedule C rows (Worksheet B) — the workbook path refuses Schedule C
    outright (orchestrator: "cannot carry Schedule C / Schedule SE"), so the
    oracle has no evidence to offer; they stay native-unit-tested.
2025 MFJ is compared ahead of its EIC-grid declaration (parity first).

ADJUDICATED DIVERGENCES (DIVERGENCES below) are rows where the workbook was
ruled wrong; each asserts BOTH sides exactly, so a change on either side
fails loudly. They are not an allowlist: they stay at their own bins.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator
from tests.eic_oracle_adapter import eic_answers_adapter
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice

YEAR = 2025
EXCLUDED = {
    "single": {"age_upper_bound_in", "age_upper_bound_out",
               "sch_c_worksheet_b", "sch_c_net_loss"},
    "married_filing_jointly": {"age_upper_bound_in", "age_upper_bound_out",
                               "sch_c_worksheet_b", "sch_c_net_loss",
                               "fact_nonresident_alien"},
}
_PROMPTS = ("eic_diag_prompt_an", "eic_diag_prompt_ao", "eic_diag_prompt_ap")
_KEYS = ("eic", "total_other_payments", "total_payments")

# (status, kind) -> (native, workbook) on every key in _KEYS: the oracle
# evidence of d9dec1f's first comparison, adjudicated workbook-wrong.
DIVERGENCES = {
    # R-S7-7: Step 1 Q4's "Yes" branch (B39) only says "See Non-resident
    # aliens, later"; B39 is absent from NoEICredit's OR-chain
    # (A1 '=OR(N1,H21<>"",H28<>"",B34<>"",H65<>"",B157<>"",H294<>"",
    # L316=0,EarnedIncomeWSB<=0,O458<=0)'), so a single NRA keeps the credit.
    ("single", "fact_nonresident_alien"): (0, 649),
    # R-S7-8: the workbook's EIC Table is rebuilt from derived slopes
    # (N7 '=ROUND(N3/N4,4)', N9 '=-ROUND(N3/(N6-N5),7)' = -0.0764969, not
    # the statutory 7.65%), so its 14,850-14,900 bin reads 324 where the
    # published table (assets/eic_tables/2025.csv) reads 323: $1 high here.
    ("single", "phase_out"): (323, 324),
    ("single", "agi_over_earned"): (323, 324),
}


def _n(value) -> int:
    return int(round(value or 0))


@needs_libreoffice
class EicNativeWorkbookParityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pairs = {}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                years.NATIVE_EIC_STATUSES,
                {YEAR: ("single", "married_filing_jointly")}):
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for status, excluded in EXCLUDED.items():
                for kind, build in eic_battery.battery_for(
                        YEAR, status).items():
                    if kind in excluded:
                        continue
                    scenario = build(YEAR)
                    native = orch.compute_federal(scenario)
                    eff, _ = orch._build_effective_scenario(scenario)
                    with eic_answers_adapter(orch):
                        workbook = orch._compute_1040_via_workbook(eff)
                    cls.pairs[(status, kind)] = (native, workbook)

    def test_the_compared_rows(self):
        expected = {(s, k) for s, excluded in EXCLUDED.items()
                    for k in eic_battery.battery_for(YEAR, s)
                    if k not in excluded}
        self.assertEqual(set(self.pairs), expected)

    def test_every_row_is_fully_answered(self):
        for (status, kind), (_, workbook) in sorted(self.pairs.items()):
            for prompt in _PROMPTS:
                with self.subTest(status=status, kind=kind, cell=prompt):
                    self.assertFalse(
                        str(workbook.get(prompt) or "").startswith("Please"),
                        workbook.get(prompt))

    def test_line_27_32_33_agree_to_the_penny(self):
        for (status, kind), (native, workbook) in sorted(self.pairs.items()):
            if (status, kind) in DIVERGENCES:
                continue
            for key in _KEYS:
                with self.subTest(status=status, kind=kind, key=key):
                    self.assertEqual(_n(native.get(key)),
                                     _n(workbook.get(key)))

    def test_each_adjudicated_divergence_holds_on_both_sides(self):
        self.assertLessEqual(set(DIVERGENCES), set(self.pairs))
        for (status, kind), expected in sorted(DIVERGENCES.items()):
            native, workbook = self.pairs[(status, kind)]
            for key in _KEYS:
                with self.subTest(status=status, kind=kind, key=key):
                    self.assertEqual((_n(native.get(key)),
                                      _n(workbook.get(key))), expected)
