"""Form 1040 age checkboxes ("You: Were born before …" / "Spouse: Was born
before …"), every year 2021-2025.

Placement: each key lands on its own widget (sentinel fill + read-back), and
that widget sits on the same printed row as, and immediately left of, its
own year's "Were born before" / "Was born before" label -- located by text
position on that year's template, so a field name borrowed from a neighbour
year (the renumbering trap) cannot pass. Ink: the mark actually renders,
modelled on ``tests/test_f1040_status_ink.py``. Value: the taxpayer box
follows the taxpayer's birthdate, the spouse box follows the spouse's and is
set only on a joint return.

The cutoff date is a transcribed per-year param (age-65-params); these tests
pass an obviously synthetic sentinel cutoff and derive every birthdate from
it. Synthetic data only.
"""
import dataclasses
import datetime
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import FilingStatus
from tenforty import orchestrator as orchestrator_mod
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal
from tests._pdf_pixels import checked_widgets, dark_pixels_in_rect, widget_rect
from tests.helpers import REPO_ROOT, make_simple_scenario

YEARS = (2021, 2022, 2023, 2024, 2025)

TAXPAYER = "age_taxpayer_born_before"
SPOUSE = "age_spouse_born_before"
AGE_KEYS = (TAXPAYER, SPOUSE)

# The printed label word that opens each box's caption ("You: Were born
# before …" / "Spouse: Was born before …").
_LABEL_WORD = {TAXPAYER: "Were", SPOUSE: "Was"}

# A drawn check glyph inside a ~8pt box at 150 dpi puts well over this many
# dark pixels in the (inset) rect; an empty box puts ~0 there.
MIN_INK = 15

# Obviously synthetic: no real tax year's cutoff looks like this.
SENTINEL_CUTOFF = datetime.date(1111, 11, 11)
DAY = datetime.timedelta(days=1)
AGED = (SENTINEL_CUTOFF - DAY).isoformat()       # born the day before
NOT_AGED = SENTINEL_CUTOFF.isoformat()            # born on the cutoff


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"


def _fill(year: int, values: dict, out: Path) -> Path:
    PdfFiller().fill(
        template_path=_template(year), output_path=out,
        field_mapping=Pdf1040.get_mapping(year), values=values,
        checkbox_states=Pdf1040.get_checkbox_states(year))
    return out


def _born_before_labels(pdf: Path, page_index: int) -> dict[str, tuple]:
    """{label word: (x0, y0, x1, y1) in PDF points} for each "<word> born
    before" phrase on the page, read from poppler's word boxes."""
    xml = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(page_index + 1),
         "-l", str(page_index + 1), str(pdf), "-"],
        check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(xml)
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    page = root.find(".//x:page", ns)
    height = float(page.get("height"))
    words = [(w.text or "", float(w.get("xMin")), float(w.get("yMin")),
              float(w.get("xMax")), float(w.get("yMax")))
             for w in page.findall("x:word", ns)]
    found: dict[str, list] = {}
    for i in range(len(words) - 2):
        word = words[i][0]
        if (word in _LABEL_WORD.values() and words[i + 1][0] == "born"
                and words[i + 2][0] == "before"):
            _, x0, top, x1, bottom = words[i]
            found.setdefault(word, []).append(
                (x0, height - bottom, x1, height - top))
    return {w: boxes for w, boxes in found.items()}


