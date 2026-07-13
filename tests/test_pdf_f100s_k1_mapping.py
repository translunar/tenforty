"""Filled-emit verification for the California Schedule K-1 (100S) PDF mapping.

Mirrors tests/test_pdf_f100s_mapping.py: fill known synthetic values through the
real PdfFiller against each year's real template (one PDF per shareholder),
reopen, and assert /V read-back. Because the AcroForm field-name namespace
differs by revision (bare "1029" for 2021-2023, "Sch K-1 (100s) 1030 A" for
2024-2025), every check is driven off the per-year mapping, and the
blank-stays-blank guard is year-aware.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f100s_k1 import PdfF100SK1
from tests.helpers import REPO_ROOT

_EXPECTED_MAPPED_KEYS = frozenset({
    "k1_shareholder_name", "k1_shareholder_id", "k1_corp_fein",
    "k1_corp_ca_number", "k1_corp_name", "k1_ownership_pct_whole",
    "k1_ownership_pct_frac", "k1_federal_ordinary_income",
    "k1_ca_ordinary_income_total", "k1_ca_ordinary_income_source",
})

# Distinctive synthetic fill values: financial = distinct multiples of 50 under
# 1000 (no thousands-comma formatting to normalize); identity = obviously-fake
# strings. None resemble real data (PII scanner-safe).
_FILL = {
    "k1_shareholder_name": "SHNAME",
    "k1_shareholder_id": "000-00-0000",
    "k1_corp_fein": "00-0000000",
    "k1_corp_ca_number": "0000000",
    "k1_corp_name": "CORPNAME",
    "k1_ownership_pct_whole": "60",
    "k1_ownership_pct_frac": "12",
    "k1_federal_ordinary_income": 50,
    "k1_ca_ordinary_income_total": 100,
    "k1_ca_ordinary_income_source": 150,
}


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "california" / str(year) / "f100s_k1.pdf"


def _guard_field(year: int) -> str:
    """Blank-guard field (Side-1 calendar-year date field) in the year's own
    namespace: bare for 2021-2023, prefixed for 2024-2025. NOT one of the ten
    mapped targets."""
    return "1001" if year <= 2023 else "Sch K-1 (100s) 1001"


class PdfF100SK1MappingTests(unittest.TestCase):
    def test_every_mapped_key_present_for_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                self.assertEqual(set(PdfF100SK1.get_mapping(year)),
                                 _EXPECTED_MAPPED_KEYS)

    def test_every_target_is_a_real_pdf_field(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                real = set(PdfReader(_template(year)).get_fields() or {})
                bad = sorted(p for p in PdfF100SK1.get_mapping(year).values()
                             if p not in real)
                self.assertEqual(bad, [])

    def test_filled_emit_round_trip(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                mapping = PdfF100SK1.get_mapping(year)
                template = _template(year)
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "filled.pdf"
                    PdfFiller().fill(template, out, mapping, _FILL)
                    fields = PdfReader(out).get_fields() or {}
                    for key, expected in _FILL.items():
                        got = (fields[mapping[key]].get("/V") or "")
                        norm = str(got).replace(",", "").replace("$", "").strip()
                        self.assertEqual(norm, str(expected),
                                         f"{year} {key} -> {mapping[key]}")
                    # blank-stays-blank guard: an unmapped Side-1 field (the
                    # calendar-year date field) must remain empty.
                    guard = fields.get(_guard_field(year))
                    if guard is not None:
                        self.assertEqual((guard.get("/V") or ""), "")
