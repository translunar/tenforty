"""Integration test: Schedule B checkbox cells render correctly for non-default answers.

Loads scorp_sch_b_nondefault.yaml (accrual accounting + three "Yes" Sch B answers),
renders the full return via ReturnOrchestrator.run_full_return, then reads back the
f1120s_2025.pdf with pypdf and asserts that the True-valued checkboxes have the correct
/V state.

pypdf observation: IRS XFA forms use per-field state names ("/1", "/2", "/3") rather
than the conventional "/Yes". PdfFiller.fill() uses the checkbox_states registry from
PdfF1120S.get_checkbox_states() to write the correct state name for each bool field.
pypdf's update_page_form_field_values sets both /AS and /V to the NameObject state;
get_fields() returns these as NameObject strings with a leading slash (e.g. "/1", "/2").

The accounting method is a radio group: [0]=Cash(/1), [1]=Accrual(/2), [2]=Other(/3).
The yes/no questions each use "/1" as their checked state and "/Off" as unchecked.
The critical assertion is that True-valued cells round-trip to their checked state.
Off/unchecked cells may show "/Off" — the test asserts they are NOT the checked state.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class SchBCheckboxRenderTests(unittest.TestCase):
    """End-to-end: non-default Sch B fixture checkboxes round-trip correctly."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        scenario = load_scenario(FIXTURES_DIR / "scorp_sch_b_nondefault.yaml")
        orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(cls._tmp.name),
        )
        out_dir = Path(cls._tmp.name) / "out"
        _results, emitted = orch.run_full_return(scenario, out_dir)
        reader = PdfReader(str(emitted["1120s"]))
        cls._fields = reader.get_fields() or {}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _v(self, full_field_name: str):
        """Return the /V value for a field as a string, or None if absent."""
        field = self._fields.get(full_field_name)
        if field is None:
            return None
        raw = field.get("/V")
        if raw is None:
            return None
        return str(raw)

    # accrual = True  →  c2_1[1] state is /2 in the IRS XFA form
    def test_accounting_method_accrual_checkbox_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[1]")
        self.assertEqual(v, "/2", f"accrual checkbox /V was {v!r}; expected '/2'")

    # cash = False (not selected) →  c2_1[0] should be /Off
    def test_accounting_method_cash_checkbox_is_off(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[0]")
        self.assertNotEqual(v, "/1", f"cash checkbox /V was {v!r}; expected NOT '/1'")

    # other = False (not selected) →  c2_1[2] should be /Off
    def test_accounting_method_other_checkbox_is_off(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[2]")
        self.assertNotEqual(v, "/3", f"other checkbox /V was {v!r}; expected NOT '/3'")

    # has_any_foreign_shareholders = True  →  c2_2[0] state is /1
    def test_has_any_foreign_shareholders_checkbox_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_2[0]")
        self.assertEqual(v, "/1", f"has_any_foreign_shareholders /V was {v!r}; expected '/1'")

    # any_c_corp_subsidiaries = True  →  c2_3[0] state is /1
    def test_any_c_corp_subsidiaries_checkbox_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_3[0]")
        self.assertEqual(v, "/1", f"any_c_corp_subsidiaries /V was {v!r}; expected '/1'")

    # owns_foreign_entity = True  →  c2_4[0] state is /1
    def test_owns_foreign_entity_checkbox_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_4[0]")
        self.assertEqual(v, "/1", f"owns_foreign_entity /V was {v!r}; expected '/1'")
