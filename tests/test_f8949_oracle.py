"""XLSX oracle cross-check: f8949.compute subsection totals match the
federal workbook's 8949A/B/C/D sheet named-range outputs.

Note on partitioning: ``f8949.compute`` emits per-box subsection totals
over 8949-path lots only. The flattener writes per-lot 8949 keys for
8949-path lots only (aggregate-path lots flow to Sch D 1a/8a cells).
Thus the workbook's 8949 sheet totals and the native subsection totals
agree by construction.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f8949
from tenforty.models import Form1099B, Scenario, TaxReturnConfig
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import (
    SPREADSHEETS_DIR, needs_libreoffice, scope_out_attestation_defaults,
)


@needs_libreoffice
class TestF8949XlsxOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_dir = Path(tempfile.mkdtemp())
        # has_foreign_accounts and prior_year_itemized are included in
        # scope_out_attestation_defaults(); pass only non-overlapping fields here.
        cfg = TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            first_name="Taxpayer", last_name="A", ssn="000-00-0000",
            **scope_out_attestation_defaults(),
        )
        # Use 8949-path lots (Box B short non-covered; Box E long non-covered)
        # so the workbook's 8949 sheet totals are populated and agree with
        # native totals. Clean Box-A/D lots aggregate directly to Sch D
        # 1a/8a in both paths, leaving box-letter totals at zero in both —
        # a vacuous cross-check.
        cls.scenario = Scenario(
            config=cfg,
            form1099_b=[
                Form1099B(
                    broker="Brokerage Inc", description="NonCovST",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=1500.0, cost_basis=1000.0,
                    short_term=True, basis_reported_to_irs=False,
                ),
                Form1099B(
                    broker="Brokerage Inc", description="NonCovLT",
                    date_acquired="2022-03-15", date_sold="2025-08-10",
                    proceeds=10000.0, cost_basis=6000.0,
                    short_term=False, basis_reported_to_irs=False,
                ),
            ],
        )
        cls.orch = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=cls.work_dir,
        )
        cls.oracle = cls.orch.compute_federal(cls.scenario)
        cls.native = f8949.compute(cls.scenario, upstream={})

    def test_box_b_total_matches_oracle(self) -> None:
        self.assertEqual(
            self.native["f8949_box_b_total_gain"],
            int(self.oracle.get("f8949_box_b_total_gain", 0)),
        )

    def test_box_e_total_matches_oracle(self) -> None:
        self.assertEqual(
            self.native["f8949_box_e_total_gain"],
            int(self.oracle.get("f8949_box_e_total_gain", 0)),
        )

    # The net_short/net_long aggregates emitted by f8949.compute have no
    # dedicated XLS named range (the workbook tracks per-sheet ST/LT totals
    # only). Per-box cross-checks above already exercise the same arithmetic
    # for the chosen fixture (one lot per box → box total == net), so
    # separate net_*_matches_oracle tests would be redundant.
