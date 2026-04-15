"""Scenario load-time validation for v1 scope-out attestations."""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.scenario import load_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _base_config(**overrides) -> dict:
    cfg = {
        "year": 2025,
        "filing_status": "single",
        "birthdate": "1990-01-01",
        "state": "CA",
        "has_foreign_accounts": False,
        "acknowledges_form_8949_unsupported": False,
        "acknowledges_sch_a_sales_tax_unsupported": False,
    }
    cfg.update(overrides)
    return cfg


def _write_and_load(doc: dict) -> Path:
    """Write `doc` as YAML to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False,
    )
    tmp.write(yaml.safe_dump(doc))
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


class LoadScenarioForeignAccountsTests(unittest.TestCase):
    def test_load_raises_when_has_foreign_accounts_omitted(self):
        cfg = _base_config()
        cfg.pop("has_foreign_accounts")
        path = _write_and_load({"config": cfg})
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "has_foreign_accounts"):
            load_scenario(path)

    def test_load_raises_not_implemented_when_true(self):
        path = _write_and_load({"config": _base_config(has_foreign_accounts=True)})
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(NotImplementedError, "Part III"):
            load_scenario(path)

    def test_load_succeeds_when_false(self):
        path = _write_and_load({"config": _base_config(has_foreign_accounts=False)})
        self.addCleanup(path.unlink)
        s = load_scenario(path)
        self.assertFalse(s.config.has_foreign_accounts)


class LoadScenarioForm8949Tests(unittest.TestCase):
    def test_load_raises_when_acknowledges_form_8949_unsupported_omitted(self):
        cfg = _base_config()
        cfg.pop("acknowledges_form_8949_unsupported")
        path = _write_and_load({"config": cfg})
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "acknowledges_form_8949_unsupported"):
            load_scenario(path)

    def test_load_succeeds_when_false(self):
        path = _write_and_load(
            {"config": _base_config(acknowledges_form_8949_unsupported=False)},
        )
        self.addCleanup(path.unlink)
        s = load_scenario(path)
        self.assertFalse(s.config.acknowledges_form_8949_unsupported)

    def test_load_succeeds_when_true(self):
        # No raise here — the raise happens later in forms.sch_d.compute
        # only if an 8949-required lot is actually encountered (Task 11).
        path = _write_and_load(
            {"config": _base_config(acknowledges_form_8949_unsupported=True)},
        )
        self.addCleanup(path.unlink)
        s = load_scenario(path)
        self.assertTrue(s.config.acknowledges_form_8949_unsupported)


class FixtureAttestationsTests(unittest.TestCase):
    def test_every_fixture_declares_both_attestations_as_false(self):
        for fixture in sorted(FIXTURES_DIR.glob("*.yaml")):
            with self.subTest(fixture=fixture.name):
                s = load_scenario(fixture)
                self.assertFalse(s.config.has_foreign_accounts)
                self.assertFalse(s.config.acknowledges_form_8949_unsupported)
                self.assertFalse(s.config.acknowledges_sch_a_sales_tax_unsupported)
