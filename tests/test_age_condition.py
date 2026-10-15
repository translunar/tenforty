"""Aged standard deduction on the native 1040 spine (age-65-spine).

Age condition: a person born strictly before the year's
``FederalParams.aged_born_before`` is counted (one Form 1040 "born before"
box). The taxpayer is always eligible; the spouse is counted on a joint
return only. The standard deduction is the status column plus boxes x the
per-box ``additional_standard_deduction`` column, and every reader of the
standard deduction goes through ``f1040_spine.standard_deduction_for``.

Every expected dollar figure and every birthdate is derived from the year's
loaded params; tests of the pending (None) behaviour run on synthetic params
only. Synthetic data only.
"""
import ast
import dataclasses
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.forms import f1040_spine
from tenforty.models import (
    FilingStatus, Form1099INT, ItemizedDeductions, ScheduleCBusiness,
)
from tenforty import orchestrator as orchestrator_mod
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params import federal as federal_params
from tests.fixtures.spine_battery import battery_for
from tests.helpers import REPO_ROOT, make_simple_scenario

DAY = datetime.timedelta(days=1)
ALL_YEARS = years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS

SINGLE = FilingStatus.SINGLE
MFJ = FilingStatus.MARRIED_FILING_JOINTLY
MFS = FilingStatus.MARRIED_FILING_SEPARATELY
HOH = FilingStatus.HEAD_OF_HOUSEHOLD
QW = FilingStatus.QUALIFYING_WIDOW

# Far from every year's cutoff: never meets the age condition.
YOUNG = "1990-06-15"


def _aged(year: int) -> str:
    """Born the day before the year's cutoff: meets the age condition."""
    return (federal_params.load(year).aged_born_before - DAY).isoformat()


def _not_aged(year: int) -> str:
    """Born on the year's cutoff: does not (strictly-before test)."""
    return federal_params.load(year).aged_born_before.isoformat()


def _config(year: int, status: FilingStatus = SINGLE, *, birthdate: str,
            spouse_birthdate: str = ""):
    return dataclasses.replace(
        make_simple_scenario().config, year=year, filing_status=status.value,
        birthdate=birthdate, spouse_birthdate=spouse_birthdate)


def _scenario(year: int, status: FilingStatus = SINGLE, *, birthdate: str,
              spouse_birthdate: str = ""):
    scenario = make_simple_scenario()
    scenario.config = _config(year, status, birthdate=birthdate,
                              spouse_birthdate=spouse_birthdate)
    return scenario


def _orchestrator(test: unittest.TestCase) -> ReturnOrchestrator:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return ReturnOrchestrator(
        spreadsheets_dir=REPO_ROOT / "spreadsheets",
        work_dir=Path(tmp.name) / "work")


def _patched_load(year: int, **replacements):
    """A ``federal_params.load`` stand-in returning synthetic params for
    ``year`` (fields replaced) and the real params for every other year."""
    real = federal_params.load
    synthetic = dataclasses.replace(real(year), **replacements)

    def load(y: int):
        return synthetic if y == year else real(y)
    return load


