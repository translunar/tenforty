"""Cross-check Schedule B native compute against the XLSX oracle.

Exercises the 1040 engine end-to-end on a scenario with 1099-INT/DIV
inputs and confirms that forms.sch_b.compute produces totals consistent
with the oracle's 1040 outputs after IRS rounding.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.forms.sch_b import compute as sch_b_compute
from tenforty.models import Form1099DIV, Form1099INT
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round

from tests.helpers import REPO_ROOT, needs_libreoffice, make_simple_scenario


@needs_libreoffice
class SchBOracleTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_sch_b_totals_match_1040_engine_outputs(self):
        scenario = make_simple_scenario()
        # The 2025 1040 oracle workbook wires a single 1099-INT / 1099-DIV
        # payer slot; multi-payer aggregation is our Python side's job
        # (tested directly in test_sch_b_compute). Here we just confirm the
        # native compute matches the oracle's totals when there's one payer.
        scenario.form1099_int = [
            Form1099INT(payer="Bank A", interest=1200.0),
        ]
        scenario.form1099_div = [
            Form1099DIV(payer="Broker", ordinary_dividends=2000.0),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040_result = orch.compute_federal(scenario)
        sch_b = sch_b_compute(scenario, upstream={"f1040": f1040_result})

        self.assertEqual(
            sch_b["total_interest"],
            irs_round(f1040_result["taxable_interest"]),
        )
        self.assertEqual(
            sch_b["total_ordinary_dividends"],
            irs_round(f1040_result["ordinary_dividends"]),
        )


if __name__ == "__main__":
    unittest.main()
