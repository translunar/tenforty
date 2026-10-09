"""Line 13 Opens: Schedule C line 13 prints and counts the resolved
depreciation.

Line 13 enters the line-28 total, both net-profit estimates and the emitted
values through ONE definition (`sch_c.part_ii_lines`), so the page total, the
routing estimate, the excess-business-loss guard and the printed form cannot
disagree about whether depreciation is in.

The 2,000 figure is a legacy regression pin (first year of a five-year asset
on a 10,000 basis, from the pre-existing depreciation tests), not a hand
oracle.
"""

import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tenforty.forms import sch_c
from tenforty.models import DepreciableAsset, ScheduleCBusiness
from tenforty.orchestrator import ReturnOrchestrator, aggregate_business_losses
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

YEAR = 2025
LINE_13 = 2_000
LINE_13_KEY = "sch_c_line_13_depreciation"


def _equipment(basis: float = 10_000.0) -> DepreciableAsset:
    """Five-year property placed early THIS year."""
    return DepreciableAsset(
        description="Equipment", date_placed_in_service=date(YEAR, 2, 1),
        basis=basis, recovery_class="5-year",
        no_bonus_or_section_179_history=True)


def _biz(*, gross: float = 50_000.0, assets=(), **extra) -> ScheduleCBusiness:
    return ScheduleCBusiness(
        description="Consulting", gross_receipts=gross,
        depreciable_assets=tuple(assets), **extra)


def _scenario(*businesses, at_risk: bool | None = None):
    s = make_simple_scenario()
    s.config.year = YEAR
    if at_risk is not None:
        s.config.acknowledges_sch_c_all_investment_at_risk = at_risk
    s.schedule_c_businesses = list(businesses)
    return s


def _lines(*businesses, at_risk=None) -> dict:
    return sch_c.compute(
        _scenario(*businesses, at_risk=at_risk),
        upstream={})["sch_c_businesses"][0]


class Line13InResultsTests(unittest.TestCase):
    def test_line_13_present_and_counted(self):
        lines = _lines(_biz(supplies=5_000.0, assets=[_equipment()]))
        self.assertEqual(lines[LINE_13_KEY], LINE_13)
        self.assertEqual(
            lines["sch_c_line_28_total_expenses"], 5_000 + LINE_13)
        self.assertEqual(
            lines["sch_c_line_29_tentative_profit"],
            50_000 - 5_000 - LINE_13)
        self.assertEqual(
            lines["sch_c_line_31_net_profit"], 50_000 - 5_000 - LINE_13)

    def test_page_foots_from_printed_lines(self):
        lines = _lines(_biz(
            gross=50_000.4, supplies=5_000.6, assets=[_equipment()]))
        self.assertEqual(
            lines["sch_c_line_28_total_expenses"], 5_001 + lines[LINE_13_KEY])
        self.assertEqual(
            lines["sch_c_line_29_tentative_profit"],
            lines["sch_c_line_7_gross_income"]
            - lines["sch_c_line_28_total_expenses"])

    def test_business_without_depreciation_prints_no_line_13(self):
        lines = _lines(_biz(supplies=5_000.0))
        self.assertNotIn(LINE_13_KEY, lines)
        self.assertEqual(lines["sch_c_line_28_total_expenses"], 5_000)

    def test_stated_mode_line_13(self):
        lines = _lines(_biz(
            supplies=5_000.0, depreciation=1_234.5,
            acknowledges_depreciation_stated_outside_macrs=True))
        self.assertEqual(lines[LINE_13_KEY], 1_235)
        self.assertEqual(lines["sch_c_line_28_total_expenses"], 6_235)

    def test_total_sums_resolved_line_13_across_businesses(self):
        s = _scenario(
            _biz(assets=[_equipment()]),
            _biz(gross=20_000.0, supplies=1_000.0))
        out = sch_c.compute(s, upstream={})
        self.assertEqual(
            out["sch_c_line_31_net_profit_total"],
            (50_000 - LINE_13) + (20_000 - 1_000))


class EstimatesSeeLine13Tests(unittest.TestCase):
    """The EIC-routing estimate and the 461(l) guard see the same business
    the page shows."""

    def test_net_profit_estimate_includes_line_13(self):
        biz = _biz(supplies=5_000.0, assets=[_equipment()])
        self.assertEqual(
            sch_c.net_profit_estimate(biz, YEAR), 50_000.0 - 5_000.0 - LINE_13)

    def test_printed_net_profit_includes_line_13(self):
        biz = _biz(supplies=5_000.0, assets=[_equipment()])
        self.assertEqual(
            sch_c.printed_net_profit(biz, YEAR), 50_000 - 5_000 - LINE_13)

    def test_loss_guard_counts_a_loss_made_by_line_13(self):
        s = _scenario(_biz(gross=1_500.0, assets=[_equipment()]))
        self.assertEqual(aggregate_business_losses(s), LINE_13 - 1_500)
        # Twin: no assets, no loss.
        self.assertEqual(
            aggregate_business_losses(_scenario(_biz(gross=1_500.0))), 0)


