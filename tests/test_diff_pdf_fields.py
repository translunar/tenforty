# tests/test_diff_pdf_fields.py
"""Field-inventory differ: names + widget types. A verdict of `identical`
licenses mapping inheritance for a new year; anything else routes the
form to re-probing. (Positional moves without a rename are NOT detected —
the probe step covers those; this differ's job is the fast common case.)"""
import unittest

from scripts.diff_pdf_fields import diff, inventory
from tests.helpers import REPO_ROOT


class DiffLogicTests(unittest.TestCase):
    def test_identical_inventories(self):
        inv = {"a[0]": "/Tx", "b[0]": "/Btn"}
        result = diff(inv, dict(inv))
        self.assertTrue(result.identical)
        self.assertEqual(result.added, ())
        self.assertEqual(result.removed, ())
        self.assertEqual(result.retyped, ())

    def test_added_removed_retyped(self):
        old = {"a[0]": "/Tx", "b[0]": "/Btn", "c[0]": "/Tx"}
        new = {"a[0]": "/Tx", "b[0]": "/Tx", "d[0]": "/Tx"}
        result = diff(old, new)
        self.assertFalse(result.identical)
        self.assertEqual(result.added, ("d[0]",))
        self.assertEqual(result.removed, ("c[0]",))
        self.assertEqual(result.retyped, ("b[0]",))


class InventoryTests(unittest.TestCase):
    def test_real_template_self_diff_is_identical(self):
        template = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040sa.pdf"
        inv = inventory(template)
        self.assertGreater(len(inv), 10)
        self.assertTrue(diff(inv, inventory(template)).identical)
