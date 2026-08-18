import unittest

from tenforty.forms.f1040 import compute, workbook_refusal


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


class WorkbookDiagnosticRefusalTests(unittest.TestCase):
    """The workbook DETECTS incomplete input and REFUSES; we must listen.

    The vendor sheet does not only compute. When it cannot, it writes a
    plain-English diagnostic into the `Deduction` named range (the Form 1040
    line-12 CAPTION cell), forces line 12 to 0, and blanks `Tax_SubTotal`
    (line 16, tenforty's `total_tax`). tenforty harvested the blanked number
    and proceeded. `workbook_refusal` is the decision that stops that.

    EVERY TEST HERE INJECTS A DICT. No workbook, no LibreOffice, no oracle
    marker -- deliberately, and it is the point: the oracle tier is deselected
    by the standard `-m "not oracle"` invocation, so a guard reachable only
    through a real workbook run is invisible to every gate this branch
    reports. That invisibility is how this family of defects survived.
    """

    # The five diagnostic branches of the `Deduction` formula, read verbatim
    # from all five workbooks (2021 '1040'!AJ51, 2022 AJ58, 2023 AK64,
    # 2024 AK67, 2025 AU91 -- the ADDRESS drifts, the NAME does not).
    DIAGNOSTICS = (
        "Manual Override",
        "Filing status error.",
        "Birthdate(s) needed.",
        "Filing status error or invalid spouse input.",
        "Filing status not indicated.",
    )

    # The six label branches of the SAME formula -- the captions the cell
    # carries on a return the sheet was willing to compute. These must NOT
    # refuse. The "See Standard ..." labels are assembled with CHAR(10)s and a
    # trailing arrow in the sheet; both the 2021-2024 ("Chart") and the 2025
    # ("Calculation") wordings appear.
    LABELS = (
        "Standard Deduction",
        "Schedule A",
        "See Standard \n Deduction Chart\n at right  →",
        "See Standard \n Deduction Calculation\n at right  →",
        "Line 12a - Standard Deduction for Dependents",
        "Standard deduction plus net qualified disaster losses\n"
        "on Sch. A, Line 16.",
        "Deduction is $0 due to spouse itemizing or dual-status alien.",
    )

    def test_refuses_when_the_diagnostic_carries_the_birthdate_message(self):
        """(a) The refusal FIRES, and its message names CAUSE and REMEDY."""
        message = workbook_refusal({
            "deduction_diagnostic": "Birthdate(s) needed.",
            "total_tax": None,
        })
        self.assertIsNotNone(
            message,
            "`Deduction` = 'Birthdate(s) needed.' is the workbook declining "
            "to compute the return; it must not be passed over.",
        )
        # The diagnostic itself, VERBATIM -- a reader must be able to grep the
        # sheet for the exact string the sheet wrote.
        self.assertIn("Birthdate(s) needed.", message)

        low = message.lower()
        # CAUSE: tenforty supplies no spouse birthdate, for MFJ/MFS.
        self.assertIn("spouse birthdate", low)
        self.assertIn("married_jointly", low)
        self.assertIn("married_separate", low)
        # REMEDY: the spouse-birthdate unit lifts this.
        self.assertIn("spouse-birthdate unit", low)
        # The refusal also protects line 17, which the SAME blank corrupts
        # into a wrong NONZERO value via Form 6251 on AMT-bearing returns.
        self.assertIn("line 17", low)
        self.assertIn("6251", low)
        # And it must say what it is refusing to do, in the sheet's terms.
        self.assertIn("tax_subtotal", low)

    def test_does_not_refuse_on_a_clean_harvest(self):
        """(b) INJECTION PROOF. A guard that always fires is indistinguishable
        from a broken pipeline, so this matters exactly as much as (a).

        Three shapes of "clean": the key absent entirely (any caller that does
        not harvest it, and every year before this key existed), the key
        present but empty, and the key present carrying each real deduction
        LABEL the sheet writes on a return it did compute. If any of these
        refuses, every return refuses and the guard proves nothing.
        """
        self.assertIsNone(workbook_refusal({}))
        self.assertIsNone(workbook_refusal({"deduction_diagnostic": None}))
        self.assertIsNone(workbook_refusal({"deduction_diagnostic": ""}))
        self.assertIsNone(workbook_refusal({"deduction_diagnostic": "   "}))
        for label in self.LABELS:
            with self.subTest(label=label):
                self.assertIsNone(
                    workbook_refusal({"deduction_diagnostic": label}),
                    f"{label!r} is a deduction-source CAPTION on a return the "
                    f"workbook computed normally, not a refusal.",
                )

    def test_refuses_on_every_known_diagnostic_branch(self):
        """Not just the birthdate one. All five diagnostic branches refuse.

        "Manual Override" is unreachable today -- tenforty never writes the
        override cells -- but it is NOT special-cased, on purpose: the moment
        we start deciding which of the sheet's own statements deserve a
        hearing we are back to the defect this guard exists to remove.
        """
        for diagnostic in self.DIAGNOSTICS:
            with self.subTest(diagnostic=diagnostic):
                message = workbook_refusal(
                    {"deduction_diagnostic": diagnostic})
                self.assertIsNotNone(message)
                self.assertIn(diagnostic, message)

    def test_refuses_a_diagnostic_that_merely_starts_with_a_label(self):
        """The allowlist is matched by EQUALITY, not by short prefix.

        A short prefix is a hole in a fail-closed allowlist. If "schedule a"
        or "standard deduction" were prefix-matched, a future vendor
        diagnostic opening with those words would be waved through as an
        ordinary caption -- re-opening this defect on a narrower surface,
        which is the very species this unit exists to remove.

        The two "See Standard ..." labels are the deliberate exceptions,
        because they alone carry a trailing "  →" whose encoding across the
        recalc round-trip is not verifiable without launching soffice. Their
        prefixes stop before the arrow and are long enough to be specific.
        The last case pins that the exception stays NARROW: a string that
        opens with "See Standard" but then says something else still refuses.
        """
        for extended in (
            "Schedule A required — attach Form 8283.",
            "Standard Deduction unavailable; see instructions.",
            "Standard deduction plus something the vendor added later.",
            "Line 12a - Standard Deduction for Dependents cannot be computed.",
            "See Standard Deduction Worksheet — spouse data missing.",
        ):
            with self.subTest(extended=extended):
                self.assertIsNotNone(
                    workbook_refusal({"deduction_diagnostic": extended}),
                    f"{extended!r} opens like a caption but is not one. "
                    f"Waving it through would be exactly the guess this "
                    f"guard exists to refuse.",
                )

    def test_refuses_on_an_unrecognised_diagnostic(self):
        """(c) FAIL CLOSED. An unrecognised string is precisely when guessing
        is worst -- it means the vendor changed something we have not read."""
        for unknown in (
            "Spousal identification number required.",
            "#VALUE!",
            "=IF(AX78<>\"\",\"Manual Override\",",
            0,
        ):
            with self.subTest(unknown=unknown):
                message = workbook_refusal(
                    {"deduction_diagnostic": unknown})
                self.assertIsNotNone(
                    message,
                    f"{unknown!r} is neither a known deduction label nor a "
                    f"known diagnostic. Passing it would be a guess.",
                )
                self.assertIn(str(unknown), message)

    def test_compute_raises_rather_than_returning_a_refused_dict(self):
        """The decision is wired into `compute`, not merely available.

        The exception type matches the sibling out-of-scope refusals in this
        pipeline (`orchestrator`'s QBI above-threshold guard, `sch_a`,
        `sch_d`), and the cause genuinely IS an unimplemented input.
        """
        with self.assertRaises(NotImplementedError) as ctx:
            compute(
                raw_1040={
                    "deduction_diagnostic": "Birthdate(s) needed.",
                    "total_tax": None,
                    "standard_deduction": 31500,
                },
                upstream={},
            )
        self.assertIn("Birthdate(s) needed.", str(ctx.exception))

    def test_compute_passes_a_clean_harvest_through_and_drops_the_key(self):
        """The companion half: `compute` still computes on a clean harvest.

        Without this, a `compute` that raised unconditionally would satisfy
        the test above. The diagnostic key is CONSUMED here rather than
        forwarded -- it is a harvest-time control value, not a result, and
        letting the only legitimately-string OUTPUT travel into the results
        dict would put a caption where downstream consumers expect money.
        """
        result = compute(
            raw_1040={
                "deduction_diagnostic": "Standard Deduction",
                "total_tax": 4_321.0,
            },
            upstream={},
        )
        self.assertEqual(result["total_tax"], 4_321.0)
        self.assertNotIn("deduction_diagnostic", result)
