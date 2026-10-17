# tests/test_stylesheet_crosscheck.py
"""The official stylesheet cross-check (emit-verification harness spec §5.3).

One generated method per DECLARED federal form-year: a declared label the
IRS MeF stylesheet does not print, declared text that materially differs,
or a declared ``mef_element`` the stylesheet does not put on that line is a
failure. Stylesheet amount lines no declaration names are written to
``form_coverage_report.txt`` for the roadmap, never asserted.

Until federal forms declare, there are no generated methods; the
non-vacuity controls (``tests/test_verification_harness.py`` S10) prove the
check fires.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry
from tenforty.verification.crosscheck import crosscheck, undeclared_amount_lines


def _federal_declarations():
    return sorted(((form, key) for form, key in registry.declared_forms()
                   if form[0] == "federal"), key=str)


def _method(form, key):
    def test(self):
        decl = registry.for_form(form, key)
        findings = crosscheck(decl, propose.stylesheet_lines(form[1], key))
        self.assertEqual(findings, [], "\n" + "\n".join(
            f.message for f in findings))
    return test


class StylesheetCrosscheckTests(unittest.TestCase):
    """Generated: test_<form>_<year> per declared federal form-year."""


for _form, _key in _federal_declarations():
    setattr(StylesheetCrosscheckTests, f"test_{_form[1]}_{_key}",
            _method(_form, _key))


class FormCoverageReportTests(unittest.TestCase):

    def test_write_the_undeclared_amount_line_report(self):
        lines = []
        for form, key in _federal_declarations():
            lines += undeclared_amount_lines(
                registry.for_form(form, key),
                propose.stylesheet_lines(form[1], key))
        path = Path(tempfile.mkdtemp()) / "form_coverage_report.txt"
        path.write_text("\n".join(lines) + "\n")
        print(f"\nform coverage report ({len(lines)} undeclared stylesheet "
              f"amount lines): {path}")
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
