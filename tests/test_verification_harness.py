# tests/test_verification_harness.py
"""Testing the harness itself (emit-verification harness spec §12): one
planted defect per seam, each of which must yield exactly the expected
finding, so no check can pass vacuously.

Each control builds its own scratch emit through the real chokepoint
(``verification.fill.fill``) of a small real form, Schedule D (540) 2024
(tooltips) or Form 8582 2024 (none), with FTB 3532 for the button seams, and
an in-memory declaration written from the official line labels (text from
the extracted inventory), never from the mapping.
"""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    BooleanObject,
    DecodedStreamObject,
    NameObject,
)

from tenforty.declarations import propose, registry
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.inventory import load as load_inventory
from tenforty.declarations.model import (
    DeclaredLine,
    FormDeclaration,
    Repeat,
)
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.mappings.pdf_ftb3532 import PdfFtb3532
from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
from tenforty.verification import checks, gate, pending
from tenforty.verification.coverage import WORKBOOK_LABEL, coverage_cells
from tenforty.verification.crosscheck import crosscheck
from tenforty.verification.fill import FillSpec, fill, fill_spec_for
from tenforty.verification.gate import IncompleteEmitError, missing_lines
from tenforty.verification.record import EmitRecorder
from tenforty.verification.undeclared import undeclared_keys
from tests.helpers import REPO_ROOT

YEAR = 2024
SCH_D = ("california", "sch_d_540")
F8582 = ("federal", "f8582")
FTB3532 = ("california", "ftb3532")
K_NET = "sch_d_540_net_capital_gain"
K_SUB = "sch_d_540_total_subtractions"
K_ADD = "sch_d_540_total_additions"
K_1A = "f8582_line_1a_activities_with_income"
K_1B = "f8582_line_1b_activities_with_loss"
K_1C = "f8582_line_1c_prior_year_unallowed_loss"
K_1D = "f8582_line_1d_combine"


def _template(form, year=YEAR):
    return REPO_ROOT / "pdfs" / form[0] / str(year) / f"{form[1]}.pdf"


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


def _decl(form, *lines, not_printed=None, key=YEAR):
    return FormDeclaration(form=form, key=key, lines=tuple(lines),
                           not_printed=dict(not_printed or {}))


SCH_D_DECL = _decl(SCH_D, _line(SCH_D, "8", K_NET), _line(SCH_D, "12a", K_SUB),
                   _line(SCH_D, "12b", K_ADD))
F8582_DECL = _decl(F8582, _line(F8582, "1a", K_1A, "Part I"),
                   _line(F8582, "1b", K_1B, "Part I"),
                   _line(F8582, "1c", K_1C, "Part I"))
SCH_D_VALUES = {K_NET: 1500.0, K_SUB: 0.0, K_ADD: 250.0}
F8582_VALUES = {K_1A: 1200.0, K_1B: -300.0, K_1C: 0.0}


def _spec(form):
    if form == SCH_D:
        return fill_spec_for(PdfSchD540, YEAR)
    return fill_spec_for(PdfF8582, YEAR).flattened()


def _emit(form, values, spec=None, template=None, year=YEAR):
    spec = spec or _spec(form)
    out = Path(tempfile.mkdtemp()) / f"{form[1]}.pdf"
    recorder = EmitRecorder()
    fill(form, year, spec, template or _template(form, year), out, values,
         recorder)
    (rec,) = recorder.record()
    return rec


def _inject(pdf, field, value):
    writer = PdfWriter(clone_from=PdfReader(str(pdf)))
    for page in writer.pages:
        writer.update_page_form_field_values(page, {field: value})
    with open(pdf, "wb") as f:
        writer.write(f)


def _declared(form, decl, year=YEAR):
    """Register ``decl`` and take ``form`` off the pending list."""
    without = {k: v for k, v in pending.PENDING_DECLARATIONS.items()
               if k != form}
    return (unittest.mock.patch.dict(registry._DECLARATIONS,
                                     {(form, year): decl}),
            unittest.mock.patch.object(pending, "PENDING_DECLARATIONS",
                                       without))


def _refuses(form, spec, values, year=YEAR):
    try:
        gate.check(form, year, spec, values)
    except IncompleteEmitError:
        return True
    return False


