# tests/test_attestations_ca.py
import unittest
from tenforty.attestations import _ATTESTATIONS, validate_load_time, enforce_compute_time
from tenforty.models import TaxReturnConfig
from tests.helpers import scope_out_attestation_defaults


_EXPECTED_CA_FIELDS = frozenset({
    "acknowledges_no_540nr_filing",
    "acknowledges_no_ca_amt_preferences",
    "acknowledges_no_ca_sch_d_federal_state_divergence",
    "acknowledges_no_ca_nol_carryover",
    "acknowledges_no_ca_depreciation_divergence",
    "acknowledges_no_ca_ira_basis_divergence",
    "acknowledges_no_ca_rdp_status",
    "acknowledges_no_excess_business_loss_carryover",
    "acknowledges_no_1031_personal_property_divergence",
    "acknowledges_no_ic_worker_reclassification",
    "acknowledges_no_other_state_tax_credit",
})


class CaAttestationRegistryTests(unittest.TestCase):
    def test_all_eleven_ca_attestations_registered(self):
        registered = {a.field for a in _ATTESTATIONS if a.field.startswith(
            ("acknowledges_no_540nr", "acknowledges_no_ca_", "acknowledges_no_excess_business_loss",
             "acknowledges_no_1031_personal_property", "acknowledges_no_ic_worker",
             "acknowledges_no_other_state_tax")
        )}
        self.assertEqual(registered, _EXPECTED_CA_FIELDS)

    def test_each_ca_attestation_has_substantive_load_error(self):
        for a in _ATTESTATIONS:
            if a.field in _EXPECTED_CA_FIELDS:
                with self.subTest(field=a.field):
                    self.assertIn(a.field, a.load_error,
                        f"load_error for {a.field} must reference its own field name verbatim")
                    self.assertGreater(len(a.load_error), 80,
                        f"load_error for {a.field} is too terse — must explain WHY")

    def test_year_aware_attestations_have_applies_in_years(self):
        year_bounded = {
            "acknowledges_no_excess_business_loss_carryover": {2021, 2022, 2023, 2024, 2025},
            "acknowledges_no_1031_personal_property_divergence": {2021, 2022, 2023, 2024, 2025},
        }
        for field_name, expected_years in year_bounded.items():
            attestation = next(a for a in _ATTESTATIONS if a.field == field_name)
            self.assertEqual(attestation.applies_in_years, expected_years,
                f"{field_name} should apply only in {expected_years}")


class CaAttestationLoadGateTests(unittest.TestCase):
    def _make_cfg_with_ca(self, **overrides) -> TaxReturnConfig:
        defaults = {
            "year": 2025,
            "filing_status": "single",
            "birthdate": "1990-01-01",
            "state": "CA",
            **scope_out_attestation_defaults(),
        }
        defaults.update(overrides)
        return TaxReturnConfig(**defaults)

    def test_540nr_unset_raises_at_load_time(self):
        cfg = self._make_cfg_with_ca(acknowledges_no_540nr_filing=None)
        with self.assertRaises(ValueError) as ctx:
            validate_load_time(cfg)
        self.assertIn("540NR", str(ctx.exception))

    def test_year_2018_skips_1031_personal_property(self):
        # TY2018 predates §1031 personal-property divergence semantics
        cfg = self._make_cfg_with_ca(
            year=2018,
            acknowledges_no_1031_personal_property_divergence=None,
        )
        # Should NOT raise — attestation doesn't apply in 2018
        validate_load_time(cfg)
