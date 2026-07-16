"""Mapping-shape and field-existence tests for FTB Form 540 PDF mapping.

Per-field-path correctness lives in the T12 probe artifact
(`docs/plans/sp3-t12-f540-probe.md`); this test verifies (a) the
partition invariant — every f540.compute() output key is owned by
exactly one of MAPPING / AGGREGATIONS / SUPPRESSED, with derivations
consuming but not owning — and (b) every mapped/aggregated/derived PDF
field path resolves to a real field in `pdfs/california/2025/f540.pdf`.
"""

from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
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
        # 2021 now resolves (direct-map-only emit pack); 2022 remains a gap.
        for year in (2022, 2026):
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


class PdfF540FilledEmit2021Tests(unittest.TestCase):
    """Filled-emit round-trip for the TY2021 Form 540 DIRECT-MAP-ONLY pack.

    2021 is a FOURTH FTB field-naming scheme: mixed bare-numeric AcroForm
    names ('2009'/'2017'/'3008') plus a few 'Text Field N' widgets (residence
    county = 'Text Field 439'). Sequence numbers do NOT line up with 2023 —
    2021's exemption credit is box 2017 (2023's box 2031) and its renter
    credit is box 2031 (2023's exemption credit). This fills the REAL 2021
    template via PdfFiller().fill(...) with distinctive values and reads each
    back at its mapped path via pypdf — the load-bearing check is that
    f540_exemption_credit lands in box 2017 (line 32 "Exemption credits"
    placement regression), NOT a 2023-style box.

    The direct-mapped cells asserted here are a subset; the 22 ported
    derivations (line totals / tax-source + filing-status checkboxes /
    sign-split refund-owe) are covered by PdfF540Derivations2021Tests below.
    """

    @staticmethod
    def _read_v(pdf_path, field_path):
        """Read one AcroForm field's /V, normalizing thousands-comma / $."""
        fields = PdfReader(str(pdf_path)).get_fields() or {}
        got = fields[field_path].get("/V") or ""
        return str(got).replace(",", "").replace("$", "").strip()

    def test_2021_filled_emit_round_trip(self):
        root = Path(__file__).resolve().parent.parent
        template = root / "pdfs" / "california" / "2021" / "f540.pdf"

        mapping = pdf_f540.PdfF540.get_mapping(2021)
        aggregations = pdf_f540.PdfF540.get_aggregations(2021)
        derivations = pdf_f540.PdfF540.get_derivations(2021)
        checkbox_states = pdf_f540.PdfF540.get_checkbox_states(2021)

        # Distinctive, non-round values (no SSN/EIN-shaped sentinels).
        values = {
            "f540_taxpayer_first_name": "Marisol",
            "f540_taxpayer_last_name": "Vandermeer",
            "f540_ca_agi": 84321,
            "f540_taxable_income": 71234,
            "f540_ca_tax": 3456,
            "f540_exemption_credit": 129,
            "f540_renter_credit": 60,
            "f540_estimated_payments": 2750,
            "f540_use_tax": 41,
            "f540_voluntary_contributions": 27,
            "f540_estimated_tax_penalty": 18,
        }

        # Expected {mapped PDF field path: rendered read-back string}.
        expected = {
            mapping["f540_taxpayer_first_name"]: "Marisol",
            mapping["f540_taxpayer_last_name"]: "Vandermeer",
            mapping["f540_ca_agi"]: "84321",
            mapping["f540_taxable_income"]: "71234",
            mapping["f540_ca_tax"]: "3456",
            # Line-32 placement regression: exemption credit MUST land in 2017.
            mapping["f540_exemption_credit"]: "129",
            mapping["f540_renter_credit"]: "60",
            mapping["f540_estimated_payments"]: "2750",   # payment line
            mapping["f540_use_tax"]: "41",
            mapping["f540_voluntary_contributions"]: "27",
            mapping["f540_estimated_tax_penalty"]: "18",
        }

        # Pin the load-bearing placement explicitly (2021 namespace, not 2023).
        self.assertEqual(mapping["f540_exemption_credit"], "2017")

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "f540_2021_filled.pdf"
            PdfFiller().fill(
                template, out, mapping, values,
                aggregations=aggregations,
                derivations=derivations,
                checkbox_states=checkbox_states,
            )
            for field_path, want in expected.items():
                with self.subTest(field=field_path):
                    self.assertEqual(self._read_v(out, field_path), want)


