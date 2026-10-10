"""When Form 4562 is emitted, and when the merged form cannot be.

Instructions for Form 4562 (2025), page 2, "Who Must File": "complete and
file Form 4562 if you are claiming any of the following. - Depreciation for
property placed in service during the 2025 tax year. ..." The other listed
triggers (a section 179 deduction, listed property, amortization beginning
this year, a corporate return) are all out of scope and refuse or have no
input. So: no placement this year anywhere on the return, no Form 4562 --
the depreciation still prints on Schedule E line 18 / Schedule C line 13.

On this branch the form is still ONE merged form per return listing every
asset with the engine's figures. That cannot print consistently when any
activity's deduction is an override amount, so a placement year with an
override anywhere refuses.

Field paths are literals probed on the 2025 templates. 6,970 is a legacy
regression pin (January 27.5-year building on 200,000).
"""

import dataclasses
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms import f4562, sch_e
from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.resolver import (
    reconstruct_prior_depreciation,
)
from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

YEAR = 2025
SCH_E_LINE_18_PROPERTY_A = (
    "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]")
# Probed on the 2025 template (the Part IV summary is on page 2 in this
# revision): the widget on the line whose printed number is "22".
# `TemplateAnchorTests` below re-derives that from the template itself on
# every run, so this literal is anchored to the artifact, not to
# mappings/pdf_4562.py.
F4562_LINE_22 = "topmostSubform[0].Page2[0].f2_2[0]"


F4562_TEMPLATE = (
    Path(__file__).parent.parent / "pdfs" / "federal" / str(YEAR)
    / "f4562.pdf")


# A line's text starts beside its number and may wrap onto a second row; the
# amount box sits on the line's LAST row. So a widget's line number is the
# nearest left-margin number at or above the widget's row, and never further
# above than a wrapped line can reach.
_LEFT_MARGIN_MAX_X = 60.0
_ROW_TOLERANCE = 6.0
_MAX_WRAP_HEIGHT = 30.0
_LINE_NUMBER = re.compile(r"(\d+[a-z]?)\b")


def _left_margin_line_numbers(page) -> list[tuple[float, str]]:
    """``(y, line number)`` for every line-number label printed in the left
    margin of a page, top to bottom.

    Only the START of a left-margin text fragment is read. That is the one
    thing pypdf versions agree on for these forms: the line's number begins
    a fragment at the left margin whether or not the words after it are
    split off ("22" / "22 Total."). The right-hand copy of the number, at
    the end of the leader dots, is NOT used -- pypdf 6.9.2 does not emit it
    as a separate fragment, which is what broke the first version of this
    probe."""
    labels = []

    def visit(text, cm, tm, _font_dict, _font_size):
        text = text.strip()
        x, y = tm[4] + cm[4], tm[5] + cm[5]
        match = _LINE_NUMBER.match(text)
        if match and x < _LEFT_MARGIN_MAX_X:
            labels.append((y, match.group(1)))

    page.extract_text(visitor_text=visit)
    return sorted(labels, reverse=True)


def _page_widgets(page) -> list[tuple[float, float, str]]:
    """``(row y, left x, full field name)`` for every widget on a page."""
    widgets = []
    for annotation in page.get("/Annots", []):
        annotation = annotation.get_object()
        if annotation.get("/Subtype") != "/Widget":
            continue
        names, node = [], annotation
        while node is not None:
            if "/T" in node:
                names.append(node["/T"])
            node = node.get("/Parent")
            node = node.get_object() if node is not None else None
        left, bottom, _right, top = (float(v) for v in annotation["/Rect"])
        widgets.append(((bottom + top) / 2, left, ".".join(reversed(names))))
    return widgets


def _line_number_of(row_y: float, labels) -> str | None:
    """The nearest left-margin line number at or above a widget's row, or
    None when there is none within a wrapped line's reach."""
    above = [(y, number) for y, number in labels
             if row_y - _ROW_TOLERANCE <= y <= row_y + _MAX_WRAP_HEIGHT]
    return min(above)[1] if above else None


def _widgets_by_printed_line(template: Path, page_index: int) -> dict:
    """{printed line number: [field names]} for the widgets on one page of a
    blank template, by the nearest-number-above rule."""
    page = PdfReader(str(template)).pages[page_index]
    labels = _left_margin_line_numbers(page)
    found: dict[str, list[str]] = {}
    for row_y, _left, name in _page_widgets(page):
        number = _line_number_of(row_y, labels)
        if number is not None:
            found.setdefault(number, []).append(name)
    return found


def _read(pdf_path, field_path) -> str:
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "").replace(",", "").strip()


