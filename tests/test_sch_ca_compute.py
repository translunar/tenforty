# tests/test_sch_ca_compute.py
import unittest

from tenforty.forms.sch_ca import compute as sch_ca_compute
from tenforty.models import CA540Return, CASchCAAdjustment, DivergenceDirection, DivergenceSource


class SchCaKernelTests(unittest.TestCase):
    def test_empty_divergences_produce_no_adjustments(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={"agi": 100_000.0, "wages": 100_000.0},
        )
        # No subtractions, no additions; CA AGI matches federal
        self.assertEqual(result["sch_ca_total_subtractions"], 0.0)
        self.assertEqual(result["sch_ca_total_additions"], 0.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0)

    def test_single_subtraction_routes_to_correct_line(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §C 13",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=4300.0,
                    description="HSA disallowed",
                ),
            ]),
            federal_results={"agi": 100_000.0},
        )
        # Subtraction reduces CA AGI
        self.assertEqual(result["sch_ca_line_part_i_c_13_subtractions"], 4300.0)
        self.assertEqual(result["sch_ca_total_subtractions"], 4300.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0 - 4300.0)

    def test_multiple_divergences_same_line_sum(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.AUTO_DERIVED,
                    sch_ca_line="Part I §B 8z",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=1500.0,
                    description="CA Lottery",
                ),
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §B 8z",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=200.0,
                    description="Recycling income",
                ),
            ]),
            federal_results={"agi": 50_000.0},
        )
        self.assertEqual(result["sch_ca_line_part_i_b_8z_subtractions"], 1700.0)

    def test_addition_increases_ca_agi(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §A 2",
                    direction=DivergenceDirection.ADDITION,
                    amount=350.0,
                    description="Out-of-state muni",
                ),
            ]),
            federal_results={"agi": 80_000.0},
        )
        self.assertEqual(result["sch_ca_ca_agi"], 80_000.0 + 350.0)
        self.assertEqual(result["sch_ca_line_part_i_a_2_additions"], 350.0)
        self.assertEqual(result["sch_ca_total_additions"], 350.0)


class SchCaIntegratedKernelTests(unittest.TestCase):
    def test_kernel_combines_auto_derived_and_worksheet_divergences(self):
        worksheet_divergences = [
            CASchCAAdjustment(
                source=DivergenceSource.WORKSHEET,
                sch_ca_line="Part I §C 13",
                direction=DivergenceDirection.SUBTRACTION,
                amount=4300.0,
                description="HSA disallowed",
            ),
        ]
        federal_results = {
            "agi": 100_000.0,
            "schedule_1_unemployment_compensation": 4500.0,
        }
        ca540 = CA540Return(divergences=worksheet_divergences)
        result = sch_ca_compute(ca540=ca540, federal_results=federal_results)
        self.assertEqual(result["sch_ca_total_subtractions"], 4300.0 + 4500.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0 - (4300.0 + 4500.0))

    def test_kernel_returns_empty_when_ca540_is_none(self):
        result = sch_ca_compute(ca540=None, federal_results={"agi": 50_000.0})
        self.assertEqual(result, {})

    def test_kernel_pulls_auto_derive_with_empty_worksheet(self):
        ca540 = CA540Return(divergences=[])
        federal_results = {
            "agi": 75_000.0,
            "schedule_1_unemployment_compensation": 2_000.0,
        }
        result = sch_ca_compute(ca540=ca540, federal_results=federal_results)
        self.assertEqual(result["sch_ca_total_subtractions"], 2_000.0)
        self.assertEqual(result["sch_ca_ca_agi"], 75_000.0 - 2_000.0)
