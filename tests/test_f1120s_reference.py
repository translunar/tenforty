"""Unit tests of the Form 1120-S reference oracle's OWN arithmetic.

These pin the hand-coded oracle in ``tests/oracles/f1120s_reference.py``
against expected values worked by hand from the IRS form faces. They do NOT
compare against any production compute -- that battery is a separate task.

All scenarios are fully synthetic; every input amount is divisible by $50,
with ONE documented exception: ``TestNoRoundingAtEntityLevel`` carries cents
(team-lead ruling) to pin the charter's no-rounding rule.
Inputs are plain stand-in objects with the S-corp input schema's attribute
names (the oracle is duck-typed and imports nothing from ``tenforty``).
"""

import unittest
from types import SimpleNamespace

from tests.oracles import f1120s_reference as oracle

ALL_YEARS = (2021, 2022, 2023, 2024, 2025)


def make_income(**overrides):
    fields = dict(
        gross_receipts=500_000.0,
        returns_and_allowances=20_000.0,
        cogs_aggregate=150_000.0,
        net_gain_loss_4797=5_000.0,
        other_income=2_500.0,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def make_deductions(**overrides):
    fields = dict(
        compensation_of_officers=80_000.0,
        salaries_wages=60_000.0,
        repairs_maintenance=3_000.0,
        bad_debts=1_000.0,
        rents=24_000.0,
        taxes_licenses=9_000.0,
        interest=2_000.0,
        depreciation=12_000.0,
        depletion=500.0,
        advertising=4_000.0,
        pension_profit_sharing_plans=6_000.0,
        employee_benefits=5_000.0,
        other_deductions=10_500.0,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def make_scope_outs(**overrides):
    fields = dict(
        net_passive_income_tax=0.0,
        built_in_gains_tax=0.0,
        interest_on_453_deferred=0.0,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def make_payments(**overrides):
    fields = dict(
        estimated_tax_payments=0.0,
        prior_year_overpayment_credited=0.0,
        tax_deposited_with_7004=0.0,
        credit_for_federal_excise_tax=0.0,
        refundable_credits=0.0,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def make_answers(method="cash"):
    return SimpleNamespace(
        accounting_method=method,
        business_activity_code="541990",
        business_activity_description="Consulting",
        product_or_service="Services",
        any_c_corp_subsidiaries=False,
        has_any_foreign_shareholders=False,
        owns_foreign_entity=True,
    )


def make_holder(name, pct):
    return SimpleNamespace(
        name=name, ssn_or_ein="000-00-0000", address=None,
        ownership_percentage=pct,
    )


def make_scorp(**overrides):
    fields = dict(
        income=make_income(),
        deductions=make_deductions(),
        schedule_b_answers=make_answers(),
        shareholders=[make_holder("Shareholder A", 100.0)],
        scope_outs=make_scope_outs(),
        payments=make_payments(),
        section_199a=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


# Hand-worked constants for the default scenario above:
#   1c = 500,000 - 20,000 = 480,000
#   3  = 480,000 - 150,000 = 330,000
#   6  = 330,000 + 5,000 + 2,500 = 337,500
#   total deductions = 217,000
#   ordinary business income = 337,500 - 217,000 = 120,500
DEFAULT_TOTAL_DEDUCTIONS = 217_000.0
DEFAULT_OBI = 120_500.0


class TestSupportedYears(unittest.TestCase):
    def test_every_entry_point_rejects_unsupported_years(self):
        for year in (2020, 2026):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    oracle.page1_income(year, make_income())
                with self.assertRaises(ValueError):
                    oracle.page1_deductions(year, make_deductions())
                with self.assertRaises(ValueError):
                    oracle.tax_and_payments(
                        year, make_scope_outs(), make_payments())
                with self.assertRaises(ValueError):
                    oracle.schedule_k(year, 0.0)
                with self.assertRaises(ValueError):
                    oracle.reference_f1120s(year, make_scorp())


class TestPage1LineNumbering(unittest.TestCase):
    def test_2021_2022_ordinary_income_is_line_21(self):
        for year in (2021, 2022):
            lines = oracle.PAGE1_LINES[year]
            self.assertEqual(lines["other_deductions"], "19")
            self.assertEqual(lines["total_deductions"], "20")
            self.assertEqual(lines["ordinary_business_income"], "21")
            self.assertEqual(lines["total_tax"], "22c")
            self.assertEqual(lines["total_payments"], "23d")
            self.assertEqual(lines["amount_owed"], "25")
            self.assertEqual(lines["overpayment"], "26")
            self.assertNotIn("refundable_credits", lines)

    def test_2023_onward_shifted_by_new_line_19(self):
        for year in (2023, 2024, 2025):
            lines = oracle.PAGE1_LINES[year]
            self.assertEqual(
                lines["energy_efficient_commercial_buildings_deduction"], "19")
            self.assertEqual(lines["other_deductions"], "20")
            self.assertEqual(lines["total_deductions"], "21")
            self.assertEqual(lines["ordinary_business_income"], "22")
            self.assertEqual(lines["total_tax"], "23c")
            self.assertEqual(lines["refundable_credits"], "24d")
            self.assertEqual(lines["total_payments"], "24z")
            self.assertEqual(lines["amount_owed"], "26")
            self.assertEqual(lines["overpayment"], "27")

    def test_2025_splits_credited_line(self):
        self.assertEqual(oracle.PAGE1_LINES[2024]["credited_to_next_year"], "28")
        self.assertEqual(oracle.PAGE1_LINES[2025]["credited_to_next_year"], "28a")

    def test_income_lines_unchanged_across_years(self):
        for year in ALL_YEARS:
            lines = oracle.PAGE1_LINES[year]
            self.assertEqual(lines["net_receipts"], "1c")
            self.assertEqual(lines["gross_profit"], "3")
            self.assertEqual(lines["total_income"], "6")
            self.assertEqual(lines["employee_benefits"], "18")


class TestPage1Income(unittest.TestCase):
    def test_chain(self):
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.page1_income(year, make_income())
                self.assertEqual(out["f1120s_gross_receipts"], 500_000.0)
                self.assertEqual(out["f1120s_returns_and_allowances"], 20_000.0)
                self.assertEqual(out["f1120s_net_receipts"], 480_000.0)
                self.assertEqual(out["f1120s_cost_of_goods_sold"], 150_000.0)
                self.assertEqual(out["f1120s_gross_profit"], 330_000.0)
                self.assertEqual(out["f1120s_net_gain_loss_4797"], 5_000.0)
                self.assertEqual(out["f1120s_other_income"], 2_500.0)
                self.assertEqual(out["f1120s_total_income"], 337_500.0)

    def test_each_input_moves_total_income_in_the_right_direction(self):
        base = oracle.page1_income(2024, make_income())["f1120s_total_income"]
        cases = (
            ("gross_receipts", 500_050.0, +50.0),
            ("returns_and_allowances", 20_050.0, -50.0),
            ("cogs_aggregate", 150_050.0, -50.0),
            ("net_gain_loss_4797", 5_050.0, +50.0),
            ("other_income", 2_550.0, +50.0),
        )
        for field, value, delta in cases:
            with self.subTest(field=field):
                out = oracle.page1_income(2024, make_income(**{field: value}))
                self.assertEqual(out["f1120s_total_income"], base + delta)

    def test_4797_loss_and_other_loss_reduce_total_income(self):
        out = oracle.page1_income(
            2022, make_income(net_gain_loss_4797=-7_500.0, other_income=-1_500.0))
        self.assertEqual(out["f1120s_gross_profit"], 330_000.0)
        self.assertEqual(out["f1120s_total_income"], 321_000.0)

    def test_gross_profit_can_be_negative(self):
        out = oracle.page1_income(
            2021,
            make_income(gross_receipts=100_000.0, returns_and_allowances=0.0,
                        cogs_aggregate=130_000.0, net_gain_loss_4797=0.0,
                        other_income=0.0))
        self.assertEqual(out["f1120s_gross_profit"], -30_000.0)
        self.assertEqual(out["f1120s_total_income"], -30_000.0)


class TestPage1Deductions(unittest.TestCase):
    def test_total_is_sum_of_all_thirteen_lines(self):
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.page1_deductions(year, make_deductions())
                self.assertEqual(
                    out["f1120s_total_deductions"], DEFAULT_TOTAL_DEDUCTIONS)

    def test_every_field_enters_the_total_exactly_once(self):
        base = make_deductions()
        for field in vars(base):
            with self.subTest(field=field):
                bumped = make_deductions(**{field: getattr(base, field) + 50.0})
                out = oracle.page1_deductions(2025, bumped)
                self.assertEqual(
                    out["f1120s_total_deductions"],
                    DEFAULT_TOTAL_DEDUCTIONS + 50.0)

    def test_passthrough_keys(self):
        out = oracle.page1_deductions(2023, make_deductions())
        expected = {
            "f1120s_compensation_of_officers": 80_000.0,
            "f1120s_salaries_wages": 60_000.0,
            "f1120s_repairs_maintenance": 3_000.0,
            "f1120s_bad_debts": 1_000.0,
            "f1120s_rents": 24_000.0,
            "f1120s_taxes_licenses": 9_000.0,
            "f1120s_interest": 2_000.0,
            "f1120s_depreciation": 12_000.0,
            "f1120s_depletion": 500.0,
            "f1120s_advertising": 4_000.0,
            "f1120s_pension_profit_sharing": 6_000.0,
            "f1120s_employee_benefits": 5_000.0,
            "f1120s_other_deductions": 10_500.0,
            "f1120s_total_deductions": DEFAULT_TOTAL_DEDUCTIONS,
        }
        self.assertEqual(out, expected)


class TestOrdinaryBusinessIncome(unittest.TestCase):
    def test_income(self):
        self.assertEqual(
            oracle.ordinary_business_income(337_500.0, 217_000.0), DEFAULT_OBI)

    def test_loss(self):
        self.assertEqual(
            oracle.ordinary_business_income(100_000.0, 217_000.0), -117_000.0)


class TestTaxAndPayments(unittest.TestCase):
    def test_total_tax_adds_passive_income_tax_and_built_in_gains_tax(self):
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.tax_and_payments(
                    year,
                    make_scope_outs(net_passive_income_tax=2_100.0,
                                    built_in_gains_tax=4_200.0),
                    make_payments())
                self.assertEqual(out["f1120s_net_passive_income_tax"], 2_100.0)
                self.assertEqual(out["f1120s_built_in_gains_tax"], 4_200.0)
                self.assertEqual(out["f1120s_total_tax"], 6_300.0)

    def test_section_453_interest_is_reported_but_not_in_total_tax(self):
        # FLAG-1: shareholder-level per the instructions (box 17 codes M/N).
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.tax_and_payments(
                    year,
                    make_scope_outs(built_in_gains_tax=1_000.0,
                                    interest_on_453_deferred=350.0),
                    make_payments())
                self.assertEqual(out["f1120s_interest_on_453_deferred"], 350.0)
                self.assertEqual(out["f1120s_total_tax"], 1_000.0)
                self.assertEqual(out["f1120s_amount_owed"], 1_000.0)

    def test_total_payments_2021_2022(self):
        for year in (2021, 2022):
            with self.subTest(year=year):
                out = oracle.tax_and_payments(
                    year, make_scope_outs(),
                    make_payments(estimated_tax_payments=3_000.0,
                                  prior_year_overpayment_credited=500.0,
                                  tax_deposited_with_7004=1_500.0,
                                  credit_for_federal_excise_tax=250.0))
                self.assertEqual(out["f1120s_estimated_tax_payments"], 3_000.0)
                self.assertEqual(
                    out["f1120s_prior_year_overpayment_credited"], 500.0)
                self.assertEqual(out["f1120s_tax_deposited_with_7004"], 1_500.0)
                self.assertEqual(
                    out["f1120s_credit_for_federal_excise_tax"], 250.0)
                self.assertEqual(out["f1120s_total_payments"], 5_250.0)

    def test_refundable_credits_enter_line_24d_from_2023(self):
        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                out = oracle.tax_and_payments(
                    year, make_scope_outs(),
                    make_payments(estimated_tax_payments=3_000.0,
                                  prior_year_overpayment_credited=500.0,
                                  tax_deposited_with_7004=1_500.0,
                                  credit_for_federal_excise_tax=250.0,
                                  refundable_credits=750.0))
                self.assertEqual(out["f1120s_refundable_credits"], 750.0)
                self.assertEqual(out["f1120s_total_payments"], 6_000.0)

    def test_refundable_credits_have_no_line_before_2023(self):
        # FLAG-2.
        for year in (2021, 2022):
            with self.subTest(year=year):
                with self.assertRaises(NotImplementedError):
                    oracle.tax_and_payments(
                        year, make_scope_outs(),
                        make_payments(refundable_credits=750.0))

    def test_zero_refundable_credits_accepted_before_2023(self):
        out = oracle.tax_and_payments(2021, make_scope_outs(), make_payments())
        self.assertEqual(out["f1120s_refundable_credits"], 0.0)
        self.assertEqual(out["f1120s_total_payments"], 0.0)

    def test_amount_owed_when_payments_fall_short(self):
        out = oracle.tax_and_payments(
            2024,
            make_scope_outs(net_passive_income_tax=5_000.0),
            make_payments(estimated_tax_payments=3_000.0),
            estimated_tax_penalty=150.0)
        self.assertEqual(out["f1120s_estimated_tax_penalty"], 150.0)
        self.assertEqual(out["f1120s_amount_owed"], 2_150.0)
        self.assertEqual(out["f1120s_overpayment"], 0.0)
        self.assertEqual(out["f1120s_credited_to_next_year"], 0.0)

    def test_overpayment_when_payments_exceed_tax_plus_penalty(self):
        out = oracle.tax_and_payments(
            2022,
            make_scope_outs(built_in_gains_tax=2_000.0),
            make_payments(estimated_tax_payments=3_000.0,
                          tax_deposited_with_7004=500.0),
            estimated_tax_penalty=100.0,
            credited_to_next_year=400.0)
        self.assertEqual(out["f1120s_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_overpayment"], 1_400.0)
        self.assertEqual(out["f1120s_credited_to_next_year"], 400.0)

    def test_penalty_can_turn_an_overpayment_into_a_balance_due(self):
        scope_outs = make_scope_outs(built_in_gains_tax=2_000.0)
        payments = make_payments(estimated_tax_payments=2_100.0)
        without = oracle.tax_and_payments(2023, scope_outs, payments)
        self.assertEqual(without["f1120s_overpayment"], 100.0)
        with_penalty = oracle.tax_and_payments(
            2023, scope_outs, payments, estimated_tax_penalty=250.0)
        self.assertEqual(with_penalty["f1120s_overpayment"], 0.0)
        self.assertEqual(with_penalty["f1120s_amount_owed"], 150.0)

    def test_exact_payment_leaves_both_lines_zero(self):
        out = oracle.tax_and_payments(
            2025,
            make_scope_outs(net_passive_income_tax=1_050.0),
            make_payments(estimated_tax_payments=1_050.0))
        self.assertEqual(out["f1120s_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_overpayment"], 0.0)

    def test_no_tax_no_payments(self):
        out = oracle.tax_and_payments(2021, make_scope_outs(), make_payments())
        self.assertEqual(out["f1120s_total_tax"], 0.0)
        self.assertEqual(out["f1120s_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_overpayment"], 0.0)

    def test_credit_to_next_year_cannot_exceed_overpayment(self):
        with self.assertRaises(ValueError):
            oracle.tax_and_payments(
                2024, make_scope_outs(),
                make_payments(estimated_tax_payments=500.0),
                credited_to_next_year=550.0)
        with self.assertRaises(ValueError):
            oracle.tax_and_payments(
                2024, make_scope_outs(),
                make_payments(estimated_tax_payments=500.0),
                credited_to_next_year=-50.0)

    def test_full_overpayment_may_be_credited(self):
        out = oracle.tax_and_payments(
            2024, make_scope_outs(),
            make_payments(estimated_tax_payments=500.0),
            credited_to_next_year=500.0)
        self.assertEqual(out["f1120s_credited_to_next_year"], 500.0)


class TestScheduleB(unittest.TestCase):
    def _flags(self, method):
        out = oracle.schedule_b(make_answers(method))
        return (
            out["f1120s_sch_b_accounting_method_cash"],
            out["f1120s_sch_b_accounting_method_accrual"],
            out["f1120s_sch_b_accounting_method_other"],
        )

    def test_plain_string_methods(self):
        self.assertEqual(self._flags("cash"), (True, False, False))
        self.assertEqual(self._flags("accrual"), (False, True, False))
        self.assertEqual(self._flags("hybrid"), (False, False, True))

    def test_enum_like_member_matched_by_value_or_name(self):
        by_value = SimpleNamespace(name="METHOD_B", value="Accrual")
        by_name = SimpleNamespace(name="CASH", value=1)
        neither = SimpleNamespace(name="OTHER", value="other")
        self.assertEqual(self._flags(by_value), (False, True, False))
        self.assertEqual(self._flags(by_name), (True, False, False))
        self.assertEqual(self._flags(neither), (False, False, True))

    def test_identity_passthroughs(self):
        out = oracle.schedule_b(make_answers())
        self.assertEqual(out["f1120s_sch_b_business_activity_code"], "541990")
        self.assertEqual(
            out["f1120s_sch_b_business_activity_description"], "Consulting")
        self.assertEqual(out["f1120s_sch_b_product_or_service"], "Services")
        self.assertIs(out["f1120s_sch_b_any_c_corp_subsidiaries"], False)
        self.assertIs(out["f1120s_sch_b_has_any_foreign_shareholders"], False)
        self.assertIs(out["f1120s_sch_b_owns_foreign_entity"], True)


class TestScheduleK(unittest.TestCase):
    def test_line_1_and_reconciliation_with_no_separately_stated_items(self):
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.schedule_k(year, DEFAULT_OBI)
                self.assertEqual(
                    out["f1120s_sch_k_ordinary_business_income"], DEFAULT_OBI)
                self.assertEqual(
                    out["f1120s_sch_k_income_loss_reconciliation"], DEFAULT_OBI)
                for name in oracle.SCH_K_ITEMS[1:]:
                    self.assertEqual(out[f"f1120s_sch_k_{name}"], 0.0)

    def test_line_18_combines_lines_1_through_10_less_deductions(self):
        stated = {
            "net_rental_real_estate": -4_000.0,      # line 2
            "other_net_rental_income": 1_500.0,      # line 3c
            "interest_income": 800.0,                # line 4
            "ordinary_dividends": 1_200.0,           # line 5a
            "royalties": 600.0,                      # line 6
            "net_short_term_capital_gain": -350.0,   # line 7
            "net_long_term_capital_gain": 2_500.0,   # line 8a
            "net_section_1231_gain": 900.0,          # line 9
            "other_income": 250.0,                   # line 10
            "section_179_deduction": 5_000.0,        # line 11
            "charitable_contributions": 1_000.0,     # line 12a
        }
        # Lines 1-10: 100,000 - 4,000 + 1,500 + 800 + 1,200 + 600 - 350
        #             + 2,500 + 900 + 250 = 103,400
        # Less 11, 12a-12d/e, 16f: 5,000 + 1,000 + 450 + 300 = 6,750
        out = oracle.schedule_k(
            2024, 100_000.0, stated,
            other_line_12_deductions=450.0,
            foreign_taxes_paid_or_accrued=300.0)
        self.assertEqual(out["f1120s_sch_k_income_loss_reconciliation"], 96_650.0)
        for name, amount in stated.items():
            self.assertEqual(out[f"f1120s_sch_k_{name}"], amount)

    def test_each_income_item_moves_line_18_up(self):
        base = oracle.schedule_k(2023, 50_000.0)
        for name in oracle.SCH_K_ITEMS[1:10]:
            with self.subTest(item=name):
                out = oracle.schedule_k(2023, 50_000.0, {name: 50.0})
                self.assertEqual(
                    out["f1120s_sch_k_income_loss_reconciliation"],
                    base["f1120s_sch_k_income_loss_reconciliation"] + 50.0)

    def test_each_deduction_item_moves_line_18_down(self):
        for name in ("section_179_deduction", "charitable_contributions"):
            with self.subTest(item=name):
                out = oracle.schedule_k(2023, 50_000.0, {name: 50.0})
                self.assertEqual(
                    out["f1120s_sch_k_income_loss_reconciliation"], 49_950.0)
        out = oracle.schedule_k(2023, 50_000.0, other_line_12_deductions=50.0)
        self.assertEqual(out["f1120s_sch_k_income_loss_reconciliation"], 49_950.0)
        out = oracle.schedule_k(
            2023, 50_000.0, foreign_taxes_paid_or_accrued=50.0)
        self.assertEqual(out["f1120s_sch_k_income_loss_reconciliation"], 49_950.0)

    def test_credits_amt_and_information_items_do_not_enter_line_18(self):
        for name in ("low_income_housing_credit", "foreign_transactions",
                     "amt_items", "tax_exempt_interest", "investment_income"):
            with self.subTest(item=name):
                out = oracle.schedule_k(2025, 50_000.0, {name: 1_000.0})
                self.assertEqual(out[f"f1120s_sch_k_{name}"], 1_000.0)
                self.assertEqual(
                    out["f1120s_sch_k_income_loss_reconciliation"], 50_000.0)

    def test_ordinary_loss_flows_to_line_18(self):
        out = oracle.schedule_k(2021, -35_000.0, {"interest_income": 500.0})
        self.assertEqual(out["f1120s_sch_k_income_loss_reconciliation"], -34_500.0)

    def test_unknown_item_rejected(self):
        with self.assertRaises(ValueError):
            oracle.schedule_k(2024, 0.0, {"qualified_dividends": 100.0})
        with self.assertRaises(ValueError):
            oracle.schedule_k(2024, 0.0, {"ordinary_business_income": 100.0})


class TestSection199ATotals(unittest.TestCase):
    def test_none_means_no_statement(self):
        self.assertIsNone(oracle.section_199a_totals(DEFAULT_OBI, None))

    def test_default_qbi_is_ordinary_business_income(self):
        info = SimpleNamespace(qbi_override=None, w2_wages=140_000.0, ubia=60_000.0)
        self.assertEqual(
            oracle.section_199a_totals(DEFAULT_OBI, info),
            {"qbi": DEFAULT_OBI, "w2_wages": 140_000.0, "ubia": 60_000.0})

    def test_override_replaces_default(self):
        info = SimpleNamespace(qbi_override=90_000.0, w2_wages=0.0, ubia=0.0)
        self.assertEqual(
            oracle.section_199a_totals(DEFAULT_OBI, info)["qbi"], 90_000.0)

    def test_zero_override_is_honoured_not_treated_as_missing(self):
        info = SimpleNamespace(qbi_override=0.0, w2_wages=0.0, ubia=0.0)
        self.assertEqual(oracle.section_199a_totals(DEFAULT_OBI, info)["qbi"], 0.0)

    def test_negative_qbi_passes_through(self):
        info = SimpleNamespace(qbi_override=None, w2_wages=0.0, ubia=0.0)
        self.assertEqual(
            oracle.section_199a_totals(-20_000.0, info)["qbi"], -20_000.0)


class TestProRataShare(unittest.TestCase):
    def test_sole_shareholder_takes_everything(self):
        self.assertEqual(oracle.pro_rata_share(120_500.0, 100.0), 120_500.0)

    def test_instruction_example_fifty_fifty(self):
        self.assertEqual(oracle.pro_rata_share(120_500.0, 50.0), 60_250.0)

    def test_fractional_percentages(self):
        self.assertAlmostEqual(oracle.pro_rata_share(120_500.0, 37.5), 45_187.5)
        self.assertAlmostEqual(oracle.pro_rata_share(100_000.0, 12.25), 12_250.0)

    def test_share_is_not_rounded(self):
        # 100,050 x 33.3333% = 33,349.96665 -- reported with its sub-cent tail.
        share = oracle.pro_rata_share(100_050.0, 33.3333)
        self.assertAlmostEqual(share, 33_349.96665, places=6)
        self.assertNotEqual(share, round(share, 2))

    def test_loss_allocates_with_its_sign(self):
        self.assertEqual(oracle.pro_rata_share(-40_000.0, 25.0), -10_000.0)


class TestK1Allocations(unittest.TestCase):
    def _sch_k(self, obi=DEFAULT_OBI, stated=None):
        return oracle.schedule_k(2024, obi, stated)

    def test_empty_shareholder_list(self):
        self.assertEqual(oracle.k1_allocations(self._sch_k(), [], None), [])

    def test_sole_shareholder(self):
        (record,) = oracle.k1_allocations(
            self._sch_k(), [make_holder("Shareholder A", 100.0)], None)
        self.assertEqual(record["name"], "Shareholder A")
        self.assertEqual(record["ssn_or_ein"], "000-00-0000")
        self.assertEqual(record["ownership_percentage"], 100.0)
        self.assertEqual(record["ordinary_business_income"], DEFAULT_OBI)
        self.assertIsNone(record["section_199a"])

    def test_sixty_forty_split_of_every_item(self):
        stated = {"interest_income": 1_000.0, "section_179_deduction": 5_000.0,
                  "net_long_term_capital_gain": -2_000.0}
        records = oracle.k1_allocations(
            self._sch_k(100_000.0, stated),
            [make_holder("Shareholder A", 60.0), make_holder("Shareholder B", 40.0)],
            None)
        self.assertEqual([r["name"] for r in records],
                         ["Shareholder A", "Shareholder B"])
        a, b = records
        self.assertAlmostEqual(a["ordinary_business_income"], 60_000.0)
        self.assertAlmostEqual(b["ordinary_business_income"], 40_000.0)
        self.assertAlmostEqual(a["interest_income"], 600.0)
        self.assertAlmostEqual(b["interest_income"], 400.0)
        self.assertAlmostEqual(a["section_179_deduction"], 3_000.0)
        self.assertAlmostEqual(b["section_179_deduction"], 2_000.0)
        self.assertAlmostEqual(a["net_long_term_capital_gain"], -1_200.0)
        self.assertAlmostEqual(b["net_long_term_capital_gain"], -800.0)
        self.assertEqual(a["royalties"], 0.0)

    def test_shares_sum_back_to_schedule_k_for_uneven_split(self):
        stated = {"ordinary_dividends": 1_250.0, "other_income": 350.0}
        sch_k = self._sch_k(87_650.0, stated)
        records = oracle.k1_allocations(
            sch_k,
            [make_holder("Shareholder A", 37.5),
             make_holder("Shareholder B", 12.25),
             make_holder("Shareholder C", 50.25)],
            None)
        for name in oracle.SCH_K_ITEMS:
            with self.subTest(item=name):
                self.assertAlmostEqual(
                    sum(r[name] for r in records),
                    sch_k[f"f1120s_sch_k_{name}"], places=6)
        self.assertAlmostEqual(
            records[0]["ordinary_business_income"], 32_868.75, places=6)
        self.assertAlmostEqual(
            records[1]["ordinary_business_income"], 10_737.125, places=6)
        self.assertAlmostEqual(
            records[2]["ordinary_business_income"], 44_044.125, places=6)

    def test_line_18_is_schedule_k_only_and_not_allocated(self):
        (record,) = oracle.k1_allocations(
            self._sch_k(), [make_holder("Shareholder A", 100.0)], None)
        self.assertNotIn("income_loss_reconciliation", record)
        self.assertEqual(
            set(record),
            {"name", "ssn_or_ein", "ownership_percentage", "section_199a",
             *oracle.SCH_K_ITEMS})

    def test_section_199a_shares(self):
        entity = {"qbi": 100_000.0, "w2_wages": 140_000.0, "ubia": 60_000.0}
        a, b = oracle.k1_allocations(
            self._sch_k(100_000.0),
            [make_holder("Shareholder A", 75.0), make_holder("Shareholder B", 25.0)],
            entity)
        self.assertEqual(
            a["section_199a"],
            {"qbi": 75_000.0, "w2_wages": 105_000.0, "ubia": 45_000.0})
        self.assertEqual(
            b["section_199a"],
            {"qbi": 25_000.0, "w2_wages": 35_000.0, "ubia": 15_000.0})

    def test_thirds_to_four_decimals_accepted(self):
        records = oracle.k1_allocations(
            self._sch_k(90_000.0),
            [make_holder("Shareholder A", 33.3333),
             make_holder("Shareholder B", 33.3333),
             make_holder("Shareholder C", 33.3334)],
            None)
        self.assertAlmostEqual(
            records[0]["ordinary_business_income"], 29_999.97, places=6)
        self.assertAlmostEqual(
            records[2]["ordinary_business_income"], 30_000.06, places=6)

    def test_total_just_inside_tolerance_accepted(self):
        # 3 x 33.3333 = 99.9999 and 3 x 33.3336 = 100.0008: both within the
        # 0.001-point tolerance, on either side of 100.
        for pct in (33.3333, 33.3336):
            with self.subTest(pct=pct):
                self.assertLess(
                    abs(3 * pct - 100.0), oracle.OWNERSHIP_TOTAL_TOLERANCE)
                records = oracle.k1_allocations(
                    self._sch_k(90_000.0),
                    [make_holder(f"Shareholder {i}", pct) for i in range(3)],
                    None)
                self.assertEqual(len(records), 3)

    def test_total_just_outside_tolerance_rejected(self):
        # 3 x 33.33 = 99.99 and 3 x 33.34 = 100.02: two-decimal thirds are a
        # deliberate rejection (FLAG-8), on either side of 100.
        for pct in (33.33, 33.34, 33.3327, 33.334):
            with self.subTest(pct=pct):
                self.assertGreater(
                    abs(3 * pct - 100.0), oracle.OWNERSHIP_TOTAL_TOLERANCE)
                with self.assertRaises(ValueError):
                    oracle.k1_allocations(
                        self._sch_k(90_000.0),
                        [make_holder(f"Shareholder {i}", pct) for i in range(3)],
                        None)

    def test_shares_within_tolerance_are_not_renormalised(self):
        records = oracle.k1_allocations(
            self._sch_k(90_000.0),
            [make_holder(f"Shareholder {i}", 33.3333) for i in range(3)],
            None)
        # 3 x 29,999.97 = 89,999.91: the 0.0001% residual goes to nobody.
        self.assertAlmostEqual(
            sum(r["ordinary_business_income"] for r in records),
            89_999.91, places=6)

    def test_percentages_not_totalling_100_rejected(self):
        # FLAG-8.
        for pcts in ((60.0, 30.0), (60.0, 50.0), (99.0,)):
            with self.subTest(pcts=pcts):
                holders = [make_holder(f"Shareholder {i}", p)
                           for i, p in enumerate(pcts)]
                with self.assertRaises(ValueError):
                    oracle.k1_allocations(self._sch_k(), holders, None)

    def test_out_of_range_percentage_rejected(self):
        for pcts in ((0.0, 100.0), (-50.0, 150.0), (150.0, -50.0)):
            with self.subTest(pcts=pcts):
                holders = [make_holder(f"Shareholder {i}", p)
                           for i, p in enumerate(pcts)]
                with self.assertRaises(ValueError):
                    oracle.k1_allocations(self._sch_k(), holders, None)


class TestReferenceF1120S(unittest.TestCase):
    EXPECTED_KEYS = {
        "f1120s_advertising", "f1120s_amount_owed", "f1120s_bad_debts",
        "f1120s_built_in_gains_tax", "f1120s_compensation_of_officers",
        "f1120s_cost_of_goods_sold", "f1120s_credit_for_federal_excise_tax",
        "f1120s_credited_to_next_year", "f1120s_depletion",
        "f1120s_depreciation", "f1120s_employee_benefits",
        "f1120s_estimated_tax_payments", "f1120s_estimated_tax_penalty",
        "f1120s_gross_profit", "f1120s_gross_receipts",
        "f1120s_interest_on_453_deferred", "f1120s_interest",
        "f1120s_net_gain_loss_4797", "f1120s_net_passive_income_tax",
        "f1120s_net_receipts", "f1120s_ordinary_business_income",
        "f1120s_other_deductions", "f1120s_other_income", "f1120s_overpayment",
        "f1120s_pension_profit_sharing",
        "f1120s_prior_year_overpayment_credited", "f1120s_refundable_credits",
        "f1120s_rents", "f1120s_repairs_maintenance",
        "f1120s_returns_and_allowances", "f1120s_salaries_wages",
        "f1120s_sch_b_accounting_method_accrual",
        "f1120s_sch_b_accounting_method_cash",
        "f1120s_sch_b_accounting_method_other",
        "f1120s_sch_b_any_c_corp_subsidiaries",
        "f1120s_sch_b_business_activity_code",
        "f1120s_sch_b_business_activity_description",
        "f1120s_sch_b_has_any_foreign_shareholders",
        "f1120s_sch_b_owns_foreign_entity", "f1120s_sch_b_product_or_service",
        "f1120s_sch_k_amt_items", "f1120s_sch_k_charitable_contributions",
        "f1120s_sch_k_foreign_transactions",
        "f1120s_sch_k_income_loss_reconciliation",
        "f1120s_sch_k_interest_income", "f1120s_sch_k_investment_income",
        "f1120s_sch_k_low_income_housing_credit",
        "f1120s_sch_k_net_long_term_capital_gain",
        "f1120s_sch_k_net_rental_real_estate",
        "f1120s_sch_k_net_section_1231_gain",
        "f1120s_sch_k_net_short_term_capital_gain",
        "f1120s_sch_k_ordinary_business_income",
        "f1120s_sch_k_ordinary_dividends", "f1120s_sch_k_other_income",
        "f1120s_sch_k_other_net_rental_income", "f1120s_sch_k_royalties",
        "f1120s_sch_k_section_179_deduction",
        "f1120s_sch_k_tax_exempt_interest", "f1120s_sch_k1_allocations",
        "f1120s_tax_deposited_with_7004", "f1120s_taxes_licenses",
        "f1120s_total_deductions", "f1120s_total_income",
        "f1120s_total_payments", "f1120s_total_tax",
    }

    def test_key_surface_is_exactly_the_output_key_list(self):
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.reference_f1120s(year, make_scorp())
                self.assertEqual(set(out), self.EXPECTED_KEYS)

    def test_end_to_end_two_shareholders_with_qbi(self):
        scorp = make_scorp(
            shareholders=[make_holder("Shareholder A", 70.0),
                          make_holder("Shareholder B", 30.0)],
            scope_outs=make_scope_outs(built_in_gains_tax=2_100.0),
            payments=make_payments(estimated_tax_payments=1_500.0,
                                   tax_deposited_with_7004=1_000.0),
            section_199a=SimpleNamespace(
                qbi_override=None, w2_wages=140_000.0, ubia=50_000.0),
        )
        for year in ALL_YEARS:
            with self.subTest(year=year):
                out = oracle.reference_f1120s(
                    year, scorp, credited_to_next_year=150.0)
                self.assertEqual(out["f1120s_net_receipts"], 480_000.0)
                self.assertEqual(out["f1120s_gross_profit"], 330_000.0)
                self.assertEqual(out["f1120s_total_income"], 337_500.0)
                self.assertEqual(
                    out["f1120s_total_deductions"], DEFAULT_TOTAL_DEDUCTIONS)
                self.assertEqual(
                    out["f1120s_ordinary_business_income"], DEFAULT_OBI)
                self.assertEqual(
                    out["f1120s_sch_k_ordinary_business_income"], DEFAULT_OBI)
                self.assertEqual(
                    out["f1120s_sch_k_income_loss_reconciliation"], DEFAULT_OBI)
                self.assertEqual(out["f1120s_total_tax"], 2_100.0)
                self.assertEqual(out["f1120s_total_payments"], 2_500.0)
                self.assertEqual(out["f1120s_amount_owed"], 0.0)
                self.assertEqual(out["f1120s_overpayment"], 400.0)
                self.assertEqual(out["f1120s_credited_to_next_year"], 150.0)
                a, b = out["f1120s_sch_k1_allocations"]
                self.assertAlmostEqual(a["ordinary_business_income"], 84_350.0)
                self.assertAlmostEqual(b["ordinary_business_income"], 36_150.0)
                self.assertAlmostEqual(a["section_199a"]["qbi"], 84_350.0)
                self.assertAlmostEqual(b["section_199a"]["qbi"], 36_150.0)
                self.assertAlmostEqual(a["section_199a"]["w2_wages"], 98_000.0)
                self.assertAlmostEqual(b["section_199a"]["w2_wages"], 42_000.0)
                self.assertAlmostEqual(a["section_199a"]["ubia"], 35_000.0)
                self.assertAlmostEqual(b["section_199a"]["ubia"], 15_000.0)

    def test_loss_year_allocates_the_loss_and_owes_nothing(self):
        scorp = make_scorp(
            income=make_income(gross_receipts=150_000.0),
            shareholders=[make_holder("Shareholder A", 50.0),
                          make_holder("Shareholder B", 50.0)],
            section_199a=SimpleNamespace(
                qbi_override=None, w2_wages=0.0, ubia=0.0),
        )
        # 1c = 130,000; 3 = -20,000; 6 = -12,500; OBI = -12,500 - 217,000.
        out = oracle.reference_f1120s(2023, scorp)
        self.assertEqual(out["f1120s_ordinary_business_income"], -229_500.0)
        self.assertEqual(out["f1120s_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_overpayment"], 0.0)
        for record in out["f1120s_sch_k1_allocations"]:
            self.assertEqual(record["ordinary_business_income"], -114_750.0)
            self.assertEqual(record["section_199a"]["qbi"], -114_750.0)

    def test_qbi_override_changes_only_the_statement(self):
        scorp = make_scorp(
            section_199a=SimpleNamespace(
                qbi_override=100_000.0, w2_wages=0.0, ubia=0.0))
        out = oracle.reference_f1120s(2025, scorp)
        (record,) = out["f1120s_sch_k1_allocations"]
        self.assertEqual(record["ordinary_business_income"], DEFAULT_OBI)
        self.assertEqual(record["section_199a"]["qbi"], 100_000.0)

    def test_section_199a_attribute_is_required_like_every_other_field(self):
        # None means "no statement"; an ABSENT attribute is a malformed input
        # and must not be silently read as None.
        scorp = make_scorp()
        del scorp.section_199a
        with self.assertRaises(AttributeError):
            oracle.reference_f1120s(2024, scorp)

    def test_missing_199a_info_yields_no_statement(self):
        out = oracle.reference_f1120s(2022, make_scorp())
        (record,) = out["f1120s_sch_k1_allocations"]
        self.assertIsNone(record["section_199a"])

    def test_amounts_are_unrounded_floats(self):
        scorp = make_scorp(
            shareholders=[make_holder("Shareholder A", 33.3333),
                          make_holder("Shareholder B", 66.6667)])
        out = oracle.reference_f1120s(2024, scorp)
        share = out["f1120s_sch_k1_allocations"][0]["ordinary_business_income"]
        self.assertIsInstance(out["f1120s_ordinary_business_income"], float)
        self.assertAlmostEqual(share, 40_166.6265, places=6)
        self.assertNotEqual(share, round(share, 2))


class TestNoRoundingAtEntityLevel(unittest.TestCase):
    """Pins charter rule 3 ("no rounding inside the oracle") at entity level.

    DELIBERATE EXCEPTION to the $50-multiple fixture convention (team-lead
    ruling): on $50-multiple inputs every entity-level amount is a whole
    dollar, so rounding is the identity and an added ``round()`` anywhere in
    the page 1 / Schedule K / payments chain would go undetected. This one
    scenario carries obviously synthetic cents so each surface has a
    fractional expected value. Every cents part is below .50 and the cents do
    not cancel, so rounding any single input, any line, or any total changes
    an asserted value. Do not copy these amounts into other fixtures.
    """

    def setUp(self):
        self.income = make_income(
            gross_receipts=50_000.37,
            returns_and_allowances=1_000.12,
            cogs_aggregate=10_000.11,
            net_gain_loss_4797=500.26,
            other_income=250.19,
        )
        # Whole dollars total 22,700; cents total 323 -> 22,703.23.
        self.deductions = make_deductions(
            compensation_of_officers=10_000.41,
            salaries_wages=5_000.33,
            repairs_maintenance=300.09,
            bad_debts=100.13,
            rents=2_400.27,
            taxes_licenses=900.31,
            interest=200.17,
            depreciation=1_200.43,
            depletion=50.07,
            advertising=400.21,
            pension_profit_sharing_plans=600.39,
            employee_benefits=500.23,
            other_deductions=1_050.19,
        )
        self.payments = make_payments(
            estimated_tax_payments=1_000.17,
            prior_year_overpayment_credited=200.19,
            tax_deposited_with_7004=300.23,
            credit_for_federal_excise_tax=50.11,
            refundable_credits=25.13,
        )
        self.scope_outs = make_scope_outs(built_in_gains_tax=2_000.29)

    def test_page1_income_keeps_cents(self):
        out = oracle.page1_income(2024, self.income)
        self.assertEqual(out["f1120s_gross_receipts"], 50_000.37)
        self.assertEqual(out["f1120s_returns_and_allowances"], 1_000.12)
        self.assertEqual(out["f1120s_cost_of_goods_sold"], 10_000.11)
        self.assertEqual(out["f1120s_net_gain_loss_4797"], 500.26)
        self.assertEqual(out["f1120s_other_income"], 250.19)
        self.assertAlmostEqual(out["f1120s_net_receipts"], 49_000.25, places=6)
        self.assertAlmostEqual(out["f1120s_gross_profit"], 39_000.14, places=6)
        self.assertAlmostEqual(out["f1120s_total_income"], 39_750.59, places=6)

    def test_deduction_lines_and_total_keep_cents(self):
        out = oracle.page1_deductions(2024, self.deductions)
        self.assertEqual(out["f1120s_compensation_of_officers"], 10_000.41)
        self.assertEqual(out["f1120s_depletion"], 50.07)
        self.assertEqual(out["f1120s_other_deductions"], 1_050.19)
        self.assertAlmostEqual(
            out["f1120s_total_deductions"], 22_703.23, places=6)

    def test_ordinary_business_income_keeps_cents(self):
        self.assertAlmostEqual(
            oracle.ordinary_business_income(39_750.59, 22_703.23),
            17_047.36, places=6)

    def test_schedule_k_line_18_keeps_cents(self):
        out = oracle.schedule_k(
            2024, 17_047.36, {"interest_income": 100.27},
            foreign_taxes_paid_or_accrued=10.12)
        self.assertEqual(out["f1120s_sch_k_ordinary_business_income"], 17_047.36)
        self.assertAlmostEqual(
            out["f1120s_sch_k_income_loss_reconciliation"], 17_137.51, places=6)

    def test_total_payments_and_balance_keep_cents(self):
        out = oracle.tax_and_payments(
            2024, self.scope_outs, self.payments, estimated_tax_penalty=10.14)
        self.assertEqual(out["f1120s_total_tax"], 2_000.29)
        self.assertAlmostEqual(out["f1120s_total_payments"], 1_575.83, places=6)
        self.assertAlmostEqual(out["f1120s_amount_owed"], 434.60, places=6)

    def test_overpayment_keeps_cents(self):
        out = oracle.tax_and_payments(
            2024, make_scope_outs(built_in_gains_tax=1_000.29), self.payments)
        self.assertAlmostEqual(out["f1120s_overpayment"], 575.54, places=6)

    def test_end_to_end_keeps_cents(self):
        scorp = make_scorp(
            income=self.income, deductions=self.deductions,
            payments=self.payments, scope_outs=self.scope_outs,
            section_199a=SimpleNamespace(
                qbi_override=None, w2_wages=15_000.74, ubia=0.0))
        out = oracle.reference_f1120s(2024, scorp)
        self.assertAlmostEqual(
            out["f1120s_ordinary_business_income"], 17_047.36, places=6)
        self.assertAlmostEqual(
            out["f1120s_sch_k_ordinary_business_income"], 17_047.36, places=6)
        self.assertAlmostEqual(
            out["f1120s_sch_k_income_loss_reconciliation"], 17_047.36, places=6)
        self.assertAlmostEqual(out["f1120s_total_payments"], 1_575.83, places=6)
        self.assertAlmostEqual(out["f1120s_amount_owed"], 424.46, places=6)
        (record,) = out["f1120s_sch_k1_allocations"]
        self.assertAlmostEqual(
            record["ordinary_business_income"], 17_047.36, places=6)
        self.assertAlmostEqual(record["section_199a"]["qbi"], 17_047.36, places=6)
        self.assertAlmostEqual(
            record["section_199a"]["w2_wages"], 15_000.74, places=6)


if __name__ == "__main__":
    unittest.main()
