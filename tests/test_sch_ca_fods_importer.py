import unittest
from pathlib import Path

from tenforty.forms.sch_ca_fods import FodsDivergences, import_fods_divergences
from tenforty.models import (
    CASchCAAdjustment,
    CASchD540Adjustment,
    DivergenceDirection,
    DivergenceSource,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sch_ca_fods"


class ImportFodsDivergencesEmptyTests(unittest.TestCase):
    def test_empty_fods_returns_empty_dataclass(self):
        result = import_fods_divergences(FIXTURES / "empty.fods")
        self.assertEqual(result, FodsDivergences(sch_ca=[], sch_d_540=[]))


class ImportFodsDivergencesPerTabTests(unittest.TestCase):
    def test_single_tab_zero_totals_emits_no_adjustments(self):
        result = import_fods_divergences(FIXTURES / "single_tab_zero.fods")
        self.assertEqual(result.sch_ca, [])
        self.assertEqual(result.sch_d_540, [])

    def test_single_tab_subtraction_emits_one_subtraction(self):
        result = import_fods_divergences(FIXTURES / "single_tab_subtraction.fods")
        self.assertEqual(len(result.sch_ca), 1)
        self.assertEqual(result.sch_d_540, [])
        adj = result.sch_ca[0]
        self.assertEqual(adj.source, DivergenceSource.WORKSHEET)
        self.assertEqual(adj.sch_ca_line, "Part I §A 2")
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.amount, 123.0)

    def test_two_tabs_mixed_emits_one_per_non_zero_total(self):
        result = import_fods_divergences(FIXTURES / "two_tabs_mixed.fods")
        self.assertEqual(len(result.sch_ca), 2)
        self.assertEqual(result.sch_d_540, [])
        by_line = {a.sch_ca_line: a for a in result.sch_ca}
        self.assertEqual(by_line["Part I §A 2"].direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(by_line["Part I §A 2"].amount, 500.0)
        self.assertEqual(by_line["Part I §B 8z"].direction, DivergenceDirection.ADDITION)
        self.assertEqual(by_line["Part I §B 8z"].amount, 200.0)

    def test_extra_user_rows_does_not_corrupt_total(self):
        result = import_fods_divergences(FIXTURES / "extra_user_rows.fods")
        self.assertEqual(len(result.sch_ca), 1)
        adj = result.sch_ca[0]
        self.assertEqual(adj.amount, 123.0)
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.sch_ca_line, "Part I §A 2")

    def test_sch_d_540_tab_routes_to_sch_d_540_list(self):
        result = import_fods_divergences(FIXTURES / "single_tab_sch_d_540.fods")
        self.assertEqual(result.sch_ca, [])
        self.assertEqual(len(result.sch_d_540), 1)
        adj = result.sch_d_540[0]
        self.assertIsInstance(adj, CASchD540Adjustment)
        self.assertEqual(adj.source, DivergenceSource.WORKSHEET)
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.amount, 750.0)