class PdfF540Derivations2021Tests(unittest.TestCase):
    """The 22-cell get_derivations surface ported additively from 2023 to the
    2021 pack — 15 line-total / refund-owe text cells + 2 line-31 tax-source
    checkboxes + 5 filing-status checkboxes. Every target box was re-placed
    from the 2021 template's own /TU tooltips (the 2021 namespace differs from
    2023); this test guards that each derivation target is a real 2021 field,
    that the checkbox targets carry a /Yes ON-state in their own /_States_, and
    that the arithmetic/enum lambdas resolve as expected."""

    @classmethod
    def setUpClass(cls):
        cls.derivations = pdf_f540.PdfF540.get_derivations(2021)
        root = Path(__file__).resolve().parent.parent
        template = root / "pdfs" / "california" / "2021" / "f540.pdf"
        cls.fields = PdfReader(str(template)).get_fields() or {}

    def test_2021_derivations_count_is_22(self):
        self.assertEqual(len(self.derivations), 22)

    def test_2021_every_derivation_target_is_a_real_2021_field(self):
        for path in self.derivations:
            with self.subTest(path=path):
                self.assertIn(
                    path, self.fields,
                    f"derivation target {path!r} is not a real field on the "
                    f"2021 f540 template",
                )

    def test_2021_checkbox_targets_have_yes_on_state(self):
        # Line-31 tax-source + five filing-status checkboxes: the ON value we
        # emit ("/Yes") must be a member of each box's own /_States_.
        checkbox_targets = [p for p in self.derivations if p.endswith(" CB")]
        self.assertEqual(len(checkbox_targets), 7)
        for path in checkbox_targets:
            with self.subTest(path=path):
                states = self.fields[path].get("/_States_")
                self.assertIsNotNone(states, f"{path} has no /_States_")
                self.assertIn("/Yes", states)

    def test_2021_filing_status_checkboxes_cover_all_statuses(self):
        # Every FilingStatus must resolve to a distinct 2021 checkbox target.
        cells = set(pdf_f540._FILING_STATUS_CB_2021.values())
        self.assertEqual(len(cells), len(FilingStatus))
        for status, cell in pdf_f540._FILING_STATUS_CB_2021.items():
            with self.subTest(status=status):
                self.assertIn(cell, self.derivations)
                self.assertEqual(self.derivations[cell]({"f540_filing_status": status}), "/Yes")
                # A different status leaves the box off.
                other = next(s for s in FilingStatus if s != status)
                self.assertEqual(self.derivations[cell]({"f540_filing_status": other}), "/Off")

    def test_2021_tax_source_checkboxes_split_on_taxable_income(self):
        # Box 2012 (tax table) on at/below 100k; box 2013 (rate schedule) above.
        self.assertEqual(self.derivations["2012 CB"]({"f540_taxable_income": 100_000}), "/Yes")
        self.assertEqual(self.derivations["2012 CB"]({"f540_taxable_income": 100_001}), "/Off")
        self.assertEqual(self.derivations["2013 CB"]({"f540_taxable_income": 100_001}), "/Yes")
        self.assertEqual(self.derivations["2013 CB"]({"f540_taxable_income": 100_000}), "/Off")

    def test_2021_line_totals_resolve_from_compute_keys(self):
        # A representative flow: refund case (payments exceed tax).
        c = {
            "f540_ca_tax": 3000,
            "f540_exemption_credit": 129,
            "f540_renter_credit": 60,
            "f540_estimated_payments": 5000,
            "f540_use_tax": 40,
        }
        d = self.derivations
        self.assertEqual(d["2018"](c), 2871)          # line 33 = 3000 - 129
        self.assertEqual(d["2022"](c), 2871)          # line 35 = line 33
        self.assertEqual(d["2032"](c), 60)            # line 47 = renter credit
        self.assertEqual(d["2033"](c), 2811)          # line 48 = 2871 - 60
        self.assertEqual(d["3006"](c), 2811)          # line 65 total tax = line 48
        self.assertEqual(d["3013"](c), 5000)          # line 78 total payments
        self.assertEqual(d["3016"](c), 4960)          # line 93 = 5000 - 40
        self.assertEqual(d["3017"](c), 4960)          # line 95 = line 93
        self.assertEqual(d["3018"](c), 2149)          # line 97 = 4960 - 2811
        self.assertEqual(d["3021"](c), 0)             # line 100 tax due = 0

    def test_2021_sign_split_refund_and_owe(self):
        d = self.derivations
        self.assertEqual(d["5003"]({"f540_total_liability": 1234}), 1234)   # owe
        self.assertIsNone(d["5003"]({"f540_total_liability": -1234}))       # no owe
        self.assertEqual(d["5009"]({"f540_total_liability": -1234}), 1234)  # refund
        self.assertIsNone(d["5009"]({"f540_total_liability": 1234}))        # no refund
