import unittest

from tenforty.models import CA540Return, FilingStatus, VoluntaryContribution
from tenforty.params import california as ca_params
from tenforty.forms.f540 import (
    compute_standard_deduction,
    compute_exemption_credit,
    compute_ca_tax,
    compute,
)


# Verified against FTB Form 540 PDFs (committed in T1; constants in T9a).
# DO NOT modify these values — they are the FTB-published actuals
# extracted from each year's f540.pdf line 18 (standard deduction)
# and lines 7-10 (exemption credit multipliers).
EXPECTED_STANDARD_DEDUCTION: dict[int, dict[FilingStatus, int]] = {
    2025: {
        FilingStatus.SINGLE: 5_706,
        FilingStatus.MARRIED_SEPARATELY: 5_706,
        FilingStatus.MARRIED_JOINTLY: 11_412,
        FilingStatus.HEAD_OF_HOUSEHOLD: 11_412,
        FilingStatus.QUALIFYING_WIDOW: 11_412,
    },
    2024: {
        FilingStatus.SINGLE: 5_540,
        FilingStatus.MARRIED_SEPARATELY: 5_540,
        FilingStatus.MARRIED_JOINTLY: 11_080,
        FilingStatus.HEAD_OF_HOUSEHOLD: 11_080,
        FilingStatus.QUALIFYING_WIDOW: 11_080,
    },
    2023: {
        FilingStatus.SINGLE: 5_363,
        FilingStatus.MARRIED_SEPARATELY: 5_363,
        FilingStatus.MARRIED_JOINTLY: 10_726,
        FilingStatus.HEAD_OF_HOUSEHOLD: 10_726,
        FilingStatus.QUALIFYING_WIDOW: 10_726,
    },
    2022: {
        FilingStatus.SINGLE: 5_202,
        FilingStatus.MARRIED_SEPARATELY: 5_202,
        FilingStatus.MARRIED_JOINTLY: 10_404,
        FilingStatus.HEAD_OF_HOUSEHOLD: 10_404,
        FilingStatus.QUALIFYING_WIDOW: 10_404,
    },
    2021: {
        FilingStatus.SINGLE: 4_803,
        FilingStatus.MARRIED_SEPARATELY: 4_803,
        FilingStatus.MARRIED_JOINTLY: 9_606,
        FilingStatus.HEAD_OF_HOUSEHOLD: 9_606,
        FilingStatus.QUALIFYING_WIDOW: 9_606,
    },
}


EXPECTED_EXEMPTION_CREDIT: dict[int, dict[FilingStatus, int]] = {
    2025: {
        FilingStatus.SINGLE: 153,
        FilingStatus.MARRIED_SEPARATELY: 153,
        FilingStatus.HEAD_OF_HOUSEHOLD: 153,
        FilingStatus.MARRIED_JOINTLY: 306,
        FilingStatus.QUALIFYING_WIDOW: 306,
    },
    2024: {
        FilingStatus.SINGLE: 149,
        FilingStatus.MARRIED_SEPARATELY: 149,
        FilingStatus.HEAD_OF_HOUSEHOLD: 149,
        FilingStatus.MARRIED_JOINTLY: 298,
        FilingStatus.QUALIFYING_WIDOW: 298,
    },
    2023: {
        FilingStatus.SINGLE: 144,
        FilingStatus.MARRIED_SEPARATELY: 144,
        FilingStatus.HEAD_OF_HOUSEHOLD: 144,
        FilingStatus.MARRIED_JOINTLY: 288,
        FilingStatus.QUALIFYING_WIDOW: 288,
    },
    2022: {
        FilingStatus.SINGLE: 140,
        FilingStatus.MARRIED_SEPARATELY: 140,
        FilingStatus.HEAD_OF_HOUSEHOLD: 140,
        FilingStatus.MARRIED_JOINTLY: 280,
        FilingStatus.QUALIFYING_WIDOW: 280,
    },
    2021: {
        FilingStatus.SINGLE: 129,
        FilingStatus.MARRIED_SEPARATELY: 129,
        FilingStatus.HEAD_OF_HOUSEHOLD: 129,
        FilingStatus.MARRIED_JOINTLY: 258,
        FilingStatus.QUALIFYING_WIDOW: 258,
    },
}


