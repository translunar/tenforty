"""Native-path producers for the 1040 tax band: lines 17, 18 and 24.

Before these landed, `schedule2_tax` (line 17), `tax_plus_schedule2` (line 18)
and the line-24 total-tax box were mapped to PDF fields in all five year blocks
of `mappings/pdf_1040.py` and produced by NOTHING on the native path, so all
three printed BLANK on every 1040 the spine emitted — including on a return
that attaches a Schedule 2 for an excess-advance-PTC repayment, which then
contradicted itself on its own face.

These tests drive `ReturnOrchestrator.compute_federal` (native spine; no
LibreOffice) and then the real PDF field resolution, because the defect being
guarded was about what the FILED FORM SHOWS, not only about dict values. A test
asserting `schedule2_tax == 0` would have passed throughout the whole period
line 17 printed blank.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round
from tenforty.years import FEDERAL_YEARS
from tests.helpers import scope_out_attestation_defaults

REPO_ROOT = Path(__file__).parent.parent

YEAR = 2025


def _scenario(wages: float, withheld: float, form_1095a=None) -> Scenario:
    """Single-filer W-2-only scenario, above the EIC income ceiling so it
    routes to the native spine rather than the workbook fallback."""
    return Scenario(
        config=TaxReturnConfig(
            year=YEAR,
            filing_status="single",
            birthdate="1990-06-15",
            state="TX",
            **scope_out_attestation_defaults(),
        ),
        w2s=[
            W2(
                employer="Acme Corp",
                wages=wages,
                federal_tax_withheld=withheld,
                ss_wages=wages,
                ss_tax_withheld=round(wages * 0.062),
                medicare_wages=wages,
                medicare_tax_withheld=round(wages * 0.0145),
            ),
        ],
        form_1095a=form_1095a,
    )


def _months(premium: float, slcsp: float, aptc: float):
    return tuple(
        Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc) for _ in range(12)
    )


def _repayment_block() -> Form1095A:
    """APTC far above entitlement -> a nonzero excess-APTC repayment, which is
    the only Schedule 2 Part I component the native spine models."""
    return Form1095A(months=_months(premium=500, slcsp=500, aptc=400))


class _NativeComputeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _fields(self, results: dict, year: int = YEAR) -> dict[str, str]:
        """The exact {pdf_field_path: rendered_string} dict the 1040 emit would
        write. Built through the same `PdfFiller.resolve_fields` the render and
        the changed-forms selector use, and with the same derivations the
        orchestrator passes for the 1040 spec, so it cannot drift from what
        actually fills."""
        return PdfFiller.resolve_fields(
            Pdf1040.get_mapping(year),
            results,
            derivations=Pdf1040.get_derivations(year),
        )


class NativeSchedule2LineProducersTests(_NativeComputeCase):
    def test_line_17_is_the_excess_aptc_repayment_and_line_18_adds_it_to_16(self):
        with_block = self.orch.compute_federal(
            _scenario(55_000, 8_000, _repayment_block()))
        without = self.orch.compute_federal(_scenario(55_000, 8_000, None))

        repayment = with_block["f8962_repayment"]
        self.assertGreater(repayment, 0)

        # Line 17 = Schedule 2 line 3. The spine models exactly one of its two
        # components (the repayment); the other, AMT, is guarded by the
        # `acknowledges_no_federal_amt` attestation.
        self.assertEqual(repayment, with_block["schedule2_tax"])

        # Line 18 = "Add lines 16 and 17".
        self.assertEqual(
            with_block["total_tax"] + with_block["schedule2_tax"],
            with_block["tax_plus_schedule2"],
        )

        # ...and line 18 genuinely MOVED, so the assertion above is not
        # satisfiable by line 18 having silently stayed equal to line 16.
        self.assertNotEqual(with_block["total_tax"], with_block["tax_plus_schedule2"])

        # Line 16 is UNCHANGED by the Schedule 2 addition. This is the whole
        # point of the unit: `total_tax` means line 16 on every path.
        self.assertEqual(without["total_tax"], with_block["total_tax"])

    def test_line_17_and_18_print_rather_than_going_blank(self):
        results = self.orch.compute_federal(
            _scenario(55_000, 8_000, _repayment_block()))
        fields = self._fields(results)
        mapping = Pdf1040.get_mapping(YEAR)

        line_17_box = mapping["schedule2_tax"]
        line_18_box = mapping["tax_plus_schedule2"]
        self.assertIn(line_17_box, fields)
        self.assertIn(line_18_box, fields)
        self.assertEqual(str(irs_round(results["schedule2_tax"])), fields[line_17_box])
        self.assertEqual(
            str(irs_round(results["tax_plus_schedule2"])), fields[line_18_box])


class NativeSchedule2ZeroPrintsZeroTests(_NativeComputeCase):
    """The no-Schedule-2 case, asserting the PRINTED CONVENTION.

    `PdfFiller.resolve_fields` renders 0 but SKIPS None, so a line-17 producer
    that emitted None instead of 0 would leave the box blank while every
    dict-level assertion about "no Schedule 2 tax" still passed. The workbook
    path settled this convention from the other side by normalizing a blank
    `Schedule2_Tax` harvest to 0 (`forms/f1040.py::compute`); the native path
    has to reach the same printed result or the two paths disagree about what
    an empty Schedule 2 looks like on paper.
    """

    def test_empty_schedule_2_prints_a_literal_zero_in_the_line_17_box(self):
        results = self.orch.compute_federal(_scenario(55_000, 8_000, None))
        self.assertEqual(0, results["schedule2_tax"])
        self.assertIsNotNone(results["schedule2_tax"])

        fields = self._fields(results)
        line_17_box = Pdf1040.get_mapping(YEAR)["schedule2_tax"]
        self.assertIn(line_17_box, fields)
        self.assertEqual("0", fields[line_17_box])

    def test_line_18_equals_line_16_when_there_is_no_schedule_2(self):
        results = self.orch.compute_federal(_scenario(55_000, 8_000, None))
        self.assertEqual(results["total_tax"], results["tax_plus_schedule2"])
        self.assertGreater(results["total_tax"], 0)


class NativeLine24TotalTaxTests(_NativeComputeCase):
    """1040 line 24 on the native path, filled by `Pdf1040.get_derivations`.

    The scenario carries BOTH a Schedule 2 Part I item (excess-APTC repayment)
    and a Schedule 2 Part II item (Form 8959 Additional Medicare Tax, from
    wages above the $200,000 single threshold). That combination is what makes
    the assertion discriminating: with Part II zero, line 24 collapses to line
    18 and the test could not tell the two apart.
    """

    def _high_wage_results(self) -> dict:
        return self.orch.compute_federal(
            _scenario(250_000, 40_000, _repayment_block()))

    def test_line_24_box_is_filled_and_carries_line_24_semantics(self):
        results = self._high_wage_results()
        self.assertGreater(results["schedule2_tax"], 0)
        self.assertGreater(results["f8959_tax_total"], 0)

        # Hand-written oracle, deliberately NOT a call to the production
        # helper: line 22 = MAX(0, line 18 - nonrefundable credits), and line
        # 24 = line 22 + Schedule 2 Part II. The zero floor sits on line 22
        # ALONE — flooring the whole sum instead would swallow a Part II tax
        # the filer owes. The native spine models no nonrefundable credits, so
        # line 21 is zero here and line 22 reduces to line 18; the floor is
        # written out anyway so this oracle stays right if credits ever appear.
        line_18 = results["total_tax"] + results["schedule2_tax"]
        line_22 = max(0, line_18 - 0)
        expected_line_24 = line_22 + results["f8959_tax_total"]

        # Distinguishable from its neighbours, so an off-by-one-line producer
        # cannot pass: Part II is nonzero, so line 24 != line 18 != line 16.
        self.assertNotEqual(line_18, expected_line_24)
        self.assertNotEqual(results["total_tax"], line_18)

        fields = self._fields(results)
        line_24_box = Pdf1040.get_mapping(YEAR)["tax_liability_line24"]
        self.assertIn(line_24_box, fields)
        self.assertEqual(str(irs_round(expected_line_24)), fields[line_24_box])

    def test_line_24_box_is_filled_on_a_plain_return_too(self):
        """No Schedule 2 at all: line 24 must still print, and equal line 16.

        Guards the failure this task exists to remove — the box printing blank
        — in the common case, where the two Schedule 2 components are both
        zero and a producer that silently dropped out would be invisible in
        the arithmetic."""
        results = self.orch.compute_federal(_scenario(55_000, 8_000, None))
        fields = self._fields(results)
        line_24_box = Pdf1040.get_mapping(YEAR)["tax_liability_line24"]
        self.assertIn(line_24_box, fields)
        self.assertEqual(str(irs_round(results["total_tax"])), fields[line_24_box])
        self.assertNotEqual("", fields[line_24_box])


class Line24KeyNameReconciliationTests(unittest.TestCase):
    """One name for 1040 line 24, across the PDF mapping and the harvest.

    `total_tax_liability` (the pdf_1040 field key) and `tax_liability_line24`
    (the F1040 workbook-harvest OUTPUT key, and `forms/f4868.py`'s
    `_LINE_24_KEY`) both named 1040 line 24 at once. The negative assertion
    below has genuinely reachable negative space: `total_tax_liability` WAS
    present in every year block of this mapping until this change, so its
    absence is a fact about the rename, not about a name that never existed.
    """

    def test_every_year_maps_line_24_under_the_reconciled_name_only(self):
        for year in FEDERAL_YEARS:
            with self.subTest(year=year):
                mapping = Pdf1040.get_mapping(year)
                self.assertIn("tax_liability_line24", mapping)
                self.assertNotIn("total_tax_liability", mapping)

    # Line 24's amount box, per year, written out as LITERALS rather than read
    # back out of the mapping under test. Reading them from `get_mapping`
    # would make this assertion agree with the mapping by construction; these
    # were transcribed from the per-year blocks and match the independent pins
    # in tests/test_pdf_mapping.py.
    _LINE_24_BOX = {
        2021: "topmostSubform[0].Page2[0].f2_10[0]",
        2022: "topmostSubform[0].Page2[0].f2_10[0]",
        2023: "topmostSubform[0].Page2[0].f2_10[0]",
        2024: "topmostSubform[0].Page2[0].f2_15[0]",
        2025: "topmostSubform[0].Page2[0].f2_16[0]",
    }

    def test_the_reconciled_key_maps_to_the_line_24_box_in_every_year(self):
        for year in FEDERAL_YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    self._LINE_24_BOX[year],
                    Pdf1040.get_mapping(year)["tax_liability_line24"],
                )

    def test_the_derivation_targets_the_line_24_box_and_nothing_else(self):
        """Both halves matter. That the derivation is NONEMPTY is what stops
        line 24 printing blank on the native path; that it targets ONLY the
        line-24 box is what stops a derivation from quietly overwriting some
        other cell the 1:1 mapping already fills correctly."""
        for year in FEDERAL_YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    {self._LINE_24_BOX[year]},
                    set(Pdf1040.get_derivations(year)),
                )


if __name__ == "__main__":
    unittest.main()
