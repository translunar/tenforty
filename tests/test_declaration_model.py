# tests/test_declaration_model.py
"""Emit declarations (emit-verification harness spec §2.1; rulings A2, A5,
single_state): the declaration types, year derivation, repeat expansion,
validation against the official inventory, the registry, and the
independence rule (no declaration module imports tenforty's mappings,
computations or orchestrator)."""
import ast
import dataclasses
import unittest
from pathlib import Path

import tenforty.declarations as declarations_pkg
from tenforty.declarations import anchors, registry
from tenforty.declarations.anchors import (
    COLUMN_PT,
    LABEL_GAP_PT,
    NEXT_ROW_PT,
    ROW_PT,
    WRAP_PT,
    FieldRelation,
    LabelRelation,
    NearField,
    NearLabel,
    RowLabel,
    Tooltip,
)
from tenforty.declarations.model import (
    DeclaredLine,
    FormDeclaration,
    Repeat,
    derive,
    expand,
)
from tenforty.declarations.validate import validate
from tenforty.verification.findings import Finding

F8995 = ("federal", "f8995")


def _line(line: str, key: str, section: str = "", **over) -> DeclaredLine:
    fields = dict(line=line, description=f"Line {line} text", key=key,
                  kind="amount", section=section)
    fields.update(over)
    return DeclaredLine(**fields)


def _decl(*lines: DeclaredLine, key=2025, not_printed=None,
          form=F8995) -> FormDeclaration:
    return FormDeclaration(form=form, key=key, lines=tuple(lines),
                           not_printed=dict(not_printed or {}))


BASE_2024 = _decl(
    _line("10", "f8995_line_10"),
    _line("11", "f8995_line_11"),
    _line("12", "f8995_line_12"),
    key=2024,
    not_printed={"f8995_scratch": "intermediate: feeds line 10"},
)


