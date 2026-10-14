"""The native-spine (year × status) support grid and its three fail-closed
gates (spec §4): the spine/orchestrator predicate, params completeness and
battery completeness.

``params_gaps`` and ``battery_gaps`` are pure, injectable gate functions so
the gates themselves are unit-tested with synthetic loaders (a declared
column a later edit deletes must surface here, never as a runtime KeyError).
"""
import dataclasses
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.forms.f1040_spine import compute_spine
from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import (
    W2,
    FilingStatus,
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
    parse_filing_status,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params import california as ca_params
from tenforty.params.california import PER_STATUS_CALIFORNIA_FIELDS
from tenforty.params import f8962 as f8962_params
from tenforty.params.f8962 import PER_STATUS_F8962_FIELDS
from tenforty.params.federal import PER_STATUS_FEDERAL_FIELDS
from tenforty.params.federal import load as load_federal
from tests.fixtures.spine_battery import (
    DECLARED_REFUSAL_CELLS,
    REQUIRED_STATUS_SCENARIO_KINDS,
    battery_for,
)
from tests.helpers import scope_out_attestation_defaults

REPO_ROOT = Path(__file__).resolve().parent.parent

# Prefix that distinguishes a California field in a gap triple from the
# federal field of the same name (both jurisdictions carry e.g.
# standard_deduction).
CALIFORNIA_GAP_PREFIX = "california."
# Same for Form 8962 per-status fields (e.g. repayment_caps).
F8962_GAP_PREFIX = "f8962."

_STATUS_VALUES = frozenset(s.value for s in FilingStatus)


def params_gaps(
    grid: Mapping[int, tuple[str, ...]],
    *,
    load_federal: Callable[[int], object],
    load_california: Callable[[int], object],
    load_f8962: Callable[[int], object],
) -> list[tuple[int, str, str]]:
    """(year, status, field) for every declared (year, status) whose column
    is missing from a per-status params field. California fields are checked
    only for years California supports, and are reported with the
    ``california.`` prefix; Form 8962 fields with the ``f8962.`` prefix."""
    ca_years = set(years.CALIFORNIA_YEARS + years.CALIFORNIA_COMPUTE_ONLY_YEARS)
    gaps: list[tuple[int, str, str]] = []
    for year in sorted(grid):
        federal = load_federal(year)
        california = load_california(year) if year in ca_years else None
        f8962 = load_f8962(year)
        for status in grid[year]:
            for name in PER_STATUS_FEDERAL_FIELDS:
                if status not in getattr(federal, name):
                    gaps.append((year, status, name))
            for name in PER_STATUS_F8962_FIELDS:
                if status not in getattr(f8962, name):
                    gaps.append((year, status, F8962_GAP_PREFIX + name))
            if california is None:
                continue
            for name in PER_STATUS_CALIFORNIA_FIELDS:
                if status not in getattr(california, name):
                    gaps.append((year, status, CALIFORNIA_GAP_PREFIX + name))
    return gaps


def battery_gaps(
    grid: Mapping[int, tuple[str, ...]],
    *,
    battery: Callable[[int, FilingStatus], list[tuple[str, object]]],
) -> list[tuple[int, str, str]]:
    """(year, status, kind) for every declared NON-single (year, status)
    missing one of the required scenario kinds (ruling R-battery-n). A
    battery entry's kind is its name prefix before ``__``. A cell listed in
    DECLARED_REFUSAL_CELLS is also covered by its refusal kind — that cell
    only (ruling R-hoh-ptc)."""
    gaps: list[tuple[int, str, str]] = []
    for year in sorted(grid):
        for status in grid[year]:
            if status == FilingStatus.SINGLE.value:
                continue
            present = {
                name.split("__", 1)[0]
                for name, _ in battery(year, FilingStatus(status))}
            gaps.extend(
                (year, status, kind)
                for kind in REQUIRED_STATUS_SCENARIO_KINDS
                if kind not in present
                and DECLARED_REFUSAL_CELLS.get((status, kind)) not in present)
    return gaps


def _status_keyed_fields(params_by_year) -> set[str]:
    """Fields whose value, in SOME year, is a non-empty dict keyed only by
    FilingStatus value strings."""
    keyed: set[str] = set()
    for params in params_by_year:
        for f in dataclasses.fields(params):
            value = getattr(params, f.name)
            if (isinstance(value, dict) and value
                    and set(value) <= _STATUS_VALUES):
                keyed.add(f.name)
    return keyed


def _high_income(year: int, status: FilingStatus) -> Scenario:
    """Synthetic wage earner far above every EIC ceiling."""
    return Scenario(
        config=TaxReturnConfig(
            year=year,
            filing_status=status,
            birthdate="1980-01-01",
            state="TX",
            first_name="Example",
            last_name="Filer",
            ssn="000-00-0001",
            **scope_out_attestation_defaults(),
        ),
        w2s=[W2(employer="Example Employer", wages=150_000.0,
                federal_tax_withheld=20_000.0, ss_wages=150_000.0,
                ss_tax_withheld=9_300.0, medicare_wages=150_000.0,
                medicare_tax_withheld=2_175.0)],
    )


def _orchestrator(test: unittest.TestCase) -> ReturnOrchestrator:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return ReturnOrchestrator(
        spreadsheets_dir=REPO_ROOT / "spreadsheets",
        work_dir=Path(tmp.name) / "work")


class GridShapeTests(unittest.TestCase):
    def test_every_federal_year_declared_and_values_are_filing_statuses(self):
        declared = set(years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS)
        self.assertEqual(set(years.NATIVE_SPINE_STATUSES), declared)
        for year, statuses in years.NATIVE_SPINE_STATUSES.items():
            with self.subTest(year=year):
                self.assertIsInstance(statuses, tuple)
                for status in statuses:
                    # Raises ValueError for anything not a FilingStatus value.
                    self.assertEqual(FilingStatus(status).value, status)
                self.assertEqual(len(statuses), len(set(statuses)))

    def test_single_declared_every_year(self):
        for year, statuses in years.NATIVE_SPINE_STATUSES.items():
            self.assertIn("single", statuses, year)

    def test_mfs_and_qw_never_declared(self):  # spec §2 Out
        for y, sts in years.NATIVE_SPINE_STATUSES.items():
            self.assertFalse(
                {"married_filing_separately", "qualifying_widow"} & set(sts), y)

    def test_native_spine_supports_reads_the_grid(self):
        self.assertTrue(years.native_spine_supports(2025, "single"))
        with mock.patch.dict(years.NATIVE_SPINE_STATUSES,
                             {2025: ("single", "head_of_household")}):
            self.assertTrue(
                years.native_spine_supports(2025, "head_of_household"))
        self.assertFalse(years.native_spine_supports(2025, "head_of_household"))

    def test_undeclared_year_is_not_supported(self):
        self.assertNotIn(1999, years.NATIVE_SPINE_STATUSES)
        self.assertFalse(years.native_spine_supports(1999, "single"))


class PerStatusFieldRegistryTests(unittest.TestCase):
    def test_registry_equals_status_keyed_dict_fields_every_year(self):
        all_years = years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS
        expected = _status_keyed_fields(load_federal(y) for y in all_years)
        self.assertEqual(set(PER_STATUS_FEDERAL_FIELDS), expected)
        self.assertEqual(len(PER_STATUS_FEDERAL_FIELDS),
                         len(set(PER_STATUS_FEDERAL_FIELDS)))

    def test_california_registry_equals_status_keyed_dict_fields_every_year(self):
        all_years = years.CALIFORNIA_YEARS + years.CALIFORNIA_COMPUTE_ONLY_YEARS
        expected = _status_keyed_fields(ca_params.load(y) for y in all_years)
        self.assertEqual(set(PER_STATUS_CALIFORNIA_FIELDS), expected)
        self.assertEqual(len(PER_STATUS_CALIFORNIA_FIELDS),
                         len(set(PER_STATUS_CALIFORNIA_FIELDS)))

    def test_f8962_registry_equals_status_keyed_dict_fields_every_year(self):
        all_years = years.amendable_federal_years()
        expected = _status_keyed_fields(f8962_params.load(y) for y in all_years)
        self.assertEqual(set(PER_STATUS_F8962_FIELDS), expected)
        self.assertEqual(len(PER_STATUS_F8962_FIELDS),
                         len(set(PER_STATUS_F8962_FIELDS)))


class ParamsCompletenessGateTests(unittest.TestCase):
    def test_declared_grid_has_every_column(self):
        self.assertEqual(
            params_gaps(years.NATIVE_SPINE_STATUSES, load_federal=load_federal,
                        load_california=ca_params.load,
                        load_f8962=f8962_params.load), [])

    def test_gate_names_a_removed_column(self):
        def fake(year):
            p = load_federal(year)
            if year != 2025:
                return p
            return dataclasses.replace(p, standard_deduction={
                k: v for k, v in p.standard_deduction.items() if k != "single"})
        gaps = params_gaps(years.NATIVE_SPINE_STATUSES, load_federal=fake,
                           load_california=ca_params.load,
                           load_f8962=f8962_params.load)
        self.assertIn((2025, "single", "standard_deduction"), gaps)

    def test_gate_names_a_removed_california_column(self):
        def fake(year):
            p = ca_params.load(year)
            if year != 2025:
                return p
            return dataclasses.replace(p, exemption_credit={
                k: v for k, v in p.exemption_credit.items() if k != "single"})
        gaps = params_gaps(years.NATIVE_SPINE_STATUSES,
                           load_federal=load_federal, load_california=fake,
                           load_f8962=f8962_params.load)
        california_gaps = [
            g for g in gaps if g[2].startswith(CALIFORNIA_GAP_PREFIX)]
        self.assertEqual(california_gaps,
                         [(2025, "single", "california.exemption_credit")])

    def test_gate_names_a_removed_f8962_column(self):
        def fake(year):
            p = f8962_params.load(year)
            if year != 2025:
                return p
            return dataclasses.replace(p, repayment_caps={
                k: v for k, v in p.repayment_caps.items() if k != "single"})
        gaps = params_gaps(years.NATIVE_SPINE_STATUSES,
                           load_federal=load_federal,
                           load_california=ca_params.load, load_f8962=fake)
        f8962_gaps = [g for g in gaps if g[2].startswith(F8962_GAP_PREFIX)]
        self.assertEqual(f8962_gaps, [(2025, "single", "f8962.repayment_caps")])

    def test_gate_names_an_undeclared_status_f8962_column(self):
        # Declaring a status whose repayment-cap column is absent surfaces in
        # the gate, not at runtime. The column is dropped synthetically so the
        # negative space exists however complete the real params are.
        def fake(year):
            p = f8962_params.load(year)
            return dataclasses.replace(p, repayment_caps={
                k: v for k, v in p.repayment_caps.items()
                if k != "married_filing_jointly"})
        gaps = params_gaps({2025: ("single", "married_filing_jointly")},
                           load_federal=load_federal,
                           load_california=ca_params.load,
                           load_f8962=fake)
        f8962_gaps = [g for g in gaps if g[2].startswith(F8962_GAP_PREFIX)]
        self.assertEqual(
            f8962_gaps,
            [(2025, "married_filing_jointly", "f8962.repayment_caps")])


class BatteryCompletenessGateTests(unittest.TestCase):
    def test_declared_grid_battery_complete(self):
        self.assertEqual(
            battery_gaps(years.NATIVE_SPINE_STATUSES, battery=battery_for), [])

    def test_gate_names_missing_kind(self):
        gaps = battery_gaps({2025: ("single", "head_of_household")},
                            battery=lambda y, s: [])
        self.assertIn((2025, "head_of_household", "wages_only"), gaps)

    def test_kind_is_the_name_prefix_before_double_underscore(self):
        names = [f"{kind}__hoh" for kind in REQUIRED_STATUS_SCENARIO_KINDS
                 if kind != "addl_medicare"]
        gaps = battery_gaps({2025: ("head_of_household",)},
                            battery=lambda y, s: [(n, None) for n in names])
        self.assertEqual(gaps, [(2025, "head_of_household", "addl_medicare")])

    def test_declared_refusal_covers_only_its_cell(self):
        # R-hoh-ptc: ptc_reconciliation_refused__<s> satisfies the
        # ptc_reconciliation cell for head_of_household and nowhere else.
        def rows(suffix):
            return [(f"{kind}__{suffix}", None)
                    for kind in REQUIRED_STATUS_SCENARIO_KINDS
                    if kind != "ptc_reconciliation"] + [
                (f"ptc_reconciliation_refused__{suffix}", None)]
        self.assertEqual(
            battery_gaps({2025: ("head_of_household",)},
                         battery=lambda y, s: rows("hoh")), [])
        self.assertEqual(
            battery_gaps({2025: ("married_filing_jointly",)},
                         battery=lambda y, s: rows("mfj")),
            [(2025, "married_filing_jointly", "ptc_reconciliation")])

    def test_non_single_rows_carry_their_status(self):
        for status, suffix in ((FilingStatus.MARRIED_FILING_JOINTLY, "mfj"),
                               (FilingStatus.HEAD_OF_HOUSEHOLD, "hoh")):
            rows = battery_for(2025, status)
            self.assertEqual(len(rows), len(REQUIRED_STATUS_SCENARIO_KINDS))
            for name, build in rows:
                with self.subTest(row=name):
                    self.assertTrue(name.endswith(f"__{suffix}"))
                    self.assertIs(
                        parse_filing_status(build().config.filing_status),
                        status)
        self.assertEqual(
            [name for name, _ in battery_for(2025, FilingStatus.SINGLE)],
            [name for name, _ in battery_for(2025)])
        self.assertTrue(battery_for(2025))

    def test_declared_refusal_row_refuses(self):
        build = dict(battery_for(2025, FilingStatus.HEAD_OF_HOUSEHOLD))[
            "ptc_reconciliation_refused__hoh"]
        orch = _orchestrator(self)
        with mock.patch.dict(years.NATIVE_SPINE_STATUSES,
                             {2025: ("single", "married_filing_jointly",
                                     "head_of_household")}):
            with self.assertRaisesRegex(
                    NotImplementedError,
                    r"^Form 8962 .*head_of_household.*family size"):
                orch.compute_federal(build())

    def test_status_rows_route_native_once_declared(self):
        # Wage levels clear the EIC gate: with 2025 MFJ/HoH declared, every
        # computing row is in spine scope; undeclared, none is.
        orch = _orchestrator(self)
        rows = [(name, build)
                for status in (FilingStatus.MARRIED_FILING_JOINTLY,
                               FilingStatus.HEAD_OF_HOUSEHOLD)
                for name, build in battery_for(2025, status)
                if name.split("__", 1)[0] not in DECLARED_REFUSAL_CELLS.values()]
        self.assertEqual(len(rows), 2 * len(REQUIRED_STATUS_SCENARIO_KINDS) - 1)
        for name, build in rows:
            with self.subTest(row=name):
                scenario = build()
                self.assertFalse(orch._scenario_in_spine_scope(scenario))
                with mock.patch.dict(
                        years.NATIVE_SPINE_STATUSES,
                        {2025: ("single", "married_filing_jointly",
                                "head_of_household")}):
                    self.assertTrue(orch._scenario_in_spine_scope(scenario))

class SpineGateTests(unittest.TestCase):
    def test_predicate_follows_grid(self):
        orch = _orchestrator(self)
        scenario = _high_income(2025, FilingStatus.HEAD_OF_HOUSEHOLD)
        with mock.patch.dict(years.NATIVE_SPINE_STATUSES,
                             {2025: ("single", "head_of_household")}):
            self.assertTrue(orch._scenario_in_spine_scope(scenario))
        self.assertFalse(orch._scenario_in_spine_scope(scenario))
        # Single stays in scope (positive control for the unpatched grid).
        self.assertTrue(orch._scenario_in_spine_scope(
            _high_income(2025, FilingStatus.SINGLE)))

    def test_spine_refuses_undeclared_status_naming_grid(self):
        # Anchored on compute_spine's OWN message: the spine calls qdcgt_tax,
        # whose grid refusal also names the grid, so an unanchored regex
        # would pass with the spine gate deleted.
        with self.assertRaisesRegex(
                NotImplementedError, r"^compute_spine: .*NATIVE_SPINE_STATUSES"):
            compute_spine(
                _high_income(2025, FilingStatus.MARRIED_FILING_JOINTLY),
                load_federal(2025), {})

    def test_qdcgt_refuses_undeclared_status(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"^QDCGT worksheet: .*NATIVE_SPINE_STATUSES"):
            qdcgt_tax(150_000.0, 1_000.0, 1_000.0, load_federal(2025),
                      FilingStatus.HEAD_OF_HOUSEHOLD)

    def test_undeclared_mfj_with_1095a_still_refuses(self):  # carve-out holds
        scenario = dataclasses.replace(
            _high_income(2025, FilingStatus.MARRIED_FILING_JOINTLY),
            form_1095a=Form1095A(months=tuple(
                Form1095AMonth(premium=500, slcsp=500, aptc=0)
                for _ in range(12))))
        with self.assertRaisesRegex(NotImplementedError,
                                    "out of native-1040-spine scope"):
            _orchestrator(self).compute_federal(scenario)
