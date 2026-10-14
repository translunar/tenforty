# tests/test_params_attestation.py
"""Layer-1 gate: every per-year params module must agree, field for field,
with an INDEPENDENTLY TRANSCRIBED attestation module. Two air-gapped
transcriptions agreeing on the same wrong value is the failure mode this
kills; a disagreement is surfaced for human adjudication, never
auto-resolved (and never resolved by editing whichever side is easier)."""
import contextlib
import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

from tenforty import years as year_manifest
from tenforty.params import ca_scorp
from tenforty.params import california as ca_params
from tenforty.params.ca_scorp import CAScorpParams
from tenforty.params.california import CaliforniaParams
from tenforty.params.f8962 import F8962Params
from tenforty.params.f8962 import load as load_f8962
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
    # int|None field: in a year without a non-itemizer charitable deduction the
    # params hold None (no cap), so the documented no-op sentinel is None.
    "nonitemizer_charitable_cap": None,
}


def _assert_attested(test: unittest.TestCase, params, params_cls,
                     module_name: str) -> None:
    module = importlib.import_module(module_name)
    attested = module.ATTESTED
    not_applicable = getattr(module, "NOT_APPLICABLE", {})
    test.assertTrue(module.SOURCES, f"{module_name}: SOURCES must cite "
                                    f"the official publications used")
    pending = getattr(module, "PENDING_TRANSCRIPTION", {})
    field_names = {f.name for f in dataclasses.fields(params_cls)}
    test.assertEqual(set(attested), field_names,
                     f"{module_name}: ATTESTED keys must equal the "
                     f"dataclass fields exactly")
    for name in sorted(field_names):
        with test.subTest(field=name):
            params_value = getattr(params, name)
            attested_value = attested[name]
            if name in pending:
                # Transcription not landed yet: absent on BOTH sides. A
                # pending entry can never bless a live params value, and a
                # stale pending entry next to a transcribed value fails too.
                test.assertIsNone(
                    attested_value,
                    f"{module_name}.{name}: listed in PENDING_TRANSCRIPTION "
                    f"but attested a value; remove the pending entry")
                test.assertIsNone(
                    params_value,
                    f"{module_name}.{name}: pending transcription, but the "
                    f"params hold a live value with no attestation")
                continue
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
        # Compute-only years carry an attested params pack too (native spine
        # compute needs cross-validated brackets), so they are attested while
        # in the tier — unlike CA compute-only, which is attested on exit.
        for year in (year_manifest.FEDERAL_YEARS
                     + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS):
            _assert_attested(
                self, load_federal(year), FederalParams,
                f"tests.params_attestations.federal_y{year}")


class CaliforniaAttestationTests(unittest.TestCase):
    def test_every_full_california_year_attested(self):
        # Compute-only CA years carry an attested params pack too (native 540
        # compute needs cross-validated rate schedules), so they are attested
        # while in the tier, mirroring the federal compute-only registration.
        for year in (year_manifest.CALIFORNIA_YEARS
                     + year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS):
            _assert_attested(
                self, ca_params.load(year), CaliforniaParams,
                f"tests.params_attestations.california_y{year}")


class CAScorpAttestationTests(unittest.TestCase):
    def test_every_ca_scorp_year_attested(self):
        for year in year_manifest.CA_SCORP_YEARS:
            _assert_attested(
                self, ca_scorp.load(year), CAScorpParams,
                f"tests.params_attestations.ca_scorp_y{year}")


class F8962AttestationTests(unittest.TestCase):
    def test_every_f8962_year_attested(self):
        for year in year_manifest.amendable_federal_years():
            _assert_attested(
                self, load_f8962(year), F8962Params,
                f"tests.params_attestations.f8962_y{year}")


@dataclasses.dataclass(frozen=True)
class _ProbeParams:
    year: int
    pending_field: int | None = None


class _Probe(unittest.TestCase):
    """Runs _assert_attested with subTest as a no-op, so a gate failure
    raises AssertionError here instead of being recorded as a subtest."""

    def subTest(self, msg=None, **params):  # noqa: N802 (unittest API)
        return contextlib.nullcontext()

    def run_probe(self):  # pragma: no cover - only used as a method name
        pass


class PendingTranscriptionGateTests(unittest.TestCase):
    """The PENDING_TRANSCRIPTION branch of _assert_attested, on synthetic
    modules. Real attestation modules no longer list any pending field once
    transcription lands, so the branch needs its own negative space."""

    MODULE = "tests._synthetic_pending_attestation"

    def _gate(self, *, params_value, attested_value):
        module = types.ModuleType(self.MODULE)
        module.SOURCES = ("synthetic",)
        module.ATTESTED = {"year": 2025, "pending_field": attested_value}
        module.PENDING_TRANSCRIPTION = {"pending_field": "synthetic"}
        with mock.patch.dict(sys.modules, {self.MODULE: module}):
            _assert_attested(_Probe("run_probe"),
                             _ProbeParams(2025, params_value), _ProbeParams,
                             self.MODULE)

    def test_pending_absent_on_both_sides_passes(self):
        self._gate(params_value=None, attested_value=None)

    def test_pending_with_live_params_value_fails(self):
        with self.assertRaisesRegex(AssertionError, "pending transcription"):
            self._gate(params_value=7, attested_value=None)

    def test_stale_pending_entry_next_to_attested_value_fails(self):
        with self.assertRaisesRegex(AssertionError, "remove the pending entry"):
            self._gate(params_value=7, attested_value=7)
