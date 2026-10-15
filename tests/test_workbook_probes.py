"""Workbook numeric-cell probes (workbook-health-2025 step 2).

A probe is a 2025 workbook cell whose healthy value is a NUMBER (or blank)
but which can instead hold a plain-English diagnostic string that a
downstream SUM/MIN/arithmetic would silently skip — the partial-total
species. The harvest reads each probe cell; any non-empty text or error
marker refuses, naming the sheet, cell and defined name and quoting the
value. There is no string allowlist: a numeric cell's allowlist is empty.

The probe set is the numeric-path cut of the step-1 inventory (both are
gitignored docs: docs/plans/2026-10-13-briefs/workbook-health-2025-
inventory.md and -numeric-cut.md), less the three cells team-lead ruled
recorded-not-harvested ('Line 6ab (SS Bene)'!L23, '2441'!V111,
'Sch. 1, Line 20 (IRA)'!Q21). Synthetic harvested dicts only; the
registry checks read the workbook with openpyxl (no recalc, no soffice).
"""
import unittest

import openpyxl

from tenforty.forms import f1040 as form_1040
from tenforty.mappings.f1040 import F1040, WORKBOOK_PROBES_2025
from tests.helpers import REPO_ROOT

WORKBOOK_2025 = REPO_ROOT / "spreadsheets" / "federal" / "2025" / "1040.xlsx"

# The cut doc's IN list less the three recorded-not-harvested cells (73),
# less the 32 dispatch-family cells below: 41.
# Independent of the registry, so a silently deleted probe key reddens.
EXPECTED_PROBE_CELLS: frozenset[tuple[str, str]] = frozenset({
    ("1040", "AL71"),
    ("1040", "BM100"),
    ("6251", "AC27"),
    ("6251", "AC39"),
    ("6251", "M89"),
    ("6251", "M95"),
    ("6251", "M102"),
    ("6251", "M104"),
    ("6251", "M111"),
    ("8582", "AT18"),
    ("8582", "X33"),
    ("8812", "AL30"),
    ("8863", "X16"),
    ("8959", "K24"),
    ("8959", "K34"),
    ("8959", "K46"),
    ("8960", "L44"),
    ("Line 16 (QDCG Tax)", "N67"),
    ("Line 16 (QDCG Tax)", "N71"),
    ("Line 16 (QDCG Tax)", "N95"),
    ("Line 16 (QDCG Tax)", "N99"),
    ("Line 16 (QDCG Tax)", "AA106"),
    ("Line 16 (QDCG Tax)", "V111"),
    ("Line 16 (QDCG Tax)", "X131"),
    ("Line 16 (QDCG Tax)", "X142"),
    ("Line 16 (QDCG Tax)", "X160"),
    ("Line 16 (QDCG Tax)", "Y165"),
    ("Line 6ab (SS Bene)", "L29"),
    ("Line 6ab (SS Bene)", "L49"),
    ("Sch. 1, Line 21 (Stu Loan)", "J20"),
    ("Sch. 1-A", "AU30"),
    ("Sch. 1-A", "AY30"),
    ("Sch. A", "AI10"),
    ("Sch. D WS", "L91"),
    ("Sch. D WS", "L92"),
    ("Sch. D WS", "L98"),
    ("Sch. D WS", "L110"),
    ("Sch. D WS", "L111"),
    ("Sch. D WS", "R134"),
    ("Sch. D WS", "R137"),
    ("Sch. SE", "X20"),
})

