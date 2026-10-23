"""The CalEITC fail-closed refusal (spec §12.11; rulings R-S8-12, R-S8-13,
R-S8-14, R-S8-15). tenforty does not compute Form 540 lines 75 (CalEITC) or
76 (YCTC); a CA return that could claim either refuses, naming FTB 3514,
rather than file with a credit silently omitted.

Earned income for the gate: the W-2 wage term — the LESSER of total W-2
wages and the CA box-16 wages, the CA reading counted only when at least one
W-2 is attributed to CA (R-S8-14, B2) — plus net Schedule C / partnership SE
earnings (losses reduce). Refuse when 0 < earned <= the year's
caleitc_max_earned_income (inclusive); earned <= 0 refuses only with a
dependent (the YCTC proxy). These per-year boundary pairs are the exerciser
record for caleitc_max_earned_income (R-S8-15). All identities synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.models import ScheduleCBusiness, W2
from tenforty.orchestrator import ReturnOrchestrator, refuse_caleitc_not_modeled
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

PREFIX = "caleitc_not_modeled: "
# R-S8-15: each year's boundary, written out from the FTB 3514 instructions
# ("must be less than $X+1"), so the param is load-bearing: a moved param
# fails the pair rather than moving with it.
BOUNDARY = {2021: 30_000, 2022: 30_000, 2023: 30_950, 2024: 31_950,
            2025: 32_900}


def _w2(wages, *, state=None, state_wages=0.0):
    return W2(employer="Synthetic Employer CA", wages=wages,
              federal_tax_withheld=0.0, ss_wages=wages,
              ss_tax_withheld=round(wages * 0.062, 2), medicare_wages=wages,
              medicare_tax_withheld=round(wages * 0.0145, 2),
              state_wages=state_wages, state=state)


def _ca(year=2024, w2s=(), dependents=(), schedule_c=()):
    base = make_simple_scenario()
    return dataclasses.replace(
        base,
        config=dataclasses.replace(base.config, year=year,
                                   dependents=list(dependents)),
        w2s=list(w2s), schedule_c_businesses=list(schedule_c))


class CalEitcRefusalTests(unittest.TestCase):

    def _refuses(self, scenario):
        with self.assertRaises(NotImplementedError) as ctx:
            refuse_caleitc_not_modeled(scenario)
        self.assertTrue(str(ctx.exception).startswith(PREFIX))
        return str(ctx.exception)

    def test_the_message_names_ftb_3514_and_lines_75_76(self):
        message = self._refuses(_ca(w2s=[_w2(20_000.0)]))
        for words in ("FTB 3514", "line 75", "line 76"):
            with self.subTest(words=words):
                self.assertIn(words, message)

    def test_low_wages_with_no_state_attribution_refuse(self):
        # The fail-open B1 case (R-S8-14): childless, $20k, no box 16.
        self._refuses(_ca(w2s=[_w2(20_000.0)]))

    def test_the_lesser_ca_reading_counts_when_attributed(self):
        self._refuses(_ca(w2s=[_w2(40_000.0, state="CA",
                                   state_wages=20_000.0)]))
        refuse_caleitc_not_modeled(_ca(w2s=[_w2(40_000.0, state="CA",
                                                state_wages=40_000.0)]))

    def test_an_attributed_zero_box_16_reads_zero(self):
        # Genuine data: CA-attributed with $0 CA wages is earned 0.
        refuse_caleitc_not_modeled(_ca(w2s=[_w2(40_000.0, state="CA")]))
        self._refuses(_ca(w2s=[_w2(40_000.0, state="CA")],
                          dependents=["Child A"]))

    def test_without_attribution_total_wages_govern(self):
        refuse_caleitc_not_modeled(_ca(w2s=[_w2(40_000.0)]))

    def test_a_schedule_c_loss_reduces_earned_income(self):
        loss = ScheduleCBusiness(description="Example Route",
                                 gross_receipts=0.0, supplies=10_000.0)
        refuse_caleitc_not_modeled(_ca(w2s=[_w2(40_000.0)]))
        self._refuses(_ca(w2s=[_w2(40_000.0)], schedule_c=[loss]))

    def test_zero_earned_income_refuses_only_with_a_dependent(self):
        refuse_caleitc_not_modeled(_ca())
        self._refuses(_ca(dependents=["Child A"]))

    def test_each_years_ceiling_is_inclusive(self):
        # R-S8-15: the boundary pair per year — the param is load-bearing.
        for year, ceiling in sorted(BOUNDARY.items()):
            with self.subTest(year=year, side="at the ceiling"):
                self._refuses(_ca(year, w2s=[_w2(float(ceiling))]))
            with self.subTest(year=year, side="one dollar over"):
                refuse_caleitc_not_modeled(
                    _ca(year, w2s=[_w2(float(ceiling + 1))]))


class CaComputeRunsTheGateFirstTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                       work_dir=Path(tmp.name))

    def test_a_refused_return_never_reaches_schedule_ca(self):
        stop = mock.Mock(side_effect=AssertionError("Schedule CA reached"))
        with mock.patch("tenforty.orchestrator.form_sch_ca.compute", stop), \
                self.assertRaises(NotImplementedError) as ctx:
            self.orch._compute_ca_results(_ca(w2s=[_w2(20_000.0)]), None, {})
        self.assertTrue(str(ctx.exception).startswith(PREFIX))
        stop.assert_not_called()

    def test_a_return_above_the_ceiling_proceeds(self):
        class Stop(Exception):
            pass
        with mock.patch("tenforty.orchestrator.form_sch_ca.compute",
                        side_effect=Stop), self.assertRaises(Stop):
            self.orch._compute_ca_results(_ca(w2s=[_w2(40_000.0)]), None, {})
