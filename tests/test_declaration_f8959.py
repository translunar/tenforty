"""The Form 8959 declaration validates against each year's own inventory,
covers every computation key, and its anchor phrases print (emit-
verification protocol step 4; adjudication
/private/tmp/pilot-packet-8959/ADJUDICATION.md).

These tests read the module directly, not the registry: declaration
modules are side-effect-free, and registration lives in
tenforty.declarations.forms (8959 graduated there).
"""
import unittest
from pathlib import Path

from tenforty.declarations import f8959, propose, registry
from tenforty.declarations.anchors import NearLabel
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.declarations.validate import validate
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "8959")
LINE_KEYS = {f"f8959_line_{n}" for n in range(1, 25)}
OUTPUT_KEYS = LINE_KEYS | {"taxpayer_name", "taxpayer_ssn"}


class F8959DeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(f8959.DECLARATIONS), list(YEARS))
        for year in YEARS:
            decl = f8959.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertIsInstance(decl, FormDeclaration)
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)
                self.assertEqual(len(decl.lines), 24)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(f8959.DECLARATIONS[year],
                                    siblings=f8959.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_no_line_carries_an_inventory_exemption(self):
        # The inventory is defect-free and every line is an inventory line
        # (no composed sub-lines): zero exemptions.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    [ln.line for ln in f8959.DECLARATIONS[year].lines
                     if ln.inventory_exemption], [])

    def test_every_output_key_is_bound_or_not_printed(self):
        for year in YEARS:
            decl = f8959.DECLARATIONS[year]
            bound = {ln.key for ln in decl.lines if ln.key}
            with self.subTest(year=year):
                self.assertEqual(bound, LINE_KEYS)
                self.assertEqual(bound | set(decl.not_printed), OUTPUT_KEYS)

    def test_every_line_is_value_only(self):
        # forms/f8959.compute sets all 24 keys on every Form 8959.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    {ln.single_state for ln in f8959.DECLARATIONS[year].lines},
                    {"value"})

    def test_the_documented_witness_discrepancies_are_the_raw_findings(self):
        # The wired in-force pin: every documented entry is a real raw
        # stylesheet cross-check finding, and every raw finding documented.
        for year in YEARS:
            decl = f8959.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            raw = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("8959", year))
            in_force = crosscheck_mod.discrepancies_in_force(f8959, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in raw})
                self.assertEqual(crosscheck_mod.crosscheck(
                    decl, propose.stylesheet_lines("8959", year),
                    discrepancies=in_force), [])

    def test_explicit_phrases_print_exactly_once(self):
        # The anchor evaluator matches whole printed tokens; a phrase that
        # ends mid-token ("box 5" for the printed "box 5.") prints zero
        # times. Each explicit phrase prints once on the page.
        for year in YEARS:
            template = str(REPO_ROOT / "pdfs" / "federal" / str(year)
                           / "f8959.pdf")
            words = anchor_eval._page_words(template, 0)
            for ln in f8959.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)

    def test_graduated(self):
        # Graduated: registered for every year and off the pending list,
        # together (a registered form that is still pending is a hard
        # registry error).
        self.assertNotIn(FORM, PENDING_DECLARATIONS)
        for year in YEARS:
            with self.subTest(year=year):
                self.assertIs(registry.for_form(FORM, year),
                              f8959.DECLARATIONS[year])


if __name__ == "__main__":
    unittest.main()
