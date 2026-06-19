# tests/test_spine_year_agnostic.py
import ast
import unittest
from pathlib import Path

MODULES = [
    Path("tenforty/forms/f1040_spine.py"),
    Path("tenforty/forms/f1040_tax.py"),
]


class YearAgnosticTests(unittest.TestCase):
    def test_no_year_equality_branches(self):
        for path in MODULES:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    left = node.left
                    if isinstance(left, ast.Name) and left.id == "year":
                        self.fail(f"{path}: `year` comparison in math module")
                    if (isinstance(left, ast.Attribute)
                            and left.attr == "year"):
                        self.fail(f"{path}: `.year` comparison in math module")
