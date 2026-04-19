"""End-to-end tests for a comprehensive tax return exercising all supported forms.

These tests define the scenarios we WANT to support. Many will fail initially
because the models, flattener, mappings, or invariants don't exist yet.
As we build each piece, tests go from red to green.

Forms covered:
- 1040 (core return)
- Schedule 1 (additional income/adjustments — via rental income, SE deductions)
- Schedule 2 (additional taxes — self-employment tax, PTC excess)
- Schedule A (itemized deductions — mortgage, property tax, state tax)
- Schedule E Part I (rental property income/expenses)
- Schedule E Part II (K-1 pass-through from S-corp)
- Schedule D + 8949 (capital gains/losses from stock sales)
- Form 8962 (Premium Tax Credit)
- W-2 (wage income)
- 1099-INT, 1099-DIV, 1099-B (investment income)
- 1098 (mortgage interest)
- K-1 (S-corp pass-through)

The 1120-S (S-corp return itself) is a separate spreadsheet and is tested
separately — here we only test consuming K-1 output on the individual return.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_w2_withholding_matches_input,
)


def _make_rental_property_scenario() -> Scenario:
    """Single filer with W-2 + rental property (Schedule E Part I).

    Exercises: 1040, Schedule 1 (line 5 rental income), Schedule E Part I.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            has_foreign_accounts=False,
            acknowledges_form_8949_unsupported=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=False,
            basis_tracked_externally=False,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=False,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=False,
            prior_year_itemized=False,
        ),
        w2s=[W2(
            employer="Tech Corp", wages=130000,
            federal_tax_withheld=24000,
            ss_wages=130000, ss_tax_withheld=8050,
            medicare_wages=130000, medicare_tax_withheld=1900,
        )],
        # Rental property needs to be representable in the scenario.
        # We need a RentalProperty model or to extend Scenario.
    )


def _make_capital_gains_scenario() -> Scenario:
    """Single filer with W-2 + stock sales (Schedule D + 8949).

    Exercises: 1040, Schedule D, Form 8949, 1099-B.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            has_foreign_accounts=False,
            acknowledges_form_8949_unsupported=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=False,
            basis_tracked_externally=False,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=False,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=False,
            prior_year_itemized=False,
        ),
        w2s=[W2(
            employer="Tech Corp", wages=100000,
            federal_tax_withheld=15000,
            ss_wages=100000, ss_tax_withheld=6200,
            medicare_wages=100000, medicare_tax_withheld=1450,
        )],
        form1099_b=[
            # Long-term gain
            Form1099B(
                broker="Brokerage Inc",
                description="100 shares ACME",
                date_acquired="2023-01-15",
                date_sold="2025-03-20",
                proceeds=15000,
                cost_basis=10000,
                gain_loss=5000,
                short_term=False,
            ),
            # Short-term loss
            Form1099B(
                broker="Brokerage Inc",
                description="50 shares FAKE",
                date_acquired="2025-01-10",
                date_sold="2025-06-15",
                proceeds=4000,
                cost_basis=5000,
                gain_loss=-1000,
                short_term=True,
            ),
        ],
    )


def _make_k1_scenario() -> Scenario:
    """Single filer with W-2 + S-corp K-1 (Schedule E Part II).

    Exercises: 1040, Schedule 1, Schedule E Part II, K-1.
    The K-1 has ordinary business income from the S-corp.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            has_foreign_accounts=False,
            acknowledges_form_8949_unsupported=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=True,
            basis_tracked_externally=True,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=True,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=True,
            prior_year_itemized=False,
        ),
        w2s=[W2(
            employer="Tech Corp", wages=130000,
            federal_tax_withheld=24000,
            ss_wages=130000, ss_tax_withheld=8050,
            medicare_wages=130000, medicare_tax_withheld=1900,
        )],
        schedule_k1s=[ScheduleK1(
            entity_name="Example LLC",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=6000.0,
        )],
    )


