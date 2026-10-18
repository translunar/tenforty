"""Checkbox lines carry explicit anchors (team-lead ruling b3, sch_c
declaration lane).

The default federal anchor, ``RowLabel(line)``, reads the marker probe,
which stamps text fields only and recognizes digit-led line tokens only: a
checkbox, or a letter-labeled line, can never be located by it. A bound
line of kind ``checkbox`` that relies on the default is therefore a named
placement finding of its own, never a geometry finding it could not have
passed. A checkbox with an explicit anchor is evaluated as usual; key-less
checkboxes (unserved, preprinted) have no field and are untouched.
"""
import dataclasses
import unittest
from pathlib import Path

from tenforty.declarations import sch_c
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.verification.checks import check_placement
from tenforty.verification.fill import fill_spec_for

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
CONVENTION = "checkbox lines carry explicit anchors"


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"


def _with_anchor(decl, line, anchor):
    return dataclasses.replace(decl, lines=tuple(
        dataclasses.replace(ln, anchor=anchor) if ln.line == line else ln
        for ln in decl.lines))


def _findings(year, decl):
    return {f.line: f for f in check_placement(
        _template(year), decl, fill_spec_for(PdfSchC, year))}


class CheckboxAnchorConventionTests(unittest.TestCase):
    def test_a_bound_checkbox_on_the_default_anchor_is_a_named_finding(self):
        for year in YEARS:
            for line in ("F", "G", "32a"):
                decl = _with_anchor(sch_c.DECLARATIONS[year], line, None)
                with self.subTest(year=year, line=line):
                    finding = _findings(year, decl).get(line)
                    self.assertIsNotNone(finding)
                    self.assertEqual(finding.check, "placement")
                    self.assertIn(CONVENTION, finding.message)

    def test_an_explicit_checkbox_anchor_is_evaluated_not_flagged(self):
        # Line F's explicit anchor places; a wrong explicit anchor fails on
        # geometry, not on the convention.
        for year in YEARS:
            decl = sch_c.DECLARATIONS[year]
            wrong = _with_anchor(decl, "F", NearLabel(
                "Accrual", LabelRelation.LEFT_OF))
            with self.subTest(year=year):
                self.assertNotIn("F", _findings(year, decl))
                finding = _findings(year, wrong).get("F")
                self.assertIsNotNone(finding)
                self.assertNotIn(CONVENTION, finding.message)

    def test_non_checkbox_lines_keep_the_default_anchor(self):
        # Line 28 (amount, default RowLabel) still places with no anchor.
        for year in YEARS:
            decl = sch_c.DECLARATIONS[year]
            line_28 = next(ln for ln in decl.lines if ln.line == "28")
            with self.subTest(year=year):
                self.assertIsNone(line_28.anchor)
                self.assertNotIn("28", _findings(year, decl))


if __name__ == "__main__":
    unittest.main()