class StandardDeductionTests(unittest.TestCase):
    def test_all_years_all_filing_statuses(self):
        for year, expected_by_status in EXPECTED_STANDARD_DEDUCTION.items():
            for filing_status, expected in expected_by_status.items():
                with self.subTest(year=year, filing_status=filing_status):
                    self.assertEqual(
                        compute_standard_deduction(year=year, filing_status=filing_status),
                        expected,
                    )


class ExemptionCreditTests(unittest.TestCase):
    def test_all_years_all_filing_statuses(self):
        for year, expected_by_status in EXPECTED_EXEMPTION_CREDIT.items():
            for filing_status, expected in expected_by_status.items():
                with self.subTest(year=year, filing_status=filing_status):
                    self.assertEqual(
                        compute_exemption_credit(year=year, filing_status=filing_status),
                        expected,
                    )


class UnsupportedYearTests(unittest.TestCase):
    def test_year_not_in_supported_range_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            compute_standard_deduction(year=2020, filing_status=FilingStatus.SINGLE)
        self.assertIn("2020", str(ctx.exception))
        self.assertIn("2021", str(ctx.exception))
        self.assertIn("2025", str(ctx.exception))


# ---------------------------------------------------------------------------
# compute_ca_tax oracles
#
# Oracle 1 (TAX_TABLE_BOUNDARY_ANCHORS_2025): FTB Tax Table boundary anchors
#   for TY2025. Values are PRE-VERIFIED bin midpoint computations against the
#   TY2025 rate schedules extracted from the FTB 540 booklet. Source: FTB-
#   published 2025 Tax Table (TY2025 540 booklet), extracted by team-lead.
#   $50,000 maps to bin $49,951–$50,050 (regular 100-wide bin, midpoint
#   $50,000.5). $100,000 maps to the truncated last bin $99,951–$100,000
#   (midpoint $99,975.5).
#
# Oracle 2 (TRIVIAL_TAX_TABLE_BINS): Status/year-invariant zero-tax incomes
#   ($0, $1, $25, $50). Holds for all supported CA years (see tenforty/years.py)
#   and all filing statuses.
#
# Oracle 3 (EXPECTED_CHRIS_PAT_MFJ_125K): FTB Personal Income Tax Booklet
#   "How to Figure Your Tax — Example: Chris and Pat Smith" (TY2021-TY2025),
#   MFJ, taxable income $125,000. Source: FTB-published rate-schedule worked
#   examples from each year's booklet.
#
# Oracle 4 (RATE_SCHEDULE_BOUNDARY_ANCHORS_2025): First dollar above the Tax
#   Table ($100,001) for TY2025 using Rate Schedule branch directly. Source:
#   hand-walked rate schedule by team-lead, verified independently by sp3.
# ---------------------------------------------------------------------------

# Oracle 1 — TY2025 Tax Table boundary anchors
# Format: (filing_status, taxable_income) -> expected tax
TAX_TABLE_BOUNDARY_ANCHORS_2025: dict[tuple[FilingStatus, int], int] = {
    # $50,000 — bin $49,951-$50,050 (regular 100-wide bin, midpoint $50,000.5)
    (FilingStatus.SINGLE,             50_000): 1_535,
    (FilingStatus.MARRIED_SEPARATELY, 50_000): 1_535,
    (FilingStatus.MARRIED_JOINTLY,    50_000):   778,
    (FilingStatus.QUALIFYING_WIDOW,   50_000):   778,
    (FilingStatus.HEAD_OF_HOUSEHOLD,  50_000):   778,
    # $100,000 — bin $99,951-$100,000 (TRUNCATED last bin, midpoint $99,975.5)
    (FilingStatus.SINGLE,            100_000): 5_736,
    (FilingStatus.MARRIED_SEPARATELY,100_000): 5_736,
    (FilingStatus.MARRIED_JOINTLY,   100_000): 3_068,
    (FilingStatus.QUALIFYING_WIDOW,  100_000): 3_068,
    (FilingStatus.HEAD_OF_HOUSEHOLD, 100_000): 3_708,
}

# Oracle 2 — trivial bins (status/year invariant)
# These hold for all supported CA years (see tenforty/years.py) and all filing statuses.
TRIVIAL_TAX_TABLE_BINS: list[int] = [0, 1, 25, 50]

