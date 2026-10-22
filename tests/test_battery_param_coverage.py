# tests/test_battery_param_coverage.py
"""Layer-3 coverage gate: every FederalParams field is either exercised by
a battery scenario at its boundary, or consciously waived with a reason.
A field in neither map fails — adding a params field forces this
conversation instead of silently shipping untested."""
import dataclasses
import unittest
from unittest import mock

from tenforty import years as year_manifest
from tenforty.models import FilingStatus
from tenforty.params.federal import PER_STATUS_FEDERAL_FIELDS, FederalParams
from tests.fixtures import eic_battery
from tests.fixtures.spine_battery import (
    REQUIRED_STATUS_SCENARIO_KINDS,
    battery_for,
)

# field -> battery scenario names that exercise it at a boundary.
EXERCISED: dict[str, tuple[str, ...]] = {
    "year": ("canonical_wage_investment_rental",),          # threads everywhere
    "standard_deduction": ("zero_tax_refund", "tax_table_band"),
    "ordinary_brackets": ("zero_tax_refund", "tax_table_band"),
    "qdcgt_breakpoints": ("qdcgt_15_to_20_boundary",),
    "addl_medicare_threshold": ("addl_medicare_boundary",),
    "ss_wage_base": ("qdcgt_15_to_20_boundary",),           # wages above base
    "qbi_threshold": ("qbi_threshold_boundary",),
    "salt_cap_starting": ("itemizer_with_w2_state_tax",),   # cap binds in 2024
    "salt_cap_floor": ("itemizer_with_w2_state_tax",),
    "salt_phaseout_threshold": ("itemizer_with_w2_state_tax",),  # consulted every itemizer
    "nonitemizer_charitable_cap": ("charitable_nonitemizer_2021",),
    # EXERCISED, deliberately NOT waived: the defect this unit exists to fix
    # is precisely an unenforced §1211(b) cap, which regresses SILENTLY — a
    # loss deducted in full instead of at $3,000 understates tax badly and
    # raises nothing. The scenario drives a $50,000 net capital loss, far
    # past the cap, so the limitation binds by a wide margin.
    "capital_loss_limit": ("capital_loss_over_cap",),
    # The aged single row (2021-2024; 2025's is a Schedule 1-A refusal row,
    # R-senior-1a): taxpayer born the day before the cutoff, so both the
    # cutoff and the per-box amount bind. The cutoff's boundary pair is
    # driven in tests/test_age_condition.py::AgeConditionBoundaryTests.
    "additional_standard_deduction": ("std_deduction_aged__single",),
    "aged_born_before": ("std_deduction_aged__single",),
    # Childless EIC (ruling R-S7-4): exercised by tests/fixtures/eic_battery
    # rows, named "eic:<kind>" (the universe below includes them; each is
    # compared native-vs-workbook in tests/test_eic_parity_oracle.py through
    # the answer adapter, except the Schedule C rows, which the workbook
    # path refuses — R-S7-3; no field below rests on those alone).
    "eic_credit_pct": ("eic:phase_in",),
    "eic_earned_income_amount": ("eic:plateau",),
    "eic_max_credit": ("eic:plateau",),
    "eic_phaseout_pct": ("eic:phase_out",),
    "eic_phaseout_threshold": ("eic:agi_over_earned", "eic:phase_out"),
    "eic_completed_phaseout": ("eic:just_under_ceiling", "eic:over_ceiling"),
    "eic_investment_income_limit": ("eic:investment_at_limit",
                                    "eic:investment_over_limit"),
    "eic_min_earned_income": ("eic:earned_income_below_min",
                              "eic:earned_income_at_min"),
    "eic_min_age": ("eic:age_lower_bound_in", "eic:age_lower_bound_out"),
}

