import unittest

from tenforty.forms.sch_d_540 import compute as sch_d_540_compute
from tenforty.models import CASchD540Adjustment, DivergenceDirection, DivergenceSource


def _adj(direction: DivergenceDirection, amount: float) -> CASchD540Adjustment:
    return CASchD540Adjustment(
        source=DivergenceSource.USER,
        direction=direction,
        amount=amount,
        description="test",
    )


class SchD540ComputeTests(unittest.TestCase):
    def test_no_worksheet_passes_federal_through(self):
        result = sch_d_540_compute(
            federal_results={"schd_line16": 4_000.0},
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 4_000)
        self.assertEqual(result["sch_d_540_total_subtractions"], 0)
        self.assertEqual(result["sch_d_540_total_additions"], 0)

    def test_federal_loss_passes_through(self):
        result = sch_d_540_compute(
            federal_results={"schd_line16": -3_000.0},
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], -3_000)

    def test_missing_schd_line16_defaults_to_zero(self):
        result = sch_d_540_compute(federal_results={})
        self.assertEqual(result["sch_d_540_net_capital_gain"], 0)


class SchD540DivergenceTests(unittest.TestCase):
    def test_subtraction_reduces_net(self):
        result = sch_d_540_compute(
            federal_results={"schd_line16": 10_000.0},
            worksheet_adjustments=[_adj(DivergenceDirection.SUBTRACTION, 4_000.0)],
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 6_000)
        self.assertEqual(result["sch_d_540_federal_net"], 10_000)
        self.assertEqual(result["sch_d_540_total_subtractions"], 4_000)
        self.assertEqual(result["sch_d_540_total_additions"], 0)

    def test_addition_increases_net(self):
        result = sch_d_540_compute(
            federal_results={"schd_line16": 10_000.0},
            worksheet_adjustments=[_adj(DivergenceDirection.ADDITION, 1_500.0)],
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 11_500)
        self.assertEqual(result["sch_d_540_total_subtractions"], 0)
        self.assertEqual(result["sch_d_540_total_additions"], 1_500)

    def test_mixed_sums_independently(self):
        result = sch_d_540_compute(
            federal_results={"schd_line16": 10_000.0},
            worksheet_adjustments=[
                _adj(DivergenceDirection.SUBTRACTION, 2_000.0),
                _adj(DivergenceDirection.SUBTRACTION, 500.0),
                _adj(DivergenceDirection.ADDITION, 800.0),
            ],
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 8_300)
        self.assertEqual(result["sch_d_540_total_subtractions"], 2_500)
        self.assertEqual(result["sch_d_540_total_additions"], 800)


class SchD540IsRequiredTests(unittest.TestCase):
    """The schedule's instructions: "Do not complete this schedule if all of
    your California gains (losses) are the same as your federal gains (losses)."
    """

    def test_not_required_when_california_equals_federal(self):
        from tenforty.forms import sch_d_540
        for net in (0.0, 4_000.0, -3_000.0):
            with self.subTest(net=net):
                result = sch_d_540_compute(federal_results={"schd_line16": net})
                self.assertIs(sch_d_540.is_required(result), False)

    def test_required_when_there_is_a_subtraction_or_an_addition(self):
        from tenforty.forms import sch_d_540
        for direction in (DivergenceDirection.SUBTRACTION, DivergenceDirection.ADDITION):
            with self.subTest(direction=direction):
                result = sch_d_540_compute(
                    federal_results={"schd_line16": 4_000.0},
                    worksheet_adjustments=[_adj(direction, 250.0)])
                self.assertIs(sch_d_540.is_required(result), True)

    def test_required_when_offsetting_adjustments_leave_the_net_unchanged(self):
        from tenforty.forms import sch_d_540
        result = sch_d_540_compute(
            federal_results={"schd_line16": 4_000.0},
            worksheet_adjustments=[_adj(DivergenceDirection.SUBTRACTION, 250.0),
                                   _adj(DivergenceDirection.ADDITION, 250.0)])
        self.assertEqual(result["sch_d_540_net_capital_gain"],
                         result["sch_d_540_federal_net"])
        self.assertIs(sch_d_540.is_required(result), True)

    def test_missing_adjustment_keys_are_loud_not_treated_as_zero(self):
        from tenforty.forms import sch_d_540
        with self.assertRaises(KeyError):
            sch_d_540.is_required({"sch_d_540_net_capital_gain": 0})
