"""The Schedule D declaration validates against each year's own inventory
(emit-verification protocol step 4; adjudication
/private/tmp/pilot-packet-sch_d/ADJUDICATION.md).

The module ships inert: graduation (registration in
tenforty.declarations.forms with the pending removal) is a later, separate
step, so this test reads the module directly, not the registry.
"""
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry, sch_d
from tenforty.declarations.anchors import NearLabel
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.declarations.validate import validate
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "sch_d")


class SchDDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_d.DECLARATIONS), list(YEARS))
        for year in YEARS:
            decl = sch_d.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertIsInstance(decl, FormDeclaration)
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_d.DECLARATIONS[year],
                                    siblings=sch_d.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_the_documented_witness_discrepancies_are_the_raw_findings(self):
        # The wired in-force pin: every documented entry is a real raw
        # stylesheet cross-check finding, and every raw finding documented.
        for year in YEARS:
            decl = sch_d.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            raw = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("sch_d", year))
            in_force = crosscheck_mod.discrepancies_in_force(sch_d, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in raw})
                self.assertEqual(crosscheck_mod.crosscheck(
                    decl, propose.stylesheet_lines("sch_d", year),
                    discrepancies=in_force), [])

    def test_explicit_phrases_print_exactly_once(self):
        # The anchor evaluator matches whole printed tokens; a phrase that
        # ends mid-token ("partnerships" for the printed "partnerships,")
        # prints zero times. Each explicit phrase prints once on its page.
        for year in YEARS:
            template = str(REPO_ROOT / "pdfs" / "federal" / str(year)
                           / "f1040sd.pdf")
            for ln in sch_d.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                page = 1 if ln.section == "Part III" else 0
                words = anchor_eval._page_words(template, page)
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)

    def test_ships_inert(self):
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


if __name__ == "__main__":
    unittest.main()
