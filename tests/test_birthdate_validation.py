"""birthdate: load-time ISO contract, mirroring spouse_birthdate.

Every consumer of `birthdate` (the 1040 age checkboxes, the workbook
flattener's year/month/day split, the 540 date of birth) reads it as an ISO
YYYY-MM-DD string. A month-day-year value used to load silently and only fail
-- or be misread -- downstream; it now refuses at load, naming the field.
Synthetic data only.
"""
import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.models import FilingStatus, TaxReturnConfig
from tenforty import scenario as scenario_mod
from tenforty.scenario import load_scenario
from tests.helpers import scope_out_attestation_defaults


def _config_body(**extra) -> dict:
    body = {
        "year": 2025,
        "filing_status": "single",
        "birthdate": "1985-03-01",
        "state": "CA",
        "first_name": "Example",
        "last_name": "Filer",
        "ssn": "000-00-0001",
        "digital_assets": False,
        **scope_out_attestation_defaults(),
    }
    body.update(extra)
    return body


def _config(birthdate) -> TaxReturnConfig:
    return TaxReturnConfig(
        year=2025, filing_status=FilingStatus.SINGLE, birthdate=birthdate,
        state="CA", digital_assets=False, **scope_out_attestation_defaults())


class BirthdateConfigTests(unittest.TestCase):
    """Load-time contract, through the real YAML loader and the pure check."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _load(self, **extra):
        path = Path(self._tmp.name) / "scenario.yaml"
        path.write_text(yaml.safe_dump(
            {"config": _config_body(**extra)}, sort_keys=False))
        return load_scenario(path)

    def test_iso_birthdate_loads(self) -> None:
        self.assertEqual(self._load().config.birthdate, "1985-03-01")

    def test_month_day_year_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "`birthdate`"):
            self._load(birthdate="03-01-1985")

    def test_slashed_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "`birthdate`"):
            self._load(birthdate="03/01/1985")

    def test_impossible_date_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "`birthdate`"):
            self._load(birthdate="1985-02-30")

    def test_blank_birthdate_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "`birthdate`"):
            self._load(birthdate="")

    def test_unquoted_yaml_date_is_refused_with_a_quoting_hint(self) -> None:
        body = _config_body()
        del body["birthdate"]
        path = Path(self._tmp.name) / "scenario.yaml"
        path.write_text(yaml.safe_dump({"config": body}, sort_keys=False)
                        + "  birthdate: 1985-03-01\n")
        with self.assertRaisesRegex(ValueError, "`birthdate` must be a quoted ISO"):
            load_scenario(path)

    def test_pure_check_refuses_and_accepts_without_a_loader(self) -> None:
        validate_birthdate = scenario_mod.validate_birthdate
        for bad in ("03-01-1985", "03/01/1985", "1985-02-30", ""):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "`birthdate`"):
                    validate_birthdate(_config(bad))
        validate_birthdate(_config("1985-03-01"))


if __name__ == "__main__":
    unittest.main()
