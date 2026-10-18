# tests/test_verification_checks.py
"""The harness checks (spec §3.1, §3.3, §12; check-suite lane; rulings
2026-10-17: plan scope, the repeat-row zone pinned named-and-empty, FTB 3532
as the button vehicle).

Value and Placement run on scratch emits of two real small forms through
the real chokepoint: Schedule D (540) 2024 (tooltips -> Tooltip anchors) and
Form 8582 2024 (no tooltips -> RowLabel anchors). Ink and option groups need
buttons, which neither has, so FTB 3532 2024 (independent checkboxes) and
2025 (one radio group) carry them. Every declaration here is written from
the official line labels, its text taken from the extracted inventory; none
is derived from the mapping.
"""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, DecodedStreamObject, NameObject

import tests._pdf_pixels as shim
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.inventory import load as load_inventory
from tenforty.declarations.model import DeclaredLine, FormDeclaration
from tenforty.mappings.catalog import CATALOG
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
from tenforty.verification import checks, pixels
from tenforty.verification.checks import REPEATER_SHAPES
from tenforty.verification.anchors import default_anchor, label_pattern
from tenforty.verification.fill import FillSpec, fill, fill_spec_for
from tenforty.verification.record import EmitRecorder
from tests.helpers import REPO_ROOT

SCH_D = ("california", "sch_d_540")
F8582 = ("federal", "f8582")
YEAR = 2024


def _template(form, year=YEAR):
    juris, name = form
    return REPO_ROOT / "pdfs" / juris / str(year) / f"{name}.pdf"


def _text(form, label, section=""):
    for ln in load_inventory(form[1], YEAR).lines:
        if ln.label == label and ln.section == section:
            return ln.text
    raise LookupError((form, label, section))


def _line(form, label, key, section="", **over):
    fields = dict(line=label, description=_text(form, label, section),
                  key=key, kind="amount", section=section)
    fields.update(over)
    return DeclaredLine(**fields)


SCH_D_DECL = FormDeclaration(form=SCH_D, key=YEAR, not_printed={}, lines=(
    _line(SCH_D, "8", "sch_d_540_net_capital_gain"),
    _line(SCH_D, "12a", "sch_d_540_total_subtractions"),
    _line(SCH_D, "12b", "sch_d_540_total_additions"),
))
F8582_DECL = FormDeclaration(form=F8582, key=YEAR, not_printed={}, lines=(
    _line(F8582, "1a", "f8582_line_1a_activities_with_income", "Part I"),
    _line(F8582, "1b", "f8582_line_1b_activities_with_loss", "Part I"),
    _line(F8582, "1c", "f8582_line_1c_prior_year_unallowed_loss", "Part I"),
))
SCH_D_VALUES = {"sch_d_540_net_capital_gain": 1500.0,
                "sch_d_540_total_subtractions": 0.0,
                "sch_d_540_total_additions": 250.0}
F8582_VALUES = {"f8582_line_1a_activities_with_income": 1200.0,
                "f8582_line_1b_activities_with_loss": -300.0,
                "f8582_line_1c_prior_year_unallowed_loss": 0.0}


def _spec(form):
    if form == SCH_D:
        return fill_spec_for(PdfSchD540, YEAR)
    return fill_spec_for(PdfF8582, YEAR).flattened()


def _emit(form, values, spec=None, name="out"):
    spec = spec or _spec(form)
    out = Path(tempfile.mkdtemp()) / f"{name}.pdf"
    recorder = EmitRecorder()
    fill(form, YEAR, spec, _template(form), out, values, recorder)
    (rec,) = recorder.record()
    return rec


def _inject(pdf: Path, field_path: str, value: str) -> None:
    """Write /V into a filled PDF behind the filler's back (regenerating the
    appearance), to make 'printed where nothing was computed' reachable."""
    reader = PdfReader(str(pdf))
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, {field_path: value})
    with open(pdf, "wb") as f:
        writer.write(f)


def _swap(spec, key_a, key_b):
    m = dict(spec.mapping)
    m[key_a], m[key_b] = m[key_b], m[key_a]
    return dataclasses.replace(spec, mapping=m)