class AgeConditionBoundaryTests(unittest.TestCase):
    """``age_boxes``: strict born-before on each year's own cutoff."""

    def test_day_before_counts_cutoff_day_does_not_every_year(self):
        for year in ALL_YEARS:
            params = federal_params.load(year)
            with self.subTest(year=year):
                self.assertEqual(f1040_spine.age_boxes(
                    _config(year, birthdate=_aged(year)), params), 1)
                self.assertEqual(f1040_spine.age_boxes(
                    _config(year, birthdate=_not_aged(year)), params), 0)

    def test_taxpayer_and_spouse_count_independently_on_mfj(self):
        for year in ALL_YEARS:
            params = federal_params.load(year)
            aged, not_aged = _aged(year), _not_aged(year)
            for tp, sp, expect in ((aged, aged, 2), (aged, not_aged, 1),
                                   (not_aged, aged, 1),
                                   (not_aged, not_aged, 0)):
                with self.subTest(year=year, taxpayer=tp, spouse=sp):
                    self.assertEqual(f1040_spine.age_boxes(
                        _config(year, MFJ, birthdate=tp,
                                spouse_birthdate=sp), params), expect)

    def test_spouse_counted_on_mfj_only(self):
        # Non-joint configs carrying an aged spouse birthdate (built around
        # the loader) count the taxpayer alone.
        for year in ALL_YEARS:
            params = federal_params.load(year)
            for status in (SINGLE, HOH, MFS, QW):
                with self.subTest(year=year, status=status.value):
                    self.assertEqual(f1040_spine.age_boxes(
                        _config(year, status, birthdate=_not_aged(year),
                                spouse_birthdate=_aged(year)), params), 0)
                    self.assertEqual(f1040_spine.age_boxes(
                        _config(year, status, birthdate=_aged(year),
                                spouse_birthdate=_aged(year)), params), 1)

    def test_mfj_blank_spouse_birthdate_refuses_naming_the_field(self):
        params = federal_params.load(ALL_YEARS[0])
        with self.assertRaises(ValueError) as ctx:
            f1040_spine.age_boxes(
                _config(ALL_YEARS[0], MFJ, birthdate=YOUNG), params)
        self.assertIn("spouse_birthdate", str(ctx.exception))


class AgedStandardDeductionTests(unittest.TestCase):
    """``standard_deduction_for`` = status column + boxes x per-box column,
    every attested year and status."""

    def test_status_column_plus_boxes_times_per_box(self):
        for year in ALL_YEARS:
            params = federal_params.load(year)
            aged, young = _aged(year), YOUNG
            for status in FilingStatus:
                view = params.for_status(status)
                base = view.standard_deduction
                per_box = view.additional_standard_deduction
                cases = [(young, young, 0), (aged, young, 1)]
                if status is MFJ:
                    cases += [(young, aged, 1), (aged, aged, 2)]
                for tp, sp, boxes in cases:
                    with self.subTest(year=year, status=status.value,
                                      boxes=boxes):
                        # Precondition: the "differs from base" assertion
                        # below is reachable.
                        self.assertGreater(per_box, 0)
                        got = f1040_spine.standard_deduction_for(
                            _config(year, status, birthdate=tp,
                                    spouse_birthdate=sp), params)
                        self.assertEqual(got, base + boxes * per_box)
                        if boxes:
                            self.assertNotEqual(got, base)

    def test_native_spine_line_12_carries_the_aged_amount(self):
        # End to end through compute_federal on a computing year: the aged
        # single filer's applied standard deduction is the aged amount.
        orch = _orchestrator(self)
        for year in ALL_YEARS:
            if year in _SENIOR_REFUSAL_YEARS:
                continue
            params = federal_params.load(year)
            scenario = _scenario(year, birthdate=_aged(year))
            with self.subTest(year=year):
                self.assertTrue(orch._scenario_in_spine_scope(scenario))
                results = orch.compute_federal(scenario)
                self.assertEqual(
                    results["standard_deduction"],
                    f1040_spine.standard_deduction_for(
                        scenario.config, params))
                self.assertNotEqual(
                    results["standard_deduction"],
                    params.for_status(SINGLE).standard_deduction)


# Years whose aged returns are refused (ruling R-senior-1a: Schedule 1-A).
_SENIOR_REFUSAL_YEARS = tuple(y for y in ALL_YEARS if y >= 2025)


