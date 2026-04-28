"""Scenario load-time validation for Sch A line 5a (sales-tax) scope-out."""

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
        "acknowledges_sch_a_sales_tax_unsupported": False,
        "acknowledges_qbi_below_threshold": False,
        "acknowledges_unlimited_at_risk": False,
        "basis_tracked_externally": False,
        "acknowledges_no_partnership_se_earnings": False,
        "acknowledges_no_section_1231_gain": False,
        "acknowledges_no_more_than_four_k1s": False,
        "acknowledges_no_k1_credits": False,
        "acknowledges_no_section_179": False,
        "acknowledges_no_estate_trust_k1": False,
        "prior_year_itemized": False,
        "acknowledges_no_wash_sale_adjustments": False,
        "acknowledges_no_other_basis_adjustments": False,
        "acknowledges_no_28_rate_gain": False,
        "acknowledges_no_unrecaptured_section_1250": False,
        # 1120-S scope-out attestations (Sub-plan 2, Task 5)
        "acknowledges_no_1120s_schedule_l_needed": False,
        "acknowledges_no_1120s_schedule_m_needed": False,
        "acknowledges_constant_shareholder_ownership": False,
        "acknowledges_no_section_1375_tax": False,
        "acknowledges_no_section_1374_tax": False,
        "acknowledges_cogs_aggregate_only": False,
        "acknowledges_officer_comp_aggregate_only": False,
        "acknowledges_no_elective_payment_election": False,
    }
    cfg.update(overrides)
    return cfg


def _write_yaml(doc: dict, tmp: Path) -> Path:
    p = tmp / "s.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


class LoadScenarioSchASalesTaxTests(unittest.TestCase):
    def test_load_raises_when_attestation_omitted(self):
        cfg = _base_config()
        cfg.pop("acknowledges_sch_a_sales_tax_unsupported")
        doc = {"config": cfg}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            with self.assertRaisesRegex(
                ValueError, "acknowledges_sch_a_sales_tax_unsupported"
            ):
                load_scenario(p)

    def test_load_succeeds_when_false(self):
        doc = {"config": _base_config(acknowledges_sch_a_sales_tax_unsupported=False)}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertFalse(s.config.acknowledges_sch_a_sales_tax_unsupported)

    def test_load_succeeds_when_true(self):
        doc = {"config": _base_config(acknowledges_sch_a_sales_tax_unsupported=True)}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertTrue(s.config.acknowledges_sch_a_sales_tax_unsupported)


class FixtureSchASalesTaxAttestationTests(unittest.TestCase):
    def test_every_fixture_declares_the_attestation(self):
        for fixture in sorted(FIXTURES_DIR.glob("*.yaml")):
            with self.subTest(fixture=fixture.name):
                s = load_scenario(fixture)
                self.assertIsNotNone(
                    s.config.acknowledges_sch_a_sales_tax_unsupported,
                    f"{fixture.name} must declare "
                    f"acknowledges_sch_a_sales_tax_unsupported",
                )


if __name__ == "__main__":
    unittest.main()
