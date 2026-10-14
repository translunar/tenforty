"""Per-status consumer rows (MFJ, HoH) for TY2025, one per audited consumer.

Each row checks that a federal consumer of a per-status parameter reads the
requested status's column, measured against
``load_federal(2025).for_status(status)``. No expected value is written
here: every expectation is read from params or produced by the spine.

Reachability rule: a row asserts a result DIFFERS from the single column
only after a precondition ``assertNotEqual`` on the two params columns.
Where the columns coincide, the row asserts equality, and its docstring says
the negative is unreachable for that field and year.

Rows run with 2025 MFJ/HoH declared on the native grid by patch, until
declare-2025 lands. Identities and amounts are synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.forms import f1040_tax, f1040x, f8949, f8959, f8995, sch_1, sch_a, sch_d
from tenforty.models import (
    AmendmentCase, FilingStatus, Form1095A, Form1095AMonth, Form1099G,
    Form1099INT, ItemizedDeductions, K1FanoutData, ScheduleCBusiness,
    ScheduleK1, Scenario,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal
from tenforty.scenario import _validate_scenario_config
from tests.fixtures.spine_battery import (
    _battery_config, build_capital_loss_over_cap, build_wages_only,
)
from tests.helpers import REPO_ROOT

_YEAR = 2025
_S = FilingStatus.SINGLE
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD
_ROW_STATUSES = (_MFJ, _HOH)
_DECLARED = {_YEAR: (_S.value, _MFJ.value, _HOH.value)}


def _declared():
    return mock.patch.dict(years.NATIVE_SPINE_STATUSES, _DECLARED)


def _no_workbook():
    """Any route to the workbook fails the row: these rows are native."""
    return mock.patch.object(
        ReturnOrchestrator, "_compute_1040_via_workbook",
        side_effect=AssertionError("row routed to the XLSX workbook"))


class _Rows(unittest.TestCase):
    def setUp(self):
        self.params = load_federal(_YEAR)
        self.single = self.params.for_status(_S)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work")

    def view(self, status):
        return self.params.for_status(status)

    def compute(self, scenario):
        with _declared(), _no_workbook():
            return self.orch.compute_federal(scenario)

    def config(self, status, **overrides):
        return _battery_config(_YEAR, status, **overrides)


class SpineStandardDeductionRowTests(_Rows):
    def test_wages_only_takes_the_status_standard_deduction(self):
        for status in _ROW_STATUSES:
            view = self.view(status)
            with self.subTest(status=status):
                self.assertNotEqual(view.standard_deduction,
                                    self.single.standard_deduction)
                results = self.compute(build_wages_only(_YEAR, status))
                self.assertEqual(results["total_deductions"],
                                 view.standard_deduction)
                self.assertNotEqual(results["total_deductions"],
                                    self.single.standard_deduction)


class OrdinaryTaxRowTests(_Rows):
    def test_bracket_schedule_reads_the_status_column(self):
        income = float(self.params.for_status(_MFJ).ordinary_brackets[2][0])
        for status in _ROW_STATUSES:
            view = self.view(status)
            with self.subTest(status=status):
                self.assertNotEqual(view.ordinary_brackets,
                                    self.single.ordinary_brackets)
                self.assertEqual(
                    f1040_tax.ordinary_tax(income, self.params, status),
                    f1040_tax.tax_from_schedule(income, view))
                self.assertNotEqual(
                    f1040_tax.ordinary_tax(income, self.params, status),
                    f1040_tax.ordinary_tax(income, self.params, _S))

    def test_spine_tax_is_the_status_tax_on_its_taxable_income(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                self.assertNotEqual(self.view(status).ordinary_brackets,
                                    self.single.ordinary_brackets)
                results = self.compute(build_wages_only(_YEAR, status))
                ti = results["taxable_income"]
                self.assertEqual(
                    results["total_tax"],
                    f1040_tax.ordinary_tax(ti, self.params, status))
                self.assertNotEqual(
                    results["total_tax"],
                    f1040_tax.ordinary_tax(ti, self.params, _S))


class QdcgtRowTests(_Rows):
    def test_zero_percent_band_reads_the_status_breakpoint(self):
        """Taxable income sits between single's 0% breakpoint and the
        status's: under the status column every preferential dollar is in
        the 0% band, so the worksheet tax is the ordinary tax alone."""
        ordinary = 20_000.0
        for status in _ROW_STATUSES:
            zero_top = self.view(status).qdcgt_breakpoints[0]
            single_zero_top = self.single.qdcgt_breakpoints[0]
            with self.subTest(status=status):
                self.assertNotEqual(zero_top, single_zero_top)
                self.assertGreater(zero_top, single_zero_top)
                ti = float(single_zero_top + (zero_top - single_zero_top) // 2)
                preferential = ti - ordinary
                with _declared():
                    status_tax = f1040_tax.qdcgt_tax(
                        ti, preferential, 0.0, self.params, status)
                    single_tax = f1040_tax.qdcgt_tax(
                        ti, preferential, 0.0, self.params, _S)
                self.assertEqual(
                    status_tax,
                    f1040_tax.ordinary_tax(ordinary, self.params, status))
                self.assertGreater(
                    single_tax,
                    f1040_tax.ordinary_tax(ordinary, self.params, _S))


class SaltCapRowTests(_Rows):
    def _sch_a(self, status, magi, property_tax):
        scenario = Scenario(
            config=self.config(status),
            itemized_deductions=ItemizedDeductions(property_tax=property_tax))
        return sch_a.compute(scenario, {"f1040": {"agi": magi, "magi": magi}})

    def test_starting_cap_reads_the_status_column(self):
        """TY2025's MFJ and HoH starting caps equal single's, so a
        differs-from-single negative is unreachable for this field and year;
        the row asserts equality with the status column."""
        for status in _ROW_STATUSES:
            cap = self.view(status).salt_cap_starting
            with self.subTest(status=status):
                self.assertEqual(cap, self.single.salt_cap_starting)
                out = self._sch_a(status, magi=100_000.0,
                                  property_tax=float(cap) * 2)
                self.assertEqual(out["sch_a_line_5e_salt_capped"], cap)

    def test_phaseout_refusal_names_the_status_floor(self):
        """TY2025's MFJ and HoH floors equal single's, so a
        differs-from-single negative is unreachable for this field and year;
        the row asserts the refusal names the status column's floor."""
        magi = float(self.params.salt_phaseout_threshold) + 1
        for status in _ROW_STATUSES:
            view = self.view(status)
            with self.subTest(status=status):
                self.assertEqual(view.salt_cap_floor, self.single.salt_cap_floor)
                with self.assertRaisesRegex(
                        NotImplementedError,
                        rf"toward {view.salt_cap_floor:,} "):
                    self._sch_a(status, magi=magi, property_tax=1_000.0)