class TypesTests(unittest.TestCase):

    def test_everything_is_frozen(self):
        for obj in (BASE_2024, BASE_2024.lines[0], Repeat("i", max=3),
                    Tooltip("Line 3"), RowLabel("3"),
                    NearLabel("dependent", LabelRelation.RIGHT_OF),
                    NearField("12", FieldRelation.NEXT_ROW_BELOW),
                    Finding("s", "f", 2025, "1", "value", "m")):
            with self.subTest(obj=type(obj).__name__):
                self.assertTrue(dataclasses.is_dataclass(obj))
                field = dataclasses.fields(obj)[0].name
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(obj, field, getattr(obj, field))

    def test_declared_line_defaults(self):
        ln = _line("1", "k")
        self.assertEqual(
            (ln.section, ln.anchor, ln.mef_element, ln.scope, ln.group,
             ln.selects, ln.repeat, ln.single_state, ln.single_state_reason),
            ("", None, None, "NATIVE", None, None, None, None, None))

    def test_anchor_constants_and_enums(self):
        self.assertEqual((ROW_PT, COLUMN_PT, NEXT_ROW_PT, LABEL_GAP_PT,
                          WRAP_PT), (2, 5, 20, 12, 14))
        self.assertEqual({m.name for m in LabelRelation},
                         {"ON_ROW", "LEFT_OF", "RIGHT_OF", "AFTER_WRAPPED"})
        self.assertEqual({m.name for m in FieldRelation},
                         {"SAME_ROW_RIGHT_OF", "NEXT_ROW_BELOW"})
        self.assertEqual(set(anchors.Anchor.__args__),
                         {Tooltip, RowLabel, NearLabel, NearField})

    def test_repeat_sets_exactly_one_of_values_or_max(self):
        Repeat("col", values=("a", "b"))
        Repeat("i", max=14)
        for bad in (dict(), dict(values=("a",), max=3)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Repeat("i", **bad)


class DeriveTests(unittest.TestCase):

    def test_derive_applies_exactly_the_four_differences(self):
        added = _line("13", "f8995_line_13")
        d = derive(BASE_2024, 2025,
                   add=(added,),
                   drop=(("", "12"),),
                   relabel={("", "11"): "11a"},
                   rebind={("", "10"): "f8995_line_10_new"})
        self.assertEqual(d.form, F8995)
        self.assertEqual(d.key, 2025)
        self.assertEqual(
            [(ln.line, ln.key) for ln in d.lines],
            [("10", "f8995_line_10_new"), ("11a", "f8995_line_11"),
             ("13", "f8995_line_13")])
        # Everything else about the carried lines is unchanged.
        self.assertEqual(d.lines[1].description, BASE_2024.lines[1].description)
        self.assertEqual(dict(d.not_printed), dict(BASE_2024.not_printed))
        # The base is untouched.
        self.assertEqual([ln.line for ln in BASE_2024.lines], ["10", "11", "12"])

    def test_derive_with_no_changes_copies_lines(self):
        d = derive(BASE_2024, 2025)
        self.assertEqual(d.lines, BASE_2024.lines)
        self.assertEqual(d.key, 2025)

    def test_dropping_a_nonexistent_line_raises(self):
        with self.assertRaises(KeyError):
            derive(BASE_2024, 2025, drop=(("", "99"),))

    def test_relabel_or_rebind_of_a_nonexistent_line_raises(self):
        with self.assertRaises(KeyError):
            derive(BASE_2024, 2025, relabel={("Part I", "10"): "10a"})
        with self.assertRaises(KeyError):
            derive(BASE_2024, 2025, rebind={("", "77"): "k"})

    def test_section_is_part_of_the_line_identity(self):
        base = _decl(_line("1", "a_line_1", section="Part I"),
                     _line("1", "a_line_1_p2", section="Part II"), key=2024)
        d = derive(base, 2025, drop=(("Part II", "1"),))
        self.assertEqual([(ln.section, ln.key) for ln in d.lines],
                         [("Part I", "a_line_1")])


class ExpandTests(unittest.TestCase):

    def test_explicit_column_values_expand_to_one_line_each(self):
        decl = _decl(_line("3{col}", "sch_e_line_3_rents_{col}",
                           repeat=Repeat("col", values=("a", "b", "c"))),
                     form=("federal", "sch_e"))
        lines = expand(decl, {})
        self.assertEqual([(ln.line, ln.key) for ln in lines],
                         [("3a", "sch_e_line_3_rents_a"),
                          ("3b", "sch_e_line_3_rents_b"),
                          ("3c", "sch_e_line_3_rents_c")])
        self.assertTrue(all(ln.repeat is None for ln in lines))

    def test_numbered_rows_expand_only_to_the_rows_present(self):
        decl = _decl(_line("1{i}", "f8949_row_{i}_proceeds",
                           repeat=Repeat("i", max=14)),
                     form=("federal", "f8949"))
        values = {f"f8949_row_{i}_proceeds": 100.0 * i for i in (1, 2, 3)}
        lines = expand(decl, values)
        self.assertEqual([ln.key for ln in lines],
                         ["f8949_row_1_proceeds", "f8949_row_2_proceeds",
                          "f8949_row_3_proceeds"])
        self.assertEqual([ln.line for ln in lines], ["11", "12", "13"])

    def test_rows_beyond_max_are_not_expanded(self):
        decl = _decl(_line("{i}", "row_{i}", repeat=Repeat("i", max=2)))
        lines = expand(decl, {"row_1": 1, "row_2": 2, "row_3": 3})
        self.assertEqual([ln.key for ln in lines], ["row_1", "row_2"])

    def test_non_repeat_lines_pass_through_in_order(self):
        decl = _decl(_line("1", "k1"),
                     _line("{i}", "row_{i}", repeat=Repeat("i", max=5)),
                     _line("9", "k9"))
        lines = expand(decl, {"row_2": 0})
        self.assertEqual([ln.key for ln in lines], ["k1", "row_2", "k9"])


class ValidateTests(unittest.TestCase):
    """One test per rule. The inventory vehicle is the real f8995 2025
    inventory (tenforty/declarations/inventories/f8995_2025.json)."""

    def _checks(self, decl):
        return sorted(f.check for f in validate(decl))

    def test_a_valid_declaration_has_no_findings(self):
        self.assertEqual(validate(_decl(_line("10", "f8995_line_10"),
                                        _line("15", "f8995_line_15"))), [])

    def test_line_absent_from_the_inventory(self):
        findings = validate(_decl(_line("10", "f8995_line_10"),
                                  _line("99", "f8995_line_99")))
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("99", "inventory")])
        self.assertEqual(findings[0].form, "federal/f8995")
        self.assertEqual(findings[0].year, 2025)

    def test_section_mismatch_is_absent_from_the_inventory(self):
        findings = validate(_decl(_line("10", "k", section="Part IX")))
        self.assertEqual([f.check for f in findings], ["inventory"])

    def test_repeat_lines_are_not_checked_against_the_inventory(self):
        self.assertEqual(validate(_decl(_line(
            "{i}", "row_{i}", repeat=Repeat("i", max=3)))), [])

    def test_selects_without_group(self):
        self.assertEqual(self._checks(_decl(
            _line("10", "f8995_choice", kind="checkbox", selects="yes"))),
            ["group"])

    def test_group_lines_must_share_one_key(self):
        self.assertEqual(self._checks(_decl(
            _line("10", "f8995_choice", kind="checkbox", group="g",
                  selects="a"),
            _line("11", "f8995_other", kind="checkbox", group="g",
                  selects="b"))), ["group"])
        self.assertEqual(validate(_decl(
            _line("10", "f8995_choice", kind="checkbox", group="g",
                  selects="a"),
            _line("11", "f8995_choice", kind="checkbox", group="g",
                  selects="b"))), [])

    def test_single_state_needs_a_reason(self):
        self.assertEqual(self._checks(_decl(
            _line("10", "f8995_line_10", single_state="value"))),
            ["single_state"])
        self.assertEqual(self._checks(_decl(
            _line("10", "f8995_line_10", single_state="value",
                  single_state_reason="   "))), ["single_state"])
        self.assertEqual(validate(_decl(
            _line("10", "f8995_line_10", single_state="nothing",
                  single_state_reason="no battery scenario reaches the "
                                      "refusal-free branch"))), [])

    def test_not_printed_reasons_need_a_known_tag(self):
        self.assertEqual(self._checks(_decl(
            _line("10", "f8995_line_10"),
            not_printed={"f8995_tmp": "because"})), ["not_printed"])
        for tag in ("intermediate:", "presentation-only:", "diagnostic:"):
            with self.subTest(tag=tag):
                self.assertEqual(validate(_decl(
                    _line("10", "f8995_line_10"),
                    not_printed={"f8995_tmp": f"{tag} feeds line 10"})), [])

    # "other-year:" (sch_2 lane ruling): a key whose printed line exists only
    # in another year's layout. Self-verifying: accepted only when the same
    # key is BOUND in another year of the same form (``siblings``), so the
    # claim cannot go silently false.
    _OTHER_YEAR = {"f8995_line_11": "other-year: prints on line 11 only in "
                                    "2024"}

    def test_other_year_is_accepted_when_another_year_binds_the_key(self):
        sibling = _decl(_line("11", "f8995_line_11"), key=2024)
        self.assertEqual(validate(_decl(
            _line("10", "f8995_line_10"), not_printed=self._OTHER_YEAR),
            siblings=[sibling]), [])

    def test_other_year_bound_in_no_other_year_is_refused(self):
        unbound = _decl(_line("10", "f8995_line_10"), key=2024)
        same_year = _decl(_line("11", "f8995_line_11"), key=2025)
        other_form = _decl(_line("11", "f8995_line_11"), key=2024,
                           form=("federal", "sch_2"))
        for name, siblings in (("no siblings", []), ("unbound", [unbound]),
                               ("same year", [same_year]),
                               ("other form", [other_form])):
            with self.subTest(siblings=name):
                findings = validate(_decl(
                    _line("10", "f8995_line_10"),
                    not_printed=self._OTHER_YEAR), siblings=siblings)
                self.assertEqual([(f.line, f.check) for f in findings],
                                 [("f8995_line_11", "not_printed")])
                self.assertIn("bound in no other year", findings[0].message)

    def test_the_declarations_own_binding_does_not_verify_other_year(self):
        # Bound in THIS year is not bound in another year.
        findings = validate(_decl(
            _line("10", "f8995_line_10"), _line("11", "f8995_line_11"),
            not_printed=self._OTHER_YEAR))
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("f8995_line_11", "not_printed")])

    def test_a_line_declared_twice(self):
        findings = validate(_decl(_line("10", "f8995_line_10"),
                                  _line("10", "f8995_line_10b")))
        self.assertEqual([(f.line, f.check) for f in findings],
                         [("10", "duplicate")])

    def test_same_label_in_two_sections_is_not_a_duplicate(self):
        decl = _decl(_line("1", "a", section="Part I"),
                     _line("1", "b", section="Part II"),
                     form=("federal", "f8949"), key=2024)
        self.assertNotIn("duplicate", self._checks(decl))

    def test_validate_reads_only_the_inventory_model_and_findings(self):
        import tenforty.declarations.validate as module
        tree = ast.parse(Path(module.__file__).read_text())
        imported = {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)}
        imported |= {a.name for node in ast.walk(tree)
                     if isinstance(node, ast.Import) for a in node.names}
        self.assertEqual(
            {m for m in imported if m.startswith("tenforty")},
            {"tenforty.declarations", "tenforty.declarations.model",
             "tenforty.verification.findings"})


