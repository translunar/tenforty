# tests/test_stylesheet_crosscheck.py
"""The official stylesheet cross-check (emit-verification harness spec §5.3).

One generated method per DECLARED federal form-year: a declared label the
IRS MeF stylesheet does not print, declared text that materially differs,
or a declared ``mef_element`` the stylesheet does not put on that line is a
failure. Stylesheet amount lines no declaration names are written to
``form_coverage_report.txt`` for the roadmap, never asserted. A form
module's documented WITNESS_DISCREPANCIES suppress exactly their own
findings, and go stale-red if the stylesheet in fact agrees.

Until federal forms declare, there are no generated methods; the
non-vacuity controls (``tests/test_verification_harness.py`` S10) prove the
check fires.
"""
import importlib
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import propose, registry
from tenforty.declarations.model import expand
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification.crosscheck import crosscheck, undeclared_amount_lines


def _federal_declarations():
    return sorted(((form, key) for form, key in registry.declared_forms()
                   if form[0] == "federal"), key=str)


def _method(form, key):
    def test(self):
        decl = registry.for_form(form, key)
        # The form's documented witness discrepancies, by the
        # module-per-form convention (tenforty.declarations.<form>).
        module = importlib.import_module(f"tenforty.declarations.{form[1]}")
        findings = crosscheck(
            decl, propose.stylesheet_lines(form[1], key),
            discrepancies=crosscheck_mod.discrepancies_in_force(module, key))
        self.assertEqual(findings, [], "\n" + "\n".join(
            f.message for f in findings))
    return test


class StylesheetCrosscheckTests(unittest.TestCase):
    """Generated: test_<form>_<year> per declared federal form-year."""


for _form, _key in _federal_declarations():
    setattr(StylesheetCrosscheckTests, f"test_{_form[1]}_{_key}",
            _method(_form, _key))


class WitnessDiscrepancyTests(unittest.TestCase):
    """A declaration module's documented WITNESS_DISCREPANCIES suppress
    exactly their own cross-check findings, two-directionally (S3 ruling):
    an undocumented disagreement still fails, and a documented one the
    stylesheet in fact agrees with is stale. Direct calls on Schedule C
    (sch_c records 20 per year, 21 in 2023), independent of registration."""

    YEARS = (2021, 2022, 2023, 2024, 2025)

    def _raw(self, decl):
        return crosscheck(decl, propose.stylesheet_lines("sch_c", decl.key))

    def _with(self, decl, discrepancies):
        return crosscheck(decl, propose.stylesheet_lines("sch_c", decl.key),
                          discrepancies=discrepancies)

    def test_documented_discrepancies_leave_no_finding(self):
        from tenforty.declarations import sch_c
        for year in self.YEARS:
            with self.subTest(year=year):
                in_force = crosscheck_mod.discrepancies_in_force(sch_c, year)
                findings = self._with(sch_c.DECLARATIONS[year], in_force)
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_in_force_set_is_exactly_the_raw_findings(self):
        from tenforty.declarations import sch_c
        for year in self.YEARS:
            with self.subTest(year=year):
                decl = sch_c.DECLARATIONS[year]
                in_force = crosscheck_mod.discrepancies_in_force(sch_c, year)
                lines = {ln.line_id[1]: ln.line_id
                         for ln in expand(decl, {})}
                raw = {lines[f.line] for f in self._raw(decl)}
                self.assertEqual(set(in_force), raw)
                self.assertEqual(len(in_force), 21 if year == 2023 else 20)

    def test_removing_a_documented_entry_returns_its_red(self):
        from tenforty.declarations import sch_c
        in_force = dict(crosscheck_mod.discrepancies_in_force(sch_c, 2022))
        del in_force[("Part II", "32a")]
        findings = self._with(sch_c.DECLARATIONS[2022], in_force)
        self.assertEqual([f.line for f in findings], ["32a"])
        self.assertIn("is not printed by the official stylesheet",
                      findings[0].message)

    def test_a_documented_entry_the_stylesheet_agrees_with_is_stale(self):
        from tenforty.declarations import sch_c
        decl = sch_c.DECLARATIONS[2022]
        line_1 = next(ln.line_id for ln in decl.lines if ln.line == "1")
        self.assertEqual([f for f in self._raw(decl) if f.line == "1"], [])
        in_force = dict(crosscheck_mod.discrepancies_in_force(sch_c, 2022))
        in_force[line_1] = "bogus: line 1 prints exactly as declared"
        findings = self._with(decl, in_force)
        self.assertEqual([f.line for f in findings], ["1"])
        self.assertIn("stale", findings[0].message)

    def test_a_module_without_a_record_has_nothing_in_force(self):
        from tenforty.declarations import sch_se
        self.assertEqual(crosscheck_mod.discrepancies_in_force(sch_se, 2024),
                         {})


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
