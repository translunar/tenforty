"""Tests for derive_auto_divergences — auto-derived divergence catalog.

Post-T14b: keys realigned to real federal compute outputs (`sch_1_line_*`,
`social_security_taxable`). RRB and PFL are auto-derived from named
CA540Return fields (`rrb_tier_1_2_amount`, `pfl_amount`) — federal compute
does not separately surface them, so the taxpayer supplies the amount on
their CA return inputs and the kernel routes it as an AUTO_DERIVED
subtraction. Users with no RRB / no PFL declare the corresponding
scope-out attestation and leave the field unset (or zero).
"""

import unittest
from tenforty.forms.sch_ca import derive_auto_divergences
from tenforty.models import CA540Return, DivergenceDirection, DivergenceSource


class AutoDerivedCatalogTests(unittest.TestCase):

    def test_unemployment_compensation_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 50_000.0,
            "sch_1_line_7_unemployment": 4_200.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 4_200.0)
        self.assertIn("R&TC 17083", d.description)

    def test_social_security_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 80_000.0,
            "social_security_taxable": 12_000.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §A 6")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 12_000.0)
        self.assertIn("Social Security", d.description)

    def test_state_income_tax_refund_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 65_000.0,
            "sch_1_line_1_taxable_refunds": 800.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 1")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 800.0)
        self.assertIn("refund", d.description)

    def test_no_signals_yields_empty(self):
        result = derive_auto_divergences(federal_results={"agi": 100_000.0})
        self.assertEqual(len(result), 0)

    def test_multiple_signals_yield_multiple_divergences(self):
        result = derive_auto_divergences(federal_results={
            "agi": 90_000.0,
            "sch_1_line_7_unemployment": 5_000.0,
            "social_security_taxable": 8_000.0,
            "sch_1_line_1_taxable_refunds": 600.0,
        })
        self.assertEqual(len(result), 3)

    def test_rrb_named_field_yields_subtraction(self):
        ca540 = CA540Return(rrb_tier_1_2_amount=9_000.0)
        result = derive_auto_divergences(
            federal_results={"agi": 70_000.0},
            ca540=ca540,
        )
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §A 5b")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 9_000.0)
        self.assertIn("Railroad", d.description)

    def test_pfl_named_field_yields_subtraction(self):
        ca540 = CA540Return(pfl_amount=3_500.0)
        result = derive_auto_divergences(
            federal_results={"agi": 60_000.0},
            ca540=ca540,
        )
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 3_500.0)
        self.assertIn("Paid Family Leave", d.description)

    def test_rrb_field_unset_yields_no_divergence(self):
        ca540 = CA540Return()
        result = derive_auto_divergences(
            federal_results={"agi": 70_000.0},
            ca540=ca540,
        )
        # No RRB amount provided → no RRB divergence (kernel does not
        # synthesize one from federal pensions_taxable).
        self.assertEqual([d for d in result if d.sch_ca_line == "Part I §A 5b"], [])

    def test_pfl_field_unset_yields_no_divergence(self):
        ca540 = CA540Return()
        result = derive_auto_divergences(
            federal_results={"agi": 60_000.0},
            ca540=ca540,
        )
        self.assertEqual(
            [d for d in result if d.sch_ca_line == "Part I §B 7" and "Paid Family Leave" in d.description],
            [],
        )

    def test_no_ca540_arg_falls_back_to_federal_only(self):
        # Backward compatibility: callers that pass only federal_results
        # still get the federal-derived catalog; no RRB / PFL.
        result = derive_auto_divergences(federal_results={
            "agi": 80_000.0,
            "social_security_taxable": 12_000.0,
        })
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].sch_ca_line, "Part I §A 6")


if __name__ == "__main__":
    unittest.main()
