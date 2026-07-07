# tests/test_scaffold_year.py
"""Scaffolder generates fail-closed stubs: a scaffolded-but-unfilled year
cannot pass any gate."""
import tempfile
import unittest
from pathlib import Path

from scripts.scaffold_year import scaffold


class ScaffoldTests(unittest.TestCase):
    def test_creates_params_and_attestation_stubs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            created = scaffold(root, "federal", 2023)
            names = {p.relative_to(root).as_posix() for p in created}
            self.assertEqual(names, {
                "tenforty/params/federal/y2023.py",
                "tests/params_attestations/federal_y2023.py",
            })

    def test_params_stub_raises_at_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (stub,) = [p for p in scaffold(root, "federal", 2023)
                       if "params" in str(p) and "attestations" not in str(p)]
            text = stub.read_text()
            self.assertIn("raise NotImplementedError", text)
            self.assertIn("2023", text)

    def test_attestation_stub_is_all_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (att,) = [p for p in scaffold(root, "california", 2023)
                      if "attestations" in str(p)]
            text = att.read_text()
            self.assertIn("ATTESTED", text)
            self.assertIn("None", text)
            self.assertNotIn("raise", text)

    def test_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold(root, "federal", 2023)
            with self.assertRaises(FileExistsError):
                scaffold(root, "federal", 2023)
