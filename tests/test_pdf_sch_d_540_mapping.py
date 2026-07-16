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

TY2024 probe note: the 2024 sch_d_540.pdf also surfaces 125 /Tx widgets
(no /Btn, no unnamed placeholders), but with a DIFFERENT naming scheme
(`540D - NNNN`) and a different layout: all 22 detail rows 1a..1v fit on
a single page (1003..1112), followed by lines 2–7 (1113..1119), with
lines 8–12 on page 2 (2001..2006). Probed 2026-06-19.
"""

from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
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
        for year in (2020, 2026):  # 2021/2022/2023 are now supported PDF-mapping years
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

    def test_lines_12a_12b_mapped_for_divergences(self):
        """Lines 12a (subtraction total) and 12b (addition total) must be
        present in the 2025 mapping so user-supplied Sch D divergences
        render on the PDF, not just in compute output."""
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2025)
        self.assertIn("sch_d_540_total_subtractions", mapping)
        self.assertIn("sch_d_540_total_additions", mapping)

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


# ---------------------------------------------------------------------------
# TY2024 support
# ---------------------------------------------------------------------------

# Canonical TY2024 named-field enumeration for sch_d_540.pdf.
#
# Source: extracted via direct probe of pdfs/california/2024/sch_d_540.pdf
# using pypdf.PdfReader.get_fields() on 2026-06-19; documented as the
# authoritative TY2024 named-field set for this form.
#
# Layout (differs from 2025 — all detail rows on a single page):
# - Header (page 1):
#     1001 = filer name
#     1002 = filer SSN
# - Detail rows 1a..1v (22 rows × 5 columns a–e = 110 fields, page 1):
#     1a → 1003-1007, 1b → 1008-1012, 1c → 1013-1017,
#     1d → 1018-1022, 1e → 1023-1027, 1f → 1028-1032,
#     1g → 1033-1037, 1h → 1038-1042, 1i → 1043-1047,
#     1j → 1048-1052, 1k → 1053-1057, 1l → 1058-1062,
#     1m → 1063-1067, 1n → 1068-1072, 1o → 1073-1077,
#     1p → 1078-1082, 1q → 1083-1087, 1r → 1088-1092,
#     1s → 1093-1097, 1t → 1098-1102, 1u → 1103-1107,
#     1v → 1108-1112
# - Lines 2–7 (page 1): 1113-1119 (7 fields)
# - Lines 8–12 (page 2): 2001-2006 (6 fields)
#
# Total: 2 + 110 + 7 + 6 = 125 named fields. Naming scheme: '540D - NNNN'
# (space before dash, no 'sch' segment — distinct from 2025's
# '540 sch D - PRRR'). PdfFiller addresses fields by /T.
def _build_expected_named_fields_2024() -> frozenset[str]:
    fields: list[str] = []
    # Header (page 1, 1001..1002)
    fields.append("540D - 1001")
    fields.append("540D - 1002")
    # Page 1: detail rows 1a..1v + lines 2–7 (1003..1119)
    for n in range(1003, 1120):
        fields.append(f"540D - {n}")
    # Page 2: lines 8–12 (2001..2006)
    for n in range(2001, 2007):
        fields.append(f"540D - {n}")
    return frozenset(fields)


_EXPECTED_NAMED_FIELDS_2024: frozenset[str] = _build_expected_named_fields_2024()


class PdfSchD540Mapping2024Tests(unittest.TestCase):
    def test_2024_get_mapping_returns_dict(self):
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2024)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_2024_get_aggregations_is_empty(self):
        self.assertEqual(pdf_sch_d_540.PdfSchD540.get_aggregations(2024), {})

    def test_2024_get_checkbox_states_is_empty(self):
        # The 2024 Sch D (540) PDF has no /Btn widgets — pure /Tx.
        self.assertEqual(pdf_sch_d_540.PdfSchD540.get_checkbox_states(2024), {})

    def test_2024_net_capital_gain_in_mapping(self):
        # Line 8 (net gain/loss) maps to 540D - 2001 on the 2024 form,
        # per /TU annotation: "Line 8. Net gain or (loss). Combine line 4 and line 7."
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2024)
        self.assertIn("sch_d_540_net_capital_gain", mapping)
        self.assertEqual(mapping["sch_d_540_net_capital_gain"], "540D - 2001")

    def test_2024_get_derivations_includes_federal_passthrough_lines(self):
        # Line 10 (federal net) → 540D - 2003
        # Line 11 (CA gain from line 8) → 540D - 2004
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2024)
        self.assertIn("540D - 2003", derivations)
        self.assertIn("540D - 2004", derivations)

    def test_2024_lines_12a_12b_mapped_for_divergences(self):
        """Lines 12a (subtraction total) and 12b (addition total) must be
        present in the 2024 mapping so user-supplied Sch D divergences
        render on the PDF, not just in compute output."""
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2024)
        self.assertIn("sch_d_540_total_subtractions", mapping)
        self.assertIn("sch_d_540_total_additions", mapping)

    def test_2024_partition_invariant_covers_all_named_widgets_exactly_once(self):
        """The union of MAPPING-values, AGGREGATIONS-keys,
        DERIVATIONS-keys, and SUPPRESSED equals the canonical set of
        TY2024 named PDF field names; pairwise intersections are empty.
        """
        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2024)
        aggregations = pdf_sch_d_540.PdfSchD540.get_aggregations(2024)
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2024)
        suppressed = pdf_sch_d_540.PdfSchD540.get_suppressed(2024)

        mapping_targets = set(mapping.values())
        aggregation_targets = set(aggregations.keys())
        derivation_targets = set(derivations.keys())

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

        missing = _EXPECTED_NAMED_FIELDS_2024 - accounted
        self.assertEqual(
            missing,
            set(),
            f"{len(missing)} PDF fields are unaccounted for: {sorted(missing)}",
        )

        extra = accounted - _EXPECTED_NAMED_FIELDS_2024
        self.assertEqual(
            extra,
            set(),
            f"{len(extra)} accounted PDF fields are not in the canonical "
            f"TY2024 named-field set: {sorted(extra)}",
        )

    def test_2024_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/california/2024/sch_d_540.pdf.

        Also confirms the canonical `_EXPECTED_NAMED_FIELDS_2024` set
        matches the actual PDF (guards against drift if the form
        artifact is updated).
        """
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "california" / "2024" / "sch_d_540.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2024)
        aggregations = pdf_sch_d_540.PdfSchD540.get_aggregations(2024)
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2024)

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
            _EXPECTED_NAMED_FIELDS_2024,
            real_fields,
            "Canonical _EXPECTED_NAMED_FIELDS_2024 has drifted from the "
            "actual PDF; update the constant after re-probing.",
        )


