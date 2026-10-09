"""Schedule C net LOSS: at-risk attestation, line 32a, no SE tax, Form 8995
loss carryforward, and the loss netting on the 1040.

A Schedule C business whose line 31 is below zero computes only when
`acknowledges_sch_c_all_investment_at_risk` is true (box 32a). The loss then
flows to Schedule 1 line 3, owes no self-employment tax, and enters Form 8995
as a negative QBI component: it nets against positive QBI, the deduction
floors at zero, and the unused loss carries forward on line 16.

Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.forms import f8995, sch_c, sch_se
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.models import (
    K1FanoutData, RentalProperty, ScheduleCBusiness, Scenario,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario

ATTESTATION = "acknowledges_sch_c_all_investment_at_risk"

# gross 400 - (advertising 430 + supplies 40) = -70
_LOSS = -70
_LOSS_BIZ = dict(description="Synthetic Loss Shop", business_code="541990",
                 gross_receipts=400.0, advertising=430.0, supplies=40.0)

# Literal Schedule C paths, the same in every year 2022-2025.
_LINE_29 = "topmostSubform[0].Page1[0].f1_42[0]"
_LINE_31 = "topmostSubform[0].Page1[0].f1_46[0]"
_BOX_32A = "topmostSubform[0].Page1[0].c1_7[0]"
_BOX_32B = "topmostSubform[0].Page1[0].c1_7[1]"
# Form 8995 line 16 (loss carryforward) and line 15 (deduction).
_F8995_LINE_15 = "topmostSubform[0].Page1[0].f1_31[0]"
_F8995_LINE_16 = "topmostSubform[0].Page1[0].f1_32[0]"

_YEARS = (2022, 2023, 2024, 2025)


def _scenario(*businesses, at_risk=True, year=2025, rentals=()):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, acknowledges_no_source_documents=True,
        first_name="Example", last_name="Filer", ssn="000-00-0000",
        **{ATTESTATION: at_risk})
    return Scenario(config=config, w2s=base.w2s,
                    schedule_c_businesses=list(businesses),
                    rental_properties=list(rentals))


def _loss_biz():
    return ScheduleCBusiness(**_LOSS_BIZ)


def _fanout(qbi_aggregate=0.0):
    return K1FanoutData(
        sch_b_interest_additions=(), sch_b_dividend_additions=(),
        sch_d_short_term_additions=(), sch_d_long_term_additions=(),
        qbi_aggregate=qbi_aggregate, qualified_dividends_aggregate=0.0,
        passive_activities=())


def _f8995(sch_c_total, k1_qbi=0.0):
    return f8995.compute(make_simple_scenario(), {
        "k1_fanout": _fanout(k1_qbi),
        "f1040": {"taxable_income_before_qbi_deduction": 80_000.0,
                  "net_capital_gain": 0.0, "qualified_dividends": 0.0},
        "sch_c": {"sch_c_line_31_net_profit_total": sch_c_total},
        "sch_se": {},
    })


def _field(pdf_path, field_path):
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "")


class SchCNetLossComputeTests(unittest.TestCase):
    def test_loss_computes_when_all_investment_is_attested_at_risk(self):
        out = sch_c.compute(_scenario(_loss_biz()), upstream={})
        lines = out["sch_c_businesses"][0]
        self.assertEqual(lines["sch_c_line_28_total_expenses"], 470)
        self.assertEqual(lines["sch_c_line_29_tentative_profit"], _LOSS)
        self.assertEqual(lines["sch_c_line_31_net_profit"], _LOSS)
        self.assertEqual(out["sch_c_line_31_net_profit_total"], _LOSS)
        self.assertIs(lines["sch_c_line_32a_all_investment_at_risk"], True)

    def test_loss_refuses_without_the_attestation_and_names_it(self):
        scn = _scenario(_loss_biz(), at_risk=False)
        self.assertIs(getattr(scn.config, ATTESTATION), False)
        with self.assertRaises(NotImplementedError) as ctx:
            sch_c.compute(scn, upstream={})
        message = str(ctx.exception)
        self.assertIn(ATTESTATION, message)
        self.assertIn("Form 6198", message)

    def test_profit_business_carries_no_line_32_mark(self):
        profit = ScheduleCBusiness(description="Synthetic Profit",
                                   gross_receipts=5_000.0, supplies=1_000.0)
        out = sch_c.compute(_scenario(profit, at_risk=False), upstream={})
        self.assertNotIn("sch_c_line_32a_all_investment_at_risk",
                         out["sch_c_businesses"][0])
        # Reachability of the absent key: the loss case above carries it.

    def test_profit_and_loss_businesses_net_in_the_total(self):
        profit = ScheduleCBusiness(description="Synthetic Profit",
                                   gross_receipts=5_000.0, supplies=1_000.0)
        out = sch_c.compute(_scenario(profit, _loss_biz()), upstream={})
        self.assertEqual(out["sch_c_line_31_net_profit_total"], 4_000 + _LOSS)
        first, second = out["sch_c_businesses"]
        self.assertNotIn("sch_c_line_32a_all_investment_at_risk", first)
        self.assertIs(second["sch_c_line_32a_all_investment_at_risk"], True)


class SchCNetLossSelfEmploymentTests(unittest.TestCase):
    def test_a_net_loss_owes_no_self_employment_tax(self):
        scn = _scenario(_loss_biz())
        self.assertEqual(
            sch_se.compute(scn, {"sch_c": sch_c.compute(scn, upstream={})}),
            {})

    def test_se_tax_is_figured_on_the_net_of_profit_and_loss(self):
        profit = ScheduleCBusiness(description="Synthetic Profit",
                                   gross_receipts=5_000.0, supplies=1_000.0)
        scn = _scenario(profit, _loss_biz())
        out = sch_se.compute(scn, {"sch_c": sch_c.compute(scn, upstream={})})
        self.assertEqual(out["sch_se_line_2_net_profit"], 4_000 + _LOSS)
        self.assertGreater(out["sch_se_line_12_se_tax"], 0)


class SchCLossQbiTests(unittest.TestCase):
    def test_a_lone_loss_carries_forward_with_zero_deduction(self):
        out = _f8995(_LOSS)
        self.assertEqual(out["f8995_line_1_qbi"], _LOSS)
        self.assertEqual(out["f8995_line_2_total_qbi"], _LOSS)
        self.assertEqual(out["f8995_line_4_total_qbi"], 0)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], _LOSS)

    def test_the_loss_nets_against_larger_k1_qbi(self):
        out = _f8995(_LOSS, k1_qbi=1_070.0)
        self.assertEqual(out["f8995_line_1_qbi"], 1_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 200)  # 20% x 1,000
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], 0)

    def test_a_loss_larger_than_k1_qbi_carries_the_remainder(self):
        out = _f8995(_LOSS, k1_qbi=30.0)
        self.assertEqual(out["f8995_line_1_qbi"], -40)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], -40)


class SchCNetLossReturnTests(unittest.TestCase):
    """The real shape: W-2 wages, a profitable rental, one small Schedule C
    loss -- through compute_federal and emit_pdfs."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    @staticmethod
    def _rental():
        return RentalProperty(
            address="1 Example Ave, Example City, EX 00000", property_type=1,
            fair_rental_days=365, personal_use_days=0,
            rents_received=12_000.0, taxes=2_000.0)

    def test_refusal_through_the_real_entry_point_names_the_attestation(self):
        scn = _scenario(_loss_biz(), at_risk=False, rentals=[self._rental()])
        self.assertIs(getattr(scn.config, ATTESTATION), False)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scn)
        self.assertIn(ATTESTATION, str(ctx.exception))

    def test_loss_nets_on_the_1040_with_no_se_tax(self):
        with_loss = self.orch.compute_federal(
            _scenario(_loss_biz(), rentals=[self._rental()]))
        without = self.orch.compute_federal(
            _scenario(rentals=[self._rental()]))
        self.assertEqual(with_loss["sch_1_line_3_business_income"], _LOSS)
        self.assertEqual(with_loss["sch_1_line_5_rental_re_royalty"], 10_000)
        self.assertEqual(with_loss["agi"], without["agi"] + _LOSS)
        self.assertEqual(with_loss["sch_se_line_12_se_tax"], 0)
        self.assertEqual(with_loss["sch_1_line_15_se_tax"], 0)
        self.assertEqual(with_loss["qbi_deduction"], 0)

    def test_emitted_packet_shows_the_loss_box_32a_and_the_carryforward(self):
        for year in _YEARS:
            with self.subTest(year=year):
                scn = _scenario(_loss_biz(), year=year,
                                rentals=[self._rental()])
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(
                    scn, results, self.tmp / f"out_{year}")
                self.assertNotIn("sch_se", emitted)
                self.assertNotIn("sch_2", emitted)

                sch_c_pdf = emitted["sch_c_1"]
                self.assertEqual(_field(sch_c_pdf, _LINE_29), str(_LOSS))
                self.assertEqual(_field(sch_c_pdf, _LINE_31), str(_LOSS))
                self.assertEqual(_field(sch_c_pdf, _BOX_32A), "/1")
                self.assertIn(_field(sch_c_pdf, _BOX_32B), ("", "/Off"))
                self.assertEqual(
                    PdfSchC.get_mapping(year)["sch_c_line_31_net_profit"],
                    _LINE_31)

                sch_1 = PdfSch1.get_mapping(year)
                sch_1 = sch_1.get("scalars", sch_1)
                self.assertEqual(
                    _field(emitted["sch_1"],
                           sch_1["sch_1_line_3_business_income"]),
                    str(_LOSS))

                self.assertIn("f8995", emitted)
                self.assertEqual(
                    PdfF8995.get_mapping(year)["scalars"][
                        "f8995_line_16_qbi_loss_carryforward"],
                    _F8995_LINE_16)
                # The compute key is signed; the line 16 cell has
                # PREPRINTED parentheses, so the magnitude prints in it.
                self.assertEqual(
                    _field(emitted["f8995"], _F8995_LINE_16), str(-_LOSS))
                self.assertEqual(_field(emitted["f8995"], _F8995_LINE_15), "0")

    def test_a_profit_business_leaves_both_line_32_boxes_blank(self):
        profit = ScheduleCBusiness(
            description="Synthetic Profit", business_code="541990",
            gross_receipts=5_000.0, supplies=1_000.0)
        scn = _scenario(profit)
        emitted = self.orch.emit_pdfs(
            scn, self.orch.compute_federal(scn), self.tmp / "out_profit")
        self.assertIn(_field(emitted["sch_c_1"], _BOX_32A), ("", "/Off"))
        self.assertIn(_field(emitted["sch_c_1"], _BOX_32B), ("", "/Off"))