class ValueCheckTests(unittest.TestCase):

    def test_valued_keys_print_their_values(self):
        for form, decl, values in ((SCH_D, SCH_D_DECL, SCH_D_VALUES),
                                   (F8582, F8582_DECL, F8582_VALUES)):
            with self.subTest(form=form):
                self.assertEqual(checks.check_value(_emit(form, values),
                                                    decl), [])

    def test_valued_key_not_printed_is_a_finding(self):
        spec = _spec(SCH_D)
        spec = dataclasses.replace(spec, mapping={
            k: v for k, v in spec.mapping.items()
            if k != "sch_d_540_total_additions"})
        findings = checks.check_value(_emit(SCH_D, SCH_D_VALUES, spec), SCH_D_DECL)
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("12b", "value")])

    def test_none_key_printed_is_a_finding(self):
        values = dict(SCH_D_VALUES, sch_d_540_total_additions=None)
        rec = _emit(SCH_D, values)
        self.assertEqual(checks.check_value(rec, SCH_D_DECL), [])
        _inject(rec.pdf_path, PdfSchD540.get_mapping(YEAR)[
            "sch_d_540_total_additions"], "999")
        findings = checks.check_value(rec, SCH_D_DECL)
        self.assertEqual([f.line for f in findings], ["12b"])
        self.assertIn("nothing computed", findings[0].message)

    def _posture(self, line, posture):
        """F8582_DECL with ``line`` declared single_state=``posture``."""
        reason = f"synthetic control: line {line} is always {posture}"
        return dataclasses.replace(F8582_DECL, lines=tuple(
            dataclasses.replace(ln, single_state=posture,
                                single_state_reason=reason)
            if ln.line == line else ln for ln in F8582_DECL.lines)), reason

    def test_declared_value_line_with_nothing_computed_is_a_finding(self):
        decl, reason = self._posture("1b", "value")
        self.assertEqual(checks.check_value(
            _emit(F8582, F8582_VALUES), decl), [])
        values = dict(F8582_VALUES, f8582_line_1b_activities_with_loss=None)
        findings = checks.check_value(_emit(F8582, values), decl)
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("1b", "value")])
        self.assertIn("single_state='value'", findings[0].message)
        self.assertIn(reason, findings[0].message)

    def test_declared_nothing_bound_line_with_a_value_is_a_finding(self):
        decl, reason = self._posture("1b", "nothing")
        values = dict(F8582_VALUES, f8582_line_1b_activities_with_loss=None)
        self.assertEqual(checks.check_value(_emit(F8582, values), decl), [])
        findings = checks.check_value(_emit(F8582, F8582_VALUES), decl)
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("1b", "value")])
        self.assertIn("single_state='nothing'", findings[0].message)
        self.assertIn(reason, findings[0].message)

    def test_zero_prints_zero(self):
        rec = _emit(SCH_D, SCH_D_VALUES)
        field = PdfSchD540.get_mapping(YEAR)["sch_d_540_total_subtractions"]
        self.assertEqual(str(PdfReader(str(rec.pdf_path)).get_fields()[field]
                             .get("/V")), "0")
        self.assertEqual(checks.check_value(rec, SCH_D_DECL), [])

    def test_zero_printed_blank_is_a_finding(self):
        rec = _emit(SCH_D, SCH_D_VALUES)
        _inject(rec.pdf_path, PdfSchD540.get_mapping(YEAR)[
            "sch_d_540_total_subtractions"], "")
        findings = checks.check_value(rec, SCH_D_DECL)
        self.assertEqual([f.line for f in findings], ["12a"])
        self.assertIn("'0'", findings[0].message)

    def test_wrong_amount_is_a_finding(self):
        rec = _emit(F8582, F8582_VALUES)
        _inject(rec.pdf_path, PdfF8582.get_mapping(YEAR)["scalars"][
            "f8582_line_1a_activities_with_income"], "1300")
        self.assertEqual([f.line for f in checks.check_value(rec, F8582_DECL)],
                         ["1a"])


class BlankWhenZeroCauseTests(unittest.TestCase):
    """Review Focus 3: a computed 0 erased by blank_when_zero names the
    cause, not a generic blank."""

    def test_message_names_blank_when_zero_and_the_mapping_class(self):
        field = PdfSchD540.get_mapping(YEAR)["sch_d_540_total_subtractions"]
        spec = _spec(SCH_D).extend(blank_when_zero={field})
        findings = checks.check_value(_emit(SCH_D, SCH_D_VALUES, spec),
                                      SCH_D_DECL)
        self.assertEqual([f.line for f in findings], ["12a"])
        self.assertIn("blank_when_zero", findings[0].message)
        self.assertIn("PdfSchD540", findings[0].message)