def _attribute_reads(path: Path, attr: str) -> list[tuple[str, int, str]]:
    """(file name, line, enclosing function name or '<module>') for every
    ``.<attr>`` attribute load in ``path``."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[tuple[str, int, str]] = []

    def visit(node: ast.AST, func: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = node.name
        if (isinstance(node, ast.Attribute) and node.attr == attr
                and isinstance(node.ctx, ast.Load)):
            found.append((path.name, node.lineno, func))
        for child in ast.iter_child_nodes(node):
            visit(child, func)
    visit(tree, "<module>")
    return found


_TENFORTY = REPO_ROOT / "tenforty"
_SCANNED = sorted((_TENFORTY / "forms").glob("*.py")) + [
    _TENFORTY / "orchestrator.py"]

# (file, enclosing function) allowed to read `.standard_deduction`.
_ALLOWED_READERS = {
    ("f1040_spine.py", "standard_deduction_for"),
    # California params (ca_params.load(...)), not federal: the CA 540
    # standard deduction has no aged addition.
    ("f540.py", "compute_standard_deduction"),
}


class StandardDeductionChokepointTests(unittest.TestCase):
    """Every federal standard-deduction read goes through
    ``standard_deduction_for`` (Review Focus 7)."""

    def test_only_the_chokepoint_reads_the_status_column(self):
        reads = [r for p in _SCANNED
                 for r in _attribute_reads(p, "standard_deduction")]
        # Non-vacuous: the chokepoint's own read is found by this scan.
        self.assertIn(("f1040_spine.py", "standard_deduction_for"),
                      {(f, fn) for f, _, fn in reads})
        offenders = [r for r in reads if (r[0], r[2]) not in _ALLOWED_READERS]
        self.assertEqual(offenders, [])

    def _emits_sch_a(self, year: int, birthdate: str, itemized: int) -> bool:
        scenario = _scenario(year, birthdate=birthdate)
        scenario.itemized_deductions = ItemizedDeductions(
            mortgage_interest=itemized)
        agi = sum(w.wages for w in scenario.w2s)
        return _orchestrator(self)._should_emit_sch_a(
            scenario, {"f1040": {"agi": agi, "magi": agi}})

    def test_aged_itemizer_between_base_and_aged_gets_no_schedule_a(self):
        for year in ALL_YEARS:
            view = federal_params.load(year).for_status(SINGLE)
            # Strictly above base, strictly below base + one box.
            itemized = view.standard_deduction + view.additional_standard_deduction // 2
            with self.subTest(year=year):
                # Positive control: the same itemizer, not aged, itemizes.
                self.assertTrue(self._emits_sch_a(year, YOUNG, itemized))
                self.assertFalse(
                    self._emits_sch_a(year, _aged(year), itemized))


class SeniorDeductionRefusalTests(unittest.TestCase):
    """Ruling R-senior-1a: TY2025 aged returns refuse naming Schedule 1-A
    (the 2025 seniors deduction, unmodeled), before the native/workbook
    split; non-aged 2025 returns compute."""

    def test_refusal_years_are_nonempty(self):
        self.assertIn(2025, _SENIOR_REFUSAL_YEARS)

    def test_aged_native_scenario_refuses_naming_schedule_1a(self):
        orch = _orchestrator(self)
        for year in _SENIOR_REFUSAL_YEARS:
            scenario = _scenario(year, birthdate=_aged(year))
            with self.subTest(year=year):
                self.assertTrue(orch._scenario_in_spine_scope(scenario))
                with self.assertRaisesRegex(NotImplementedError,
                                            "Schedule 1-A"):
                    orch.compute_federal(scenario)

    def test_spouse_only_aged_refuses_before_the_workbook_runs(self):
        orch = _orchestrator(self)
        for year in _SENIOR_REFUSAL_YEARS:
            scenario = _scenario(year, MFJ, birthdate=YOUNG,
                                 spouse_birthdate=_aged(year))
            with self.subTest(year=year):
                with mock.patch.object(
                        ReturnOrchestrator, "_compute_1040_via_workbook",
                        side_effect=AssertionError("workbook ran")), \
                        mock.patch.object(
                            ReturnOrchestrator, "_compute_native_schedules",
                            side_effect=AssertionError("spine ran")):
                    with self.assertRaisesRegex(NotImplementedError,
                                                "Schedule 1-A"):
                        orch.compute_federal(scenario)

    def test_battery_refusal_rows_refuse_naming_schedule_1a(self):
        # The three aged battery rows (single in battery_for(year), MFJ/HoH
        # in the status batteries). Neither the workbook nor the native
        # schedules may run: the refusal sits before the native/workbook
        # split.
        orch = _orchestrator(self)
        for year in _SENIOR_REFUSAL_YEARS:
            rows = [(name, build) for status in (SINGLE, MFJ, HOH)
                    for name, build in battery_for(year, status)
                    if name.split("__", 1)[0].startswith("std_deduction_")]
            self.assertEqual(sorted(n for n, _ in rows), [
                "std_deduction_aged_refused__hoh",
                "std_deduction_aged_refused__single",
                "std_deduction_both_aged_refused__mfj"])
            for name, build in rows:
                with self.subTest(year=year, row=name), mock.patch.object(
                        ReturnOrchestrator, "_compute_1040_via_workbook",
                        side_effect=AssertionError("workbook ran")), \
                        mock.patch.object(
                            ReturnOrchestrator, "_compute_native_schedules",
                            side_effect=AssertionError("spine ran")):
                    with self.assertRaisesRegex(NotImplementedError,
                                                "Schedule 1-A"):
                        orch.compute_federal(build())

    def test_non_aged_scenario_computes(self):
        orch = _orchestrator(self)
        for year in _SENIOR_REFUSAL_YEARS:
            scenario = _scenario(year, birthdate=_not_aged(year))
            with self.subTest(year=year):
                results = orch.compute_federal(scenario)
                self.assertEqual(
                    results["standard_deduction"],
                    federal_params.load(year).for_status(
                        SINGLE).standard_deduction)


def _retiree(year: int, interest: float, *, birthdate: str):
    """Single filer with NO W-2 (interest income only): routes native via
    the routing gate's no-earned-income short-circuit, whatever the AGI."""
    scenario = _scenario(year, birthdate=birthdate)
    scenario.w2s = []
    scenario.form1099_int = [
        Form1099INT(payer="Synthetic Bank", interest=float(interest))]
    return scenario


