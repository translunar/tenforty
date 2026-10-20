"""Positions phase 2: Form 8995 consults qbi-sehi-shareholder-reduction.

The ruled mechanics (team-lead, 2026-10-20): on the S corporation shape the
return's election decides whether the self-employed health insurance
deduction reduces that K-1's QBI row (irs-faq: straight subtraction, no
floor) or not (no-reduction). With more than one S corporation K-1 the
irs-faq election is refused: which entity's premiums sourced the deduction
is not modeled. Shapes outside the gate keep their refusals. All figures
synthetic."""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tenforty import positions
from tenforty.forms import f8995
from tenforty.models import (FilingStatus, K1FanoutData, ScheduleCBusiness,
                             ScheduleK1)
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_wages_only
from tests.helpers import REPO_ROOT, make_k1_scenario

QBI_SEHI = "qbi-sehi-shareholder-reduction"
_K1_ACKS = ("acknowledges_qbi_below_threshold", "acknowledges_unlimited_at_risk",
            "basis_tracked_externally",
            "acknowledges_no_partnership_se_earnings",
            "acknowledges_no_section_1231_gain",
            "acknowledges_no_more_than_four_k1s", "acknowledges_no_k1_credits",
            "acknowledges_no_section_179", "acknowledges_no_estate_trust_k1")


def _k1(entity_type, qbi, n=1):
    return ScheduleK1(
        entity_name=f"Example Entity {n}", entity_ein="00-0000000",
        entity_type=entity_type, material_participation=True,
        ordinary_business_income=qbi, qbi_amount=qbi)


def _pin_shape(**elections):
    """The pin shape: wages, SEHI 3,000 and one S corporation K-1 with QBI
    10,000."""
    base = build_wages_only(2024, FilingStatus.SINGLE)
    cfg = dataclasses.replace(
        base.config, self_employed_health_insurance_deduction=3_000.0,
        **{k: True for k in _K1_ACKS})
    return dataclasses.replace(
        base, config=cfg, positions=dict(elections),
        schedule_k1s=[_k1("s_corp", 10_000.0)])


def _orch():
    return ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                              work_dir=Path(tempfile.mkdtemp()))


def _compute(scenario):
    with unittest.mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=AssertionError("workbook path reached")):
        return _orch().compute_federal(scenario)


class PinShapeTests(unittest.TestCase):
    """Ruling points 2, 3 and 5 end to end on the native spine."""

    def test_irs_faq_reduces_the_k1_qbi(self):
        # 20% x (10,000 - 3,000)
        results = _compute(_pin_shape(**{QBI_SEHI: "irs-faq"}))
        self.assertEqual(results["qbi_deduction"], 1_400)

    def test_no_reduction_leaves_the_k1_qbi_whole(self):
        # 20% x 10,000
        results = _compute(_pin_shape(**{QBI_SEHI: "no-reduction"}))
        self.assertEqual(results["qbi_deduction"], 2_000)

    def test_the_elections_differ(self):
        # An election that changes nothing could not fire.
        self.assertNotEqual(
            _compute(_pin_shape(**{QBI_SEHI: "irs-faq"}))["qbi_deduction"],
            _compute(_pin_shape(**{QBI_SEHI: "no-reduction"}))
            ["qbi_deduction"])

    def test_no_election_refuses_naming_the_controversy(self):
        with self.assertRaises(NotImplementedError) as cm:
            _compute(_pin_shape())
        self.assertEqual(str(cm.exception),
                         positions.refusal_message(QBI_SEHI))

    def test_the_run_records_the_consult(self):
        for choice in ("irs-faq", "no-reduction"):
            with self.subTest(choice=choice):
                results = _compute(_pin_shape(**{QBI_SEHI: choice}))
                self.assertEqual(results[positions.RESULTS_KEY], [
                    {"slug": QBI_SEHI, "choice": choice, "reached": True}])


def _case(k1s, se_health=3_000.0, businesses=(), taxable_income=100_000.0,
          **elections):
    """Form 8995 alone: a scenario and an upstream that agrees with it."""
    s = make_k1_scenario()
    s.config.self_employed_health_insurance_deduction = se_health
    s.schedule_k1s = list(k1s)
    s.schedule_c_businesses = [ScheduleCBusiness(description=desc)
                               for desc, _ in businesses]
    s.positions = dict(elections)
    nets = [net for _, net in businesses]
    upstream = {
        "f1040": {"taxable_income_before_qbi_deduction": taxable_income,
                  "net_capital_gain": 0.0, "qualified_dividends": 0.0},
        "k1_fanout": K1FanoutData(
            sch_b_interest_additions=(), sch_b_dividend_additions=(),
            sch_d_short_term_additions=(), sch_d_long_term_additions=(),
            qbi_aggregate=sum(k1.qbi_amount for k1 in k1s),
            qualified_dividends_aggregate=0.0, passive_activities=()),
        "sch_c": {"sch_c_businesses": [{"sch_c_line_31_net_profit": net}
                                       for net in nets],
                  "sch_c_line_31_net_profit_total": sum(nets)},
        "sch_se": {"sch_se_line_13_half_deduction": 0.0},
    }
    return s, upstream