class PdfSchD540MappingTests2023(unittest.TestCase):
    """TY2023 Sch D (540) mapping — a THIRD FTB field-naming scheme (bare
    zero-padded numbers '1001'/'2001', no '540D'/'540 sch D' prefix). The
    mapping was read from the widgets' /TU tooltips on the 2023 template and
    filled-emit-verified (probe committed as
    pdfs/california/2023/sch_d_540.probe.pdf). Partition is checked against the
    live probe rather than a hardcoded constant.
    """

    @classmethod
    def setUpClass(cls):
        pdf_path = (Path(__file__).resolve().parent.parent
                    / "pdfs" / "california" / "2023" / "sch_d_540.pdf")
        cls.real_fields = frozenset(PdfReader(pdf_path).get_fields() or {})

    def test_2023_renumbered_cells(self):
        """Line 8 net gain, line 12a/12b Sch-CA deltas land on the bare-number
        2023 widgets read from the /TU tooltips."""
        m = pdf_sch_d_540.PdfSchD540.get_mapping(2023)
        self.assertEqual(m["sch_d_540_net_capital_gain"], "2001")     # line 8
        self.assertEqual(m["sch_d_540_total_subtractions"], "2005")   # line 12a
        self.assertEqual(m["sch_d_540_total_additions"], "2006")      # line 12b
        d = pdf_sch_d_540.PdfSchD540.get_derivations(2023)
        self.assertEqual(set(d), {"2003", "2004"})                    # lines 10, 11

    def test_2023_partition_covers_every_widget_exactly_once(self):
        P = pdf_sch_d_540.PdfSchD540
        mapping_t = set(P.get_mapping(2023).values())
        agg_t = set(P.get_aggregations(2023).keys())
        deriv_t = set(P.get_derivations(2023).keys())
        supp = set(P.get_suppressed(2023))
        # pairwise disjoint
        parts = [mapping_t, agg_t, deriv_t, supp]
        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                self.assertEqual(parts[i] & parts[j], set(),
                                 "a 2023 widget is owned by two registries")
        accounted = mapping_t | agg_t | deriv_t | supp
        self.assertEqual(
            accounted, self.real_fields,
            "2023 partition does not exactly cover the live probe field set")

    def test_2023_no_checkbox_states(self):
        self.assertEqual(pdf_sch_d_540.PdfSchD540.get_checkbox_states(2023), {})


