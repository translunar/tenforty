"""Childless-EIC parity: native vs the workbook (oracle tier; spec §10.4).

For each (2025, status) battery row, the native result and the workbook's —
computed through the oracle-only answer adapter, which writes every EIC
answer from the scenario's facts (tests/eic_oracle_adapter.py) — agree to
the penny on line 27 (`eic`), line 32 and line 33. A row counts as evidence
only when the workbook's own state confirms it (spec §10.3 item 2; ruling
R-S7-9a): a CREDITED row raises no "Please answer" prompt and is not denied
(NoEICredit, A1, FALSE); a DENIED row positively reaches the workbook STOP
for the same rule native cites (DENIAL_STOPS) with NoEICredit TRUE. The
sheet's Step 5 prompt (AP1) is not gated on NoEICredit, so it fires on
every row stopped earlier — denied rows are exempt from AP1 only, never
from the stop. The health constants are pinned on the fast tier
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
REFUSED DIVERGENCES (R-S7-10/10a) are rows where the workbook contradicts
itself — NoEICredit TRUE yet line 27 positive — so production refuses
(workbook_eic_inconsistent); each asserts native's 0, the exact refusal,
and the line 27 the sheet computed, read from the refusal's harvest. NO
other row may refuse: a credited row refusing means the NoEICredit harvest
is not an exact bool (R-S7-10a) — STOP and enumerate.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator, WorkbookEicInconsistent
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

# Rulings R-S7-10/10a: (status, kind) -> the line 27 the sheet computed
# despite declaring no credit (the oracle on ec4ea3d: 155 on both rows).
REFUSED_DIVERGENCES = {
    ("single", "investment_over_limit"): 155,
    ("married_filing_jointly", "investment_over_limit"): 155,
}
REFUSAL = "workbook_eic_inconsistent: "

# Ruling R-S7-9a: kind -> (stop output, its reached value, native's rule).
# Stop outputs are read back by the adapter (EIC_WORKBOOK_CELLS "stops").
DENIAL_STOPS = {
    "over_ceiling": ("eic_stop_agi_limit", True, "Step 1, question 1"),
    "fact_ssn_not_valid": ("eic_stop_ssn", True, "Step 1, question 2"),
    "investment_over_limit": ("eic_stop_form_4797_no", "X",
                              "Step 2, question 2"),
    "age_lower_bound_out": ("eic_stop_age", True, "Step 4, question 2"),
    "fact_main_home_not_in_us": ("eic_stop_main_home", True,
                                 "Step 4, question 3"),
    "fact_qualifying_child_of_another": ("eic_stop_qc_of_another", True,
                                         "Step 4, question 5"),
    "fact_claimable_as_dependent": ("eic_stop_dependent", True,
                                    "Step 4, question 6"),
    "just_under_ceiling": ("eic_stop_credit_zero", True,
                           "Worksheet A, credit line"),
    "earned_income_below_min": ("eic_stop_credit_zero", True,
                                "Worksheet A, earned income"),
}

# Ruling R-S7-9a, adjudicated observation (static prediction; the oracle run
# after d9dec1f is its first LibreOffice confirmation — a contradiction is a
# finding, STOP and enumerate): Step 4 Q6's "Yes. STOP" (A226) is in
# neither NoEICredit's OR-chain (A1) nor N1, so the workbook stops the flow
# (credit 0) without declaring the denial. Same species as R-S7-7 (a STOP
# missing from the OR-chain); harmless in dollars; production is
# guard-protected (an unfavorable fact refuses on the workbook path, R-S7-2).
UNDECLARED_DENIALS = {("single", "fact_claimable_as_dependent")}


def _n(value) -> int:
    return int(round(value or 0))


@needs_libreoffice
class EicNativeWorkbookParityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pairs, cls.refusals = {}, {}
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
                        try:
                            workbook = orch._compute_1040_via_workbook(eff)
                        except WorkbookEicInconsistent as refusal:
                            # The refused compute's harvest: R-S7-9a's
                            # display pins read it through production.
                            workbook = refusal.harvested
                            cls.refusals[(status, kind)] = str(refusal)
                    cls.pairs[(status, kind)] = (native, workbook)

    def test_the_compared_rows(self):
        expected = {(s, k) for s, excluded in EXCLUDED.items()
                    for k in eic_battery.battery_for(YEAR, s)
                    if k not in excluded}
        self.assertEqual(set(self.pairs), expected)

    def _denied(self, status, kind):
        native, workbook = self.pairs[(status, kind)]
        expected = DIVERGENCES.get((status, kind),
                                   (None, _n(native.get("eic"))))[1]
        return expected == 0

    def _prompt_free(self, status, kind, workbook, prompts):
        for prompt in prompts:
            with self.subTest(status=status, kind=kind, cell=prompt):
                self.assertFalse(
                    str(workbook.get(prompt) or "").startswith("Please"),
                    workbook.get(prompt))

    def test_every_denied_row_has_its_stop(self):
        denied = {k for (s, k) in self.pairs if self._denied(s, k)}
        self.assertLessEqual(denied, set(DENIAL_STOPS))
        self.assertLessEqual(UNDECLARED_DENIALS, {
            (s, k) for (s, k) in self.pairs if self._denied(s, k)})

    def test_credited_rows_are_fully_answered_and_not_denied(self):
        for (status, kind), (_, workbook) in sorted(self.pairs.items()):
            if self._denied(status, kind):
                continue
            self._prompt_free(status, kind, workbook, _PROMPTS)
            with self.subTest(status=status, kind=kind, cell="A1"):
                self.assertEqual(workbook.get("eic_diag_no_credit"), False)

    def test_denied_rows_stop_where_native_stops(self):
        for (status, kind), (native, workbook) in sorted(self.pairs.items()):
            if not self._denied(status, kind):
                continue
            stop, reached, rule = DENIAL_STOPS[kind]
            with self.subTest(status=status, kind=kind, check="native"):
                self.assertEqual(native["eic_determination"]["rule"], rule)
            with self.subTest(status=status, kind=kind, check=stop):
                self.assertEqual(workbook.get(stop), reached)
            with self.subTest(status=status, kind=kind, cell="A1"):
                self.assertEqual(workbook.get("eic_diag_no_credit"),
                                 (status, kind) not in UNDECLARED_DENIALS)
            self._prompt_free(status, kind, workbook, _PROMPTS[:2])

    def test_only_the_adjudicated_rows_refuse(self):
        self.assertEqual(sorted(self.refusals), sorted(REFUSED_DIVERGENCES))

    def test_each_refused_divergence_holds_on_both_sides(self):
        for (status, kind), line_27 in sorted(REFUSED_DIVERGENCES.items()):
            native, harvested = self.pairs[(status, kind)]
            with self.subTest(status=status, kind=kind, side="native"):
                self.assertEqual(_n(native.get("eic")), 0)
            with self.subTest(status=status, kind=kind, side="refusal"):
                self.assertTrue(self.refusals.get((status, kind), "")
                                .startswith(REFUSAL),
                                self.refusals.get((status, kind)))
            with self.subTest(status=status, kind=kind, side="line_27"):
                self.assertEqual(_n(harvested.get("eic")), line_27)

    def test_line_27_32_33_agree_to_the_penny(self):
        for (status, kind), (native, workbook) in sorted(self.pairs.items()):
            if (status, kind) in DIVERGENCES or (
                    status, kind) in REFUSED_DIVERGENCES:
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
