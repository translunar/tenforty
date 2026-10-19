"""Official line inventories, machine-extracted from the pinned templates.

For each form and tax year (or revision), the printed line labels with
their text, page, Part/section and position, taken ONLY from the tax
authority's own artifact (spec 2026-10-17 emit-verification harness §4.1):

* Federal templates carry no tooltips, so their lines come from the printed
  page: ``pdftotext -bbox-layout`` words, line-number tokens in the page's
  label columns, the same-row text to the right of each label, and the
  ``Part <roman>`` headings the label sits under.
* California templates carry ``/TU`` tooltips reading "Line 12. ..."; lines
  come from those, and any printed label whose widgets carry only a generic
  tooltip is taken from the printed page the federal way.

Lines are keyed by ``(page, section, label)``: a label that recurs under
two Parts (or Questions) is two lines, never merged. This module never
reads tenforty's own mappings, computations or orchestrator; that is the
independence rule (pinned by NoMappingImportTests).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

INVENTORY_DIR = Path(__file__).parent / "inventories"
REPO_ROOT = Path(__file__).resolve().parents[2]

_XHTML = "{http://www.w3.org/1999/xhtml}"
# A printed line number: 1-3 digits, no leading zero (so a cents column's
# "00" is not a line), optionally a lowercase sub-letter ("4a").
_NUMBER = re.compile(r"^[1-9]\d{0,2}[a-z]?$")
# A sub-line marker printed on its own beside the number column: a letter,
# or a lowercase roman row numeral (f8995 rows 1i-1v).
_SUBLINE = re.compile(r"^(?:[a-z]|ii|iii|iv|vi|vii|viii)$")
_ROMAN = re.compile(r"^[IVX]+$")
_LEADER = re.compile(r"^[.\s]+$")
_SAME_ROW = 2.5        # pt: words whose tops differ by less share a row
_LABEL_GAP = 8.0       # pt: a label has no word ending within this to its left
_COMPOSITE_GAP = 6.0   # pt: "1" + "a" printed as two words form "1a"
_SUBLINE_REACH = 10.0  # pt: a sub-letter sits this far right of the numbers
# pt: sub-point jitter in the template's own coordinates. FTB 3532 (2025)
# prints its sub-letters at x0 46.998 / 47.0 / 47.001 against a reach limit
# of exactly 47.0, and each right-hand line-number box 0.001 pt above its
# sub-letter: attribution must not turn on a thousandth of a point.
_JITTER = 0.01
_COLUMN_GAP = 8.0      # pt: label x-positions closer than this share a column
_BOX_REPEAT = 14.0     # pt: a line-number box repeats its row's label
_FULL_HEIGHT = 0.8     # a label at least this fraction of the median height
                       # (footnote markers are smaller)


@dataclasses.dataclass(frozen=True)
class InventoryLine:
    page: int
    section: str
    label: str
    text: str
    bbox: tuple[float, float, float, float]
    # Where the line was read: "tooltip" (an FTB /TU naming it) or
    # "printed" (the printed page; every federal line). Stored in the JSON
    # only for tooltip lines, so a missing field reads as "printed".
    source: str = "printed"

    @property
    def key(self) -> tuple[int, str, str]:
        return line_key(self.page, self.section, self.label)


def line_key(page: int, section: str, label: str) -> tuple[int, str, str]:
    """The one identity of a printed line, shared by both extractors: a
    label that recurs under two sections is two lines (Review Focus 1)."""
    return (page, section, label)


@dataclasses.dataclass(frozen=True)
class Inventory:
    source_sha256: str
    lines: tuple[InventoryLine, ...]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- federal: the printed page ---------------------------------------------

def _page_words(pdf: Path) -> list[list[tuple[float, float, float, float, str]]]:
    out = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True).stdout
    root = ElementTree.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", out))
    return [[(float(w.get("xMin")), float(w.get("yMin")),
              float(w.get("xMax")), float(w.get("yMax")), w.text or "")
             for w in page.iter(_XHTML + "word")]
            for page in root.iter(_XHTML + "page")]


def _columns(xs: list[float]) -> list[tuple[float, float]]:
    """Clusters of label x-positions (two or more labels each)."""
    groups: list[list[float]] = []
    for x in sorted(xs):
        if groups and x - groups[-1][-1] <= _COLUMN_GAP:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [(g[0] - 1, g[-1] + 1) for g in groups if len(g) >= 2]


def _number_of(label: str) -> int:
    return int(re.match(r"^\d+", label).group(0))


def extract_federal(pdf: Path) -> tuple[InventoryLine, ...]:
    """Every printed line label of a template, from its printed pages."""
    lines: list[InventoryLine] = []
    section = ""
    for page_no, words in enumerate(_page_words(pdf), 1):
        def row(w):
            return [v for v in words
                    if v is not w and abs(v[1] - w[1]) < _SAME_ROW]

        def left_clear(w):
            return not any(v[2] > w[0] - _LABEL_GAP and v[0] < w[0]
                           for v in row(w))

        def right_neighbour(w):
            right = sorted(v for v in row(w) if v[0] >= w[2] - 0.5)
            return right[0] if right else None

        numbers = [w for w in words if _NUMBER.match(w[4]) and left_clear(w)]
        if not numbers:
            continue
        median_height = statistics.median(w[3] - w[1] for w in numbers)

        def full_height(w):
            return (w[3] - w[1]) >= _FULL_HEIGHT * median_height

        numbers = [w for w in numbers if full_height(w)]
        columns = _columns([w[0] for w in numbers])

        def column_of(w):
            return next(((lo, hi) for lo, hi in columns if lo <= w[0] <= hi),
                        None)

        events = []
        for w in words:
            if w[4] == "Part" and left_clear(w):
                # A heading starts its row; "go to Part III" is a reference.
                nxt = right_neighbour(w)
                if nxt and _ROMAN.match(nxt[4]) and nxt[0] - w[2] < _LABEL_GAP:
                    # A heading printed on its first line's row precedes it.
                    events.append((w[1] - 3, 0, "part", f"Part {nxt[4]}", w))
            elif w in numbers and column_of(w):
                events.append((w[1], 1, "number", w[4], w))
            elif (_SUBLINE.match(w[4]) and full_height(w) and left_clear(w)
                  and any(lo <= w[0] <= hi + _SUBLINE_REACH + _JITTER
                          for lo, hi in columns)):
                events.append((w[1], 1, "subline", w[4], w))
        for w in _item_letters(words, columns, left_clear, right_neighbour,
                               full_height):
            events.append((w[1], 1, "letter", w[4], w))
        events.sort(key=lambda e: (e[0], e[1], e[4][0]))

        # A label column counts up within a Part. A column whose numbers fall
        # back inside one Part is a table's values (e.g. Form 4562's
        # recovery periods, "25 yrs.", "39 yrs."), not line labels.
        sequences: dict = {}
        current = section
        for _, _, kind, value, w in events:
            if kind == "part":
                current = value
            elif kind == "number":
                sequences.setdefault((column_of(w), current), []).append(
                    _number_of(value))
        not_labels = {col for (col, _), seq in sequences.items()
                      if any(b < a for a, b in zip(seq, seq[1:]))}
        events = [e for e in events
                  if not (e[2] == "number" and column_of(e[4]) in not_labels)]

        def parent_column(w):
            # The label column a bare sub-letter belongs to: the nearest
            # column at or left of it whose reach covers it.
            cover = [c for c in columns
                     if c[0] <= w[0] <= c[1] + _SUBLINE_REACH + _JITTER]
            return max(cover) if cover else None

        # A sub-letter composes with the last number of ITS OWN column. On a
        # two-column page (Schedule C Part II: lines 8-17 beside 18-27) the
        # last number in reading order may be the other column's.
        last_number: dict = {}
        for _, _, kind, value, w in events:
            if kind == "part":
                section = value
                continue
            consumed = {id(w)}
            if kind == "letter":
                label = value
            elif kind == "number":
                label = value
                last_number[column_of(w)] = str(_number_of(value))
                nxt = right_neighbour(w)
                if (nxt and not value[-1].isalpha() and _SUBLINE.match(nxt[4])
                        and nxt[0] - w[2] < _COMPOSITE_GAP):
                    label = value + nxt[4]
                    consumed.add(id(nxt))
            else:
                parent = last_number.get(parent_column(w))
                if parent is None:
                    continue
                label = parent + value
            mids = _mid_row_sub_lines(w, label, consumed, row, left_clear,
                                      right_neighbour, full_height)

            def text_between(start, end_x, skip):
                edge = start[2] + 2
                if kind == "letter" and start is w:
                    # A narrow capital ("I") can end short of the number
                    # column's left edge: its text runs to the first column
                    # past its own first word.
                    first = right_neighbour(w)
                    edge = max(edge, first[0]) if first else edge
                stop = min([lo for lo, _ in columns if lo > edge] + [end_x])
                return " ".join(
                    v[4] for v in sorted(row(start) + [start])
                    if start[2] < v[0] < stop and id(v) not in skip
                    and not _LEADER.match(v[4])).strip()

            # A mid-row sub-line ends the text of the line before it.
            found = [InventoryLine(
                page_no, section, label,
                text_between(w, mids[0][0][0] if mids else 1e9, consumed),
                tuple(round(c, 2) for c in w[:4]))]
            for i, (v, mid_label) in enumerate(mids):
                end = mids[i + 1][0][0] if i + 1 < len(mids) else 1e9
                found.append(InventoryLine(
                    page_no, section, mid_label,
                    text_between(v, end, {id(v)}),
                    tuple(round(c, 2) for c in v[:4])))
            for line in found:
                # The same line seen again: its own key, or a line-number
                # box repeating its row's label.
                same = [i for i, o in enumerate(lines)
                        if o.page == page_no and o.label == line.label
                        and (o.section == section
                             or abs(o.bbox[1] - line.bbox[1]) < _BOX_REPEAT)]
                if same:
                    earlier = lines[same[0]]
                    # The printed label to the LEFT wins over an EMPTY line
                    # a box (or a stray digit) made first, whichever sorted
                    # first by a fraction of a point; the line keeps its
                    # key. A line that already has text is never rewritten.
                    if (not earlier.text and line.text
                            and line.bbox[0] < earlier.bbox[0]):
                        lines[same[0]] = dataclasses.replace(
                            line, section=earlier.section)
                    continue
                lines.append(line)
    return tuple(lines)


_MID_ROW_WORD_GAP = 35.0  # pt: a mid-row sub-letter's (or item letter's)
                          # own text follows it
_ITEM_LETTER = re.compile(r"^[A-Z]$")
_CAPITALISED = re.compile(r"^[“\"(]?[A-Z]")


def _item_letters(words, columns, left_clear, right_neighbour, full_height):
    """Uppercase item letters printed as labels (Schedule C's header items
    A-J, Schedule SE's line A, Form 1120-S's A-J): a lone capital, left-
    clear, full height, followed closely by a capitalised word -- so "A late
    filing penalty ..." (Form 4868) is a sentence, not a label -- and
    either in a column of such letters that ascends without repeating (so
    Schedule CA's repeated A / B / C column headers are not lines) or alone
    at the left margin, left of every number column (Schedule SE's A)."""
    def candidate(w):
        if not (_ITEM_LETTER.match(w[4]) and left_clear(w) and full_height(w)):
            return False
        nxt = right_neighbour(w)
        return (bool(nxt) and nxt[0] - w[2] < _MID_ROW_WORD_GAP
                and _CAPITALISED.match(nxt[4]) is not None)
    letters = sorted((w for w in words if candidate(w)),
                     key=lambda w: (w[1], w[0]))
    letter_columns = []
    for lo, hi in _columns([w[0] for w in letters]):
        seq = [w[4] for w in letters if lo <= w[0] <= hi]
        if all(b > a for a, b in zip(seq, seq[1:])):
            letter_columns.append((lo, hi))
    first_number_column = min((lo for lo, _ in columns), default=1e9)
    return [w for w in letters
            if any(lo <= w[0] <= hi for lo, hi in letter_columns)
            or (w[0] < first_number_column - 2 and w[0] <= _LEFT_MARGIN)]


def _mid_row_sub_lines(w, label, consumed, row, left_clear, right_neighbour,
                       full_height):
    """Sub-lines printed LATER on a label's row ("44a Business b Commuting
    c Other"; Form 1040 "2a ... 2a b Taxable interest 2b"), as
    ``[(word, label), ...]``. Each is a left-clear token naming the next
    sub-letter in sequence ("b", or the full "2b"), after at least one word
    of the label's own text, with its own text right after it. A label with
    no sub-letter opens them only when the row prints at least two ("a ...
    b ..."): one lone "a" is an alternative in the text (Schedule D (540)
    line 9, "the smaller of: a the loss ... b $3,000")."""
    if not label[:1].isdigit():    # an item letter (A, B, ...)
        return []
    base = str(_number_of(label))
    letter = label[len(base):]
    if len(letter) > 1:            # a roman row (1ii): no sub-letters follow
        return []
    want = chr(ord(letter) + 1) if letter else "a"
    mids = []
    seen_text = False
    for v in sorted(row(w)):
        if v[0] <= w[2] or id(v) in consumed:
            continue
        if (seen_text and left_clear(v) and v[4] in (want, base + want)
                and full_height(v)):
            nxt = right_neighbour(v)
            if (nxt and nxt[0] - v[2] < _MID_ROW_WORD_GAP
                    and nxt[4][:1].isalpha()):
                mids.append((v, base + want))
                want = chr(ord(want) + 1)
                continue
        if not _LEADER.match(v[4]):
            seen_text = True
    if not letter and len(mids) < 2:
        return []
    return mids


# --- California: the templates' own tooltips, sectioned by the printed page --

# A tooltip names its line with the first "Line N" token, anywhere in the
# tooltip ("Line 12. ...", "Line 1 h. ...", "Line 8 A. ...", or after a
# heading: "Assets Line 1. Cash."). The sub-line is one letter or a
# lowercase roman row. An address field's "Line 1 of 2" is not a form line;
# its prefix is classified "not-line" in the census below.
_TOOLTIP_LINE = re.compile(
    r"\bLine (?P<number>[1-9]\d{0,2})"
    r"(?:\s?(?P<sub>ii|iii|iv|vi|vii|viii|[a-zA-Z]))?\b")

# Every tooltip-prefix shape the FTB templates use before their "Line N"
# (surveyed over every California template, 2021-2025; shape = the prefix
# with whitespace collapsed, outer " ." stripped, digits as N and "(a)" as
# "(x)"). A new shape fails extraction loudly instead of being guessed at.
#   "section"  : names a Part / Section / Schedule (cross-checked against
#                the printed heading) or a Schedule Q question (which the
#                page prints only as a letter, so the tooltip is its source)
#   "context"  : a heading or column descriptor; the line keeps its printed
#                section
#   "not-line" : not a form line (an address field's "Line 1 of 2")
_PREFIX_CENSUS: dict[str, str] = {
    "": "context",
    "Alternative Minimum Tax (A M T) Items. Column (x) Pro-rata share items": "context",
    "Alternative Minimum Tax (AMT) Items Column (x) Pro-rata share items": "context",
    "Alternative Minimum Tax (AMT) Items. Column (x) Pro-rata share items": "context",
    "Amount You Owe": "context",
    "Assets": "context",
    "California Net Income": "context",
    "Casualty and Theft Losses": "context",
    "Column (x) Pro-rata share items": "context",
    "Column (x). Pro-rata share items": "context",
    "Credits Column (x) Pro-rata share items": "context",
    "Credits. Column (x) Pro-rata share items": "context",
    "Deductions": "context",
    "Deductions Column (x) Pro-rata share items": "context",
    "Deductions. Column (x) Pro-rata share items": "context",
    "Exemptions. For line N, line N, line N, and line N: Multiply the number "
    "you enter in the box by the pre-printed dollar amount for that line. "
    "Whole dollars only": "context",
    "Fill in the information to authorize direct deposit of your refund into "
    "one or two accounts. Do not attach a voided check or a deposit slip. See "
    "instructions. Have you verified the routing and account numbers? Use "
    "whole dollars only. All or the following amount of my refund (line N) is "
    "authorized for direct deposit into the account shown below": "context",
    "Fill in the information to authorize direct deposit of your refund into "
    "one or two accounts. Do not attach a voided check or a deposit slip. See "
    "instructions. Have you verified the routing and account numbers? Use "
    "whole dollars only. All or the following amount of my refund (line N) is "
    "authorized for direct deposit into the account shown below:": "context",
    "Firm's name (or yours if self-employed) and address": "not-line",
    "Firm's name (or yours, if self-employed) and address": "not-line",
    "For line N, line N, line N, and line N: Multiply the number you enter in "
    "the box by the pre-printed dollar amount for that line. Whole dollars "
    "only": "context",
    "Gifts to Charity": "context",
    "Income": "context",
    "Income (Loss) Column (x) Pro-rata share items": "context",
    "Income (Loss) column (x) Pro-rata share items": "context",
    "Income (Loss). Column (x) Pro-rata share items": "context",
    "Income (Loss). Column (x). Pro-rata share items": "context",
    "Income (loss) Column (x) Pro-rata share items": "context",
    "Individual Shared Responsibility Penalty": "context",
    "Interest You Paid": "context",
    "Interest and Penalties": "context",
    "Items Affecting Shareholder Basis Column (x) Pro-rata share items": "context",
    "Items Affecting Shareholder Basis. Column (x) Pro-rata share items": "context",
    "Job Expenses and Certain Miscellaneous Deductions": "context",
    "Liabilities and shareholders' equity": "context",
    "Liabilities and shareholders’ equity": "context",
    "Medical and Dental Expenses": "context",
    "Other Income (Loss) Column (x) Pro-rata share items": "context",
    "Other Income (Loss) column (x) Pro-rata share items": "context",
    "Other Income (Loss). Column (x) Pro-rata share items": "context",
    "Other Income (Loss). Column (x). Pro-rata share items": "context",
    "Other Information Column (x) Pro-rata share items": "context",
    "Other Information. Column (x) Pro-rata share items": "context",
    "Other Itemized Deductions": "context",
    "Other State Taxes Column (x) Pro-rata share items": "context",
    "Other State Taxes. Column (x) Pro-rata share items": "context",
    "Other Taxes": "context",
    "Overpaid Tax or Tax Due": "context",
    "Paid preparer's Use Only Firms name (or yours, if self-employed) and "
    "address": "not-line",
    "Part N": "section",
    "Part One. Income Adjustment Schedule. Section A. Income from federal "
    "Form N or N-SR": "section",
    "Part One. Section A": "section",
    # FTB 3532 (2023-2025), each verified against the printed page's
    # "Part I Marital Status" / "Part II Qualifying Person" / "Part III
    # Qualifying Person Information" headings (2026-10-17).
    "Part One": "section",
    "Part Two": "section",
    "Part Three": "section",
    "Part one": "section",
    "Part two": "section",
    "Part three": "section",
    "Part three. Qualifying Person Information": "section",
    "Payments": "context",
    "Question A": "section",
    "Question B": "section",
    "Reconciliation Column (x) Pro-rata share items": "context",
    "Reconciliation. Column (x) Pro-rata share items": "context",
    "Refund and Direct Deposit": "context",
    "Refund or Amount Due": "context",
    "Schedule F Income": "section",
    "Schedule J": "section",
    "Schedule M-N": "section",
    "Schedule Q Question A": "section",
    "Schedule V": "section",
    "Section B": "section",
    "Section B – Additional Income from federal Schedule N (Form N)": "section",
    "Section C": "section",
    "Section C . Adjustments to Income from federal Schedule N (Form N)": "section",
    "Special Credits": "context",
    "State Adjustments": "context",
    "Tax": "context",
    "Taxable Income": "context",
    "Taxes": "context",
    "Taxes You Paid": "context",
    "The remaining amount of my refund (line N) is authorized for direct "
    "deposit into the account shown below": "context",
    "The remaining amount of my refund (line N) is authorized for direct "
    "deposit into the account shown below:": "context",
    "Use Tax": "context",
}

# A printed section heading: "Part I", "Schedule L", "Schedule M-1",
# "Section B", starting its row at the left margin (every FTB section
# heading prints at the margin; a mid-page "Schedule G-1" or "Part I, line
# 27" is a reference). Schedule Q is not one: its questions sit inside the
# Side 1 main form ("continued on Side 3"), so the lines below it are the
# main form's; each question is named by its tooltip.
_HEADING_WORDS = ("Part", "Schedule", "Section")
_HEADING_ID = re.compile(r"^(?:[IVX]+|[A-Z](?:-\d)?|\d+)$")
_LEFT_MARGIN = 72.0
_FOOTER = 60.0
_QUESTION_BLOCK = ("Schedule", "Q")
_ROMAN_OF = {"1": "I", "2": "II", "3": "III", "One": "I", "Two": "II",
             "Three": "III"}


class UnknownTooltipShapeError(ValueError):
    """A California tooltip prefix the census does not classify."""


def prefix_shape(prefix: str) -> str:
    shape = " ".join(prefix.split()).strip(" .")
    shape = re.sub(r"\(\s*\w\s*\)", "(x)", shape)
    return re.sub(r"\d+", "N", shape)


def _tooltip(annotation) -> str | None:
    node = annotation
    while node is not None:
        if node.get("/TU") is not None:
            return str(node["/TU"])
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def _printed_headings(pdf: Path) -> list[tuple[int, float, str, str]]:
    """(page, top, word, identifier) for every printed section heading."""
    headings = []
    for page_no, words in enumerate(_page_words(pdf), 1):
        bottom = max((w[3] for w in words), default=0.0)
        for w in words:
            if w[4] not in _HEADING_WORDS or w[0] > _LEFT_MARGIN:
                continue
            if w[1] > bottom - _FOOTER:
                continue
            row = sorted(v for v in words
                         if v is not w and abs(v[1] - w[1]) < _SAME_ROW)
            if any(v[2] > w[0] - _LABEL_GAP and v[0] < w[0] for v in row):
                continue
            right = [v for v in row if v[0] >= w[2] - 0.5]
            if right and _HEADING_ID.match(right[0][4]):
                headings.append((page_no, w[1], w[4], right[0][4]))
    return sorted(headings)


def _section_at(headings, page: int, top: float) -> str:
    """The printed section a point on the page sits in."""
    part = section = ""
    for h_page, h_top, word, ident in headings:
        if (h_page, h_top) > (page, top + 3):
            break
        if (word, ident) == _QUESTION_BLOCK:
            continue
        if word == "Section":
            section = f"Section {ident}"
        else:
            part, section = f"{word} {ident}", ""
    return " ".join(p for p in (part, section) if p)


def _tooltip_sections(prefix: str) -> list[str]:
    """The Part / Section / Schedule names a section-class prefix states,
    normalized to the printed spelling ("Part 1", "Part One" -> "Part I")."""
    names = []
    # Only a clause that STARTS with the name states a section; "Section B
    # - Additional Income from federal Schedule 1" refers to Schedule 1.
    for clause in re.split(r"\.\s+|\s+[–-]\s+", " ".join(prefix.split())):
        m = re.match(r"(Part|Section|Schedule) ([A-Z](?:-\d)?|[IVX]+|\d+|"
                     r"[Oo]ne|[Tt]wo|[Tt]hree)\b", clause.strip(" ."))
        if not m:
            continue
        word, ident = m.groups()
        if (word, ident) == _QUESTION_BLOCK:
            continue
        if word == "Part":
            # FTB writes the Part number as a word in either case ("Part
            # One", FTB 3532 2024's "Part one").
            ident = _ROMAN_OF.get(ident.capitalize(), ident)
        names.append(f"{word} {ident}")
    return names


def tooltip_line(tip: str, where: str = "") -> tuple[str, str, str, str] | None:
    """(label, text, census kind, prefix) for the form line a tooltip names,
    or None when it names none (no "Line N", an address field's "Line 1 of
    2", or a not-line prefix). An unclassified prefix shape refuses."""
    tip = " ".join(tip.split())
    m = _TOOLTIP_LINE.search(tip)
    if not m:
        return None
    prefix = tip[:m.start()]
    shape = prefix_shape(prefix)
    kind = _PREFIX_CENSUS.get(shape)
    if kind is None:
        raise UnknownTooltipShapeError(
            f"{where}: tooltip prefix shape {shape!r} is not in the census "
            "(_PREFIX_CENSUS); classify it as section, context or not-line. "
            f"Tooltip: {tip[:120]!r}")
    if kind == "not-line":
        return None
    label = m.group("number") + (m.group("sub") or "")
    return label, tip[m.end():].lstrip(" .").strip(), kind, prefix


def extract_california(pdf: Path) -> tuple[InventoryLine, ...]:
    """Lines from the FTB template's /TU tooltips, each placed in the
    printed section its widget sits under. A tooltip's own section prefix
    is a cross-check (it appears only on a Part's first line); a Schedule Q
    question, printed only as a letter, is named by its tooltip. A printed
    label no tooltip names comes from the printed page."""
    headings = _printed_headings(pdf)
    lines: list[InventoryLine] = []
    seen: set[tuple[int, str, str]] = set()
    reader = PdfReader(str(pdf))
    for page_no, page in enumerate(reader.pages, 1):
        height = float(page.mediabox.height)
        for ref in page.get("/Annots") or []:
            annotation = ref.get_object()
            tip = _tooltip(annotation)
            if tip is None:
                continue
            parsed = tooltip_line(tip, where=str(pdf))
            if parsed is None:
                continue
            label, text, kind, prefix = parsed
            x0, y0, x1, y1 = (float(c) for c in annotation["/Rect"])
            # Top-left origin, like pdftotext.
            bbox = (round(x0, 2), round(height - y1, 2),
                    round(x1, 2), round(height - y0, 2))
            section = _section_at(headings, page_no, bbox[1])
            if kind == "section":
                printed = re.findall(r"(?:Part|Section|Schedule) \S+",
                                     section)
                for stated in _tooltip_sections(prefix):
                    if stated not in printed:
                        raise ValueError(
                            f"{pdf}: page {page_no} tooltip states {stated!r} "
                            f"but the widget sits under the printed "
                            f"{section or 'main form'!r}: {tip[:120]!r}")
                question = re.search(r"\bQuestion ([A-Z])\b", prefix)
                if question:
                    section = " ".join(p for p in (
                        section, f"Schedule Q Question {question.group(1)}")
                        if p)
            key = line_key(page_no, section, label)
            if key in seen:
                continue
            seen.add(key)
            lines.append(InventoryLine(page_no, section, label, text, bbox,
                                       source="tooltip"))
    for line in extract_federal(pdf):
        section = _section_at(headings, line.page, line.bbox[1])
        if any(o.page == line.page and o.label == line.label
               and (o.section == section
                    or abs(o.bbox[1] - line.bbox[1]) < _BOX_REPEAT)
               for o in lines):
            continue
        lines.append(dataclasses.replace(line, section=section))
    return tuple(lines)


# --- storage -----------------------------------------------------------------

def _sorted(lines) -> tuple[InventoryLine, ...]:
    return tuple(sorted(lines, key=lambda l: (l.page, l.bbox[1], l.bbox[0],
                                              l.section, l.label)))


def _line_json(line: InventoryLine) -> dict:
    data = dataclasses.asdict(line)
    if data["source"] == "printed":
        del data["source"]
    return data


def extract(jurisdiction: str, pdf: Path) -> tuple[InventoryLine, ...]:
    if jurisdiction == "federal":
        return extract_federal(pdf)
    if jurisdiction == "california":
        return extract_california(pdf)
    raise ValueError(f"unknown jurisdiction {jurisdiction!r}")


def to_json(form: str, key: int | str, jurisdiction: str, source: Path,
            lines) -> str:
    return json.dumps({
        "form": form,
        "key": key,
        "jurisdiction": jurisdiction,
        "source": Path(source).resolve().relative_to(REPO_ROOT).as_posix(),
        "source_sha256": sha256_of(source),
        "lines": [_line_json(l) for l in _sorted(lines)],
    }, indent=1, ensure_ascii=False) + "\n"


def write(form: str, key: int | str, jurisdiction: str, source: Path) -> Path:
    """Extract one template's inventory and write it (reviewed data: a
    re-extraction that changes anything shows as a diff)."""
    path = inventory_path(form, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(form, key, jurisdiction, source,
                            extract(jurisdiction, source)))
    return path


def refresh() -> list[Path]:
    """Re-extract every committed inventory from the template it records."""
    written = []
    for path in sorted(INVENTORY_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        written.append(write(data["form"], data["key"], data["jurisdiction"],
                             REPO_ROOT / data["source"]))
    return written


def inventory_path(form: str, key: int | str) -> Path:
    return INVENTORY_DIR / f"{form}_{key}.json"


def load(form: str, key: int | str) -> Inventory:
    data = json.loads(inventory_path(form, key).read_text())
    return Inventory(
        source_sha256=data["source_sha256"],
        lines=tuple(InventoryLine(
            page=l["page"], section=l["section"], label=l["label"],
            text=l["text"], bbox=tuple(l["bbox"]),
            source=l.get("source", "printed")) for l in data["lines"]))
