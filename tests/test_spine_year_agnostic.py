# tests/test_spine_year_agnostic.py
import ast
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent
MODULES = [
    _ROOT / "tenforty/forms/f1040_spine.py",
    _ROOT / "tenforty/forms/f1040_tax.py",
    _ROOT / "tenforty/forms/sch_a.py",
    _ROOT / "tenforty/forms/f8995.py",
    _ROOT / "tenforty/forms/sch_1.py",
]


class YearAgnosticTests(unittest.TestCase):
    def test_no_year_equality_branches(self):
        for path in MODULES:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    # Check both sides of the comparison so neither
                    # `if year == X` nor `if X == year` slips through.
                    operands = [node.left, *node.comparators]
                    for operand in operands:
                        if (isinstance(operand, ast.Name)
                                and operand.id == "year"):
                            self.fail(
                                f"{path}: `year` comparison in math module")
                        if (isinstance(operand, ast.Attribute)
                                and operand.attr == "year"):
                            self.fail(
                                f"{path}: `.year` comparison in math module")
