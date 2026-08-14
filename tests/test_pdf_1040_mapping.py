"""Read-back tests for the federal 1040 line-26 (estimated tax payments) cell.

The federal spine emits result key ``estimated_tax_payments`` (line 26,
verbatim). This test locks the pdf_1040 mapping to that same key name for
all four years with committed templates, and verifies the mapped cell is a
real field on each year's template that round-trips a filled value.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tests.helpers import REPO_ROOT, scope_out_attestation_defaults
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f8995
from tenforty.forms.f1040_spine import compute_income_preamble, compute_spine
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import K1FanoutData, Scenario, TaxReturnConfig, W2
from tenforty.params.federal import load as load_federal_params

YEAR_CELLS = {
    2022: "topmostSubform[0].Page2[0].f2_15[0]",
    2023: "topmostSubform[0].Page2[0].f2_15[0]",
    2024: "topmostSubform[0].Page2[0].f2_20[0]",
    2025: "topmostSubform[0].Page2[0].f2_21[0]",
}


class TestPdf1040EstimatedTaxPaymentsMapping(unittest.TestCase):
    def test_mapping_keys_on_new_name(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                mapping = Pdf1040.get_mapping(year)
                self.assertEqual(mapping.get("estimated_tax_payments"), cell)
                self.assertNotIn("estimated_payments", mapping)

    def test_mapped_cell_is_real_field_on_template(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                fields = pypdf.PdfReader(template).get_fields()
                self.assertIn(cell, fields)

    def test_readback_distinctive_value(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(
                        template, out, mapping, values={"estimated_tax_payments": 13579}
                    )
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    self.assertEqual(fields[cell].get("/V"), "13579")

    def test_readback_zero_case_renders_zero(self):
        # Per team-lead ruling: a present 0 renders "0" (consistent with line
        # 25d/33 neighbors). The plan's "absent -> blank" means ONLY the case
        # where the results dict LACKS the key entirely (e.g. an old
        # filed-values surface) -- not zero-suppression.
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(
                        template, out, mapping, values={"estimated_tax_payments": 0}
                    )
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    self.assertEqual(fields[cell].get("/V"), "0")

    def test_readback_absent_case_is_blank(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(template, out, mapping, values={})
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    value = fields[cell].get("/V")
                    self.assertTrue(value is None or value == "")


class TestPdf1040_2021EmitRoundTrip(unittest.TestCase):
    """Fill the real 2021 f1040 template via PdfFiller with distinctive values,
    then read the cells back directly with pypdf — no soffice.

    Locks the render-verified 2021 placements, most importantly the wage-line
    regression: `wages` must land in the SINGLE 2021 line-1 box
    (Lines1-11_ReadOrder f1_28), NOT a 1a-1z sub-line (2021 has none). Uses
    plain tokens + integers — no SSN/EIN-shaped sentinels — so the
    personal-data denylist stays clean. If any value fails to land at its
    mapped path the test fails loudly; it must never be weakened.
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        template = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040.pdf"
        mapping = Pdf1040.get_mapping(2021)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040_2021.pdf"
            PdfFiller().fill(template, out, mapping, values=values)
            return {
                name: (fld.get("/V") or "")
                for name, fld in (pypdf.PdfReader(str(out)).get_fields() or {}).items()
            }

    def test_representative_subset_round_trips(self):
        mapping = Pdf1040.get_mapping(2021)
        values = {
            "first_name": "Distinct1040First",
            "last_name": "Distinct1040Last",
            "ssn": "SSN-SENTINEL-2021",
            "wages": 111_028,
            "taxable_interest": 222_030,
            "ordinary_dividends": 333_032,
            "agi": 444_043,
            "taxable_income": 555_049,
            "total_tax": 666_002,
            "total_payments": 777_024,
            "refund": 888_026,
            "combat_pay_election": 999_017,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(mapping[key]), str(expected))

    def test_wages_land_in_single_line1_box_f1_28(self):
        # The wage-line regression: 2021 has a single line-1 wages box; `wages`
        # must land in Lines1-11_ReadOrder f1_28 specifically.
        read = self._fill_and_read({"wages": 123_456})
        self.assertEqual(
            read.get("topmostSubform[0].Page1[0].Lines1-11_ReadOrder[0].f1_28[0]"),
            "123456",
            "wages must land in the single 2021 line-1 box f1_28",
        )

    def test_combat_pay_election_lands_in_f2_17(self):
        read = self._fill_and_read({"combat_pay_election": 42_017})
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].f2_17[0]"),
            "42017",
            "combat_pay_election must land in f2_17 (line 27b)",
        )


