"""Structural proof that the resolver is the only read path to an activity's
depreciation.

An AST scan of every module under ``tenforty/``: no ``.depreciation``
attribute read, and no ``"depreciation"`` string constant (an expense-field
tuple member, a ``getattr`` name), anywhere outside the allowlist below.
Each allowlisted site is named with the reason it is not an amount reader.

A new reader that goes around the resolver shows up here as an unlisted site.
"""

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).parent.parent / "tenforty"

# (module path relative to tenforty/, enclosing scope) -> why it is allowed.
ALLOWED_ATTRIBUTE_READS: dict[tuple[str, str], str] = {
    ("forms/depreciation/resolver.py", "resolve"):
        "the one door: stated mode returns the activity's scalar",
    ("forms/depreciation/resolver.py", "stated_mode_activity_labels"):
        "inside the door, truthiness only: which activities are in stated "
        "mode, for the mid-quarter test's unverifiable-totals refusal",
    ("attestations.py", "_dual_source_activities"):
        "shape rule, truthiness only: assets AND a stated scalar refuse",
    ("attestations.py", "_unacknowledged_stated_figures"):
        "shape rule, truthiness only: a stated scalar needs its "
        "acknowledgment",
    ("forms/f1120s.py", "_compute_deductions.lines"):
        "Form 1120-S line 14 -- SCorpDeductions, a stated aggregate that is "
        "deliberately outside asset integration",
}

ALLOWED_STRING_CONSTANTS: dict[tuple[str, str], str] = {
    ("scenario.py", "_SCHEDULE_C_AMOUNT_FIELDS"):
        "negative-amount refusal at load: a sign check, not an amount read",
    ("scenario.py", "_load_deductions"):
        "s_corp_return.deductions YAML key (Form 1120-S line 14)",
}


def _scan() -> tuple[set, set]:
    """Every (module, scope) holding a `.depreciation` attribute read, and
    every (module, scope) holding a "depreciation" string constant."""
    attribute_reads: set[tuple[str, str]] = set()
    string_constants: set[tuple[str, str]] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        module = path.relative_to(PACKAGE).as_posix()
        tree = ast.parse(path.read_text())
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        def scope_of(node: ast.AST) -> str:
            names: list[str] = []
            while node in parents:
                node = parents[node]
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.append(node.name)
                elif (isinstance(node, ast.Assign)
                      and isinstance(node.targets[0], ast.Name)):
                    names.append(node.targets[0].id)
                elif (isinstance(node, ast.AnnAssign)
                      and isinstance(node.target, ast.Name)):
                    names.append(node.target.id)
            return ".".join(reversed(names)) or "<module>"

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "depreciation":
                attribute_reads.add((module, scope_of(node)))
            elif (isinstance(node, ast.Constant)
                  and node.value == "depreciation"):
                string_constants.add((module, scope_of(node)))
    return attribute_reads, string_constants


class SingleReadPathTests(unittest.TestCase):
    def test_no_attribute_read_outside_the_allowlist(self):
        attribute_reads, _ = _scan()
        self.assertEqual(
            attribute_reads - set(ALLOWED_ATTRIBUTE_READS), set(),
            "`.depreciation` is read outside the resolver")

    def test_no_string_constant_outside_the_allowlist(self):
        _, string_constants = _scan()
        self.assertEqual(
            string_constants - set(ALLOWED_STRING_CONSTANTS), set(),
            '"depreciation" appears in a field tuple / getattr outside the '
            "resolver")

    def test_allowlists_carry_no_stale_entries(self):
        """An allowlisted site that no longer exists is removed, so the list
        cannot quietly accumulate permissions."""
        attribute_reads, string_constants = _scan()
        self.assertEqual(set(ALLOWED_ATTRIBUTE_READS) - attribute_reads, set())
        self.assertEqual(
            set(ALLOWED_STRING_CONSTANTS) - string_constants, set())

    def test_the_scan_sees_the_resolver_itself(self):
        """Reachable negative space: the scan does find `.depreciation`
        reads where they exist (the door itself), so an empty difference
        above is a finding and not a scan that sees nothing."""
        attribute_reads, string_constants = _scan()
        self.assertIn(
            ("forms/depreciation/resolver.py", "resolve"), attribute_reads)
        self.assertIn(
            ("scenario.py", "_SCHEDULE_C_AMOUNT_FIELDS"), string_constants)


if __name__ == "__main__":
    unittest.main()
