"""Pixel-level proof that checked CA checkboxes / radios actually print.

Field state is not pixels. Before this was fixed, the 2024 and 2025 Form 540
filing-status radio was "checked" in the field tree (``/AS`` set) yet rendered
as an empty box, because pypdf wrote the radio group's ``/V`` as a text string
instead of a name. These tests RENDER the filled page with poppler and assert
dark pixels inside each checked widget's rectangle — see
``tests/_pdf_pixels.py`` (reusable by other test modules).
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f540 as form_f540
from tenforty.mappings import pdf_f540
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.models import CA540Return, FilingStatus
from tests._ca_emit_helpers import CA_YEARS, REPO_ROOT, emit_ca, make_ca_scenario
from tests._pdf_pixels import checked_widgets, dark_pixels_in_rect, widget_rect

# A drawn check glyph or X inside a ~16pt box at 150 dpi puts well over this
# many dark pixels in the (inset) rect; an empty box puts ~0 there.
MIN_INK = 15

_CB_BY_YEAR = {
    2021: pdf_f540._FILING_STATUS_CB_2021,
    2022: pdf_f540._FILING_STATUS_CB_2022,
    2023: pdf_f540._FILING_STATUS_CB_2023,
}


def filing_status_widget(year: int, fs: FilingStatus):
    """(field_name, on_state_or_None) of the filing-status widget the 540
    mapping selects for ``fs`` in ``year`` — read from the mapping's own tables."""
    if year in _CB_BY_YEAR:
        return _CB_BY_YEAR[year][fs], None
    if year == 2024:
        return "540-1036 RB", pdf_f540._FILING_STATUS_RB_STATES_2024[fs]
    return "540_form_1036 RB", pdf_f540._FILING_STATUS_RB_STATES[fs]


def fill_f540_direct(year: int, fs: FilingStatus, out: Path) -> Path:
    """Fill the real 540 template straight from the mapping (no workbook), so
    every filing status — incl. MFJ/MFS, which the workbook refuses — is testable."""
    values = form_f540.compute(
        year=year, filing_status=fs, federal_agi=80_000, ca_agi=80_000,
        ca540=CA540Return(), num_dependents=0)
    PdfFiller().fill(
        template_path=REPO_ROOT / "pdfs" / "california" / str(year) / "f540.pdf",
        output_path=out,
        field_mapping=PdfF540.get_mapping(year), values=values,
        aggregations=PdfF540.get_aggregations(year),
        derivations=PdfF540.get_derivations(year),
        checkbox_states=PdfF540.get_checkbox_states(year),
    )
    return out


class FilingStatusMarkPrintsTests(unittest.TestCase):
    """The filing-status mark must have ink in the box — every year, every status."""

    def test_filing_status_mark_has_ink_every_year_and_status(self):
        tmp = Path(tempfile.mkdtemp())
        for year in CA_YEARS:
            for fs in FilingStatus:
                with self.subTest(year=year, fs=fs.value):
                    pdf = fill_f540_direct(year, fs, tmp / f"f540_{year}_{fs.value}.pdf")
                    name, state = filing_status_widget(year, fs)
                    page, rect = widget_rect(pdf, name, state)
                    ink = dark_pixels_in_rect(pdf, page, rect)
                    self.assertGreaterEqual(
                        ink, MIN_INK,
                        f"{year} {fs.value}: filing-status widget {name!r} is "
                        f"checked but renders blank ({ink} dark px)")

    def test_exactly_one_filing_status_widget_is_checked(self):
        tmp = Path(tempfile.mkdtemp())
        for year in CA_YEARS:
            with self.subTest(year=year):
                pdf = fill_f540_direct(year, FilingStatus.HEAD_OF_HOUSEHOLD, tmp / f"h{year}.pdf")
                name, state = filing_status_widget(year, FilingStatus.HEAD_OF_HOUSEHOLD)
                checked = [n for pi, n, r, s in checked_widgets(pdf) if pi == 0 and n == name]
                self.assertEqual(len(checked), 1, checked)