class TestPdf1040Line1zPlacement(unittest.TestCase):
    """Line 1z ("Total (add lines 1a through 1h)") must not be blank.

    Regression test for the compute-dead `total_w2_income` result key: the
    merged-year (2022-2025) pdf_1040 mapping maps `total_w2_income` to the
    line-1z box, but pre-fix no `tenforty/forms/` module emitted it, so 1z
    printed blank while 1a (wages) printed filled. Since W-2 box-1 is the
    only modeled line-1 component, line 1z must equal line 1a for a
    wages-only scenario. Runs the real native compute_spine (no soffice) so
    the assertion is not a tautology against hand-supplied mapping values.
    """

    WAGES = 54_000

    def _compute_and_read(self, year: int) -> dict[str, str | None]:
        scenario = Scenario(
            config=TaxReturnConfig(
                year=year,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
                **scope_out_attestation_defaults(),
            ),
            w2s=[
                W2(
                    employer="Acme Corp",
                    wages=self.WAGES,
                    federal_tax_withheld=0,
                    ss_wages=self.WAGES,
                    ss_tax_withheld=0,
                    medicare_wages=self.WAGES,
                    medicare_tax_withheld=0,
                ),
            ],
        )
        params = load_federal_params(year)
        results = compute_spine(scenario, params, {"sch_a": {"sch_a_line_17_total": 0}})

        mapping = Pdf1040.get_mapping(year)
        template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out.pdf"
            PdfFiller().fill(template, out, mapping, values=results)
            reader = pypdf.PdfReader(out)
            fields = reader.get_fields()
            return {
                "1a": fields[mapping["wages"]].get("/V"),
                "1z": fields[mapping["total_w2_income"]].get("/V"),
            }

    def test_line_1z_equals_line_1a_for_wages_only_scenario(self):
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                read = self._compute_and_read(year)
                self.assertEqual(
                    read["1a"], str(self.WAGES),
                    f"{year}: line 1a (wages) did not land at its mapped cell",
                )
                self.assertEqual(
                    read["1z"], str(self.WAGES),
                    f"{year}: line 1z (total_w2_income) is blank or wrong — "
                    "must equal line 1a for a wages-only scenario",
                )