class PlacementTests(unittest.TestCase):

    def test_correct_mappings_place_cleanly(self):
        for form, decl in ((SCH_D, SCH_D_DECL), (F8582, F8582_DECL)):
            with self.subTest(form=form):
                self.assertEqual(checks.check_placement(
                    _template(form), decl, _spec(form)), [])

    def test_swapped_paths_are_two_placement_findings_and_value_stays_clean(self):
        for form, decl, values, a, b in (
                (SCH_D, SCH_D_DECL, SCH_D_VALUES,
                 "sch_d_540_total_subtractions", "sch_d_540_total_additions"),
                (F8582, F8582_DECL, F8582_VALUES,
                 "f8582_line_1a_activities_with_income",
                 "f8582_line_1b_activities_with_loss")):
            with self.subTest(form=form):
                spec = _swap(_spec(form), a, b)
                placement = checks.check_placement(_template(form), decl, spec)
                self.assertEqual(len(placement), 2, placement)
                # The anchor, not the value, carries the identity.
                self.assertEqual(checks.check_value(
                    _emit(form, values, spec), decl), [])

    def test_key_less_lines_are_not_placed(self):
        # A key-less line (unmodeled, or preprinted) has no mapped field by
        # definition; placement checks mapping-declaration agreement, which
        # exists only for bound lines.
        decl = dataclasses.replace(F8582_DECL, lines=F8582_DECL.lines + (
            _line(F8582, "2a", "", "Part I", single_state="nothing",
                  single_state_reason="unmodeled: synthetic control"),))
        self.assertEqual(checks.check_placement(
            _template(F8582), decl, _spec(F8582)), [])

    def test_bound_line_without_a_mapped_field_is_still_a_finding(self):
        decl = dataclasses.replace(F8582_DECL, lines=F8582_DECL.lines + (
            _line(F8582, "2a", "f8582_no_such_key", "Part I"),))
        findings = checks.check_placement(
            _template(F8582), decl, _spec(F8582))
        self.assertEqual([f.line for f in findings], ["2a"])
        self.assertIn("has no field to place", findings[0].message)

    def test_ambiguous_near_label_is_a_finding(self):
        # "Activities with net income" prints for both line 1a and line 2a.
        decl = FormDeclaration(form=F8582, key=YEAR, not_printed={}, lines=(
            _line(F8582, "1a", "f8582_line_1a_activities_with_income",
                  "Part I", anchor=NearLabel("Activities with net income",
                                             LabelRelation.ON_ROW)),))
        findings = checks.check_placement(_template(F8582), decl, _spec(F8582))
        self.assertEqual(len(findings), 1)
        self.assertIn("ambiguous", findings[0].message)

    def test_default_anchors(self):
        ln = SCH_D_DECL.lines[1]
        self.assertEqual(default_anchor(ln, True).pattern, label_pattern("12a"))
        self.assertEqual(default_anchor(ln, False).token, "12a")
        import re
        self.assertRegex("Line 12 a. If line 10", label_pattern("12a"))
        self.assertNotRegex("Line 18. Total", label_pattern("8"))
        self.assertNotRegex("Line 12 b.", label_pattern("12a"))