def _old_building() -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Rental building", date_placed_in_service=date(2019, 6, 1),
        basis=200_000.0, recovery_class="27.5-year")
    asset.prior_depreciation = float(
        reconstruct_prior_depreciation(asset, YEAR, mid_quarter_years=frozenset()))
    return asset


def _new_building() -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=200_000.0, recovery_class="27.5-year")


def _new_equipment() -> DepreciableAsset:
    return DepreciableAsset(
        description="Equipment", date_placed_in_service=date(YEAR, 2, 1),
        basis=10_000.0, recovery_class="5-year",
        no_bonus_or_section_179_history=True)


def _rental(*assets, override_amount=None) -> RentalProperty:
    rental = RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=list(assets))
    if override_amount is not None:
        engine = sum(macrs_deduction(a, YEAR, mid_quarter_years=frozenset()) for a in assets)
        rental.depreciation_override = DepreciationOverride(
            amount=override_amount, restates_engine_amount=float(engine),
            acknowledgment=True)
    return rental


def _scenario(rentals=(), businesses=()):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=YEAR, first_name="Test", last_name="Filer",
        ssn="000-00-0000", acknowledges_no_source_documents=True)
    return dataclasses.replace(
        base, config=config, rental_properties=list(rentals),
        schedule_c_businesses=list(businesses),
        acknowledges_no_listed_property=True)


class TemplateAnchorTests(unittest.TestCase):
    """The line 22 literal is what the blank 2025 template itself puts on
    the line printed "22" -- read from the PDF, not from the mapping.

    This class reads the 2025 template (its page 2 layout). The same anchor
    for every template year 2021-2025, and for line 17, is
    tests/test_f4562_prior_asset_line17.py::TemplateAnchorTests.

    Two independent readings of the page must agree:
      1. geometry: each widget takes the nearest left-margin line number at
         or above its row;
      2. order: the first three line numbers printed on the page (top to
         bottom) pair off with the first three widgets (top to bottom).
    A probe that finds no "22" label FAILS -- it never skips and never
    passes on a missing label."""

    def setUp(self):
        self.page = PdfReader(str(F4562_TEMPLATE)).pages[1]
        self.labels = _left_margin_line_numbers(self.page)
        self.numbers = [number for _y, number in self.labels]

    def test_the_probe_finds_the_line_numbers_it_relies_on(self):
        """Loud failure, by name, if a pypdf version stops yielding them."""
        for number in ("21", "22", "23a"):
            self.assertIn(
                number, self.numbers,
                f"no left-margin label for line {number} was extracted from "
                f"{F4562_TEMPLATE.name} page 2; labels found: {self.numbers}")
        self.assertEqual(self.numbers[:3], ["21", "22", "23a"])

    def test_line_22_literal_is_the_widget_on_the_line_printed_22(self):
        by_line = _widgets_by_printed_line(F4562_TEMPLATE, page_index=1)
        self.assertIn("22", by_line, f"lines located: {sorted(by_line)}")
        # Exactly one widget belongs to line 22, and it is the literal.
        self.assertEqual(by_line["22"], [F4562_LINE_22])
        # The neighbouring lines are different widgets, so an off-by-one
        # literal cannot pass.
        self.assertNotIn(F4562_LINE_22, by_line["21"])
        self.assertNotIn(F4562_LINE_22, by_line["23a"])

    def test_reading_order_agrees_with_the_geometry(self):
        top_three = [
            name for _y, _x, name in sorted(
                _page_widgets(self.page), reverse=True)[:3]]
        by_order = dict(zip(self.numbers[:3], top_three))
        by_line = _widgets_by_printed_line(F4562_TEMPLATE, page_index=1)
        self.assertEqual(by_order["22"], F4562_LINE_22)
        for number in ("21", "22", "23a"):
            self.assertIn(by_order[number], by_line[number])

    def test_the_literal_is_a_real_field_of_the_template(self):
        fields = PdfReader(str(F4562_TEMPLATE)).get_fields() or {}
        self.assertIn(F4562_LINE_22, fields)

    def test_a_missing_label_is_a_failure_not_a_pass(self):
        """With the "22" label withheld from the probe, no widget is
        attributed to line 22 -- the anchor test's assertIn then fails."""
        labels = [(y, n) for y, n in self.labels if n != "22"]
        attributed = {
            _line_number_of(row_y, labels)
            for row_y, _x, _name in _page_widgets(self.page)}
        self.assertNotIn("22", attributed)
        # ...and the widget is NOT silently handed to a neighbouring line
        # in a way that would let the literal pass as line 22.
        row_y = next(y for y, _x, name in _page_widgets(self.page)
                     if name == F4562_LINE_22)
        self.assertNotEqual(_line_number_of(row_y, labels), "22")