class LossOnlyBecauseOfLine13Tests(unittest.TestCase):
    def _loss_biz(self):
        return _biz(gross=1_500.0, assets=[_equipment()])

    def test_refuses_without_the_at_risk_acknowledgment(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"computes a net LOSS \(line 31 = -500\)"):
            sch_c.compute(_scenario(self._loss_biz(), at_risk=False),
                          upstream={})

    def test_checks_32a_with_it(self):
        lines = _lines(self._loss_biz(), at_risk=True)
        self.assertEqual(lines["sch_c_line_31_net_profit"], 1_500 - LINE_13)
        self.assertIs(lines["sch_c_line_32a_all_investment_at_risk"], True)

    def test_same_business_without_assets_is_a_profit_and_answers_no_32(self):
        lines = _lines(_biz(gross=1_500.0), at_risk=False)
        self.assertEqual(lines["sch_c_line_31_net_profit"], 1_500)
        self.assertNotIn("sch_c_line_32a_all_investment_at_risk", lines)


class StatedFigureRefusalTests(unittest.TestCase):
    """Replaces the old blanket line-13 refusal: a stated amount now needs
    only its per-activity acknowledgment."""

    def test_stated_depreciation_without_acknowledgment_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"Schedule C business \('Consulting'\) states "
                r"`depreciation` without an asset list"):
            sch_c.compute(_scenario(_biz(depreciation=100.0)), upstream={})

    def test_with_acknowledgment_it_computes(self):
        lines = _lines(_biz(
            depreciation=100.0,
            acknowledges_depreciation_stated_outside_macrs=True))
        self.assertEqual(lines[LINE_13_KEY], 100)


class EmitValuesTests(unittest.TestCase):
    def test_emit_values_carry_line_13(self):
        s = _scenario(_biz(supplies=5_000.0, assets=[_equipment()]))
        lines = sch_c.compute(s, upstream={})["sch_c_businesses"][0]
        values = sch_c.emit_values(s, 0, lines)
        self.assertEqual(values[LINE_13_KEY], LINE_13)
        self.assertEqual(values["sch_c_expense_supplies"], 5_000.0)

    def test_emit_values_omit_line_13_when_there_is_none(self):
        s = _scenario(_biz(supplies=5_000.0))
        lines = sch_c.compute(s, upstream={})["sch_c_businesses"][0]
        self.assertNotIn(LINE_13_KEY, sch_c.emit_values(s, 0, lines))


class DownstreamOfLine31Tests(unittest.TestCase):
    """Schedule SE net earnings, the Form 8995 QBI component and Schedule 1
    line 3 each move with line 13."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(self._tmp.name))

    def _schedules(self, *businesses):
        schedules, _fanout = self.orchestrator._compute_native_schedules(
            _scenario(*businesses))
        return schedules

    def test_each_consumer_falls_by_line_13(self):
        without = self._schedules(_biz(supplies=5_000.0))
        with_13 = self._schedules(_biz(supplies=5_000.0,
                                       assets=[_equipment()]))
        self.assertEqual(
            without["sch_1"]["sch_1_line_3_business_income"]
            - with_13["sch_1"]["sch_1_line_3_business_income"], LINE_13)
        self.assertEqual(
            without["sch_se"]["sch_se_line_2_net_profit"]
            - with_13["sch_se"]["sch_se_line_2_net_profit"], LINE_13)
        self.assertEqual(
            with_13["sch_se"]["sch_se_line_2_net_profit"],
            50_000 - 5_000 - LINE_13)
        # QBI = net profit less half the SE tax (and SE health); a lower net
        # profit lowers both, so the component falls by a little under
        # line 13 -- strictly between zero and line 13.
        drop = (without["f8995"]["f8995_line_1_qbi"]
                - with_13["f8995"]["f8995_line_1_qbi"])
        self.assertGreater(drop, 0)
        self.assertLess(drop, LINE_13 + 1)

    def test_results_reach_compute_federal(self):
        results = self.orchestrator.compute_federal(
            _scenario(_biz(supplies=5_000.0, assets=[_equipment()])))
        self.assertEqual(
            results["sch_1_line_3_business_income"], 50_000 - 5_000 - LINE_13)
        self.assertEqual(
            results["depreciation_recon_sch_c_0_used_amount"], LINE_13)


class WorkbookPathGuardTests(unittest.TestCase):
    """Unchanged behaviour, proven not regressed: Schedule C on the workbook
    compute path still refuses -- with assets as without."""

    def test_schedule_c_with_assets_refuses_on_the_workbook_path(self):
        s = _scenario(_biz(assets=[_equipment()]))
        s.config.filing_status = "married_jointly"
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(tmp))
            self.assertFalse(orchestrator._scenario_in_spine_scope(s))
            with self.assertRaisesRegex(NotImplementedError, "Schedule C"):
                orchestrator._compute_1040_pipeline(s)


if __name__ == "__main__":
    unittest.main()
