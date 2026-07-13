"""§4a entity amended-return checkbox marks — filled-emit read-back tests.

Drives ``run_full_federal_scorp_return`` / ``run_full_california_scorp_return``
with the S-corp return's ``amended_return`` flag OFF (default) and ON, reopens
the REAL filled PDFs, and asserts the certified per-year amended field reads
back its ON-state (or its absence) on each of the three forms:

  * Form 1120-S box H(4) "Amended return"      (federal, simple checkbox)
  * Schedule K-1 (1120-S) "Amended K-1"        (federal, simple checkbox)
  * Schedule K-1 (100S) line E amended         (CA; checkbox 2021-23, radio 2024-25)

The field PATH + ON-state come from each mapping class's ``get_amended_mark``
(certified from the template's own get_fields()/_States_ — see
docs/plans/amended-returns-probe-tables.md, "Entity amended checkboxes"). Also
covers the CA Form-100X manifest note and the loader round-trip (accepts the
key; fails closed on an unknown sibling key). Native throughout (no soffice)."""
import datetime
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.mappings.pdf_f100s_k1 import PdfF100SK1
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._scorp_fixtures import _make_v1_scenario, _scorp_attestation_defaults
from tests.helpers import scope_out_attestation_defaults


def _raw_v(pdf_path: Path, field_path: str):
    """The raw /V of one AcroForm field by its full path (a pypdf NameObject
    like '/1', '/Off', or the verbose radio literal), or None when unset."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V")
    return None if got is None else str(got)


def _with_ca(scenario, first_year=False):
    scenario.s_corp_return.ca = SCorpCAInputs(
        first_year=first_year,
        estimated_tax_payments=0.0,
        prior_year_overpayment_applied=0.0,
        state_tax_deducted_federally=0.0,
        depreciation_adjustment=0.0,
        apportionment_ca_only=True,
    )
    return scenario


def _scenario_yaml_dict(amended=None, extra_scorp=None):
    """A minimal-but-valid single-shareholder S-corp scenario dict for the
    loader round-trip test. All attestations present (load-time contract);
    the 8 1120-S keys affirmed True to match the v1 fixture posture."""
    config = {
        "year": 2025,
        "filing_status": "single",
        "birthdate": "01-01-1980",
        "state": "EX",
        "first_name": "Taxpayer",
        "last_name": "A",
        "ssn": "000-00-0000",
        **scope_out_attestation_defaults(),
        **_scorp_attestation_defaults(),
    }
    addr = {"street": "1 Example Ave", "city": "Example City",
            "state": "EX", "zip_code": "00000"}
    scorp = {
        "name": "Example S-Corp Inc.",
        "ein": "00-0000000",
        "address": addr,
        "date_incorporated": datetime.date(2020, 1, 1),
        "s_election_effective_date": datetime.date(2020, 1, 1),
        "total_assets": 50000.0,
        "income": {"gross_receipts": 100000.0, "returns_and_allowances": 0.0,
                   "cogs_aggregate": 0.0, "net_gain_loss_4797": 0.0,
                   "other_income": 0.0},
        "deductions": {"compensation_of_officers": 30000.0, "salaries_wages": 0.0,
                       "repairs_maintenance": 0.0, "bad_debts": 0.0, "rents": 0.0,
                       "taxes_licenses": 0.0, "interest": 0.0, "depreciation": 0.0,
                       "depletion": 0.0, "advertising": 0.0,
                       "pension_profit_sharing_plans": 0.0,
                       "employee_benefits": 0.0, "other_deductions": 0.0},
        "schedule_b_answers": {"accounting_method": "cash",
                               "business_activity_code": "541990",
                               "business_activity_description": "Services",
                               "product_or_service": "Consulting",
                               "any_c_corp_subsidiaries": False,
                               "has_any_foreign_shareholders": False,
                               "owns_foreign_entity": False},
        "shareholders": [{"name": "Taxpayer A", "ssn_or_ein": "000-00-0000",
                          "address": addr, "ownership_percentage": 100.0}],
    }
    if amended is not None:
        scorp["amended_return"] = amended
    if extra_scorp:
        scorp.update(extra_scorp)
    return {"config": config, "s_corp_return": scorp}


class FederalAmendedMarkTests(unittest.TestCase):
    """1120-S box H(4) + K-1 (1120-S) 'Amended K-1', all federal S-corp years."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, amended):
        s = _make_v1_scenario()
        s.config.year = year
        s.s_corp_return.amended_return = amended
        out = Path(self._tmp.name) / f"fed_{year}_{amended}"
        self.orch.run_full_federal_scorp_return(s, out)
        return out

    def test_flag_off_leaves_amended_fields_unmarked(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                out = self._emit(year, False)
                m_path, _ = PdfF1120S.get_amended_mark(year)
                self.assertIn(
                    _raw_v(out / f"f1120s_{year}.pdf", m_path), (None, "/Off"))
                k_path, _ = PdfF1120SK1.get_amended_mark(year)
                self.assertIn(
                    _raw_v(out / f"f1120s_k1_1_{year}.pdf", k_path),
                    (None, "/Off"))

    def test_flag_on_sets_certified_on_state(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                out = self._emit(year, True)
                m_path, m_on = PdfF1120S.get_amended_mark(year)
                self.assertEqual(
                    _raw_v(out / f"f1120s_{year}.pdf", m_path), m_on)
                k_path, k_on = PdfF1120SK1.get_amended_mark(year)
                self.assertEqual(
                    _raw_v(out / f"f1120s_k1_1_{year}.pdf", k_path), k_on)


class CaK1AmendedMarkTests(unittest.TestCase):
    """K-1 (100S) line E amended: checkbox (/Yes) 2021-23, radio 2024-25."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, amended):
        s = _with_ca(_make_v1_scenario())
        s.config.year = year
        s.s_corp_return.amended_return = amended
        out = Path(self._tmp.name) / f"ca_{year}_{amended}"
        self.orch.run_full_california_scorp_return(s, out)
        return out

    def test_flag_off_not_amended_token(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                out = self._emit(year, False)
                path, on = PdfF100SK1.get_amended_mark(year)
                v = _raw_v(out / f"f100s_k1_1_{year}.pdf", path)
                # Checkbox years: unset or /Off. Radio years: any value that is
                # NOT the amended token (may be /Off, the final-option token, or
                # None). Both reduce to: the amended token was NOT selected.
                self.assertNotEqual(v, on)

    def test_flag_on_sets_certified_on_state(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                out = self._emit(year, True)
                path, on = PdfF100SK1.get_amended_mark(year)
                self.assertEqual(
                    _raw_v(out / f"f100s_k1_1_{year}.pdf", path), on)


class Ca100XNoteTests(unittest.TestCase):
    """The loud CA Form-100X note renders iff the CA S-corp run is flagged."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, amended):
        s = _with_ca(_make_v1_scenario())
        s.s_corp_return.amended_return = amended
        out = Path(self._tmp.name) / f"note_{amended}"
        self.orch.run_full_california_scorp_return(s, out)
        return out / "scorp_amendment_note.txt"

    def test_note_renders_when_flagged(self):
        note = self._run(True)
        self.assertTrue(note.exists())
        body = note.read_text()
        self.assertIn("100X", body)
        self.assertIn("does not emit", body)

    def test_note_absent_when_unflagged(self):
        self.assertFalse(self._run(False).exists())


class ScorpAmendedLoaderTests(unittest.TestCase):
    def _write(self, data):
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return Path(f.name)

    def test_amended_true_loads(self):
        scenario = load_scenario(self._write(_scenario_yaml_dict(amended=True)))
        self.assertTrue(scenario.s_corp_return.amended_return)

    def test_default_false_when_absent(self):
        scenario = load_scenario(self._write(_scenario_yaml_dict()))
        self.assertFalse(scenario.s_corp_return.amended_return)

    def test_unknown_sibling_key_fails_closed(self):
        with self.assertRaises(ValueError):
            load_scenario(self._write(
                _scenario_yaml_dict(extra_scorp={"amend_return": True})))


if __name__ == "__main__":
    unittest.main()
