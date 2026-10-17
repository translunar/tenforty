"""Official line inventories, machine-extracted from the pinned templates
(emit-verification harness spec §4.1).

Each inventory lists a form-year's printed line labels with their text,
page, Part/section and position, extracted only from the tax authority's
own artifact: the printed page for federal templates (which carry no
tooltips), the /TU tooltips for California templates (with the printed page
as the fallback for generic tooltips). The committed JSONs are reviewed
data; these tests pin the extraction's hard cases, the (page, section,
label) keying, the provenance hash, and the independence rule.
"""
import ast
import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from tenforty.declarations import inventory
from tenforty.declarations.inventory import (
    extract_california,
    extract_federal,
    load,
    sha256_of,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PDFS = REPO_ROOT / "pdfs"


def _labels(lines, section=None):
    return [l.label for l in lines if section is None or l.section == section]


class FederalInventoryTests(unittest.TestCase):
    def test_f8995_2025_lines_1_to_17(self):
        lines = extract_federal(PDFS / "federal/2025/f8995.pdf")
        labels = set(_labels(lines))
        for n in range(1, 18):
            self.assertIn(str(n), labels)
        (line_10,) = [l for l in lines if l.label == "10"]
        self.assertTrue(line_10.text.startswith(
            "Qualified business income deduction before the income "
            "limitation"), line_10.text)

    def test_f8995_2025_table_rows_1i_to_1v(self):
        # Line 1's rows are printed as lowercase roman numerals beside the
        # number column ("Combine lines 1i through 1v").
        labels = _labels(extract_federal(PDFS / "federal/2025/f8995.pdf"))
        for row in ("1i", "1ii", "1iii", "1iv", "1v"):
            self.assertIn(row, labels)

    def test_sch_se_2024_sublines(self):
        labels = set(_labels(extract_federal(
            PDFS / "federal/2024/f1040sse.pdf")))
        for label in ("4a", "4b", "4c", "8a", "8b", "8c", "8d"):
            self.assertIn(label, labels)

    def test_sch_se_2024_part_i_exactly(self):
        # Pins the printed-page hard cases on one form:
        # - "1 a" printed as two words is the single label "1a";
        # - a lone "b" beside the number column carries the last number
        #   ("1b", "4b", "5b");
        # - the right-hand line-number boxes repeat each label and add none;
        # - no bare "1", "4", "5" or "8" (the numbers of lettered lines).
        lines = extract_federal(PDFS / "federal/2024/f1040sse.pdf")
        self.assertEqual(_labels(lines, "Part I"), [
            "1a", "1b", "2", "3", "4a", "4b", "4c", "5a", "5b", "6", "7",
            "8a", "8b", "8c", "8d", "9", "10", "11", "12", "13"])

    def test_sch_se_2024_footnote_markers_are_not_lines(self):
        # Page 2's footnotes are numbered 1-4 in small type under Part II;
        # only the Part II lines themselves are lines.
        lines = extract_federal(PDFS / "federal/2024/f1040sse.pdf")
        self.assertEqual(_labels(lines, "Part II"), ["14", "15", "16", "17"])

    def test_f4562_2024_recovery_periods_are_not_lines(self):
        # Part III's recovery-period column ("25 yrs.", "39 yrs.") is a
        # table of values that falls back inside the Part, not a label
        # column; line 25 and line 39 belong to Part V only.
        lines = extract_federal(PDFS / "federal/2024/f4562.pdf")
        part_iii = _labels(lines, "Part III")
        for value in ("12", "25", "30", "39", "40"):
            self.assertNotIn(value, part_iii)
        for label in ("19a", "20a", "21", "22"):
            self.assertIn(label, _labels(lines))

    def test_f8959_2024_parts_exactly(self):
        # Each Part's last right-hand line-number box sits below the next
        # Part's heading; it repeats its row's label and must not reappear
        # as a line of the next Part.
        lines = extract_federal(PDFS / "federal/2024/f8959.pdf")
        self.assertEqual(
            {s: _labels(lines, s) for s in sorted({l.section for l in lines})},
            {"Part I": ["1", "2", "3", "4", "5", "6", "7"],
             "Part II": ["8", "9", "10", "11", "12", "13"],
             "Part III": ["14", "15", "16", "17"],
             "Part IV": ["18"],
             "Part V": ["19", "20", "21", "22", "23", "24"]})

    def test_sch_d_2024_a_part_reference_is_not_a_heading(self):
        # Line 15's text ends "Then, go to Part III on the back": a
        # reference, not the Part III heading (which starts its own row).
        lines = extract_federal(PDFS / "federal/2024/f1040sd.pdf")
        (line_15,) = [l for l in lines if l.label == "15"]
        self.assertEqual(line_15.section, "Part II")
        self.assertEqual(_labels(lines, "Part III")[0], "16")

    def test_sch_b_2024_parts(self):
        # The Part II heading is printed on line 5's own row, and line 7a
        # shares its row with the Part III sidebar title.
        lines = extract_federal(PDFS / "federal/2024/f1040sb.pdf")
        self.assertEqual(_labels(lines, "Part I"), ["1", "2", "3", "4"])
        self.assertEqual(_labels(lines, "Part II"), ["5", "6"])
        self.assertEqual(_labels(lines, "Part III"), ["7a", "7b", "8"])


class DuplicateLabelTests(unittest.TestCase):
    """Review Focus 1: lines are keyed by (page, section, label). A label
    printed under two sections is two lines, never merged."""

    def test_no_inventory_has_two_lines_with_one_key(self):
        for path in sorted(inventory.INVENTORY_DIR.glob("*.json")):
            with self.subTest(inventory=path.name):
                data = json.loads(path.read_text())
                keys = Counter((l["page"], l["section"], l["label"])
                               for l in data["lines"])
                self.assertEqual([k for k, n in keys.items() if n > 1], [])

    def test_f8949_2024_lines_1_and_2_recur_in_part_i_and_part_ii(self):
        # Real recurring-label form-year (found by scanning every
        # inventory): Form 8949 (2024) prints lines 1 and 2 in Part I
        # (short-term) and again in Part II (long-term).
        lines = extract_federal(PDFS / "federal/2024/f8949.pdf")
        for label in ("1", "2"):
            with self.subTest(label=label):
                sections = [l.section for l in lines if l.label == label]
                self.assertEqual(sorted(sections), ["Part I", "Part II"])

    def test_f100s_2025_line_2_recurs_on_one_page(self):
        # Real same-page recurrence (found by scanning every inventory):
        # Form 100S (2025) page 1 prints line 2 of the main form and line 2
        # of Schedule Q Questions A and B. Only `section` tells them apart.
        lines = [l for l in extract_california(
                     PDFS / "california/2025/f100s.pdf")
                 if l.page == 1 and l.label == "2"]
        self.assertEqual(sorted(l.section for l in lines),
                         ["", "Question A", "Question B"])


    def test_schedule_x_2025_line_1_recurs_in_part_1_and_part_2(self):
        # Real same-page recurrence: Schedule X (2025) page 1 prints line 1
        # of Part 1 (amount you owe) and line 1 of Part 2 (reasons for
        # filing).
        lines = [l for l in extract_california(
                     PDFS / "california/amendments/schedule_x_2025.pdf")
                 if l.page == 1 and l.label == "1"]
        self.assertEqual(sorted(l.section for l in lines),
                         ["Part 1", "Part 2"])


class CaliforniaInventoryTests(unittest.TestCase):
    def test_f540_2025_line_8_from_its_tooltip(self):
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        (line_8,) = [l for l in lines if l.label == "8"]
        # The tooltip's own wording ("R D P" spelled out for screen
        # readers), not the printed "spouse/RDP".
        self.assertTrue(line_8.text.startswith(
            "Blind: If you (or your spouse / R D P )"), line_8.text)

    def test_f540_2025_line_7_from_the_printed_page(self):
        # No f540 year 2021-2025 has a /TU beginning "Line 7": line 7's
        # widgets carry generic tooltips ("Exemptions. For line 7, line 8,
        # ..."), so the line comes from the printed row.
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        (line_7,) = [l for l in lines if l.label == "7"]
        self.assertTrue(line_7.text.startswith("Personal:"), line_7.text)

    def test_section_from_the_tooltip_prefix(self):
        # Schedule X (2025) is the California template whose tooltips carry
        # Part prefixes: "Part 1 . Line 1 . Enter the amount you owe, ...".
        lines = extract_california(
            PDFS / "california/amendments/schedule_x_2025.pdf")
        (line_1,) = [l for l in lines
                     if l.label == "1" and l.section == "Part 1"]
        self.assertTrue(line_1.text.startswith("Enter the amount you owe"))

    def test_spaced_sub_letter_tooltips(self):
        # Schedule CA writes "Line 1 h." and "Line 3 ." in its tooltips.
        labels = set(_labels(extract_california(
            PDFS / "california/2025/sch_ca.pdf")))
        for label in ("1h", "3", "8c"):
            self.assertIn(label, labels)

    def test_cents_column_is_not_a_line(self):
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        self.assertNotIn("00", _labels(lines))


class InventoryProvenanceTests(unittest.TestCase):
    def test_every_inventory_matches_its_template(self):
        paths = sorted(inventory.INVENTORY_DIR.glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(inventory=path.name):
                data = json.loads(path.read_text())
                source = REPO_ROOT / data["source"]
                self.assertEqual(
                    data["source_sha256"], sha256_of(source),
                    f"{data['form']} {data['key']}: template {data['source']} "
                    "changed since its inventory was extracted; re-extract "
                    "it (inventory.refresh) and review the diff.")

    def test_committed_inventories_equal_a_fresh_extraction(self):
        # A sample across both extractors and every template family.
        for form, key in (("sch_se", 2024), ("f8995", 2025), ("f540", 2025),
                          ("schedule_x", 2025), ("f3115", "rev-2022-12")):
            with self.subTest(form=form, key=key):
                committed = inventory.inventory_path(form, key).read_text()
                data = json.loads(committed)
                self.assertEqual(committed, inventory.to_json(
                    form, key, data["jurisdiction"], REPO_ROOT / data["source"],
                    inventory.extract(data["jurisdiction"],
                                      REPO_ROOT / data["source"])))

    def test_inventory_set_is_every_emitted_form_template(self):
        # Drift guard: a form tenforty emits with no inventory fails, by
        # name. (Tests may read the catalog; inventory.py never does.)
        from tenforty import years
        from tenforty.mappings.catalog import CATALOG
        expected = {}
        for (jurisdiction, form), entry in CATALOG.items():
            for year in (years.FEDERAL_YEARS if jurisdiction == "federal"
                         else years.CALIFORNIA_YEARS):
                expected[(form, str(year))] = (
                    f"pdfs/{jurisdiction}/{year}/{entry.template_stem}.pdf")
        for form, revision in years.AMENDMENT_TEMPLATE_REVISIONS.items():
            expected[(form, revision)] = f"pdfs/federal/amendments/{form}.pdf"
        for form, revision in years.REVISION_KEYED_FORM_REVISIONS.items():
            expected[(form, revision)] = (
                f"pdfs/federal/revision_keyed/{form}.pdf")
        for year in years.amendable_california_years():
            expected[("schedule_x", str(year))] = (
                f"pdfs/california/amendments/schedule_x_{year}.pdf")
        actual = {}
        for path in inventory.INVENTORY_DIR.glob("*.json"):
            data = json.loads(path.read_text())
            actual[(data["form"], str(data["key"]))] = data["source"]
        self.assertEqual(sorted(set(expected) - set(actual)), [],
                         "forms with no inventory")
        self.assertEqual(sorted(set(actual) - set(expected)), [],
                         "inventories for no emitted form")
        self.assertEqual(actual, expected)

    def test_load_returns_the_committed_inventory(self):
        loaded = load("sch_se", 2024)
        self.assertEqual(loaded.source_sha256,
                         sha256_of(PDFS / "federal/2024/f1040sse.pdf"))
        self.assertEqual(
            sorted(l.key for l in loaded.lines),
            sorted(l.key for l in extract_federal(
                PDFS / "federal/2024/f1040sse.pdf")))

    def test_every_inventory_has_lines(self):
        for path in sorted(inventory.INVENTORY_DIR.glob("*.json")):
            with self.subTest(inventory=path.name):
                self.assertTrue(json.loads(path.read_text())["lines"])


class NoMappingImportTests(unittest.TestCase):
    """The independence rule, structurally: the extractor reads only the
    official templates, never tenforty's mappings, computations or
    orchestrator."""

    def test_inventory_imports_nothing_from_mappings_forms_or_orchestrator(self):
        tree = ast.parse(Path(inventory.__file__).read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                imported.append(base)
                imported += [f"{base}.{a.name}" for a in node.names]
        forbidden = [name for name in imported if any(
            name == p or name.startswith(p + ".") for p in (
                "tenforty.mappings", "tenforty.forms",
                "tenforty.orchestrator"))]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
