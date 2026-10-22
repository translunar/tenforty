"""The native childless-EIC (year × status) grid and its fail-closed gates
(childless-EITC spec §10.4): params completeness, battery completeness,
refusal reachability, and the structural unreachability proofs.

The gate functions are pure and injectable, so each is unit-tested with
synthetic inputs (a gate that cannot go red proves nothing), as in
tests/test_status_grid_gates.py.
"""
import dataclasses
import re
import types
import typing
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path

from tenforty import years
from tenforty.models import FilingStatus, Scenario
from tenforty.params.federal import EIC_SCALAR_FIELDS, PER_STATUS_EIC_FIELDS
from tenforty.params.federal import load as load_federal
from tenforty.scenario import load_scenario
from tests.fixtures import eic_battery

REPO_ROOT = Path(__file__).resolve().parent.parent
_EIC_STATUSES = frozenset({FilingStatus.SINGLE.value,
                           FilingStatus.MARRIED_FILING_JOINTLY.value})
# The one scalar whose None is a stated value (no upper age bound), not a gap.
_NULLABLE_SCALARS = frozenset({"eic_max_age"})
_MISSING = object()


def eic_params_gaps(grid: Mapping[int, tuple[str, ...]], *,
                    load: Callable[[int], object]) -> list[tuple[int, str, str]]:
    """(year, status, field) for every declared cell missing an EIC param:
    a per-status field without that status's column, or a scalar that is
    absent (or None, except where None is a stated value)."""
    gaps = []
    for year in sorted(grid):
        params = load(year)
        for status in grid[year]:
            for name in PER_STATUS_EIC_FIELDS:
                column = getattr(params, name, None)
                if column is None or status not in column:
                    gaps.append((year, status, name))
            for name in EIC_SCALAR_FIELDS:
                value = getattr(params, name, _MISSING)
                if value is _MISSING or (
                        value is None and name not in _NULLABLE_SCALARS):
                    gaps.append((year, status, name))
    return gaps


def eic_battery_gaps(grid: Mapping[int, tuple[str, ...]], *,
                     battery: Callable[[int, str], Mapping],
                     required: Callable[[int, str], tuple[str, ...]],
                     ) -> list[tuple[int, str, str]]:
    """(year, status, kind) for every declared cell missing a battery kind."""
    return [(year, status, kind)
            for year in sorted(grid) for status in grid[year]
            for kind in required(year, status)
            if kind not in battery(year, status)]


def eic_refusal_gaps(grid: Mapping[int, tuple[str, ...]], *,
                     required: Callable[[int, tuple[str, ...]],
                                        tuple[str, ...]],
                     fixtures: Mapping[str, Mapping[int, str]],
                     reaches: Callable[[str, str], bool],
                     ) -> list[tuple[int, str]]:
    """(year, refusal key) for every year with a declared cell whose
    refusal has no fixture, or whose fixture does not reach it."""
    gaps = []
    for year in sorted(y for y, statuses in grid.items() if statuses):
        for key in required(year, grid[year]):
            path = fixtures.get(key, {}).get(year)
            if path is None or not reaches(key, path):
                gaps.append((year, key))
    return gaps


def _reaches(key: str, path: str) -> bool:
    """load_scenario then compute_federal refuses, naming ``key`` (a
    load-time refusal counts), through the REAL routing (the step-5
    routing patch was deleted with the step-6 routing change, ruling
    R-S5-1). The workbook path is patched to raise, so a fixture that would
    leave the native spine fails here instead of reaching LibreOffice."""
    from tenforty.orchestrator import ReturnOrchestrator
    import tempfile
    from unittest import mock
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=AssertionError("workbook path reached")):
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=Path(tmp))
        try:
            orch.compute_federal(load_scenario(REPO_ROOT / path))
        except (NotImplementedError, ValueError) as exc:
            return key in str(exc)
    return False


