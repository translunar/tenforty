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
    ("attestations.py", "_negative_stated_depreciation"):
        "shape rule, sign only: a negative stated amount refuses",
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


# --- The asset-list species -------------------------------------------------
#
# The raw scalar is one way around the resolver; walking an activity's asset
# list and computing amounts from it is the other (review finding: the legacy
# Form 4562 summed table amounts over the assets itself, so it disagreed with
# an overridden activity's printed line). Two rules close it:
#   - `.depreciable_assets` is read only at the sites listed here;
#   - the per-asset table function `macrs_deduction` is referenced only
#     inside forms/depreciation/, so nobody else can turn an asset into an
#     amount.

# Every function in the resolver module may read the list: it is the door.
ASSET_LIST_MODULES: dict[str, str] = {
    "forms/depreciation/resolver.py": "the one door",
}
ALLOWED_ASSET_LIST_READS: dict[tuple[str, str], str] = {
    ("forms/f4562.py", "scenario_assets"):
        "Form 4562's read path: flattens the lists for the form's rows and "
        "the placement-year rule; amounts come from resolver.asset_amount",
    ("attestations.py", "_assets"):
        "ledger: iterates assets for the per-asset shape rules",
    ("attestations.py", "_bonus_history_assets"):
        "ledger: history field per asset, lifted by an activity override",
    ("attestations.py", "_dual_source_activities"):
        "ledger, truthiness only",
    ("attestations.py", "_unacknowledged_stated_figures"):
        "ledger, truthiness only",
    ("attestations.py", "_overrides_outside_asset_mode"):
        "ledger, truthiness only",
    ("attestations.py", "_asset_mode_on_unprinted_rentals"):
        "ledger, truthiness only",
    ("attestations.py", "_computable_overridden_activities"):
        "ledger: which overridden activities the engine can compute",
    ("attestations.py", "_merged_4562_with_override"):
        "ledger: placement dates only",
}
MACRS_DEDUCTION_MODULES: dict[str, str] = {
    "forms/depreciation/macrs.py": "defines it",
    "forms/depreciation/resolver.py": "the one door",
}


def _scan_asset_list() -> tuple[set, set]:
    """Every (module, scope) reading `.depreciable_assets`, and every module
    that references the name `macrs_deduction` at all (import, call, or
    attribute)."""
    list_reads: set[tuple[str, str]] = set()
    table_users: set[str] = set()
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
            return ".".join(reversed(names)) or "<module>"

        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and node.attr == "depreciable_assets"):
                list_reads.add((module, scope_of(node)))
            if ((isinstance(node, ast.Name) and node.id == "macrs_deduction")
                    or (isinstance(node, ast.Attribute)
                        and node.attr == "macrs_deduction")
                    or (isinstance(node, ast.alias)
                        and node.name == "macrs_deduction")
                    or (isinstance(node, ast.FunctionDef)
                        and node.name == "macrs_deduction")):
                table_users.add(module)
    return list_reads, table_users


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

    def test_asset_lists_are_read_only_at_the_listed_sites(self):
        list_reads, _ = _scan_asset_list()
        outside = {
            site for site in list_reads
            if site[0] not in ASSET_LIST_MODULES
            and site not in ALLOWED_ASSET_LIST_READS}
        self.assertEqual(
            outside, set(),
            "`.depreciable_assets` is walked outside the resolver")

    def test_only_the_depreciation_package_turns_an_asset_into_an_amount(self):
        _, table_users = _scan_asset_list()
        self.assertEqual(
            table_users - set(MACRS_DEDUCTION_MODULES), set(),
            "`macrs_deduction` is used outside forms/depreciation/")

    def test_asset_list_allowlists_carry_no_stale_entries(self):
        list_reads, table_users = _scan_asset_list()
        self.assertEqual(set(ALLOWED_ASSET_LIST_READS) - list_reads, set())
        self.assertEqual(
            set(ASSET_LIST_MODULES) - {module for module, _ in list_reads},
            set())
        self.assertEqual(set(MACRS_DEDUCTION_MODULES) - table_users, set())

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