# field -> reason it is consciously NOT exercised. Shrinking this map is
# progress; growing it is a decision that belongs in review.
WAIVED: dict[str, str] = {
    "salt_phaseout_rate": "OBBBA >$500k phaseout math is scoped out "
                          "(sch_a raises NotImplementedError above threshold)",
    "medical_agi_floor_pct": "no medical-expense battery scenario yet; "
                             "add one when a medical itemizer enters scope",
    "prior_year_salt_cap": "battery pins prior_year_itemized=False, "
                           "short-circuiting the Sch 1 tax-benefit rule",
    # eic_max_age (ruling R-S7-4 / P5-1): no 2025 battery row can exercise
    # its boundary — both 2025 upper-age rows are aged filers, refused
    # upstream by the Schedule 1-A seniors refusal before any credit is
    # figured. Its boundary is driven by tests/test_eic_compute.py AgeTests
    # and becomes EXERCISED by the step-8 (2022-2024) upper-age rows, where
    # nothing refuses first; this waiver is removed then.
    "eic_max_age": "2025 upper-age rows refuse upstream (Schedule 1-A "
                   "seniors refusal, P5-1); boundary unit-driven by "
                   "tests/test_eic_compute.py AgeTests until the step-8 rows",
    "eic_income_ceiling": "exercised as the routing guard (scope gate), "
                          "not as a computed value",
    "excess_business_loss_threshold":
        "a fail-closed refusal trip-wire, not a computed value: a battery "
        "scenario over it would refuse by design, and battery scenarios "
        "must compute. Driven at its boundary (at / one over, all three "
        "loss lanes) in tests/test_excess_business_loss_guard.py",
}


# Per-status coverage (native-filing-statuses battery-2025): for each
# declared NON-single (year, status), every per-status FederalParams field is
# bound by a kind present in that status's battery, or waived below with a
# reason. Kind = battery-row name prefix before `__`.
STATUS_KIND_BINDS: dict[str, tuple[str, ...]] = {
    "wages_only": ("standard_deduction", "ordinary_brackets"),
    "investments_qdcgt": ("qdcgt_breakpoints",),
    "qbi_k1": ("qbi_threshold",),
    "itemized_salt_at_cap": ("salt_cap_starting",),
    "addl_medicare": ("addl_medicare_threshold",),
    # Binds Form 8962 params (FPL, applicable figure, repayment caps), none
    # of them FederalParams fields.
    "ptc_reconciliation": (),
    # R-hoh-ptc refusal row: refuses before any params are read.
    "ptc_reconciliation_refused": (),
    # Computing aged rows (2021-2024; per-box amount at the cutoff boundary)
    # bind both the base column and the per-box amount.
    "std_deduction_aged": ("standard_deduction",
                           "additional_standard_deduction"),
    "std_deduction_both_aged": ("standard_deduction",
                                "additional_standard_deduction"),
    # R-senior-1a refusal rows (Schedule 1-A): refuse before the deduction
    # is computed, so they bind nothing.
    "std_deduction_aged_refused": (),
    "std_deduction_both_aged_refused": (),
}

PER_STATUS_WAIVED: dict[str, str] = {
    "salt_cap_floor": "read only in sch_a's above-phaseout refusal message; "
                      "below salt_phaseout_threshold the cap is "
                      "salt_cap_starting, so no computing row can reach it",
    "prior_year_salt_cap": "battery pins prior_year_itemized=False, "
                           "short-circuiting the Sch 1 tax-benefit rule",
    "capital_loss_limit": "not one of the six R-battery-n kinds; the "
                          "status-keyed cap is exercised for single by "
                          "capital_loss_over_cap",
    "excess_business_loss_threshold":
        "a fail-closed refusal trip-wire, not a computed value (see WAIVED); "
        "battery rows must compute",
}

