"""The Schedule B declaration validates against each year's own inventory,
covers the computation's keys, and its anchor phrases print (emit-
verification protocol step 4; adjudication
/private/tmp/pilot-packet-sch_b/ADJUDICATION.md).

The declaration is inert until graduation: registration and the pending
removal land together, so these tests read the module directly, not the
registry.
"""
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry, sch_b
from tenforty.declarations.anchors import NearLabel
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.declarations.validate import validate
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "sch_b")
BOUND_KEYS = {"interest_payer_1", "interest_amount_1", "total_interest",
              "excludable_savings_bond", "taxable_interest",
              "dividend_payer_1", "dividend_amount_1",
              "total_ordinary_dividends"}
TWO_STATE = {"interest_payer_1", "interest_amount_1", "dividend_payer_1",
             "dividend_amount_1"}


class SchBDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_b.DECLARATIONS), list(YEARS))
        for year in YEARS:
            decl = sch_b.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertIsInstance(decl, FormDeclaration)
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)
                self.assertEqual(len(decl.lines), 11)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_b.DECLARATIONS[year],
                                    siblings=sch_b.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_only_the_composed_amount_cells_carry_exemptions(self):
        # By design (Q1 composed sub-lines); no defect exemptions.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    sorted(ln.line for ln in sch_b.DECLARATIONS[year].lines
                           if ln.inventory_exemption),
                    ["1(Amount)", "5(Amount)"])

    def test_bound_keys_and_header(self):
        for year in YEARS:
            decl = sch_b.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertEqual({ln.key for ln in decl.lines if ln.key},
                                 BOUND_KEYS)
                self.assertEqual(set(decl.not_printed),
                                 {"taxpayer_name", "taxpayer_ssn"})

    def test_postures(self):
        # Totals value-only; row-1 payer cells two-state; Part III unserved.
        for year in YEARS:
            lines = sch_b.DECLARATIONS[year].lines
            with self.subTest(year=year):
                self.assertEqual(
                    {ln.key for ln in lines if ln.key and ln.single_state
                     is None}, TWO_STATE)
                self.assertEqual(
                    {ln.key for ln in lines if ln.single_state == "value"},
                    BOUND_KEYS - TWO_STATE)
                self.assertEqual(
                    sorted(ln.line for ln in lines
                           if ln.single_state == "nothing"),
                    ["7a", "7b", "8"])

    def test_the_documented_witness_discrepancies_are_the_raw_findings(self):
        for year in YEARS:
            decl = sch_b.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            raw = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("sch_b", year))
            in_force = crosscheck_mod.discrepancies_in_force(sch_b, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in raw})
                self.assertEqual(crosscheck_mod.crosscheck(
                    decl, propose.stylesheet_lines("sch_b", year),
                    discrepancies=in_force), [])

    def test_explicit_phrases_print_exactly_once(self):
        # The anchor evaluator matches whole printed tokens: a phrase that
        # ends mid-token prints zero times.
        for year in YEARS:
            words = anchor_eval._page_words(
                str(REPO_ROOT / "pdfs" / "federal" / str(year)
                    / "f1040sb.pdf"), 0)
            for ln in sch_b.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)

    def test_ships_inert(self):
        # Graduation (registration + unpending) is a later, separate lane.
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


if __name__ == "__main__":
    unittest.main()