# Dispatch-family cells removed from the probe set (team-lead ruling after
# the step-3 probe-value dump): the 29 cells that held '---' / '#N/A' /
# '#VALUE!' on every workbook row (unused-worksheet operands and the
# unchosen table/schedule side) plus three table-side dispatch cells of the
# same structure. A MEMBERSHIP correction, not a string allowlist.
REMOVED_DISPATCH_FAMILY: frozenset[tuple[str, str]] = frozenset({
    ("1040", "BI100"),
    ("1040", "BI99"),
    ("Line 16 (QDCG Tax)", "AA98"),
    ("Line 16 (QDCG Tax)", "U164"),
    ("Line 16 (QDCG Tax)", "U165"),
    ("Line 16 (QDCG Tax)", "U171"),
    ("Line 16 (QDCG Tax)", "U172"),
    ("Line 16 (QDCG Tax)", "U59"),
    ("Line 16 (QDCG Tax)", "U60"),
    ("Line 16 (QDCG Tax)", "U66"),
    ("Line 16 (QDCG Tax)", "U67"),
    ("Line 16 (QDCG Tax)", "U80"),
    ("Line 16 (QDCG Tax)", "U81"),
    ("Line 16 (QDCG Tax)", "U86"),
    ("Line 16 (QDCG Tax)", "U87"),
    ("Line 16 (QDCG Tax)", "V113"),
    ("Line 16 (QDCG Tax)", "W105"),
    ("Line 16 (QDCG Tax)", "W106"),
    ("Line 16 (QDCG Tax)", "W97"),
    ("Line 16 (QDCG Tax)", "W98"),
    ("Line 16 (QDCG Tax)", "X167"),
    ("Line 16 (QDCG Tax)", "Y172"),
    ("Line 16 (QDCG Tax)", "Y60"),
    ("Line 16 (QDCG Tax)", "Y67"),
    ("Line 16 (QDCG Tax)", "Y81"),
    ("Line 16 (QDCG Tax)", "Y87"),
    ("Sch. D WS", "AD134"),
    ("Sch. D WS", "AD135"),
    ("Sch. D WS", "AD143"),
    ("Sch. D WS", "AD144"),
    ("Sch. D WS", "AH135"),
    ("Sch. D WS", "AH144"),
})

# Cells ruled recorded-not-harvested: normal-operation strings consumed only
# behind a textual guard (team-lead adjudication, workbook-health-2025).
NOT_PROBED: frozenset[tuple[str, str]] = frozenset({
    ("Line 6ab (SS Bene)", "L23"),
    ("2441", "V111"),
    ("Sch. 1, Line 20 (IRA)", "Q21"),
})

AL71 = "workbook_probe__1040__al71"   # '1040'!AL71 [SocSecBenefits_Taxable]
K34 = "workbook_probe__8959__k34"   # '8959'!K34, no defined name
AU30 = "workbook_probe__sch_1_a__au30"


class ProbeRegistryTests(unittest.TestCase):
    """The probe key set is exactly the adjudicated cut, and every key is
    wired so the engine reads its cell."""

    def test_probe_cells_match_the_cut(self):
        cells = {(p.sheet, p.cell) for p in WORKBOOK_PROBES_2025.values()}
        self.assertEqual(len(EXPECTED_PROBE_CELLS), 41)
        self.assertEqual(len(WORKBOOK_PROBES_2025), 41)
        self.assertEqual(cells, set(EXPECTED_PROBE_CELLS))
        self.assertEqual(cells & set(NOT_PROBED), set())
        self.assertEqual(len(REMOVED_DISPATCH_FAMILY), 32)
        self.assertEqual(cells & set(REMOVED_DISPATCH_FAMILY), set())

    def test_every_probe_is_a_2025_output_routed_to_its_sheet(self):
        outputs = F1040.OUTPUTS[2025]
        sheet_map = F1040.SHEET_MAP[2025]
        for key, probe in WORKBOOK_PROBES_2025.items():
            with self.subTest(key=key):
                self.assertTrue(key.startswith(form_1040.WORKBOOK_PROBE_PREFIX))
                self.assertEqual(outputs[key], probe.cell)
                self.assertEqual(sheet_map[key], probe.sheet)

    def test_probes_are_2025_only(self):
        for year in (2021, 2022, 2023, 2024):
            with self.subTest(year=year):
                self.assertEqual(
                    [k for k in F1040.OUTPUTS[year]
                     if k.startswith(form_1040.WORKBOOK_PROBE_PREFIX)], [])

    def test_each_probe_cell_is_a_formula_and_names_match_the_workbook(self):
        # A probe pointed at a blank or constant cell would read None and
        # pass forever; the recorded defined name must be the workbook's.
        wb = openpyxl.load_workbook(WORKBOOK_2025)
        names_at: dict[tuple[str, str], set[str]] = {}
        for name, defn in wb.defined_names.items():
            for sheet, ref in defn.destinations:
                names_at.setdefault((sheet, ref.replace("$", "")),
                                    set()).add(name)
        for key, probe in WORKBOOK_PROBES_2025.items():
            with self.subTest(key=key):
                value = wb[probe.sheet][probe.cell].value
                self.assertIsInstance(value, str)
                self.assertTrue(value.startswith("="), value)
                recorded = {n for n in probe.defined_name.split(" / ") if n}
                self.assertEqual(
                    recorded, names_at.get((probe.sheet, probe.cell), set()))


