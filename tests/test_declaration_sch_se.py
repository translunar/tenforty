"""The Schedule SE declaration validates against each year's own inventory
(emit-verification protocol step 4).

The declaration is inert until graduation: registration and the pending
removal land together (ruling 2026-10-17), so this test reads the module
directly, not the registry.
"""
import unittest

from tenforty.declarations import sch_se
from tenforty.declarations.anchors import NearLabel
from tenforty.declarations.validate import validate
from tenforty.verification import anchors as anchor_eval
from tests.helpers import REPO_ROOT

YEARS = (2021, 2022, 2023, 2024, 2025)

# The one known finding per year. The official form prints line A (the Form
# 4361 checkbox; MeF ExemptForm4361Ind), but the committed PDF inventory
# omits it: line A has no left-number-box label, so the extractor misses it.
# The declaration keeps line A (ruling 2026-10-17). The extractor fix is a
# routed lane item due before sch_se graduates; when it lands, this
# expectation must become [] (the exact comparison forces the flip).
KNOWN_INVENTORY_GAP = [("A", "inventory")]


class SchSeDeclarationValidatesTests(unittest.TestCase):

    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_se.DECLARATIONS), list(YEARS))
        for year in YEARS:
            with self.subTest(year=year):
                decl = sch_se.DECLARATIONS[year]
                self.assertEqual(decl.form, ("federal", "sch_se"))
                self.assertEqual(decl.key, year)

    def test_validation_finds_only_the_known_inventory_gap(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_se.DECLARATIONS[year])
                self.assertEqual(
                    [(f.line, f.check) for f in findings],
                    KNOWN_INVENTORY_GAP,
                    "\n".join(f.message for f in findings))


class SchSeAnchorPhrasesPrintOnceTests(unittest.TestCase):
    """Every explicit anchor phrase prints exactly once on that year's
    official template, under the evaluator's own semantics (token-exact
    against ``pdftotext -bbox`` words, so a trailing "31;" or "4b." is part
    of its token). Every anchored Schedule SE line is in Part I, on page 1.
    """

    def test_each_phrase_prints_exactly_once(self):
        for year in YEARS:
            template = str(REPO_ROOT / "pdfs" / "federal" / str(year)
                           / "f1040sse.pdf")
            words = anchor_eval._page_words(template, 0)
            for ln in sch_se.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)
