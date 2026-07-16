"""Mapping-shape and field-existence tests for FTB Schedule CA (540) PDF mapping.

Per-field-path correctness is tooltip-verified (T14 probe artifact at
`docs/plans/sp3-t14-sch-ca-probe.md` records the /TU annotations behind
each widget). This test verifies (a) the partition invariant — every
Sch CA compute key the kernel may emit is owned by exactly one of
MAPPING / AGGREGATIONS / SUPPRESSED, with derivations consuming but not
owning — and (b) every mapped/aggregated/derived PDF field path resolves
to a real field in `pdfs/california/2025/sch_ca.pdf`.
"""

from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings import pdf_sch_ca


# Compute keys the kernel may emit. Per-line `_col_a` keys are
# conditional (only emitted when a federal-results value is present);
# the partition invariant treats them as expected for the 20 v1-wired
# lines in `_FEDERAL_TO_SCH_CA_COL_A_MAP`. The 4 `_subtractions` keys
# correspond to the lines `derive_auto_divergences` emits a mechanical
# subtraction for (RRB, SS, state-tax-refund, UI/PFL).
_EXPECTED_COMPUTE_KEYS = frozenset({
    # Always-emitted totals
    "sch_ca_federal_agi",
    "sch_ca_total_subtractions",
    "sch_ca_total_additions",
    "sch_ca_ca_agi",
    # Conditional per-line Col A passthrough — one per
    # `_FEDERAL_TO_SCH_CA_COL_A_MAP` entry (20 v1 lines)
    "sch_ca_line_part_i_a_1z_col_a",
    "sch_ca_line_part_i_a_2_col_a",
    "sch_ca_line_part_i_a_3_col_a",
    "sch_ca_line_part_i_a_4_col_a",
    "sch_ca_line_part_i_a_5b_col_a",
    "sch_ca_line_part_i_a_6_col_a",
    "sch_ca_line_part_i_a_7_col_a",
    "sch_ca_line_part_i_b_1_col_a",
    "sch_ca_line_part_i_b_3_col_a",
    "sch_ca_line_part_i_b_4_col_a",
    "sch_ca_line_part_i_b_5_col_a",
    "sch_ca_line_part_i_b_6_col_a",
    "sch_ca_line_part_i_b_7_col_a",
    "sch_ca_line_part_i_b_8z_col_a",
    "sch_ca_line_part_i_c_11_col_a",
    "sch_ca_line_part_i_c_13_col_a",
    "sch_ca_line_part_i_c_15_col_a",
    "sch_ca_line_part_i_c_17_col_a",
    "sch_ca_line_part_i_c_20_col_a",
    "sch_ca_line_part_i_c_21_col_a",
    # Conditional per-line subtractions emitted by auto-derive
    # (4 lines: §A 5b RRB, §A 6 SS, §B 1 state refund, §B 7 UI/PFL).
    "sch_ca_line_part_i_a_5b_subtractions",
    "sch_ca_line_part_i_a_6_subtractions",
    "sch_ca_line_part_i_b_1_subtractions",
    "sch_ca_line_part_i_b_7_subtractions",
})