class QbiThresholdRowTests(_Rows):
    def _f8995(self, status, taxable_income):
        qbi = 20_000.0
        scenario = Scenario(
            config=self.config(status),
            schedule_k1s=[ScheduleK1(
                entity_name="Synthetic S Corp", entity_ein="00-0000000",
                entity_type="s_corp", material_participation=True,
                qbi_amount=qbi)])
        scenario.config.acknowledges_qbi_below_threshold = False
        fanout = K1FanoutData(
            sch_b_interest_additions=(), sch_b_dividend_additions=(),
            sch_d_short_term_additions=(), sch_d_long_term_additions=(),
            qbi_aggregate=qbi, qualified_dividends_aggregate=0.0,
            passive_activities=())
        return f8995.compute(scenario, {
            "f1040": {"taxable_income_before_qbi_deduction": taxable_income,
                      "net_capital_gain": 0.0, "qualified_dividends": 0.0},
            "k1_fanout": fanout})

    def test_mfj_threshold_reads_the_status_column(self):
        threshold = self.view(_MFJ).qbi_threshold
        self.assertNotEqual(threshold, self.single.qbi_threshold)
        between = float(self.single.qbi_threshold + threshold) / 2
        self.assertGreater(between, self.single.qbi_threshold)
        self.assertLess(between, threshold)
        self.assertIn("f8995_line_15_qbi_deduction", self._f8995(_MFJ, between))
        with self.assertRaisesRegex(NotImplementedError, "simple-path threshold"):
            self._f8995(_S, between)

    def test_hoh_threshold_reads_the_status_column(self):
        """TY2025's HoH threshold equals single's, so a differs-from-single
        negative is unreachable for this field and year; the row pins the
        refusal boundary at the status column."""
        threshold = self.view(_HOH).qbi_threshold
        self.assertEqual(threshold, self.single.qbi_threshold)
        self.assertIn("f8995_line_15_qbi_deduction",
                      self._f8995(_HOH, float(threshold)))
        with self.assertRaisesRegex(NotImplementedError, "simple-path threshold"):
            self._f8995(_HOH, float(threshold) + 1)


