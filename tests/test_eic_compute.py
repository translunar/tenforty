"""tenforty/forms/eic.py — the childless earned income credit (line 27a).

Every expected credit is read from the published EIC Table asset or the
attested params, never typed in: the table is the method, and these tests
drive each params field at its boundary (the coverage map's waiver reason
points here until the parity rows land). All identities synthetic.
"""
import dataclasses
import datetime
import unittest

from tenforty.eic_table import eic_from_table
from tenforty.forms.eic import compute_eic, meets_age_test
from tenforty.models import (
    FilingStatus,
    Form1099INT,
    Scenario,
    ScheduleCBusiness,
)
from tenforty.params.federal import load as load_params
from tests.fixtures.spine_battery import _battery_config

YEAR = 2025
P = load_params(YEAR)
SINGLE, MFJ = FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY


def _scenario(status=SINGLE, **config):
    base = _battery_config(YEAR, status)
    return Scenario(config=dataclasses.replace(base, **config))


def _eic(earned, agi=None, status=SINGLE, scenario=None, sched=None,
         **spine):
    scenario = scenario or _scenario(status)
    spine = {"wages": earned, "agi": earned if agi is None else agi,
             "taxable_interest": 0, "ordinary_dividends": 0,
             "capital_gain_loss": None, **spine}
    return compute_eic(scenario, spine, P, sched or {})


def _key(status):
    return status.value


class CreditCurveTests(unittest.TestCase):

    def test_plateau_is_the_max_credit(self):
        for status in (SINGLE, MFJ):
            with self.subTest(status=status):
                out = _eic(P.eic_earned_income_amount + 100, status=status)
                self.assertEqual(out["eic"], P.eic_max_credit)
                self.assertEqual(out["eic"], eic_from_table(
                    P.eic_earned_income_amount + 100, YEAR, status))
                self.assertTrue(out["eic_determination"]["eligible"])

    def test_phase_in_is_below_the_max(self):
        earned = P.eic_earned_income_amount // 2
        out = _eic(earned)
        self.assertEqual(out["eic"], eic_from_table(earned, YEAR, SINGLE))
        self.assertLess(0, out["eic"])
        self.assertLess(out["eic"], P.eic_max_credit)

    def test_phase_out_is_partial(self):
        for status in (SINGLE, MFJ):
            with self.subTest(status=status):
                key = _key(status)
                earned = (P.eic_phaseout_threshold[key]
                          + P.eic_completed_phaseout[key]) // 2
                out = _eic(earned, status=status)
                self.assertEqual(out["eic"],
                                 eic_from_table(earned, YEAR, status))
                self.assertLess(0, out["eic"])
                self.assertLess(out["eic"], P.eic_max_credit)

    def test_just_under_the_ceiling_reads_the_table(self):
        for status in (SINGLE, MFJ):
            with self.subTest(status=status):
                earned = P.eic_completed_phaseout[_key(status)] - 1
                self.assertEqual(_eic(earned, status=status)["eic"],
                                 eic_from_table(earned, YEAR, status))

    def test_agi_at_the_ceiling_stops_at_step_1(self):
        for status in (SINGLE, MFJ):
            with self.subTest(status=status):
                ceiling = P.eic_completed_phaseout[_key(status)]
                out = _eic(1000, agi=ceiling, status=status)
                self.assertEqual(out["eic"], 0)
                self.assertEqual(out["eic_determination"]["reason"],
                                 "agi_at_or_over_limit")
                # One under: Step 1 passes and the table decides (the last
                # dollars below the ceiling can read $0 off a footnoted bin).
                under = _eic(1000, agi=ceiling - 1, status=status)
                self.assertNotEqual(under["eic_determination"]["reason"],
                                    "agi_at_or_over_limit")
                self.assertEqual(under["eic"], min(
                    eic_from_table(1000, YEAR, status),
                    eic_from_table(ceiling - 1, YEAR, status)))

    def test_earned_income_at_the_ceiling_stops_at_step_5(self):
        for status in (SINGLE, MFJ):
            with self.subTest(status=status):
                ceiling = P.eic_completed_phaseout[_key(status)]
                out = _eic(ceiling, agi=1000, status=status)
                self.assertEqual(out["eic"], 0)
                self.assertEqual(out["eic_determination"]["reason"],
                                 "earned_income_at_or_over_limit")

    def test_high_income_needs_no_birthdate(self):
        # Step 1 stops before the age test reads a birth date.
        scenario = _scenario(birthdate="")
        out = _eic(P.eic_completed_phaseout["single"] + 50_000,
                   scenario=scenario)
        self.assertEqual(out["eic_determination"]["reason"],
                         "agi_at_or_over_limit")

    def test_ceiling_agrees_with_the_routing_gate_param(self):
        # spec §5.2: the MFJ completed phaseout is the existing MFJ-column
        # ceiling the routing gate already reads.
        self.assertEqual(P.eic_completed_phaseout["married_filing_jointly"],
                         P.eic_income_ceiling[0])

    def test_no_earned_income(self):
        for earned in (0, P.eic_min_earned_income - 1):
            with self.subTest(earned=earned):
                out = _eic(earned)
                self.assertEqual(out["eic"], 0)
                self.assertEqual(out["eic_determination"]["reason"],
                                 "no_earned_income")
        self.assertGreater(_eic(P.eic_min_earned_income)["eic"], 0)


