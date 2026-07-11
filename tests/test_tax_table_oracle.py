# tests/test_tax_table_oracle.py
"""Layer-2 oracle: the ingested published tax tables must agree with the
params-driven computation for every bin.

Federal: the IRS builds each bin's tax as the rate schedule applied to the
bin midpoint, rounded — so every row cross-validates BOTH the ingested CSV
and params.ordinary_brackets. Sweep scope is the single column (the spine's
ordinary_brackets are single-filer; other statuses are outside spine scope).

California: compute_ca_tax already implements the FTB bin-midpoint method;
the sweep proves it against the actual published table, all four columns.
"""
import unittest

from tenforty import years as year_manifest
from tenforty.forms.f1040_tax import tax_from_schedule
from tenforty.forms.f540 import compute_ca_tax
from tenforty.models import FilingStatus
from tenforty.params.federal import load as load_federal
from tenforty.rounding import irs_round
from tenforty.tax_table import TABLE_CEILING, load_table, tax_from_table

_CA_COLUMN_STATUS = (
    ("single", FilingStatus.SINGLE),
    ("mfj", FilingStatus.MARRIED_JOINTLY),
    ("mfs", FilingStatus.MARRIED_SEPARATELY),
    ("hoh", FilingStatus.HEAD_OF_HOUSEHOLD),
)


class FederalTableSweepTests(unittest.TestCase):
    def test_every_bin_matches_rate_schedule_at_midpoint(self):
        for year in year_manifest.FEDERAL_YEARS:
            params = load_federal(year)
            rows = load_table("federal", year)
            self.assertGreater(len(rows), 1_000)
            mismatches = []
            for lower, upper, taxes in rows:
                midpoint = (lower + upper) / 2
                expected = irs_round(tax_from_schedule(midpoint, params))
                if expected != taxes["single"]:
                    mismatches.append((lower, upper, taxes["single"], expected))
            self.assertEqual(
                mismatches[:10], [],
                f"{year}: {len(mismatches)} bins disagree "
                f"(first shown as (lower, upper, published, computed))")

    def test_lookup_returns_published_value(self):
        for year in year_manifest.FEDERAL_YEARS:
            rows = load_table("federal", year)
            lower, upper, taxes = rows[len(rows) // 2]
            self.assertEqual(
                tax_from_table(lower, year, FilingStatus.SINGLE),
                taxes["single"])
            self.assertEqual(
                tax_from_table(upper - 1, year, FilingStatus.SINGLE),
                taxes["single"])

    def test_qss_uses_mfj_column(self):
        year = year_manifest.FEDERAL_YEARS[-1]
        rows = load_table("federal", year)
        lower, _, taxes = rows[len(rows) // 2]
        self.assertEqual(
            tax_from_table(lower, year, FilingStatus.QUALIFYING_WIDOW),
            taxes["mfj"])

    def test_lookup_rejects_income_at_or_above_ceiling(self):
        year = year_manifest.FEDERAL_YEARS[-1]
        with self.assertRaises(ValueError):
            tax_from_table(TABLE_CEILING, year, FilingStatus.SINGLE)


class CaliforniaTableSweepTests(unittest.TestCase):
    def test_every_bin_matches_compute_ca_tax(self):
        for year in year_manifest.CALIFORNIA_YEARS:
            rows = load_table("california", year)
            self.assertGreater(len(rows), 500)
            mismatches = []
            for lower, upper, taxes in rows:
                probe_income = (lower + upper) / 2
                for column, status in _CA_COLUMN_STATUS:
                    computed = compute_ca_tax(
                        year=year, filing_status=status,
                        taxable_income=probe_income)
                    if computed != taxes[column]:
                        mismatches.append(
                            (lower, upper, column, taxes[column], computed))
            self.assertEqual(
                mismatches[:10], [],
                f"{year}: {len(mismatches)} bin/status cells disagree")