# ---------------------------------------------------------------------------
# TY2021 support
# ---------------------------------------------------------------------------


class PdfSchD540MappingTests2021(unittest.TestCase):
    """TY2021 Sch D (540) mapping — a FOURTH FTB field-naming scheme
    ("Text Field N"), disjoint from 2023's bare zero-padded numbers and
    2024/2025's prefixed schemes. Fresh air-gapped probe, controller-
    reconciled against the 2021 template; five direct keys wired (header
    name/SSN, line 8 net gain, line 12a/12b Sch CA deltas) plus two
    derivations (lines 10/11 federal/CA net)."""

    @classmethod
    def setUpClass(cls):
        pdf_path = (Path(__file__).resolve().parent.parent
                    / "pdfs" / "california" / "2021" / "sch_d_540.pdf")
        cls.real_fields = frozenset(PdfReader(pdf_path).get_fields() or {})

    def test_2021_mapped_cells(self):
        m = pdf_sch_d_540.PdfSchD540.get_mapping(2021)
        self.assertEqual(m["sch_d_540_taxpayer_name"], "Text Field 2")
        self.assertEqual(m["sch_d_540_taxpayer_ssn"], "Text Field 3")
        self.assertEqual(m["sch_d_540_net_capital_gain"], "Text Field 121")     # line 8
        self.assertEqual(m["sch_d_540_total_subtractions"], "Text Field 125")  # line 12a
        self.assertEqual(m["sch_d_540_total_additions"], "Text Field 126")     # line 12b

    def test_2021_no_aggregations_or_checkbox_states(self):
        P = pdf_sch_d_540.PdfSchD540
        self.assertEqual(P.get_aggregations(2021), {})
        self.assertEqual(P.get_checkbox_states(2021), {})

    def test_2021_get_derivations_includes_federal_ca_net_lines(self):
        """Lines 10 (federal net) and 11 (CA net) ported from 2023. Target
        boxes verified against the 2021 template's own /TU tooltips and probe
        render; formulas carried from 2023."""
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2021)
        self.assertEqual(len(derivations), 2)
        # Line 10 — federal Form 1040/1040-SR line 7 (federal net).
        self.assertIn("Text Field 123", derivations)
        # Line 11 — California gain from line 8 / loss from line 9 (CA net).
        self.assertIn("Text Field 124", derivations)

    def test_2021_derivation_lambdas_resolve_expected_compute_keys(self):
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2021)
        compute = {
            "sch_d_540_federal_net": 12_345,
            "sch_d_540_net_capital_gain": 67_890,
        }
        # Line 10 pulls the federal net; line 11 pulls the CA net.
        self.assertEqual(derivations["Text Field 123"](compute), 12_345)
        self.assertEqual(derivations["Text Field 124"](compute), 67_890)

    def test_2021_derivation_targets_are_real_template_fields(self):
        project_root = Path(__file__).resolve().parent.parent
        template = project_root / "pdfs" / "california" / "2021" / "sch_d_540.pdf"
        fields = PdfReader(template).get_fields() or {}
        derivations = pdf_sch_d_540.PdfSchD540.get_derivations(2021)
        for path in derivations:
            self.assertIn(
                path, fields,
                f"derivation target {path!r} is not a real field on the 2021 template",
            )

    def test_2021_partition_covers_every_widget_exactly_once(self):
        P = pdf_sch_d_540.PdfSchD540
        mapping_t = set(P.get_mapping(2021).values())
        agg_t = set(P.get_aggregations(2021).keys())
        deriv_t = set(P.get_derivations(2021).keys())
        supp = set(P.get_suppressed(2021))
        # pairwise disjoint
        parts = [mapping_t, agg_t, deriv_t, supp]
        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                self.assertEqual(parts[i] & parts[j], set(),
                                 "a 2021 widget is owned by two registries")
        accounted = mapping_t | agg_t | deriv_t | supp
        self.assertEqual(
            accounted, self.real_fields,
            "2021 partition does not exactly cover the live probe field set")


