"""The refusal ledger: field-less, scenario-triggered refusals.

A sibling species to the config-field ``Attestation`` registry. An entry has
no ``TaxReturnConfig`` field, so it taxes no scenario at load; it fires only
when its own predicate finds offending items in the scenario.

``FIRING_PROOFS`` is the mechanical form of U-1 for this registry: every
registered refusal names the test that makes it fire, and an entry without a
proof (or naming a test that does not exist) fails the suite.
"""

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tenforty import attestations
from tenforty.attestations import (
    ScopedRefusal,
    _ATTESTATIONS,
    enforce_scoped_refusals,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import (
    SPREADSHEETS_DIR, make_simple_scenario, scope_out_attestation_defaults,
)

# refusal name -> "tests.module::Class::test_method" that makes it fire.
FIRING_PROOFS: dict[str, str] = {}

# The config-field registry as it stood before the ledger was added. A literal,
# not derived from the registry, so the pin cannot become a tautology.
_CONFIG_FIELD_ATTESTATIONS_BEFORE_LEDGER = [
    "has_foreign_accounts",
    "acknowledges_sch_a_sales_tax_unsupported",
    "acknowledges_qbi_below_threshold",
    "acknowledges_no_more_than_four_k1s",
    "acknowledges_unlimited_at_risk",
    "basis_tracked_externally",
    "acknowledges_no_section_1231_gain",
    "acknowledges_no_section_179",
    "acknowledges_no_partnership_se_earnings",
    "acknowledges_no_k1_credits",
    "acknowledges_form_7203_attached_separately",
    "acknowledges_sch_c_all_investment_at_risk",
    "acknowledges_no_estate_trust_k1",
    "prior_year_itemized",
    "acknowledges_no_wash_sale_adjustments",
    "acknowledges_no_other_basis_adjustments",
    "acknowledges_no_28_rate_gain",
    "acknowledges_no_unrecaptured_section_1250",
    "acknowledges_no_1120s_schedule_l_needed",
    "acknowledges_no_1120s_schedule_m_needed",
    "acknowledges_constant_shareholder_ownership",
    "acknowledges_no_section_1375_tax",
    "acknowledges_no_section_1374_tax",
    "acknowledges_cogs_aggregate_only",
    "acknowledges_officer_comp_aggregate_only",
    "acknowledges_no_elective_payment_election",
    "acknowledges_no_540nr_filing",
    "acknowledges_no_ca_amt_preferences",
    "acknowledges_no_ca_nol_carryover",
    "acknowledges_no_ca_depreciation_divergence",
    "acknowledges_no_ca_ira_basis_divergence",
    "acknowledges_no_ca_rdp_status",
    "acknowledges_no_excess_business_loss_carryover",
    "acknowledges_no_1031_personal_property_divergence",
    "acknowledges_no_ic_worker_reclassification",
    "acknowledges_no_other_state_tax_credit",
    "acknowledges_no_railroad_retirement_benefits",
    "acknowledges_no_paid_family_leave_benefits",
    "acknowledges_no_capital_loss_carryforward",
    "acknowledges_no_federal_amt",
]


def _synthetic(name: str, stage: str, exception=ValueError) -> ScopedRefusal:
    """A refusal that fires on any scenario carrying a W-2, naming the
    employers it found."""
    return ScopedRefusal(
        name=name,
        stage=stage,
        offenders=lambda subject: [w.employer for w in subject.w2s],
        message=lambda offenders: (
            f"synthetic refusal {name} fired for {', '.join(offenders)}"),
        exception=exception,
    )


def _minimal_yaml(tmp: Path) -> Path:
    cfg = {
        "year": 2025, "filing_status": "single", "birthdate": "1980-01-01",
        "state": "CA", "first_name": "Test", "last_name": "Filer",
        "ssn": "000-00-0000", "has_foreign_accounts": False,
        "prior_year_itemized": False,
        **scope_out_attestation_defaults(),
    }
    data = {
        "config": cfg,
        "w2s": [{
            "employer": "Example Employer", "wages": 50_000.0,
            "federal_tax_withheld": 5_000.0, "ss_wages": 50_000.0,
            "ss_tax_withheld": 3_100.0, "medicare_wages": 50_000.0,
            "medicare_tax_withheld": 725.0,
        }],
    }
    path = tmp / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


class ScopedRefusalDispatchTests(unittest.TestCase):
    def test_fires_at_its_own_stage_with_its_message(self):
        entry = _synthetic("synthetic_load", "load")
        scenario = make_simple_scenario()
        with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
            with self.assertRaises(ValueError) as cm:
                enforce_scoped_refusals(scenario, "load")
        self.assertEqual(
            str(cm.exception),
            "synthetic refusal synthetic_load fired for "
            + ", ".join(w.employer for w in scenario.w2s))

    def test_does_not_fire_at_the_other_stage(self):
        entry = _synthetic("synthetic_load", "load")
        scenario = make_simple_scenario()
        with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
            # Positive twin: the same entry on the same scenario DOES fire at
            # its own stage, so the silence below is reachable negative space.
            with self.assertRaises(ValueError):
                enforce_scoped_refusals(scenario, "load")
            enforce_scoped_refusals(scenario, "compute")

    def test_silent_when_predicate_finds_nothing(self):
        entry = _synthetic("synthetic_load", "load")
        scenario = make_simple_scenario()
        with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
            with self.assertRaises(ValueError):
                enforce_scoped_refusals(scenario, "load")
            scenario.w2s = []
            enforce_scoped_refusals(scenario, "load")

    def test_raises_the_entrys_own_exception_type(self):
        entry = _synthetic(
            "synthetic_compute", "compute", exception=NotImplementedError)
        scenario = make_simple_scenario()
        with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
            with self.assertRaisesRegex(
                    NotImplementedError, "synthetic refusal synthetic_compute"):
                enforce_scoped_refusals(scenario, "compute")

    def test_unknown_stage_is_refused(self):
        with self.assertRaisesRegex(ValueError, "stage"):
            enforce_scoped_refusals(make_simple_scenario(), "emit")

    def test_entry_with_unknown_stage_cannot_be_constructed(self):
        with self.assertRaisesRegex(ValueError, "stage"):
            _synthetic("bad_stage", "emit")


class ScopedRefusalWiringTests(unittest.TestCase):
    """The loader and the orchestrator actually call the ledger."""

    def test_load_scenario_enforces_load_stage(self):
        entry = _synthetic("synthetic_load", "load")
        with tempfile.TemporaryDirectory() as tmp:
            path = _minimal_yaml(Path(tmp))
            load_scenario(path)  # twin: loads with the ledger as registered
            with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
                with self.assertRaisesRegex(
                        ValueError, "synthetic refusal synthetic_load"):
                    load_scenario(path)

    def test_load_scenario_enforces_parse_stage_on_the_raw_mapping(self):
        entry = ScopedRefusal(
            name="synthetic_parse",
            stage="parse",
            offenders=lambda raw: sorted(k for k in raw if k == "w2s"),
            message=lambda offenders: (
                f"synthetic parse refusal fired for {offenders}"),
            exception=ValueError,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _minimal_yaml(Path(tmp))
            load_scenario(path)
            with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
                with self.assertRaisesRegex(
                        ValueError, r"synthetic parse refusal fired for \['w2s'\]"):
                    load_scenario(path)

    def test_load_scenario_does_not_enforce_compute_stage(self):
        entry = _synthetic("synthetic_compute", "compute")
        with tempfile.TemporaryDirectory() as tmp:
            path = _minimal_yaml(Path(tmp))
            with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
                scenario = load_scenario(path)
                # Twin: the entry is live and would fire at compute.
                with self.assertRaises(ValueError):
                    enforce_scoped_refusals(scenario, "compute")

    def _orchestrator(self, tmp: str) -> ReturnOrchestrator:
        return ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(tmp))

    def test_compute_federal_enforces_compute_stage(self):
        entry = _synthetic(
            "synthetic_compute", "compute", exception=NotImplementedError)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
                with self.assertRaisesRegex(
                        NotImplementedError,
                        "synthetic refusal synthetic_compute"):
                    self._orchestrator(tmp).compute_federal(
                        make_simple_scenario())

    def test_compute_federal_enforces_load_stage_for_programmatic_scenarios(self):
        """A Scenario built in code never passed through load_scenario, so
        compute re-checks the load-stage entries rather than trusting that
        the loader ran."""
        entry = _synthetic("synthetic_load", "load")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
                with self.assertRaisesRegex(
                        ValueError, "synthetic refusal synthetic_load"):
                    self._orchestrator(tmp).compute_federal(
                        make_simple_scenario())

    def test_effective_scenario_rerun_enforces_the_ledger(self):
        """The S-corp path re-runs compute-time gates on the effective
        scenario (with synthesized K-1s); the ledger rides along."""
        from tests._scorp_fixtures import _make_v1_scenario
        scenario = _make_v1_scenario()
        seen: list[tuple[int, str]] = []
        real = attestations.enforce_scoped_refusals

        def spy(subject, stage):
            seen.append((len(subject.schedule_k1s), stage))
            return real(subject, stage)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                    "tenforty.orchestrator.enforce_scoped_refusals", spy):
                effective, _ = self._orchestrator(
                    tmp)._build_effective_scenario(scenario)
        self.assertGreater(
            len(effective.schedule_k1s), len(scenario.schedule_k1s))
        self.assertIn((len(effective.schedule_k1s), "compute"), seen)


