import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from tenforty.forms import f1120s
from tenforty.models import (
    Address, EntityType, FilingStatus, Form1099INT, K1Allocation,
    K1AllocationEntity, K1AllocationShareholder, ScheduleK1, W2,
)
from tenforty.orchestrator import ReturnOrchestrator, _make_k1_from_1120s_allocation
from tenforty.params.federal import load as load_federal_params
from tests._scorp_fixtures import _make_v1_scenario
from tests.helpers import make_k1_scenario, needs_libreoffice


def _address():
    return Address(street="1 Example Ave", city="Example City",
                   state="EX", zip_code="00000")


def _alloc(*, box_1=70_000.0, qbi=70_000.0, pct=100.0):
    return K1Allocation(
        entity=K1AllocationEntity(
            name="Example S-Corp Inc.", ein="00-0000000", address=_address()),
        shareholder=K1AllocationShareholder(
            name="Taxpayer A", ssn_or_ein="000-00-0000", address=_address()),
        ownership_percentage=pct,
        box_1_ordinary_business_income=box_1,
        box_17v_qbi=qbi,
    )


class BridgeCarriesQbiTests(unittest.TestCase):
    def test_qbi_crosses_the_bridge(self):
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=70_000.0, qbi=70_000.0))
        self.assertEqual(k1.qbi_amount, 70_000.0)

    def test_qbi_independent_of_ordinary_business_income(self):
        """An override makes QBI differ from box 1; the bridge must carry the
        QBI figure, not re-derive it from ordinary business income."""
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=70_000.0, qbi=80_000.0))
        self.assertEqual(k1.qbi_amount, 80_000.0)
        self.assertEqual(k1.ordinary_business_income, 70_000.0)

    def test_qbi_amount_is_a_float(self):
        """box_17v_qbi arrives as an int from irs_round; ScheduleK1.qbi_amount
        is typed float, so the bridge converts explicitly."""
        k1 = _make_k1_from_1120s_allocation(_alloc(qbi=70_000))
        self.assertIsInstance(k1.qbi_amount, float)

    def test_loss_qbi_crosses_intact(self):
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=-5_000.0, qbi=-5_000.0))
        self.assertEqual(k1.qbi_amount, -5_000.0)

    def test_existing_bridge_fields_still_carried(self):
        """Guard against the wire breaking what already worked."""
        k1 = _make_k1_from_1120s_allocation(_alloc())
        self.assertEqual(k1.entity_name, "Example S-Corp Inc.")
        self.assertEqual(k1.entity_ein, "00-0000000")
        self.assertEqual(k1.entity_type, EntityType.S_CORP)
        self.assertEqual(k1.ordinary_business_income, 70_000.0)


class BridgeCrossPathAgreementTests(unittest.TestCase):
    def test_emitted_qbi_equals_consumed_qbi(self):
        """The QBI the entity side reports on the K-1 must be the QBI the
        individual side's Form 8995 consumes. Same run, same number."""
        scenario = _make_v1_scenario(
            gross_receipts=100_000.0, compensation_of_officers=30_000.0)

        # ENTITY side: what the emitted K-1 / Statement A assert.
        corp = f1120s.compute(scenario, upstream={})
        alloc = corp["f1120s_sch_k1_allocations"][0]
        emitted_qbi = float(alloc.box_17v_qbi)
        self.assertGreater(emitted_qbi, 0.0)  # fixture must be QBI-bearing

        # INDIVIDUAL side: drive the real orchestrator path end to end.
        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            effective, _corp_results = orch._build_effective_scenario(scenario)

        spliced = [k1 for k1 in effective.schedule_k1s
                   if k1.entity_ein == alloc.entity.ein]
        self.assertEqual(len(spliced), 1)
        self.assertEqual(spliced[0].qbi_amount, emitted_qbi)