# Per-status waivers that apply only in the named years: field -> (years,
# reason). Ruled at back-year-2024 step 8: a global waiver would under-enforce
# the back years, whose computing aged rows bind the field. Per year, a
# year-scoped waiver must NOT coincide with a binding in that year's battery
# (per_status_waiver_conflicts) -- a waiver may only cover what is truly
# unbound.
PER_STATUS_WAIVED_IN_YEARS: dict[str, tuple[frozenset[int], str]] = {
    "additional_standard_deduction": (
        frozenset({2025}),
        "2025 aged rows are Schedule 1-A refusal rows (R-senior-1a), which "
        "refuse before reading it; the per-box arithmetic is unit-tested in "
        "tests/test_age_condition.py::AgedStandardDeductionTests"),
}


def _waived(field: str, year: int) -> bool:
    if field in PER_STATUS_WAIVED:
        return True
    years, _ = PER_STATUS_WAIVED_IN_YEARS.get(field, (frozenset(), ""))
    return year in years


def _kinds(year, status, battery):
    return {name.split("__", 1)[0]
            for name, _ in battery(year, FilingStatus(status))}


def per_status_waiver_conflicts(grid, *, battery=battery_for) -> list[tuple]:
    """(year, status, field) where a year-scoped waiver covers a field that
    the year's battery for that status also binds."""
    conflicts: list[tuple] = []
    for year in sorted(grid):
        for status in grid[year]:
            if status == FilingStatus.SINGLE.value:
                continue
            bound = {f for k in _kinds(year, status, battery)
                     for f in STATUS_KIND_BINDS.get(k, ())}
            conflicts.extend(
                (year, status, f)
                for f, (years, _) in sorted(PER_STATUS_WAIVED_IN_YEARS.items())
                if year in years and f in bound)
    return conflicts


def per_status_coverage_gaps(grid, *, battery=battery_for) -> list[tuple]:
    """(year, status, field-or-unmapped-kind) for every declared non-single
    (year, status) whose battery leaves a per-status field neither bound nor
    waived, or carries a kind STATUS_KIND_BINDS does not map."""
    gaps: list[tuple] = []
    for year in sorted(grid):
        for status in grid[year]:
            if status == FilingStatus.SINGLE.value:
                continue
            kinds = _kinds(year, status, battery)
            gaps.extend((year, status, f"unmapped kind {k}")
                        for k in sorted(kinds - set(STATUS_KIND_BINDS)))
            bound = {f for k in kinds for f in STATUS_KIND_BINDS.get(k, ())}
            gaps.extend((year, status, f) for f in PER_STATUS_FEDERAL_FIELDS
                        if f not in bound and not _waived(f, year))
    return gaps


class PerStatusParamCoverageTests(unittest.TestCase):
    def test_every_per_status_field_exercised_per_declared_status(self):
        self.assertEqual(
            per_status_coverage_gaps(year_manifest.NATIVE_SPINE_STATUSES), [])

    def test_per_status_maps_name_real_fields_and_are_disjoint(self):
        bound = {f for fields in STATUS_KIND_BINDS.values() for f in fields}
        # All-years waivers never overlap a binding; year-scoped waivers are
        # checked per year below (they cover what is unbound THAT year).
        self.assertEqual(bound & set(PER_STATUS_WAIVED), set())
        self.assertEqual(set(PER_STATUS_WAIVED)
                         & set(PER_STATUS_WAIVED_IN_YEARS), set())
        self.assertEqual((bound | set(PER_STATUS_WAIVED)
                          | set(PER_STATUS_WAIVED_IN_YEARS))
                         - set(PER_STATUS_FEDERAL_FIELDS), set())
        self.assertEqual(set(REQUIRED_STATUS_SCENARIO_KINDS)
                         - set(STATUS_KIND_BINDS), set())

    def test_gate_is_live_for_the_2025_status_battery(self):
        # Pinned explicitly (declared since declare-2025, so the declared-grid
        # test above covers them too): the gate is live over their actual
        # rows, and dropping a kind's row is caught.
        grid = {2025: (FilingStatus.MARRIED_FILING_JOINTLY.value,
                       FilingStatus.HEAD_OF_HOUSEHOLD.value)}
        self.assertEqual(per_status_coverage_gaps(grid), [])
        without_medicare = lambda y, s: [
            row for row in battery_for(y, s)
            if not row[0].startswith("addl_medicare__")]
        self.assertEqual(
            per_status_coverage_gaps(grid, battery=without_medicare),
            [(2025, s, "addl_medicare_threshold") for s in grid[2025]])
        stray = lambda y, s: battery_for(y, s) + [("mystery__x", None)]
        self.assertIn((2025, grid[2025][0], "unmapped kind mystery"),
                      per_status_coverage_gaps(grid, battery=stray))