class S0UndeclaredKeyControls(unittest.TestCase):

    def test_a_computed_key_bound_nowhere_is_undeclared(self):
        values = dict(SCH_D_VALUES, sch_d_540_orphan=42.0)
        rec = _emit(SCH_D, values)
        p1, p2 = _declared(SCH_D, SCH_D_DECL)
        with p1, p2:
            findings = undeclared_keys([rec], scenario="control")
        self.assertEqual([f.check for f in findings], ["undeclared"])
        self.assertIn("sch_d_540_orphan", findings[0].message)

    def test_a_not_printed_key_with_a_reason_is_declared(self):
        decl = dataclasses.replace(SCH_D_DECL, not_printed={
            "sch_d_540_orphan": "intermediate: feeds line 8"})
        rec = _emit(SCH_D, dict(SCH_D_VALUES, sch_d_540_orphan=42.0))
        p1, p2 = _declared(SCH_D, decl)
        with p1, p2:
            self.assertEqual(undeclared_keys([rec]), [])

    def test_a_declared_key_whose_mapping_entry_is_gone(self):
        spec = _spec(SCH_D)
        spec = dataclasses.replace(spec, mapping={
            k: v for k, v in spec.mapping.items() if k != K_ADD})
        rec = _emit(SCH_D, SCH_D_VALUES, spec)
        self.assertEqual([f.line for f in checks.check_value(rec, SCH_D_DECL)],
                         ["12b"])
        p1, p2 = _declared(SCH_D, SCH_D_DECL)
        with p1, p2:
            self.assertTrue(_refuses(SCH_D, spec, SCH_D_VALUES))


class S1ToS4ValueAndGateControls(unittest.TestCase):
    """Each planted defect is a Value finding AND a gate refusal."""

    def _both(self, form, decl, spec, values, line):
        rec = _emit(form, values, spec)  # pending outside the patch: fills
        p1, p2 = _declared(form, decl)
        with p1, p2:
            self.assertTrue(_refuses(form, spec, values),
                            "the gate must refuse")
        findings = missing_lines(decl, values,
                                 gate.final_payload(spec, values), spec)
        self.assertEqual([f.line for f in findings], [line])
        self.assertIn(line, [f.line for f in checks.check_value(rec, decl)])

    def test_s1_derived_cell_whose_lambda_raises_keyerror(self):
        field = PdfF8582.get_mapping(YEAR)["scalars"][K_1A]
        spec = _spec(F8582)
        spec = dataclasses.replace(
            spec, mapping={k: v for k, v in spec.mapping.items() if k != K_1A},
            derivations={field: lambda v: v["never_computed"]})
        self._both(F8582, F8582_DECL, spec, F8582_VALUES, "1a")

    def test_s2_valued_key_the_one_to_one_pass_skips(self):
        # The mapping spells the key differently: the 1:1 pass never sees it.
        spec = _spec(F8582)
        m = dict(spec.mapping)
        m["f8582_line_1b_activities_with_loss_TYPO"] = m.pop(K_1B)
        spec = dataclasses.replace(spec, mapping=m)
        self._both(F8582, F8582_DECL, spec, F8582_VALUES, "1b")

    def test_s3_aggregation_with_a_none_constituent(self):
        field_1d = PdfF8582.get_mapping(YEAR)["scalars"][K_1D]
        decl = _decl(F8582, _line(F8582, "1d", K_1D, "Part I"))
        spec = FillSpec(kind="flat", mapping={K_1D: field_1d},
                        aggregations={field_1d: (K_1A, K_1B, K_1C)})
        values = {K_1D: 900.0, K_1A: 1200.0, K_1B: -300.0, K_1C: None}
        self._both(F8582, decl, spec, values, "1d")

    def test_s4_none_repeat_cell_under_a_valued_key(self):
        fields = PdfF8582.get_mapping(YEAR)["scalars"]
        decl = _decl(F8582, DeclaredLine(
            line="1{col}", description="Part I line 1", key="row_{col}",
            kind="amount", section="Part I",
            repeat=Repeat("col", values=("a", "b"))))
        spec = FillSpec(kind="flat", mapping={"row_a": fields[K_1A]})
        values = {"row_a": 10.0, "row_b": 20.0}
        self._both(F8582, decl, spec, values, "1b")


