import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f1120s
from tenforty.models import (
    Address, EntityType, Form1099INT, K1Allocation, K1AllocationEntity,
    K1AllocationShareholder, W2,
)
from tenforty.orchestrator import ReturnOrchestrator, _make_k1_from_1120s_allocation
from tests._scorp_fixtures import _make_v1_scenario


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
