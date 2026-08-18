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

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator, _FederalFormSpec
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

    def _spec_1040(self, scenario: Scenario, results: dict) -> _FederalFormSpec:
        """The orchestrator's OWN prepared 1040 emit spec.

        Taken from `_federal_individual_emit_specs` rather than reassembled
        here, because the wiring is part of what these tests have to protect.
        An earlier version of this helper called `Pdf1040.get_mapping` and
        `Pdf1040.get_derivations` itself and claimed it therefore "could not
        drift from what actually fills" — which was FALSE, and provably so:
        deleting `derivations=Pdf1040.get_derivations(year)` from the
        orchestrator's 1040 spec left the whole always-running gate byte-for-
        byte green while every emitted 1040 went back to a blank line 24. A
        test that rebuilds the wiring cannot see the wiring removed.
        """
        specs = self.orch._federal_individual_emit_specs(scenario, results)
        spec = next(s for s in specs if s.name == "1040")
        # The wiring assertion itself, sited where every payload-based test
        # below passes through it: if the orchestrator stops handing the 1040
        # its derivations, line 24 silently reverts to blank, so an empty
        # derivations dict is a defect and not merely an absent optional.
        self.assertTrue(
            spec.derivations,
            "the orchestrator's 1040 spec carries no derivations — 1040 line "
            "24 has no other producer and would print blank",
        )
        return spec

    def _fields(self, scenario: Scenario, results: dict) -> dict[str, str]:
        """The exact {pdf_field_path: rendered_string} dict the 1040 emit would
        write, resolved through the orchestrator's own spec and its own
        `_federal_spec_payload` — the same call the renderer and the
        changed-forms selector go through."""
        return ReturnOrchestrator._federal_spec_payload(
            self._spec_1040(scenario, results))


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
        scenario = _scenario(55_000, 8_000, _repayment_block())
        results = self.orch.compute_federal(scenario)
        fields = self._fields(scenario, results)
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
        scenario = _scenario(55_000, 8_000, None)
        results = self.orch.compute_federal(scenario)
        self.assertEqual(0, results["schedule2_tax"])
        self.assertIsNotNone(results["schedule2_tax"])

        fields = self._fields(scenario, results)
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

    def _high_wage(self) -> tuple[Scenario, dict]:
        scenario = _scenario(250_000, 40_000, _repayment_block())
        return scenario, self.orch.compute_federal(scenario)

    def test_line_24_box_is_filled_and_carries_line_24_semantics(self):
        scenario, results = self._high_wage()
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

        fields = self._fields(scenario, results)
        line_24_box = Pdf1040.get_mapping(YEAR)["tax_liability_line24"]
        self.assertIn(line_24_box, fields)
        self.assertEqual(str(irs_round(expected_line_24)), fields[line_24_box])

    def test_line_24_box_is_filled_on_a_plain_return_too(self):
        """No Schedule 2 at all: line 24 must still print, and equal line 16.

        Guards the failure this task exists to remove — the box printing blank
        — in the common case, where the two Schedule 2 components are both
        zero and a producer that silently dropped out would be invisible in
        the arithmetic."""
        scenario = _scenario(55_000, 8_000, None)
        results = self.orch.compute_federal(scenario)
        fields = self._fields(scenario, results)
        line_24_box = Pdf1040.get_mapping(YEAR)["tax_liability_line24"]
        self.assertIn(line_24_box, fields)
        self.assertEqual(str(irs_round(results["total_tax"])), fields[line_24_box])
        self.assertNotEqual("", fields[line_24_box])


class NativeResultsMustNotCarryTheLine24KeyTests(_NativeComputeCase):
    """The native spine must NOT emit `tax_liability_line24`. Load-bearing.

    THIS IS THE DESIGN DECISION BEHIND THE LINE-24 DERIVATION, WRITTEN AS AN
    ASSERTION. Read this before "simplifying" line 24 into a spine output key:
    the key's ABSENCE from a native results dict is what tells the two compute
    paths apart, in two places that both branch on exactly that.

      - `forms/f4868.py::total_tax_liability_line_24` returns the key's value
        outright when it is present (the WORKBOOK harvest, the vendor's own
        line 24) and only otherwise composes from the spine's parts.
      - `tests/invariants.py`'s 4868 fill helper branches the same way, and its
        workbook arm exists precisely to compare production against an
        INDEPENDENT oracle — the vendor's `Tot_Tax` — rather than against our
        own arithmetic.

    So a spine that published this key would silently route every native
    return down the harvest arm: `compose_line_24` would go dead, and the
    invariant's independent-oracle comparison would become a comparison of our
    own answer with itself. Both would still be green. That is why line 24 is
    produced at the PDF layer (`Pdf1040.get_derivations`) instead.

    THE NEGATIVE SPACE IS REACHABLE, so this is a real assertion and not a
    decorative one about a name that could never appear: adding
    `"tax_liability_line24": max(0, tax_plus_schedule2) + f8959_tax_total` to
    the spine's output dict — the correct-valued line that a well-meaning
    future task would write — is a one-line change that leaves the entire
    always-running gate unchanged. This test is the thing that reddens.
    """

    _KEY = "tax_liability_line24"

    def test_native_results_do_not_carry_the_line_24_key(self):
        for label, scenario in (
            ("plain", _scenario(55_000, 8_000, None)),
            ("schedule 2 part I + part II",
             _scenario(250_000, 40_000, _repayment_block())),
        ):
            with self.subTest(scenario=label):
                results = self.orch.compute_federal(scenario)
                # Precondition: this really is the native path, and it really
                # did produce a tax band — otherwise "key absent" would be
                # true for the boring reason that nothing was computed.
                self.assertIn("tax_plus_schedule2", results)
                self.assertGreater(results["total_tax"], 0)
                self.assertNotIn(self._KEY, results)

    def test_the_line_24_box_still_fills_without_that_key(self):
        """The other half, so the assertion above cannot be satisfied by
        deleting line 24's producer: the key is absent from `results` AND the
        box is filled anyway, by the derivation."""
        scenario = _scenario(55_000, 8_000, None)
        results = self.orch.compute_federal(scenario)
        self.assertNotIn(self._KEY, results)
        fields = self._fields(scenario, results)
        self.assertIn(Pdf1040.get_mapping(YEAR)["tax_liability_line24"], fields)


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
