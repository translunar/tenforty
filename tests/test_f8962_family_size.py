"""Form 8962 tax-family size and per-status repayment caps (ptc-family lane,
rulings R-ptc-schema and R-hoh-ptc).

Line 1 is the tax-family size (filer, plus spouse when married filing
jointly); line 4 is the FPL for that size, read through the fail-closed
``fpl_for_family_size``; line 28 reads the filing status's repayment-cap
column through ``params.for_status``. HoH returns and returns with dependents
refuse a Form 1095-A until dependents are modeled. Expected figures come from
params or from synthetic sentinel params, never from hand-written tax values.
"""
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from tenforty import years
from tenforty.forms.f8962 import compute, ptc_family_refusal
from tenforty.models import (
    W2,
    FilingStatus,
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
)
from tenforty.orchestrator import ReturnOrchestrator, tax_family_size
from tenforty.params.f8962 import (
    FamilySizeNotSupportedError,
    fpl_for_family_size,
    load,
)
from tenforty.params.status_view import UnsupportedStatusError
from tests.fixtures.spine_battery import _battery_config, battery_for

REPO_ROOT = Path(__file__).resolve().parent.parent

# Machine-captured from the base commit (17fa027, before this lane) by running
# every single-filer ptc_* battery scenario through
# ReturnOrchestrator.compute_federal and keeping every f8962_* key. Not
# hand-written: it pins that the re-key changes no single-filer output.
SINGLE_BASE_SNAPSHOT = (
    REPO_ROOT / "tests" / "fixtures" / "f8962_single_base_snapshot.json")

_MFJ = FilingStatus.MARRIED_FILING_JOINTLY


def _config(status: FilingStatus, *, dependents=()) -> TaxReturnConfig:
    spouse = {}
    if status in (_MFJ, FilingStatus.MARRIED_FILING_SEPARATELY):
        spouse = dict(spouse_first_name="Example", spouse_last_name="Spouse",
                      spouse_ssn="000-00-0002", spouse_birthdate="1985-04-01")
    return dataclasses.replace(
        _battery_config(2025, **spouse), filing_status=status,
        dependents=list(dependents))


def _block(premium: float, slcsp: float, aptc: float) -> Form1095A:
    return Form1095A(months=tuple(
        Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc)
        for _ in range(12)))


def _orchestrator(test: unittest.TestCase) -> ReturnOrchestrator:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                              work_dir=Path(tmp.name) / "work")


def _ptc_scenario(status: FilingStatus, *, dependents=()) -> Scenario:
    build = dict(battery_for(2025))["ptc_capped_repayment"]
    base = build()
    return dataclasses.replace(
        base, config=_config(status, dependents=dependents))