class IrsFaqMechanicsTests(unittest.TestCase):
    """Ruling 2: straight subtraction from that K-1's row, no floor, before
    anything aggregates it."""

    def test_the_row_carries_the_reduction(self):
        s, up = _case([_k1("s_corp", 10_000.0)], **{QBI_SEHI: "irs-faq"})
        out = f8995.compute(s, up)
        self.assertEqual(out["f8995_line_1i_qbi"], 7_000)
        self.assertEqual(out["f8995_line_1_qbi"], 7_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 1_400)

    def test_no_floor(self):
        # SEHI above the K-1's QBI leaves a negative row; the existing
        # negative-QBI netting carries it forward.
        s, up = _case([_k1("s_corp", 2_000.0)], **{QBI_SEHI: "irs-faq"})
        out = f8995.compute(s, up)
        self.assertEqual(out["f8995_line_1i_qbi"], -1_000)
        self.assertEqual(out["f8995_line_2_total_qbi"], -1_000)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], -1_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)

    def test_the_threshold_gate_sees_the_reduced_qbi(self):
        # Above the simple-path threshold the 8995-A refusal fires only
        # while QBI is positive: under irs-faq this K-1's QBI is not.
        over = 1_000_000.0
        s, up = _case([_k1("s_corp", 2_000.0)], taxable_income=over,
                      **{QBI_SEHI: "irs-faq"})
        s.config.acknowledges_qbi_below_threshold = False
        self.assertEqual(f8995.compute(s, up)["f8995_line_1i_qbi"], -1_000)
        s, up = _case([_k1("s_corp", 2_000.0)], taxable_income=over,
                      **{QBI_SEHI: "no-reduction"})
        s.config.acknowledges_qbi_below_threshold = False
        with self.assertRaisesRegex(NotImplementedError, "8995-A"):
            f8995.compute(s, up)


class NoReductionMechanicsTests(unittest.TestCase):
    """Ruling 3: the K-1's QBI flows untouched."""

    def test_the_row_is_untouched(self):
        s, up = _case([_k1("s_corp", 10_000.0)],
                      **{QBI_SEHI: "no-reduction"})
        out = f8995.compute(s, up)
        self.assertEqual(out["f8995_line_1i_qbi"], 10_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 2_000)

    def test_two_s_corp_k1s_compute(self):
        s, up = _case([_k1("s_corp", 10_000.0, 1), _k1("s_corp", 5_000.0, 2)],
                      **{QBI_SEHI: "no-reduction"})
        out = f8995.compute(s, up)
        self.assertEqual(out["f8995_line_1i_qbi"], 10_000)
        self.assertEqual(out["f8995_line_1ii_qbi"], 5_000)


class MultiK1RefusalTests(unittest.TestCase):
    """Ruling 4: irs-faq with more than one S corporation K-1 refuses
    fail-closed rather than allocate."""

    def setUp(self):
        self.s, self.up = _case(
            [_k1("s_corp", 10_000.0, 1), _k1("s_corp", 5_000.0, 2)],
            **{QBI_SEHI: "irs-faq"})

    def test_refused(self):
        with self.assertRaises(NotImplementedError) as cm:
            f8995.compute(self.s, self.up)
        message = str(cm.exception)
        for needle in (QBI_SEHI, "irs-faq", "positions", "premiums"):
            self.assertIn(needle, message)

    def test_refused_end_to_end(self):
        base = _pin_shape(**{QBI_SEHI: "irs-faq"})
        scenario = dataclasses.replace(
            base, schedule_k1s=[_k1("s_corp", 10_000.0, 1),
                                _k1("s_corp", 5_000.0, 2)])
        with self.assertRaisesRegex(NotImplementedError, "premiums"):
            _compute(scenario)


class RetainedRefusalTests(unittest.TestCase):
    """Shapes outside the gate keep their refusals, whatever the
    position's state, and an election for them is refused at load."""

    SHAPES = {
        "schedule c + s-corp k1": dict(
            k1s=[_k1("s_corp", 10_000.0)],
            businesses=[("Example Bindery", 30_000.0)]),
        "partnership k1": dict(k1s=[_k1("partnership", 10_000.0)]),
        "s-corp k1 + partnership k1": dict(
            k1s=[_k1("s_corp", 10_000.0, 1),
                 _k1("partnership", 5_000.0, 2)]),
    }

    def test_refused(self):
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                s, up = _case(**shape)
                with self.assertRaises(NotImplementedError) as cm:
                    f8995.compute(s, up)
                message = str(cm.exception)
                self.assertIn(QBI_SEHI, message)
                self.assertIn("plan", message)
                self.assertNotIn("phase 2", message)

    def test_no_consult(self):
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                s, up = _case(**shape)
                with unittest.mock.patch.object(
                        positions, "election",
                        wraps=positions.election) as spy, \
                        self.assertRaises(NotImplementedError):
                    f8995.compute(s, up)
                self.assertEqual(spy.call_count, 0)

    def test_an_election_for_them_is_refused_at_load(self):
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                s, _ = _case(**shape)
                with self.assertRaisesRegex(ValueError, "never reaches"):
                    positions.validate_elections(
                        dataclasses.replace(s, positions={QBI_SEHI: "irs-faq"}),
                        exact=True)


class NonReachingShapesTests(unittest.TestCase):
    """Shapes the position never touches see no consult."""

    def test_schedule_c_only_sehi_is_not_consulted(self):
        s, up = _case([], businesses=[("Example Bindery", 30_000.0)])
        up["sch_c"]["sch_c_businesses"][0]["sch_c_line_7_gross_income"] = (
            30_000.0)
        with unittest.mock.patch.object(
                positions, "election", wraps=positions.election) as spy:
            out = f8995.compute(s, up)
        self.assertEqual(spy.call_count, 0)
        self.assertEqual(out["f8995_line_1i_qbi"], 27_000)


if __name__ == "__main__":
    unittest.main()
