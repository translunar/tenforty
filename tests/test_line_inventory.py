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
import unittest.mock
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
        # A federal-only vehicle would leave the drop-section mutation
        # green: no federal template repeats a label in two Parts on ONE
        # page, so `page` alone already separates every federal recurrence.
        lines = [l for l in extract_california(
                     PDFS / "california/2025/f100s.pdf")
                 if l.page == 1 and l.label == "2"]
        self.assertEqual(sorted(l.section for l in lines),
                         ["", "Schedule Q Question A",
                          "Schedule Q Question B"])


    def test_schedule_x_2025_line_1_recurs_in_part_1_and_part_2(self):
        # Real same-page recurrence: Schedule X (2025) page 1 prints line 1
        # of Part I (amount you owe) and line 1 of Part II (reasons for
        # filing).
        lines = [l for l in extract_california(
                     PDFS / "california/amendments/schedule_x_2025.pdf")
                 if l.page == 1 and l.label == "1"]
        self.assertEqual(sorted(l.section for l in lines),
                         ["Part I", "Part II"])


class CaliforniaSectionTests(unittest.TestCase):
    """California sections come from the printed page's own headings
    (Schedule X, Part N, Section X, at the left margin), positionally, as
    for federal. A tooltip's prefix appears only on the first line of a
    Part, so it cannot be the source."""

    def test_f100s_2025_page_4_line_3_is_two_lines(self):
        # Schedule F line 3 ("Gross profit") and Schedule L line 3
        # ("Inventories") share page 4 and label 3.
        lines = [l for l in extract_california(
                     PDFS / "california/2025/f100s.pdf")
                 if l.page == 4 and l.label == "3"]
        self.assertEqual(sorted((l.section, l.text.split(".")[0])
                                for l in lines),
                         [("Schedule F", "Gross profit"),
                          ("Schedule L", "Inventories")])

    def test_schedule_x_2025_line_2_is_two_lines(self):
        # Part I line 2 ("Overpaid tax...") and Part II line 2 ("Provide
        # further explanation...") share page 1; only each Part's first
        # tooltip carries a "Part N" prefix.
        lines = [l for l in extract_california(
                     PDFS / "california/amendments/schedule_x_2025.pdf")
                 if l.page == 1 and l.label == "2"]
        self.assertEqual(sorted((l.section, l.text.split(",")[0])
                                for l in lines),
                         [("Part I", "Overpaid tax"),
                          ("Part II", "Provide further explanation of "
                           "reason or reasons for amending below. If "
                           "needed")])


    def test_every_section_heading_prints_at_the_left_margin(self):
        # Premise of the left-margin heading rule: no FTB template prints a
        # section heading in a column (so no heading needs an x-extent).
        # The only heading-shaped words that start a row beyond the margin
        # are form-name footers and one in-text reference; a new one fails
        # here instead of being silently ignored.
        import re
        found = set()
        for path in sorted(inventory.INVENTORY_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["jurisdiction"] != "california":
                continue
            for words in inventory._page_words(REPO_ROOT / data["source"]):
                for w in words:
                    if (w[4] not in inventory._HEADING_WORDS
                            or w[0] <= inventory._LEFT_MARGIN):
                        continue
                    row = sorted(v for v in words if v is not w and abs(
                        v[1] - w[1]) < inventory._SAME_ROW)
                    if any(v[2] > w[0] - inventory._LABEL_GAP and v[0] < w[0]
                           for v in row):
                        continue
                    right = [v for v in row if v[0] >= w[2] - 0.5]
                    if right and inventory._HEADING_ID.match(right[0][4]):
                        found.add((data["form"], w[4],
                                   re.sub(r"\d", "N", right[0][4])))
        self.assertEqual(sorted(found), [
            ("f100s_k1", "Schedule", "K-N"),   # footer "Schedule K-1 (100S)"
            ("f540", "Schedule", "G-N"),       # text "Schedule G-1 FTB 5870A"
            ("sch_d_540", "Schedule", "D"),    # footer "Schedule D (540)"
            ("schedule_x", "Schedule", "X"),   # footer "Schedule X <year>"
        ])


class TooltipPrefixCensusTests(unittest.TestCase):
    """Ruling 4: every tooltip-prefix shape the FTB templates use is
    classified in the pinned census; a new shape fails loudly."""

    def _observed_shapes(self) -> set[str]:
        from pypdf import PdfReader
        shapes = set()
        for path in sorted(inventory.INVENTORY_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["jurisdiction"] != "california":
                continue
            reader = PdfReader(str(REPO_ROOT / data["source"]))
            for page in reader.pages:
                for ref in page.get("/Annots") or []:
                    tip = inventory._tooltip(ref.get_object())
                    if tip is None:
                        continue
                    tip = " ".join(tip.split())
                    m = inventory._TOOLTIP_LINE.search(tip)
                    if m:
                        shapes.add(inventory.prefix_shape(tip[:m.start()]))
        return shapes

    def test_census_is_exactly_the_observed_shapes(self):
        self.assertEqual(sorted(self._observed_shapes()),
                         sorted(inventory._PREFIX_CENSUS))

    def test_an_unknown_shape_refuses(self):
        census = dict(inventory._PREFIX_CENSUS)
        del census["Assets"]
        with unittest.mock.patch.object(inventory, "_PREFIX_CENSUS", census):
            with self.assertRaisesRegex(inventory.UnknownTooltipShapeError,
                                        "'Assets'"):
                extract_california(PDFS / "california/2025/f100s.pdf")

    def test_an_address_line_is_not_a_form_line(self):
        # The preparer's "Firm's name ... and address. Line 1 of 2." (Form
        # 100S, page 3) names an address line, not line 1. Tested on the
        # tooltip itself: on the page its key collides with Schedule J line
        # 1, which the widget order happens to keep, so only the parse can
        # show the rule.
        for tip in (
                "Firm's name (or yours, if self-employed) and address. "
                "Line 1 of 2.",
                "Firm's name (or yours if self-employed) and address. "
                "Line 2 of 2."):
            with self.subTest(tip=tip):
                self.assertIsNone(inventory.tooltip_line(tip))
        self.assertEqual(inventory.tooltip_line(
            "Schedule J Line 1. Last In First Out (LIFO) recapture.")[:2],
            ("1", "Last In First Out (LIFO) recapture."))

    def test_a_prefix_that_contradicts_the_printed_page_refuses(self):
        # Reachable negative space for the cross-check: with the printed
        # headings withheld, Schedule X's "Part 1 . Line 1" tooltip states
        # a Part the widget no longer sits under.
        with unittest.mock.patch.object(
                inventory, "_printed_headings", lambda pdf: []):
            with self.assertRaisesRegex(ValueError, "states 'Part I'"):
                extract_california(
                    PDFS / "california/amendments/schedule_x_2025.pdf")

    def test_ftb3532_part_words_cross_check_in_either_case(self):
        # FTB 3532's tooltips name Parts as words: "Part One." (2023),
        # "Part one." (2024), "Part three. Qualifying Person Information."
        # (2025). Each must state the printed Part, or the cross-check
        # would assert nothing.
        for prefix, stated in (("Part One. ", ["Part I"]),
                               ("Part one. ", ["Part I"]),
                               ("Part two. ", ["Part II"]),
                               ("Part three. Qualifying Person Information. ",
                                ["Part III"])):
            with self.subTest(prefix=prefix):
                self.assertEqual(inventory._tooltip_sections(prefix), stated)

    def test_only_a_clause_starting_with_a_name_states_a_section(self):
        self.assertEqual(inventory._tooltip_sections(
            "Section B – Additional Income from federal Schedule 1 "
            "(Form 1040). "), ["Section B"])
        self.assertEqual(inventory._tooltip_sections(
            "Part One. Income Adjustment Schedule. Section A. Income from "
            "federal Form 1040 or 1040-SR. "), ["Part I", "Section A"])


class SameRowLabelAttributionTests(unittest.TestCase):
    """A printed line's label is attributed robustly to sub-point jitter in
    BOTH axes (extractor-ordering lane): a sub-letter a thousandth of a
    point past the reach, or sorting a thousandth of a point below the
    right-hand line-number box on its row, still makes the line with its
    printed text. Evidence: FTB 3532 (2025) page 1, where "a" sits at
    x0 46.998, "b"-"f" at 47.001 (Part I) and 47.0 (Part II) against a
    reach limit of exactly 47.0, and each box sorts 0.001 pt above its
    sub-letter."""

    _PRINTED = {
        ("Part I", "1a"): "Not legally married/RDP during 2025",
        ("Part I", "1b"): "Surviving spouse/RDP",
        ("Part I", "1c"): "Marriage/RDP was annulled",
        ("Part I", "1d"): "Received final decree of divorce",
        ("Part I", "1e"): "Legally married/RDP and did not live with",
        ("Part I", "1f"): "Legally married/RDP and lived with",
        ("Part II", "2b"): "Grandchild, brother, sister",
        ("Part II", "2c"): "Eligible foster child",
        ("Part II", "2d"): "Father, mother, stepfather, or stepmother",
    }

    def test_ftb3532_2025_sub_lines_carry_their_printed_text(self):
        lines = {(l.section, l.label): l for l in extract_california(
            PDFS / "california/2025/ftb3532.pdf")}
        for key, printed in self._PRINTED.items():
            with self.subTest(line=key):
                self.assertTrue(lines[key].text.startswith(printed),
                                lines[key].text)
                # Made by the printed sub-letter, not the right-hand box.
                self.assertLess(lines[key].bbox[0], 60)

    def _synthetic(self, letter_x, letter_y, box_y):
        # One page: line "1" in the number column, its sub-line "a" with
        # caption text, and the right-hand box "1a" on the same row.
        h = 11.0
        words = [(36.0, 100.0, 41.0, 100.0 + h, "1"),
                 (47.0, 100.0, 70.0, 100.0 + h, "Total"),
                 (36.0, 80.0, 41.0, 80.0 + h, "2"),
                 (36.0, 160.0, 41.0, 160.0 + h, "3"),
                 (letter_x, letter_y, letter_x + 5, letter_y + h, "a"),
                 (letter_x + 11, letter_y, letter_x + 60, letter_y + h,
                  "Caption"),
                 (534.0, box_y, 546.0, box_y + h, "1a"),
                 (534.0, 100.0, 546.0, 100.0 + h, "1")]
        with unittest.mock.patch.object(inventory, "_page_words",
                                        lambda pdf: [words]):
            return {l.label: l for l in extract_federal(Path("synthetic"))}

    def test_knife_edge_in_both_axes_stops_mattering(self):
        for letter_x in (46.998, 47.0, 47.001):
            for letter_y, box_y in ((120.001, 120.0), (120.0, 120.001)):
                with self.subTest(x=letter_x, letter_y=letter_y,
                                  box_y=box_y):
                    line = self._synthetic(letter_x, letter_y, box_y)["1a"]
                    self.assertEqual(line.text, "Caption")
                    self.assertEqual(line.bbox[0], round(letter_x, 2))

    def test_a_stray_digit_no_longer_holds_a_real_lines_key(self):
        # Schedule E (2021): the property-type code "7 Self-Rental" made an
        # empty line 7 that blocked the real line 7; the printed label now
        # wins and the line carries its own text.
        lines = extract_federal(PDFS / "federal/2021/f1040se.pdf")
        (line_7,) = [l for l in lines
                     if l.label == "7" and l.section == "Part I"]
        self.assertEqual(line_7.text, "Cleaning and maintenance")

    def test_a_line_with_text_is_never_rewritten(self):
        # The narrowed rule: the left label wins only over an EMPTY line.
        # Form 100S (2021) Schedule F line 1's printed-page row keeps its
        # own text (an unconditional left-wins rewrote rows like it).
        lines = extract_california(PDFS / "california/2021/f100s.pdf")
        (line_1,) = [l for l in lines
                     if l.page == 4 and l.section == "Schedule F"
                     and l.label == "1"]
        self.assertTrue(line_1.text.startswith("a) Gross receipts or sales"),
                        line_1.text)


class Ftb3532InventoryTests(unittest.TestCase):
    """FTB 3532 (2021-2025): Parts I-III from the printed headings. 2025
    prints Parts I and II as radio groups whose tooltips name no line, so
    those lines come from the printed page."""

    def test_parts_from_the_printed_headings_every_year(self):
        for year in range(2021, 2026):
            with self.subTest(year=year):
                lines = load("ftb3532", year).lines
                by_section = {}
                for l in lines:
                    by_section.setdefault(l.section, set()).add(l.label)
                self.assertEqual(sorted(by_section),
                                 ["Part I", "Part II", "Part III"])
                self.assertLessEqual(
                    {"1a", "1b", "1c", "1d", "1e", "1f"}, by_section["Part I"])
                self.assertLessEqual(
                    {"2a", "2b", "2c", "2d", "2e"}, by_section["Part II"])
                self.assertLessEqual(
                    {"3", "3a", "3b", "4", "5"}, by_section["Part III"])

    def test_2025_parts_i_and_ii_come_from_the_printed_page(self):
        # Asserts the in-memory InventoryLine.source of a FRESH extraction
        # only (the JSON stores `source` only for tooltip lines). The nine
        # sub-lines' printed text is pinned in SameRowLabelAttributionTests.
        lines = {(l.section, l.label): l for l in extract_california(
            PDFS / "california/2025/ftb3532.pdf")}
        self.assertEqual(lines[("Part I", "1a")].source, "printed")
        self.assertEqual(lines[("Part III", "3")].source, "tooltip")


class CaliforniaInventoryTests(unittest.TestCase):
    def test_f540_2025_line_8_from_its_tooltip(self):
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        (line_8,) = [l for l in lines if l.label == "8"]
        # The tooltip's own wording ("R D P" spelled out for screen
        # readers), not the printed "spouse/RDP".
        self.assertTrue(line_8.text.startswith(
            "Blind: If you (or your spouse / R D P )"), line_8.text)

    def test_f540_2025_line_7_from_its_tooltip_after_a_preamble(self):
        # Line 7's tooltip opens with the exemptions preamble ("Exemptions.
        # For line 7, line 8, ... Whole dollars only.") and only then names
        # "Line 7. Personal: ...": the first "Line N" token anywhere counts.
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        (line_7,) = [l for l in lines if l.label == "7"]
        self.assertTrue(line_7.text.startswith(
            "Personal: If you checked box 1, 3, or 4 above, enter 1 in the "
            "box."), line_7.text)

    def test_f540_2025_line_1_from_the_printed_page(self):
        # The filing-status boxes' tooltips name no line ("Filing status
        # ..."), so line 1 ("Single") comes from the printed row.
        lines = extract_california(PDFS / "california/2025/f540.pdf")
        (line_1,) = [l for l in lines if l.label == "1"]
        self.assertEqual(line_1.text, "Single")

    def test_printed_section_agrees_with_the_tooltip_prefix(self):
        # Schedule X (2025): the tooltip says "Part 1 . Line 1 . Enter the
        # amount you owe, ..."; the page prints "Part I". The printed
        # heading is the source, the prefix a cross-check (extraction
        # refuses a disagreement).
        lines = extract_california(
            PDFS / "california/amendments/schedule_x_2025.pdf")
        (line_1,) = [l for l in lines
                     if l.label == "1" and l.section == "Part I"]
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
