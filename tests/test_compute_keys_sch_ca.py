"""Schedule CA (540): every printed value comes from the computation (ruling A1).

The Schedule CA mapping computed 16 printed cells itself (15 in 2021): the
Part I section totals (line 1z columns B/C, lines 9a, 10, 25 and 26 in
columns A/B/C), the line 1a column A mirror of the wages (2022-2025; 2021
prints one un-lettered line 1), and Part II line 30 (the Form 540 line 18
deduction, printed only when Part II is on the page). All of that moves into
the computation -- the section totals into forms.sch_ca.compute (every input
is the kernel's own key), line 30 to the CA assembly point (it reads Form 540)
-- and the mapping only places compute keys in cells. Every printed value is
unchanged (before-values below).

Before-values (tests/fixtures/compute_keys_sch_ca_before.json) were captured
once from the merge-commit tree 96a5d2c: values the code produced, never
hand-derived. Sources (BATTERIES emits no California form, so these stand
in): (a) real emits through run_full_california_return, the Schedule CA
values read from the EmitRecord -- a plain return, an itemizing return, and
one catalog divergence per Part I member block in each column; (b) the
production kernel (forms.sch_ca.compute) fed federal results carrying the
Column A sources (line 8z, Section C) and one divergence per block per
column; (c) the hand-worked oracle cases' production chain. The capture
asserted its own coverage every year: every cell nonzero in some row, every
absent-when-blank cell also absent, lines 10 and 26 never absent, every
catalog-reachable (block, column) driven, and line 25 column A proved
unreachable (no Column A source in the line-24 block), so always blank.
"""
import ast
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path

from tenforty.ca_divergences import (
    CatalogDirection, load_catalog, materialize_user_divergence)
from tenforty.forms import sch_ca as form_sch_ca
from tenforty.mappings import pdf_sch_ca
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.models import CA540Return
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_emit_helpers import REPO_ROOT, make_ca_scenario
from tests._ca_fixtures import _write_ca_yaml
from tests.test_ca_sch_ca_part_ii_print import itemizing_scenario

_BEFORE = Path(__file__).parent / "fixtures" / "compute_keys_sch_ca_before.json"
_YEARS = (2021, 2022, 2023, 2024, 2025)

# Printed cell token -> compute key (approved classification).
KEYS = {
    "1aA": "sch_ca_line_part_i_1a_wages_col_a",
    "1zB": "sch_ca_line_part_i_1z_total_subtractions",
    "1zC": "sch_ca_line_part_i_1z_total_additions",
    "line30": "sch_ca_line_part_ii_30",
}
for _line in ("9a", "10", "25", "26"):
    for _col, _suffix in (("A", "col_a"), ("B", "subtractions"),
                          ("C", "additions")):
        KEYS[_line + _col] = f"sch_ca_line_part_i_{_line}_total_{_suffix}"


def _cell_tokens(year):
    """The year's derivation cells before the move: cell -> token."""
    table = {2022: 2023}.get(year, year)
    # Only the moved tokens: 1z column A and 1a columns B/C were always 1:1
    # entries, not derivations.
    totals = {cell: token for token, cell in
              getattr(pdf_sch_ca, f"_TOTAL_CELLS_{table}").items()
              if token in KEYS}
    totals[pdf_sch_ca._PART_II_LINE_30_FIELD[table]] = "line30"
    return totals


# Variant selection ONLY (which catalog ids drive which Part I block); the
# membership the totals use is the computation's, not this table.
_SELECT = {
    "line1": r"part_i_(a_1[a-z]|line_1)", "a_rest": r"part_i_a_(2|3|4|5b|6|7)",
    "b_main": r"part_i_b_(1|2a|3|4|5|6|7)", "line8": r"part_i_b_8[a-z]",
    "line9b": r"part_i_b_9b\d", "c_main": r"part_i_c_(1[1-8]|19a|2[0-3])",
    "line24": r"part_i_c_24[a-z]", "line26": r"part_i_line_26",
}


def _picks(year, direction):
    entries = load_catalog(year)
    entries = list(entries.values()) if isinstance(entries, dict) else list(entries)
    chosen = {}
    for e in sorted(entries, key=lambda e: e.id):
        if not (e.sch_ca_line.startswith("Part I ")
                or e.sch_ca_line == "Part I line 26"):
            continue
        if e.direction not in (direction, CatalogDirection.BOTH):
            continue
        n = form_sch_ca._normalize_line(e.sch_ca_line)
        for block, pattern in _SELECT.items():
            if block not in chosen and re.fullmatch(pattern, n):
                chosen[block] = e
    return chosen