class PdfSchCaMappingTests(unittest.TestCase):
    def test_2025_get_mapping_returns_dict(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_2025_get_aggregations_is_empty(self):
        # Per-line and total sums are kernel-emitted; no PDF cell
        # receives a sum of multiple compute keys at fill time.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_aggregations(2025), {})

    def test_2025_get_derivations_is_empty(self):
        # No within-form arithmetic wired in v1.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_derivations(2025), {})

    def test_2025_get_checkbox_states_is_empty(self):
        # The single /Btn widget on the form is out-of-scope for v1.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_checkbox_states(2025), {})

    def test_2025_unsupported_year_raises(self):
        for year in (2020, 2019, 2026):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    pdf_sch_ca.PdfSchCa.get_mapping(year)

    def test_2025_partition_invariant(self):
        """Every expected kernel-emitted compute key is OWNED by exactly
        one of `_MAPPING_2025`, `_AGGREGATIONS_2025`, or
        `_SUPPRESSED_2025`. Derivation lambdas (none in Sch CA v1)
        CONSUME compute keys but do not OWN them.
        """
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2025)
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2025)

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

    def test_2025_b1_subtractions_is_mapped(self):
        # Tooltip-verified: widget 1053 is "Line 1. Column B. Subtractions"
        # for the §B 1 state-tax-refund row. The auto-derived subtraction
        # routes to this per-line cell (was incorrectly believed to be
        # a form anomaly in earlier T14 work).
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2025)
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        self.assertIn("sch_ca_line_part_i_b_1_subtractions", mapping)
        self.assertNotIn("sch_ca_line_part_i_b_1_subtractions", suppressed)
        self.assertEqual(
            mapping["sch_ca_line_part_i_b_1_subtractions"],
            "540ca_form - 1053",
        )

    def test_2025_b1_col_a_widget_is_correct(self):
        # Tooltip-verified: widget 1052 (NOT 1054) is the §B 1 Col A.
        # Widget 1054 is "Line 2a. Alimony received. Column A." Existing
        # T14 code had this swapped; this test guards against regression.
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        self.assertEqual(
            mapping["sch_ca_line_part_i_b_1_col_a"],
            "540ca_form - 1052",
        )

    def test_2025_ca_agi_is_suppressed_transit_only(self):
        # sch_ca_ca_agi has no Sch CA PDF cell; it flows to f540 line 13
        # via the f540_ca_agi mapping. Verify the ownership.
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2025)
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        self.assertIn("sch_ca_ca_agi", suppressed)
        self.assertNotIn("sch_ca_ca_agi", mapping)

    def test_2025_column_omissions_suppressed(self):
        # Lines whose 2025 form omits a column widget must declare the
        # omission via SUPPRESSED so worksheet divergences routed there
        # are explicitly known to flow through totals only.
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2025)
        # Lines with no Col C widget (subtraction-only conformance)
        for key in (
            "sch_ca_line_part_i_a_6_additions",   # SS
            "sch_ca_line_part_i_b_1_additions",   # state refund
            "sch_ca_line_part_i_b_7_additions",   # UI
            "sch_ca_line_part_i_c_11_additions",  # educator
            "sch_ca_line_part_i_c_13_additions",  # HSA
            "sch_ca_line_part_i_c_15_additions",  # SE tax
            "sch_ca_line_part_i_c_17_additions",  # SE health
        ):
            with self.subTest(key=key):
                self.assertIn(key, suppressed)
        # Line with no Col B widget (addition-only conformance)
        self.assertIn("sch_ca_line_part_i_c_21_subtractions", suppressed)

    def test_2025_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/california/2025/sch_ca.pdf.
        """
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "california" / "2025" / "sch_ca.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})

        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2025)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2025)
        derivations = pdf_sch_ca.PdfSchCa.get_derivations(2025)

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

    # ------------------------------------------------------------------
    # 2024 tests
    # ------------------------------------------------------------------

    def test_2024_get_mapping_returns_dict(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2024)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_2024_get_aggregations_is_empty(self):
        # Per-line and total sums are kernel-emitted; no PDF cell
        # receives a sum of multiple compute keys at fill time.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_aggregations(2024), {})

    def test_2024_get_derivations_is_empty(self):
        # No within-form arithmetic wired in v1.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_derivations(2024), {})

    def test_2024_get_checkbox_states_is_empty(self):
        # The single /Btn widget on the 2024 form is out-of-scope for v1.
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_checkbox_states(2024), {})

    def test_2024_partition_invariant(self):
        """Every expected kernel-emitted compute key is OWNED by exactly
        one of `_MAPPING_2024`, `_AGGREGATIONS_2024`, or
        `_SUPPRESSED_2024`. Derivation lambdas (none in Sch CA v1)
        CONSUME compute keys but do not OWN them.
        """
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2024)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2024)
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2024)

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

    def test_2024_ca_agi_is_suppressed_transit_only(self):
        # sch_ca_ca_agi has no Sch CA PDF cell; it flows to f540 line 13
        # via the f540_ca_agi mapping. Verify the ownership.
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2024)
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2024)
        self.assertIn("sch_ca_ca_agi", suppressed)
        self.assertNotIn("sch_ca_ca_agi", mapping)

    def test_2024_column_omissions_suppressed(self):
        # Lines whose 2024 form omits a column widget must declare the
        # omission via SUPPRESSED so worksheet divergences routed there
        # are explicitly known to flow through totals only.
        # Tooltip-verified: same column structure as 2025.
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2024)
        # Lines with no Col C widget (subtraction-only conformance)
        for key in (
            "sch_ca_line_part_i_a_6_additions",   # SS
            "sch_ca_line_part_i_b_1_additions",   # state refund
            "sch_ca_line_part_i_b_7_additions",   # UI
            "sch_ca_line_part_i_c_11_additions",  # educator
            "sch_ca_line_part_i_c_13_additions",  # HSA
            "sch_ca_line_part_i_c_15_additions",  # SE tax
            "sch_ca_line_part_i_c_17_additions",  # SE health
        ):
            with self.subTest(key=key):
                self.assertIn(key, suppressed)
        # Line with no Col B widget (addition-only conformance)
        self.assertIn("sch_ca_line_part_i_c_21_subtractions", suppressed)

    def test_2024_every_pdf_target_is_a_real_pdf_field(self):
        """Every PDF field path referenced (in mapping values, aggregation
        keys, or derivation keys) must resolve to a field that exists in
        pdfs/california/2024/sch_ca.pdf.
        """
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2024" / "sch_ca.pdf")
        real = set(reader.get_fields() or {})

        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2024)
        derivations = pdf_sch_ca.PdfSchCa.get_derivations(2024)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2024)

        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2024 PDF: {bad}")

    # ------------------------------------------------------------------
    # 2023 tests
    #
    # 2023 is the THIRD FTB naming scheme: bare numbers ('1027', '2035'),
    # no '540ca_form - ' prefix. 54 of 57 fields keep the same sequence
    # number as 2025 (prefix stripped); line 8z's three cells SHIFTED
    # 2038/2039/2040 -> 2035/2036/2037 (invisible-shift trap, tooltip-
    # caught). Column structure identical to 2024/2025 (Step-1 conformity).
    # ------------------------------------------------------------------

    def test_2023_registries_empty_where_expected(self):
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_aggregations(2023), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_derivations(2023), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_checkbox_states(2023), {})

    def test_2023_partition_invariant(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2023)
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2023)
        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed
        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(missing, set(), f"unaccounted: {sorted(missing)}")
        in_mapping = set(mapping.keys()) & _EXPECTED_COMPUTE_KEYS
        double = ((in_mapping & agg_contributors) | (in_mapping & suppressed)
                  | (agg_contributors & suppressed))
        self.assertEqual(double, set(), f"double-accounted: {sorted(double)}")

    def test_2023_bare_number_scheme_no_prefix(self):
        # Every 2023 field path is a bare number — the '540ca_form - '
        # prefix of 2024/2025 must be gone.
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        for key, field in mapping.items():
            with self.subTest(key=key):
                self.assertNotIn("540ca_form", field)
                self.assertTrue(field.isdigit(), f"{field!r} not a bare number")

    def test_2023_line_8z_shifted_from_2024(self):
        # The one sequence-number shift vs 2024/2025 — regression guard
        # against assuming the prefix-strip carried every number.
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        self.assertEqual(mapping["sch_ca_line_part_i_b_8z_col_a"], "2035")
        self.assertEqual(mapping["sch_ca_line_part_i_b_8z_subtractions"], "2036")
        self.assertEqual(mapping["sch_ca_line_part_i_b_8z_additions"], "2037")

    def test_2023_ca_agi_is_suppressed_transit_only(self):
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2023)
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        self.assertIn("sch_ca_ca_agi", suppressed)
        self.assertNotIn("sch_ca_ca_agi", mapping)

    def test_2023_column_omissions_suppressed(self):
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2023)
        for key in (
            "sch_ca_line_part_i_a_6_additions",   # SS
            "sch_ca_line_part_i_b_1_additions",   # state refund
            "sch_ca_line_part_i_b_7_additions",   # UI
            "sch_ca_line_part_i_c_11_additions",  # educator
            "sch_ca_line_part_i_c_13_additions",  # HSA
            "sch_ca_line_part_i_c_15_additions",  # SE tax
            "sch_ca_line_part_i_c_17_additions",  # SE health
        ):
            with self.subTest(key=key):
                self.assertIn(key, suppressed)
        self.assertIn("sch_ca_line_part_i_c_21_subtractions", suppressed)

    def test_2023_every_pdf_target_is_a_real_pdf_field(self):
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2023" / "sch_ca.pdf")
        real = set(reader.get_fields() or {})
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        derivations = pdf_sch_ca.PdfSchCa.get_derivations(2023)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2023)
        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2023 PDF: {bad}")

    # ------------------------------------------------------------------
    # 2022 tests — INHERITED from 2023 by field-tree identity
    # (diff_pdf_fields-IDENTICAL, controller-verified).
    # ------------------------------------------------------------------

    def test_2022_registries_empty_where_expected(self):
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_aggregations(2022), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_derivations(2022), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_checkbox_states(2022), {})

    def test_2022_partition_invariant(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2022)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2022)
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2022)
        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed
        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(missing, set(), f"unaccounted: {sorted(missing)}")
        in_mapping = set(mapping.keys()) & _EXPECTED_COMPUTE_KEYS
        double = ((in_mapping & agg_contributors) | (in_mapping & suppressed)
                  | (agg_contributors & suppressed))
        self.assertEqual(double, set(), f"double-accounted: {sorted(double)}")

    def test_2022_inherits_2023_mapping(self):
        # 2022 is IDENTICAL to 2023 by field-tree diff; the mapping payload
        # is inherited verbatim.
        self.assertEqual(
            pdf_sch_ca.PdfSchCa.get_mapping(2022),
            pdf_sch_ca.PdfSchCa.get_mapping(2023),
        )

    def test_2022_every_pdf_target_is_a_real_pdf_field(self):
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2022" / "sch_ca.pdf")
        real = set(reader.get_fields() or {})
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2022)
        derivations = pdf_sch_ca.PdfSchCa.get_derivations(2022)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2022)
        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2022 PDF: {bad}")


    # ------------------------------------------------------------------
    # 2021 tests — FRESH air-gapped direct-map probe (controller-reconciled
    # 57/57 against the 2021 template). Bare-numeric FTB namespace like 2023,
    # but 2021 renumbers its widgets end-to-end so it does NOT inherit 2023
    # (e.g. name/ssn 1001/1002 vs 2023's 1000/1001; line 1z Col A 1003 vs
    # 2023's 1027). Zero-derivation (allowlisted). Column structure identical
    # to 2022/2023.
    # ------------------------------------------------------------------

    def test_2021_registries_empty_where_expected(self):
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_aggregations(2021), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_derivations(2021), {})
        self.assertEqual(pdf_sch_ca.PdfSchCa.get_checkbox_states(2021), {})

    def test_2021_partition_invariant(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2021)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2021)
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2021)
        agg_contributors = {k for keys in aggregations.values() for k in keys}
        accounted = set(mapping.keys()) | agg_contributors | suppressed
        missing = _EXPECTED_COMPUTE_KEYS - accounted
        self.assertEqual(missing, set(), f"unaccounted: {sorted(missing)}")
        in_mapping = set(mapping.keys()) & _EXPECTED_COMPUTE_KEYS
        double = ((in_mapping & agg_contributors) | (in_mapping & suppressed)
                  | (agg_contributors & suppressed))
        self.assertEqual(double, set(), f"double-accounted: {sorted(double)}")

    def test_2021_is_fresh_map_not_2023_inherit(self):
        # 2021 renumbers its widgets end-to-end; it must NOT be the 2023
        # payload. Guards against an accidental inherit.
        m2021 = pdf_sch_ca.PdfSchCa.get_mapping(2021)
        m2023 = pdf_sch_ca.PdfSchCa.get_mapping(2023)
        self.assertNotEqual(m2021, m2023)
        self.assertEqual(m2021["sch_ca_taxpayer_name"], "1001")
        self.assertEqual(m2021["sch_ca_line_part_i_a_1z_col_a"], "1003")

    def test_2021_bare_number_scheme_no_prefix(self):
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2021)
        for key, field in mapping.items():
            with self.subTest(key=key):
                self.assertNotIn("540ca_form", field)
                self.assertTrue(field.isdigit(), f"{field!r} not a bare number")

    def test_2021_ca_agi_is_suppressed_transit_only(self):
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2021)
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2021)
        self.assertIn("sch_ca_ca_agi", suppressed)
        self.assertNotIn("sch_ca_ca_agi", mapping)

    def test_2021_column_omissions_suppressed(self):
        suppressed = pdf_sch_ca.PdfSchCa.get_suppressed(2021)
        for key in (
            "sch_ca_line_part_i_a_6_additions",   # SS
            "sch_ca_line_part_i_b_1_additions",   # state refund
            "sch_ca_line_part_i_b_7_additions",   # UI
            "sch_ca_line_part_i_c_11_additions",  # educator
            "sch_ca_line_part_i_c_13_additions",  # HSA
            "sch_ca_line_part_i_c_15_additions",  # SE tax
            "sch_ca_line_part_i_c_17_additions",  # SE health
        ):
            with self.subTest(key=key):
                self.assertIn(key, suppressed)
        self.assertIn("sch_ca_line_part_i_c_21_subtractions", suppressed)

    def test_2021_every_pdf_target_is_a_real_pdf_field(self):
        root = Path(__file__).resolve().parent.parent
        reader = PdfReader(root / "pdfs" / "california" / "2021" / "sch_ca.pdf")
        real = set(reader.get_fields() or {})
        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2021)
        derivations = pdf_sch_ca.PdfSchCa.get_derivations(2021)
        aggregations = pdf_sch_ca.PdfSchCa.get_aggregations(2021)
        targets = set(mapping.values()) | set(derivations) | set(aggregations)
        bad = sorted(t for t in targets if t not in real)
        self.assertEqual(bad, [], f"field paths not in 2021 PDF: {bad}")


class PdfSchCaFilledEmit2021Tests(unittest.TestCase):
    """Filled-emit round-trip for the FRESH 2021 direct-map pack. Fill the
    real 2021 template with DISTINCTIVE values for every mapped compute key,
    read the filled PDF back with pypdf, and assert each value landed at its
    mapped (bare-number 2021-scheme) field path — proving the fresh probe
    addresses real 2021 widgets, not just that the paths exist."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_2021_fill_then_read_back(self):
        project_root = Path(__file__).resolve().parent.parent
        template = project_root / "pdfs" / "california" / "2021" / "sch_ca.pdf"
        out = self.tmp / "sch_ca_2021_filled.pdf"

        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2021)

        # Distinctive value per mapped key. Header keys get non-numeric
        # sentinels (no SSN/EIN shape); every numeric line-cell gets a
        # unique amount so a mis-routed value would collide detectably.
        string_values = {
            "sch_ca_taxpayer_name": "Wilhelmina Frostpocket",
            "sch_ca_taxpayer_ssn": "PROBE-ID-2021-RT",
        }
        values: dict[str, object] = {}
        numeric_keys = [k for k in mapping if k not in string_values]
        for idx, key in enumerate(sorted(numeric_keys)):
            values[key] = 200_003 + idx * 7  # distinct per cell
        values.update(string_values)

        PdfFiller().fill(
            template_path=template,
            output_path=out,
            field_mapping=mapping,
            values=values,
        )

        fields = PdfReader(out).get_fields() or {}

        def _v(path: str) -> str:
            fld = fields.get(path)
            self.assertIsNotNone(fld, f"field {path!r} missing from filled PDF")
            v = fld.get("/V")
            return "" if v is None else str(v)

        for key, path in mapping.items():
            with self.subTest(key=key):
                expected = values[key]
                self.assertEqual(
                    _v(path), str(expected),
                    f"{key} did not land at its mapped path {path!r}",
                )


