# tests/test_params_attestation.py
"""Layer-1 gate: every per-year params module must agree, field for field,
with an INDEPENDENTLY TRANSCRIBED attestation module. Two air-gapped
transcriptions agreeing on the same wrong value is the failure mode this
kills; a disagreement is surfaced for human adjudication, never
auto-resolved (and never resolved by editing whichever side is easier)."""
import dataclasses
import importlib
import unittest

from tenforty import years as year_manifest
from tenforty.params import ca_scorp
from tenforty.params import california as ca_params
from tenforty.params.ca_scorp import CAScorpParams
from tenforty.params.california import CaliforniaParams
from tenforty.params.federal import FederalParams
from tenforty.params.federal import load as load_federal


# Documented no-op sentinels: the value a field holds in a year where the
# concept genuinely does not apply. An attestation may leave such a field None
# (declared in the module's NOT_APPLICABLE with a law-scope rationale) ONLY
# when the params hold exactly this sentinel — a not-applicable attestation can
# never bless a live value (fail-closed).
NO_OP_SENTINELS: dict[str, object] = {
    "salt_phaseout_threshold": None,
    "salt_phaseout_rate": 0.0,
}


def _assert_attested(test: unittest.TestCase, params, params_cls,
                     module_name: str) -> None:
    module = importlib.import_module(module_name)
    attested = module.ATTESTED
    not_applicable = getattr(module, "NOT_APPLICABLE", {})
    test.assertTrue(module.SOURCES, f"{module_name}: SOURCES must cite "
                                    f"the official publications used")
    field_names = {f.name for f in dataclasses.fields(params_cls)}
    test.assertEqual(set(attested), field_names,
                     f"{module_name}: ATTESTED keys must equal the "
                     f"dataclass fields exactly")
    for name in sorted(field_names):
        with test.subTest(field=name):
            params_value = getattr(params, name)
            attested_value = attested[name]
            if attested_value is None:
                # None is either "not applicable this year" — allowed ONLY when
                # the field is declared in NOT_APPLICABLE (rationale present)
                # AND the params hold that field's documented no-op sentinel
                # exactly — or "couldn't source", which fails as unattested and
                # drives the human source-adjudication path.
                test.assertIn(
                    name, not_applicable,
                    f"{module_name}.{name}: unattested (None with no "
                    f"not-applicable rationale)")
                test.assertIn(
                    name, NO_OP_SENTINELS,
                    f"{module_name}.{name}: declared not-applicable but no "
                    f"no-op sentinel is documented for it")
                test.assertEqual(
                    params_value, NO_OP_SENTINELS[name],
                    f"{module_name}.{name}: attested not-applicable, but the "
                    f"params hold a live value, not the no-op sentinel")
                continue
            if isinstance(params_value, dict) and isinstance(attested_value, dict):
                # Params may be single-scoped (storing only the statuses the
                # spine exercises); the attestation carries the full-status
                # transcription as documentation. Require the params' keys to be
                # a subset of the attested keys, and compare values on exactly
                # the keys the params actually store.
                test.assertLessEqual(
                    set(params_value), set(attested_value),
                    f"{module_name}.{name}: params keys are not a subset of "
                    f"the attested keys")
                test.assertEqual(
                    params_value,
                    {k: attested_value[k] for k in params_value},
                    f"{module_name}.{name}: value mismatch on the params' keys")
            else:
                test.assertEqual(params_value, attested_value,
                                 f"{module_name}.{name}: value mismatch")


class FederalAttestationTests(unittest.TestCase):
    def test_every_federal_year_attested(self):
        for year in year_manifest.FEDERAL_YEARS:
            _assert_attested(
                self, load_federal(year), FederalParams,
                f"tests.params_attestations.federal_y{year}")


class CaliforniaAttestationTests(unittest.TestCase):
    def test_every_full_california_year_attested(self):
        # Compute-only years are attested when they leave that tier.
        for year in year_manifest.CALIFORNIA_YEARS:
            _assert_attested(
                self, ca_params.load(year), CaliforniaParams,
                f"tests.params_attestations.california_y{year}")


class CAScorpAttestationTests(unittest.TestCase):
    def test_every_ca_scorp_year_attested(self):
        for year in year_manifest.CA_SCORP_YEARS:
            _assert_attested(
                self, ca_scorp.load(year), CAScorpParams,
                f"tests.params_attestations.ca_scorp_y{year}")