def _yaml_divergences(year, direction, amount):
    rows = []
    for _, e in sorted(_picks(year, direction).items()):
        row = {"id": e.id, "amount": amount}
        if e.direction == CatalogDirection.BOTH:
            row["direction"] = "sub" if direction == CatalogDirection.SUB else "add"
        rows.append(row)
    return rows


def _emit(scenario, ca540):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ca_yaml = _write_ca_yaml(
            {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0,
                       "interest_and_penalties": 0.0, **ca540}}, tmp_dir=td)
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=td / "work")
        _, pdfs = orch.run_full_california_return(
            scenario=scenario, ca_yaml_path=ca_yaml, output_dir=td)
        (record,) = [r for r in pdfs.record if r.form == ("california", "sch_ca")]
        return dict(record.values)


def real_emit_values():
    rows = {}
    for year in _YEARS:
        rows[f"plain__{year}"] = _emit(make_ca_scenario(year), {})
        rows[f"itemizing__{year}"] = _emit(itemizing_scenario(year), {})
        rows[f"all_subtractions__{year}"] = _emit(make_ca_scenario(year), {
            "divergences": _yaml_divergences(year, CatalogDirection.SUB, 100)})
        rows[f"all_additions__{year}"] = _emit(make_ca_scenario(year), {
            "divergences": _yaml_divergences(year, CatalogDirection.ADD, 70)})
    return rows


def kernel_values():
    rows = {}
    for year in _YEARS:
        federal = {"agi": 90_000, "wages": 80_000, "taxable_interest": 1_200,
                   "sch_1_line_8z_other_income": 900,
                   "sch_1_line_11_educator": 250, "sch_1_line_20_ira": 3_000,
                   "sch_1_line_15_se_tax": 400}
        adjustments = []
        for direction, amount in ((CatalogDirection.SUB, 30),
                                  (CatalogDirection.ADD, 20)):
            for _, e in sorted(_picks(year, direction).items()):
                d = None
                if e.direction == CatalogDirection.BOTH:
                    d = "sub" if direction == CatalogDirection.SUB else "add"
                adjustments.append(
                    materialize_user_divergence(e, float(amount), d))
        rows[f"col_a_sources_both_directions__{year}"] = form_sch_ca.compute(
            CA540Return(divergences=adjustments), federal, year)
        rows[f"line_8z_col_a_only__{year}"] = form_sch_ca.compute(
            CA540Return(), {"agi": 50_000, "sch_1_line_8z_other_income": 500},
            year)
    return rows


def chain_values():
    import tests.test_ca_540_oracle as oracle_tests
    from tests.oracles import ca_540_reference as ref
    chain = oracle_tests.HandWorkedStatusCaseProductionChainTests()
    sets = {2025: (ref.HAND_WORKED_STATUS_CASES_2025
                   + ref.HAND_WORKED_AGED_CASES_2025, ref.senior_count_2025)}
    for y in (2021, 2022, 2023, 2024):
        sets[y] = (getattr(ref, f"HAND_WORKED_CASES_{y}")
                   + getattr(ref, f"HAND_WORKED_TABLE_CASES_{y}"),
                   getattr(ref, f"senior_count_{y}"))
    rows = {}
    for year, (cases, seniors) in sets.items():
        for case in cases:
            sch, f540 = chain._run_chain(
                case, ca_withholding=int(sum(case.w2_ca_withholding)),
                year=year, num_seniors=seniors(case))
            rows[f"{case.name}__{year}"] = {**sch, **f540}
    return rows


def _derive(year, values):
    """Every printed cell the before-values cover, as the mapping fills it
    now: a derivation if one remains, else the cell's 1:1 compute key."""
    derivations = PdfSchCa.get_derivations(year)
    by_cell = {cell: key for key, cell in PdfSchCa.get_mapping(year).items()}
    out = {}
    for cell in _cell_tokens(year):
        if cell in derivations:
            out[cell] = derivations[cell](values)
        else:
            out[cell] = values.get(by_cell[cell]) if cell in by_cell else "UNMAPPED"
    return out