class S5UnknownStateControl(unittest.TestCase):
    """Spec §12 S5 (O6). Recorded with pypdf 6.9.2 (the pinned venv; a bump
    must re-derive it): a radio token absent from every kid's /AP /N is
    SKIPPED at the widget (parent /V written, every kid /Off), so the Value
    check reports the missing selection and the group reads 0 ON."""

    def test_unknown_radio_state_is_caught(self):
        decl = _decl(FTB3532, *(
            DeclaredLine(line=f"1{c}", description=f"Part I line 1{c}",
                         key="ftb3532_marital_status", kind="checkbox",
                         section="Part I", group="marital_status", selects=v)
            for c, v in zip("abcdef", (
                "unmarried", "surviving_spouse", "marriage_annulled",
                "divorced_or_legally_separated",
                "married_lived_apart_all_year",
                "married_lived_together_part_of_year"))), key=2025)
        spec = fill_spec_for(PdfFtb3532, 2025)
        spec = dataclasses.replace(spec, derivations={
            **spec.derivations, "3532_1003 RB": lambda v: "/9"})
        rec = _emit(FTB3532, {"ftb3532_marital_status": "unmarried"}, spec,
                    year=2025)
        value = checks.check_value(rec, decl)
        groups = checks.check_option_groups(rec, decl)
        self.assertEqual([f.line for f in value], ["1a"])
        self.assertTrue(any("0 widget(s) ON" in f.message for f in groups))


class S6ProvenanceControls(unittest.TestCase):

    def test_a_value_printed_over_a_none_key_is_ink_where_nothing(self):
        values = dict(F8582_VALUES, **{K_1B: None})
        rec = _emit(F8582, values)
        _inject(rec.pdf_path, PdfF8582.get_mapping(YEAR)["scalars"][K_1B],
                "77777")
        self.assertEqual([f.line for f in checks.check_ink(rec, F8582_DECL)],
                         ["1b"])

    def test_a_blank_over_a_computed_zero_is_a_value_finding(self):
        rec = _emit(SCH_D, SCH_D_VALUES)
        _inject(rec.pdf_path, PdfSchD540.get_mapping(YEAR)[K_SUB], "")
        self.assertEqual([f.line for f in checks.check_value(rec, SCH_D_DECL)],
                         ["12a"])


class S7UnpaintedCheckboxControl(unittest.TestCase):

    def test_checked_box_painting_nothing_is_an_ink_finding(self):
        src = _template(FTB3532)
        writer = PdfWriter(clone_from=PdfReader(str(src)))
        for page in writer.pages:
            for annot in page.get("/Annots") or []:
                w = annot.get_object()
                if str(w.get("/T")) == "3532_1003 CB":
                    stream = DecodedStreamObject()
                    stream.set_data(b"")
                    w["/AP"]["/N"][NameObject("/Yes")] = \
                        writer._add_object(stream)
        blank = Path(tempfile.mkdtemp()) / "ftb3532.pdf"
        with open(blank, "wb") as f:
            writer.write(f)
        decl = _decl(FTB3532, DeclaredLine(
            line="1a", description="Part I line 1a",
            key="ftb3532_marital_status", kind="checkbox", section="Part I",
            group="marital_status", selects="unmarried"))
        with unittest.mock.patch(
                "tenforty.filing.pdf.ensure_button_marks_visible"):
            rec = _emit(FTB3532, {"ftb3532_marital_status": "unmarried"},
                        fill_spec_for(PdfFtb3532, YEAR), template=blank)
        # Model a viewer that does not regenerate appearances (pypdf sets
        # /NeedAppearances; poppler would otherwise redraw from /MK).
        w2 = PdfWriter(clone_from=PdfReader(str(rec.pdf_path)))
        w2._root_object["/AcroForm"][NameObject("/NeedAppearances")] = \
            BooleanObject(False)
        with open(rec.pdf_path, "wb") as f:
            w2.write(f)
        self.assertEqual([f.line for f in checks.check_ink(rec, decl)], ["1a"])


class S8S9SwappedPathControls(unittest.TestCase):
    """Two keys' mapped paths swapped: read-back still 'matches', placement
    fails. The anchor, not the read-back, carries field identity."""

    def test_swap_fails_placement_while_value_passes(self):
        for form, decl, values, a, b in (
                (SCH_D, SCH_D_DECL, SCH_D_VALUES, K_SUB, K_ADD),
                (F8582, F8582_DECL, F8582_VALUES, K_1A, K_1B)):
            with self.subTest(form=form):
                spec = _spec(form)
                m = dict(spec.mapping)
                m[a], m[b] = m[b], m[a]
                spec = dataclasses.replace(spec, mapping=m)
                self.assertEqual(checks.check_value(_emit(form, values, spec),
                                                    decl), [])
                self.assertEqual(len(checks.check_placement(
                    _template(form), decl, spec)), 2)