class AgiBranchTests(unittest.TestCase):

    def test_agi_in_the_phase_out_takes_the_smaller_credit(self):
        earned = P.eic_earned_income_amount + 100
        agi = (P.eic_phaseout_threshold["single"]
               + P.eic_completed_phaseout["single"]) // 2
        out = _eic(earned, agi=agi)
        self.assertEqual(out["eic_table_agi"],
                         eic_from_table(agi, YEAR, SINGLE))
        self.assertEqual(out["eic"], out["eic_table_agi"])
        self.assertLess(out["eic"], out["eic_table_earned"])

    def test_agi_below_the_phaseout_threshold_is_not_looked_up(self):
        earned = P.eic_earned_income_amount + 100
        out = _eic(earned, agi=P.eic_phaseout_threshold["single"] - 1)
        self.assertIsNone(out["eic_table_agi"])
        self.assertEqual(out["eic"], P.eic_max_credit)

    def test_agi_at_the_threshold_is_looked_up(self):
        earned = P.eic_earned_income_amount + 100
        out = _eic(earned, agi=P.eic_phaseout_threshold["single"])
        self.assertIsNotNone(out["eic_table_agi"])


class InvestmentIncomeTests(unittest.TestCase):

    def test_at_the_limit_is_allowed_one_over_is_not(self):
        earned = P.eic_earned_income_amount + 100
        at = _eic(earned, taxable_interest=P.eic_investment_income_limit)
        self.assertEqual(at["eic_investment_income"],
                         P.eic_investment_income_limit)
        self.assertGreater(at["eic"], 0)
        over = _eic(earned,
                    taxable_interest=P.eic_investment_income_limit + 1)
        self.assertEqual(over["eic"], 0)
        self.assertEqual(over["eic_determination"]["reason"],
                         "investment_income_over_limit")

    def test_lines_2a_2b_3b_and_positive_7a_are_summed(self):
        scenario = dataclasses.replace(_scenario(), form1099_int=[
            Form1099INT(payer="Example Bank", interest=0.0,
                        tax_exempt_interest=10.0)])
        out = _eic(5000, scenario=scenario, taxable_interest=20,
                   ordinary_dividends=30, capital_gain_loss=40)
        self.assertEqual(out["eic_investment_income"], 100)
        loss = _eic(5000, scenario=scenario, taxable_interest=20,
                    ordinary_dividends=30, capital_gain_loss=-3000)
        self.assertEqual(loss["eic_investment_income"], 60)


