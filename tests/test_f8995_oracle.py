"""Cross-check forms.f8995 against the XLSX oracle end-to-end."""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.forms import f8995 as form_f8995
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator

from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice


@needs_libreoffice
class F8995OracleTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_line_15_matches_xlsx(self):
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
            qbi_amount=50_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(s)

        _sch_e_part_ii_fields, fanout = form_sch_e_part_ii.compute(s, upstream={})
        upstream = {
            "f1040": f1040,
            "k1_fanout": fanout,
        }
        native = form_f8995.compute(s, upstream=upstream)
        self.assertEqual(
            native["f8995_line_15_qbi_deduction"],
            round(f1040["f8995_line_15_oracle"]),
        )


if __name__ == "__main__":
    unittest.main()