class PdfSchD540FilledEmit2021Tests(unittest.TestCase):
    """Filled-emit round-trip for the 2021 pack: fill the real 2021 template
    with distinctive values for all five mapped keys, read the filled PDF
    back with pypdf, and assert each value landed at its mapped field path.
    Explicitly checks that total_subtractions (line 12a, col B) and
    total_additions (line 12b, col C) land at their DISTINCT fields — the
    regression a subtractions/additions swap would trip."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_2021_fill_then_read_back(self):
        project_root = Path(__file__).resolve().parent.parent
        template = project_root / "pdfs" / "california" / "2021" / "sch_d_540.pdf"
        out = self.tmp / "sch_d_540_2021_filled.pdf"

        values = {
            "sch_d_540_taxpayer_name": "Zephyrine Quillfeather",
            "sch_d_540_taxpayer_ssn": "PROBE-ID-ROUNDTRIP",
            "sch_d_540_net_capital_gain": 48_213,
            "sch_d_540_total_subtractions": 9_271,
            "sch_d_540_total_additions": 6_154,
        }

        PdfFiller().fill(
            template_path=template,
            output_path=out,
            field_mapping=pdf_sch_d_540.PdfSchD540.get_mapping(2021),
            values=values,
        )

        fields = PdfReader(out).get_fields() or {}

        def _v(path: str) -> str:
            fld = fields.get(path)
            self.assertIsNotNone(fld, f"field {path!r} missing from filled PDF")
            v = fld.get("/V")
            return "" if v is None else str(v)

        self.assertEqual(_v("Text Field 2"), "Zephyrine Quillfeather")
        self.assertEqual(_v("Text Field 3"), "PROBE-ID-ROUNDTRIP")
        self.assertEqual(_v("Text Field 121"), "48213")
        # The col-B/col-C placement — a subtractions/additions swap would
        # trip these two assertions against each other.
        self.assertEqual(_v("Text Field 125"), "9271")
        self.assertEqual(_v("Text Field 126"), "6154")


class PdfSchD540FilledEmit2022Tests(unittest.TestCase):
    """Filled-emit round-trip for the 2022 pack, INHERITED from 2023 by
    field-tree identity (diff_pdf_fields-IDENTICAL, controller-verified).
    Fill the real 2022 template with distinctive values for all five mapped
    keys, read the filled PDF back with pypdf, and assert each value landed
    at its mapped (bare-number 2023-scheme) field path. Explicitly checks
    that total_subtractions (line 12a, col B) and total_additions (line 12b,
    col C) land at their DISTINCT fields — the swap a subtractions/additions
    regression would trip."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_2022_fill_then_read_back(self):
        project_root = Path(__file__).resolve().parent.parent
        template = project_root / "pdfs" / "california" / "2022" / "sch_d_540.pdf"
        out = self.tmp / "sch_d_540_2022_filled.pdf"

        values = {
            "sch_d_540_taxpayer_name": "Bartholomew Nettershaw",
            "sch_d_540_taxpayer_ssn": "PROBE-ID-2022-RT",
            "sch_d_540_net_capital_gain": 71_804,
            "sch_d_540_total_subtractions": 3_142,
            "sch_d_540_total_additions": 8_925,
        }

        PdfFiller().fill(
            template_path=template,
            output_path=out,
            field_mapping=pdf_sch_d_540.PdfSchD540.get_mapping(2022),
            values=values,
        )

        fields = PdfReader(out).get_fields() or {}

        def _v(path: str) -> str:
            fld = fields.get(path)
            self.assertIsNotNone(fld, f"field {path!r} missing from filled PDF")
            v = fld.get("/V")
            return "" if v is None else str(v)

        mapping = pdf_sch_d_540.PdfSchD540.get_mapping(2022)
        self.assertEqual(_v(mapping["sch_d_540_taxpayer_name"]),
                         "Bartholomew Nettershaw")
        self.assertEqual(_v(mapping["sch_d_540_taxpayer_ssn"]),
                         "PROBE-ID-2022-RT")
        self.assertEqual(_v(mapping["sch_d_540_net_capital_gain"]), "71804")
        # The col-B/col-C placement — a subtractions/additions swap would
        # trip these two assertions against each other.
        self.assertEqual(_v(mapping["sch_d_540_total_subtractions"]), "3142")
        self.assertEqual(_v(mapping["sch_d_540_total_additions"]), "8925")
