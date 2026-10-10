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


def _scenario(k1_rental_loss: float):
    """An income rental (net 3,000) and one passive partnership K-1 whose
    rental real estate box is ``k1_rental_loss``. Invented figures."""
    s = make_k1_scenario()
    s.rental_properties = [RentalProperty(
        address="1 Test St", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=5_000.0, mortgage_interest=2_000.0,
    )]
    s.schedule_k1s = [ScheduleK1(
        entity_name="Example LLC", entity_ein="00-0000000",
        entity_type="partnership", material_participation=False,
        net_rental_real_estate=k1_rental_loss,
    )]
    return s


def _native_f8582(s, f1040: dict) -> dict:
    sch_e = form_sch_e.compute(s, upstream={"f1040": f1040})
    _part_ii_fields, fanout = form_sch_e_part_ii.compute(s, upstream={})
    return form_f8582.compute(s, upstream={
        "f1040": f1040, "sch_e": sch_e, "k1_fanout": fanout,
    })


@needs_libreoffice
class F8582OracleTests(unittest.TestCase):
    """Two cases, because the return itself now refuses when Form 8582 binds
    (passive_loss_limitation_not_applied): the allowed loss is computed but
    not applied to the return.

    * NON-BINDING, end to end: ``compute_federal`` on a loss Form 8582 allows
      in full, so the spine -> Form 8582 wiring stays workbook-compared.
    * BINDING, form level: the suspended-loss arithmetic stays
      workbook-compared by evaluating the workbook directly and feeding its
      result to the native form compute -- ``compute_federal`` would refuse.
    """

    @pytest.mark.oracle
    def test_line_11_matches_xlsx(self):
        # K-1 loss 28,000 against rental income 3,000 + the 25,000 allowance:
        # allowed in full, nothing suspended.
        s = _scenario(-28_000.0)
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(s)
            workbook = orch._compute_1040_via_workbook(s)

        native = _native_f8582(s, f1040)
        self.assertEqual(native["f8582_line_11_allowed_loss"], 28_000)
        # The return's own figure (this single filer computes on the native
        # spine, so this key is the spine's pass-through of Form 8582) ...
        self.assertEqual(
            native["f8582_line_11_allowed_loss"],
            round(f1040["f8582_line_11_oracle"]),
        )
        # ... and the workbook's, evaluated separately.
        self.assertEqual(
            native["f8582_line_11_allowed_loss"],
            round(workbook["f8582_line_11_oracle"]),
        )

    @pytest.mark.oracle
    def test_line_11_matches_xlsx_when_the_limitation_binds(self):
        # K-1 loss 30,000: 2,000 more than income + allowance, so part is
        # suspended. The native return refuses this shape, so the workbook is
        # evaluated directly (no native spine) and its figures are the
        # explicitly assembled upstream for the native Form 8582 compute.
        s = _scenario(-30_000.0)
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            with self.assertRaisesRegex(
                    NotImplementedError, "Form 8582 limitation"):
                orch.compute_federal(s)
            workbook = orch._compute_1040_via_workbook(s)

        # The workbook result carries no `magi` key; Form 8582's modified AGI
        # input is AGI here (no tax-exempt interest or other add-backs).
        native = _native_f8582(s, {**workbook, "magi": workbook["agi"]})
        self.assertLess(
            native["f8582_line_11_allowed_loss"],
            native["f8582_line_1b_activities_with_loss"])
        self.assertEqual(
            native["f8582_line_11_allowed_loss"],
            round(workbook["f8582_line_11_oracle"]),
        )


if __name__ == "__main__":
    unittest.main()