class ExemptedAnchoredPlacementTests(unittest.TestCase):
    """R1 ruling: an inventory-exempted line that declares an explicit
    anchor is PLACED; only an exempted line with no expressible anchor (the
    Schedule C Part V grid rows) is skipped. Vehicle: Form 8995 2024's row i
    name cell, which the inventory does not print (it lists bare row ids)."""

    YEAR = 2024

    @classmethod
    def setUpClass(cls):
        from tenforty.mappings.pdf_f8995 import PdfF8995
        cls.spec = fill_spec_for(PdfF8995, cls.YEAR)
        cls.template = (REPO_ROOT / "pdfs" / "federal" / str(cls.YEAR)
                        / "f8995.pdf")

    def _decl(self, anchor):
        line = DeclaredLine(
            line="1i(a)", description="(a) Trade, business, or aggregation "
            "name", key="f8995_line_1i_name", kind="text", section="",
            anchor=anchor, inventory_exemption="synthetic control: the "
            "inventory prints bare row ids")
        return FormDeclaration(form=("federal", "f8995"), key=self.YEAR,
                               not_printed={}, lines=(line,))

    def test_an_exempted_line_with_its_anchor_places(self):
        self.assertEqual(checks.check_placement(
            self.template, self._decl(NearLabel("i", LabelRelation.RIGHT_OF)),
            self.spec), [])

    def test_an_exempted_line_with_a_wrong_anchor_is_a_finding(self):
        # Kill-check: line 2's phrase locates line 2's field, not row i's.
        wrong = NearLabel("Total qualified business income or (loss).",
                          LabelRelation.AFTER_WRAPPED)
        findings = checks.check_placement(self.template, self._decl(wrong),
                                          self.spec)
        self.assertEqual([f.line for f in findings], ["1i(a)"])

    def test_an_exempted_line_without_an_anchor_is_skipped(self):
        # The Schedule C Part V case: no printed label to anchor on.
        self.assertEqual(checks.check_placement(
            self.template, self._decl(None), self.spec), [])


class NearFieldSameRowTests(unittest.TestCase):
    """NearField SAME_ROW_RIGHT_OF (R2 ruling): abutting cells are right-of
    (gap 0), overlap is not. Form 8995 2024's line-1 row i cells abut: (b)
    ends at x=482.4 exactly where (c) begins."""

    YEAR = 2024
    REL = None

    @classmethod
    def setUpClass(cls):
        from tenforty.declarations.anchors import FieldRelation
        from tenforty.mappings.pdf_f8995 import PdfF8995
        cls.REL = FieldRelation.SAME_ROW_RIGHT_OF
        spec = fill_spec_for(PdfF8995, cls.YEAR)
        scalars = (spec.mapping["scalars"] if spec.kind == "repeater"
                   else spec.mapping)
        cls.a = scalars["f8995_line_1i_name"]
        cls.b = scalars["f8995_line_1i_tin"]
        cls.c = scalars["f8995_line_1_qbi"]
        cls.template = REPO_ROOT / "pdfs" / "federal" / str(cls.YEAR) / "f8995.pdf"

    def _evaluate(self, field, other_line, other_field):
        from tenforty.declarations.anchors import NearField
        from tenforty.verification import anchors as anchor_eval
        return anchor_eval.evaluate(NearField(other_line, self.REL), field,
                                    self.template, other_field=other_field)

    def test_the_cells_abut(self):
        _p, b = shim.widget_rect(self.template, self.b)
        _p, c = shim.widget_rect(self.template, self.c)
        self.assertEqual(c[0], b[2])

    def test_an_abutting_cell_is_right_of(self):
        self.assertIsNone(self._evaluate(self.c, "1i(b)", self.b))

    def test_a_gapped_cell_is_right_of(self):
        self.assertIsNone(self._evaluate(self.b, "1i(a)", self.a))

    def test_a_cell_to_the_left_is_not_right_of(self):
        finding = self._evaluate(self.a, "1i(b)", self.b)
        self.assertIsNotNone(finding)
        self.assertIn("same_row_right_of", finding.message)


class InkTests(unittest.TestCase):

    def test_valued_text_lines_carry_ink(self):
        self.assertEqual(checks.check_ink(_emit(F8582, F8582_VALUES),
                                          F8582_DECL), [])

    def test_none_key_with_injected_ink_is_a_finding(self):
        values = dict(F8582_VALUES, f8582_line_1b_activities_with_loss=None)
        rec = _emit(F8582, values)
        self.assertEqual(checks.check_ink(rec, F8582_DECL), [])
        _inject(rec.pdf_path, PdfF8582.get_mapping(YEAR)["scalars"][
            "f8582_line_1b_activities_with_loss"], "88888")
        findings = checks.check_ink(rec, F8582_DECL)
        self.assertEqual([f.line for f in findings], ["1b"])
        self.assertIn("ink where nothing", findings[0].message)


