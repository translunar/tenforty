"""Integration test: Schedule B checkbox cells render correctly for non-default answers.

Loads scorp_sch_b_nondefault.yaml (accrual accounting + three printable "Yes" Sch B
answers: line 6 Form 8918, line 9 section 163(j) election, line 13 QSub termination),
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

    # filed_form_8918 = True (line 6)  ->  Yes box c2_7[0] is /1, No box clear
    def test_filed_form_8918_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_7[0]")
        self.assertEqual(v, "/1", f"filed_form_8918 Yes /V was {v!r}; expected '/1'")
        no = self._v("topmostSubform[0].Page2[0].c2_7[1]")
        self.assertNotEqual(no, "/2", f"filed_form_8918 No /V was {no!r}")

    # section_163j_election = True (line 9)  ->  Yes box c2_9[0] is /1
    def test_section_163j_election_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_9[0]")
        self.assertEqual(v, "/1", f"section_163j_election Yes /V was {v!r}; expected '/1'")

    # qsub_election_terminated = True (line 13)  ->  Yes box c3_2[0] is /1
    def test_qsub_election_terminated_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page3[0].c3_2[0]")
        self.assertEqual(v, "/1", f"qsub_election_terminated Yes /V was {v!r}; expected '/1'")

    # an answered No (line 3) marks the No box, on-state /2
    def test_line_3_no_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_2[1]")
        self.assertEqual(v, "/2", f"line 3 No /V was {v!r}; expected '/2'")


class SchBCheckboxRender2021Tests(unittest.TestCase):
    """2021 certification: the S-corp-only federal year (no 1040 spine) emits
    its Sch B checkbox states through the PUBLIC run_full_federal_scorp_return.

    get_checkbox_states(2021) dispatches to _CHECKBOX_STATES_2024; this reopens
    the real filled f1120s_2021.pdf and asserts the same non-default Sch B
    checkboxes round-trip to their expected on-states, certifying render (not
    just the mapping table) for 2021."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        scenario = load_scenario(FIXTURES_DIR / "scorp_sch_b_nondefault.yaml")
        scenario.config.year = 2021
        # Line 16 (digital assets) is not on the 2021 form: leave it unstated.
        scenario.s_corp_return.schedule_b_answers.digital_asset_transactions = None
        orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(cls._tmp.name),
        )
        out_dir = Path(cls._tmp.name) / "out"
        _results, emitted = orch.run_full_federal_scorp_return(scenario, out_dir)
        reader = PdfReader(str(emitted["1120s"]))
        cls._fields = reader.get_fields() or {}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _v(self, full_field_name: str):
        field = self._fields.get(full_field_name)
        if field is None:
            return None
        raw = field.get("/V")
        if raw is None:
            return None
        return str(raw)

    # accrual = True  →  c2_1[1] state is /2 (2024 on-states)
    def test_accounting_method_accrual_checkbox_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[1]")
        self.assertEqual(v, "/2", f"accrual checkbox /V was {v!r}; expected '/2'")

    # cash = False (not selected) →  c2_1[0] should NOT be /1
    def test_accounting_method_cash_checkbox_is_off(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[0]")
        self.assertNotEqual(v, "/1", f"cash checkbox /V was {v!r}; expected NOT '/1'")

    # other = False (not selected) →  c2_1[2] should NOT be /3
    def test_accounting_method_other_checkbox_is_off(self):
        v = self._v("topmostSubform[0].Page2[0].c2_1[2]")
        self.assertNotEqual(v, "/3", f"other checkbox /V was {v!r}; expected NOT '/3'")

    # filed_form_8918 = True (line 6)  ->  Yes box c2_07[0] is /1, No box clear
    def test_filed_form_8918_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_07[0]")
        self.assertEqual(v, "/1", f"filed_form_8918 Yes /V was {v!r}; expected '/1'")
        no = self._v("topmostSubform[0].Page2[0].c2_07[1]")
        self.assertNotEqual(no, "/2", f"filed_form_8918 No /V was {no!r}")

    # section_163j_election = True (line 9)  ->  Yes box c2_09[0] is /1
    def test_section_163j_election_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_09[0]")
        self.assertEqual(v, "/1", f"section_163j_election Yes /V was {v!r}; expected '/1'")

    # qsub_election_terminated = True (line 13)  ->  Yes box c3_2[0] is /1
    def test_qsub_election_terminated_yes_box_is_checked(self):
        v = self._v("topmostSubform[0].Page3[0].c3_2[0]")
        self.assertEqual(v, "/1", f"qsub_election_terminated Yes /V was {v!r}; expected '/1'")

    # an answered No (line 3) marks the No box, on-state /2
    def test_line_3_no_box_is_checked(self):
        v = self._v("topmostSubform[0].Page2[0].c2_2[1]")
        self.assertEqual(v, "/2", f"line 3 No /V was {v!r}; expected '/2'")