class AgeTests(unittest.TestCase):
    """The born-before/after formulation, each bound from both sides."""

    MIN_CUTOFF = datetime.date(YEAR - P.eic_min_age + 1, 1, 2)
    MAX_CUTOFF = datetime.date(YEAR - P.eic_max_age, 12, 31)

    def _meets(self, born, status=SINGLE, spouse=None):
        extra = {"spouse_birthdate": spouse} if spouse else {}
        config = dataclasses.replace(_battery_config(YEAR, status),
                                     birthdate=born, **extra)
        return meets_age_test(config, YEAR, P)

    def _iso(self, d, days=0):
        return (d + datetime.timedelta(days=days)).isoformat()

    def test_lower_bound(self):
        self.assertTrue(self._meets(self._iso(self.MIN_CUTOFF, -1)))
        self.assertFalse(self._meets(self._iso(self.MIN_CUTOFF)))

    def test_upper_bound(self):
        self.assertFalse(self._meets(self._iso(self.MAX_CUTOFF)))
        self.assertTrue(self._meets(self._iso(self.MAX_CUTOFF, 1)))

    def test_mfj_either_spouse(self):
        young, inband = self._iso(self.MIN_CUTOFF), self._iso(
            self.MIN_CUTOFF, -1)
        self.assertTrue(self._meets(young, MFJ, spouse=inband))
        self.assertTrue(self._meets(inband, MFJ, spouse=young))
        self.assertFalse(self._meets(young, MFJ, spouse=young))

    def test_failing_the_age_test_zeroes_the_credit(self):
        scenario = _scenario(birthdate=self._iso(self.MIN_CUTOFF))
        out = _eic(P.eic_earned_income_amount, scenario=scenario)
        self.assertEqual(out["eic"], 0)
        self.assertEqual(out["eic_determination"]["reason"],
                         "age_test_not_met")


class WorksheetBTests(unittest.TestCase):

    def _scn(self):
        return dataclasses.replace(_scenario(), schedule_c_businesses=[
            ScheduleCBusiness(description="Example Business")])

    def test_filing_schedule_se_uses_line_3_less_line_13(self):
        sched = {"sch_se": {"sch_se_line_3_net_profit": 6000,
                            "sch_se_line_4c_net_earnings": 5541,
                            "sch_se_line_13_half_deduction": 424}}
        out = _eic(1000, scenario=self._scn(), sched=sched)
        self.assertEqual(out["eic_worksheet"], "B")
        self.assertEqual(out["eic_earned_income"], 1000 + 6000 - 424)

    def test_a_net_loss_reduces_earned_income(self):
        sched = {"sch_se": {}, "sch_c": {
            "sch_c_line_31_net_profit_total": -500}}
        out = _eic(3000, scenario=self._scn(), sched=sched)
        self.assertEqual(out["eic_earned_income"], 2500)

    def test_below_the_se_threshold_is_part_2(self):
        sched = {"sch_se": {"sch_se_line_3_net_profit": 300,
                            "sch_se_line_4c_net_earnings": 277,
                            "sch_se_line_13_half_deduction": 0},
                 "sch_c": {"sch_c_line_31_net_profit_total": 300}}
        out = _eic(3000, scenario=self._scn(), sched=sched)
        self.assertEqual(out["eic_earned_income"], 3300)


class ScopeTests(unittest.TestCase):

    def test_only_single_and_mfj(self):
        with self.assertRaises(ValueError):
            _eic(5000, scenario=_scenario(FilingStatus.HEAD_OF_HOUSEHOLD))


class SpineWiringTests(unittest.TestCase):
    """compute_spine lines 27a / 32 / 33 (no routing yet: called directly)."""

    def _spine(self, year, wages):
        from tenforty.forms.f1040_spine import compute_spine
        from tests.fixtures.spine_battery import _w2
        scenario = Scenario(config=_battery_config(year),
                            w2s=[_w2(year, "Example Employer", wages, 0.0)])
        return compute_spine(scenario, load_params(year), {})

    def test_a_plateau_credit_reaches_lines_27_32_and_33(self):
        out = self._spine(YEAR, float(P.eic_earned_income_amount + 100))
        self.assertEqual(out["eic"], P.eic_max_credit)
        self.assertEqual(out["total_other_payments"], out["eic"])
        self.assertEqual(out["total_payments"],
                         out["federal_withheld"] + out["estimated_tax_payments"]
                         + out["total_other_payments"])
        self.assertTrue(out["eic_determination"]["eligible"])

    def test_no_credit_prints_nothing_but_keeps_the_record(self):
        out = self._spine(YEAR, float(P.eic_completed_phaseout["single"]
                                      + 10_000))
        self.assertNotIn("eic", out)
        self.assertIsNone(out["total_other_payments"])
        self.assertEqual(out["eic_determination"]["reason"],
                         "agi_at_or_over_limit")

    def test_a_year_outside_the_eic_grid_computes_nothing(self):
        out = self._spine(2024, 9000.0)
        self.assertNotIn("eic", out)
        self.assertNotIn("eic_determination", out)
        self.assertIsNone(out["total_other_payments"])
