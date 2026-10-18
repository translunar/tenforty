"""A declared exemption for a ruled paper line the inventory cannot print
(team-lead ruling b1, sch_c declaration lane).

Schedule C Part V prints nine unlabeled grid rows; the inventory extractor
captures only labeled lines, so row 1's two bound lines ("row1(description)",
"row1(amount)", synthetic ids ruled in ADDENDUM 3) are absent from every
inventory. A line carrying ``inventory_exemption`` (a non-empty reason) is
accepted by validate's [inventory] check ONLY while it is absent; if a
regenerated inventory prints it, the exemption is stale and validate
reports it. Every exemption in force is enumerated (never silent), and the
same field excludes the line from placement (no below-a-heading relation
exists yet), while its value and ink checks still run.
"""
import unittest
from pathlib import Path

from tenforty.declarations import sch_c
from tenforty.declarations.model import DeclaredLine, FormDeclaration
from tenforty.declarations.validate import exemptions_in_force, validate
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.verification.checks import check_placement
from tenforty.verification.fill import fill_spec_for

REPO_ROOT = Path(__file__).resolve().parents[1]
_REASON = ("ADDENDUM 3: the official paper prints nine unlabeled Part V rows; "
           "the inventory extractor captures only labeled lines")


def _decl(*lines, key=2025):
    return FormDeclaration(form=("federal", "sch_c"), key=key, lines=lines,
                           not_printed={})


def _line(line, section="Part V", exemption=None, key="k"):
    return DeclaredLine(line=line, description="d", key=key, kind="amount",
                        section=section, inventory_exemption=exemption)


class InventoryExemptionTests(unittest.TestCase):
    def test_an_absent_line_without_an_exemption_is_refused(self):
        self.assertEqual([f.check for f in validate(_decl(
            _line("row1(amount)")))], ["inventory"])

    def test_an_exempt_absent_line_is_accepted(self):
        self.assertEqual(validate(_decl(
            _line("row1(amount)", exemption=_REASON))), [])

    def test_an_exemption_on_a_printed_line_is_stale(self):
        # Line 48 IS printed: an exemption there can no longer be true.
        findings = validate(_decl(
            _line("48", exemption=_REASON, key="sch_c_line_48_total_other_expenses")))
        self.assertEqual([f.check for f in findings], ["inventory_exemption"])
        self.assertIn("stale", findings[0].message)

    def test_a_blank_exemption_is_refused(self):
        findings = validate(_decl(_line("row1(amount)", exemption="  ")))
        self.assertIn("inventory_exemption", [f.check for f in findings])

    def test_every_exemption_in_force_is_enumerated(self):
        decl = _decl(_line("row1(description)", exemption=_REASON),
                     _line("row1(amount)", exemption=_REASON),
                     _line("48", key="sch_c_line_48_total_other_expenses"))
        self.assertEqual(
            [line_id for line_id, _ in exemptions_in_force(decl)],
            [("Part V", "row1(description)"), ("Part V", "row1(amount)")])


class SchCExemptionsTests(unittest.TestCase):
    """Exactly Part V row 1's two lines carry the exemption, every year."""

    def test_exactly_part_v_row_1_is_exempt(self):
        for year, decl in sorted(sch_c.DECLARATIONS.items()):
            with self.subTest(year=year):
                self.assertEqual(
                    [line_id for line_id, _ in exemptions_in_force(decl)],
                    [("Part V", "row1(description)"), ("Part V", "row1(amount)")])

    def test_exempt_lines_are_excluded_from_placement(self):
        for year, decl in sorted(sch_c.DECLARATIONS.items()):
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"
            lines = {f.line for f in check_placement(
                template, decl, fill_spec_for(PdfSchC, year))}
            with self.subTest(year=year):
                self.assertNotIn("row1(description)", lines)
                self.assertNotIn("row1(amount)", lines)


if __name__ == "__main__":
    unittest.main()
