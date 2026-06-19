import math
import unittest

from tenforty.params.federal import load
from tenforty.models import FilingStatus


class FederalParamsTests(unittest.TestCase):
    def test_2025_single_structure_and_spot_values(self):
        p = load(2025)
        single = FilingStatus.SINGLE.value
        # 2025 standard deduction, single (IRS published).
        self.assertEqual(p.standard_deduction[single], 15_750)
        # QDCGT 0%/15% breakpoints, single (IRS published 2025).
        self.assertEqual(p.qdcgt_breakpoints[single], (48_350, 533_400))
        # Additional Medicare threshold, single.
        self.assertEqual(p.addl_medicare_threshold[single], 200_000)
        # Brackets ascend and terminate at infinity.
        bounds = [b for b, _ in p.ordinary_brackets]
        self.assertEqual(bounds, sorted(bounds))
        self.assertTrue(math.isinf(p.ordinary_brackets[-1][0]))

    def test_2024_single_spot_values(self):
        p = load(2024)
        single = FilingStatus.SINGLE.value
        self.assertEqual(p.standard_deduction[single], 14_600)
        self.assertEqual(p.qdcgt_breakpoints[single], (47_025, 518_900))
        self.assertEqual(p.addl_medicare_threshold[single], 200_000)
        # 2024 SALT cap was flat $10k (pre-OBBBA).
        self.assertEqual(p.salt_cap_starting["single"], 10_000)
        self.assertIsNone(p.salt_phaseout_threshold)

    def test_2025_eic_income_ceiling_spot_values(self):
        # 2025 MFJ EITC maximum-AGI limits (Rev. Proc. 2024-40), used as the
        # orchestrator's conservative scope-gate threshold. Pinned so a future
        # from-memory edit can't silently regress them (a too-low ceiling would
        # admit possibly-EIC-eligible single filers to the no-EIC native spine).
        p = load(2025)
        self.assertEqual(
            p.eic_income_ceiling,
            {0: 26_214, 1: 57_554, 2: 64_430, 3: 68_675},
        )

    def test_unknown_year_raises(self):
        with self.assertRaises(ValueError):
            load(1999)


class FederalParamsSaltStructureTests(unittest.TestCase):
    def test_2025_salt_cap_starting_single_and_mfs(self):
        p = load(2025)
        self.assertEqual(p.salt_cap_starting["single"], 40_000)
        self.assertEqual(p.salt_cap_starting["married_separately"], 20_000)
        self.assertEqual(p.salt_cap_starting["married_jointly"], 40_000)
        self.assertEqual(p.salt_cap_starting["head_of_household"], 40_000)
        self.assertEqual(p.salt_cap_starting["qualifying_widow"], 40_000)

    def test_2025_salt_phaseout_threshold_and_rate(self):
        p = load(2025)
        self.assertEqual(p.salt_phaseout_threshold, 500_000)
        self.assertAlmostEqual(p.salt_phaseout_rate, 0.30)

    def test_2025_salt_cap_floor(self):
        p = load(2025)
        self.assertEqual(p.salt_cap_floor["single"], 10_000)
        self.assertEqual(p.salt_cap_floor["married_separately"], 5_000)

    def test_2024_salt_cap_starting_flat_no_phaseout(self):
        p = load(2024)
        self.assertEqual(p.salt_cap_starting["single"], 10_000)
        self.assertEqual(p.salt_cap_starting["married_separately"], 5_000)
        self.assertIsNone(p.salt_phaseout_threshold)
        self.assertEqual(p.salt_phaseout_rate, 0.0)

    def test_2024_salt_cap_floor_equals_starting(self):
        p = load(2024)
        self.assertEqual(p.salt_cap_floor["single"], 10_000)
        self.assertEqual(p.salt_cap_floor["married_separately"], 5_000)


class FederalParamsMedicalAndPriorSaltTests(unittest.TestCase):
    def test_medical_agi_floor_pct_both_years(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                p = load(year)
                self.assertAlmostEqual(p.medical_agi_floor_pct, 0.075)

    def test_2025_prior_year_salt_cap_single(self):
        """2025 return looks back to 2024 — pre-OBBBA $10k / $5k MFS."""
        p = load(2025)
        self.assertEqual(p.prior_year_salt_cap["single"], 10_000)
        self.assertEqual(p.prior_year_salt_cap["married_separately"], 5_000)
        self.assertEqual(p.prior_year_salt_cap["married_jointly"], 10_000)

    def test_2024_prior_year_salt_cap_single(self):
        """2024 return looks back to 2023 — also $10k / $5k MFS."""
        p = load(2024)
        self.assertEqual(p.prior_year_salt_cap["single"], 10_000)
        self.assertEqual(p.prior_year_salt_cap["married_separately"], 5_000)


class FederalParamsQbiThresholdTests(unittest.TestCase):
    def test_2025_qbi_threshold_all_statuses(self):
        p = load(2025)
        self.assertEqual(p.qbi_threshold["single"], 197_300)
        self.assertEqual(p.qbi_threshold["married_separately"], 197_300)
        self.assertEqual(p.qbi_threshold["head_of_household"], 197_300)
        self.assertEqual(p.qbi_threshold["married_jointly"], 394_600)
        self.assertEqual(p.qbi_threshold["qualifying_widow"], 394_600)

    def test_2024_qbi_threshold_single(self):
        """2024 single QBI threshold (Rev. Proc. 2023-34)."""
        p = load(2024)
        self.assertEqual(p.qbi_threshold["single"], 191_950)
        self.assertEqual(p.qbi_threshold["married_jointly"], 383_900)