class S10LabelControls(unittest.TestCase):

    def test_a_wrong_line_label_fails_the_stylesheet_diff(self):
        decl = _decl(F8582, dataclasses.replace(
            F8582_DECL.lines[0], line="1z"))
        findings = crosscheck(decl, propose.stylesheet_lines("f8582", YEAR))
        self.assertEqual([f.line for f in findings], ["1z"])
        self.assertIn("not printed by the official stylesheet",
                      findings[0].message)

    def test_correct_labels_pass_the_stylesheet_diff(self):
        self.assertEqual(crosscheck(F8582_DECL,
                                    propose.stylesheet_lines("f8582", YEAR)),
                         [])

    def test_a_wrong_mef_element_fails_the_stylesheet_diff(self):
        decl = _decl(F8582, dataclasses.replace(
            F8582_DECL.lines[0], mef_element="NotTheRightElementAmt"))
        findings = crosscheck(decl, propose.stylesheet_lines("f8582", YEAR))
        self.assertEqual(len(findings), 1)
        self.assertIn("mef_element", findings[0].message)

    def test_a_near_label_phrase_matching_twice_is_ambiguous(self):
        decl = _decl(F8582, dataclasses.replace(
            F8582_DECL.lines[0], anchor=NearLabel(
                "Activities with net income", LabelRelation.ON_ROW)))
        findings = checks.check_placement(_template(F8582), decl, _spec(F8582))
        self.assertTrue(findings and "ambiguous" in findings[0].message)


class CoverageControls(unittest.TestCase):

    def test_a_line_seen_only_valued_is_one_uncovered_cell(self):
        decl = _decl(SCH_D, _line(SCH_D, "8", K_NET))
        rec = _emit(SCH_D, {K_NET: 1500.0})
        report = coverage_cells([("only-valued", rec)], [decl])
        self.assertEqual(report.uncovered,
                         ((SCH_D, YEAR, "8", "nothing"),))

    def test_both_states_seen_is_covered(self):
        decl = _decl(SCH_D, _line(SCH_D, "8", K_NET))
        records = [("valued", _emit(SCH_D, {K_NET: 1500.0})),
                   ("nothing", _emit(SCH_D, {K_NET: None}))]
        self.assertEqual(coverage_cells(records, [decl]).uncovered, ())

    def test_a_single_state_line_needs_only_its_state(self):
        decl = _decl(SCH_D, _line(SCH_D, "8", K_NET, single_state="value",
                                  single_state_reason="never blank here"))
        rec = _emit(SCH_D, {K_NET: 1500.0})
        self.assertEqual(coverage_cells([("v", rec)], [decl]).uncovered, ())


class WorkbookScopeControls(unittest.TestCase):
    """The WORKBOOK label is the only thing holding the line green."""

    def test_workbook_line_is_listed_not_red_and_native_is_red(self):
        workbook = _decl(SCH_D, _line(SCH_D, "8", K_NET, scope="WORKBOOK"))
        native = _decl(SCH_D, _line(SCH_D, "8", K_NET))
        rec = _emit(SCH_D, {K_NET: 1500.0})
        wb = coverage_cells([("s", rec)], [workbook])
        self.assertEqual(wb.uncovered, ())
        self.assertIn((SCH_D, YEAR, "8", "nothing"), wb.workbook_scoped)
        self.assertIn(WORKBOOK_LABEL, wb.render())
        self.assertEqual(coverage_cells([("s", rec)], [native]).uncovered,
                         ((SCH_D, YEAR, "8", "nothing"),))


class RegistryControls(unittest.TestCase):

    def test_a_form_both_pending_and_declared_is_caught(self):
        with unittest.mock.patch.dict(registry._DECLARATIONS,
                                      {(SCH_D, YEAR): SCH_D_DECL}):
            problems = pending.registry_problems()
        self.assertTrue(any("sch_d_540" in p and "pending" in p
                            for p in problems), problems)

    def test_a_declared_form_with_work_in_progress_is_caught(self):
        with unittest.mock.patch.object(
                registry, "WORK_IN_PROGRESS",
                {(SCH_D, YEAR): ("12b",)}):
            self.assertTrue(pending.registry_problems())

    def test_the_live_registry_has_no_problems(self):
        self.assertEqual(pending.registry_problems(), [])
