# tests/test_spine_year_agnostic.py
import ast
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent

# Strict tier: math modules — no comparison involving `year` at all.
STRICT_MODULES = [
    _ROOT / "tenforty/forms/f1040_spine.py",
    _ROOT / "tenforty/forms/f1040_tax.py",
    _ROOT / "tenforty/forms/sch_a.py",
    _ROOT / "tenforty/forms/f8995.py",
    _ROOT / "tenforty/forms/sch_1.py",
]

# Literal tier: modules that may key data structures BY year (membership
# tests like `year not in cls._MAPPINGS` are the approved pattern) but must
# never branch on a year literal (`if year == 2024`).
LITERAL_TIER_MODULES = sorted(
    (_ROOT / "tenforty/mappings").glob("*.py")
) + [_ROOT / "tenforty/forms/f540.py"]


def _is_year_operand(node: ast.expr) -> bool:
    return (isinstance(node, ast.Name) and node.id == "year") or (
        isinstance(node, ast.Attribute) and node.attr == "year")


class YearAgnosticTests(unittest.TestCase):
    def test_no_year_comparisons_in_math_modules(self):
        for path in STRICT_MODULES:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    for operand in [node.left, *node.comparators]:
                        if _is_year_operand(operand):
                            self.fail(
                                f"{path}: `year` comparison in math module")

    def test_no_year_literal_dispatch_in_mapping_modules(self):
        for path in LITERAL_TIER_MODULES:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                operands = [node.left, *node.comparators]
                has_year = any(_is_year_operand(o) for o in operands)
                has_int_literal = any(
                    isinstance(o, ast.Constant) and isinstance(o.value, int)
                    for o in operands)
                if has_year and has_int_literal:
                    self.fail(
                        f"{path}: `year` compared against an int literal — "
                        f"dispatch through a year-keyed dict instead")