class RegistryTests(unittest.TestCase):

    def test_undeclared_form_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            registry.for_form(("federal", "no_such_form"), 2025)

    def test_declared_forms_is_a_frozenset(self):
        self.assertIsInstance(registry.declared_forms(), frozenset)

    def test_work_in_progress_is_empty_to_merge(self):
        # Spec §10 D2: may be non-empty on a lane branch, never on merge.
        self.assertEqual(dict(registry.WORK_IN_PROGRESS), {})

    def test_every_registered_declaration_validates_clean(self):
        for form, key in sorted(registry.declared_forms(), key=str):
            with self.subTest(form=form, key=key):
                self.assertEqual(validate(registry.for_form(form, key)), [])


class NoMappingImportTests(unittest.TestCase):
    """The independence rule, structurally, for EVERY module under
    tenforty/declarations/ (spec §4.3)."""

    FORBIDDEN = ("tenforty.mappings", "tenforty.forms", "tenforty.orchestrator")

    def _modules(self):
        root = Path(declarations_pkg.__file__).parent
        return sorted(root.rglob("*.py"))

    def test_the_scan_covers_this_lanes_modules(self):
        names = {p.name for p in self._modules()}
        self.assertLessEqual(
            {"model.py", "registry.py", "validate.py", "anchors.py",
             "inventory.py", "stylesheet.py", "manifest.py"}, names)

    def test_no_declarations_module_imports_mappings_forms_or_orchestrator(self):
        for path in self._modules():
            with self.subTest(module=str(path.relative_to(
                    Path(declarations_pkg.__file__).parent))):
                imported = []
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.Import):
                        imported += [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        base = node.module or ""
                        imported.append(base)
                        imported += [f"{base}.{a.name}" for a in node.names]
                forbidden = [n for n in imported if any(
                    n == p or n.startswith(p + ".") for p in self.FORBIDDEN)]
                self.assertEqual(forbidden, [])
