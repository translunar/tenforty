"""Mapping-shape and partition tests for FTB Schedule D (540) PDF mapping.

Per-field-path correctness is tooltip-verified (each widget's `/TU`
annotation in `pdfs/california/2025/sch_d_540.pdf` records the line and
column it represents). This test verifies (a) the partition invariant —
every named PDF field on the 2025 form is OWNED by exactly one of
MAPPING / AGGREGATIONS / DERIVATIONS / SUPPRESSED, with no double
ownership — and (b) every mapped/aggregated/derived PDF field path
resolves to a real field in `pdfs/california/2025/sch_d_540.pdf`.

Probe note: the 2025 sch_d_540.pdf surfaces 125 /Tx widgets, all of
which are named (no unnamed visual placeholders). The 22 detail rows
1a..1v each populate 5 columns (a–e) contiguously, then lines 2..12
follow on page 4. The full enumeration is encoded as the module-level
constant `_EXPECTED_NAMED_FIELDS_2025` so this test does not depend on
pypdf for its partition assertion (pypdf is still used in the
field-existence test, but as a confirmation, not as the source of
truth).
"""

from pathlib import Path
import unittest

from pypdf import PdfReader

from tenforty.mappings import pdf_sch_d_540


# Canonical TY2025 named-field enumeration for sch_d_540.pdf.
#
# Source: extracted via direct probe of pdfs/california/2025/sch_d_540.pdf
# using pypdf.PdfReader.get_fields() on 2026-04-29; documented as the
# authoritative TY2025 named-field set for this form.
#
# Layout:
# - Header (page 1):
#     1001 = filer name (combined)
#     1002 = filer SSN
# - Detail rows 1a..1v (22 rows × 5 columns a–e = 110 fields):
#     1a → 1003-1007, 1b → 1008-1012, 1c → 1013-1017,
#     1d → 1018-1022, 1e → 1023-1027, 1f → 1028-1032,
#     1g → 2001-2005, 1h → 2006-2010, 1i → 2011-2015,
#     1j → 2016-2020, 1k → 2021-2025, 1l → 2026-2030,
#     1m → 2031-2035, 1n → 3001-3005, 1o → 3006-3010,
#     1p → 3011-3015, 1q → 3016-3020, 1r → 3021-3025,
#     1s → 3026-3030, 1t → 3031-3035, 1u → 4001-4005,
#     1v → 4006-4010
# - Lines 2..12 (page 4): 4011-4023 (13 fields)
#
# Total: 2 + 110 + 13 = 125 named fields. PdfFiller addresses fields by
# /T; this set is the complete addressable surface for TY2025.
def _build_expected_named_fields_2025() -> frozenset[str]:
    fields: list[str] = []
    # Header
    fields.append("540 sch D - 1001")
    fields.append("540 sch D - 1002")
    # Page 1 detail rows 1a..1f (1003..1032)
    for n in range(1003, 1033):
        fields.append(f"540 sch D - {n}")
    # Page 2 detail rows 1g..1m (2001..2035)
    for n in range(2001, 2036):
        fields.append(f"540 sch D - {n}")
    # Page 3 detail rows 1n..1t (3001..3035)
    for n in range(3001, 3036):
        fields.append(f"540 sch D - {n}")
    # Page 4 detail rows 1u..1v + lines 2..12 (4001..4023)
    for n in range(4001, 4024):
        fields.append(f"540 sch D - {n}")
    return frozenset(fields)


_EXPECTED_NAMED_FIELDS_2025: frozenset[str] = _build_expected_named_fields_2025()


