"""check_placement's cache never returns another declaration's findings
(team-lead ruling, bucket b, sch_c declaration lane).

The cache keyed on ``id(decl)`` / ``id(spec)`` alone: once a declaration
built in a test was freed, CPython handed its id to the next one, and the
next call returned the freed declaration's findings -- false reds and
false greens alike. A cached entry now answers only for the very objects
it was computed from.
"""
import dataclasses
import gc
import unittest
import unittest.mock
from pathlib import Path

from tenforty.declarations import sch_c
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.verification import checks
from tenforty.verification.fill import fill_spec_for

REPO_ROOT = Path(__file__).resolve().parents[1]
YEAR = 2025
TEMPLATE = REPO_ROOT / "pdfs" / "federal" / str(YEAR) / "f1040sc.pdf"
LINES = ("F", "G", "32a")


def _unanchored(line):
    """The 2025 declaration with ``line``'s explicit anchor removed: a
    convention finding on that line alone."""
    base = sch_c.DECLARATIONS[YEAR]
    return dataclasses.replace(base, lines=tuple(
        dataclasses.replace(ln, anchor=None) if ln.line == line else ln
        for ln in base.lines))


def _lines(decl, spec):
    return {f.line for f in checks.check_placement(TEMPLATE, decl, spec)}


class PlacementCacheIdentityTests(unittest.TestCase):
    def test_colliding_ids_do_not_share_findings(self):
        # Every object gets the same id: only identity can tell them apart.
        spec = fill_spec_for(PdfSchC, YEAR)
        with unittest.mock.patch.object(
                checks, "id", create=True, new=lambda obj: 0):
            for line in LINES:
                with self.subTest(line=line):
                    self.assertEqual(_lines(_unanchored(line), spec), {line})

    def test_a_freed_declaration_hands_nothing_to_its_successor(self):
        # The real lifetime: build, check, free, rebuild a differing one.
        spec = fill_spec_for(PdfSchC, YEAR)
        for trial in range(20):
            for line in LINES:
                decl = _unanchored(line)
                with self.subTest(trial=trial, line=line):
                    self.assertEqual(_lines(decl, spec), {line})
                del decl
                gc.collect()

    def test_a_freed_spec_hands_nothing_to_its_successor(self):
        decl = sch_c.DECLARATIONS[YEAR]
        for trial in range(20):
            spec = fill_spec_for(PdfSchC, YEAR)
            if trial % 2:
                # A spec that maps nothing: every bound line is unplaced.
                spec = dataclasses.replace(spec, mapping={})
            with self.subTest(trial=trial):
                self.assertEqual(bool(_lines(decl, spec)), bool(trial % 2))
            del spec
            gc.collect()

    def test_the_same_objects_hit_the_cache(self):
        decl, spec = _unanchored("G"), fill_spec_for(PdfSchC, YEAR)
        with unittest.mock.patch.object(
                checks, "_placement", wraps=checks._placement) as computed:
            _lines(decl, spec)
            _lines(decl, spec)
        self.assertLessEqual(computed.call_count, 1)


if __name__ == "__main__":
    unittest.main()