class ProbeRefusalTests(unittest.TestCase):
    """workbook_probe_refusal over synthetic harvested dicts."""

    def test_numbers_pass(self):
        for value in (0, 1, -250, 1234.5, 0.0):
            with self.subTest(value=value):
                self.assertIsNone(form_1040.workbook_probe_refusal(
                    {AL71: value, K34: value}))

    def test_blank_and_empty_string_pass(self):
        for value in (None, "", "   ", "\n"):
            with self.subTest(value=value):
                self.assertIsNone(form_1040.workbook_probe_refusal(
                    {AL71: value}))

    def test_absent_keys_pass(self):
        self.assertIsNone(form_1040.workbook_probe_refusal({}))

    def test_string_refuses_naming_sheet_cell_name_and_value(self):
        message = form_1040.workbook_probe_refusal(
            {AL71: "See 'Line 6ab' sheet."})
        self.assertIsNotNone(message)
        for part in ("'1040'!AL71", "SocSecBenefits_Taxable",
                     "\"See 'Line 6ab' sheet.\""):
            self.assertIn(part, message)

    def test_unnamed_cell_refusal_names_sheet_and_cell(self):
        message = form_1040.workbook_probe_refusal({K34: "Filing status?"})
        self.assertIsNotNone(message)
        self.assertIn("'8959'!K34", message)
        self.assertIn("'Filing status?'", message)

    def test_error_markers_refuse(self):
        for marker in ("#VALUE!", "#NAME?", "#REF!", "#DIV/0!", "#N/A"):
            with self.subTest(marker=marker):
                message = form_1040.workbook_probe_refusal({K34: marker})
                self.assertIsNotNone(message)
                self.assertIn(marker, message)

    def test_dispatch_family_strings_are_not_allowlisted(self):
        # The 32-cell removal is a MEMBERSHIP correction: '---' and '#N/A'
        # still refuse in every probe that remains.
        for value in ("---", "#N/A", "#VALUE!"):
            for key in WORKBOOK_PROBES_2025:
                with self.subTest(value=value, key=key):
                    self.assertIsNotNone(
                        form_1040.workbook_probe_refusal({key: value}))

    def test_booleans_refuse(self):
        # A numeric cell holding TRUE/FALSE is not a number either.
        self.assertIsNotNone(form_1040.workbook_probe_refusal({K34: True}))

    def test_sch_1a_caption_refuses(self):
        # Vendor bug: 'Sch. 1-A'!AU30 reads the 'W-2s'!F$39 caption where its
        # siblings read the row-46 tips amount; the caption is exactly the
        # corrupting value, so it must refuse.
        message = form_1040.workbook_probe_refusal(
            {AU30: "Spouse's \nEmployer #4"})
        self.assertIsNotNone(message)
        self.assertIn("'Sch. 1-A'!AU30", message)

    def test_every_registered_probe_refuses_text(self):
        for key in WORKBOOK_PROBES_2025:
            with self.subTest(key=key):
                self.assertIsNotNone(form_1040.workbook_probe_refusal(
                    {key: "Filing status?"}))


class ProbeComputeTests(unittest.TestCase):
    """forms.f1040.compute listens to the probes and consumes them."""

    def _raw(self, **probes):
        return {"wages": 1000, "deduction_diagnostic": "Standard Deduction",
                **probes}

    def test_text_in_a_probe_refuses_compute(self):
        with self.assertRaises(NotImplementedError) as ctx:
            form_1040.compute(self._raw(**{K34: "Filing status?"}), {})
        self.assertIn("'8959'!K34", str(ctx.exception))

    def test_probe_keys_are_consumed_not_forwarded(self):
        result = form_1040.compute(
            self._raw(**{K34: 0, AL71: "", AU30: None}), {})
        self.assertEqual(
            [k for k in result
             if k.startswith(form_1040.WORKBOOK_PROBE_PREFIX)], [])
        self.assertEqual(result["wages"], 1000)
