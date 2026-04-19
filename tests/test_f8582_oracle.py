"""Cross-check forms.f8582 against the XLSX oracle end-to-end."""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.forms import f8582 as form_f8582
from tenforty.forms import sch_e as form_sch_e
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import RentalProperty, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator

from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice


@needs_libreoffice
class F8582OracleTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_line_11_matches_xlsx(self):
        s = make_k1_scenario()
        s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=5_000.0, mortgage_interest=2_000.0,
        )]
        s.schedule_k1s = [ScheduleK1(
            entity_name="Example LLC", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
            net_rental_real_estate=-30_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(s)

        sch_e = form_sch_e.compute(s, upstream={"f1040": f1040})
        part_ii = form_sch_e_part_ii.compute(s, upstream={})
        native = form_f8582.compute(s, upstream={
            "f1040": f1040,
            "sch_e": sch_e,
            "_k1_fanout": part_ii["_k1_fanout"],
        })
        self.assertEqual(
            native["f8582_line_11_allowed_loss"],
            round(f1040["f8582_line_11_oracle"]),
        )


if __name__ == "__main__":
    unittest.main()
