"""Fill-and-reread integration test for the 2025 Form 1040 PDF mapping.

Ground truth (field name -> form line) was transcribed from the probe rendered
by scripts/probe_pdf_fields.py. The 2025 form shifted field numbers relative
to the mapping that was originally committed. Update these assertions whenever
the IRS re-issues the form and field numbers shift again.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.models import (
    FilingStatus,
    Form1099DIV,
    Form1099INT,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator

from tests.helpers import needs_libreoffice, scope_out_attestation_defaults

REPO_ROOT = Path(__file__).parent.parent
F1040_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040.pdf"


def _build_synthetic_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01",
            state="CA",
            first_name="Alice",
            last_name="Example",
            ssn="000-00-0001",
            address="1 Test Street",
            address_city="Testville",
            address_state="TX",
            address_zip="00001",
            acknowledges_no_540nr_filing=False,
            acknowledges_no_ca_amt_preferences=False,
            acknowledges_no_ca_nol_carryover=False,
            acknowledges_no_ca_depreciation_divergence=False,
            acknowledges_no_ca_ira_basis_divergence=False,
            acknowledges_no_ca_rdp_status=False,
            acknowledges_no_excess_business_loss_carryover=False,
            acknowledges_no_1031_personal_property_divergence=False,
            acknowledges_no_ic_worker_reclassification=False,
            acknowledges_no_other_state_tax_credit=False,
            acknowledges_no_railroad_retirement_benefits=False,
            acknowledges_no_paid_family_leave_benefits=False,
        ),
        w2s=[
            W2(
                employer="Tech Corp",
                wages=12350.00,
                federal_tax_withheld=1550.00,
                ss_wages=12350.00,
                ss_tax_withheld=750.00,
                medicare_wages=12350.00,
                medicare_tax_withheld=200.00,
            )
        ],
        form1099_int=[Form1099INT(payer="National Bank", interest=150.00)],
        form1099_div=[
            Form1099DIV(
                payer="Investment Brokerage",
                ordinary_dividends=250.00,
                qualified_dividends=200.00,
            )
        ],
    )


# Drives the orchestrator's workbook/oracle path (compute_federal on an out-of-native-spine scenario) → requires LibreOffice; oracle-tier.
@needs_libreoffice
@unittest.skipUnless(F1040_TEMPLATE.exists(), "f1040.pdf template not found")
class TestPdf1040FillGroundTruth(unittest.TestCase):
    """Pin field-name -> value routing against the 2025 form revision."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        out_dir = Path(cls._tmpdir)
        scenario = _build_synthetic_scenario()
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=out_dir / "work",
        )
        cls.results = orch.compute_federal(scenario)
        emitted = orch.emit_pdfs(scenario, cls.results, out_dir)
        reader = pypdf.PdfReader(str(emitted["1040"]))
        fields = reader.get_fields() or {}
        cls.field_values = {
            name: (field.get("/V") or "") for name, field in fields.items()
        }

    def _assert_field(self, field_name: str, expected: str):
        actual = self.field_values.get(field_name, "<missing>")
        self.assertEqual(
            actual, expected,
            f"Field {field_name} expected {expected!r} got {actual!r}",
        )

    # === PAGE 1 ===
    def test_line_1a_wages(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_47[0]", "12350")

    def test_line_2b_taxable_interest(self):
        # Translation: engine `interest_income` -> `taxable_interest`.
        self._assert_field("topmostSubform[0].Page1[0].f1_59[0]", "150")

    def test_line_3b_ordinary_dividends(self):
        # Translation: engine `dividend_income` -> `ordinary_dividends`.
        self._assert_field("topmostSubform[0].Page1[0].f1_61[0]", "250")

    def test_line_9_total_income(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_73[0]", "12750")

    def test_line_11a_agi(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_75[0]", "12750")

    def test_line_7a_capital_gain_left_blank(self):
        # Engine produces no `capital_gain_loss` key for this W-2 scenario;
        # Schedule D line 16 is surfaced as `schd_line16` but no translation
        # rename wires it. Field f1_70 must stay blank — regression guard
        # against accidental routing of total_income here, which is the bug
        # that motivated this fix.
        self._assert_field("topmostSubform[0].Page1[0].f1_70[0]", "")

    # === PAGE 2 ===
    # Page 2 lines 16-35a were off-by-one (16-26) and off-by-two (27a-35a)
    # relative to the current form revision. These assertions pin them.
    def test_line_11b_agi_copy(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_01[0]", "12750")

    def test_line_12e_standard_deduction(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_02[0]", "15750")

    def test_line_14_deductions_plus_qbi(self):
        # Line 14 = deductions_plus_qbi = line 12c + line 13 (QBI deduction).
        # This scenario (EIC-eligible single filer, routed to the oracle/
        # workbook path via _compute_1040_via_workbook) has QBI = 0, so the
        # value is unchanged from the standard deduction (15750). Before the
        # Bug #6 normalize fix, f1040.py::compute() never emitted
        # `deductions_plus_qbi` on the oracle path and this field printed
        # blank on every oracle-routed 1040.
        self._assert_field("topmostSubform[0].Page2[0].f2_05[0]", "15750")

    def test_line_15_taxable_income(self):
        # 12750 - 15750 < 0 -> 0
        self._assert_field("topmostSubform[0].Page2[0].f2_06[0]", "0")

    def test_line_16_total_tax(self):
        # Regression guard: f2_07 is the 8814/4972 checkbox on line 16,
        # NOT the amount. Line 16 amount is f2_08. Tax on 0 taxable = 0.
        self._assert_field("topmostSubform[0].Page2[0].f2_08[0]", "0")

    def test_line_24_total_tax_liability_blank(self):
        # Engine doesn't produce `total_tax_liability` for this scenario
        # (total tax = 0). Field must stay blank — regression guard against
        # e.g. `overpaid` (2034) accidentally routing here.
        self._assert_field("topmostSubform[0].Page2[0].f2_16[0]", "")

    def test_line_25a_federal_withheld_w2(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_17[0]", "1550")

    def test_line_25d_federal_withheld_total(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_20[0]", "1550")

    def test_line_33_total_payments(self):
        # 1550 W-2 withholding + 484 EIC (single, $12,350 AGI, no kids).
        self._assert_field("topmostSubform[0].Page2[0].f2_29[0]", "2034")

    def test_line_34_overpaid(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_30[0]", "2034")


def _build_oracle_routed_qbi_scenario() -> Scenario:
    """Single filer, wages low enough to be EIC-eligible (out of native-spine
    scope -> routes to `_compute_1040_via_workbook`, the oracle path Bug #6
    fixes), plus an S-corp K-1 so Form 8995 yields a nonzero QBI deduction —
    the case the native-spine-only ground-truth tests above (which drive
    `compute_spine` in scope, never the oracle translation in `f1040.py`)
    cannot exercise.

    Wages $8,000 + K-1 ordinary business income $10,000 -> AGI $18,000,
    comfortably under the 2025 single/0-dependent EIC-ceiling-gate estimate
    ($26,214), so `_scenario_in_spine_scope` is False. QBI deduction is
    $450 (20% of the $2,250 taxable-income-before-QBI, the binding limit —
    not 20% of the $10,000 QBI itself).
    """
    defaults = scope_out_attestation_defaults()
    for name in (
        "acknowledges_qbi_below_threshold",
        "acknowledges_unlimited_at_risk",
        "basis_tracked_externally",
        "acknowledges_no_partnership_se_earnings",
        "acknowledges_no_section_1231_gain",
        "acknowledges_no_more_than_four_k1s",
        "acknowledges_no_k1_credits",
        "acknowledges_no_section_179",
        "acknowledges_no_estate_trust_k1",
    ):
        defaults[name] = True
    defaults["prior_year_itemized"] = False
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01",
            state="TX",
            first_name="Carla",
            last_name="Example",
            ssn="000-00-0004",
            **defaults,
        ),
        w2s=[
            W2(
                employer="Synthetic Employer",
                wages=8_000.00,
                federal_tax_withheld=500.00,
                ss_wages=8_000.00,
                ss_tax_withheld=496.00,
                medicare_wages=8_000.00,
                medicare_tax_withheld=116.00,
            )
        ],
        schedule_k1s=[ScheduleK1(
            entity_name="Fake S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=10_000.00,
            qbi_amount=10_000.00,
        )],
    )


# Drives the orchestrator's workbook/oracle path (compute_federal on an out-of-native-spine scenario) → requires LibreOffice; oracle-tier.
@needs_libreoffice
@unittest.skipUnless(F1040_TEMPLATE.exists(), "f1040.pdf template not found")
class TestPdf1040FillOraclePathQbiConsistency(unittest.TestCase):
    """Bug #6 regression: the ORACLE path (`_compute_1040_via_workbook` ->
    `forms.f1040.compute`) with a real QBI deduction, read back from the
    ACTUAL emitted PDF boxes — not the native spine (`compute_spine`), which
    the ground-truth tests above exercise and which never had this bug.
    Before the normalize fix, `deductions_plus_qbi`/`total_deductions` were
    simply absent from the oracle path's translated dict, so line 14 printed
    blank on every oracle-routed 1040 with real QBI (or without, per the
    ground-truth test above).

    PARITY_KEYS finding (tests/test_f1040_spine_oracle.py): `total_deductions`
    IS a member of PARITY_KEYS, and that gate's comparison calls
    `_compute_1040_via_workbook` directly (bypassing the spine-scope routing
    gate), so a QBI>0 parity scenario WOULD have caught this asymmetry (pre-
    fix, the oracle side would have been 14-inclusive against the native
    side's 12c-exclusive value, and the two never match by construction).
    It never tripped only because none of the battery scenarios in
    tests/fixtures/spine_battery.py carries any K-1/QBI income —
    `build_qbi_threshold_boundary` is explicitly QBI-FREE by construction
    (its own docstring: "no K-1 QBI is present and the scenario has no
    QBI-generating pass-through"), and no other battery builder attaches
    `schedule_k1s` at all. The gap was structural (no QBI-bearing parity
    fixture existed), not a hole in the gate's own logic."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        out_dir = Path(cls._tmpdir)
        scenario = _build_oracle_routed_qbi_scenario()
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=out_dir / "work",
        )
        cls.orch = orch
        cls.scenario = scenario
        cls.results = orch.compute_federal(scenario)
        emitted = orch.emit_pdfs(scenario, cls.results, out_dir)
        reader = pypdf.PdfReader(str(emitted["1040"]))
        fields = reader.get_fields() or {}
        cls.field_values = {
            name: (field.get("/V") or "") for name, field in fields.items()
        }

    def _field(self, field_name: str) -> float:
        raw = self.field_values.get(field_name, "")
        return float(raw.replace(",", "").replace("$", "")) if raw else 0.0

    def test_scenario_is_oracle_routed(self):
        # Confirm the routing claim rather than assume it: single filer,
        # low enough AGI estimate to fail the native spine's EIC-ceiling
        # gate -> _compute_1040_pipeline falls back to
        # _compute_1040_via_workbook (the oracle path).
        eff, _ = self.orch._build_effective_scenario(self.scenario)
        self.assertFalse(self.orch._scenario_in_spine_scope(eff))

    def test_qbi_deduction_is_nonzero(self):
        self.assertGreater(self.results["qbi_deduction"], 0)

    def test_line_14_equals_line_12_plus_line_13(self):
        # Line 12 (applied_deduction, f2_02) + Line 13a (qbi_deduction,
        # f2_03) must equal Line 14 (deductions_plus_qbi, f2_05) — read from
        # the ACTUAL emitted boxes, independently of the results dict.
        line_12 = self._field("topmostSubform[0].Page2[0].f2_02[0]")
        line_13 = self._field("topmostSubform[0].Page2[0].f2_03[0]")
        line_14 = self._field("topmostSubform[0].Page2[0].f2_05[0]")
        self.assertGreater(line_13, 0)
        self.assertEqual(line_12 + line_13, line_14)

    def test_line_15_equals_line_11_minus_line_14(self):
        # Line 11 (AGI, f2_01) minus Line 14 (deductions_plus_qbi, f2_05)
        # must equal Line 15 (taxable_income, f2_06) — again read from the
        # actual boxes.
        line_11 = self._field("topmostSubform[0].Page2[0].f2_01[0]")
        line_14 = self._field("topmostSubform[0].Page2[0].f2_05[0]")
        line_15 = self._field("topmostSubform[0].Page2[0].f2_06[0]")
        self.assertEqual(line_11 - line_14, line_15)


if __name__ == "__main__":
    unittest.main()