class PdfSchCaFilledEmit2022Tests(unittest.TestCase):
    """Filled-emit round-trip for the 2022 pack, INHERITED from 2023 by
    field-tree identity. Fill the real 2022 template with DISTINCTIVE values
    for every mapped compute key, read the filled PDF back with pypdf, and
    assert each value landed at its mapped (bare-number 2023-scheme) field
    path — proving the inherited map addresses real 2022 widgets, not just
    that the paths exist."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_2022_fill_then_read_back(self):
        project_root = Path(__file__).resolve().parent.parent
        template = project_root / "pdfs" / "california" / "2022" / "sch_ca.pdf"
        out = self.tmp / "sch_ca_2022_filled.pdf"

        mapping = pdf_sch_ca.PdfSchCa.get_mapping(2022)

        # Distinctive value per mapped key. Header keys get non-numeric
        # sentinels (no SSN/EIN shape); every numeric line-cell gets a
        # unique amount so a mis-routed value would collide detectably.
        string_values = {
            "sch_ca_taxpayer_name": "Wilhelmina Frostpocket",
            "sch_ca_taxpayer_ssn": "PROBE-ID-2022-RT",
        }
        values: dict[str, object] = {}
        numeric_keys = [k for k in mapping if k not in string_values]
        for idx, key in enumerate(sorted(numeric_keys)):
            values[key] = 100_003 + idx * 7  # distinct per cell
        values.update(string_values)

        PdfFiller().fill(
            template_path=template,
            output_path=out,
            field_mapping=mapping,
            values=values,
        )

        fields = PdfReader(out).get_fields() or {}

        def _v(path: str) -> str:
            fld = fields.get(path)
            self.assertIsNotNone(fld, f"field {path!r} missing from filled PDF")
            v = fld.get("/V")
            return "" if v is None else str(v)

        for key, path in mapping.items():
            with self.subTest(key=key):
                expected = values[key]
                self.assertEqual(
                    _v(path), str(expected),
                    f"{key} did not land at its mapped path {path!r}",
                )