class AgeBoxPlacementTests(unittest.TestCase):
    """Each age key fills its own widget, and that widget is the box printed
    beside its own "born before" caption -- every year."""

    def test_sentinel_fill_reads_back_on_both_boxes_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            states = Pdf1040.get_checkbox_states(year)
            self.assertNotEqual(mapping[TAXPAYER], mapping[SPOUSE])
            for on in AGE_KEYS:
                with self.subTest(year=year, on=on):
                    pdf = _fill(year, {k: k == on for k in AGE_KEYS},
                                tmp / f"rb_{year}_{on}.pdf")
                    checked = {n for _, n, _, _ in checked_widgets(pdf)}
                    self.assertIn(mapping[on], checked)
                    other = SPOUSE if on == TAXPAYER else TAXPAYER
                    self.assertNotIn(mapping[other], checked)
                    fields = PdfReader(str(pdf)).get_fields()
                    self.assertEqual(
                        str(fields[mapping[on]].get("/V")), states[on])

    def test_widget_sits_left_of_its_own_caption_every_year(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            states = Pdf1040.get_checkbox_states(year)
            for key in AGE_KEYS:
                with self.subTest(year=year, key=key):
                    page, rect = widget_rect(
                        _template(year), mapping[key], states[key])
                    labels = _born_before_labels(_template(year), page)
                    boxes = labels.get(_LABEL_WORD[key], [])
                    self.assertEqual(
                        len(boxes), 1,
                        f"{year}: expected one '{_LABEL_WORD[key]} born "
                        f"before' caption on page {page}, found {boxes}")
                    lx0, ly0, lx1, ly1 = boxes[0]
                    wx0, wy0, wx1, wy1 = (float(v) for v in rect)
                    # Same printed row: vertical centres within 3pt.
                    self.assertLess(
                        abs((wy0 + wy1) / 2 - (ly0 + ly1) / 2), 3,
                        f"{year} {key}: {mapping[key]!r} not on the caption row")
                    # Immediately left of the caption: gap under 10pt.
                    gap = lx0 - wx1
                    self.assertTrue(
                        0 < gap < 10,
                        f"{year} {key}: {mapping[key]!r} is {gap:.1f}pt from "
                        "its caption, not the box beside it")


class AgeBoxInkTests(unittest.TestCase):
    """The age mark has ink in its box when on, and none when off -- every
    year, each box independently."""

    def test_ink_present_when_on_absent_when_off_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            states = Pdf1040.get_checkbox_states(year)
            rects = {k: widget_rect(_template(year), mapping[k], states[k])
                     for k in AGE_KEYS}
            cases = {"none": (), TAXPAYER: (TAXPAYER,), SPOUSE: (SPOUSE,),
                     "both": AGE_KEYS}
            for label, on in cases.items():
                pdf = _fill(year, {k: k in on for k in AGE_KEYS},
                            tmp / f"ink_{year}_{label}.pdf")
                cache: dict = {}
                for key, (page, rect) in rects.items():
                    with self.subTest(year=year, case=label, box=key):
                        ink = dark_pixels_in_rect(
                            pdf, page, rect, _render_cache=cache)
                        if key in on:
                            self.assertGreaterEqual(
                                ink, MIN_INK,
                                f"{year} {key}: {mapping[key]!r} renders "
                                f"blank ({ink} dark px)")
                        else:
                            self.assertEqual(
                                ink, 0,
                                f"{year} {key}: {mapping[key]!r} has ink "
                                f"({ink} dark px) while off")


def _config(fs: FilingStatus, birthdate: str, spouse_birthdate: str = ""):
    scn = make_simple_scenario()
    return dataclasses.replace(
        scn.config, filing_status=fs, birthdate=birthdate,
        spouse_birthdate=spouse_birthdate)


class AgeBoxValueTests(unittest.TestCase):
    """The two bools: taxpayer box from the taxpayer's birthdate; spouse box
    on a joint return only, from the spouse's. Strictly before the cutoff."""

    MFJ = FilingStatus.MARRIED_FILING_JOINTLY
    HOH = FilingStatus.HEAD_OF_HOUSEHOLD

    def _values(self, cfg):
        return orchestrator_mod.form_1040_age_box_values(cfg, SENTINEL_CUTOFF)

    def test_mfj_spouse_only_aged_sets_spouse_box_only(self):
        got = self._values(_config(self.MFJ, NOT_AGED, AGED))
        self.assertEqual(got, {TAXPAYER: False, SPOUSE: True})

    def test_mfj_both_aged_and_neither_aged(self):
        self.assertEqual(self._values(_config(self.MFJ, AGED, AGED)),
                         {TAXPAYER: True, SPOUSE: True})
        self.assertEqual(self._values(_config(self.MFJ, NOT_AGED, NOT_AGED)),
                         {TAXPAYER: False, SPOUSE: False})

    def test_hoh_aged_taxpayer_sets_taxpayer_box_never_spouse(self):
        got = self._values(_config(self.HOH, AGED))
        self.assertEqual(got, {TAXPAYER: True, SPOUSE: False})

    def test_non_mfj_never_sets_spouse_box(self):
        # MFS may carry an (aged) spouse birthdate; it still never sets the
        # spouse box. Single/HoH are built bypassing the loader's refusal so
        # an aged spouse date is present and the gate is what's tested.
        for fs in (FilingStatus.SINGLE, self.HOH,
                   FilingStatus.MARRIED_FILING_SEPARATELY,
                   FilingStatus.QUALIFYING_WIDOW):
            with self.subTest(fs=fs.value):
                got = self._values(_config(fs, NOT_AGED, AGED))
                self.assertIs(got[SPOUSE], False)
                self.assertIs(got[TAXPAYER], False)

    def test_cutoff_is_exclusive_for_taxpayer_and_spouse(self):
        day_after = (SENTINEL_CUTOFF + DAY).isoformat()
        for born, expect in ((AGED, True), (NOT_AGED, False),
                             (day_after, False)):
            with self.subTest(born=born):
                got = self._values(_config(self.MFJ, born, born))
                self.assertEqual(got, {TAXPAYER: expect, SPOUSE: expect})

    def test_mfj_blank_spouse_birthdate_is_refused_naming_the_field(self):
        with self.assertRaises(ValueError) as ctx:
            self._values(_config(self.MFJ, AGED, ""))
        self.assertIn("spouse_birthdate", str(ctx.exception))

    def test_non_iso_birthdate_is_refused_naming_the_field(self):
        # In-memory configs never pass the loader's ISO check.
        for field, cfg in (
                ("`birthdate`", _config(FilingStatus.SINGLE, "11-10-1111")),
                ("`spouse_birthdate`",
                 _config(self.MFJ, NOT_AGED, "11/10/1111"))):
            with self.subTest(field=field):
                with self.assertRaises(ValueError) as ctx:
                    self._values(cfg)
                self.assertIn(field, str(ctx.exception))

    def test_checkbox_values_carry_the_helper_result(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name) / "work")
        scn = make_simple_scenario()
        scn = dataclasses.replace(scn, config=_config(self.MFJ, NOT_AGED, AGED))
        got = orch._form_1040_checkbox_values(
            scn, {}, aged_born_before=SENTINEL_CUTOFF)
        self.assertEqual({k: got[k] for k in AGE_KEYS},
                         {TAXPAYER: False, SPOUSE: True})
        self.assertIs(got["filing_status_mfj"], True)
        # Pending cutoff (age-65-params not yet transcribed): no age key is
        # emitted, rather than a guessed False.
        pending = orch._form_1040_checkbox_values(scn, {})
        self.assertEqual([k for k in AGE_KEYS if k in pending], [])


