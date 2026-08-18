import unittest

from tenforty.forms.f1040 import compute


class F1040ComputeTests(unittest.TestCase):
    def test_renames_engine_keys_to_pdf_keys(self):
        raw = {
            "interest_income": 100,
            "dividend_income": 200,
            "schd_line16": 300,
            "sche_line26": 400,
            "federal_withheld": 1000,
            "additional_medicare_withheld": 50,
            "agi": 75000,
        }
        result = compute(raw_1040=raw, upstream={})
        self.assertEqual(result["taxable_interest"], 100)
        self.assertEqual(result["ordinary_dividends"], 200)
        self.assertEqual(result["other_income"], 400)
        self.assertEqual(result["federal_withheld_w2"], 1000)
        self.assertEqual(result["federal_withheld_other"], 50)
        self.assertEqual(result["agi"], 75000)
        self.assertEqual(result["agi_page2"], 75000)

        # `schd_line16` is NOT renamed: it is the true, UNCAPPED Schedule D
        # line 16 total and survives under its own name for its own consumers
        # (sch_d_540, the CLI summary, the e2e tests).
        self.assertEqual(result["schd_line16"], 300)

        # And it is NOT copied into `capital_gain_loss`. That key is 1040 line
        # 7a, the IRC §1211(b)-CAPPED transfer from Schedule D line 21, and it
        # comes only from the workbook's `CapitalGains` named range. This raw
        # dict has no `capital_gain_loss`, so compute() must not synthesize
        # one -- pinning against reintroduction of the old convenience alias.
        self.assertNotIn("capital_gain_loss", result)

    def test_sums_line_25d(self):
        raw = {
            "federal_withheld": 1000,
            "additional_medicare_withheld": 50,
            "federal_withheld_1099": 25,
        }
        result = compute(raw_1040=raw, upstream={})
        self.assertEqual(result["federal_withheld"], 1000 + 25 + 50)

    def test_missing_agi_omits_page2(self):
        result = compute(raw_1040={"federal_withheld": 0}, upstream={})
        self.assertNotIn("agi_page2", result)

    def test_qbi_deduction_1040_reemitted_normalized(self):
        # Value arm: the raw workbook value is re-emitted under the
        # oracle-facing key AND matches the normalized qbi_deduction.
        result = compute(
            raw_1040={"_qbi_deduction_1040": 450.0}, upstream={})
        self.assertEqual(result["_qbi_deduction_1040"], 450.0)
        self.assertEqual(result["qbi_deduction"], 450.0)

        # None arm: a blank workbook cell normalizes to 0 on BOTH keys,
        # matching the native spine (which always emits a number).
        result = compute(
            raw_1040={"_qbi_deduction_1040": None}, upstream={})
        self.assertEqual(result["_qbi_deduction_1040"], 0)
        self.assertEqual(result["qbi_deduction"], 0)

    def test_f8959_tax_total_none_normalized_to_zero(self):
        # None arm: a blank F8959_Tax cell normalizes to 0, not None.
        result = compute(raw_1040={"f8959_tax_total": None}, upstream={})
        self.assertEqual(result["f8959_tax_total"], 0)

        # Value arm: a real Additional Medicare Tax amount passes through
        # unchanged.
        result = compute(raw_1040={"f8959_tax_total": 123.0}, upstream={})
        self.assertEqual(result["f8959_tax_total"], 123.0)


class Schedule2TaxHarvestNormalizationTests(unittest.TestCase):
    """1040 line 17 (`schedule2_tax`) prints "0", not blank, in all 5 years.

    The `Schedule2_Tax` named range's formula drifted between year workbooks:
    2021-2023 fall through to a plain `SUM(...)` (numeric 0 when Schedule 2
    Part I is empty), while 2024-2025 wrap that sum in
    `IF(SUM(...)>0, SUM(...), "")` and go BLANK in the identical situation.
    The engine reads a blank cell as Python None and `filing/pdf.py` renders
    0 but SKIPS None, so without normalization the same empty Schedule 2
    Part I prints "0" on a 2023 1040 and nothing at all on a 2024 one.

    These are injected synthetic result dicts, not workbook runs: the
    normalization must stay visible to the standard `-m "not oracle"` gate.

    NO TEST HERE PINS A HARVESTED NUMERIC 0 (the 2021-2023 shape). That input
    exercises no code path in `compute`: the `is None` guard does not fire, so
    0 passes through identically whether the normalization is present or
    absent. Such a test cannot fail under any mutation of the code it claims
    to cover, so it is deliberately ABSENT rather than counted as coverage.

    There is likewise NO test asserting `tax_plus_schedule2 is None`, because
    the workbook cannot produce that input: the `Tax` named range's else-arm
    is unconditionally `SUM(Tax_SubTotal, <line-17 cell>)`, and spreadsheet
    SUM() ignores text in referenced cells, so `Tax` always evaluates to a
    number. Line 18's real hazard is that it is a PLAUSIBLE NUMBER silently
    omitting its own line-16 component on MFJ/MFS -- a mislabeled partial
    total no normalization here can detect or repair. See
    `test_normalization_does_not_reach_the_refusal_keys` for the property
    that actually needs guarding at this layer.
    """

    def test_blank_schedule2_tax_normalizes_to_numeric_zero(self):
        # The 2024/2025 shape: Schedule 2 Part I is empty, so the cell's own
        # `IF(SUM>0, SUM, "")` writes blank -- the vendor's spelling of zero.
        result = compute(raw_1040={"schedule2_tax": None}, upstream={})
        self.assertEqual(result["schedule2_tax"], 0)
        self.assertIsNotNone(result["schedule2_tax"])

    def test_nonzero_schedule2_tax_passes_through_unchanged(self):
        # A real Schedule 2 Part I total must survive untouched --
        # normalization may not clamp, zero, or re-round a live value.
        result = compute(raw_1040={"schedule2_tax": 1234.0}, upstream={})
        self.assertEqual(result["schedule2_tax"], 1234.0)

    def test_normalization_does_not_reach_the_refusal_keys(self):
        """A blank `total_tax` must stay None, never become 0.

        This is the exclusion with real teeth. `total_tax` maps to
        `Tax_SubTotal`, which IS one of the cells gated by the workbook's
        `Birthday_Needed` flag -- unconditionally true for every MFJ/MFS
        return -- so None here is a PRODUCIBLE input meaning "the workbook
        REFUSED to compute your tax", not "your tax is zero". If anyone ever
        generalizes the `schedule2_tax` coercion into a key-set sweep, this
        is what breaks first, and it must: coercing this key would fabricate
        a zero tax on a real return and silently disarm the sibling refusal
        guard.
        """
        result = compute(raw_1040={"total_tax": None}, upstream={})
        self.assertIsNone(result["total_tax"])