class EveryCheckedWidgetPrintsTests(unittest.TestCase):
    """End-to-end (compute -> mapping -> fill): no checked widget on any
    emitted CA form may be blank."""

    def test_every_checked_widget_has_ink_on_emitted_forms(self):
        for year in CA_YEARS:
            _, pdfs = emit_ca(make_ca_scenario(year))
            for basename, path in pdfs.items():
                with self.subTest(year=year, form=basename):
                    seen = 0
                    for page, name, rect, state in checked_widgets(path):
                        seen += 1
                        ink = dark_pixels_in_rect(path, page, rect)
                        self.assertGreaterEqual(
                            ink, MIN_INK,
                            f"{year} {basename}: {name!r}={state!r} checked but blank")
                    if basename == "f540":
                        # the filing-status mark + a line-31 tax-source box
                        self.assertGreaterEqual(seen, 2)


class RadioValueIsNameTests(unittest.TestCase):
    def test_radio_group_value_is_a_pdf_name_not_a_text_string(self):
        pdf = fill_f540_direct(2025, FilingStatus.SINGLE, Path(tempfile.mkdtemp()) / "r.pdf")
        reader = PdfReader(str(pdf))
        found = False
        for annot in reader.pages[0]["/Annots"]:
            w = annot.get_object()
            parent = w.get("/Parent")
            if parent is not None and parent.get_object().get("/T") == "540_form_1036 RB":
                found = True
                self.assertIsInstance(parent.get_object()["/V"], NameObject)
        self.assertTrue(found)


class EmptyAppearanceStreamFallbackTests(unittest.TestCase):
    """A template whose on-state stream paints nothing still prints a mark."""

    def _template_with_blank_on_state(self, tmp: Path) -> Path:
        src = REPO_ROOT / "pdfs" / "california" / "2023" / "f540.pdf"
        writer = PdfWriter(clone_from=PdfReader(str(src)))
        blanked = 0
        for annot in writer.pages[0]["/Annots"]:
            w = annot.get_object()
            if w.get("/T") == "1036 CB":  # 2023 line 1 Single checkbox
                stream = w["/AP"]["/N"]["/Yes"].get_object()
                stream.set_data(b"")
                blanked += 1
        self.assertEqual(blanked, 1)
        out = tmp / "blank_on_state.pdf"
        writer.write(str(out))
        return out

    def test_blank_on_state_stream_gets_a_visible_mark(self):
        tmp = Path(tempfile.mkdtemp())
        template = self._template_with_blank_on_state(tmp)
        out = tmp / "filled.pdf"
        # Control: the blanked template really does render empty when merely checked.
        PdfFiller().fill(
            template_path=template, output_path=out,
            field_mapping={}, values={},
            derivations={"1036 CB": lambda c: "/Yes"})
        page, rect = widget_rect(out, "1036 CB")
        self.assertGreaterEqual(dark_pixels_in_rect(out, page, rect), MIN_INK)

    def test_real_stream_is_left_untouched(self):
        tmp = Path(tempfile.mkdtemp())
        src = REPO_ROOT / "pdfs" / "california" / "2023" / "f540.pdf"
        before = None
        for annot in PdfReader(str(src)).pages[0]["/Annots"]:
            w = annot.get_object()
            if w.get("/T") == "1036 CB":
                before = w["/AP"]["/N"]["/Yes"].get_object().get_data()
        out = tmp / "filled.pdf"
        PdfFiller().fill(
            template_path=src, output_path=out, field_mapping={}, values={},
            derivations={"1036 CB": lambda c: "/Yes"})
        after = None
        for annot in PdfReader(str(out)).pages[0]["/Annots"]:
            w = annot.get_object()
            if w.get("/T") == "1036 CB":
                after = w["/AP"]["/N"]["/Yes"].get_object().get_data()
        self.assertEqual(before, after)
        self.assertIn(b"ZaDb", after)


if __name__ == "__main__":
    unittest.main()