# Oracle 3 — Chris+Pat MFJ $125k rate-schedule worked examples (FTB-published)
EXPECTED_CHRIS_PAT_MFJ_125K: dict[int, int] = {
    2025: 4_768,
    2024: 4_920,
    2023: 5_083,
    2022: 5_231,
    2021: 5_630,
}

# Oracle 4 — Rate Schedule branch boundary at $100,001 (TY2025, hand-walked)
RATE_SCHEDULE_BOUNDARY_ANCHORS_2025: dict[FilingStatus, int] = {
    # $100,001 — first dollar above the Tax Table; uses Rate Schedule branch
    FilingStatus.SINGLE:          5_739,
    FilingStatus.MARRIED_JOINTLY: 3_070,
}


class TaxTableBoundaryAnchors2025Tests(unittest.TestCase):
    """Oracle 1: TY2025 Tax Table boundary anchors at $50k and $100k."""

    def test_tax_table_boundary_anchors_2025(self):
        for (filing_status, taxable_income), expected in TAX_TABLE_BOUNDARY_ANCHORS_2025.items():
            with self.subTest(filing_status=filing_status, taxable_income=taxable_income):
                self.assertEqual(
                    compute_ca_tax(2025, filing_status, taxable_income),
                    expected,
                )


class TrivialTaxTableBinsTests(unittest.TestCase):
    """Oracle 2: Status/year-invariant zero-tax incomes."""

    def test_trivial_bins_all_years_all_statuses(self):
        all_statuses = list(FilingStatus)
        for year in range(2021, 2026):
            for status in all_statuses:
                for income in TRIVIAL_TAX_TABLE_BINS:
                    with self.subTest(year=year, status=status, income=income):
                        self.assertEqual(
                            compute_ca_tax(year, status, income),
                            0,
                        )


class ChrisPatMFJ125KTests(unittest.TestCase):
    """Oracle 3: FTB-published MFJ $125k rate-schedule worked examples."""

    def test_chris_pat_mfj_125k_all_years(self):
        for year, expected in EXPECTED_CHRIS_PAT_MFJ_125K.items():
            with self.subTest(year=year):
                self.assertEqual(
                    compute_ca_tax(year, FilingStatus.MARRIED_JOINTLY, 125_000),
                    expected,
                )


class RateScheduleBoundaryAnchors2025Tests(unittest.TestCase):
    """Oracle 4: Rate Schedule branch at $100,001 (TY2025)."""

    def test_rate_schedule_boundary_100001(self):
        for filing_status, expected in RATE_SCHEDULE_BOUNDARY_ANCHORS_2025.items():
            with self.subTest(filing_status=filing_status):
                self.assertEqual(
                    compute_ca_tax(2025, filing_status, 100_001),
                    expected,
                )


class HighIncomeBinMidpointTests(unittest.TestCase):
    """Regression pin for the midpoint-convention fix (Layer-2 oracle
    disagreement): the FTB Tax Table uses the integer bin midpoint."""

    def test_high_income_bin_uses_integer_midpoint(self):
        # FTB Tax Table 2024, bin $70,651–$70,750, Single column = $3,117.
        # The integer bin midpoint (70,700) reproduces it; the half-dollar
        # midpoint (70,700.5) rounds $1 high. Regression pin for the
        # midpoint-convention fix (Layer-2 oracle disagreement).
        self.assertEqual(
            compute_ca_tax(year=2024, filing_status=FilingStatus.SINGLE,
                           taxable_income=70_700),
            3_117)
        self.assertEqual(
            compute_ca_tax(year=2024, filing_status=FilingStatus.MARRIED_SEPARATELY,
                           taxable_income=70_700),
            3_117)


class ComputeCaTaxUnsupportedYearTests(unittest.TestCase):
    """Oracle 5: NotImplementedError contract for unsupported years."""

    def test_year_not_in_supported_range_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            compute_ca_tax(year=2020, filing_status=FilingStatus.SINGLE, taxable_income=50_000)
        self.assertIn("2020", str(ctx.exception))
        self.assertIn("2021", str(ctx.exception))
        self.assertIn("2025", str(ctx.exception))