class EicGridShapeTests(unittest.TestCase):

    def test_every_federal_year_has_a_row(self):
        self.assertEqual(set(years.NATIVE_EIC_STATUSES),
                         set(years.FEDERAL_YEARS))

    def test_grid_is_within_the_spine_grid(self):
        for year, statuses in years.NATIVE_EIC_STATUSES.items():
            with self.subTest(year=year):
                self.assertLessEqual(set(statuses),
                                     set(years.NATIVE_SPINE_STATUSES[year]))

    def test_only_single_and_mfj(self):
        for year, statuses in years.NATIVE_EIC_STATUSES.items():
            with self.subTest(year=year):
                self.assertLessEqual(set(statuses), _EIC_STATUSES)
                self.assertEqual(len(statuses), len(set(statuses)))

    def test_native_eic_supports_reads_the_grid(self):
        for year, statuses in years.NATIVE_EIC_STATUSES.items():
            for status in _EIC_STATUSES:
                with self.subTest(year=year, status=status):
                    self.assertEqual(years.native_eic_supports(year, status),
                                     status in statuses)
        self.assertFalse(years.native_eic_supports(1999, "single"))

    def test_eic_fields_are_disjoint(self):
        self.assertEqual(set(PER_STATUS_EIC_FIELDS) & set(EIC_SCALAR_FIELDS),
                         set())


class EicGatesOnTheDeclaredGridTests(unittest.TestCase):
    """The live gates. Red until each declared cell's data lands."""

    def test_declared_grid_has_every_eic_param(self):
        self.assertEqual(eic_params_gaps(years.NATIVE_EIC_STATUSES,
                                         load=load_federal), [])

    def test_declared_grid_has_every_battery_kind(self):
        self.assertEqual(eic_battery_gaps(
            years.NATIVE_EIC_STATUSES, battery=eic_battery.battery_for,
            required=eic_battery.required_eic_kinds), [])

    def test_declared_grid_reaches_every_refusal(self):
        self.assertEqual(eic_refusal_gaps(
            years.NATIVE_EIC_STATUSES,
            required=eic_battery.required_eic_refusals,
            fixtures=eic_battery.EIC_REFUSAL_FIXTURES, reaches=_reaches), [])


class EicGateLivenessTests(unittest.TestCase):
    """Each gate goes red on synthetic input missing exactly one thing."""

    GRID = {2025: ("single",), 2024: ()}

    def _params(self, **overrides):
        values = {name: {"single": 1} for name in PER_STATUS_EIC_FIELDS}
        values |= {name: 1 for name in EIC_SCALAR_FIELDS}
        values |= overrides
        return types.SimpleNamespace(**values)

    def test_params_gate_passes_complete_params(self):
        self.assertEqual(eic_params_gaps(
            self.GRID, load=lambda y: self._params()), [])

    def test_params_gate_names_a_missing_status_column(self):
        name = PER_STATUS_EIC_FIELDS[0]
        self.assertEqual(eic_params_gaps(
            self.GRID, load=lambda y: self._params(**{name: {"mfj": 1}})),
            [(2025, "single", name)])

    def test_params_gate_names_a_missing_scalar(self):
        params = self._params()
        delattr(params, EIC_SCALAR_FIELDS[0])
        self.assertEqual(eic_params_gaps(self.GRID, load=lambda y: params),
                         [(2025, "single", EIC_SCALAR_FIELDS[0])])

    def test_params_gate_allows_only_the_stated_none(self):
        none_all = {name: None for name in EIC_SCALAR_FIELDS}
        gaps = eic_params_gaps(self.GRID,
                               load=lambda y: self._params(**none_all))
        self.assertEqual({g[2] for g in gaps},
                         set(EIC_SCALAR_FIELDS) - _NULLABLE_SCALARS)

    def test_battery_gate_names_a_missing_kind(self):
        self.assertEqual(eic_battery_gaps(
            self.GRID, battery=lambda y, s: {"a": None},
            required=lambda y, s: ("a", "b")), [(2025, "single", "b")])

    def test_refusal_gate_names_missing_and_unreaching_fixtures(self):
        gaps = eic_refusal_gaps(
            self.GRID, required=lambda y, s: ("reached", "unreached", "absent"),
            fixtures={"reached": {2025: "r.yaml"},
                      "unreached": {2025: "u.yaml"}},
            reaches=lambda key, path: path == "r.yaml")
        self.assertEqual(gaps, [(2025, "unreached"), (2025, "absent")])

    def test_refusal_gate_skips_years_with_no_declared_cell(self):
        self.assertEqual(eic_refusal_gaps(
            {2024: ()}, required=lambda y, s: ("k",), fixtures={},
            reaches=lambda key, path: False), [])


