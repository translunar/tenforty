"""spouse_birthdate: the scenario input that lets the workbook oracle reach MFJ.

The vendor 1040 workbook's `Birthday_Needed` flag is TRUE on a married return
whenever any spouse birth part is blank, and that blanks line 16. These tests
pin the load-time contract (MFJ requires it; SINGLE/HoH refuse it; MFS accepts
it without requiring it), the flattener keys, and the per-year mapping onto
the workbook-scoped `SpouseBirth*` named inputs.
"""
import tempfile
import unittest
from pathlib import Path

import openpyxl
import yaml

from tenforty import years as year_manifest
from tenforty.mappings.f1040 import F1040
from tenforty.models import FilingStatus, Scenario, TaxReturnConfig, W2
from tenforty.oracle.flattener import flatten_scenario
from tenforty import scenario as scenario_mod
from tenforty.scenario import load_scenario
from tests.helpers import SPREADSHEETS_DIR, scope_out_attestation_defaults

_SPOUSE_KEYS = {
    "spouse_birthdate_month": "SpouseBirthMonth",
    "spouse_birthdate_day": "SpouseBirthDay",
    "spouse_birthdate_year": "SpouseBirthYear",
}


def _config_body(status: str, **extra) -> dict:
    body = {
        "year": 2025,
        "filing_status": status,
        "birthdate": "1985-03-01",
        "state": "CA",
        "first_name": "Example",
        "last_name": "Filer",
        "ssn": "000-00-0001",
        "digital_assets": False,
        **scope_out_attestation_defaults(),
    }
    if status in ("married_filing_jointly", "married_filing_separately"):
        body.update(spouse_first_name="Example", spouse_last_name="Spouse",
                    spouse_ssn="000-00-0002")
    if status == "married_filing_separately":
        body["mfs_lived_with_spouse_any_time"] = False
    body.update(extra)
    return body


def _config(status: FilingStatus, **extra) -> TaxReturnConfig:
    return TaxReturnConfig(
        year=2025, filing_status=status, birthdate="1985-03-01", state="CA",
        digital_assets=False, **scope_out_attestation_defaults(), **extra)


