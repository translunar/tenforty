# tests/test_runtime_gate.py
"""The runtime gate (emit-verification harness spec §8, §10 D3; rulings
Q0-Q6, 2026-10-17).

Inside ``fill()``, before a declared form's PDF is written, every declared
line whose key has a value must reach a field in what is about to print
(rule 1), and a line printed by an aggregation cell needs every constituent
(rule 2). A failure refuses the emit with ``IncompleteEmitError``; no file
is written. Forms on ``PENDING_DECLARATIONS`` emit exactly as today; a form
neither declared nor pending refuses (fail closed).

The vehicle is an in-memory declaration over the real Form 8582 2024
template and a hand-built FillSpec: no production declaration exists yet.
Every refusal species has a test proving it fires on reachable input.
"""
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tenforty.declarations import registry
from tenforty.declarations.model import (
    DeclaredLine,
    FormDeclaration,
    Repeat,
)
from tenforty.filing import pdf as pdf_module
from tenforty.filing.pdf import PdfFiller, apply_blank_when_zero
from tenforty.mappings.catalog import CATALOG
from tenforty.verification import gate, pending
from tenforty.verification.fill import FillSpec, fill
from tenforty.verification.findings import Finding
from tenforty.verification.gate import IncompleteEmitError, missing_lines
from tenforty.verification.record import EmitRecorder
from tests.helpers import REPO_ROOT

F8582 = ("federal", "f8582")
YEAR = 2024
TEMPLATE = REPO_ROOT / "pdfs" / "federal" / str(YEAR) / "f8582.pdf"
F_1A = "topmostSubform[0].Page1[0].f1_3[0]"
F_1B = "topmostSubform[0].Page1[0].f1_4[0]"
F_1C = "topmostSubform[0].Page1[0].f1_5[0]"
F_1D = "topmostSubform[0].Page1[0].f1_6[0]"
K_1A = "f8582_line_1a_activities_with_income"
K_1B = "f8582_line_1b_activities_with_loss"
K_1C = "f8582_line_1c_prior_year_unallowed_loss"
K_1D = "f8582_line_1d_combine"
TEXT_1A = "Activities with net income"


def _line(line, key, description, **over):
    fields = dict(line=line, description=description, key=key,
                  kind="amount", section="Part I")
    fields.update(over)
    return DeclaredLine(**fields)


def _decl(*lines):
    return FormDeclaration(form=F8582, key=YEAR, lines=tuple(lines),
                           not_printed={})


DECL = _decl(_line("1a", K_1A, TEXT_1A),
             _line("1b", K_1B, "Activities with net loss"))

# A spec that prints 1b but NOT 1a: rule 1's reachable failure.
SPEC_MISSING_1A = FillSpec(kind="flat", mapping={K_1B: F_1B})
SPEC_FULL = FillSpec(kind="flat", mapping={K_1A: F_1A, K_1B: F_1B})


def _payload(spec, values):
    return gate.final_payload(spec, values)


class _Declared(unittest.TestCase):
    """f8582 2024 declared (in memory) and NOT pending for the test."""

    decl = DECL

    def setUp(self):
        p1 = unittest.mock.patch.dict(registry._DECLARATIONS,
                                      {(F8582, YEAR): self.decl})
        without = {k: v for k, v in pending.PENDING_DECLARATIONS.items()
                   if k != F8582}
        p2 = unittest.mock.patch.object(pending, "PENDING_DECLARATIONS",
                                        without)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)


class GateRuleOneTests(_Declared):

    def test_valued_line_with_no_printing_field_is_a_finding(self):
        values = {K_1A: 1200.0, K_1B: -300.0}
        findings = missing_lines(DECL, values, _payload(SPEC_MISSING_1A, values),
                                 SPEC_MISSING_1A)
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("1a", "gate")])
        self.assertIsInstance(findings[0], Finding)

    def test_check_raises_naming_form_year_label_and_text(self):
        values = {K_1A: 1200.0, K_1B: -300.0}
        with self.assertRaises(IncompleteEmitError) as cm:
            gate.check(F8582, YEAR, SPEC_MISSING_1A, values)
        msg = str(cm.exception)
        for part in ("f8582", "2024", "1a", TEXT_1A):
            self.assertIn(part, msg)
        self.assertIsInstance(cm.exception, ValueError)

    def test_field_in_mapping_but_dropped_from_payload_is_a_finding(self):
        # The key is mapped, but blank_when_zero drops its "0": a computed
        # zero that would print blank.
        spec = FillSpec(kind="flat", mapping={K_1A: F_1A, K_1B: F_1B},
                        blank_when_zero=frozenset({F_1A}))
        values = {K_1A: 0.0, K_1B: -300.0}
        findings = missing_lines(DECL, values, _payload(spec, values), spec)
        self.assertEqual([f.line for f in findings], ["1a"])

    def test_zero_with_its_field_present_is_no_finding(self):
        values = {K_1A: 0.0, K_1B: -300.0}
        self.assertEqual(missing_lines(DECL, values,
                                       _payload(SPEC_FULL, values),
                                       SPEC_FULL), [])
        gate.check(F8582, YEAR, SPEC_FULL, values)

    def test_none_or_absent_key_is_no_finding(self):
        for values in ({K_1A: None, K_1B: -300.0}, {K_1B: -300.0}):
            with self.subTest(values=values):
                self.assertEqual(
                    missing_lines(DECL, values,
                                  _payload(SPEC_MISSING_1A, values),
                                  SPEC_MISSING_1A), [])

    def test_all_findings_are_listed_at_once(self):
        spec = FillSpec(kind="flat", mapping={})
        values = {K_1A: 1.0, K_1B: 2.0}
        with self.assertRaises(IncompleteEmitError) as cm:
            gate.check(F8582, YEAR, spec, values)
        self.assertIn("1a", str(cm.exception))
        self.assertIn("1b", str(cm.exception))


