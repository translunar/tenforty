"""Schedule C: every printed value comes from the computation (ruling A1).

The mapping's two constant check marks -- line F accounting method "Cash"
and line G "materially participate: Yes" -- were derivations returning a
fixed on-state. They become compute keys (ruling A3):
`sch_c_line_f_cash_method` and `sch_c_line_g_material_participation`,
True for every business tenforty models, and the mapping only translates
them to their on-states. Line 32a was already a translation of a compute
key and stays. Every printed amount was already a 1:1 compute-key binding.

The moved values are constants of tenforty's modeled scope; the workbook
computes no such cell, so there is no oracle test for them (an oracle test
asserting nothing would be ceremony). The invariants are the before-values
below and the fill chokepoint's byte-identical emit fixture
(run_full_return_sch_c_2025).
"""
import ast
import inspect
import json
import unittest
from pathlib import Path

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import sch_c
from tenforty.mappings import pdf_sch_c
from tenforty.mappings.pdf_sch_c import PdfSchC
from tests.fixtures.sch_c_battery import SCENARIOS

_BEFORE = Path(__file__).parent / "fixtures" / "compute_keys_sch_c_before.json"
_NEW_KEYS = ("sch_c_line_f_cash_method", "sch_c_line_g_material_participation")


def _battery_businesses():
    """(scenario, year, index, computed per-business values) for every
    Schedule C battery scenario x Schedule C family year."""
    for name, build in sorted(SCENARIOS.items()):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            scn = build(year)
            for i, values in enumerate(
                    sch_c.compute(scn, upstream={})["sch_c_businesses"]):
                yield name, year, i, values


class NewKeysMatchOldDerivationTests(unittest.TestCase):
    """The marks the mapping prints, now from compute keys, equal what the
    pre-move derivations produced (captured once from the merge-commit
    tree, 3fd56fe: values the code produced, not hand-derived)."""

    def test_printed_marks_equal_the_pre_move_derivations(self):
        # The marks now print as bool keys through checkbox states (sch_c
        # declaration lane, ruling b2): read them off the real translation
        # path, at the boxes the pre-move capture recorded.
        before = json.loads(_BEFORE.read_text())
        seen = 0
        for name, year, i, values in _battery_businesses():
            expected = before[name][str(year)][i]
            printed = PdfFiller.resolve_fields(
                PdfSchC.get_mapping(year), values,
                checkbox_states=PdfSchC.get_checkbox_states(year))
            with self.subTest(scenario=name, year=year, business=i):
                self.assertEqual({path: printed.get(path) for path in expected},
                                 expected)
                seen += 1
        self.assertEqual(seen, sum(len(b) for y in before.values()
                                   for b in y.values()))


class ModeledScopePinTests(unittest.TestCase):
    """Both scope constants are emitted, True, for every business."""

    def test_every_battery_business_emits_both_keys_true(self):
        for name, year, i, values in _battery_businesses():
            with self.subTest(scenario=name, year=year, business=i):
                for key in _NEW_KEYS:
                    self.assertIs(values.get(key), True, key)


class MappingHasNoArithmeticTests(unittest.TestCase):
    """Every remaining Schedule C derivation is an approved TRANSLATION: it
    reads a compute key and maps it to an on-state. None returns a constant
    (ruling A3) and none does arithmetic or comparison (ruling A1)."""

    APPROVED_TRANSLATIONS = {
        "topmostSubform[0].Page1[0].c1_1[0]": "sch_c_line_f_cash_method",
        "topmostSubform[0].Page1[0].c1_2[0]":
            "sch_c_line_g_material_participation",
        "topmostSubform[0].Page1[0].c1_7[0]":
            "sch_c_line_32a_all_investment_at_risk",
    }

    def _lambdas(self):
        tree = ast.parse(inspect.getsource(pdf_sch_c))
        for node in ast.walk(tree):
            if (isinstance(node, ast.AnnAssign)
                    and getattr(node.target, "id", None) == "_DERIVATIONS"):
                for key, value in zip(node.value.keys, node.value.values):
                    yield ast.unparse(key), value

    def test_each_derivation_translates_its_approved_compute_key(self):
        # The approved translations are bool keys mapped to their boxes with
        # on-states (sch_c declaration lane, ruling b2); no derivation and
        # no lambda remains.
        on_states = {"sch_c_line_f_cash_method": "/1",
                     "sch_c_line_g_material_participation": "/Yes",
                     "sch_c_line_32a_all_investment_at_risk": "/1"}
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                self.assertEqual(PdfSchC.get_derivations(year), {})
                mapping = PdfSchC.get_mapping(year)
                states = PdfSchC.get_checkbox_states(year)
                for path, key in sorted(self.APPROVED_TRANSLATIONS.items()):
                    self.assertEqual(mapping[key], path)
                    self.assertEqual(states[key], on_states[key])
        tree = ast.parse(inspect.getsource(pdf_sch_c))
        self.assertEqual(
            [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Lambda)],
            [])
        found = 0
        for path_src, fn in self._lambdas():
            found += 1
            body = fn.body
            with self.subTest(derivation=path_src):
                self.assertIsInstance(fn, ast.Lambda)
                self.assertNotIsInstance(body, ast.Constant)
                read = [n.args[0].value for n in ast.walk(body)
                        if isinstance(n, ast.Call)
                        and getattr(n.func, "attr", None) == "get"]
                path = next(p for p in self.APPROVED_TRANSLATIONS
                            if p.endswith(path_src.split('.')[-1].strip("'\"")))
                self.assertEqual(read, [self.APPROVED_TRANSLATIONS[path]])
                for n in ast.walk(body):
                    self.assertNotIsInstance(n, (ast.BinOp, ast.Compare,
                                                 ast.AugAssign))
        self.assertEqual(found, 0)


if __name__ == "__main__":
    unittest.main()
