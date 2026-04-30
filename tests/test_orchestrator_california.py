"""Tests for ReturnOrchestrator._emit_ca_pdfs_internal (SP3-T16).

Smoke test for the CA-PDF emit helper. Exercises the helper end-to-end
with a hand-assembled `ca_results` dict (manual stand-in for the T17
compute pipeline) and asserts that all three CA-state PDFs (Form 540,
Schedule CA, Schedule D 540) land on disk with non-trivial size and
under the expected dict keys.

PDF-content correctness (which compute key lands in which widget) is
owned by the per-form mapping tests already on disk
(`test_pdf_f540_mapping.py`, `test_pdf_sch_ca_mapping.py`,
`test_pdf_sch_d_540_mapping.py`). This test deliberately stays at the
emit-shape layer.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import FilingStatus, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_v1_smoke_scenario


REPO_ROOT = Path(__file__).parent.parent


def _build_minimal_ca_results(scenario: Scenario) -> dict:
    """Assemble a ca_results dict that satisfies all three CA mappings.

    Provides a value for every compute key the three CA PDF mappings
    reference (directly via `_MAPPING_2025` or via `_DERIVATIONS_2025`
    `c[...]` accesses). Numeric line items default to 0; name/SSN/address
    placeholders come from `scenario.config`.

    T17 will replace this manual assembly with the real compute pipeline:
        sch_ca_results = sch_ca.compute(effective_ca540, federal_results)
        sch_d_540_results = sch_d_540.compute(federal_results, scenario.config.__dict__)
        f540_results = f540.compute(...)
        ca_results = {**sch_ca_results, **sch_d_540_results, **f540_results,
                      **header_keys_merged_from_scenario_config}
    """
    cfg = scenario.config
    header = {
        # Form 540 page 1 header (pulled from scenario.config in T17).
        "f540_taxpayer_first_name": cfg.first_name,
        "f540_taxpayer_middle_initial": "",
        "f540_taxpayer_last_name": cfg.last_name,
        "f540_taxpayer_suffix": "",
        "f540_taxpayer_ssn": cfg.ssn,
        "f540_spouse_first_name": "",
        "f540_spouse_last_name": "",
        "f540_spouse_ssn": "",
        "f540_address_street": cfg.address,
        "f540_address_city": cfg.address_city,
        "f540_address_state": cfg.address_state,
        "f540_address_zip": cfg.address_zip,
        "f540_residence_county": "Los Angeles",
        "f540_taxpayer_email": "smoke@example.com",
        "f540_taxpayer_phone": "5555555555",
        # Schedule CA page 1 header.
        "sch_ca_taxpayer_name": f"{cfg.first_name} {cfg.last_name}",
        "sch_ca_taxpayer_ssn": cfg.ssn,
        # Schedule D 540 page 1 header.
        "sch_d_540_taxpayer_name": f"{cfg.first_name} {cfg.last_name}",
        "sch_d_540_taxpayer_ssn": cfg.ssn,
    }
    f540_numeric = {
        # Page 2 — taxable income + tax (zeroes are valid v1 smoke values;
        # the derivations clamp via max(0, ...) and won't error on 0).
        "f540_ca_agi": 0,
        "f540_deduction": 0,
        "f540_taxable_income": 0,
        "f540_ca_tax": 0,
        "f540_exemption_credit": 0,
        # Page 3 — credits + payments + use tax.
        "f540_renter_credit": 0,
        "f540_estimated_payments": 0,
        "f540_use_tax": 0,
        # Page 4 — voluntary contributions.
        "f540_voluntary_contributions": 0,
        # Page 5 — estimated tax penalty.
        "f540_estimated_tax_penalty": 0,
        # Consumed by derivations (sign-split + RB lookup).
        "f540_total_liability": 0,
        "f540_filing_status": FilingStatus.SINGLE,
    }
    sch_ca_numeric = {
        # Per-line Col A / Col B (subtractions) / Col C (additions). The
        # mapping references all of these as direct cells; missing keys
        # are silently skipped by PdfFiller.fill but enumerating them
        # keeps the smoke surface explicit.
        "sch_ca_line_part_i_a_1z_col_a": 0,
        "sch_ca_line_part_i_a_1z_subtractions": 0,
        "sch_ca_line_part_i_a_1z_additions": 0,
        "sch_ca_line_part_i_a_2_col_a": 0,
        "sch_ca_line_part_i_a_2_subtractions": 0,
        "sch_ca_line_part_i_a_2_additions": 0,
        "sch_ca_line_part_i_a_3_col_a": 0,
        "sch_ca_line_part_i_a_3_subtractions": 0,
        "sch_ca_line_part_i_a_3_additions": 0,
        "sch_ca_line_part_i_a_4_col_a": 0,
        "sch_ca_line_part_i_a_4_subtractions": 0,
        "sch_ca_line_part_i_a_4_additions": 0,
        "sch_ca_line_part_i_a_5b_col_a": 0,
        "sch_ca_line_part_i_a_5b_subtractions": 0,
        "sch_ca_line_part_i_a_5b_additions": 0,
        "sch_ca_line_part_i_a_6_col_a": 0,
        "sch_ca_line_part_i_a_6_subtractions": 0,
        "sch_ca_line_part_i_a_7_col_a": 0,
        "sch_ca_line_part_i_a_7_subtractions": 0,
        "sch_ca_line_part_i_a_7_additions": 0,
        "sch_ca_line_part_i_b_1_col_a": 0,
        "sch_ca_line_part_i_b_1_subtractions": 0,
        "sch_ca_line_part_i_b_3_col_a": 0,
        "sch_ca_line_part_i_b_3_subtractions": 0,
        "sch_ca_line_part_i_b_3_additions": 0,
        "sch_ca_line_part_i_b_4_col_a": 0,
        "sch_ca_line_part_i_b_4_subtractions": 0,
        "sch_ca_line_part_i_b_4_additions": 0,
        "sch_ca_line_part_i_b_5_col_a": 0,
        "sch_ca_line_part_i_b_5_subtractions": 0,
        "sch_ca_line_part_i_b_5_additions": 0,
        "sch_ca_line_part_i_b_6_col_a": 0,
        "sch_ca_line_part_i_b_6_subtractions": 0,
        "sch_ca_line_part_i_b_6_additions": 0,
        "sch_ca_line_part_i_b_7_col_a": 0,
        "sch_ca_line_part_i_b_7_subtractions": 0,
        "sch_ca_line_part_i_b_8z_col_a": 0,
        "sch_ca_line_part_i_b_8z_subtractions": 0,
        "sch_ca_line_part_i_b_8z_additions": 0,
        "sch_ca_line_part_i_c_11_col_a": 0,
        "sch_ca_line_part_i_c_11_subtractions": 0,
        "sch_ca_line_part_i_c_13_col_a": 0,
        "sch_ca_line_part_i_c_13_subtractions": 0,
        "sch_ca_line_part_i_c_15_col_a": 0,
        "sch_ca_line_part_i_c_15_subtractions": 0,
        "sch_ca_line_part_i_c_17_col_a": 0,
        "sch_ca_line_part_i_c_17_subtractions": 0,
        "sch_ca_line_part_i_c_20_col_a": 0,
        "sch_ca_line_part_i_c_20_subtractions": 0,
        "sch_ca_line_part_i_c_20_additions": 0,
        "sch_ca_line_part_i_c_21_col_a": 0,
        "sch_ca_line_part_i_c_21_additions": 0,
        # Page 4 line 27 — Part I totals.
        "sch_ca_federal_agi": 0,
        "sch_ca_total_subtractions": 0,
        "sch_ca_total_additions": 0,
    }
    sch_d_540_numeric = {
        # Sole sch_d_540.compute output under v1 zero-divergence
        # attestation; consumed directly by line 8 mapping and by the
        # line 10 / line 11 derivations.
        "sch_d_540_net_capital_gain": 0,
    }
    return {**header, **f540_numeric, **sch_ca_numeric, **sch_d_540_numeric}


class EmitCaPdfsInternalTests(unittest.TestCase):
    def test_emits_all_three_ca_pdfs(self):
        scenario = _make_ca_v1_smoke_scenario()
        # T17 will be responsible for merging header keys (taxpayer name/SSN)
        # into the compute results dict before calling _emit_ca_pdfs_internal.
        # Until T17 lands, this test fixture performs the merge manually.
        ca_results = _build_minimal_ca_results(scenario)

        output_dir = Path(tempfile.mkdtemp())
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work",
        )
        emitted = orchestrator._emit_ca_pdfs_internal(
            scenario=scenario,
            ca_results=ca_results,
            output_dir=output_dir,
        )

        self.assertEqual(set(emitted.keys()), {"f540", "sch_ca", "sch_d_540"})
        for path in emitted.values():
            self.assertTrue(path.exists(), f"PDF not written: {path}")
            self.assertGreater(path.stat().st_size, 1_000)


if __name__ == "__main__":
    unittest.main()
