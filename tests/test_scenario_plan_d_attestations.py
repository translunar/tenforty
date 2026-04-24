"""3-way gate tests for all Plan D config fields."""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.scenario import load_scenario


_UNCONDITIONAL_FIELDS = (
    "acknowledges_qbi_below_threshold",
    "acknowledges_unlimited_at_risk",
    "basis_tracked_externally",
    "acknowledges_no_partnership_se_earnings",
    "acknowledges_no_section_1231_gain",
    "acknowledges_no_more_than_four_k1s",
    "acknowledges_no_k1_credits",
    "acknowledges_no_section_179",
    "acknowledges_no_estate_trust_k1",
    "prior_year_itemized",
)


def _base_config(**overrides) -> dict:
    """Default non-K-1 scenario config. All scope-out attestations set
    False so that a scenario with no K-1s, no QBI, no prior-year
    itemizing loads cleanly. For scenarios with K-1s or itemizing,
    use _base_config_with_k1 or override individual fields."""
    cfg = {
        "year": 2025,
        "filing_status": "single",
        "birthdate": "1990-01-01",
        "state": "CA",
        "has_foreign_accounts": False,
        "acknowledges_sch_a_sales_tax_unsupported": False,
        "acknowledges_no_wash_sale_adjustments": False,
        "acknowledges_no_other_basis_adjustments": False,
        "acknowledges_no_28_rate_gain": False,
        "acknowledges_no_unrecaptured_section_1250": False,
    }
    for name in _UNCONDITIONAL_FIELDS:
        cfg[name] = False
    cfg.update(overrides)
    return cfg


def _base_config_with_k1(**overrides) -> dict:
    """Config variant for scenarios that carry a K-1. Sets the K-1-gating
    attestations to True so compute-time gates don't trip on harmless
    test K-1 shapes. Override individual ones to exercise the gate."""
    k1_true = {name: True for name in _UNCONDITIONAL_FIELDS
               if name != "prior_year_itemized"}
    cfg = _base_config(**k1_true)
    cfg.update(overrides)
    return cfg


def _write_yaml(doc: dict, tmp: Path) -> Path:
    p = tmp / "s.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


class PlanDUnconditionalAttestationLoadTimeTests(unittest.TestCase):
    def test_load_raises_when_any_unconditional_field_omitted(self):
        for field_name in _UNCONDITIONAL_FIELDS:
            with self.subTest(field=field_name):
                cfg = _base_config()
                cfg.pop(field_name)
                doc = {"config": cfg}
                with tempfile.TemporaryDirectory() as tmp:
                    p = _write_yaml(doc, Path(tmp))
                    with self.assertRaisesRegex(
                        ValueError, rf"\b{field_name}\b"
                    ):
                        load_scenario(p)

    def test_load_succeeds_when_all_false(self):
        doc = {"config": _base_config()}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            for field_name in _UNCONDITIONAL_FIELDS:
                self.assertFalse(getattr(s.config, field_name))

    def test_load_succeeds_when_all_true(self):
        overrides = {name: True for name in _UNCONDITIONAL_FIELDS}
        overrides["prior_year_itemized_deduction_amount"] = 40_000.0
        overrides["prior_year_standard_deduction_amount"] = 14_600.0
        doc = {"config": _base_config(**overrides)}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            for field_name in _UNCONDITIONAL_FIELDS:
                self.assertTrue(getattr(s.config, field_name))


class PlanDConditionalFieldTests(unittest.TestCase):
    def test_mfs_without_mfs_flag_raises(self):
        cfg = _base_config(filing_status="married_separately")
        doc = {"config": cfg}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            with self.assertRaisesRegex(
                ValueError, r"\bmfs_lived_with_spouse_any_time\b"
            ):
                load_scenario(p)

    def test_mfs_with_flag_loads(self):
        cfg = _base_config(
            filing_status="married_separately",
            mfs_lived_with_spouse_any_time=False,
        )
        doc = {"config": cfg}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertFalse(s.config.mfs_lived_with_spouse_any_time)

    def test_nonmfs_without_mfs_flag_loads(self):
        """single filer does not need to declare the MFS sibling flag."""
        doc = {"config": _base_config(filing_status="single")}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertIsNone(s.config.mfs_lived_with_spouse_any_time)

    def test_prior_year_itemized_without_amounts_raises(self):
        cfg = _base_config(prior_year_itemized=True)
        doc = {"config": cfg}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            with self.assertRaisesRegex(
                ValueError,
                r"\bprior_year_(itemized|standard)_deduction_amount\b",
            ):
                load_scenario(p)

    def test_prior_year_itemized_with_amounts_loads(self):
        cfg = _base_config(
            prior_year_itemized=True,
            prior_year_itemized_deduction_amount=40_000.0,
            prior_year_standard_deduction_amount=14_600.0,
        )
        doc = {"config": cfg}
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertEqual(
                s.config.prior_year_itemized_deduction_amount, 40_000.0
            )
            self.assertEqual(
                s.config.prior_year_standard_deduction_amount, 14_600.0
            )


class ScheduleK1LoadTimeValidationTests(unittest.TestCase):
    """Per the caller-contract docstring on ScheduleK1, 1041 K-1 box 1
    is interest income, not ordinary business income. Enforce it at
    load time (the flattener also routes based on entity_type, but a
    mis-populated dataclass must be rejected up front)."""

    def test_estate_trust_k1_with_ordinary_business_income_raises(self):
        cfg = _base_config_with_k1()
        doc = {
            "config": cfg,
            "schedule_k1s": [{
                "entity_name": "Fake Trust",
                "entity_ein": "00-0000000",
                "entity_type": "estate_trust",
                "material_participation": True,
                "ordinary_business_income": 5_000.0,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            with self.assertRaisesRegex(
                ValueError,
                r"estate_trust.*ordinary_business_income|"
                r"ordinary_business_income.*estate_trust",
            ):
                load_scenario(p)

    def test_estate_trust_k1_with_interest_loads(self):
        cfg = _base_config_with_k1()
        doc = {
            "config": cfg,
            "schedule_k1s": [{
                "entity_name": "Fake Trust",
                "entity_ein": "00-0000000",
                "entity_type": "estate_trust",
                "material_participation": True,
                "interest_income": 5_000.0,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_yaml(doc, Path(tmp))
            s = load_scenario(p)
            self.assertEqual(s.schedule_k1s[0].interest_income, 5_000.0)


class PlanDFixtureDeclaresAttestationsTests(unittest.TestCase):
    """Every committed fixture must explicitly declare all Plan D fields."""

    def test_every_fixture_declares_all_unconditional_fields(self):
        fixtures_dir = Path(__file__).parent / "fixtures"
        for fixture in sorted(fixtures_dir.glob("*.yaml")):
            with self.subTest(fixture=fixture.name):
                s = load_scenario(fixture)
                for field_name in _UNCONDITIONAL_FIELDS:
                    self.assertIsNotNone(
                        getattr(s.config, field_name),
                        f"{fixture.name} must declare {field_name}",
                    )


if __name__ == "__main__":
    unittest.main()
