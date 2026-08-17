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
        scenario = dataclasses.replace(scenario, w2s=[
            W2(
                employer="Example Employer Inc.",
                wages=200_000.0,
                federal_tax_withheld=40_000.0,
                ss_wages=200_000.0,
                ss_tax_withheld=round(200_000.0 * 0.062),
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
        scenario = dataclasses.replace(scenario, form1099_int=[
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


def _mfj(scenario):
    """Re-file a `_make_v1_scenario()` fixture (which fixes filing_status=
    SINGLE) as MARRIED_JOINTLY, leaving every other field untouched.

    Also supplies a synthetic spouse identity so the MFJ scenario is complete
    at setup: filing MARRIED_JOINTLY with `spouse_first_name` /
    `spouse_last_name` / `spouse_ssn` left empty is an incomplete return, and
    the tests built on this helper must be able to fail only on the guard
    under test, never at setup. The spouse mirrors the fixture's own
    conventions for the primary filer (`first_name="Taxpayer"`,
    `last_name="A"`, `ssn="000-00-0000"`)."""
    return dataclasses.replace(
        scenario,
        config=dataclasses.replace(
            scenario.config,
            filing_status=FilingStatus.MARRIED_JOINTLY,
            spouse_first_name="Taxpayer",
            spouse_last_name="B",
            spouse_ssn="000-00-0001",
        ),
    )


@needs_libreoffice
class BridgeNonSingleWorkbookRoutingQbiThresholdTests(unittest.TestCase):
    """Non-SINGLE filers are out of native-1040-spine scope
    (`_scenario_in_spine_scope` returns False for any non-SINGLE filing
    status), so they route to the XLSX workbook path instead of the native
    spine where `forms/f8995.py`'s above-threshold refusal lives. The 2025
    workbook has an `8995` (simple-path) sheet and no `8995A` sheet, so
    before the orchestrator-level guard these scenarios silently computed a
    workbook-based result with no refusal, using formula that Form 8995-A
    is supposed to replace above the threshold. These two tests pin both
    sides of the boundary at the MARRIED_JOINTLY 2025 threshold ($394,600,
    tenforty/params/federal/y2025.py) using `_make_v1_scenario`'s default
    S-corp (gross_receipts=100,000 - compensation_of_officers=30,000 =
    70,000 ordinary business income / QBI, comfortably under the $250,000
    Schedule L / M-1 attestation trigger).

    Oracle-tier (real XLSX workbook via LibreOffice): `_compute_1040_pipeline`
    only reaches the new guard by actually routing a non-SINGLE scenario
    through `_compute_1040_via_workbook`, which requires soffice -- see
    `tests/helpers.py::needs_libreoffice`. The guard's conditional logic
    itself (independent of the real workbook numbers) is additionally pinned
    without soffice by `WorkbookQbiThresholdGuardUnitTests` below, via a
    mocked `_compute_1040_via_workbook`."""

    @pytest.mark.oracle
    def test_above_threshold_non_single_raises_instead_of_silent_workbook_result(self):
        """400,000 of W-2 wages plus the 70,000 K-1 QBI-bearing income is
        470,000, minus the 2025 MFJ standard deduction (31,500), leaving
        taxable income before QBI at 438,500 -- comfortably above the
        394,600 MFJ threshold, so the margin survives any rounding. Without
        the orchestrator-level guard this scenario would route straight to
        the XLSX workbook (MARRIED_JOINTLY is out of native-spine scope) and
        compute silently via the workbook's `8995` sheet, which is not valid
        above the threshold."""
        scenario = _mfj(_make_v1_scenario(
            gross_receipts=100_000.0, compensation_of_officers=30_000.0))
        scenario = dataclasses.replace(scenario, w2s=[
            W2(
                employer="Example Employer Inc.",
                wages=400_000.0,
                federal_tax_withheld=80_000.0,
                ss_wages=176_100.0,
                ss_tax_withheld=round(176_100.0 * 0.062),
                medicare_wages=400_000.0,
                medicare_tax_withheld=round(400_000.0 * 0.0145),
            ),
        ])

        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            with self.assertRaisesRegex(
                NotImplementedError, "8995-A|8995A"
            ):
                orch.compute_federal(scenario)

    @pytest.mark.oracle
    def test_below_threshold_non_single_still_computes_via_workbook(self):
        """No added W-2 income: taxable income before QBI is the 70,000 K-1
        income minus the 2025 MFJ standard deduction (31,500) = 38,500,
        comfortably below the 394,600 MFJ threshold. QBI is still positive
        (70,000), so this scenario must NOT be refused -- the workbook's
        `8995` sheet is valid below the threshold and must keep computing
        exactly as it does today. Asserts on real computed figures (the
        exact taxable-income-before-QBI input figure, and that a positive
        QBI deduction was actually subtracted), not merely the absence of
        an exception."""
        scenario = _mfj(_make_v1_scenario(
            gross_receipts=100_000.0, compensation_of_officers=30_000.0))

        with tempfile.TemporaryDirectory() as d:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(d))
            results = orch.compute_federal(scenario)

        self.assertEqual(
            results["taxable_income_before_qbi_deduction"], 38_500)
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
    threshold) is pinned deterministically without launching soffice. Drives `_compute_1040_pipeline` directly rather than
    `compute_federal`: the guard lives entirely inside that method, and
    `_build_effective_scenario`'s S-corp waterfall / compute-time gates are
    orthogonal to it."""

    def _mfj_scenario_with_qbi(self, qbi_amount=70_000.0,
                               acknowledges_qbi_below_threshold=False):
        scenario = make_k1_scenario()
        scenario.config.filing_status = FilingStatus.MARRIED_JOINTLY
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
        scenario = self._mfj_scenario_with_qbi()
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
        scenario = self._mfj_scenario_with_qbi()
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value={"taxable_income_before_qbi_deduction": 500_000.0},
        ):
            with self.assertRaisesRegex(
                NotImplementedError, "acknowledges_qbi_below_threshold"
            ):
                self._orch()._compute_1040_pipeline(scenario)

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
        scenario = self._mfj_scenario_with_qbi(
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
        self.assertEqual(result, sentinel_result)

    def test_does_not_raise_and_passes_through_result_when_below_threshold(self):
        scenario = self._mfj_scenario_with_qbi()
        sentinel_result = {
            "taxable_income_before_qbi_deduction": 100_000.0,
            "sentinel": "unmodified",
        }
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value=sentinel_result,
        ):
            result = self._orch()._compute_1040_pipeline(scenario)
        self.assertEqual(result, sentinel_result)

    def test_does_not_raise_when_qbi_is_zero_even_above_threshold(self):
        """QBI == 0 must never trigger the guard, regardless of taxable
        income -- mirrors f8995.compute's `qbi_total > 0` condition."""
        scenario = self._mfj_scenario_with_qbi(qbi_amount=0.0)
        sentinel_result = {"taxable_income_before_qbi_deduction": 500_000.0}
        with patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            return_value=sentinel_result,
        ):
            result = self._orch()._compute_1040_pipeline(scenario)
        self.assertEqual(result, sentinel_result)
