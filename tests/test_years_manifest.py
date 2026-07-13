# tests/test_years_manifest.py
"""The manifest is the single source of truth for year support.

Structural invariants only — whether a declared year actually has a
complete pack is the (future) completeness gate's job, not this test's.
"""
import unittest

from tenforty import years as year_manifest


class YearManifestTests(unittest.TestCase):
    def test_year_tuples_are_sorted_ints(self):
        for name in ("FEDERAL_YEARS", "FEDERAL_COMPUTE_ONLY_YEARS",
                     "CALIFORNIA_YEARS",
                     "CALIFORNIA_COMPUTE_ONLY_YEARS", "WORKBOOK_YEARS"):
            with self.subTest(tuple=name):
                years = getattr(year_manifest, name)
                self.assertTrue(all(isinstance(y, int) for y in years))
                self.assertEqual(tuple(sorted(years)), years)

    def test_workbook_years_subset_of_supported_federal(self):
        # A workbook year must be a SUPPORTED federal year — full PDF-pack
        # (FEDERAL_YEARS) OR compute-only (FEDERAL_COMPUTE_ONLY_YEARS). A
        # compute-only year may still carry a vendor workbook as a BONUS
        # acceptance oracle (penny-parity over its declared surface) even
        # though it emits no PDF pack — e.g. TY2021, whose workbook is wired
        # as a bounded partial (Form 8582 tab absent -> excluded keys).
        supported = (set(year_manifest.FEDERAL_YEARS)
                     | set(year_manifest.FEDERAL_COMPUTE_ONLY_YEARS))
        self.assertTrue(set(year_manifest.WORKBOOK_YEARS) <= supported)

    def test_compute_only_disjoint_from_full_california(self):
        self.assertEqual(
            set(year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS)
            & set(year_manifest.CALIFORNIA_YEARS),
            set())

    def test_compute_only_disjoint_from_full_federal(self):
        # A federal year is either fully supported (PDF pack) or compute-only,
        # never both — no silent half-support in the federal grid either.
        self.assertEqual(
            set(year_manifest.FEDERAL_COMPUTE_ONLY_YEARS)
            & set(year_manifest.FEDERAL_YEARS),
            set())

    def test_compute_only_forms_exclude_scorp(self):
        # The compute-only federal form set is the individual-return family;
        # the S-corp pair belongs to the S-corp packet workstream's tier.
        self.assertNotIn("f1120s", year_manifest.FEDERAL_COMPUTE_ONLY_FORMS)
        self.assertNotIn("f1120s_k1", year_manifest.FEDERAL_COMPUTE_ONLY_FORMS)
        self.assertEqual(
            set(year_manifest.FEDERAL_COMPUTE_ONLY_FORMS),
            set(year_manifest.FEDERAL_FORMS) - {"f1120s", "f1120s_k1"})

    def test_form_sets_nonempty_and_unique(self):
        for name in ("FEDERAL_FORMS", "CALIFORNIA_FORMS"):
            with self.subTest(tuple=name):
                forms = getattr(year_manifest, name)
                self.assertGreater(len(forms), 0)
                self.assertEqual(len(set(forms)), len(forms))

    def test_describe_joins_sorted(self):
        self.assertEqual(year_manifest.describe((2025, 2021, 2024)),
                         "2021, 2024, 2025")
