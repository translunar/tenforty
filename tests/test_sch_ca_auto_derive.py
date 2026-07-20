"""Tests for derive_auto_divergences — auto-derived divergence catalog.

Post-T14b: keys realigned to real federal compute outputs (`sch_1_line_*`,
`social_security_taxable`). RRB and PFL are auto-derived from named
CA540Return fields (`rrb_tier_1_2_amount`, `pfl_amount`) — federal compute
does not separately surface them, so the taxpayer supplies the amount on
their CA return inputs and the kernel routes it as a CATALOG_AUTO
subtraction. Users with no RRB / no PFL declare the corresponding
scope-out attestation and leave the field unset (or zero).

Part AUTO: the auto rows now live in the packaged CA divergence catalog
(`load_catalog(year)`), so each call threads a real `year`; the emitted
divergences carry `source=CATALOG_AUTO` and a `catalog_id` naming the
migrated row. Amounts / lines / directions / descriptions are unchanged
(behavior-preserving vs the retired hardcoded tuples).
"""

import unittest
from tenforty.forms.sch_ca import derive_auto_divergences
from tenforty.models import CA540Return, DivergenceDirection, DivergenceSource


class AutoDerivedCatalogTests(unittest.TestCase):

    def test_unemployment_compensation_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 50_000.0,
            "sch_1_line_7_unemployment": 4_200.0,
        }, year=2025)
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.CATALOG_AUTO)
        self.assertEqual(d.catalog_id, "unemployment-compensation-ca-excludes-rtc-17083")
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 4_200.0)
        self.assertIn("R&TC 17083", d.description)

    def test_social_security_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 80_000.0,
            "social_security_taxable": 12_000.0,
        }, year=2025)
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.CATALOG_AUTO)
        self.assertEqual(d.catalog_id, "social-security-benefits-ca-excludes-rtc-17087")
        self.assertEqual(d.sch_ca_line, "Part I §A 6")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 12_000.0)
        self.assertIn("Social Security", d.description)

    def test_state_income_tax_refund_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 65_000.0,
            "sch_1_line_1_taxable_refunds": 800.0,
        }, year=2025)
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.CATALOG_AUTO)
        self.assertEqual(d.catalog_id, "state-income-tax-refund-not-taxed-ca-rtc-17131")
        self.assertEqual(d.sch_ca_line, "Part I §B 1")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 800.0)
        self.assertIn("refund", d.description)

    def test_no_signals_yields_empty(self):
        result = derive_auto_divergences(federal_results={"agi": 100_000.0}, year=2025)
        self.assertEqual(len(result), 0)

    def test_multiple_signals_yield_multiple_divergences(self):
        result = derive_auto_divergences(federal_results={
            "agi": 90_000.0,
            "sch_1_line_7_unemployment": 5_000.0,
            "social_security_taxable": 8_000.0,
            "sch_1_line_1_taxable_refunds": 600.0,
        }, year=2025)
        self.assertEqual(len(result), 3)

    def test_rrb_named_field_yields_subtraction(self):
        ca540 = CA540Return(rrb_tier_1_2_amount=9_000.0)
        result = derive_auto_divergences(
            federal_results={"agi": 70_000.0},
            year=2025,
            ca540=ca540,
        )
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.CATALOG_AUTO)
        self.assertEqual(d.catalog_id, "railroad-retirement-tier-1-2-ca-excludes-rtc-17087")
        self.assertEqual(d.sch_ca_line, "Part I §A 5b")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 9_000.0)
        self.assertIn("Railroad", d.description)

    def test_pfl_named_field_yields_subtraction(self):
        ca540 = CA540Return(pfl_amount=3_500.0)
        result = derive_auto_divergences(
            federal_results={"agi": 60_000.0},
            year=2025,
            ca540=ca540,
        )
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.CATALOG_AUTO)
        self.assertEqual(d.catalog_id, "paid-family-leave-benefits-ca-excludes-ftb-pub-1001")
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 3_500.0)
        self.assertIn("Paid Family Leave", d.description)

    def test_rrb_field_unset_yields_no_divergence(self):
        ca540 = CA540Return()
        result = derive_auto_divergences(
            federal_results={"agi": 70_000.0},
            year=2025,
            ca540=ca540,
        )
        # No RRB amount provided → no RRB divergence (kernel does not
        # synthesize one from federal pensions_taxable).
        self.assertEqual([d for d in result if d.sch_ca_line == "Part I §A 5b"], [])

    def test_pfl_field_unset_yields_no_divergence(self):
        ca540 = CA540Return()
        result = derive_auto_divergences(
            federal_results={"agi": 60_000.0},
            year=2025,
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
        }, year=2025)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].sch_ca_line, "Part I §A 6")


class AutoRowCatalogIsLoadBearingTests(unittest.TestCase):
    """Mutation check: neuter one auto row in the LOADED catalog (monkeypatch,
    never the packaged YAML) and prove its divergence disappears — so the
    catalog, not a hardcoded fallback, is what fires the auto-derived rows."""

    def test_dropping_ui_auto_row_removes_its_divergence(self):
        import tenforty.forms.sch_ca as sch_ca_mod

        real_load = sch_ca_mod.load_catalog
        federal = {"agi": 90_000.0, "sch_1_line_7_unemployment": 5_000.0}

        # Baseline: the real catalog fires the UI auto row.
        baseline = sch_ca_mod.derive_auto_divergences(federal_results=federal, year=2025)
        self.assertEqual(len(baseline), 1)
        self.assertEqual(
            baseline[0].catalog_id,
            "unemployment-compensation-ca-excludes-rtc-17083",
        )

        def neutered(year):
            # Drop the UI auto row (its federal_key) from the loaded catalog.
            return tuple(
                e for e in real_load(year)
                if not (e.auto is not None
                        and e.auto.federal_key == "sch_1_line_7_unemployment")
            )

        sch_ca_mod.load_catalog = neutered
        try:
            derived = sch_ca_mod.derive_auto_divergences(
                federal_results=federal, year=2025)
            # And the compute path (which routes through derive) loses the
            # §B 7 subtraction it would otherwise emit.
            computed = sch_ca_mod.compute(
                CA540Return(divergences=[]), federal, 2025)
        finally:
            sch_ca_mod.load_catalog = real_load

        self.assertEqual(
            derived, [],
            "UI divergence must vanish when its catalog auto row is dropped",
        )
        self.assertNotIn("sch_ca_line_part_i_b_7_subtractions", computed)
        self.assertEqual(computed["sch_ca_total_subtractions"], 0.0)


if __name__ == "__main__":
    unittest.main()