class _EmitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.tmp / "work")
        self._n = 0

    def _emit(self, scenario) -> dict:
        self._n += 1
        results = self.orchestrator.compute_federal(scenario)
        return self.orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out{self._n}")


class EmitOnlyInAPlacementYearTests(_EmitCase):
    def test_predicate_false_with_only_prior_year_assets(self):
        s = _scenario(rentals=[_rental(_old_building())])
        self.assertFalse(self.orchestrator._should_emit_4562(s, {}))

    def test_predicate_true_with_a_placement_this_year(self):
        s = _scenario(rentals=[_rental(_old_building(), _new_building())])
        self.assertTrue(self.orchestrator._should_emit_4562(s, {}))

    def test_predicate_sees_a_placement_on_any_activity(self):
        s = _scenario(
            rentals=[_rental(_old_building())],
            businesses=[ScheduleCBusiness(
                description="Consulting", gross_receipts=50_000.0,
                depreciable_assets=(_new_equipment(),))])
        self.assertTrue(self.orchestrator._should_emit_4562(s, {}))

    def test_ongoing_year_emits_no_form_and_schedule_e_still_carries_it(self):
        building = _old_building()
        expected = macrs_deduction(building, YEAR, mid_quarter_years=frozenset())
        self.assertGreater(expected, 0)
        emitted = self._emit(_scenario(rentals=[_rental(building)]))
        self.assertNotIn("f4562", emitted)
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), str(expected))

    def test_placement_year_emits_and_line_22_equals_schedule_e_line_18(self):
        """The twin: the form IS emitted in a placement year, and its line
        22 is the figure Schedule E line 18 prints."""
        emitted = self._emit(_scenario(rentals=[_rental(_new_building())]))
        self.assertIn("f4562", emitted)
        line_18 = _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A)
        self.assertEqual(line_18, "6970")
        self.assertEqual(_read(emitted["f4562"], F4562_LINE_22), line_18)


class OverriddenActivityTests(_EmitCase):
    """The reviewer's reproduction: a mid-stream overridden rental printed
    the override on Schedule E and the engine's figure on Form 4562."""

    def test_overridden_mid_stream_rental_emits_no_4562(self):
        building = _old_building()
        self.assertNotEqual(macrs_deduction(building, YEAR, mid_quarter_years=frozenset()), 7_000)
        emitted = self._emit(_scenario(
            rentals=[_rental(building, override_amount=7_000.0)]))
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), "7000")
        self.assertNotIn("f4562", emitted)

    def test_no_printed_4562_can_disagree_with_schedule_e(self):
        """Why the form must be absent for an overridden return: the
        merged form's engine-only total differs from the depreciation the
        activity prints. (The emitted-and-equal case is asserted on a
        placement year in EmitOnlyInAPlacementYearTests.)"""
        scenario = _scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)])
        emitted = self._emit(scenario)
        line_18 = sch_e.compute(scenario, upstream={})[
            "sch_e_property_a_depreciation"]
        self.assertNotIn("f4562", emitted)
        # The engine-only total the merged form WOULD have printed differs,
        # which is why it must not be emitted here.
        self.assertNotEqual(
            f4562.compute(scenario, upstream={})[
                "f4562_line_22_total_depreciation"], line_18)


class MergedFormWithOverrideRefusalTests(unittest.TestCase):
    REFUSAL = (r"Form 4562 is required this year.*one merged form.*"
               r"per-activity")

    def _business(self, *assets):
        return ScheduleCBusiness(
            description="Consulting", gross_receipts=50_000.0,
            depreciable_assets=tuple(assets))

    def test_placement_on_one_activity_and_override_on_another_refuses(self):
        s = _scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)],
            businesses=[self._business(_new_equipment())])
        with self.assertRaisesRegex(NotImplementedError, self.REFUSAL) as cm:
            enforce_scoped_refusals(s, "load")
        self.assertIn("rental property #0 ('100 Example Street')",
                      str(cm.exception))

    def test_override_with_no_placement_anywhere_is_silent(self):
        enforce_scoped_refusals(_scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)],
            businesses=[self._business()]), "load")

    def test_placement_with_no_override_anywhere_is_silent(self):
        enforce_scoped_refusals(_scenario(
            rentals=[_rental(_old_building())],
            businesses=[self._business(_new_equipment())]), "load")

    def test_resolving_the_overridden_activity_alone_does_not_refuse(self):
        """Whole-return question: not asked of a single activity."""
        from tenforty.forms.depreciation.resolver import resolve
        rental = _rental(_old_building(), override_amount=7_000.0)
        self.assertEqual(resolve(rental, YEAR, mid_quarter_years=frozenset()).amount, 7_000.0)


if __name__ == "__main__":
    unittest.main()