class TestPdf1040Line14DeductionsPlusQbi(unittest.TestCase):
    """1040 line 14 ("Add lines 12(c) and 13") must equal line 12(c) + line
    13 (QBI), not just line 12(c).

    Regression test for bug #4: pdf_1040.py mapped the spine's
    `total_deductions` (line 12(c) ONLY — the spine computes taxable_income
    as agi - total_deductions - qbi_deduction, so total_deductions excludes
    QBI by construction) to the line-14 box in all 5 year blocks. Any
    scenario with QBI > 0 therefore printed line 14 == line 12, silently
    dropping the QBI deduction and breaking the line-14/line-15 footing.

    Also a regression test for bug #5: line 13 (pdf_1040.py's `qbi_deduction`
    key) was never populated because the spine only emitted the QBI amount
    under the underscore-prefixed `_qbi_deduction_1040` (consumed internally
    by the oracle-translation shim in forms/f1040.py). Line 13 now must
    read back the real QBI deduction, and the line-14 footing check reads
    all three boxes (12, 13, 14) from the actual filled PDF.

    Uses a real K-1 QBI aggregate run through the actual forms.f8995.compute
    (not a hand-typed qbi_deduction), mirroring the orchestrator's own
    f8995 pre-pass (see orchestrator.py Step 7/8), so the expected QBI
    value is independently produced by the engine, not asserted by fiat.
    """

    WAGES = 100_000
    QBI_AMOUNT = 50_000  # K-1 qualified-business-income aggregate

    @staticmethod
    def _line12_key(year: int) -> str:
        # 2021: line 12(c) = 12a (std/itemized) + 12b (charitable) is the
        # spine's `total_deductions`. 2022-2025: the single line 12 is the
        # deduction actually applied -> `applied_deduction`. Both scenarios
        # in this test have charitable_nonitemizer == 0, so the two keys
        # carry the same number regardless of which one the year uses.
        return "total_deductions" if year == 2021 else "applied_deduction"

    def _compute_with_qbi(self, year: int) -> tuple[dict, float]:
        scenario = Scenario(
            config=TaxReturnConfig(
                year=year,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
                **scope_out_attestation_defaults(),
            ),
            w2s=[
                W2(
                    employer="Acme Corp",
                    wages=self.WAGES,
                    federal_tax_withheld=0,
                    ss_wages=self.WAGES,
                    ss_tax_withheld=0,
                    medicare_wages=self.WAGES,
                    medicare_tax_withheld=0,
                ),
            ],
        )
        params = load_federal_params(year)

        # Mirror the orchestrator's f8995 pre-pass: the shared income
        # preamble supplies the pre-QBI taxable-income stand-in (Sch A is
        # not modeled here, so the standard deduction is used), then the
        # REAL f8995.compute runs against a K-1 fanout carrying nonzero QBI
        # -- the resulting qbi_deduction is engine-computed, not hand-typed.
        preamble = compute_income_preamble(scenario, params, {})
        fanout = K1FanoutData(
            sch_b_interest_additions=(),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(),
            sch_d_long_term_additions=(),
            qbi_aggregate=self.QBI_AMOUNT,
            qualified_dividends_aggregate=0.0,
            passive_activities=(),
        )
        f8995_results = f8995.compute(
            scenario,
            upstream={
                "k1_fanout": fanout,
                "f1040": {
                    "taxable_income_before_qbi_deduction":
                        preamble.taxable_income_before_qbi_std,
                    "net_capital_gain": preamble.net_capital_gain,
                    # 1040 line 3a TOTAL (1099-DIV + K-1), which f8995.compute
                    # reads strictly. Taken from the same preamble field the
                    # orchestrator's production stub uses, so this mirrors the
                    # real upstream. This scenario is W-2-only (no 1099-DIV, no
                    # K-1), so the true total is 0 — scenario-faithful, not a
                    # value chosen to satisfy the strict read.
                    "qualified_dividends": preamble.qualified_divs_total,
                },
            },
        )
        qbi_deduction = f8995_results["f8995_line_15_qbi_deduction"]
        self.assertGreater(
            qbi_deduction, 0,
            "QBI scenario setup must produce a nonzero QBI deduction for "
            "this test to actually exercise the bug-#4 code path",
        )

        results = compute_spine(
            scenario, params,
            {"sch_a": {"sch_a_line_17_total": 0}, "f8995": f8995_results},
        )
        return results, qbi_deduction

    def _fill_and_read(self, year: int, results: dict) -> dict[str, str | None]:
        mapping = Pdf1040.get_mapping(year)
        template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out.pdf"
            PdfFiller().fill(template, out, mapping, values=results)
            reader = pypdf.PdfReader(out)
            fields = reader.get_fields()
            return {
                "line11": fields[mapping["agi"]].get("/V"),
                "line12": fields[mapping[self._line12_key(year)]].get("/V"),
                "line13": fields[mapping["qbi_deduction"]].get("/V"),
                "line14": fields[mapping["deductions_plus_qbi"]].get("/V"),
                "line15": fields[mapping["taxable_income"]].get("/V"),
            }

    def test_line14_equals_12c_plus_13_and_footing_holds(self):
        for year in (2021, 2025):
            with self.subTest(year=year):
                results, qbi_deduction = self._compute_with_qbi(year)
                boxes = self._fill_and_read(year, results)

                line11 = int(boxes["line11"])
                line12 = int(boxes["line12"])
                line14 = int(boxes["line14"])
                line15 = int(boxes["line15"])

                # Bug #5 fix: line 13's PDF box (pdf_1040.py's "qbi_deduction"
                # key) must now read back a real value. The native spine emits
                # the QBI amount under both "_qbi_deduction_1040" (kept for the
                # oracle-translation shim in forms/f1040.py) and the plain
                # "qbi_deduction" key that pdf_1040.py's mapping actually keys
                # on. Assert against the independently-computed qbi_deduction
                # (from the real forms.f8995.compute call above, not a
                # hand-typed literal) so this guards against the box merely
                # being non-blank with the wrong number.
                self.assertGreater(qbi_deduction, 0)
                self.assertIsNotNone(
                    boxes["line13"],
                    "line 13 (qbi_deduction) box is blank -- Bug #5: the "
                    "spine must emit a plain `qbi_deduction` key alongside "
                    "`_qbi_deduction_1040` for pdf_1040.py's line-13 mapping "
                    "to find.",
                )
                line13 = int(boxes["line13"])
                self.assertEqual(
                    line13, int(qbi_deduction),
                    f"{year}: line 13 box must equal the engine-computed QBI "
                    f"deduction ({qbi_deduction}) -- got {line13}",
                )

                # Footing check, reading ALL THREE boxes back from the actual
                # filled PDF (not internal variables): line 14 = 12(c) + 13,
                # and line 15 = line 11 - line 14. This is the bug-#4
                # assertion class, now exercised with a genuinely populated
                # (not blank/zero-by-omission) line 13.
                self.assertEqual(
                    line14, line12 + line13,
                    f"{year}: line 14 must equal line 12 + line 13 "
                    f"({line12} + {line13} != {line14}) -- pre-fix this "
                    "failed because line 14 was wired to `total_deductions` "
                    "(line 12(c) only, no QBI)",
                )
                # Internal consistency: line 15 = line 11 - line 14.
                self.assertEqual(
                    line15, line11 - line14,
                    f"{year}: line 15 must equal line 11 - line 14 "
                    f"({line11} - {line14} != {line15})",
                )


