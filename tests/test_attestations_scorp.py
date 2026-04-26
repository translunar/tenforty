"""Load-time and compute-time gate tests for the 1120-S attestations."""

import unittest

from tenforty.attestations import _ATTESTATIONS, enforce_compute_time
from tenforty.models import FilingStatus, Scenario, TaxReturnConfig
from tests._scorp_fixtures import _make_scorp_return


_EXPECTED_SCORP_FIELDS = frozenset({
    "acknowledges_no_1120s_schedule_l_needed",
    "acknowledges_no_1120s_schedule_m_needed",
    "acknowledges_constant_shareholder_ownership",
    "acknowledges_no_section_1375_tax",
    "acknowledges_no_section_1374_tax",
    "acknowledges_cogs_aggregate_only",
    "acknowledges_officer_comp_aggregate_only",
    "acknowledges_no_elective_payment_election",  # NEW
})

# Per existing attestations.py convention, attestations whose
# triggered_when=_never have compute_error="" because their gate fires
# only at load time. The runtime-triggered ones must have non-empty
# compute_error.
_RUNTIME_TRIGGERED_SCORP_FIELDS = frozenset({
    "acknowledges_no_1120s_schedule_l_needed",
    "acknowledges_no_1120s_schedule_m_needed",
    "acknowledges_no_section_1375_tax",
    "acknowledges_no_section_1374_tax",
})

# Each load_error must mention its canonical IRC / R&TC / form anchor so a
# copy-paste error between two entries fails the content check below.
_LOAD_ERROR_ANCHORS = {
    "acknowledges_no_1120s_schedule_l_needed": "Schedule L",
    "acknowledges_no_1120s_schedule_m_needed": "Schedule M-1",
    "acknowledges_constant_shareholder_ownership": "§1377",
    "acknowledges_no_section_1375_tax": "§1375",
    "acknowledges_no_section_1374_tax": "§1374",
    "acknowledges_cogs_aggregate_only": "1125-A",
    "acknowledges_officer_comp_aggregate_only": "1125-E",
    "acknowledges_no_elective_payment_election": "§6417",
}


def _make_scorp_cfg(**overrides) -> TaxReturnConfig:
    """Build a TaxReturnConfig with all 8 1120-S attestations True by default,
    suitable for firing-test scaffolding. Override individual gates by kwarg to
    selectively set one False — per-test variance is then a single kwarg, not
    a 12-line config block."""
    base = {f: True for f in _EXPECTED_SCORP_FIELDS}
    base.update(overrides)
    return TaxReturnConfig(
        year=2025, filing_status=FilingStatus.SINGLE,
        birthdate="01-01-1980", state="EX",
        has_foreign_accounts=False, prior_year_itemized=False,
        **base,
    )


class SCorpAttestationsTests(unittest.TestCase):
    # NOTE: registry membership is already enforced canonically by
    # `tests/test_attestations.py::TestAttestationsTable` (full-set equality),
    # so a separate "are the seven registered" structural test would be
    # strictly weaker and was deliberately not added here. Content checks
    # below verify that each entry carries its canonical IRC/R&TC/form
    # anchor, catching copy-paste errors between entries.

    def test_each_scorp_load_error_mentions_canonical_anchor(self):
        """The load_error string must reference the IRC/R&TC/form anchor that
        identifies which scope-out it covers (e.g. `§1374`, `1125-A`,
        `Schedule M-1`). This catches copy-paste errors between adjacent
        entries — non-emptiness alone would not."""
        by_field = {a.field: a for a in _ATTESTATIONS}
        for field, anchor in _LOAD_ERROR_ANCHORS.items():
            self.assertIn(
                anchor, by_field[field].load_error,
                f"{field}.load_error missing canonical anchor {anchor!r}",
            )

    def test_runtime_triggered_attestations_have_compute_errors(self):
        for a in _ATTESTATIONS:
            if a.field not in _EXPECTED_SCORP_FIELDS:
                continue
            if a.field in _RUNTIME_TRIGGERED_SCORP_FIELDS:
                self.assertTrue(
                    a.compute_error,
                    f"{a.field} is runtime-triggered but has empty compute_error",
                )
            else:
                self.assertEqual(
                    a.compute_error, "",
                    f"{a.field} has triggered_when=_never; compute_error "
                    f"should be empty per convention.",
                )


class SCorpAttestationGateFiringTests(unittest.TestCase):
    """End-to-end: each runtime-triggered attestation gate actually raises
    when the underlying triggered_when predicate fires AND the attestation
    is False. All four runtime-triggered gates (Sch L, Sch M, §1375, §1374)
    are covered; the two large-balance-sheet predicates are exercised on
    BOTH arms of the OR (total_assets and gross_receipts)."""

    def test_schedule_l_gate_fires_on_high_total_assets(self):
        """Exercises the total_assets arm of `_has_scorp_large_balance_sheet`."""
        cfg = _make_scorp_cfg(acknowledges_no_1120s_schedule_l_needed=False)
        r = _make_scorp_return()
        r.total_assets = 500_000.0  # over the $250k threshold
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("Schedule L", str(cm.exception))

    def test_schedule_m_gate_fires_on_high_gross_receipts(self):
        """Exercises the gross_receipts arm of `_has_scorp_large_balance_sheet`
        (the Sch L test covers total_assets)."""
        cfg = _make_scorp_cfg(acknowledges_no_1120s_schedule_m_needed=False)
        r = _make_scorp_return()
        r.income.gross_receipts = 300_000.0
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("Schedule M-1", str(cm.exception))

    def test_section_1375_gate_fires_on_nonzero_passive_income_tax(self):
        cfg = _make_scorp_cfg(acknowledges_no_section_1375_tax=False)
        r = _make_scorp_return()
        r.scope_outs.net_passive_income_tax = 100.0
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("§1375", str(cm.exception))

    def test_section_1374_gate_fires_on_nonzero_built_in_gains_tax(self):
        cfg = _make_scorp_cfg(acknowledges_no_section_1374_tax=False)
        r = _make_scorp_return()
        r.scope_outs.built_in_gains_tax = 100.0
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("§1374", str(cm.exception))

    def test_section_1375_gate_does_not_fire_when_attestation_true(self):
        """Confirms `True` ack short-circuits the gate even when the
        triggered_when predicate fires — the attestation flag governs,
        not the predicate alone."""
        cfg = _make_scorp_cfg()  # all seven True
        r = _make_scorp_return()
        r.scope_outs.net_passive_income_tax = 100.0  # nonzero, but acked
        s = Scenario(config=cfg, s_corp_return=r)
        enforce_compute_time(s)  # no raise expected
