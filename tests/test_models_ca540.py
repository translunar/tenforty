# tests/test_models_ca540.py
import unittest

from tenforty.models import (
    CA540Return,
    CASchCAAdjustment,
    DivergenceDirection,
    DivergenceSource,
    VoluntaryContribution,
)


class CA540ReturnDataclassTests(unittest.TestCase):
    def test_ca540return_constructs_with_defaults(self):
        ca = CA540Return()
        self.assertEqual(ca.estimated_payments, 0.0)
        self.assertEqual(ca.use_tax, 0.0)
        self.assertEqual(ca.estimated_tax_penalty, 0.0)
        self.assertEqual(ca.ptet_credit, 0.0)
        self.assertEqual(ca.voluntary_contributions, [])
        self.assertEqual(ca.divergences, [])

    def test_ca540return_with_divergences(self):
        ca = CA540Return(
            divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.AUTO_DERIVED,
                    sch_ca_line="Part I §B 7",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=4500.0,
                    description="Unemployment compensation excluded by CA",
                    federal_source="Sch 1 line 7",
                    pub1001_ref="p.17",
                ),
            ],
        )
        self.assertEqual(len(ca.divergences), 1)
        self.assertEqual(ca.divergences[0].amount, 4500.0)

    def test_divergence_source_enum_values(self):
        self.assertEqual(DivergenceSource.AUTO_DERIVED.value, "auto_derived")
        self.assertEqual(DivergenceSource.WORKSHEET.value, "worksheet")

    def test_divergence_direction_enum_values(self):
        self.assertEqual(DivergenceDirection.SUBTRACTION.value, "subtraction")
        self.assertEqual(DivergenceDirection.ADDITION.value, "addition")


class CASchCAAdjustmentTests(unittest.TestCase):
    def test_minimum_required_fields(self):
        adj = CASchCAAdjustment(
            source=DivergenceSource.WORKSHEET,
            sch_ca_line="Part I §C 13",
            direction=DivergenceDirection.SUBTRACTION,
            amount=4300.0,
            description="HSA contribution disallowed",
        )
        self.assertEqual(adj.amount, 4300.0)
        self.assertIsNone(adj.federal_source)
        self.assertIsNone(adj.pub1001_ref)