class BridgeAboveThresholdTests(unittest.TestCase):
    def test_above_threshold_qbi_now_raises_instead_of_silently_zeroing(self):
        """Before the bridge carried QBI, an above-threshold S-corp scenario
        silently produced a ZERO QBI deduction — a wrong number. Now it raises
        NotImplementedError (Form 8995-A is not implemented in v1), which is
        the honest outcome. This test pins that intended behavior change.

        `_make_v1_scenario` fixes filing_status=SINGLE, whose 2025 Form 8995
        threshold is $197,300 (tenforty/params/federal/y2025.py). The S-corp
        stays at the fixture's default gross_receipts=100_000 /
        compensation_of_officers=30_000 — comfortably under the $250,000
        Schedule L / M-1 attestation trigger (tenforty/attestations.py) — so
        the 8 True `acknowledges_no_1120s_schedule_*` attestations
        `_make_v1_scenario` sets stay honest, and its net ordinary income
        (and QBI) is 100_000 - 30_000 = 70_000, positive and nonzero as the
        Form 8995 guard requires. Above-threshold income instead comes from a
        200_000 W-2 wage added on the individual side: combined with the
        70_000 of pass-through K-1 income, that's 270_000 before the $15,750
        single standard deduction, leaving taxable income before QBI at
        254_250 — comfortably above the 197_300 threshold, so the margin
        survives any rounding. `acknowledges_qbi_below_threshold` is left at
        its scope-out default (False), so the guard in
        tenforty/forms/f8995.py must fire.
        """
        scenario = _make_v1_scenario(
            gross_receipts=100_000.0, compensation_of_officers=30_000.0)
        ss_wage_base = float(
            load_federal_params(scenario.config.year).ss_wage_base)
        scenario = dataclasses.replace(scenario, w2s=[
            W2(
                employer="Example Employer Inc.",
                wages=200_000.0,
                federal_tax_withheld=40_000.0,
                # One employer withholds SS only up to the wage base.
                ss_wages=min(200_000.0, ss_wage_base),
                ss_tax_withheld=round(min(200_000.0, ss_wage_base) * 0.062, 2),
                medicare_wages=200_000.0,
                medicare_tax_withheld=round(200_000.0 * 0.0145),
            ),
        ])
        self.assertFalse(scenario.config.acknowledges_qbi_below_threshold)

        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            with self.assertRaisesRegex(
                NotImplementedError, "acknowledges_qbi_below_threshold"
            ):
                orch.compute_federal(scenario)


class BridgeLossYearQbiZeroFloorTests(unittest.TestCase):
    def test_loss_year_scorp_no_longer_yields_negative_deduction(self):
        """End-to-end reproduction of the originally-reported defect: a
        loss-year S-corp (ordinary business income and QBI both -30,000)
        combined with 120,000 of interest income previously produced a
        NEGATIVE Form 8995 deduction that INCREASED taxable income instead
        of leaving it alone. The bridge (tenforty/orchestrator.py,
        forms/sch_e_part_ii.py) correctly carries the -30,000 QBI through
        intact -- test_loss_qbi_crosses_intact in this file pins that. The
        floor belongs downstream in forms/f8995.py, where the IRS form
        itself puts it ("if zero or less, enter -0-"), and this test proves
        the floor lands: the QBI deduction must not be negative, and taxable
        income must equal taxable-income-before-QBI (a zero deduction was
        applied), not the inflated pre-fix figure.

        gross_receipts=20,000 - compensation_of_officers=50,000 yields
        ordinary business income (and QBI) of exactly -30,000, matching the
        controller's original repro. 120,000 of interest plus the 2025
        single standard deduction ($15,750) puts taxable-income-before-QBI
        at 74,250 -- the correct final taxable income once the deduction is
        properly floored at 0, versus the pre-fix 80,250 (74,250 minus a
        -6,000 "deduction" that actually added 6,000 back to taxable
        income).
        """
        scenario = _make_v1_scenario(
            gross_receipts=20_000.0, compensation_of_officers=50_000.0)
        # An S corporation box 1 loss computes only when the shareholder
        # attests the Form 7203 basis computation is attached by hand; this
        # test's subject is the QBI floor, so it affirms that gate.
        scenario = dataclasses.replace(
            scenario,
            config=dataclasses.replace(
                scenario.config,
                acknowledges_form_7203_attached_separately=True),
            form1099_int=[
                Form1099INT(payer="Example Bank", interest=120_000.0),
            ])
        self.assertFalse(scenario.config.acknowledges_qbi_below_threshold)

        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            results = orch.compute_federal(scenario)

        self.assertGreaterEqual(results["qbi_deduction"], 0)
        self.assertEqual(
            results["taxable_income"],
            results["taxable_income_before_qbi_deduction"],
        )


