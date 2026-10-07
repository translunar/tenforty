"""Filled-emit verification for the California Form 100S PDF mapping.

Mirrors tests/test_pdf_mapping.py: fill known synthetic values through the real
PdfFiller against each year's real template, reopen, and assert /V read-back.
Because the AcroForm field-name namespace differs by year (bare "1031" for
2021-2023, "100S Form 1031" for 2024-2025), every check is driven off the
per-year mapping, and the blank-stays-blank guard is year-aware.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f100s import PdfF100S
from tests.helpers import REPO_ROOT

_EXPECTED_MAPPED_KEYS = frozenset({
    "f100s_federal_ordinary_income", "f100s_state_tax_addback",
    "f100s_depreciation_adjustment", "f100s_net_income_for_tax",
    "f100s_franchise_tax", "f100s_total_tax",
    "f100s_total_tax_after_other_taxes", "f100s_payments_balance",
    "f100s_prior_year_overpayment_applied",
    "f100s_estimated_tax_payments", "f100s_total_payments",
    "f100s_amount_owed", "f100s_overpayment", "f100s_tax_rate",
    "f100s_entity_name", "f100s_entity_ca_corp_number", "f100s_entity_fein",
    "f100s_entity_street", "f100s_entity_city", "f100s_entity_state", "f100s_entity_zip",
    "f100s_entity_date_incorporated", "f100s_entity_s_election_date",
    "f100s_entity_state_incorporated", "f100s_entity_country_incorporated",
    "f100s_entity_activity_code", "f100s_entity_business_activity",
    "f100s_entity_product_or_service", "f100s_entity_max_shareholders",
    "f100s_entity_date_began_in_ca",
    "f100s_entity_unclaimed_date", "f100s_entity_unclaimed_dollars",
    "f100s_entity_unclaimed_cents", "f100s_entity_officer_title",
    "f100s_entity_tax_year_begin", "f100s_entity_tax_year_end",
    "f100s_total_additions", "f100s_total_state_deductions",
    "f100s_net_income_after_adjustments",
    "f100s_net_income_for_state_purposes", "f100s_total_amount_due",
    "f100s_sch_f_gross_receipts", "f100s_sch_f_returns_allowances",
    "f100s_sch_f_net_receipts", "f100s_sch_f_cogs", "f100s_sch_f_gross_profit",
    "f100s_sch_f_net_gain_loss", "f100s_sch_f_other_income",
    "f100s_sch_f_total_income", "f100s_sch_f_officer_comp",
    "f100s_sch_f_salaries_wages", "f100s_sch_f_repairs",
    "f100s_sch_f_bad_debts", "f100s_sch_f_rents", "f100s_sch_f_taxes",
    "f100s_sch_f_interest", "f100s_sch_f_depreciation_balance",
    "f100s_sch_f_depletion", "f100s_sch_f_advertising", "f100s_sch_f_pension",
    "f100s_sch_f_employee_benefits", "f100s_sch_f_other_deductions",
    "f100s_sch_f_total_deductions", "f100s_sch_f_ordinary_income",
    "f100s_sch_k_line1_federal", "f100s_sch_k_line1_ca_adjustment",
    "f100s_sch_k_line1_ca_total", "f100s_sch_k_line19_federal",
    "f100s_sch_k_line19_ca_adjustment", "f100s_sch_k_line19_ca_total",
})

# Distinctive synthetic fill values: financial = distinct multiples of 50 under
# 1000 (no thousands-comma formatting to normalize); identity = obviously-fake
# strings. None resemble real data (PII scanner-safe).
_FILL = {
    "f100s_federal_ordinary_income": 50,
    "f100s_state_tax_addback": 100,
    "f100s_depreciation_adjustment": 150,
    "f100s_net_income_for_tax": 200,
    "f100s_franchise_tax": 250,
    "f100s_total_tax": 550,
    "f100s_total_tax_after_other_taxes": 600,
    "f100s_payments_balance": 650,
    "f100s_prior_year_overpayment_applied": 300,
    "f100s_estimated_tax_payments": 350,
    "f100s_total_payments": 400,
    "f100s_amount_owed": 450,
    "f100s_overpayment": 500,
    # Rate box is a formatted percentage string at emit; distinctive here.
    "f100s_tax_rate": "9.9",
    "f100s_entity_name": "TESTCORP",
    "f100s_entity_ca_corp_number": "9999999",
    "f100s_entity_fein": "00-0000000",
    "f100s_entity_street": "1 TEST AVE",
    "f100s_entity_city": "TESTCITY",
    "f100s_entity_state": "TS",
    "f100s_entity_zip": "00000",
}


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "california" / str(year) / "f100s.pdf"


def _guard_field(year: int) -> str:
    """Blank-guard field (Side-2 line 9 dividends-received-deduction) in the
    year's own namespace: bare for 2021-2023, prefixed for 2024-2025."""
    return "2001" if year <= 2023 else "100S Form 2001"


class PdfF100SMappingTests(unittest.TestCase):
    def test_every_mapped_key_present_for_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                self.assertEqual(set(PdfF100S.get_mapping(year)),
                                 _EXPECTED_MAPPED_KEYS)

    def test_every_target_is_a_real_pdf_field(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                real = set(PdfReader(_template(year)).get_fields() or {})
                bad = sorted(p for p in PdfF100S.get_mapping(year).values()
                             if p not in real)
                self.assertEqual(bad, [])

    def test_filled_emit_round_trip(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                mapping = PdfF100S.get_mapping(year)
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
                    # blank-stays-blank guard: an unmapped Side-2 field (line 9
                    # dividends-received-deduction) must remain empty.
                    guard = fields.get(_guard_field(year))
                    if guard is not None:
                        self.assertEqual((guard.get("/V") or ""), "")