class PdfSchD540MappingTests(unittest.TestCase):
    def test_2025_get_mapping_returns_dict(self):
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2025)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_2025_get_aggregations_is_empty(self):
        # No PDF cell on Sch D (540) receives a sum of multiple compute
        # keys at fill time in v1; both header cells (name, SSN) are
        # filled by single orchestrator-supplied keys.
        self.assertEqual(pdf_sch_d_540.PdfSchD540.get_aggregations(2025), {})

    def test_2025_get_checkbox_states_is_empty(self):
        # The 2025 Sch D (540) PDF has no /Btn widgets — pure /Tx.
        self.assertEqual(pdf_sch_d_540.PdfSchD540.get_checkbox_states(2025), {})

    def test_2025_unsupported_year_raises(self):
        for year in (2021, 2022, 2023, 2024, 2026):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    pdf_sch_d_540.PdfSchD540.get_mapping(year)
                with self.assertRaises(ValueError):
                    pdf_sch_d_540.PdfSchD540.get_aggregations(year)
                with self.assertRaises(ValueError):
                    pdf_sch_d_540.PdfSchD540.get_derivations(year)
                with self.assertRaises(ValueError):
                    pdf_sch_d_540.PdfSchD540.get_suppressed(year)
                with self.assertRaises(ValueError):
                    pdf_sch_d_540.PdfSchD540.get_checkbox_states(year)

    def test_2025_net_capital_gain_in_mapping(self):
        # The single compute output key from sch_d_540.compute() lands
        # on line 8 (combined gain/loss), widget 4018, per /TU annotation.
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2025)
        self.assertIn("sch_d_540_net_capital_gain", mapping)
        self.assertEqual(
            mapping["sch_d_540_net_capital_gain"],
            "540 sch D - 4018",
        )

    def test_2025_partition_invariant_covers_all_named_widgets_exactly_once(self):
        """The union of MAPPING-values, AGGREGATIONS-keys,
        DERIVATIONS-keys, and SUPPRESSED equals the canonical set of
        TY2025 named PDF field names; pairwise intersections are empty.

        Unnamed widgets (none observed on the 2025 form, but in general
        any visual placeholders without /T) are not part of the
        partition because PdfFiller addresses fields by /T and cannot
        reach them; this invariant is maintained explicitly so that
        adding a new mapping requires removing the corresponding
        suppression.
        """
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2025)
        aggregations = pdf_sch_d_540.PdfSchD540.get_aggregations(2025)
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2025)
        suppressed = pdf_sch_d_540.PdfSchD540.get_suppressed(2025)

        mapping_targets = set(mapping.values())
        aggregation_targets = set(aggregations.keys())
        derivation_targets = set(derivations.keys())

        # Pairwise intersections must be empty — every named widget is
        # owned by exactly one registry.
        self.assertEqual(
            mapping_targets & aggregation_targets,
            set(),
            "PDF field appears in both MAPPING values and AGGREGATIONS keys",
        )
        self.assertEqual(
            mapping_targets & derivation_targets,
            set(),
            "PDF field appears in both MAPPING values and DERIVATIONS keys",
        )
        self.assertEqual(
            mapping_targets & suppressed,
            set(),
            "PDF field appears in both MAPPING values and SUPPRESSED",
        )
        self.assertEqual(
            aggregation_targets & derivation_targets,
            set(),
            "PDF field appears in both AGGREGATIONS keys and DERIVATIONS keys",
        )
        self.assertEqual(
            aggregation_targets & suppressed,
            set(),
            "PDF field appears in both AGGREGATIONS keys and SUPPRESSED",
        )
        self.assertEqual(
            derivation_targets & suppressed,
            set(),
            "PDF field appears in both DERIVATIONS keys and SUPPRESSED",
        )

        accounted = (
            mapping_targets
            | aggregation_targets
            | derivation_targets
            | suppressed
        )

        missing = _EXPECTED_NAMED_FIELDS_2025 - accounted
        self.assertEqual(
            missing,
            set(),
            f"{len(missing)} PDF fields are unaccounted for: {sorted(missing)}",
        )

        extra = accounted - _EXPECTED_NAMED_FIELDS_2025
        self.assertEqual(
            extra,
            set(),
            f"{len(extra)} accounted PDF fields are not in the canonical "
            f"TY2025 named-field set: {sorted(extra)}",
        )

    def test_2025_get_derivations_includes_federal_passthrough_lines(self):
        # Lines 10 and 11 are derived from federal Sch D net (line 10)
        # and the in-form line 8 result (line 11). Under the v1
        # zero-divergence attestation, line 11 = line 8.
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2025)
        self.assertIn("540 sch D - 4020", derivations)
        self.assertIn("540 sch D - 4021", derivations)

    def test_2025_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/california/2025/sch_d_540.pdf.

        Also confirms the canonical `_EXPECTED_NAMED_FIELDS_2025` set
        matches the actual PDF (guards against drift if the form
        artifact is updated).
        """
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "california" / "2025" / "sch_d_540.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2025)
        aggregations = pdf_sch_d_540.PdfSchD540.get_aggregations(2025)
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2025)

        all_targets = (
            set(mapping.values())
            | set(aggregations.keys())
            | set(derivations.keys())
        )
        bad = sorted(p for p in all_targets if p not in real_fields)
        self.assertEqual(
            bad,
            [],
            f"{len(bad)} mapped/aggregated/derived field paths do not "
            f"exist in the PDF: {bad}",
        )

        # Confirm canonical set matches reality.
        self.assertEqual(
            _EXPECTED_NAMED_FIELDS_2025,
            real_fields,
            "Canonical _EXPECTED_NAMED_FIELDS_2025 has drifted from the "
            "actual PDF; update the constant after re-probing.",
        )
