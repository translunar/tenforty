"""Mapping-shape and field-existence tests for FTB Form 540 PDF mapping.

Per-field-path correctness lives in the T12 probe artifact
(`docs/plans/sp3-t12-f540-probe.md`); this test verifies (a) the
partition invariant — every f540.compute() output key is owned by
exactly one of MAPPING / AGGREGATIONS / SUPPRESSED, with derivations
consuming but not owning — and (b) every mapped/aggregated/derived PDF
field path resolves to a real field in `pdfs/california/2025/f540.pdf`.
"""

from pathlib import Path
import unittest

from pypdf import PdfReader

from tenforty.mappings import pdf_f540
from tenforty.mappings.pdf_f540 import _FILING_STATUS_RB_STATES
from tenforty.models import FilingStatus


_EXPECTED_COMPUTE_KEYS = frozenset({
    "f540_ca_agi",
    "f540_deduction",
    "f540_taxable_income",
    "f540_ca_tax",
    "f540_exemption_credit",
    "f540_renter_credit",
    "f540_ptet_credit",
    "f540_total_credits",
    "f540_voluntary_contributions",
    "f540_use_tax",
    "f540_estimated_tax_penalty",
    "f540_estimated_payments",
    "f540_total_liability",
    "f540_filing_status",
})


class PdfF540MappingTests(unittest.TestCase):
    def test_2025_get_mapping_returns_dict(self):
        mapping = pdf_f540.PdfF540.get_mapping(2025)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_2025_get_aggregations_is_empty(self):
        # f540 has no within-form aggregations (all sums are clamped or
        # sign-split, encoded as derivations).
        self.assertEqual(pdf_f540.PdfF540.get_aggregations(2025), {})

    def test_2025_get_checkbox_states_is_empty(self):
        # No bool compute keys map to checkbox cells in v1.
        self.assertEqual(pdf_f540.PdfF540.get_checkbox_states(2025), {})

    def test_2025_unsupported_year_raises(self):
        for year in (2021, 2022, 2026):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    pdf_f540.PdfF540.get_mapping(year)

    def test_2025_partition_invariant(self):
        """Every expected compute key is OWNED by exactly one of
        `_MAPPING_2025`, `_AGGREGATIONS_2025`, or `_SUPPRESSED_2025`.

        Derivation lambdas (`_DERIVATIONS_2025`) CONSUME compute keys
        but do not OWN them. SP3 extends SUPPRESSED semantics to include
        keys consumed only by derivations (e.g., `f540_total_liability`
        sign-split, `f540_filing_status` enum-dispatch); the partition
        test treats those as owned.
        """
        mapping = pdf_f540.PdfF540.get_mapping(2025)
        aggregations = pdf_f540.PdfF540.get_aggregations(2025)
        suppressed = pdf_f540.PdfF540.get_suppressed(2025)

        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed

        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(
            missing, set(),
            f"{len(missing)} compute keys are unaccounted for: {sorted(missing)}",
        )

        in_mapping = set(mapping.keys()) & _EXPECTED_COMPUTE_KEYS
        double = (
            (in_mapping & agg_contributors)
            | (in_mapping & suppressed)
            | (agg_contributors & suppressed)
        )
        self.assertEqual(
            double, set(),
            f"{len(double)} keys are double-accounted: {sorted(double)}",
        )

    def test_2025_total_liability_is_suppressed_per_q1_adjudication(self):
        # Team-lead Q1 adjudication: f540_total_liability is owned in
        # SUPPRESSED; both target cells (owe / refund) are derivation
        # lambdas. Verify the ownership.
        suppressed = pdf_f540.PdfF540.get_suppressed(2025)
        self.assertIn("f540_total_liability", suppressed)
        self.assertNotIn("f540_total_liability", pdf_f540.PdfF540.get_mapping(2025))

    def test_2025_filing_status_rb_states_covers_all_filing_statuses(self):
        # The verbose state strings table must cover every FilingStatus
        # member; otherwise the filing-status RB derivation will
        # KeyError at fill time for that status.
        for status in FilingStatus:
            with self.subTest(status=status):
                self.assertIn(status, _FILING_STATUS_RB_STATES)
                self.assertTrue(_FILING_STATUS_RB_STATES[status].startswith("/"))

    def test_2025_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/california/2025/f540.pdf.

        Note: [PLANNED] orchestrator-supplied entries (taxpayer/spouse/
        address/email/phone/county) are real PDF fields too — they're
        only "planned" in the sense that the orchestrator hasn't wired
        them yet, not that the cells don't exist.
        """
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "california" / "2025" / "f540.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_f540.PdfF540.get_mapping(2025)
        aggregations = pdf_f540.PdfF540.get_aggregations(2025)
        derivations = pdf_f540.PdfF540.get_derivations(2025)

        all_targets = (
            set(mapping.values())
            | set(aggregations.keys())
            | set(derivations.keys())
        )
        bad = sorted(p for p in all_targets if p not in real_fields)
        self.assertEqual(
            bad, [],
            f"{len(bad)} mapped/aggregated/derived field paths do not exist in the PDF: {bad}",
        )

    def test_2024_partition_invariant(self):
        mapping = pdf_f540.PdfF540.get_mapping(2024)
        aggregations = pdf_f540.PdfF540.get_aggregations(2024)
        suppressed = pdf_f540.PdfF540.get_suppressed(2024)
        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed
        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(missing, set(), f"unaccounted: {sorted(missing)}")
        double = ((set(mapping) & agg_contributors) | (set(mapping) & suppressed)
                  | (agg_contributors & suppressed))
        self.assertEqual(double, set(), f"double-accounted: {sorted(double)}")

    def test_2024_every_pdf_target_is_a_real_pdf_field(self):
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2024" / "f540.pdf")
        real = set(reader.get_fields() or {})
        mapping = pdf_f540.PdfF540.get_mapping(2024)
        derivations = pdf_f540.PdfF540.get_derivations(2024)
        aggregations = pdf_f540.PdfF540.get_aggregations(2024)
        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2024 PDF: {bad}")


class PdfF540MappingTests2023(unittest.TestCase):
    """Mapping-shape / field-existence tests for the TY2023 Form 540 mapping.

    2023 is a THIRD FTB field-naming scheme: bare zero-padded numbers ('2023',
    '3004', '1036 CB') — no '540_form_'/'540-' prefix. Two structural
    divergences from 2024/2025, both invisible-shift traps caught only by
    reading /TU tooltips + the /Btn probe (verified by filled-emit on the real
    2023 template): (1) filing status is FIVE line-1..5 checkboxes, not a single
    verbose-export radio group; (2) several back-page cells shifted their
    sequence number (line 110->4026, 113->5006, 111 owe->4027, 115 refund->5008).
    """

    def test_2023_get_aggregations_and_checkbox_states_empty(self):
        self.assertEqual(pdf_f540.PdfF540.get_aggregations(2023), {})
        self.assertEqual(pdf_f540.PdfF540.get_checkbox_states(2023), {})

    def test_2023_partition_invariant(self):
        mapping = pdf_f540.PdfF540.get_mapping(2023)
        aggregations = pdf_f540.PdfF540.get_aggregations(2023)
        suppressed = pdf_f540.PdfF540.get_suppressed(2023)
        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed
        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(missing, set(), f"unaccounted: {sorted(missing)}")
        in_mapping = set(mapping.keys()) & _EXPECTED_COMPUTE_KEYS
        double = ((in_mapping & agg_contributors) | (in_mapping & suppressed)
                  | (agg_contributors & suppressed))
        self.assertEqual(double, set(), f"double-accounted: {sorted(double)}")

    def test_2023_every_pdf_target_is_a_real_pdf_field(self):
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2023" / "f540.pdf")
        real = set(reader.get_fields() or {})
        mapping = pdf_f540.PdfF540.get_mapping(2023)
        derivations = pdf_f540.PdfF540.get_derivations(2023)
        aggregations = pdf_f540.PdfF540.get_aggregations(2023)
        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2023 PDF: {bad}")

    def test_2023_filing_status_checkboxes_cover_all_statuses(self):
        # 2023's five-checkbox filing status must cover every FilingStatus,
        # and each mapped checkbox must be a derivation cell (driven /Yes/Off).
        cb_table = pdf_f540._FILING_STATUS_CB_2023
        derivations = pdf_f540.PdfF540.get_derivations(2023)
        for status in FilingStatus:
            with self.subTest(status=status):
                self.assertIn(status, cb_table)
                self.assertIn(cb_table[status], derivations)
        # All five checkboxes are distinct cells.
        self.assertEqual(len(set(cb_table.values())), len(FilingStatus))

    def test_2023_back_page_cells_shifted_from_2024(self):
        # Pin the four sequence-number shifts vs 2024/2025 that only the
        # tooltip read caught (regression guard against a copy-forward).
        mapping = pdf_f540.PdfF540.get_mapping(2023)
        derivations = pdf_f540.PdfF540.get_derivations(2023)
        self.assertEqual(mapping["f540_voluntary_contributions"], "4026")  # line 110
        self.assertEqual(mapping["f540_estimated_tax_penalty"], "5006")    # line 113
        self.assertIn("4027", derivations)  # line 111 (owe)
        self.assertIn("5008", derivations)  # line 115 (refund)