class CombTemplateArtInkTests(unittest.TestCase):
    """A nothing-computed field's ink is compared with the BLANK template's
    ink in the same rect at the same inset (S2 ruling). Schedule C's line B
    business code is a comb field: the official template prints divider
    marks inside its widget, which is template art, not a fill. A real
    sch_c emit (sch_c_battery sole-trade-basic 2022: no business code)
    through the battery's own entry point."""

    YEAR = 2022
    LINE_B = "sch_c_line_b_business_code"

    @classmethod
    def setUpClass(cls):
        from tenforty.declarations import sch_c
        from tenforty.verification import emit_manifest
        from tenforty.verification.batteries import BATTERIES
        battery = next(b for b in BATTERIES if b.name == "sch_c_battery")
        build = next(b for n, y, b in battery.scenarios()
                     if (n, y) == ("sole-trade-basic", cls.YEAR))
        result = emit_manifest.emit(
            battery, build(), Path(tempfile.mkdtemp()) / "out")
        cls.rec = next(r for r in result.record
                       if r.form == ("federal", "sch_c"))
        cls.decl = sch_c.DECLARATIONS[cls.YEAR]

    def test_the_vehicle_computes_no_business_code(self):
        self.assertIsNone(self.rec.values.get(self.LINE_B))

    def test_comb_template_art_is_not_ink(self):
        findings = [f for f in checks.check_ink(self.rec, self.decl)
                    if f.line == "B"]
        self.assertEqual(findings, [])

    def test_a_character_in_the_empty_comb_field_is_ink(self):
        # Kill-check: real stray print between the dividers still fires.
        field = self.rec.spec.mapping[self.LINE_B]
        _inject(self.rec.pdf_path, field, "5")
        try:
            findings = [f for f in checks.check_ink(self.rec, self.decl)
                        if f.line == "B"]
        finally:
            _inject(self.rec.pdf_path, field, "")
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("ink where nothing is computed", findings[0].message)


class RepeaterZoneTests(unittest.TestCase):
    """The repeat-row no-check zone, pinned named and empty (ruling
    2026-10-17, option ii): the repeater-shape universe is exactly f8949's
    pre-baked row lists, and a declared form whose spec carries a template
    repeater section gets a named finding instead of silent no-checks. The
    row-key convention waits for the first real template-repeater form; this
    census failing is what forces that design."""

    def test_repeater_shape_universe_is_exactly_f8949_row_lists(self):
        found = set()
        for (juris, form), entry in sorted(CATALOG.items()):
            for year in range(2021, 2026):
                try:
                    m = entry.mapping_cls.get_mapping(year)
                except ValueError:
                    continue
                if not (isinstance(m, dict) and "repeaters" in m):
                    continue
                for section, shape in m["repeaters"].items():
                    kind = ("rows" if isinstance(shape, list)
                            and all(isinstance(r, dict) for r in shape)
                            else "template" if isinstance(shape, dict)
                            and "template" in shape else "other")
                    found.add((form, section, kind))
        self.assertEqual(found, REPEATER_SHAPES)

    def test_template_section_on_a_declared_form_is_a_named_finding(self):
        spec = FillSpec(kind="repeater", mapping={
            "scalars": {"f8582_line_1a_activities_with_income":
                        "topmostSubform[0].Page1[0].f1_3[0]"},
            "repeaters": {"rows": {"template": {"amt": "F{i}"},
                                   "max_slots": 3}}})
        findings = checks.check_repeater_rows(spec, F8582_DECL)
        self.assertEqual(len(findings), 1)
        self.assertIn("no-check zone", findings[0].message)
        self.assertIn("rows", findings[0].message)

    def test_prebaked_row_specs_have_no_zone_finding(self):
        from tenforty.mappings.pdf_f8949 import PdfF8949
        self.assertEqual(checks.check_repeater_rows(
            fill_spec_for(PdfF8949, YEAR), F8582_DECL), [])


class CompletenessTests(unittest.TestCase):
    """Every emitted file is a recorded fill or a classified non-fill
    (consuming NON_FILL_EMITTED and the fill census, duplicating neither)."""

    @classmethod
    def setUpClass(cls):
        from tests.fixtures import chokepoint_scenarios as cases
        cls._tmp = tempfile.TemporaryDirectory()
        ret, _out = cases.run_case("run_full_return_f3115_2025",
                                   Path(cls._tmp.name))
        cls.emitted = ret[1]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a_real_emit_is_fully_accounted_for(self):
        self.assertEqual(checks.check_unaccounted(self.emitted,
                                                  self.emitted.record), [])

    def test_an_unrecorded_fill_is_a_finding(self):
        record = type(self.emitted.record)(
            r for r in self.emitted.record if r.form != ("federal", "1040"))
        findings = checks.check_unaccounted(self.emitted, record)
        self.assertEqual([f.form for f in findings], ["1040"])

    def test_classified_non_fills_pass(self):
        # f3115_asset_stmt and f3115_duplicate_copy are emitted, not filled.
        self.assertIn("f3115_asset_stmt", self.emitted)
        self.assertEqual(checks.check_unaccounted(self.emitted,
                                                  self.emitted.record), [])