class GateRuleTwoTests(_Declared):
    """A declared line printed by an aggregation cell needs every
    constituent; PdfFiller would otherwise print a partial sum."""

    decl = _decl(_line("1d", K_1D, "Combine lines 1a, 1b, and 1c"))
    SPEC = FillSpec(kind="flat", mapping={K_1D: F_1D},
                    aggregations={F_1D: (K_1A, K_1B, K_1C)})

    def test_missing_constituent_is_named(self):
        values = {K_1D: 900.0, K_1A: 1200.0, K_1B: -300.0, K_1C: None}
        payload = _payload(self.SPEC, values)
        self.assertIn(F_1D, payload)  # PdfFiller WOULD print a partial sum
        findings = missing_lines(self.decl, values, payload, self.SPEC)
        self.assertEqual(len(findings), 1)
        self.assertIn(K_1C, findings[0].message)
        with self.assertRaises(IncompleteEmitError) as cm:
            gate.check(F8582, YEAR, self.SPEC, values)
        self.assertIn(K_1C, str(cm.exception))

    def test_complete_constituents_pass(self):
        values = {K_1D: 900.0, K_1A: 1200.0, K_1B: -300.0, K_1C: 0.0}
        self.assertEqual(missing_lines(self.decl, values,
                                       _payload(self.SPEC, values),
                                       self.SPEC), [])


class OptionGroupPresenceTests(_Declared):
    """Q5: only the line whose `selects` equals the key's value must be
    present; exclusivity is the check-suite's."""

    decl = _decl(
        _line("1a", "choice", TEXT_1A, kind="checkbox", group="g",
              selects="yes"),
        _line("1b", "choice", "Activities with net loss", kind="checkbox",
              group="g", selects="no"))

    def test_selected_line_absent_is_a_finding(self):
        spec = FillSpec(kind="flat", mapping={})
        values = {"choice": "yes"}
        findings = missing_lines(self.decl, values,
                                 _payload(spec, values), spec)
        self.assertEqual([f.line for f in findings], ["1a"])

    def test_unselected_line_is_not_required(self):
        spec = FillSpec(kind="flat", mapping={"choice": F_1A})
        values = {"choice": "yes"}
        self.assertEqual(missing_lines(self.decl, values,
                                       _payload(spec, values), spec), [])


class ScopeAndRepeatTests(_Declared):

    def test_workbook_scope_lines_are_skipped(self):
        decl = _decl(_line("1a", K_1A, TEXT_1A, scope="WORKBOOK"))
        values = {K_1A: 5.0}
        spec = FillSpec(kind="flat", mapping={})
        self.assertEqual(missing_lines(decl, values,
                                       _payload(spec, values), spec), [])

    def test_repeat_lines_check_each_expanded_row(self):
        decl = _decl(_line("{i}", "row_{i}", "Row", repeat=Repeat("i", max=3)))
        spec = FillSpec(kind="flat", mapping={"row_1": F_1A})
        values = {"row_1": 1.0, "row_2": 2.0}
        findings = missing_lines(decl, values, _payload(spec, values), spec)
        self.assertEqual([f.line for f in findings], ["2"])


