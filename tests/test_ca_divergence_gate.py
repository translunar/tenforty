"""Acknowledgment-gate tests (spec §2.5): a gated + triggered Schedule CA
divergence must be ADDRESSED (an amount applied, or the id explicitly reviewed)
or the California return REFUSES to compute.

The gate is a pure pre-compute check over the scenario's declared inputs, the
resolved CA540Return, and the year's catalog — it never runs form compute and
never mutates results. These tests exercise ``check_unaddressed_divergences``
directly (refuses / amount-clears / reviewed-clears / un-gated-never-refuses /
zero-trigger) and pin the ORCHESTRATOR placement: the refusal fires BEFORE
``form_sch_ca.compute`` (so a refusal can never yield a partial result), and a
zero-gated-trigger scenario is byte-identical to the pre-gate baseline.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.ca_divergences import (
    UnaddressedDivergencesError,
    check_unaddressed_divergences,
    materialize_user_divergence,
    resolve_divergence_id,
)
from tenforty.models import (
    CA540Return,
    EntityType,
    FilingStatus,
    Form1099INT,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
)
from tenforty.orchestrator import ReturnOrchestrator

REPO_ROOT = Path(__file__).parent.parent

YEAR = 2025
# The single gate:true catalog row (one per year 2021-2025): out-of-state muni
# interest CA taxes, gated on the has_tax_exempt_interest trigger.
GATED_ID = "out-of-state-muni-interest-excluded-federally-ca-taxes"
GATED_TRIGGER = "has_tax_exempt_interest"


def _config(year=YEAR) -> TaxReturnConfig:
    """Smallest valid CA-resident config. The gate is pure and inspects only
    Scenario list fields + the catalog, so no scope-out attestations or compute
    are needed."""
    return TaxReturnConfig(
        year=year,
        filing_status=FilingStatus.SINGLE,
        birthdate="1985-04-20",
        state="CA",
    )


def _scenario(year=YEAR, **kwargs) -> Scenario:
    return Scenario(config=_config(year), **kwargs)


def _tax_exempt_scenario(year=YEAR) -> Scenario:
    """Fires has_tax_exempt_interest (and therefore the gated muni row)."""
    return _scenario(
        year,
        form1099_int=[
            Form1099INT(payer="Muni Fund", interest=0.0, tax_exempt_interest=1_500.0)
        ],
    )


class GateRefusalTest(unittest.TestCase):
    def test_gated_triggered_unaddressed_refuses(self):
        """A gated row whose trigger fires, neither applied nor reviewed, refuses
        — and the message names id, description, the pub1001 page, the ircrtc,
        AND the fired trigger."""
        entry = resolve_divergence_id(YEAR, GATED_ID)
        with self.assertRaises(UnaddressedDivergencesError) as cm:
            check_unaddressed_divergences(_tax_exempt_scenario(), CA540Return(), YEAR)
        msg = str(cm.exception)
        self.assertIn(entry.id, msg)
        self.assertIn(entry.description, msg)
        self.assertIn(str(entry.pub1001_page), msg)
        self.assertIn(entry.ircrtc, msg)
        self.assertIn(GATED_TRIGGER, msg)

    def test_amount_clears_it(self):
        """Applying the divergence (id in ca540.divergences) computes, no raise."""
        entry = resolve_divergence_id(YEAR, GATED_ID)
        div = materialize_user_divergence(entry, 1_500.0, None)  # ADD row, no dir key
        ca540 = CA540Return(divergences=[div])
        self.assertIsNone(
            check_unaddressed_divergences(_tax_exempt_scenario(), ca540, YEAR)
        )

    def test_reviewed_clears_it(self):
        """Marking the id reviewed (reviewed_divergence_ids) computes, no raise."""
        ca540 = CA540Return(reviewed_divergence_ids=(GATED_ID,))
        self.assertIsNone(
            check_unaddressed_divergences(_tax_exempt_scenario(), ca540, YEAR)
        )

    def test_ungated_triggered_entry_never_refuses(self):
        """A scenario firing has_k1 (the federal-K-1 row is un-gated) with that
        row unaddressed still computes — the gate touches gated rows only."""
        k1 = ScheduleK1(
            entity_name="Acme LLC",
            entity_ein="00-0000000",
            entity_type=EntityType.S_CORP,
            material_participation=True,
        )
        # No tax-exempt interest -> the one gated row does not fire.
        self.assertIsNone(
            check_unaddressed_divergences(
                _scenario(schedule_k1s=[k1]), CA540Return(), YEAR
            )
        )

    def test_zero_trigger_scenario_returns_none(self):
        """No trigger signals at all -> the gate is a no-op (returns None)."""
        self.assertIsNone(
            check_unaddressed_divergences(_scenario(), CA540Return(), YEAR)
        )

    def test_none_ca540_no_gate(self):
        """No CA return -> nothing to gate, even if a trigger would fire."""
        self.assertIsNone(
            check_unaddressed_divergences(_tax_exempt_scenario(), None, YEAR)
        )


class GatePlacementTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_compute_ca_results_refuses_before_compute(self):
        """The refusal fires BEFORE form_sch_ca.compute: passing an empty
        federal_results dict still raises UnaddressedDivergencesError (not a
        KeyError('agi') from compute), proving a refusal never yields a partial
        result."""
        with self.assertRaises(UnaddressedDivergencesError):
            self.orch._compute_ca_results(_tax_exempt_scenario(), CA540Return(), {})

    def test_zero_trigger_ca_result_byte_identical(self):
        """A zero-gated-trigger CA scenario computes to the exact pre-gate
        baseline — the gate is provably a no-op on results. Baseline captured on
        pre-implementation code: ca_agi=80000, total_liability=-804."""
        from tests._ca_fixtures import _make_ca_withholding_scenario

        scenario = _make_ca_withholding_scenario()
        federal = self.orch.compute_federal(scenario)
        ca = self.orch._compute_ca_results(scenario, scenario.ca540, federal)
        self.assertEqual(ca["sch_ca_ca_agi"], 80_000)
        self.assertEqual(ca["f540_total_liability"], -804)


if __name__ == "__main__":
    unittest.main()