class NeverRaisesTests(unittest.TestCase):
    """Every check returns findings; none raises on a broken input."""

    def test_missing_pdf_is_a_finding_not_an_exception(self):
        rec = _emit(SCH_D, SCH_D_VALUES)
        broken = dataclasses.replace(rec, pdf_path=rec.pdf_path.with_name(
            "missing.pdf"))
        for check in (checks.check_value, checks.check_ink,
                      checks.check_option_groups):
            with self.subTest(check=check.__name__):
                findings = check(broken, SCH_D_DECL)
                self.assertEqual(len(findings), 1)
                self.assertIn("could not run", findings[0].message)


class PixelsShimTests(unittest.TestCase):

    def test_shim_names_are_the_moved_objects(self):
        for name in ("dark_pixels_in_rect", "widget_rect", "checked_widgets",
                     "render_gray"):
            with self.subTest(name=name):
                self.assertIs(getattr(shim, name), getattr(pixels, name))


# --- the button vehicle: FTB 3532 (ruled 2026-10-17) -----------------------

FTB3532 = ("california", "ftb3532")
MARITAL = ("unmarried", "surviving_spouse", "marriage_annulled",
           "divorced_or_legally_separated", "married_lived_apart_all_year",
           "married_lived_together_part_of_year")


def _ftb3532_decl(year):
    """Part I of FTB 3532 as an option group, from the official labels."""
    return FormDeclaration(form=FTB3532, key=year, not_printed={}, lines=tuple(
        DeclaredLine(line=f"1{letter}", description=f"Part I line 1{letter}",
                     key="ftb3532_marital_status", kind="checkbox",
                     section="Part I", group="marital_status", selects=value)
        for letter, value in zip("abcdef", MARITAL)))


def _ftb3532_spec(year):
    from tenforty.mappings.pdf_ftb3532 import PdfFtb3532
    return fill_spec_for(PdfFtb3532, year)


def _emit_3532(year, value, spec=None, template=None):
    spec = spec or _ftb3532_spec(year)
    out = Path(tempfile.mkdtemp()) / "ftb3532.pdf"
    recorder = EmitRecorder()
    fill(FTB3532, year, spec,
         template or REPO_ROOT / "pdfs" / "california" / str(year)
         / "ftb3532.pdf", out, {"ftb3532_marital_status": value}, recorder)
    (rec,) = recorder.record()
    return rec


def _set_button(pdf: Path, field: str, state: str) -> None:
    """Turn a widget of ``field`` ON as ``state`` behind the filler's back."""
    reader = PdfReader(str(pdf))
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        for annot in page.get("/Annots") or []:
            w = annot.get_object()
            name = w.get("/T") or w.get("/Parent", {}).get("/T")
            if str(name) == field:
                w[NameObject("/AS")] = NameObject(state)
                w[NameObject("/V")] = NameObject(state)
    with open(pdf, "wb") as f:
        writer.write(f)