def _input_fields() -> dict[str, tuple[str, ...]]:
    """Every dataclass reachable from Scenario -> its field names: the whole
    scenario input surface (the loader refuses unknown keys)."""
    seen: dict[str, tuple[str, ...]] = {}

    def walk(t) -> None:
        for arg in typing.get_args(t):
            walk(arg)
        if (isinstance(t, type) and dataclasses.is_dataclass(t)
                and t.__name__ not in seen):
            hints = typing.get_type_hints(t)
            seen[t.__name__] = tuple(hints)
            for hint in hints.values():
                walk(hint)
    walk(Scenario)
    return seen


# Earned-income items the spec claims no scenario input can produce (§2 Out,
# §5.4, §5.5): each pattern must match exactly the pinned fields, so adding an
# input that could produce one turns its test red.
UNREACHABLE_ITEMS: dict[str, tuple[str, dict[str, str]]] = {
    "form_2555": (r"2555|foreign_earned|foreign_housing", {}),
    "clergy_church_employee": (r"clergy|church|minister|religious", {}),
    "medicaid_waiver": (r"medicaid|waiver|difficulty_of_care", {}),
    "nontaxable_combat_pay": (r"combat|box_?12|nontaxable_pay", {}),
    "form_8814": (r"8814|kiddie|child_(interest|dividend)", {}),
    "form_4797": (r"4797|1231", {
        "SCorpIncome.net_gain_loss_4797":
            "the S corporation's own Form 1120-S income line; it reaches "
            "the individual only inside K-1 ordinary income",
        "ScheduleK1.section_1231_gain":
            "the individual's only Form 4797 path; any K-1 on an "
            "EIC-possible return refuses (worksheet_1_k1)",
        "TaxReturnConfig.acknowledges_no_section_1231_gain":
            "the K-1 section 1231 scope-out acknowledgment, not an amount",
    }),
}


class EicUnreachableInputTests(unittest.TestCase):

    def test_each_item_matches_exactly_its_pinned_fields(self):
        fields = [f"{cls}.{name}" for cls, names in _input_fields().items()
                  for name in names]
        for item, (pattern, pinned) in UNREACHABLE_ITEMS.items():
            with self.subTest(item=item):
                matched = {f for f in fields
                           if re.search(pattern, f.split(".", 1)[1], re.I)}
                self.assertEqual(matched, set(pinned))

    def test_census_sees_the_known_input_surface(self):
        # Guards the walker itself: these must be in the census.
        census = _input_fields()
        for cls, name in (("W2", "wages"), ("ScheduleCBusiness",
                                            "statutory_employee"),
                          ("ScheduleK1", "section_1231_gain")):
            with self.subTest(cls=cls):
                self.assertIn(name, census[cls])


class StatusScopedRefusalTests(unittest.TestCase):
    """Ruling R-S5-3: the joint-return refusal has a reaching fixture now,
    though no MFJ cell is declared yet (the gate requires it once one is)."""

    def test_the_joint_nra_fixture_reaches_with_mfj_declared(self):
        from unittest import mock
        key = "nonresident_alien_spouse_election"
        path = eic_battery.EIC_REFUSAL_FIXTURES[key][2025]
        with mock.patch.dict(years.NATIVE_EIC_STATUSES,
                             {2025: ("single", "married_filing_jointly")}):
            self.assertIn(key, eic_battery.required_eic_refusals(
                2025, years.NATIVE_EIC_STATUSES[2025]))
            self.assertTrue(_reaches(key, path))

    def test_it_is_not_required_while_no_mfj_cell_is_declared(self):
        self.assertNotIn("nonresident_alien_spouse_election",
                         eic_battery.required_eic_refusals(2025, ("single",)))