# Years an aged return computes (Schedule R is then the live guard).
_COMPUTING_YEARS = tuple(y for y in ALL_YEARS
                         if y not in _SENIOR_REFUSAL_YEARS)


class SchedRRefusalTests(unittest.TestCase):
    """Ledger row R-sched-r (amended 2026-10-14): on the native spine an
    aged filer at or under the Schedule R AGI limit for their status and
    box count refuses naming Schedule R; above it, computes."""

    LIMITS = orchestrator_mod._SCHEDULE_R_AGI_LIMITS

    def test_zero_wage_retiree_routes_native_and_refuses_at_the_limit(self):
        # The case the guard exists for: no W-2, so the EIC gate never
        # keeps this filer off the spine.
        orch = _orchestrator(self)
        limit = self.LIMITS[(SINGLE.value, 1)]
        for year in _COMPUTING_YEARS:
            scenario = _retiree(year, limit, birthdate=_aged(year))
            with self.subTest(year=year):
                self.assertTrue(orch._scenario_in_spine_scope(scenario))
                with self.assertRaisesRegex(NotImplementedError,
                                            "Schedule R"):
                    orch.compute_federal(scenario)

    def test_zero_wage_retiree_above_the_limit_computes(self):
        orch = _orchestrator(self)
        limit = self.LIMITS[(SINGLE.value, 1)]
        for year in _COMPUTING_YEARS:
            scenario = _retiree(year, limit + 1, birthdate=_aged(year))
            with self.subTest(year=year):
                results = orch.compute_federal(scenario)
                self.assertEqual(results["agi"], limit + 1)

    def test_not_aged_retiree_under_the_limit_computes(self):
        orch = _orchestrator(self)
        limit = self.LIMITS[(SINGLE.value, 1)]
        for year in _COMPUTING_YEARS:
            scenario = _retiree(year, limit, birthdate=_not_aged(year))
            with self.subTest(year=year):
                self.assertEqual(orch.compute_federal(scenario)["agi"], limit)

    def test_guard_keys_on_exact_agi_not_an_overestimate(self):
        # Schedule C profit above the limit, but the half-SE-tax adjustment
        # brings true AGI under it: the refusal must still fire.
        orch = _orchestrator(self)
        limit = self.LIMITS[(SINGLE.value, 1)]
        for year in _COMPUTING_YEARS:
            scenario = _retiree(year, 0, birthdate=_aged(year))
            scenario.form1099_int = []
            scenario.schedule_c_businesses = [ScheduleCBusiness(
                description="Synthetic consulting",
                gross_receipts=float(limit + 100))]
            with self.subTest(year=year):
                self.assertTrue(orch._scenario_in_spine_scope(scenario))
                with self.assertRaisesRegex(NotImplementedError,
                                            "Schedule R"):
                    orch.compute_federal(scenario)

    def test_limits_pin_the_verified_table(self):
        # Independent pin of the guard constants (Schedule R instructions
        # Table 1, team-lead-verified 2026-10-14; ledger row R-sched-r), so
        # a changed or dropped limit reddens rather than moving both sides.
        self.assertEqual(self.LIMITS, {
            (SINGLE.value, 1): 17_500,
            (HOH.value, 1): 17_500,
            (QW.value, 1): 17_500,
            (MFJ.value, 1): 20_000,
            (MFJ.value, 2): 25_000,
        })

    def test_every_status_and_box_count_at_its_boundary(self):
        # The guard itself, per status and box count (MFJ/HoH/QSS are not
        # declared native in a computing year today, so they are driven
        # through the guard directly with an exact AGI).
        year = _COMPUTING_YEARS[-1]
        params = federal_params.load(year)
        aged, young = _aged(year), YOUNG
        cases = {
            (SINGLE.value, 1): _config(year, SINGLE, birthdate=aged),
            (HOH.value, 1): _config(year, HOH, birthdate=aged),
            (QW.value, 1): _config(year, QW, birthdate=aged),
            (MFJ.value, 1): _config(year, MFJ, birthdate=young,
                                    spouse_birthdate=aged),
            (MFJ.value, 2): _config(year, MFJ, birthdate=aged,
                                    spouse_birthdate=aged),
        }
        self.assertEqual(set(cases), set(self.LIMITS))
        guard = ReturnOrchestrator._refuse_possible_schedule_r
        for key, config in cases.items():
            scenario = make_simple_scenario()
            scenario.config = config
            limit = self.LIMITS[key]
            with self.subTest(case=key):
                with self.assertRaisesRegex(NotImplementedError,
                                            "Schedule R"):
                    guard(scenario, params, limit)
                guard(scenario, params, limit + 1)  # computes: no raise

    def test_mfj_one_box_uses_the_one_box_limit(self):
        # A spouse-only-aged couple between the one-box and both-box limits
        # computes; with both aged, the same AGI refuses.
        year = _COMPUTING_YEARS[-1]
        params = federal_params.load(year)
        agi = self.LIMITS[(MFJ.value, 1)] + 1
        self.assertLess(agi, self.LIMITS[(MFJ.value, 2)])
        guard = ReturnOrchestrator._refuse_possible_schedule_r
        one, both = make_simple_scenario(), make_simple_scenario()
        one.config = _config(year, MFJ, birthdate=YOUNG,
                             spouse_birthdate=_aged(year))
        both.config = _config(year, MFJ, birthdate=_aged(year),
                              spouse_birthdate=_aged(year))
        guard(one, params, agi)
        with self.assertRaisesRegex(NotImplementedError, "Schedule R"):
            guard(both, params, agi)

    def test_untabled_status_refuses_an_aged_filer(self):
        year = _COMPUTING_YEARS[-1]
        scenario = make_simple_scenario()
        scenario.config = _config(year, MFS, birthdate=_aged(year))
        with self.assertRaisesRegex(NotImplementedError, "Schedule R"):
            ReturnOrchestrator._refuse_possible_schedule_r(
                scenario, federal_params.load(year), 10**9)

    def test_non_aged_filer_never_refuses(self):
        year = _COMPUTING_YEARS[-1]
        scenario = make_simple_scenario()
        for status in FilingStatus:
            scenario.config = _config(year, status, birthdate=YOUNG,
                                      spouse_birthdate=YOUNG)
            with self.subTest(status=status.value):
                ReturnOrchestrator._refuse_possible_schedule_r(
                    scenario, federal_params.load(year), 0)


