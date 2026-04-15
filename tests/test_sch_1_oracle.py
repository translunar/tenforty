"""Cross-check Schedule 1 native compute against the XLSX oracle.

Runs the 1040 engine end-to-end on a scenario where Sch E (rental) is
the ONLY Sch 1 contributor and confirms that forms.sch_1.compute's
line 10 matches the oracle's Additional_Income (Sch. 1 AC56) output.
Scenarios with unemployment / business / farm income do not satisfy
the sole-contributor precondition and must not run this assertion —
see the @pytest.mark.only_sch_e_contributes_to_sch_1 marker.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.forms import sch_1 as form_sch_1
from tenforty.forms import sch_e as form_sch_e
from tenforty.models import RentalProperty
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round

from tests.helpers import REPO_ROOT, needs_libreoffice, make_simple_scenario


@needs_libreoffice
class Sch1OracleTests(unittest.TestCase):
    @pytest.mark.oracle
    @pytest.mark.only_sch_e_contributes_to_sch_1
    def test_line_10_matches_xlsx_additional_income(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [
            RentalProperty(
                address="101 Test St",
                property_type=1,
                fair_rental_days=365,
                personal_use_days=0,
                rents_received=24_000.0,
                mortgage_interest=8_000.0,
                taxes=3_000.0,
                depreciation=5_000.0,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(scenario)

        sch_e = form_sch_e.compute(scenario, upstream={"f1040": f1040})
        sch_1 = form_sch_1.compute(scenario, upstream={"sch_e": sch_e})

        self.assertEqual(
            sch_1["sch_1_line_10_total_additional_income"],
            irs_round(f1040["sch_1_line_10"]),
        )


if __name__ == "__main__":
    unittest.main()