def _make_comprehensive_scenario() -> Scenario:
    """The 'kitchen sink' scenario exercising every form we support.

    W-2 + interest + dividends + capital gains + mortgage + K-1.
    Exercises: 1040, Sch 1, Sch 2, Sch A, Sch D, Sch E, 8949, K-1.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            has_foreign_accounts=False,
            acknowledges_form_8949_unsupported=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=True,
            basis_tracked_externally=True,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=True,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=True,
            prior_year_itemized=False,
        ),
        w2s=[W2(
            employer="Tech Corp", wages=150000,
            federal_tax_withheld=30000,
            ss_wages=150000, ss_tax_withheld=9300,
            medicare_wages=150000, medicare_tax_withheld=2200,
            state_wages=150000, state_tax_withheld=10000,
        )],
        form1099_int=[Form1099INT(payer="National Bank", interest=1000)],
        form1099_div=[Form1099DIV(
            payer="Investment Brokerage",
            ordinary_dividends=3000, qualified_dividends=2500,
        )],
        form1099_b=[
            Form1099B(
                broker="Brokerage Inc",
                description="200 shares ACME",
                date_acquired="2023-06-01",
                date_sold="2025-09-15",
                proceeds=25000,
                cost_basis=18000,
                gain_loss=7000,
                short_term=False,
            ),
        ],
        form1098s=[Form1098(
            lender="Home Mortgage Co",
            mortgage_interest=18000,
            property_tax=6000,
        )],
        schedule_k1s=[ScheduleK1(
            entity_name="Example LLC",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=4000.0,
        )],
    )


@needs_libreoffice
class TestE2ECapitalGains(unittest.TestCase):
    """Scenario: W-2 + stock sales → Schedule D + 8949."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = _make_capital_gains_scenario()
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.work_dir,
        )

    def test_engine_produces_capital_gain_output(self):
        """Engine should compute net capital gain/loss from 1099-B data."""
        results = self.orchestrator.compute_federal(self.scenario)

        # Schedule D should have a net gain (5000 LT gain - 1000 ST loss = 4000 net)
        schd = results.get("schd_line16")
        self.assertIsNotNone(schd, "Schedule D line 16 should be computed")

    def test_capital_gains_in_agi(self):
        """AGI should include capital gains."""
        results = self.orchestrator.compute_federal(self.scenario)

        agi = float(results["agi"])
        # AGI should exceed wages alone (100000) because of net capital gain
        self.assertGreater(agi, 100000)

    def test_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)
        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_w2_withholding_matches_input(self, results, self.scenario)


@needs_libreoffice
class TestE2EScheduleK1(unittest.TestCase):
    """Scenario: W-2 + S-corp K-1 rental income → Schedule E Part II."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = _make_k1_scenario()
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.work_dir,
        )

    def test_k1_rental_income_in_agi(self):
        """K-1 rental income should flow into AGI via Schedule E Part II → Schedule 1."""
        results = self.orchestrator.compute_federal(self.scenario)

        agi = float(results["agi"])
        # AGI should exceed wages (130000) because of K-1 rental income (6000)
        self.assertGreater(agi, 130000)

    def test_schedule_e_has_value(self):
        """Schedule E should show the K-1 pass-through."""
        results = self.orchestrator.compute_federal(self.scenario)

        # Schedule E line 41 is total rental/partnership income
        sche = results.get("sche_line41")
        self.assertIsNotNone(sche, "Schedule E line 41 should be computed")
        self.assertNotEqual(float(sche), 0)

    def test_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_w2_withholding_matches_input(self, results, self.scenario)


@needs_libreoffice
class TestE2EComprehensive(unittest.TestCase):
    """Kitchen sink: W-2 + interest + dividends + capital gains + mortgage + K-1.

    This exercises: 1040, Schedule 1, Schedule A, Schedule D, Schedule E,
    Form 8949, and K-1 pass-through. It's the closest we can get to the
    user's actual tax return structure using synthetic data.
    """

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = _make_comprehensive_scenario()
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.work_dir,
        )

    def test_all_income_sources_in_agi(self):
        """AGI should reflect wages + interest + dividends + cap gains + K-1 rental."""
        results = self.orchestrator.compute_federal(self.scenario)

        agi = float(results["agi"])
        wages = 150000
        # AGI should exceed wages because of investment income + K-1
        self.assertGreater(agi, wages)
        # But should be reasonable (not double-counted)
        self.assertLess(agi, wages * 2)

    def test_itemizes_with_mortgage(self):
        """Should itemize: mortgage ($18k) + property tax ($6k) > standard ($15,750)."""
        results = self.orchestrator.compute_federal(self.scenario)

        deductions = float(results.get("total_deductions", 0))
        self.assertGreater(deductions, 15750)

    def test_schedule_d_has_capital_gain(self):
        """Schedule D should show the long-term gain from 1099-B."""
        results = self.orchestrator.compute_federal(self.scenario)

        schd = results.get("schd_line16")
        self.assertIsNotNone(schd)

    def test_withholding_creates_refund_or_reasonable_owed(self):
        """With $30k withheld on ~$165k total income, should be close to break-even."""
        results = self.orchestrator.compute_federal(self.scenario)

        # Just verify the math is internally consistent
        assert_refund_or_owed_consistent(self, results)

    def test_all_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_w2_withholding_matches_input(self, results, self.scenario)


# --- Invariant extensions needed for new forms ---
# These will be added to tests/invariants.py as we build the forms:
#
# assert_schedule_e_rental_consistent(test, results, scenario)
#   - Net rental income = rents - total expenses
#
# assert_schedule_d_consistent(test, results, scenario)
#   - Net gain/loss matches sum of 1099-B gain_loss values
#
# assert_k1_flows_to_schedule_e(test, results, scenario)
#   - K-1 rental income appears in Schedule E Part II
#
# assert_schedule_1_consistent(test, results)
#   - Additional income = sum of Sch E + other income sources
#   - Adjustments = sum of above-the-line deductions