class AgeBoxWiringTests(unittest.TestCase):
    """The emit path feeds the helper the year's REAL params cutoff: an
    emitted 1040 for a taxpayer born the day before
    ``aged_born_before`` prints the taxpayer box; one born on it prints
    neither age box. One year proves the call site; placement and ink above
    cover every year's mapping."""

    YEAR = 2024

    def _emitted_checked(self, born: datetime.date) -> set[str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name) / "work")
        scn = make_simple_scenario()
        scn = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, year=self.YEAR, birthdate=born.isoformat()))
        out = Path(tmp.name) / "out"
        orch.emit_pdfs(scn, orch.compute_federal(scn), out)
        (pdf,) = out.rglob(f"f1040_{self.YEAR}.pdf")
        return {n for _, n, _, _ in checked_widgets(pdf)}

    def test_emitted_1040_uses_the_params_cutoff(self):
        cutoff = load_federal(self.YEAR).aged_born_before
        self.assertIsInstance(cutoff, datetime.date)
        mapping = Pdf1040.get_mapping(self.YEAR)
        aged = self._emitted_checked(cutoff - DAY)
        self.assertIn(mapping[TAXPAYER], aged)
        self.assertNotIn(mapping[SPOUSE], aged)
        not_aged = self._emitted_checked(cutoff)
        self.assertNotIn(mapping[TAXPAYER], not_aged)
        self.assertNotIn(mapping[SPOUSE], not_aged)
        # Reachability: the not-aged emit is a real 1040 with marks on it.
        self.assertIn(mapping["filing_status_single"], not_aged)


if __name__ == "__main__":
    unittest.main()
