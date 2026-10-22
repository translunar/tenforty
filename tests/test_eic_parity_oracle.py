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
  * age-bound rows — awaiting the team-lead ruling on the Jan-1 upper-bound
    reading (the workbook's integer age vs the IRS birth-date range);
  * rows that refuse natively (no native value to compare);
  * Schedule C rows (Worksheet B) — the workbook path refuses Schedule C
    outright (orchestrator: "cannot carry Schedule C / Schedule SE"), so the
    oracle has no evidence to offer; they stay native-unit-tested.
2025 MFJ is compared ahead of its EIC-grid declaration (parity first).
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
    "single": {"age_lower_bound_in", "age_lower_bound_out",
               "age_upper_bound_in", "age_upper_bound_out",
               "sch_c_worksheet_b", "sch_c_net_loss"},
    "married_filing_jointly": {"age_lower_bound_in", "age_lower_bound_out",
                               "age_upper_bound_in", "age_upper_bound_out",
                               "sch_c_worksheet_b", "sch_c_net_loss",
                               "fact_nonresident_alien"},
}
_PROMPTS = ("eic_diag_prompt_an", "eic_diag_prompt_ao", "eic_diag_prompt_ap")


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
            for key in ("eic", "total_other_payments", "total_payments"):
                with self.subTest(status=status, kind=kind, key=key):
                    self.assertEqual(_n(native.get(key)),
                                     _n(workbook.get(key)))
