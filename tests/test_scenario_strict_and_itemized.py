"""Loader coverage for two related contracts:

1. A top-level ``itemized_deductions:`` block loads into the
   ``ItemizedDeductions`` dataclass (it is a single object, not a list).
2. The loader is fail-closed: an unknown top-level key raises ``ValueError``
   naming the key, so a typo'd or unsupported block cannot silently vanish.

These were surfaced together: a filed-return reconciliation showed an
``itemized_deductions:`` block being silently dropped, which is both a
missing loader path and a fail-closed violation.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.models import ItemizedDeductions
from tenforty.scenario import load_scenario


def _base_config(**overrides) -> dict:
    """Minimal single-filer config that loads cleanly (all scope-out
    attestations False, no K-1s, no prior-year itemizing)."""
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
        "acknowledges_no_1120s_schedule_l_needed": False,
        "acknowledges_no_1120s_schedule_m_needed": False,
        "acknowledges_constant_shareholder_ownership": False,
        "acknowledges_no_section_1375_tax": False,
        "acknowledges_no_section_1374_tax": False,
        "acknowledges_cogs_aggregate_only": False,
        "acknowledges_officer_comp_aggregate_only": False,
        "acknowledges_no_elective_payment_election": False,
        "acknowledges_no_540nr_filing": False,
        "acknowledges_no_ca_amt_preferences": False,
        "acknowledges_no_ca_nol_carryover": False,
        "acknowledges_no_ca_depreciation_divergence": False,
        "acknowledges_no_ca_ira_basis_divergence": False,
        "acknowledges_no_ca_rdp_status": False,
        "acknowledges_no_excess_business_loss_carryover": False,
        "acknowledges_no_1031_personal_property_divergence": False,
        "acknowledges_no_ic_worker_reclassification": False,
        "acknowledges_no_other_state_tax_credit": False,
        "acknowledges_no_railroad_retirement_benefits": False,
        "acknowledges_no_paid_family_leave_benefits": False,
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
    }
    cfg.update(overrides)
    return cfg


def _write_yaml(doc: dict, tmp: Path) -> Path:
    p = tmp / "s.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


class ItemizedDeductionsLoadTests(unittest.TestCase):
    def test_itemized_deductions_block_loads(self):
        doc = {
            "config": _base_config(),
            "itemized_deductions": {
                "medical_expenses": 22450.0,
                "state_income_tax": 9000.0,
                "property_tax": 3000.0,
                "mortgage_interest": 5000.0,
                "charitable_contributions": 1000.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            scenario = load_scenario(_write_yaml(doc, Path(tmp)))
        self.assertIsInstance(scenario.itemized_deductions, ItemizedDeductions)
        self.assertEqual(scenario.itemized_deductions.medical_expenses, 22450.0)
        self.assertEqual(scenario.itemized_deductions.state_income_tax, 9000.0)
        self.assertEqual(scenario.itemized_deductions.property_tax, 3000.0)
        self.assertEqual(scenario.itemized_deductions.mortgage_interest, 5000.0)
        self.assertEqual(
            scenario.itemized_deductions.charitable_contributions, 1000.0)

    def test_partial_block_uses_field_defaults(self):
        doc = {
            "config": _base_config(),
            "itemized_deductions": {"medical_expenses": 22450.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            scenario = load_scenario(_write_yaml(doc, Path(tmp)))
        self.assertEqual(scenario.itemized_deductions.medical_expenses, 22450.0)
        # unspecified fields fall back to the dataclass defaults (0.0)
        self.assertEqual(scenario.itemized_deductions.state_income_tax, 0.0)
        self.assertEqual(scenario.itemized_deductions.charitable_contributions, 0.0)

    def test_absent_block_yields_none(self):
        doc = {"config": _base_config()}
        with tempfile.TemporaryDirectory() as tmp:
            scenario = load_scenario(_write_yaml(doc, Path(tmp)))
        self.assertIsNone(scenario.itemized_deductions)

    def test_empty_block_yields_all_defaults(self):
        # A present-but-empty block is distinct from an absent one: it
        # constructs an ItemizedDeductions with every field at its 0.0
        # default (itemizing to zero), NOT None (no itemization at all).
        doc = {"config": _base_config(), "itemized_deductions": {}}
        with tempfile.TemporaryDirectory() as tmp:
            scenario = load_scenario(_write_yaml(doc, Path(tmp)))
        self.assertIsInstance(scenario.itemized_deductions, ItemizedDeductions)
        self.assertEqual(scenario.itemized_deductions.medical_expenses, 0.0)
        self.assertEqual(scenario.itemized_deductions.state_income_tax, 0.0)


class StrictTopLevelKeysTests(unittest.TestCase):
    def test_unknown_top_level_key_raises_naming_it(self):
        doc = {"config": _base_config(), "itemized_dedcutions": {}}  # typo
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_yaml(doc, Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                load_scenario(path)
        self.assertIn("itemized_dedcutions", str(ctx.exception))

    def test_known_keys_all_accepted(self):
        doc = {
            "config": _base_config(),
            "w2s": [],
            "form1099_int": [],
            "form1099_div": [],
            "form1099_b": [],
            "form1099_g": [],
            "form1098s": [],
            "schedule_k1s": [],
            "rental_properties": [],
            "depreciable_assets": [],
            "s_corp_return": None,
            "ca540": None,
            "itemized_deductions": {"medical_expenses": 22450.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            scenario = load_scenario(_write_yaml(doc, Path(tmp)))  # must not raise
        self.assertEqual(scenario.itemized_deductions.medical_expenses, 22450.0)


if __name__ == "__main__":
    unittest.main()
