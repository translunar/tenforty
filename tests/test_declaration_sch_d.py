"""The Schedule D declaration validates against each year's own inventory
(emit-verification protocol step 4; adjudication
/private/tmp/pilot-packet-sch_d/ADJUDICATION.md).

The module ships inert: graduation (registration in
tenforty.declarations.forms with the pending removal) is a later, separate
step, so this test reads the module directly, not the registry.
"""
import unittest

from tenforty.declarations import registry, sch_d
from tenforty.declarations.model import FormDeclaration
from tenforty.declarations.validate import validate
from tenforty.verification.pending import PENDING_DECLARATIONS

YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "sch_d")


class SchDDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_d.DECLARATIONS), list(YEARS))
        for year in YEARS:
            decl = sch_d.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertIsInstance(decl, FormDeclaration)
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_d.DECLARATIONS[year],
                                    siblings=sch_d.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_ships_inert(self):
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


if __name__ == "__main__":
    unittest.main()
