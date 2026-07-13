"""Year-keyed coverage + filled-emit verification for the California Schedule X
PDF mapping.

Schedule X has THREE distinct field-namespace/numbering shapes across the five
per-year FTB templates (bare + year write-in for 2021/2022; bare + preprinted
year for 2023; "Sch X Form "-prefixed + preprinted year for 2024/2025). Each
year's mapping is driven off ``PdfScheduleX.get_mapping(year)`` and certified
against THAT YEAR's own ``get_fields()`` — nothing is inherited across the
bare/prefixed or numbering-shift boundaries. Every check subTests over
``years.amendable_california_years()``.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.forms.schedule_x import assemble_ca
from tenforty.mappings.pdf_schedule_x import PdfScheduleX
from tenforty.models import AmendmentCase
from tests.helpers import REPO_ROOT

# The assembler's Part-I money-line + explanation keys, mapped EVERY year.
_LINE_KEYS = frozenset({
    "schedule_x_line1", "schedule_x_line2", "schedule_x_line3",
    "schedule_x_line4", "schedule_x_line5", "schedule_x_line6",
    "schedule_x_line7", "schedule_x_line8a", "schedule_x_line8b",
    "schedule_x_line8c", "schedule_x_line9", "schedule_x_line10",
    "schedule_x_line11", "schedule_x_explanation",
})
# The year write-in exists ONLY on the 2021/2022 templates.
_TAXABLE_YEAR_KEY = "schedule_x_taxable_year"
_YEARS_WITH_YEAR_WRITE_IN = frozenset({2021, 2022})
# Duplicate aliases carrying the same value as their bare line key — never
# mapped (mapping them would double-write a single widget).
_UNMAPPED_ALIASES = frozenset({
    "schedule_x_line7_amount_owed", "schedule_x_line11_refund",
})

_EXPLANATION = "SYNTHETIC AMENDMENT EXPLANATION FOR SCHEDULE X EMIT TEST"


def _template(year: int) -> Path:
    return (REPO_ROOT / "pdfs" / "california" / "amendments"
            / f"schedule_x_{year}.pdf")


def _expected_keys(year: int) -> frozenset[str]:
    if year in _YEARS_WITH_YEAR_WRITE_IN:
        return _LINE_KEYS | {_TAXABLE_YEAR_KEY}
    return _LINE_KEYS


def _owed_output(year: int) -> dict:
    """assemble_ca output where L7 (AMOUNT YOU OWE) is the distinctive nonzero
    line. Consistent inputs: filed OWED (positive liability) => original
    overpayment 0, so the consistency guard passes."""
    case = AmendmentCase(
        year=year, explanation=_EXPLANATION,
        original_refund_received=0.0, original_refund_applied=0.0,
        ca_original_refund_received=0.0, ca_original_refund_applied=0.0,
    )
    filed = {"f540_total_liability": 100.0}      # paid 100 with original (L5)
    corrected = {"f540_total_liability": 250.0}  # owe 250 on amended (L1)
    return assemble_ca(filed, corrected, case)   # L7 = 250 - 100 = 150


def _refund_output(year: int) -> dict:
    """assemble_ca output where L11 (REFUND) is the distinctive nonzero line.
    Consistent inputs: filed overpaid 50 => stated original overpayment 50."""
    case = AmendmentCase(
        year=year, explanation=_EXPLANATION,
        original_refund_received=0.0, original_refund_applied=0.0,
        ca_original_refund_received=50.0, ca_original_refund_applied=0.0,
    )
    filed = {"f540_total_liability": -50.0}       # original overpaid 50 (L2)
    corrected = {"f540_total_liability": -200.0}  # refund 200 on amended (L4)
    return assemble_ca(filed, corrected, case)    # L9 = 200 - 50 = 150 => L11


def _readback(out: Path, path: str) -> str:
    fields = PdfReader(out).get_fields() or {}
    return str(fields[path].get("/V") or "").replace(",", "").replace("$", "").strip()


class PdfScheduleXPayloadCoverageTests(unittest.TestCase):
    def test_every_assembler_key_maps_per_year(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                self.assertEqual(set(PdfScheduleX.get_mapping(year)),
                                 set(_expected_keys(year)))

    def test_aliases_intentionally_unmapped_every_year(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                mapping = PdfScheduleX.get_mapping(year)
                self.assertEqual(_UNMAPPED_ALIASES & set(mapping), frozenset())

    def test_taxable_year_mapped_only_for_write_in_years(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                mapped = _TAXABLE_YEAR_KEY in PdfScheduleX.get_mapping(year)
                self.assertEqual(mapped, year in _YEARS_WITH_YEAR_WRITE_IN)


class PdfScheduleXFieldsOnTemplateTests(unittest.TestCase):
    def test_every_mapped_path_is_a_real_pdf_field(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                real = set(PdfReader(_template(year)).get_fields() or {})
                bad = sorted(p for p in PdfScheduleX.get_mapping(year).values()
                             if p not in real)
                self.assertEqual(bad, [])


class PdfScheduleXFilledEmitTests(unittest.TestCase):
    def test_owed_case_reads_back_line7_and_explanation(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                mapping = PdfScheduleX.get_mapping(year)
                values = _owed_output(year)
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "filled.pdf"
                    PdfFiller().fill(_template(year), out, mapping, values)
                    self.assertEqual(_readback(out, mapping["schedule_x_line7"]),
                                     "150")
                    self.assertEqual(
                        _readback(out, mapping["schedule_x_explanation"]),
                        _EXPLANATION)
                    if year in _YEARS_WITH_YEAR_WRITE_IN:
                        self.assertEqual(
                            _readback(out, mapping[_TAXABLE_YEAR_KEY]),
                            str(year))

    def test_refund_case_reads_back_line11_and_explanation(self):
        for year in years.amendable_california_years():
            with self.subTest(year=year):
                mapping = PdfScheduleX.get_mapping(year)
                values = _refund_output(year)
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "filled.pdf"
                    PdfFiller().fill(_template(year), out, mapping, values)
                    self.assertEqual(
                        _readback(out, mapping["schedule_x_line11"]), "150")
                    self.assertEqual(
                        _readback(out, mapping["schedule_x_explanation"]),
                        _EXPLANATION)
                    if year in _YEARS_WITH_YEAR_WRITE_IN:
                        self.assertEqual(
                            _readback(out, mapping[_TAXABLE_YEAR_KEY]),
                            str(year))