class ComputePipelineWalkTests(unittest.TestCase):
    """Hand-walked oracles for compute() pipeline (TY2025)."""

    def test_ty2025_single_50k_no_credits(self):
        result = compute(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            federal_agi=50_000,
            ca_agi=50_000,
            ca540=CA540Return(),
        )
        self.assertEqual(result["f540_ca_agi"], 50_000)
        self.assertEqual(result["f540_deduction"], 5_706)
        self.assertEqual(result["f540_taxable_income"], 44_294)
        self.assertEqual(result["f540_ca_tax"], 1_193)
        self.assertEqual(result["f540_exemption_credit"], 153)
        self.assertEqual(result["f540_renter_credit"], 0)
        self.assertEqual(result["f540_total_credits"], 153)
        self.assertEqual(result["f540_total_liability"], 1_040)

    def test_ty2025_mfj_100k_two_dependents_no_renter(self):
        result = compute(
            year=2025,
            filing_status=FilingStatus.MARRIED_JOINTLY,
            federal_agi=100_000,
            ca_agi=100_000,
            ca540=CA540Return(),
            num_dependents=2,
        )
        self.assertEqual(result["f540_deduction"], 11_412)
        self.assertEqual(result["f540_taxable_income"], 88_588)
        self.assertEqual(result["f540_ca_tax"], 2_386)
        # 306 base + 2 × $475 dependent = 1,256
        self.assertEqual(result["f540_exemption_credit"], 1_256)
        self.assertEqual(result["f540_total_credits"], 1_256)
        self.assertEqual(result["f540_total_liability"], 1_130)

    def test_ty2025_single_40k_renter_eligible(self):
        result = compute(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            federal_agi=40_000,
            ca_agi=40_000,
            ca540=CA540Return(),
            renter_credit_eligible=True,
        )
        self.assertEqual(result["f540_taxable_income"], 34_294)
        self.assertEqual(result["f540_ca_tax"], 736)
        self.assertEqual(result["f540_exemption_credit"], 153)
        self.assertEqual(result["f540_renter_credit"], 60)
        self.assertEqual(result["f540_total_credits"], 213)
        self.assertEqual(result["f540_total_liability"], 523)


class AgiPhaseoutGateTests(unittest.TestCase):
    """AGI phaseout gate fires for federal_agi > AGI_PHASEOUT_THRESHOLD."""

    def test_phaseout_gate_fires_all_5_years(self):
        for year in range(2021, 2026):
            with self.subTest(year=year):
                params = ca_params.load(year)
                with self.assertRaises(NotImplementedError) as ctx:
                    compute(
                        year=year,
                        filing_status=FilingStatus.SINGLE,
                        federal_agi=params.agi_phaseout_threshold + 1,
                        ca_agi=50_000,
                        ca540=CA540Return(),
                    )
                self.assertIn(str(year), str(ctx.exception))
                self.assertIn("phaseout", str(ctx.exception).lower())

    def test_phaseout_gate_strict_at_threshold_does_not_fire(self):
        # At exactly the threshold, gate uses strict `>`, so does NOT fire.
        for year in range(2021, 2026):
            with self.subTest(year=year):
                params = ca_params.load(year)
                # Should not raise; produce a valid dict
                result = compute(
                    year=year,
                    filing_status=FilingStatus.SINGLE,
                    federal_agi=params.agi_phaseout_threshold,
                    ca_agi=50_000,
                    ca540=CA540Return(),
                )
                self.assertIsInstance(result, dict)


class ChrisPatMFJ125kFinalLiabilityTests(unittest.TestCase):
    """Cross-pipeline check: feed Chris+Pat MFJ $125k taxable through compute()."""

    def test_chris_pat_mfj_125k_pipeline_all_years(self):
        for year, expected_ca_tax in EXPECTED_CHRIS_PAT_MFJ_125K.items():
            with self.subTest(year=year):
                std_ded = EXPECTED_STANDARD_DEDUCTION[year][FilingStatus.MARRIED_JOINTLY]
                exemption = EXPECTED_EXEMPTION_CREDIT[year][FilingStatus.MARRIED_JOINTLY]
                ca_agi = 125_000 + std_ded
                result = compute(
                    year=year,
                    filing_status=FilingStatus.MARRIED_JOINTLY,
                    federal_agi=ca_agi,
                    ca_agi=ca_agi,
                    ca540=CA540Return(),
                )
                self.assertEqual(result["f540_taxable_income"], 125_000)
                self.assertEqual(result["f540_ca_tax"], expected_ca_tax)
                self.assertEqual(result["f540_total_liability"], expected_ca_tax - exemption)