def _assert_routes_to_workbook(test, orch, scenario):
    """The guard under test lives on the workbook path only; a scenario that
    routes native would pass these tests for the wrong reason (the native
    Form 8995 refusal names 8995-A too)."""
    eff, _ = orch._build_effective_scenario(scenario)
    test.assertFalse(orch._scenario_in_spine_scope(eff))


def _workbook_qbi_scenario(year, filing_status, *, wages, qbi, **config):
    """A direct S-corp K-1 (ordinary income == QBI) plus ONE taxpayer W-2 --
    the shape of test_amendment_packet_emit's `_build_eic_eligible_qbi_
    scenario`. `acknowledges_qbi_below_threshold` is set False explicitly
    (`make_k1_scenario` turns it on, which would bypass the guard)."""
    scenario = make_k1_scenario()
    base = float(load_federal_params(year).ss_wage_base)
    ss_wages = min(wages, base)
    scenario.config = dataclasses.replace(
        scenario.config, year=year, filing_status=filing_status,
        acknowledges_qbi_below_threshold=False, **config)
    scenario.w2s = [W2(
        employer="Example Employer Inc.", wages=wages,
        federal_tax_withheld=round(wages * 0.1), ss_wages=ss_wages,
        ss_tax_withheld=round(ss_wages * 0.062), medicare_wages=wages,
        medicare_tax_withheld=round(wages * 0.0145), owner="taxpayer")]
    scenario.schedule_k1s = [ScheduleK1(
        entity_name="Example S-Corp Inc.", entity_ein="00-0000000",
        entity_type=EntityType.S_CORP, material_participation=True,
        ordinary_business_income=qbi, qbi_amount=qbi)]
    return scenario


@needs_libreoffice
class BridgeWorkbookRoutingQbiThresholdTests(unittest.TestCase):
    """The orchestrator's workbook-path Form 8995 threshold guard, end to end
    through the real XLSX workbook (soffice). Workbook-routed filers never
    reach the native spine, where `forms/f8995.py`'s above-threshold refusal
    lives; the 2025 workbook has an `8995` (simple-path) sheet and no `8995A`
    sheet, so without the guard an above-threshold return would compute
    silently on the wrong formula. The guard runs AFTER the workbook (it
    reads the harvested taxable income before QBI), so a harvest refusal
    (`Deduction` diagnostic, numeric probe) legitimately preempts it.

    Vehicle (team-lead ruling, declare-fallout): the BELOW-threshold half
    runs on a 2025 SINGLE, EIC-POSSIBLE filer (low wages + a K-1) -- EIC is
    never on the native spine, so this vehicle is permanent.

    The ABOVE-threshold half is RETIRED (ruled at back-year-2024 step 8). Its
    end-to-end guard fire was proven at declare-fallout on a 2024
    married-filing-jointly vehicle (oracle tier green,
    oracle-tier-post-fallout.log); declaring 2024 MFJ native removed that
    vehicle, and no permanent clean one exists: above the QBI threshold no
    filer is EIC-possible, a 2025 MFS workbook return refuses upstream on the
    lived-apart diagnostic ('Line 6ab (SS Bene)'!L29), and QSS is unverified
    and parked. The guard's own logic stays pinned without soffice by
    `WorkbookQbiThresholdGuardUnitTests` below (mocked workbook, MFS vehicle,
    above- and below-threshold, attestation and missing-key cases)."""

    @pytest.mark.oracle
    def test_below_threshold_still_computes_via_workbook(self):
        """8,000 of wages + 10,000 of K-1 QBI income, 2025 single: the cheap
        EIC estimate is under the 0-child ceiling, so the return routes to
        the workbook; taxable income before QBI (wages + K-1 less the single
        standard deduction, from params) is below the threshold and QBI is
        positive, so it must compute -- asserted on the real figures."""
        single = FilingStatus.SINGLE
        scenario = _workbook_qbi_scenario(
            2025, single, wages=8_000.0, qbi=10_000.0)
        view = load_federal_params(2025).for_status(single)
        expected = 8_000 + 10_000 - view.standard_deduction
        self.assertGreater(expected, 0)
        self.assertLess(expected, view.qbi_threshold)

        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            _assert_routes_to_workbook(self, orch, scenario)
            results = orch.compute_federal(scenario)

        self.assertEqual(
            results["taxable_income_before_qbi_deduction"], expected)
        self.assertGreater(results["qbi_deduction"], 0)
        self.assertEqual(
            results["taxable_income"],
            results["taxable_income_before_qbi_deduction"]
            - results["qbi_deduction"],
        )