class AdditionalMedicareThresholdRowTests(_Rows):
    """Form 8959's line-5 threshold against the status column.

    These rows check values, not the read path: f8959 still carries its own
    status-keyed threshold dict (the addl-medicare-columns code half has not
    landed), so these rows pass for as long as that dict agrees with params.
    """

    def _f8959(self, status, medicare_wages):
        scenario = Scenario(
            config=self.config(status),
            w2s=[dataclasses.replace(
                build_wages_only(_YEAR, _S).w2s[0],
                medicare_wages=medicare_wages)])
        return f8959.compute(scenario, {})

    def test_mfj_threshold_is_the_status_column(self):
        threshold = self.view(_MFJ).addl_medicare_threshold
        self.assertNotEqual(threshold, self.single.addl_medicare_threshold)
        between = float(self.single.addl_medicare_threshold + threshold) / 2
        out = self._f8959(_MFJ, between)
        self.assertEqual(out["f8959_line_5"], threshold)
        self.assertEqual(out["f8959_line_7"], 0)
        self.assertGreater(self._f8959(_S, between)["f8959_line_7"], 0)

    def test_hoh_threshold_is_the_status_column(self):
        """TY2025's HoH threshold equals single's, so a differs-from-single
        negative is unreachable for this field and year."""
        threshold = self.view(_HOH).addl_medicare_threshold
        self.assertEqual(threshold, self.single.addl_medicare_threshold)
        self.assertEqual(
            self._f8959(_HOH, float(threshold))["f8959_line_5"], threshold)


class CapitalLossLimitRowTests(_Rows):
    def test_loss_limit_reads_the_status_column(self):
        """TY2025's MFJ and HoH loss limits equal single's, so a
        differs-from-single negative is unreachable for this field and year;
        the row asserts line 21 is the status column's limit."""
        base = build_capital_loss_over_cap(_YEAR)
        for status in _ROW_STATUSES:
            limit = self.view(status).capital_loss_limit
            with self.subTest(status=status):
                self.assertEqual(limit, self.single.capital_loss_limit)
                scenario = dataclasses.replace(base, config=self.config(status))
                out = sch_d.compute(
                    scenario, upstream={"f8949": f8949.compute(scenario, upstream={})})
                self.assertLess(out["sch_d_line_16_total"], -limit)
                self.assertEqual(out["sch_d_line_21_allowed_loss"], -limit)


class PriorYearSaltCapRowTests(_Rows):
    def test_state_refund_benefit_reads_the_status_column(self):
        """TY2025's MFJ and HoH prior-year caps equal single's, so a
        differs-from-single negative is unreachable for this field and year.
        Prior-year SALT paid sits above the cap by less than the refund, so
        the taxable refund is the part of the refund that dropped SALT paid
        back under the status's cap."""
        refund, over_cap = 2_000.0, 500.0
        for status in _ROW_STATUSES:
            cap = self.view(status).prior_year_salt_cap
            with self.subTest(status=status):
                self.assertEqual(cap, self.single.prior_year_salt_cap)
                scenario = Scenario(
                    config=self.config(
                        status, prior_year_itemized=True,
                        prior_year_itemized_deduction_amount=float(cap) * 10,
                        prior_year_standard_deduction_amount=float(cap),
                        prior_year_salt_paid=float(cap) + over_cap),
                    form1099_g=[Form1099G(payer="Synthetic State",
                                          state_tax_refund=refund)])
                out = sch_1.compute(scenario, {})
                self.assertEqual(out["sch_1_line_1_taxable_refunds"],
                                 refund - over_cap)


