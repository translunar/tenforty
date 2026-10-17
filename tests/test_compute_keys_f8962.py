"""Form 8962: every printed value comes from the computation (ruling A3).

Box 4c ("Other 48 states and DC" poverty table) was a mapping derivation
returning the constant on-state "/3". It becomes a compute key,
`f8962_line_4c_other48` (True), emitted by forms.f8962.compute at the line 4
poverty-table choice it attests to (line 4 prices the 48-states-and-DC
table, the only one tenforty models): a future Alaska / Hawaii table or
refusal changes both together. The mapping only translates the bool to the
box's /3 on-state, as it does the 2021 unemployment box.

Before-values (tests/fixtures/compute_keys_f8962_before.json) were captured
once from the merge-commit tree d92773e: for every BATTERIES scenario the
emit manifest lists as emitting Form 8962 (21 rows, every year 2021-2025),
the pre-move derivation's output; plus a no-1095-A row every year
(spine_battery/owes_tax), on which the form is not emitted and no record
carries the key. The capture asserted that coverage.
"""
import ast
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.forms import f8962 as form_f8962
from tenforty.mappings import pdf_f8962
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.verification import emit_manifest as em
from tenforty.verification.batteries import BATTERIES

_BEFORE = Path(__file__).parent / "fixtures" / "compute_keys_f8962_before.json"
_YEARS = (2021, 2022, 2023, 2024, 2025)
KEY = "f8962_line_4c_other48"
BOX_4C = "topmostSubform[0].Page1[0].c1_2[2]"


def _emits(row_ids):
    """row id -> EmitResult for the named BATTERIES rows."""
    tmp = Path(tempfile.mkdtemp())
    out = {}
    for battery in BATTERIES:
        for name, year, build in battery.scenarios():
            rid = em.row_id(battery.name, name, year)
            if rid in row_ids:
                out[rid] = em.emit(battery, build(), tmp / rid.replace("/", "__"))
    return out


class _Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = json.loads(_BEFORE.read_text())
        cls.results = _emits(set(cls.before["emitted"])
                             | set(cls.before["not_emitted"]))

    def f8962_records(self, rid):
        return [r for r in self.results[rid].record
                if r.form == ("federal", "f8962")]


class NewKeysMatchOldDerivationTests(_Rows):
    """Box 4c on every emitted 8962 prints what the pre-move derivation
    produced."""

    def test_box_4c_prints_its_before_value(self):
        for rid, cells in sorted(self.before["emitted"].items()):
            with self.subTest(row=rid):
                (record,) = self.f8962_records(rid)
                field = PdfReader(str(record.pdf_path)).get_fields()[BOX_4C]
                self.assertEqual(str(field.get("/V")), cells[BOX_4C])

    def test_every_row_is_covered(self):
        self.assertEqual(len(self.before["emitted"]), 21)
        self.assertEqual({rid.rsplit("/", 1)[1] for rid in self.before["emitted"]},
                         {str(y) for y in _YEARS})
        self.assertEqual(len(self.before["not_emitted"]), len(_YEARS))


class ModeledScopePinTests(_Rows):
    """The key is True on every emitted 8962 and absent where 8962 is not
    computed (the reachable negative)."""

    def test_every_emitted_8962_carries_the_key_true(self):
        for rid in sorted(self.before["emitted"]):
            with self.subTest(row=rid):
                (record,) = self.f8962_records(rid)
                self.assertIs(record.values.get(KEY), True)

    def test_no_8962_row_has_no_form_and_no_key(self):
        for rid, row in sorted(self.before["not_emitted"].items()):
            with self.subTest(row=rid):
                self.assertEqual(row, {"f8962_emitted": False,
                                       "key_in_any_record": False})
                self.assertEqual(self.f8962_records(rid), [])
                self.assertFalse(any(KEY in r.values
                                     for r in self.results[rid].record))


class KeyComesFromTheTableChoiceTests(unittest.TestCase):
    """Provenance (ruling A3): the key is set right after line 4 prices the
    poverty table, in forms.f8962.compute, not as a free-standing constant."""

    def test_key_is_assigned_immediately_after_the_line_4_table_choice(self):
        tree = ast.parse(inspect.getsource(form_f8962.compute))
        body = tree.body[0].body
        targets = [
            (i, stmt) for i, stmt in enumerate(body)
            if isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "line_4"
                    for t in stmt.targets)]
        self.assertEqual(len(targets), 1)
        i, line_4 = targets[0]
        self.assertIn("fpl_for_family_size", ast.unparse(line_4.value))
        following = body[i + 1]
        self.assertIsInstance(following, ast.Assign)
        self.assertEqual([ast.unparse(t) for t in following.targets],
                         ["line_4c_other48"])
        self.assertIs(following.value.value, True)
        # ... and the result dict carries it under the approved key.
        result_keys = [ast.unparse(k) for node in ast.walk(tree)
                       if isinstance(node, ast.Dict)
                       for k in node.keys if k is not None]
        self.assertIn(repr(KEY), result_keys)


class MappingHasNoArithmeticTests(unittest.TestCase):
    """No derivation remains; box 4c is a bool translated to its /3
    on-state, every year; the module holds no lambda."""

    def test_no_derivations_remain(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(PdfF8962.get_derivations(year), {})

    def test_box_4c_translates_the_key(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    PdfF8962.get_mapping(year)["scalars"][KEY], BOX_4C)
                self.assertEqual(PdfF8962.get_checkbox_states(year)[KEY], "/3")

    def test_module_has_no_lambda(self):
        tree = ast.parse(inspect.getsource(pdf_f8962))
        self.assertEqual(
            [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Lambda)], [])


if __name__ == "__main__":
    unittest.main()