class SpouseBirthdateConfigTests(unittest.TestCase):
    """Load-time contract, through the real YAML loader and the pure check."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _load(self, status: str, **extra):
        path = Path(self._tmp.name) / "scenario.yaml"
        path.write_text(yaml.safe_dump(
            {"config": _config_body(status, **extra)}, sort_keys=False))
        return load_scenario(path)

    def test_mfj_without_spouse_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "spouse_birthdate"):
            self._load("married_filing_jointly")

    def test_mfj_with_non_iso_spouse_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "spouse_birthdate"):
            self._load("married_filing_jointly", spouse_birthdate="03/01/1986")

    def test_mfj_with_impossible_date_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "spouse_birthdate"):
            self._load("married_filing_jointly", spouse_birthdate="1986-02-30")

    def test_mfj_with_iso_spouse_birthdate_loads(self) -> None:
        scenario = self._load(
            "married_filing_jointly", spouse_birthdate="1986-07-09")
        self.assertEqual(scenario.config.spouse_birthdate, "1986-07-09")

    def test_unquoted_yaml_date_is_refused_with_a_quoting_hint(self) -> None:
        path = Path(self._tmp.name) / "scenario.yaml"
        text = yaml.safe_dump(
            {"config": _config_body("married_filing_jointly")},
            sort_keys=False)
        path.write_text(text + "  spouse_birthdate: 1986-07-09\n")
        with self.assertRaisesRegex(ValueError, "quoted ISO"):
            load_scenario(path)

    def test_head_of_household_with_spouse_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "spouse_birthdate"):
            self._load("head_of_household", spouse_birthdate="1986-07-09")

    def test_single_with_spouse_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "spouse_birthdate"):
            self._load("single", spouse_birthdate="1986-07-09")

    def test_mfs_without_spouse_birthdate_loads(self) -> None:
        scenario = self._load("married_filing_separately")
        self.assertEqual(scenario.config.spouse_birthdate, "")

    def test_mfs_with_spouse_birthdate_loads(self) -> None:
        scenario = self._load(
            "married_filing_separately", spouse_birthdate="1986-07-09")
        self.assertEqual(scenario.config.spouse_birthdate, "1986-07-09")

    def test_pure_check_refuses_and_accepts_without_a_loader(self) -> None:
        validate_spouse_birthdate = scenario_mod.validate_spouse_birthdate
        with self.assertRaises(ValueError):
            validate_spouse_birthdate(
                _config(FilingStatus.MARRIED_FILING_JOINTLY))
        with self.assertRaises(ValueError):
            validate_spouse_birthdate(_config(
                FilingStatus.HEAD_OF_HOUSEHOLD, spouse_birthdate="1986-07-09"))
        validate_spouse_birthdate(_config(
            FilingStatus.MARRIED_FILING_JOINTLY, spouse_birthdate="1986-07-09"))
        validate_spouse_birthdate(
            _config(FilingStatus.MARRIED_FILING_SEPARATELY))
        validate_spouse_birthdate(_config(FilingStatus.SINGLE))


class SpouseBirthdateFlattenTests(unittest.TestCase):

    @staticmethod
    def _scenario(cfg: TaxReturnConfig) -> Scenario:
        return Scenario(config=cfg, w2s=[W2(
            employer="Example Employer", wages=50_000.0,
            federal_tax_withheld=5_000.0, ss_wages=50_000.0,
            ss_tax_withheld=3_100.0, medicare_wages=50_000.0,
            medicare_tax_withheld=725.0)])

    def test_present_spouse_birthdate_emits_integer_parts(self) -> None:
        flat = flatten_scenario(self._scenario(_config(
            FilingStatus.MARRIED_FILING_JOINTLY,
            spouse_birthdate="1986-07-09")))
        self.assertEqual(flat["spouse_birthdate_year"], 1986)
        self.assertEqual(flat["spouse_birthdate_month"], 7)
        self.assertEqual(flat["spouse_birthdate_day"], 9)

    def test_absent_spouse_birthdate_emits_no_keys(self) -> None:
        flat = flatten_scenario(self._scenario(_config(FilingStatus.SINGLE)))
        for key in _SPOUSE_KEYS:
            self.assertNotIn(key, flat)
        # The filer's own parts are emitted for the same scenario, so the
        # absence above is a real absence, not a flattener that emits nothing.
        self.assertIn("birthdate_year", flat)


class SpouseBirthdateMappingTests(unittest.TestCase):

    def test_every_workbook_year_maps_the_three_keys(self) -> None:
        for year in year_manifest.WORKBOOK_YEARS:
            with self.subTest(year=year):
                inputs = F1040.INPUTS[year]
                for key, name in _SPOUSE_KEYS.items():
                    self.assertEqual(inputs.get(key), name)

    def test_named_input_exists_in_every_workbook(self) -> None:
        """Each `SpouseBirth*` name must exist, resolve to ONE cell on the
        '1040' sheet, and that cell must be an input (not a formula). Mapped
        by NAME: the address drifts year to year."""
        for year in year_manifest.WORKBOOK_YEARS:
            with self.subTest(year=year):
                wb = openpyxl.load_workbook(
                    SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx",
                    read_only=False)
                try:
                    for name in _SPOUSE_KEYS.values():
                        self.assertIn(name, wb.defined_names,
                                      f"{year} missing `{name}`")
                        destinations = list(
                            wb.defined_names[name].destinations)
                        self.assertEqual(len(destinations), 1,
                                         f"{year} `{name}` not single-cell")
                        sheet, ref = destinations[0]
                        self.assertEqual(sheet, "1040")
                        cell = wb[sheet][ref.replace("$", "")]
                        self.assertNotEqual(
                            cell.data_type, "f",
                            f"{year} `{name}` is a formula, not an input")
                finally:
                    wb.close()
