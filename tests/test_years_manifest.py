# tests/test_years_manifest.py
"""The manifest is the single source of truth for year support.

Structural invariants only — whether a declared year actually has a
complete pack is the (future) completeness gate's job, not this test's.
"""
import unittest

from tenforty import years as year_manifest


class YearManifestTests(unittest.TestCase):
    def test_year_tuples_are_sorted_ints(self):
        for name in ("FEDERAL_YEARS", "CALIFORNIA_YEARS",
                     "CALIFORNIA_COMPUTE_ONLY_YEARS", "WORKBOOK_YEARS"):
            with self.subTest(tuple=name):
                years = getattr(year_manifest, name)
                self.assertTrue(all(isinstance(y, int) for y in years))
                self.assertEqual(tuple(sorted(years)), years)

    def test_workbook_years_subset_of_federal(self):
        self.assertTrue(
            set(year_manifest.WORKBOOK_YEARS) <= set(year_manifest.FEDERAL_YEARS))

    def test_compute_only_disjoint_from_full_california(self):
        self.assertEqual(
            set(year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS)
            & set(year_manifest.CALIFORNIA_YEARS),
            set())

    def test_form_sets_nonempty_and_unique(self):
        for name in ("FEDERAL_FORMS", "CALIFORNIA_FORMS"):
            with self.subTest(tuple=name):
                forms = getattr(year_manifest, name)
                self.assertGreater(len(forms), 0)
                self.assertEqual(len(set(forms)), len(forms))

    def test_describe_joins_sorted(self):
        self.assertEqual(year_manifest.describe((2025, 2021, 2024)),
                         "2021, 2024, 2025")