class TestPdf1040_2021Line12bCharitablePlacement(unittest.TestCase):
    """2021 line 12b (above-the-line cash-charitable deduction for
    non-itemizers, f1_45) and line 12c (12a + 12b, f1_46) placement.

    Regression test for the "noted, not mapped" line 12b and the wholly
    unmapped line 12c. QBI == 0 throughout, so line 14 == line 12c.
    """

    WAGES = 60_000

    def _compute(self, charitable: float) -> dict:
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2021,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
                charitable_cash_nonitemizer=charitable,
                **scope_out_attestation_defaults(),
            ),
            w2s=[
                W2(
                    employer="Acme Corp",
                    wages=self.WAGES,
                    federal_tax_withheld=0,
                    ss_wages=self.WAGES,
                    ss_tax_withheld=0,
                    medicare_wages=self.WAGES,
                    medicare_tax_withheld=0,
                ),
            ],
        )
        params = load_federal_params(2021)
        return compute_spine(
            scenario, params, {"sch_a": {"sch_a_line_17_total": 0}},
        )

    def _fill_and_read(self, results: dict) -> dict[str, str | None]:
        mapping = Pdf1040.get_mapping(2021)
        template = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040.pdf"
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out.pdf"
            PdfFiller().fill(template, out, mapping, values=results)
            reader = pypdf.PdfReader(out)
            fields = reader.get_fields()
            return {
                "12b": fields[mapping["charitable_nonitemizer"]].get("/V"),
                "12c": fields[mapping["total_deductions"]].get("/V"),
                "14": fields[mapping["deductions_plus_qbi"]].get("/V"),
            }

    def test_charitable_250_lands_in_12b_and_12c(self):
        std_2021_single = load_federal_params(2021).standard_deduction["single"]
        results = self._compute(charitable=250)
        boxes = self._fill_and_read(results)

        self.assertEqual(boxes["12b"], "250")
        self.assertEqual(boxes["12c"], str(std_2021_single + 250))
        # QBI == 0 here -> line 14 == line 12c exactly.
        self.assertEqual(boxes["14"], str(std_2021_single + 250))

    def test_zero_charitable_12b_renders_present_zero(self):
        # `charitable_nonitemizer` is unconditionally emitted by the spine
        # (0 when the scenario doesn't use the 2021 line-12b channel) --
        # it is never omitted or set to None for the zero case. Per the
        # PdfFiller convention already codified in this file (see
        # TestPdf1040EstimatedTaxPaymentsMapping.test_readback_zero_case_
        # renders_zero above: "a present 0 renders '0'... 'absent -> blank'
        # means ONLY the case where the results dict LACKS the key
        # entirely"), a present-but-zero charitable_nonitemizer renders "0",
        # not blank. This locks that real, observed behavior.
        results = self._compute(charitable=0)
        boxes = self._fill_and_read(results)
        self.assertEqual(boxes["12b"], "0")


if __name__ == "__main__":
    unittest.main()