class AgedBatteryRowTests(unittest.TestCase):
    """The battery's aged rows: computing years carry the aged deduction on
    the native spine; refusal years' rows refuse naming Schedule 1-A."""

    def test_single_aged_row_computes_the_aged_deduction(self):
        orch = _orchestrator(self)
        for year in _COMPUTING_YEARS:
            params = federal_params.load(year)
            scenario = dict(battery_for(year))["std_deduction_aged__single"]()
            with self.subTest(year=year):
                self.assertEqual(
                    scenario.config.birthdate,
                    (params.aged_born_before - DAY).isoformat())
                self.assertTrue(orch._scenario_in_spine_scope(scenario))
                results = orch.compute_federal(scenario)
                view = params.for_status(SINGLE)
                self.assertEqual(
                    results["standard_deduction"],
                    view.standard_deduction
                    + view.additional_standard_deduction)

    def test_single_aged_row_is_a_refusal_row_in_refusal_years(self):
        # declare-2025: the refusal-year single row lives in battery_for
        # (the parity harness expects `*_refused__*` rows to refuse).
        for year in ALL_YEARS:
            names = [n for n, _ in battery_for(year)]
            with self.subTest(year=year):
                if year in _SENIOR_REFUSAL_YEARS:
                    self.assertNotIn("std_deduction_aged__single", names)
                    self.assertIn("std_deduction_aged_refused__single", names)
                else:
                    self.assertIn("std_deduction_aged__single", names)
                    self.assertNotIn(
                        "std_deduction_aged_refused__single", names)