class WorkbookQbiThresholdGuardUnitTests(unittest.TestCase):
    """Isolates the orchestrator-level guard added to `_compute_1040_pipeline`
    from the real XLSX workbook, which requires LibreOffice (the oracle
    tier pinned end to end by BridgeNonSingleWorkbookRoutingQbiThresholdTests
    above). Patches `_compute_1040_via_workbook` to return a synthetic
    result carrying a chosen `taxable_income_before_qbi_deduction`, so the
    guard's conditional (out-of-spine-scope AND QBI > 0 AND the
    `acknowledges_qbi_below_threshold` attestation NOT set AND above
    threshold) is pinned deterministically without launching soffice.
    Drives `_compute_1040_pipeline` directly rather than `compute_federal`:
    the guard lives entirely inside that method, and
    `_build_effective_scenario`'s S-corp waterfall / compute-time gates are
    orthogonal to it."""

    def _mfs_scenario_with_qbi(self, qbi_amount=70_000.0,
                               acknowledges_qbi_below_threshold=False):
        scenario = make_k1_scenario()
        # MFS: never declared on the native grid, so this routes to the
        # workbook path the guard lives on (2025 MFJ is native since
        # declare-2025).
        scenario.config.filing_status = FilingStatus.MARRIED_FILING_SEPARATELY
        # Set EXPLICITLY, never inherited: `make_k1_scenario()` (tests/
        # helpers.py) turns every K-1 gate attestation ON, including
        # `acknowledges_qbi_below_threshold`, so the fixture default here is
        # True -- the opposite of what the refusal tests need. The guard now
        # honors this attestation (matching f8995.compute), so leaving it
        # inherited would bypass the guard and make every refusal test in
        # this class pass vacuously.
        scenario.config.acknowledges_qbi_below_threshold = (
            acknowledges_qbi_below_threshold
        )
        scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Example Partnership",
                entity_ein="00-0000000",
                entity_type=EntityType.PARTNERSHIP,
                material_participation=True,
                ordinary_business_income=70_000.0,
                qbi_amount=qbi_amount,
            ),
        ]
        return scenario

    def _orch(self):
        return ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path("/tmp/tenforty-qbi-guard-unit"),
        )

    def test_raises_when_qbi_positive_and_workbook_taxable_income_above_threshold(self):
        scenario = self._mfs_scenario_with_qbi()
        self.assertFalse(scenario.config.acknowledges_qbi_below_threshold)
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value={"taxable_income_before_qbi_deduction": 500_000.0},
        ):
            with self.assertRaisesRegex(NotImplementedError, "8995-A|8995A"):
                self._orch()._compute_1040_pipeline(scenario)

    def test_raise_message_names_the_attestation_escape_hatch(self):
        """A refusal that does not name its own escape hatch is a dead end
        for the reader. f8995.compute's native-spine message names
        `acknowledges_qbi_below_threshold`; this workbook-path message must
        too, since the two refuse the same class of scenario and differ only
        in which route the filer's filing status happened to take."""
        scenario = self._mfs_scenario_with_qbi()
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value={"taxable_income_before_qbi_deduction": 500_000.0},
        ):
            with self.assertRaisesRegex(
                NotImplementedError, "acknowledges_qbi_below_threshold"
            ):
                self._orch()._compute_1040_pipeline(scenario)

    def test_missing_taxable_income_key_raises_rather_than_defaulting_to_zero(self):
        """The strict read is deliberate and must stay strict. Every OTHER
        test in this class hands the guard a workbook result that carries
        `taxable_income_before_qbi_deduction`, so without this test a
        refactor could restore the old `.get(..., 0)` default and the whole
        suite would stay green -- while this exact scenario (MFJ, 70,000 of
        QBI, 500,000 of taxable income) silently returned a simple-path-8995
        workbook result instead of refusing, because `0 > threshold` is
        False. Asserting on the message as well as the type pins that the
        KeyError is the guard's own deliberate refusal and not an incidental
        dict lookup failing somewhere else in the pipeline."""
        scenario = self._mfs_scenario_with_qbi()
        self.assertFalse(scenario.config.acknowledges_qbi_below_threshold)
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            # Deliberately WITHOUT "taxable_income_before_qbi_deduction".
            return_value={"sentinel": "no_taxable_income_key"},
        ):
            with self.assertRaises(KeyError) as ctx:
                self._orch()._compute_1040_pipeline(scenario)
        message = str(ctx.exception)
        self.assertIn("taxable_income_before_qbi_deduction", message)
        self.assertIn("_compute_1040_via_workbook", message)
        self.assertIn("Do not default this to 0", message)

    def test_attestation_bypasses_the_guard_on_the_workbook_path_too(self):
        """The attestation is honored on BOTH paths. f8995.compute's
        native-spine guard has `and not
        scenario.config.acknowledges_qbi_below_threshold` as its third
        conjunct; without the same conjunct here, an identical
        above-threshold scenario would be admitted when it routes to the
        native spine and refused when filing status sends it to the
        workbook -- the escape hatch would be granted or denied by filer
        class rather than by what the filer attested. With the attestation
        set, the guard is bypassed and the workbook result passes through
        untouched."""
        scenario = self._mfs_scenario_with_qbi(
            acknowledges_qbi_below_threshold=True)
        sentinel_result = {
            "taxable_income_before_qbi_deduction": 500_000.0,
            "sentinel": "unmodified",
        }
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value=sentinel_result,
        ):
            result = self._orch()._compute_1040_pipeline(scenario)
        # Compared against a FRESH literal, not against `sentinel_result`:
        # the pipeline returns the very object the patch handed back, so
        # `assertEqual(result, sentinel_result)` would compare that object
        # with itself and hold even if the guard had mutated it in place.
        # The literal below is the only independent record of what the
        # workbook returned, so it is what makes "untouched" testable.
        self.assertEqual(result, {
            "taxable_income_before_qbi_deduction": 500_000.0,
            "sentinel": "unmodified",
        })

    def test_does_not_raise_and_passes_through_result_when_below_threshold(self):
        scenario = self._mfs_scenario_with_qbi()
        sentinel_result = {
            "taxable_income_before_qbi_deduction": 100_000.0,
            "sentinel": "unmodified",
        }
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value=sentinel_result,
        ):
            result = self._orch()._compute_1040_pipeline(scenario)
        # Fresh literal, not `sentinel_result` -- see the note in
        # test_attestation_bypasses_the_guard_on_the_workbook_path_too.
        self.assertEqual(result, {
            "taxable_income_before_qbi_deduction": 100_000.0,
            "sentinel": "unmodified",
        })

    def test_does_not_raise_when_qbi_is_zero_even_above_threshold(self):
        """QBI == 0 must never trigger the guard, regardless of taxable
        income -- mirrors f8995.compute's `qbi_total > 0` condition."""
        scenario = self._mfs_scenario_with_qbi(qbi_amount=0.0)
        sentinel_result = {"taxable_income_before_qbi_deduction": 500_000.0}
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value=sentinel_result,
        ):
            result = self._orch()._compute_1040_pipeline(scenario)
        self.assertEqual(result, sentinel_result)