class ScopedRefusalRegistryTests(unittest.TestCase):
    def test_registered_names(self):
        self.assertEqual(
            [r.name for r in attestations._SCOPED_REFUSALS], [])

    def test_names_are_unique(self):
        names = [r.name for r in attestations._SCOPED_REFUSALS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_refusal_has_a_firing_proof(self):
        registered = {r.name for r in attestations._SCOPED_REFUSALS}
        self.assertEqual(
            registered - set(FIRING_PROOFS), set(),
            "refusal(s) registered without a firing-proof test")
        self.assertEqual(
            set(FIRING_PROOFS) - registered, set(),
            "firing proof(s) name a refusal that is not registered")

    def test_every_firing_proof_names_a_real_test(self):
        for name, node in FIRING_PROOFS.items():
            with self.subTest(refusal=name):
                module_name, class_name, method_name = node.split("::")
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                self.assertTrue(issubclass(cls, unittest.TestCase))
                self.assertTrue(method_name.startswith("test_"))
                self.assertTrue(callable(getattr(cls, method_name)))

    def test_completeness_gate_fails_an_unproven_entry(self):
        """The gate itself fires: an entry with no proof is caught."""
        entry = _synthetic("synthetic_unproven", "load")
        with mock.patch.object(attestations, "_SCOPED_REFUSALS", (entry,)):
            with self.assertRaisesRegex(
                    AssertionError, "without a firing-proof test"):
                self.test_every_refusal_has_a_firing_proof()

    def test_config_field_registry_is_untouched(self):
        self.assertEqual(
            [a.field for a in _ATTESTATIONS],
            _CONFIG_FIELD_ATTESTATIONS_BEFORE_LEDGER)


if __name__ == "__main__":
    unittest.main()