class PendingInactiveTests(unittest.TestCase):
    """D3: the gate is inactive for pending forms. The SAME values object
    refuses once the form leaves the pending list (reachable negative
    space)."""

    def test_pending_returns_and_non_pending_refuses(self):
        values = {K_1A: 1200.0, K_1B: -300.0}
        with unittest.mock.patch.dict(registry._DECLARATIONS,
                                      {(F8582, YEAR): DECL}):
            self.assertIn(F8582, pending.PENDING_DECLARATIONS)
            gate.check(F8582, YEAR, SPEC_MISSING_1A, values)  # returns
            without = {k: v for k, v in pending.PENDING_DECLARATIONS.items()
                       if k != F8582}
            with unittest.mock.patch.object(pending, "PENDING_DECLARATIONS",
                                            without):
                with self.assertRaises(IncompleteEmitError):
                    gate.check(F8582, YEAR, SPEC_MISSING_1A, values)


class UndeclaredNotPendingTests(unittest.TestCase):
    """Q1: a form neither declared nor pending refuses (fail closed)."""

    def test_undeclared_and_not_pending_refuses_with_remedy(self):
        without = {k: v for k, v in pending.PENDING_DECLARATIONS.items()
                   if k != F8582}
        with unittest.mock.patch.object(pending, "PENDING_DECLARATIONS",
                                        without):
            with self.assertRaises(IncompleteEmitError) as cm:
                gate.check(F8582, YEAR, SPEC_FULL, {K_1A: 1.0})
        msg = str(cm.exception)
        self.assertIn("f8582", msg)
        self.assertIn("PENDING_DECLARATIONS", msg)


class RefuseBeforeWriteTests(_Declared):

    def test_refusing_form_leaves_no_output_file(self):
        out = Path(tempfile.mkdtemp()) / "f8582_2024.pdf"
        recorder = EmitRecorder()
        values = {K_1A: 1200.0, K_1B: -300.0}
        with self.assertRaises(IncompleteEmitError):
            fill(F8582, YEAR, SPEC_MISSING_1A, TEMPLATE, out, values,
                 recorder)
        self.assertFalse(out.exists())
        self.assertEqual(len(recorder.record()), 0)

    def test_passing_form_is_written_and_recorded(self):
        out = Path(tempfile.mkdtemp()) / "f8582_2024.pdf"
        recorder = EmitRecorder()
        values = {K_1A: 1200.0, K_1B: -300.0}
        fill(F8582, YEAR, SPEC_FULL, TEMPLATE, out, values, recorder)
        self.assertTrue(out.exists())
        self.assertEqual(len(recorder.record()), 1)


class PendingRegistryTests(unittest.TestCase):
    """The pending list is exact in BOTH directions: every form fill() can
    be called with is pending or declared, and every pending entry is a form
    fill() can still be called with (a stale entry for a form that can no
    longer be filled fails). A form both declared and pending fails too."""

    FILL_UNIVERSE = (set(CATALOG) | {("federal", "f1040x"),
                                     ("california", "schedule_x"),
                                     ("federal", "f3115")})

    def test_fill_universe_is_exactly_pending_or_declared(self):
        declared = {form for form, _key in registry.declared_forms()}
        self.assertEqual(set(pending.PENDING_DECLARATIONS) | declared,
                         self.FILL_UNIVERSE)

    def test_no_form_is_both_declared_and_pending(self):
        declared = {form for form, _key in registry.declared_forms()}
        self.assertEqual(declared & set(pending.PENDING_DECLARATIONS), set())

    def test_every_pending_entry_has_the_burn_down_reason(self):
        for form, reason in pending.PENDING_DECLARATIONS.items():
            with self.subTest(form=form):
                self.assertTrue(reason.startswith("DECLARATION PENDING:"))

    def test_a_stale_both_declared_and_pending_entry_is_caught(self):
        with unittest.mock.patch.dict(registry._DECLARATIONS,
                                      {(F8582, YEAR): DECL}):
            declared = {form for form, _key in registry.declared_forms()}
            self.assertIn(F8582,
                          declared & set(pending.PENDING_DECLARATIONS))


class BlankWhenZeroHelperTests(unittest.TestCase):
    """The blank_when_zero drop lives in one helper that both PdfFiller.fill
    and the gate's final payload use."""

    def test_drops_zero_and_negative_zero_only(self):
        fields = {"A": "0", "B": "-0", "C": "5", "D": "0"}
        self.assertEqual(apply_blank_when_zero(fields, {"A", "B", "C"}),
                         {"C": "5", "D": "0"})

    def test_pdf_filler_fill_uses_the_helper(self):
        with unittest.mock.patch.object(
                pdf_module, "apply_blank_when_zero",
                wraps=pdf_module.apply_blank_when_zero) as spy:
            out = Path(tempfile.mkdtemp()) / "x.pdf"
            PdfFiller().fill(template_path=TEMPLATE, output_path=out,
                             field_mapping={K_1A: F_1A}, values={K_1A: 0.0},
                             blank_when_zero={F_1A})
        spy.assert_called_once()