class SchCLossEicRoutingTests(unittest.TestCase):
    """The EIC-ceiling routing estimate must count a Schedule C loss. Wages
    alone clear the ceiling, but wages minus the loss do not: that filer is
    possibly EIC-eligible and must NOT route to the native spine, which does
    no EIC math."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")

    def _wage_scenario(self, wages, *businesses):
        scn = _scenario(*businesses)
        w2 = dataclasses.replace(scn.w2s[0], wages=wages, ss_wages=wages,
                                 medicare_wages=wages)
        return dataclasses.replace(scn, w2s=[w2])

    def test_loss_that_drops_agi_under_the_ceiling_leaves_the_spine(self):
        from tenforty.params.federal import load as load_federal_params
        ceiling = load_federal_params(2025).eic_income_ceiling[0]
        wages = ceiling + 1_000.0
        big_loss = ScheduleCBusiness(
            description="Synthetic Loss Shop", gross_receipts=0.0,
            supplies=5_000.0)
        # Wages alone are in scope ...
        self.assertTrue(self.orch._scenario_in_spine_scope(
            self._wage_scenario(wages)))
        # ... wages less the loss are under the ceiling.
        self.assertLess(wages - 5_000.0, ceiling)
        self.assertFalse(self.orch._scenario_in_spine_scope(
            self._wage_scenario(wages, big_loss)))

    def test_small_loss_well_above_the_ceiling_stays_native(self):
        self.assertTrue(self.orch._scenario_in_spine_scope(
            self._wage_scenario(100_000.0, _loss_biz())))


if __name__ == "__main__":
    unittest.main()