class ExcessBusinessLossThresholdRowTests(_Rows):
    def _scenario(self, status, loss):
        return Scenario(
            config=self.config(status,
                               acknowledges_sch_c_all_investment_at_risk=True),
            schedule_c_businesses=[ScheduleCBusiness(
                description="Synthetic Loss Shop", gross_receipts=0.0,
                supplies=float(loss))])

    def test_mfj_threshold_reads_the_status_column(self):
        threshold = self.view(_MFJ).excess_business_loss_threshold
        single = self.single.excess_business_loss_threshold
        self.assertNotEqual(threshold, single)
        between = (single + threshold) // 2
        self.orch._refuse_possible_excess_business_loss(
            self._scenario(_MFJ, between))
        with self.assertRaisesRegex(NotImplementedError, "461"):
            self.orch._refuse_possible_excess_business_loss(
                self._scenario(_S, between))

    def test_hoh_threshold_reads_the_status_column(self):
        """TY2025's HoH threshold equals single's, so a differs-from-single
        negative is unreachable for this field and year; the row pins the
        refusal boundary at the status column."""
        threshold = self.view(_HOH).excess_business_loss_threshold
        self.assertEqual(threshold, self.single.excess_business_loss_threshold)
        self.orch._refuse_possible_excess_business_loss(
            self._scenario(_HOH, threshold))
        with self.assertRaisesRegex(NotImplementedError, "461"):
            self.orch._refuse_possible_excess_business_loss(
                self._scenario(_HOH, threshold + 1))


class CharitableNonItemizer2021RowTests(unittest.TestCase):
    def test_2021_line_12b_still_refuses_for_mfj_and_hoh(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                cfg = _battery_config(2021, status,
                                      charitable_cash_nonitemizer=100.0)
                with self.assertRaisesRegex(ValueError, "SINGLE filers only"):
                    _validate_scenario_config(cfg)


class PtcOffGridStatusRowTests(_Rows):
    def test_mfs_and_qw_with_1095a_still_refuse(self):
        block = Form1095A(months=tuple(
            Form1095AMonth(premium=500, slcsp=500, aptc=0) for _ in range(12)))
        base = build_wages_only(_YEAR, _S)
        for status in (FilingStatus.MARRIED_FILING_SEPARATELY,
                       FilingStatus.QUALIFYING_WIDOW):
            with self.subTest(status=status):
                scenario = dataclasses.replace(
                    base, form_1095a=block,
                    config=dataclasses.replace(base.config,
                                               filing_status=status))
                with self.assertRaises(NotImplementedError):
                    self.compute(scenario)


class AmendmentRowTests(_Rows):
    """A 1040-X over an MFJ or HoH original: the header checks exactly the
    return's own status box, and Columns A and C are the native compute
    results of the original and the amended scenario."""

    def test_status_box_and_columns_from_native_compute(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                original = build_wages_only(_YEAR, status)
                amended = dataclasses.replace(original, form1099_int=[
                    Form1099INT(payer="Synthetic Bank", interest=1_000.0)])
                filed = self.compute(original)
                corrected = self.compute(amended)
                case = AmendmentCase(
                    year=_YEAR, explanation="Synthetic: omitted interest.",
                    original_refund_received=float(filed["overpaid"]),
                    original_refund_applied=0.0, prior_amendment_note=None,
                    # Whatever balance the original showed was paid with it.
                    original_tax_paid=float(max(
                        0, filed["total_tax"] - filed["total_payments"])))
                out = f1040x.assemble(filed, corrected, case)
                for line, key in (("1", "agi"), ("5", "taxable_income")):
                    self.assertEqual(out[f"f1040x_line{line}_a"], filed[key])
                    self.assertEqual(out[f"f1040x_line{line}_c"],
                                     corrected[key])
                self.assertNotEqual(out["f1040x_line1_a"],
                                    out["f1040x_line1_c"])
                boxes = {k: v for k, v in
                         f1040x.presentation_keys(amended.config).items()
                         if k.startswith("f1040x_filing_status_")}
                self.assertEqual(
                    [k for k, v in boxes.items() if v],
                    [f"f1040x_filing_status_{f1040x._FILING_STATUS_SUFFIX[status]}"])
                self.assertEqual(len(boxes), len(FilingStatus))
