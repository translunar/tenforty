"""The Schedule SE declaration validates against each year's own inventory
(emit-verification protocol step 4).

The declaration is inert until graduation: registration and the pending
removal land together (ruling 2026-10-17), so this test reads the module
directly, not the registry.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import sch_se
from tenforty.declarations.anchors import NearLabel
from tenforty.declarations.validate import validate
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import emit_manifest
from tenforty.verification.batteries import BATTERIES
from tenforty.verification.coverage import coverage_cells
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


# Cells no battery can cover yet: on the line 8a at-or-above-wage-base branch
# the form says "skip lines 8b through 10" (blank), but the native pipeline
# prints 8d, 9 and 10. Routed to the sch-se-skip-branch-blanks lane, which
# blocks graduation; a wage-base battery row arrives with that fix. This set
# must then become empty.
BLOCKED_ON_SKIP_BRANCH = {"8d", "9", "10"}
SCH_SE = ("federal", "sch_se")
COVERED_BATTERIES = ("sch_c_battery", "emit_battery_sch_se")


def _sch_se_records():
    """(scenario, RecordedForm) for every Schedule SE the covered batteries
    emit natively (no expected values: the states are observed)."""
    manifest = emit_manifest.load_manifest()
    records = []
    for battery in BATTERIES:
        if battery.name not in COVERED_BATTERIES:
            continue
        for name, year, build in battery.scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = manifest.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            out = Path(tempfile.mkdtemp()) / "out"
            records += [(rid, rec) for rec in emit_manifest.emit(
                battery, build(), out).record if rec.form == SCH_SE]
    return records


class SchSeCoverageTests(unittest.TestCase):
    """Coverage over this declaration (read directly; it is not registered
    until graduation): every cell is covered except the skip-branch
    nothing-cells, blocked on the routed compute fix. sch_c_battery covers
    2022-2025; emit_battery_sch_se adds 2021."""

    def test_the_battery_is_registered(self):
        self.assertIn("emit_battery_sch_se", [b.name for b in BATTERIES])

    def test_only_the_skip_branch_cells_are_uncovered(self):
        decls = [sch_se.DECLARATIONS[y] for y in YEARS]
        report = coverage_cells(_sch_se_records(), decls)
        self.assertEqual(
            sorted(report.uncovered, key=str),
            sorted(((SCH_SE, d.key, line, "nothing") for d in decls
                    for line in BLOCKED_ON_SKIP_BRANCH), key=str))