class NoSilentAgePathTests(unittest.TestCase):
    """A pending age input refuses by name; it never yields the base
    deduction. Synthetic (patched) params only."""

    def test_pending_cutoff_refuses_an_aged_scenario(self):
        orch = _orchestrator(self)
        for year in ALL_YEARS:
            scenario = _scenario(year, birthdate=_aged(year))
            with self.subTest(year=year), mock.patch.object(
                    federal_params, "load",
                    _patched_load(year, aged_born_before=None)):
                with self.assertRaisesRegex(NotImplementedError,
                                            "aged_born_before"):
                    orch.compute_federal(scenario)

    def test_pending_per_box_amount_refuses_an_aged_scenario(self):
        orch = _orchestrator(self)
        for year in ALL_YEARS:
            if year in _SENIOR_REFUSAL_YEARS:
                continue  # refused earlier, for Schedule 1-A
            scenario = _scenario(year, birthdate=_aged(year))
            with self.subTest(year=year), mock.patch.object(
                    federal_params, "load",
                    _patched_load(year,
                                  additional_standard_deduction=None)):
                with self.assertRaisesRegex(NotImplementedError,
                                            "additional_standard_deduction"):
                    orch.compute_federal(scenario)

    def test_helper_refuses_either_pending_input(self):
        year = ALL_YEARS[0]
        config = _config(year, birthdate=_aged(year))
        for field in ("aged_born_before", "additional_standard_deduction"):
            params = dataclasses.replace(federal_params.load(year),
                                         **{field: None})
            with self.subTest(field=field):
                with self.assertRaisesRegex(NotImplementedError, field):
                    f1040_spine.standard_deduction_for(config, params)
