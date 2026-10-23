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

# Years compared, and the subset compared AHEAD of its EIC-grid row (spec
# §12: parity, then the grid row). Native is forced for those years only;
# GridStateTests pins that they are undeclared and every other year is, so a
# reverted grid row cannot hide behind a force-native patch (R-S7-13).
YEARS = (2023, 2024, 2025)
AHEAD_OF_GRID: frozenset[int] = frozenset()
STATUSES = ("single", "married_filing_jointly")
_EXCLUDED_KINDS = {
    "single": {"sch_c_worksheet_b", "sch_c_net_loss"},
    "married_filing_jointly": {"sch_c_worksheet_b", "sch_c_net_loss",
                               "fact_nonresident_alien"},
}
# Year-scoped exclusions: the 2025 upper-age rows refuse natively (the
# Schedule 1-A seniors refusal, P5-1), so there is no native value.
_EXCLUDED_IN_YEAR = {2025: {"age_upper_bound_in", "age_upper_bound_out"}}
_PROMPTS = ("eic_diag_prompt_an", "eic_diag_prompt_ao", "eic_diag_prompt_ap")
_KEYS = ("eic", "total_other_payments", "total_payments")


class _Nonzero:
    """A workbook figure declared before its first comparison: asserted
    nonzero now, pinned exactly once the oracle has shown it (R-S7-14)."""

    def __repr__(self):
        return "NONZERO (pinned post-first-comparison)"


NONZERO = _Nonzero()

# (year, status, kind) -> (native, workbook) on every key in _KEYS:
# adjudicated workbook-wrong.
DIVERGENCES = {
    # R-S7-7: Step 1 Q4's "Yes" branch (B39) only says "See Non-resident
    # aliens, later"; B39 is absent from NoEICredit's OR-chain
    # (A1 '=OR(N1,H21<>"",H28<>"",B34<>"",H65<>"",B157<>"",H294<>"",
    # L316=0,EarnedIncomeWSB<=0,O458<=0)'), so a single NRA keeps the credit.
    (2025, "single", "fact_nonresident_alien"): (0, 649),
    # R-S7-8: the workbook's EIC Table is rebuilt from derived slopes
    # (N7 '=ROUND(N3/N4,4)', N9 '=-ROUND(N3/(N6-N5),7)' = -0.0764969, not
    # the statutory 7.65%), so its 14,850-14,900 bin reads 324 where the
    # published table (assets/eic_tables/2025.csv) reads 323: $1 high here.
    (2025, "single", "phase_out"): (323, 324),
    (2025, "single", "agi_over_earned"): (323, 324),
    # R-S7-7, 2024: the same B39 gap. Workbook figure pinned after the first
    # comparison (0e34ac9, R-S8-5): the table credit at the row's earned
    # income, as for its identical-input sibling `plateau` (632, penny-equal
    # on that run) — B39 has no dollar path in the 2024 sheet.
    (2024, "single", "fact_nonresident_alien"): (0, 632),
    # R-T2 / R-S7-1 (R-S8-3 placement): born Jan 1 of (year-64) is under 65
    # at year end (Pub. 596's asymmetric age-65 rule), so native grants; the
    # workbook's symmetric day-before age denies. Native predicted PRE-RUN
    # from the ingested published table (assets/eic_tables/2024.csv) at the
    # row's wages; workbook 0.
    (2024, "single", "age_upper_bound_in"): (43, 0),
    (2024, "married_filing_jointly", "age_upper_bound_in"): (18, 0),
    # 2023 (R-S8-8): the same B39 gap — workbook figure pinned after the
    # first comparison (9009897): the table credit at the row's earned
    # income, as for its identical-input sibling `plateau` (600, penny-equal
    # on that run). The R-T2 Jan-1 rows: native from the ingested published
    # table at the row's wages (the MFJ row: one aged spouse, option α),
    # workbook 0.
    (2023, "single", "fact_nonresident_alien"): (0, 600),
    (2023, "single", "age_upper_bound_in"): (5, 0),
    (2023, "married_filing_jointly", "age_upper_bound_in"): (160, 0),
}