class OptionGroupTests(unittest.TestCase):
    """Exclusivity (ruling A2; gate = presence, check-suite = exclusivity):
    2024 Part I is six independent checkboxes, 2025 Part I one radio."""

    def test_every_option_value_is_exclusive_valued_and_inked(self):
        for year in (2024, 2025):
            decl = _ftb3532_decl(year)
            for value in MARITAL:
                with self.subTest(year=year, value=value):
                    rec = _emit_3532(year, value)
                    self.assertEqual(checks.check_option_groups(rec, decl), [])
                    self.assertEqual(checks.check_value(rec, decl), [])
                    self.assertEqual(checks.check_ink(rec, decl), [])

    def test_two_widgets_on_in_one_group_is_a_finding(self):
        rec = _emit_3532(2024, "unmarried")
        _set_button(rec.pdf_path, "3532_1004 CB", "/Yes")
        findings = checks.check_option_groups(rec, _ftb3532_decl(2024))
        self.assertEqual(len(findings), 1)
        self.assertIn("2 widget(s) ON", findings[0].message)

    def test_a_state_absent_from_the_widgets_own_appearances_is_a_finding(self):
        """Spec §12 S5. RECORDED BEHAVIOUR, pypdf 6.9.2 (the pinned venv; a
        pypdf bump must re-derive this, not trust it): filling the 2025 radio
        with a token no kid's /AP /N carries ("/9") writes /V = /9 on the
        PARENT and leaves every kid's /AS at /Off. The widget-level state is
        SKIPPED (not written and masked), so no kid is ON and the group
        reads 0 ON for a valued key: an option-group finding."""
        spec = _ftb3532_spec(2025)
        spec = dataclasses.replace(spec, derivations={
            **spec.derivations, "3532_1003 RB": lambda v: "/9"})
        rec = _emit_3532(2025, "unmarried", spec=spec)
        states = [w[2] for w in checks._widgets(rec.pdf_path)["3532_1003 RB"]]
        self.assertEqual(sorted(set(states)), ["/Off"])  # pypdf 6.9.2
        self.assertEqual(str(PdfReader(str(rec.pdf_path)).get_fields()[
            "3532_1003 RB"].get("/V")), "/9")              # pypdf 6.9.2
        findings = checks.check_option_groups(rec, _ftb3532_decl(2025))
        self.assertEqual(len(findings), 1)
        self.assertIn("0 widget(s) ON, expected 1", findings[0].message)

    def test_an_on_state_outside_the_widgets_own_appearances_is_a_finding(self):
        # Not reachable through pypdf 6.9.2's radio fill (above), so the
        # finding is proven by writing the stray /AS directly.
        rec = _emit_3532(2024, "unmarried")
        _set_button(rec.pdf_path, "3532_1003 CB", "/9")
        findings = checks.check_option_groups(rec, _ftb3532_decl(2024))
        self.assertTrue(any("not one of its own /AP /N states" in f.message
                            for f in findings), findings)


def _without_need_appearances(pdf: Path) -> None:
    """Clear /NeedAppearances, as a viewer that does not regenerate
    appearances sees the file. Measured with pypdf 6.9.2 + poppler: the
    filler's output sets /NeedAppearances true, and poppler then regenerates
    a checkbox's look from its own /MK, so even an EMPTY on-state stream
    renders a mark there (35 dark px on FTB 3532 2024 line 1a). The
    unpainted-box case is only visible without that regeneration, which is
    exactly the viewer ensure_button_marks_visible protects."""
    writer = PdfWriter(clone_from=PdfReader(str(pdf)))
    writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = \
        BooleanObject(False)
    with open(pdf, "wb") as f:
        writer.write(f)


class ButtonInkTests(unittest.TestCase):
    """A checked box whose on-state appearance paints nothing has no visible
    mark; ensure_button_marks_visible is what normally prevents that."""

    def _blank_yes_template(self) -> Path:
        src = REPO_ROOT / "pdfs" / "california" / "2024" / "ftb3532.pdf"
        writer = PdfWriter(clone_from=PdfReader(str(src)))
        for page in writer.pages:
            for annot in page.get("/Annots") or []:
                w = annot.get_object()
                if str(w.get("/T")) == "3532_1003 CB":
                    stream = DecodedStreamObject()
                    stream.set_data(b"")
                    w["/AP"]["/N"][NameObject("/Yes")] = \
                        writer._add_object(stream)
        out = Path(tempfile.mkdtemp()) / "ftb3532_blank_yes.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        return out

    def test_unpainted_checked_box_is_an_ink_finding(self):
        template = self._blank_yes_template()
        with unittest.mock.patch(
                "tenforty.filing.pdf.ensure_button_marks_visible"):
            rec = _emit_3532(2024, "unmarried", template=template)
        _without_need_appearances(rec.pdf_path)
        findings = checks.check_ink(rec, _ftb3532_decl(2024))
        self.assertEqual([f.line for f in findings], ["1a"])
        self.assertIn("no visible mark", findings[0].message)

    def test_the_filler_makes_the_same_box_visible(self):
        rec = _emit_3532(2024, "unmarried", template=self._blank_yes_template())
        _without_need_appearances(rec.pdf_path)
        self.assertEqual(checks.check_ink(rec, _ftb3532_decl(2024)), [])
