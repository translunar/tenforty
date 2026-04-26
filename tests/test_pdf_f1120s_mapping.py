"""Mapping-shape and placeholder-sweep tests for Form 1120-S PDF mapping.

Per-field-path correctness lives in the probe artifact (docs/plans/
t14-f1120s-probe.md); this test only verifies that (a) every compute
output key has a mapping entry and (b) no mapping entry references a
non-existent PDF field path.
"""

from pathlib import Path
import unittest

from pypdf import PdfReader

from tenforty.mappings import pdf_f1120s


_EXPECTED_COMPUTE_KEYS = frozenset({
    "f1120s_gross_receipts",
    "f1120s_returns_and_allowances",
    "f1120s_net_receipts",
    "f1120s_cost_of_goods_sold",
    "f1120s_gross_profit",
    "f1120s_net_gain_loss_4797",
    "f1120s_other_income",
    "f1120s_total_income",
    "f1120s_compensation_of_officers",
    "f1120s_salaries_wages",
    "f1120s_repairs_maintenance",
    "f1120s_bad_debts",
    "f1120s_rents",
    "f1120s_taxes_licenses",
    "f1120s_interest",
    "f1120s_depreciation",
    "f1120s_depletion",
    "f1120s_advertising",
    "f1120s_pension_profit_sharing",
    "f1120s_employee_benefits",
    "f1120s_other_deductions",
    "f1120s_total_deductions",
    "f1120s_ordinary_business_income",
    "f1120s_net_passive_income_tax",
    "f1120s_built_in_gains_tax",
    "f1120s_interest_on_453_deferred",
    "f1120s_total_tax",
    "f1120s_estimated_tax_payments",
    "f1120s_prior_year_overpayment_credited",
    "f1120s_tax_deposited_with_7004",
    "f1120s_credit_for_federal_excise_tax",
    "f1120s_refundable_credits",
    "f1120s_total_payments",
    "f1120s_amount_owed",
    "f1120s_estimated_tax_penalty",
    "f1120s_overpayment",
    "f1120s_credited_to_next_year",
    "f1120s_sch_b_accounting_method_cash",
    "f1120s_sch_b_accounting_method_accrual",
    "f1120s_sch_b_accounting_method_other",
    "f1120s_sch_b_business_activity_code",
    "f1120s_sch_b_business_activity_description",
    "f1120s_sch_b_product_or_service",
    "f1120s_sch_b_any_c_corp_subsidiaries",
    "f1120s_sch_b_has_any_foreign_shareholders",
    "f1120s_sch_b_owns_foreign_entity",
    "f1120s_sch_k_ordinary_business_income",
    "f1120s_sch_k_net_rental_real_estate",
    "f1120s_sch_k_other_net_rental_income",
    "f1120s_sch_k_interest_income",
    "f1120s_sch_k_ordinary_dividends",
    "f1120s_sch_k_royalties",
    "f1120s_sch_k_net_short_term_capital_gain",
    "f1120s_sch_k_net_long_term_capital_gain",
    "f1120s_sch_k_net_section_1231_gain",
    "f1120s_sch_k_other_income",
    "f1120s_sch_k_section_179_deduction",
    "f1120s_sch_k_charitable_contributions",
    "f1120s_sch_k_low_income_housing_credit",
    "f1120s_sch_k_tax_exempt_interest",
    "f1120s_sch_k_investment_income",
    "f1120s_sch_k_income_loss_reconciliation",
})


class PdfF1120SMappingTests(unittest.TestCase):
    def test_2025_every_compute_key_is_accounted_for(self):
        """Partition invariant: every expected compute key is OWNED by
        exactly one of `_MAPPING_2025`, `_AGGREGATIONS_2025`, or
        `_SUPPRESSED_2025`. No orphans (every key is owned somewhere)
        and no double-accounting (a key may not be owned by two
        registries).

        Derivation lambdas (`_DERIVATIONS_2025`) CONSUME compute keys
        but do not OWN them — a derivation may only reference keys that
        are already owned by mapping/aggregations/suppressed. This test
        enforces ownership; derivation consumption is intentionally
        excluded from the partition.
        """
        mapping = pdf_f1120s.PdfF1120S.get_mapping(2025)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2025)
        suppressed = pdf_f1120s.PdfF1120S.get_suppressed(2025)

        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed

        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(
            missing, set(),
            f"{len(missing)} compute keys are unaccounted for: {sorted(missing)}",
        )

        in_mapping = set(mapping.keys())
        double = (
            (in_mapping & agg_contributors)
            | (in_mapping & suppressed)
            | (agg_contributors & suppressed)
        )
        self.assertEqual(
            double, set(),
            f"{len(double)} keys are double-accounted: {sorted(double)}",
        )

    def test_2025_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/federal/2025/f1120s.pdf."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2025" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2025)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2025)
        derivations = pdf_f1120s.PdfF1120S.get_derivations(2025)

        all_targets = (
            set(mapping.values())
            | set(aggregations.keys())
            | set(derivations.keys())
        )
        bad = sorted(p for p in all_targets if p not in real_fields)
        self.assertEqual(
            bad, [],
            f"{len(bad)} mapped/aggregated/derived field paths do not exist in the PDF: {bad}",
        )