class YearScopedWaiverTests(unittest.TestCase):
    """additional_standard_deduction: bound by the computing aged rows in
    every declared back year, waived (R-senior-1a) only in 2025."""

    GRID_BOTH = {2024: ("married_filing_jointly", "head_of_household"),
                 2025: ("married_filing_jointly", "head_of_household")}

    def test_no_year_scoped_waiver_shadows_a_binding(self):
        self.assertEqual(
            per_status_waiver_conflicts(year_manifest.NATIVE_SPINE_STATUSES),
            [])
        self.assertEqual(per_status_waiver_conflicts(self.GRID_BOTH), [])

    def test_conflict_detector_is_live(self):
        # Waiving the field in 2024 too would shadow the computing aged
        # rows' binding there -- the detector names exactly those cells.
        with mock.patch.dict(PER_STATUS_WAIVED_IN_YEARS, {
                "additional_standard_deduction": (frozenset({2024, 2025}),
                                                  "test")}):
            self.assertEqual(
                per_status_waiver_conflicts(self.GRID_BOTH),
                [(2024, "married_filing_jointly",
                  "additional_standard_deduction"),
                 (2024, "head_of_household",
                  "additional_standard_deduction")])

    def test_2024_is_bound_by_aged_rows_2025_is_waived(self):
        without_aged = lambda y, s: [
            row for row in battery_for(y, s)
            if "aged" not in row[0].split("__", 1)[0]]
        gaps = per_status_coverage_gaps(self.GRID_BOTH, battery=without_aged)
        # Dropping the aged rows leaves the per-box field unbound in 2024
        # (enforced) but not in 2025 (waived, R-senior-1a).
        self.assertEqual(
            [g for g in gaps if g[2] == "additional_standard_deduction"],
            [(2024, "married_filing_jointly", "additional_standard_deduction"),
             (2024, "head_of_household", "additional_standard_deduction")])
        self.assertEqual(per_status_coverage_gaps(self.GRID_BOTH), [])


class BatteryParamCoverageTests(unittest.TestCase):
    def test_every_field_exercised_or_waived(self):
        fields = {f.name for f in dataclasses.fields(FederalParams)}
        placed = set(EXERCISED) | set(WAIVED)
        self.assertEqual(set(EXERCISED) & set(WAIVED), set(),
                         "a field cannot be both exercised and waived")
        self.assertEqual(fields - placed, set(),
                         "params fields with no coverage decision")
        self.assertEqual(placed - fields, set(),
                         "coverage maps name nonexistent fields")

    def test_exercising_scenarios_exist(self):
        # Year-scoped scenarios (e.g. a 2021-only provision's battery) legitimately
        # satisfy coverage for year-scoped params, so the universe is the UNION of
        # scenario names across ALL battery years — not one year. Years come from the
        # canonical manifest so new years extend the universe automatically. Do NOT
        # collapse this back to a single year.
        names: set[str] = set()
        for year in year_manifest.FEDERAL_YEARS + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS:
            names |= {n for n, _ in battery_for(year)}
        # Ruling R-S7-4: the childless-EIC battery's rows join the universe
        # (union only — the spine names above are unchanged), as "eic:<kind>".
        names |= {f"eic:{kind}" for rows in eic_battery.EIC_ROWS.values()
                  for kind in rows}
        for field, scenarios in EXERCISED.items():
            for scenario in scenarios:
                with self.subTest(field=field, scenario=scenario):
                    self.assertIn(scenario, names)