class SignConventionTests(unittest.TestCase):
    """Verify sign convention for each line item in the final-liability formula."""

    BASELINE_KWARGS = dict(
        year=2025,
        filing_status=FilingStatus.SINGLE,
        federal_agi=50_000,
        ca_agi=50_000,
    )

    def test_voluntary_contribution_increases_liability(self):
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_vc = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(
                voluntary_contributions=[VoluntaryContribution("WLD", 50.0)],
            ),
        )
        self.assertEqual(
            with_vc["f540_total_liability"],
            baseline["f540_total_liability"] + 50,
        )

    def test_use_tax_increases_liability(self):
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_use = compute(**self.BASELINE_KWARGS, ca540=CA540Return(use_tax=25))
        self.assertEqual(
            with_use["f540_total_liability"],
            baseline["f540_total_liability"] + 25,
        )

    def test_estimated_tax_penalty_increases_liability(self):
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_pen = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(estimated_tax_penalty=15),
        )
        self.assertEqual(
            with_pen["f540_total_liability"],
            baseline["f540_total_liability"] + 15,
        )

    def test_estimated_payments_decreases_liability(self):
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_pay = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(estimated_payments=200),
        )
        self.assertEqual(
            with_pay["f540_total_liability"],
            baseline["f540_total_liability"] - 200,
        )

    def test_ptet_credit_decreases_liability(self):
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_ptet = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(ptet_credit=100),
        )
        self.assertEqual(
            with_ptet["f540_total_liability"],
            baseline["f540_total_liability"] - 100,
        )

    def test_ca_withholding_decreases_liability(self):
        # CA W-2 box-17 withholding (line 71) — omitted entirely until
        # 2026-07-16 (see loud comment at the balance term in f540.compute).
        baseline = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        with_wh = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(),
            ca_withholding=3_000,
        )
        self.assertEqual(
            with_wh["f540_total_liability"],
            baseline["f540_total_liability"] - 3_000,
        )


class VoluntaryContributionAggregationTests(unittest.TestCase):
    """CA540Return().voluntary_contributions defaults to []; explicit [] also
    yields $0; multi-item sums correctly."""

    BASELINE_KWARGS = dict(
        year=2025,
        filing_status=FilingStatus.SINGLE,
        federal_agi=50_000,
        ca_agi=50_000,
    )

    def test_default_voluntary_yields_zero(self):
        # CA540Return() defaults voluntary_contributions to []; replaces the
        # legacy None-pass case (the new signature requires CA540Return).
        result = compute(**self.BASELINE_KWARGS, ca540=CA540Return())
        self.assertEqual(result["f540_voluntary_contributions"], 0)

    def test_empty_list_voluntary_yields_zero(self):
        result = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(voluntary_contributions=[]),
        )
        self.assertEqual(result["f540_voluntary_contributions"], 0)

    def test_multiple_voluntary_contributions_sum(self):
        result = compute(
            **self.BASELINE_KWARGS,
            ca540=CA540Return(
                voluntary_contributions=[
                    VoluntaryContribution("WLD", 25.0),
                    VoluntaryContribution("KID", 30.0),
                    VoluntaryContribution("ALZ", 45.0),
                ],
            ),
        )
        self.assertEqual(result["f540_voluntary_contributions"], 100)


