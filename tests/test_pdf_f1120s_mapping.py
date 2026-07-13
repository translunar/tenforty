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

    def test_2024_every_compute_key_is_accounted_for(self):
        """Partition invariant for 2024: same logic as the 2025 test."""
        mapping = pdf_f1120s.PdfF1120S.get_mapping(2024)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2024)
        suppressed = pdf_f1120s.PdfF1120S.get_suppressed(2024)

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

    def test_2024_every_pdf_target_is_a_real_pdf_field(self):
        """Every field path referenced in the 2024 registries must exist
        in pdfs/federal/2024/f1120s.pdf."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2024" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2024)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2024)
        derivations = pdf_f1120s.PdfF1120S.get_derivations(2024)

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

    def test_2024_checkbox_on_states_match_pdf_appearance_states(self):
        """Every on-state in `_CHECKBOX_STATES_2024` must be a real appearance
        state of its target checkbox/radio widget in the 2024 PDF.

        A wrong on-state (e.g. "/Yes" where the IRS XFA form uses "/1") would
        silently render as "/Off" — the value never gets checked. pypdf's
        get_fields() exposes the available appearance states for a /Btn field
        under the "/_States_" key (a list like ["/1", "/Off"]); this test
        asserts the mapped on-state is present in that list. The compute key →
        widget field path is resolved through `get_mapping(2024)`.
        """
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2024" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        fields = reader.get_fields() or {}

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2024)
        checkbox_states = pdf_f1120s.PdfF1120S.get_checkbox_states(2024)

        bad: list[str] = []
        for compute_key, on_state in checkbox_states.items():
            field_path = mapping[compute_key]
            field = fields.get(field_path)
            available = list(field.get("/_States_", [])) if field else []
            if on_state not in available:
                bad.append(
                    f"{compute_key}: on-state {on_state!r} not in widget "
                    f"states {available} for field {field_path!r}"
                )
        self.assertEqual(bad, [], "\n".join(bad))

    def test_2023_every_compute_key_is_accounted_for(self):
        """Partition invariant for 2023: same logic as the 2025/2024 tests."""
        mapping = pdf_f1120s.PdfF1120S.get_mapping(2023)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2023)
        suppressed = pdf_f1120s.PdfF1120S.get_suppressed(2023)

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

    def test_2023_every_pdf_target_is_a_real_pdf_field(self):
        """Every field path referenced in the 2023 registries must exist
        in pdfs/federal/2023/f1120s.pdf."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2023" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2023)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2023)
        derivations = pdf_f1120s.PdfF1120S.get_derivations(2023)

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

    def test_2023_checkbox_on_states_match_pdf_appearance_states(self):
        """Every on-state in the 2023 checkbox states must be a real appearance
        state of its target widget in the 2023 PDF (same check as 2024)."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2023" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        fields = reader.get_fields() or {}

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2023)
        checkbox_states = pdf_f1120s.PdfF1120S.get_checkbox_states(2023)

        bad: list[str] = []
        for compute_key, on_state in checkbox_states.items():
            field_path = mapping[compute_key]
            field = fields.get(field_path)
            available = list(field.get("/_States_", [])) if field else []
            if on_state not in available:
                bad.append(
                    f"{compute_key}: on-state {on_state!r} not in widget "
                    f"states {available} for field {field_path!r}"
                )
        self.assertEqual(bad, [], "\n".join(bad))

    def test_2023_tax_exempt_interest_maps_to_schedule_k_line_16a(self):
        """Renumbering pin: on the 2023 Schedule K, line 16a "Tax-exempt
        interest income" is field f3_42 (verified by filled-emit on the real
        template; probe render pdfs/federal/2023/f1120s.probe.pdf). The IRS
        shifted the Schedule K AMT/other-items block by one field between years,
        so line 16a is f3_42 in 2023 but f3_43 in 2024/2025 — BOTH correct for
        their own year (filled-emit-confirmed on each template; f3_43 is line
        16b "Other tax-exempt income" on the 2023 form, but line 16a on the
        2024/2025 forms). This pin guards 2023 against a silent inherit of
        2024's f3_43, which on the 2023 form would land the value on line 16b."""
        m2023 = pdf_f1120s.PdfF1120S.get_mapping(2023)
        self.assertEqual(
            m2023["f1120s_sch_k_tax_exempt_interest"],
            "topmostSubform[0].Page3[0].f3_42[0]",
        )
        # And it genuinely differs from the 2024 mapping (f3_43).
        self.assertNotEqual(
            m2023["f1120s_sch_k_tax_exempt_interest"],
            pdf_f1120s.PdfF1120S.get_mapping(2024)["f1120s_sch_k_tax_exempt_interest"],
        )

    def test_2022_every_compute_key_is_accounted_for(self):
        """Partition invariant for 2022: same logic as the 2023-2025 tests."""
        mapping = pdf_f1120s.PdfF1120S.get_mapping(2022)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2022)
        suppressed = pdf_f1120s.PdfF1120S.get_suppressed(2022)

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

    def test_2022_every_pdf_target_is_a_real_pdf_field(self):
        """Every field path referenced in the 2022 registries must exist
        in pdfs/federal/2022/f1120s.pdf."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2022" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2022)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2022)
        derivations = pdf_f1120s.PdfF1120S.get_derivations(2022)

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

    def test_2022_checkbox_on_states_match_pdf_appearance_states(self):
        """Every on-state in the 2022 checkbox states must be a real appearance
        state of its target widget in the 2022 PDF (same check as 2023/2024)."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2022" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        fields = reader.get_fields() or {}

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2022)
        checkbox_states = pdf_f1120s.PdfF1120S.get_checkbox_states(2022)

        bad: list[str] = []
        for compute_key, on_state in checkbox_states.items():
            field_path = mapping[compute_key]
            field = fields.get(field_path)
            available = list(field.get("/_States_", [])) if field else []
            if on_state not in available:
                bad.append(
                    f"{compute_key}: on-state {on_state!r} not in widget "
                    f"states {available} for field {field_path!r}"
                )
        self.assertEqual(bad, [], "\n".join(bad))

    def test_2022_structural_delta_vs_2023(self):
        """Pins the two 2022-vs-2023 structural differences (filled-emit-
        confirmed on pdfs/federal/2022/f1120s.probe.pdf):

        1. 2022 lacks 2023's line-19 "Energy efficient commercial buildings
           (Form 7205)" field, so every mapped field from line 19 onward is
           2023's minus one — e.g. Other deductions is f1_33 (2023: f1_34).
        2. 2022 lacks 2023's line-24d "Elective payment election (Form 3800)"
           field, so `f1120s_refundable_credits` (2023: mapped to that cell)
           is SUPPRESSED, not mapped.

        Schedule K line 16a tax-exempt interest is f3_42, same as 2023 (the
        2024/2025 f3_43 shift does not reach back to 2022)."""
        m2022 = pdf_f1120s.PdfF1120S.get_mapping(2022)
        self.assertEqual(
            m2022["f1120s_other_deductions"],
            "topmostSubform[0].Page1[0].f1_33[0]",
        )
        self.assertNotIn("f1120s_refundable_credits", m2022)
        self.assertIn(
            "f1120s_refundable_credits",
            pdf_f1120s.PdfF1120S.get_suppressed(2022),
        )
        self.assertEqual(
            m2022["f1120s_sch_k_tax_exempt_interest"],
            "topmostSubform[0].Page3[0].f3_42[0]",
        )

    def test_2021_every_compute_key_is_accounted_for(self):
        """Partition invariant for 2021: same logic as the 2022-2025 tests.
        2021 inherits the 2022 mapping verbatim, so the same partition holds."""
        mapping = pdf_f1120s.PdfF1120S.get_mapping(2021)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2021)
        suppressed = pdf_f1120s.PdfF1120S.get_suppressed(2021)

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

    def test_2021_every_pdf_target_is_a_real_pdf_field(self):
        """Every field path referenced in the 2021 registries must exist
        in pdfs/federal/2021/f1120s.pdf."""
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2021" / "f1120s.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f1120s.PdfF1120S.get_mapping(2021)
        aggregations = pdf_f1120s.PdfF1120S.get_aggregations(2021)
        derivations = pdf_f1120s.PdfF1120S.get_derivations(2021)

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