# Rulings R-S7-10/10a: (year, status, kind) -> the line 27 the sheet
# computed despite declaring no credit (the oracle on ec4ea3d: 155).
REFUSED_DIVERGENCES = {
    (2025, "single", "investment_over_limit"): 155,
    (2025, "married_filing_jointly", "investment_over_limit"): 155,
    # 2024: the same display-only Step 2 stop (all years). Pinned after the
    # first comparison (0e34ac9, R-S8-5): Worksheet A's credit at the row's
    # earned income and AGI, the same table bins as its sibling
    # `investment_at_limit` (155, penny-equal on that run).
    (2024, "single", "investment_over_limit"): 155,
    (2024, "married_filing_jointly", "investment_over_limit"): 155,
    # 2023: the same display-only stop; armed via H64 in 2023's A1. Pinned
    # after the first comparison (9009897): Worksheet A at the row's earned
    # income and AGI, the same bins as `investment_at_limit` (155,
    # penny-equal on that run).
    (2023, "single", "investment_over_limit"): 155,
    (2023, "married_filing_jointly", "investment_over_limit"): 155,
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
    # Upper bound: "out" is denied on both sides; "in" is the R-T2
    # divergence, denied on the workbook side only (its native rule check is
    # skipped there; the divergence asserts native exactly).
    "age_upper_bound_out": ("eic_stop_age", True, "Step 4, question 2"),
    "age_upper_bound_in": ("eic_stop_age", True, "Step 4, question 2"),
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
# Per-year overrides. 2024 (R-S8-2 (a)): G28 is dead in that template, so
# the SSN row's stop is EIC_trigger (M34) read back FALSE — the flow stops at
# Step 1 Q2, the rule native cites.
DENIAL_STOPS_IN_YEAR = {
    2024: {"fact_ssn_not_valid": ("eic_stop_ssn", False,
                                  "Step 1, question 2")},
    # 2023: G27 is dead the same way (R-S8-8 3b); EIC_trigger is M33.
    2023: {"fact_ssn_not_valid": ("eic_stop_ssn", False,
                                  "Step 1, question 2")},
}

# Ruling R-S7-9a, adjudicated observation: Step 4 Q6's "Yes. STOP" (2025
# A226) is in neither NoEICredit's OR-chain (A1) nor N1, so the workbook
# stops the flow (credit 0) without declaring the denial. Same species as
# R-S7-7 (a STOP missing from the OR-chain); harmless in dollars; production
# is guard-protected (an unfavorable fact refuses on the workbook path,
# R-S7-2). Confirmed by the oracle on 59653a6.
# 2024: the same gap by static read (Q6 "Yes. STOP" A213 is in neither A1
# nor N1) — a first-comparison prediction; a contradiction is a finding.
UNDECLARED_DENIALS = {(2025, "single", "fact_claimable_as_dependent"),
                      (2024, "single", "fact_claimable_as_dependent")}
# 2023 (catalog #7, R-S8-8 3d): 2023's A1 has no N1 term, so EVERY Step 4
# stop is outside the verdict — static predictions, first comparison.
UNDECLARED_DENIALS |= {
    (2023, status, kind)
    for status in ("single", "married_filing_jointly")
    for kind in ("age_lower_bound_out", "age_upper_bound_out",
                 "age_upper_bound_in", "fact_main_home_not_in_us")
} | {(2023, "single", "fact_qualifying_child_of_another"),
     (2023, "single", "fact_claimable_as_dependent")}


def _n(value) -> int:
    return int(round(value or 0))


def _expected_rows():
    return {(y, s, k) for y in YEARS for s in STATUSES
            for k in eic_battery.battery_for(y, s)
            if k not in _EXCLUDED_KINDS[s]
            and k not in _EXCLUDED_IN_YEAR.get(y, ())}


def _stop(year, kind):
    return DENIAL_STOPS_IN_YEAR.get(year, {}).get(kind, DENIAL_STOPS[kind])


class GridStateTests(unittest.TestCase):
    """The force-native scope is exactly the years compared ahead of their
    grid row (fast tier: no LibreOffice)."""

    def test_only_years_ahead_of_the_grid_are_undeclared(self):
        for year in YEARS:
            for status in STATUSES:
                with self.subTest(year=year, status=status):
                    self.assertEqual(
                        years.native_eic_supports(year, status),
                        year not in AHEAD_OF_GRID)


@needs_libreoffice
class EicNativeWorkbookParityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pairs, cls.refusals = {}, {}
        ahead = {y: STATUSES for y in AHEAD_OF_GRID}
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for year, status, kind in sorted(_expected_rows()):
                scenario = eic_battery.battery_for(year, status)[kind](year)
                with mock.patch.dict(years.NATIVE_EIC_STATUSES, ahead):
                    native = orch.compute_federal(scenario)
                eff, _ = orch._build_effective_scenario(scenario)
                with eic_answers_adapter(orch):
                    try:
                        workbook = orch._compute_1040_via_workbook(eff)
                    except WorkbookEicInconsistent as refusal:
                        # The refused compute's harvest: R-S7-9a's display
                        # pins read it through production.
                        workbook = refusal.harvested
                        cls.refusals[(year, status, kind)] = str(refusal)
                cls.pairs[(year, status, kind)] = (native, workbook)

    def test_the_compared_rows(self):
        self.assertEqual(set(self.pairs), _expected_rows())

    def _denied(self, row):
        native, _ = self.pairs[row]
        expected = DIVERGENCES.get(row, (None, _n(native.get("eic"))))[1]
        return expected == 0

    def _prompt_free(self, row, workbook, prompts):
        year, status, kind = row
        for prompt in prompts:
            with self.subTest(year=year, status=status, kind=kind,
                              cell=prompt):
                self.assertFalse(
                    str(workbook.get(prompt) or "").startswith("Please"),
                    workbook.get(prompt))

    def test_every_denied_row_has_its_stop(self):
        denied = {row for row in self.pairs if self._denied(row)}
        self.assertLessEqual({k for (_, _, k) in denied}, set(DENIAL_STOPS))
        self.assertLessEqual(UNDECLARED_DENIALS, denied)

    def test_credited_rows_are_fully_answered_and_not_denied(self):
        for row, (_, workbook) in sorted(self.pairs.items()):
            if self._denied(row):
                continue
            self._prompt_free(row, workbook, _PROMPTS)
            year, status, kind = row
            with self.subTest(year=year, status=status, kind=kind, cell="A1"):
                self.assertEqual(workbook.get("eic_diag_no_credit"), False)

    def test_denied_rows_stop_where_native_stops(self):
        for row, (native, workbook) in sorted(self.pairs.items()):
            if not self._denied(row):
                continue
            year, status, kind = row
            stop, reached, rule = _stop(year, kind)
            if row not in DIVERGENCES:
                # A divergence row's native side is asserted exactly there
                # (the workbook denies where native credits).
                with self.subTest(year=year, status=status, kind=kind,
                                  check="native"):
                    self.assertEqual(native["eic_determination"]["rule"],
                                     rule)
            with self.subTest(year=year, status=status, kind=kind,
                              check=stop):
                self.assertEqual(workbook.get(stop), reached)
            with self.subTest(year=year, status=status, kind=kind, cell="A1"):
                self.assertEqual(workbook.get("eic_diag_no_credit"),
                                 row not in UNDECLARED_DENIALS)
            self._prompt_free(row, workbook, _PROMPTS[:2])

    def test_only_the_adjudicated_rows_refuse(self):
        self.assertEqual(sorted(self.refusals), sorted(REFUSED_DIVERGENCES))

    def test_each_refused_divergence_holds_on_both_sides(self):
        for row, line_27 in sorted(REFUSED_DIVERGENCES.items()):
            year, status, kind = row
            native, harvested = self.pairs[row]
            with self.subTest(year=year, status=status, kind=kind,
                              side="native"):
                self.assertEqual(_n(native.get("eic")), 0)
            with self.subTest(year=year, status=status, kind=kind,
                              side="refusal"):
                self.assertTrue(self.refusals.get(row, "").startswith(REFUSAL),
                                self.refusals.get(row))
            with self.subTest(year=year, status=status, kind=kind,
                              side="line_27"):
                if line_27 is NONZERO:
                    self.assertGreater(_n(harvested.get("eic")), 0)
                else:
                    self.assertEqual(_n(harvested.get("eic")), line_27)

    def test_each_adjudicated_divergence_holds_on_both_sides(self):
        self.assertLessEqual(set(DIVERGENCES), set(self.pairs))
        for row, (native_value, workbook_value) in sorted(
                DIVERGENCES.items()):
            year, status, kind = row
            native, workbook = self.pairs[row]
            for key in _KEYS:
                with self.subTest(year=year, status=status, kind=kind,
                                  key=key):
                    self.assertEqual(_n(native.get(key)), native_value)
                    if workbook_value is NONZERO:
                        self.assertGreater(_n(workbook.get(key)), 0)
                    else:
                        self.assertEqual(_n(workbook.get(key)),
                                         workbook_value)

    def test_line_27_32_33_agree_to_the_penny(self):
        for row, (native, workbook) in sorted(self.pairs.items()):
            if row in DIVERGENCES or row in REFUSED_DIVERGENCES:
                continue
            year, status, kind = row
            for key in _KEYS:
                with self.subTest(year=year, status=status, kind=kind,
                                  key=key):
                    self.assertEqual(_n(native.get(key)),
                                     _n(workbook.get(key)))