class CaWithholdingTests(unittest.TestCase):
    """CA W-2 box-17 withholding (Form 540 line 71).

    Regression coverage for the omission found 2026-07-16: forms/f540.py's
    final-liability balance had no withholding term at all, and
    ``f540_line71_ca_withholding`` was producer-less (the pdf mapping
    already read that exact key). See the loud comment at the balance
    term in f540.compute for the finding writeup.
    """

    BASELINE_KWARGS = dict(
        year=2025,
        filing_status=FilingStatus.SINGLE,
        federal_agi=50_000,
        ca_agi=50_000,
        ca540=CA540Return(),
    )

    def test_ca_withholding_appears_in_result(self):
        result = compute(**self.BASELINE_KWARGS, ca_withholding=3_000)
        self.assertEqual(result["f540_line71_ca_withholding"], 3_000)

    def test_zero_withholding_matches_pre_change_baseline(self):
        # Exact pre-change output for these inputs (the individual pieces
        # are separately pinned in ComputePipelineWalkTests.
        # test_ty2025_single_50k_no_credits); asserted here as a full-dict
        # equality so the new key/term can't silently perturb anything else.
        expected_pre_change = {
            "f540_ca_agi": 50_000,
            "f540_deduction": 5_706,
            "f540_taxable_income": 44_294,
            "f540_ca_tax": 1_193,
            "f540_exemption_credit": 153,
            "f540_renter_credit": 0,
            "f540_ptet_credit": 0,
            "f540_total_credits": 153,
            "f540_voluntary_contributions": 0,
            "f540_use_tax": 0,
            "f540_estimated_tax_penalty": 0,
            "f540_estimated_payments": 0,
            "f540_total_liability": 1_040,
            "f540_filing_status": FilingStatus.SINGLE,
        }
        omitted = compute(**self.BASELINE_KWARGS)
        explicit_zero = compute(**self.BASELINE_KWARGS, ca_withholding=0)
        self.assertEqual(omitted, explicit_zero)
        expected_with_new_key = {
            **expected_pre_change,
            "f540_line71_ca_withholding": 0,
        }
        self.assertEqual(omitted, expected_with_new_key)


class California2024ConstantsTests(unittest.TestCase):
    """Pin params/california/y2024.py to FTB-published 2024 values.

    This is the by-construction validation for the 2024 CA port: the CA
    compute logic is already validated for 2025 and reads everything from
    these per-year params, so correct 2024 params ⇒ correct 2024
    compute. Each value is confirmed against the FTB 2024 Form 540 booklet
    and 2024 California Tax Rate Schedules (booklet p. 75).
    """

    def setUp(self):
        self.params_2024 = ca_params.load(2024)

    def test_standard_deduction(self):
        # Source: FTB Form 540 (TY2024) side 2, line 18 worksheet
        self.assertEqual(self.params_2024.standard_deduction[FilingStatus.SINGLE.value], 5_540)
        self.assertEqual(self.params_2024.standard_deduction[FilingStatus.MARRIED_JOINTLY.value], 11_080)

    def test_exemption_credit(self):
        # Source: FTB Form 540 (TY2024) side 1, lines 7-10; per-person = $149
        self.assertEqual(self.params_2024.exemption_credit[FilingStatus.SINGLE.value], 149)      # 1 × $149
        self.assertEqual(self.params_2024.exemption_credit[FilingStatus.MARRIED_JOINTLY.value], 298)  # 2 × $149

    def test_dependent_exemption_and_phaseout(self):
        # Source: FTB Form 540 (TY2024) side 2, line 10 ($461 each)
        self.assertEqual(self.params_2024.dependent_exemption_amount, 461)
        # Source: FTB Form 540 (TY2024) side 2, line 32
        self.assertEqual(self.params_2024.agi_phaseout_threshold, 244_857)

    def test_rate_schedule_single_endpoints(self):
        # Source: FTB 2024 Tax Rate Schedules (booklet p. 75), Schedule X
        sched = self.params_2024.rate_schedule[FilingStatus.SINGLE.value]
        # 9 brackets; lowest bracket starts at 1% from $0
        self.assertEqual(len(sched), 9)
        self.assertEqual(sched[0], (0, 0.01))
        # Top marginal rate is 12.3% (1% mental-health surcharge above $1M
        # is handled separately, not as a RATE_SCHEDULE row)
        self.assertEqual(sched[-1][1], 0.123)

    def test_rate_schedule_mfj_endpoints(self):
        # Source: FTB 2024 Tax Rate Schedules (booklet p. 75), Schedule Y
        # MFJ thresholds are exactly 2× Schedule X
        sched = self.params_2024.rate_schedule[FilingStatus.MARRIED_JOINTLY.value]
        self.assertEqual(len(sched), 9)
        self.assertEqual(sched[0], (0, 0.01))
        self.assertEqual(sched[-1][1], 0.123)

    def test_renter_credit_single(self):
        # Source: FTB Personal Income Tax Booklet (TY2024) p. 25,
        # "Nonrefundable Renter's Credit Qualification Record" Q2 + Q11
        self.assertEqual(self.params_2024.renter_credit_agi_threshold[FilingStatus.SINGLE.value], 52_421)
        self.assertEqual(self.params_2024.renter_credit_amount[FilingStatus.SINGLE.value], 60)