class F8962FamilySizeTests(unittest.TestCase):
    def test_mfj_family_size_is_two_without_dependents(self):
        self.assertEqual(tax_family_size(_config(_MFJ)), 2)
        self.assertEqual(tax_family_size(_config(FilingStatus.SINGLE)), 1)

    def test_line_1_is_the_family_size_passed(self):
        params = dataclasses.replace(
            load(2025),
            fpl_48_by_family_size={1: 10_001, 2: 20_002},
            repayment_caps={"single": ((400, 111),), _MFJ.value: ((400, 222),)})
        r = compute(_block(600.0, 550.0, 0.0), 30_000.0, 2025, params,
                    filing_status=_MFJ, family_size=2)
        self.assertEqual(r["f8962_line_1"], 2)

    def test_line_4_uses_family_size_fpl(self):
        # Real params, family size 1: line 4 is the size-1 table entry.
        params = load(2025)
        r = compute(_block(600.0, 550.0, 0.0), 30_000.0, 2025, params,
                    filing_status=FilingStatus.SINGLE, family_size=1)
        self.assertEqual(r["f8962_line_4"], fpl_for_family_size(params, 1))
        self.assertEqual(r["f8962_line_4"], params.fpl_48_by_family_size[1])
        # Sentinel params, family size 2: line 4 (and line 5's denominator)
        # read the size-2 entry, never the size-1 one.
        sentinel = dataclasses.replace(
            params, fpl_48_by_family_size={1: 10_000, 2: 20_000},
            repayment_caps={"single": ((400, 111),), _MFJ.value: ((400, 222),)})
        r2 = compute(_block(600.0, 550.0, 0.0), 50_000.0, 2025, sentinel,
                     filing_status=_MFJ, family_size=2)
        self.assertEqual(r2["f8962_line_4"], 20_000)
        self.assertEqual(r2["f8962_line_5"], 250)

    def test_repayment_cap_reads_status_column(self):
        sentinel = dataclasses.replace(
            load(2025), fpl_48_by_family_size={1: 10_000, 2: 10_000},
            repayment_caps={"single": ((400, 111),), _MFJ.value: ((400, 222),)})
        # Full APTC against a small entitlement: line 27 exceeds both caps.
        block = _block(600.0, 550.0, 550.0)
        single = compute(block, 25_000.0, 2025, sentinel,
                         filing_status=FilingStatus.SINGLE, family_size=1)
        joint = compute(block, 25_000.0, 2025, sentinel,
                        filing_status=_MFJ, family_size=2)
        self.assertGreater(single["f8962_line_27"], 222)
        self.assertEqual(single["f8962_line_28"], 111)
        self.assertEqual(joint["f8962_line_28"], 222)
        self.assertEqual(joint["f8962_line_29_repayment"], 222)

    def test_missing_status_cap_column_refuses(self):
        # Synthetic sparse params: the MFJ column is dropped explicitly, so the
        # refusal stays exercised however complete the real params are.
        real = load(2025)
        params = dataclasses.replace(
            real, fpl_48_by_family_size={1: 10_000, 2: 20_000},
            repayment_caps={k: v for k, v in real.repayment_caps.items()
                            if k != _MFJ.value})
        self.assertIn("single", params.repayment_caps)  # only MFJ is absent
        with self.assertRaises(UnsupportedStatusError) as ctx:
            compute(_block(600.0, 550.0, 550.0), 50_000.0, 2025, params,
                    filing_status=_MFJ, family_size=2)
        self.assertEqual(ctx.exception.field, "repayment_caps")

    def test_hoh_with_1095a_refuses_naming_dependents_spec(self):
        scenario = _ptc_scenario(FilingStatus.HEAD_OF_HOUSEHOLD)
        with self.assertRaisesRegex(NotImplementedError,
                                    r"(?s)head_of_household.*dependents spec"):
            _orchestrator(self).compute_federal(scenario)
        with self.assertRaisesRegex(NotImplementedError, "dependents spec"):
            tax_family_size(scenario.config)

    def test_any_status_with_dependents_and_1095a_refuses(self):
        orch = _orchestrator(self)
        for status in FilingStatus:
            with self.subTest(status=status.value):
                scenario = _ptc_scenario(status, dependents=["Example Child"])
                with self.assertRaisesRegex(
                        NotImplementedError, r"(?s)dependents.*dependents spec"):
                    orch.compute_federal(scenario)

    def test_dependents_without_1095a_do_not_trip_the_ptc_refusal(self):
        # Positive control: the refusal is about Form 8962, not dependents.
        # High wages keep the scenario on the native spine (above every EIC
        # ceiling), so it computes rather than routing to the workbook.
        scenario = dataclasses.replace(
            _ptc_scenario(FilingStatus.SINGLE, dependents=["Example Child"]),
            form_1095a=None,
            w2s=[W2(employer="Example Employer", wages=150_000.0,
                    federal_tax_withheld=20_000.0, ss_wages=150_000.0,
                    ss_tax_withheld=9_300.0, medicare_wages=150_000.0,
                    medicare_tax_withheld=2_175.0)])
        results = _orchestrator(self).compute_federal(scenario)
        self.assertNotIn("f8962_line_1", results)

    def test_refusal_is_none_when_family_is_known(self):
        self.assertIsNone(ptc_family_refusal(_config(FilingStatus.SINGLE)))
        self.assertIsNone(ptc_family_refusal(_config(_MFJ)))
        self.assertIsNotNone(ptc_family_refusal(
            _config(_MFJ, dependents=["Example Child"])))
        self.assertIsNotNone(ptc_family_refusal(
            _config(FilingStatus.HEAD_OF_HOUSEHOLD)))

    def test_single_unchanged(self):
        expected = json.loads(SINGLE_BASE_SNAPSHOT.read_text())
        orch = _orchestrator(self)
        seen = set()
        for year in years.amendable_federal_years():
            for name, build in battery_for(year):
                if not name.startswith("ptc_"):
                    continue
                key = f"{year}/{name}"
                seen.add(key)
                with self.subTest(scenario=key):
                    results = orch.compute_federal(build())
                    actual = {k: v for k, v in results.items()
                              if k.startswith("f8962_")}
                    self.assertEqual(actual, expected[key])
        # Every snapshotted scenario still exists (none silently dropped).
        self.assertEqual(seen, set(expected))


def _sparse_fpl_params():
    """Real 2025 params with the FPL table cut to sizes {1, 3} and no
    per-person amount: synthetic negative space for the fail-closed
    refusals, independent of how complete the real table is."""
    real = load(2025)
    return dataclasses.replace(
        real,
        fpl_48_by_family_size={k: v for k, v in
                               real.fpl_48_by_family_size.items()
                               if k in (1, 3)},
        fpl_48_additional_person=None)


class FplForFamilySizeTests(unittest.TestCase):
    def test_size_in_table_reads_the_table(self):
        p = dataclasses.replace(load(2025), fpl_48_by_family_size={1: 7, 2: 9})
        self.assertEqual(fpl_for_family_size(p, 1), 7)
        self.assertEqual(fpl_for_family_size(p, 2), 9)

    def test_absent_size_refuses_named_error(self):
        # Synthetic sparse params: size 2 missing inside the table, and no
        # per-person amount to extend beyond it.
        p = _sparse_fpl_params()
        for absent in (2, max(p.fpl_48_by_family_size) + 1):
            with self.subTest(family_size=absent):
                with self.assertRaises(FamilySizeNotSupportedError) as ctx:
                    fpl_for_family_size(p, absent)
                self.assertIsInstance(ctx.exception, NotImplementedError)
                self.assertEqual(ctx.exception.family_size, absent)
                self.assertEqual(ctx.exception.year, 2025)

    def test_compute_refuses_absent_size(self):
        p = _sparse_fpl_params()
        absent = max(p.fpl_48_by_family_size) + 1
        with self.assertRaises(FamilySizeNotSupportedError):
            compute(_block(600.0, 550.0, 0.0), 30_000.0, 2025, p,
                    filing_status=FilingStatus.SINGLE, family_size=absent)

    def test_additional_person_extends_beyond_the_table_only(self):
        p = dataclasses.replace(
            load(2025), fpl_48_by_family_size={1: 100, 3: 300},
            fpl_48_additional_person=50)
        self.assertEqual(fpl_for_family_size(p, 5), 300 + 2 * 50)
        # A gap INSIDE the table is never filled by the per-person amount.
        with self.assertRaises(FamilySizeNotSupportedError):
            fpl_for_family_size(p, 2)

    def test_nonpositive_size_rejected(self):
        with self.assertRaises(ValueError):
            fpl_for_family_size(load(2025), 0)