class _Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = json.loads(_BEFORE.read_text())
        cls.rows = {"real_emit": real_emit_values(), "kernel": kernel_values(),
                    "hand_worked_chain": chain_values()}

    def each(self):
        for source, rows in sorted(self.rows.items()):
            for name, values in sorted(rows.items()):
                yield source, name, int(name.rsplit("__", 1)[1]), values


class NewKeysMatchOldDerivationTests(_Rows):
    """Every printed cell equals what the pre-move derivation produced."""

    def test_cell_table_is_the_moved_census(self):
        # The cells this lane moves are exactly the pre-move derivation cells
        # the before-values record (16 a year; 15 in 2021).
        for source, rows in sorted(self.before.items()):
            for name, cells in sorted(rows.items()):
                year = int(name.rsplit("__", 1)[1])
                with self.subTest(row=name):
                    self.assertEqual(sorted(cells), sorted(_cell_tokens(year)))

    def test_every_cell_equals_its_before_value(self):
        n = 0
        for source, name, year, values in self.each():
            with self.subTest(source=source, row=name):
                self.assertEqual(_derive(year, values),
                                 self.before[source][name])
                n += 1
        self.assertEqual(n, sum(len(r) for r in self.before.values()))


class PrintedValuesComeFromComputeKeysTests(_Rows):
    """PROVENANCE: each moved cell's compute key carries exactly the value
    the cell prints (absent key = blank cell)."""

    def test_keys_carry_the_printed_values(self):
        for source, name, year, values in self.each():
            before = self.before[source][name]
            for cell, token in sorted(_cell_tokens(year).items()):
                with self.subTest(row=name, token=token):
                    self.assertEqual(values.get(KEYS[token]), before[cell])

    def test_each_moved_cell_is_mapped_from_its_key_alone(self):
        # One writer per cell: before the move the 1z Column B / C cells were
        # ALSO the 1:1 target of the raw line-1z divergence keys (the total's
        # derivation overwrote them at fill time); those keys are now
        # suppressed members of the 1z total.
        for year in _YEARS:
            mapping = PdfSchCa.get_mapping(year)
            for cell, token in sorted(_cell_tokens(year).items()):
                with self.subTest(year=year, token=token):
                    self.assertEqual(
                        sorted(k for k, v in mapping.items() if v == cell),
                        [KEYS[token]])

    def test_line_1a_key_only_where_the_form_prints_line_1a(self):
        # 2021 prints one un-lettered line 1 (no 1a cell, no 1a key).
        for source, name, year, values in self.each():
            prints_1a = "1aA" in _cell_tokens(year).values()
            with self.subTest(row=name):
                if not prints_1a:
                    self.assertNotIn(KEYS["1aA"], values)

    def test_line_25_column_a_is_never_emitted(self):
        # No Column A source exists in the line-24 block (see the module
        # docstring): the key stays absent, as the cell stays blank.
        for source, name, year, values in self.each():
            with self.subTest(row=name):
                self.assertNotIn(KEYS["25A"], values)


class TotalKeysAreNotMembersTests(unittest.TestCase):
    """A total key that matched a member pattern would be summed into itself
    (or into line 10/26): the names are pinned outside every pattern."""

    def test_no_new_key_matches_a_member_pattern(self):
        for key in KEYS.values():
            for pattern in form_sch_ca.PART_I_MEMBER_PATTERNS:
                with self.subTest(key=key, pattern=pattern):
                    self.assertIsNone(re.fullmatch(
                        rf"sch_ca_line_({pattern})_(col_a|subtractions|additions)",
                        key))


class MappingHasNoArithmeticTests(unittest.TestCase):
    """The Schedule CA mapping places compute keys in cells: no derivation
    or aggregation remains, and no lambda, sum, min or max in the module."""

    def test_no_derivations_or_aggregations_remain(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(PdfSchCa.get_derivations(year), {})
                self.assertEqual(PdfSchCa.get_aggregations(year), {})

    def test_module_has_no_lambda_or_summing_calls(self):
        tree = ast.parse(inspect.getsource(pdf_sch_ca))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                found.append(f"lambda @ line {node.lineno}")
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id in ("sum", "min", "max")):
                found.append(f"{node.func.id}() @ line {node.lineno}")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
