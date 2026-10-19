"""1099-G fan-out through Schedule 1."""

import unittest

from tenforty.forms import sch_1 as form_sch_1
from tenforty.models import Form1099G

from tests.helpers import make_simple_scenario


class Sch1UnemploymentTests(unittest.TestCase):
    def test_box1_to_line_7(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(payer="State", unemployment_compensation=8_000.0)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_7_unemployment"], 8_000)

    def test_multiple_1099g_summed(self):
        s = make_simple_scenario()
        s.form1099_g = [
            Form1099G(payer="State A", unemployment_compensation=3_000.0),
            Form1099G(payer="State B", unemployment_compensation=5_000.0),
        ]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_7_unemployment"], 8_000)


class Sch1OtherIncomeTests(unittest.TestCase):
    def test_rtaa_to_line_8z(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(
            payer="State", rtaa_payments=500.0, taxable_grants=1_000.0,
            agriculture_payments=2_000.0, market_gain=150.0,
        )]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_8z_other_income"], 3_650)


class Sch1Line8zComponentsTests(unittest.TestCase):
    """Line 8z per component TYPE (team-lead rulings R1-R3, R7; Juno's 8z
    ruling): one nonzero type prints its Form 1099-G box caption in the 8z
    write-in; two or more print "See statement" and the statement rows list
    each type and amount. Each type is rounded on its own and 8z is the sum
    of the rounded types, so the statement foots; line 9 (8a through 8z,
    only 8z modeled) equals 8z. With no nonzero type the 8z/9 keys are
    absent (a blank write-in)."""

    KEYS = ("sch_1_line_8z_other_income", "sch_1_line_8z_description",
            "sch_1_line_8z_statement_rows", "sch_1_line_9_total_other_income")

    def _compute(self, *forms):
        s = make_simple_scenario()
        s.form1099_g = list(forms)
        return form_sch_1.compute(s, upstream={"sch_e": {}})

    def test_no_1099g_leaves_the_8z_keys_absent(self):
        out = self._compute()
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, out)

    def test_a_1099g_without_8z_components_leaves_them_absent(self):
        out = self._compute(Form1099G(payer="State",
                                      unemployment_compensation=8_000.0))
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, out)
        self.assertEqual(out["sch_1_line_7_unemployment"], 8_000)

    def test_a_single_type_prints_its_box_caption(self):
        out = self._compute(Form1099G(payer="State", taxable_grants=1_000.0))
        self.assertEqual(out["sch_1_line_8z_description"], "Taxable grants")
        self.assertEqual(out["sch_1_line_8z_other_income"], 1_000)
        self.assertEqual(out["sch_1_line_9_total_other_income"], 1_000)
        self.assertEqual(out["sch_1_line_8z_statement_rows"],
                         (("Taxable grants", 1_000),))

    def test_one_type_across_two_1099gs_is_a_single_component(self):
        out = self._compute(
            Form1099G(payer="State A", taxable_grants=600.0),
            Form1099G(payer="State B", taxable_grants=400.0))
        self.assertEqual(out["sch_1_line_8z_description"], "Taxable grants")
        self.assertEqual(out["sch_1_line_8z_statement_rows"],
                         (("Taxable grants", 1_000),))

    def test_two_or_more_types_print_see_statement_in_box_order(self):
        out = self._compute(Form1099G(
            payer="State", market_gain=150.0, rtaa_payments=500.0,
            agriculture_payments=2_000.0, taxable_grants=1_000.0))
        self.assertEqual(out["sch_1_line_8z_description"], "See statement")
        self.assertEqual(out["sch_1_line_8z_statement_rows"], (
            ("RTAA payments", 500), ("Taxable grants", 1_000),
            ("Agriculture payments", 2_000), ("Market gain", 150)))
        self.assertEqual(out["sch_1_line_8z_other_income"], 3_650)

    def test_each_type_rounds_alone_and_8z_foots_to_the_rows(self):
        out = self._compute(Form1099G(payer="State", rtaa_payments=100.5,
                                      taxable_grants=100.5))
        rows = out["sch_1_line_8z_statement_rows"]
        self.assertEqual(rows, (("RTAA payments", 101),
                                ("Taxable grants", 101)))
        self.assertEqual(out["sch_1_line_8z_other_income"],
                         sum(amount for _, amount in rows))
        self.assertEqual(out["sch_1_line_9_total_other_income"],
                         out["sch_1_line_8z_other_income"])

    def test_line_10_carries_the_rounded_8z(self):
        base = self._compute()["sch_1_line_10_total_additional_income"]
        out = self._compute(Form1099G(payer="State", rtaa_payments=100.5,
                                      taxable_grants=100.5))
        self.assertEqual(out["sch_1_line_10_total_additional_income"],
                         base + out["sch_1_line_8z_other_income"])


if __name__ == "__main__":
    unittest.main()
