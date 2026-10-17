"""Form 540: every printed value comes from the computation (ruling A1).

The Form 540 mapping computed 19 printed lines itself (lines 15, 33, 35,
47, 48, the total tax, 78, 93-97, 99, 100, 111, 114, 115 and the line 116
deposit amount), branched on a 100_000 literal for the line 31 tax-table vs
rate-schedule boxes and on use tax for the "no use tax" radio, and returned
a constant for the third-party-designee "No" radio. All of that moves into
the computation (forms.f540.printed_line_keys), and the mapping only
translates compute keys to cells. Every printed value is unchanged
(before-values below; the fill chokepoint's byte-identical emit fixtures).

Before-values (tests/fixtures/compute_keys_f540_before.json) were captured
once from the merge-commit tree 27f30b9: values the code produced, never
hand-derived. Sources (BATTERIES emits no California form, so these stand
in): (a) real emits through run_full_california_return, the f540 values
read from the EmitRecord, five synthetic variants x 2021-2025 chosen to
drive every derivation branch; (b) the hand-worked oracle cases'
production chain (sch_ca.compute -> f540.compute), which put both sides of
the line 31 branch in every year. The capture asserted its own branch
coverage: every cell present in some row, and every absent-when-blank cell
(lines 111, 114, 115, 116 and the deposit cells) both present and absent,
every year.
"""
import ast
import dataclasses
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f540 as form_f540
from tenforty.mappings import pdf_f540
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.models import FilingStatus, W2
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params import california as params_california
from tests._ca_emit_helpers import REPO_ROOT, make_ca_scenario
from tests._ca_fixtures import _write_ca_yaml

_BEFORE = Path(__file__).parent / "fixtures" / "compute_keys_f540_before.json"
_YEARS = (2021, 2022, 2023, 2024, 2025)

# Printed line -> compute key (approved classification).
KEYS = {
    "15": "f540_line_15_agi_after_subtractions",
    "33": "f540_line_33_tax_less_exemption_credits",
    "35": "f540_line_35_tax_before_credits",
    "47": "f540_line_47_credits_lines_40_through_46",
    "48": "f540_line_48_tax_after_credits",
    "64": "f540_line_64_total_tax",
    "65": "f540_line_65_total_tax",
    "78": "f540_line_78_total_payments",
    "93": "f540_line_93_payments_balance",
    "94": "f540_line_94_use_tax_balance",
    "95": "f540_line_95_payments_after_isr_penalty",
    "96": "f540_line_96_isr_penalty_balance",
    "97": "f540_line_97_overpaid_tax",
    "99": "f540_line_99_overpaid_tax_available",
    "100": "f540_line_100_tax_due",
    "111": "f540_line_111_amount_you_owe",
    "114": "f540_line_114_total_amount_due",
    "115": "f540_line_115_refund",
    "116": "f540_line_116_direct_deposit_amount",
}
BOOL_KEYS = {
    "tax_table": "f540_line_31_tax_table",
    "no_use_tax": "f540_line_91_no_use_tax",
    "designee": "f540_designee_no",
}


def _cells(prefix, l15, line_cells, amount_due, deposit, table, use, designee):
    out = {"15": prefix + l15, "tax_table": table, "no_use_tax": use,
           "designee": designee}
    out.update({line: prefix + cell for line, cell in line_cells.items()})
    out.update(dict(zip(("111", "114", "115"), amount_due)))
    out["116"] = deposit
    return out


_STANDARD = {"33": "2032", "35": "2036", "47": "3005", "48": "3006",
             "64": "3010", "78": "3018", "93": "3023", "94": "3024",
             "95": "3025", "96": "3026", "97": "3027", "99": "4004",
             "100": "4005"}
# Year -> printed line -> its cell (the census of the Step-2 classification).
CELLS = {
    2021: _cells("", "2007", {
        "33": "2018", "35": "2022", "47": "2032", "48": "2033", "65": "3006",
        "78": "3013", "93": "3016", "94": "3023", "95": "3017", "96": "3024",
        "97": "3018", "99": "3020", "100": "3021"},
        ("5003", "5008", "5009"), "5010", "2012 CB", "3015 RB", "5025 RB"),
    2022: _cells("", "2021", _STANDARD, ("4027", "5007", "5008"), "5012",
                 "2026 CB", "3020 RB", "5025 RB"),
    2023: _cells("", "2021", _STANDARD, ("4027", "5007", "5008"), "5012",
                 "2026 CB", "3020 RB", "6008 RB"),
    2024: _cells("540-", "2021", _STANDARD,
                 ("540-5002", "540-5006", "540-5007"), "540-5008",
                 "540-2026 CB", "540-3020 RB", "540-6008 RB"),
    2025: _cells("540_form_", "2021", _STANDARD,
                 ("540_form_5002", "540_form_5006", "540_form_5007"),
                 "540_form_5011", "540_form_2026 CB", "540_form_3020 RB",
                 "540_form_6008 RB"),
}


def _w2(withheld, wages=80_000.0):
    return W2(employer="Synthetic Employer", wages=wages,
              federal_tax_withheld=9_000.0, ss_wages=wages,
              ss_tax_withheld=round(wages * 0.062, 2), medicare_wages=wages,
              medicare_tax_withheld=round(wages * 0.0145, 2), state="CA",
              state_tax_withheld=withheld)


_DEPOSIT = dict(refund_routing_number="011000015",
                refund_account_number="000123456")
VARIANTS = {
    "single_refund_direct_deposit": dict(
        status=FilingStatus.SINGLE, withheld=6_000.0, ca540={},
        config=dict(_DEPOSIT, refund_account_type="checking")),
    "single_refund_direct_deposit_savings": dict(
        status=FilingStatus.SINGLE, withheld=6_000.0, ca540={},
        config=dict(_DEPOSIT, refund_account_number="000654321",
                    refund_account_type="savings")),
    "mfj_refund": dict(
        status=FilingStatus.MARRIED_FILING_JOINTLY, withheld=6_000.0,
        ca540={}, config=dict(spouse_first_name="Example",
                              spouse_last_name="Spouse",
                              spouse_ssn="000-00-0002",
                              spouse_birthdate="1986-04-02")),
    "single_balance_due": dict(
        status=FilingStatus.SINGLE, withheld=500.0,
        ca540={"use_tax": 40.0,
               "voluntary_contributions": [{"fund_code": "WLD",
                                            "amount": 10.0}],
               "interest_and_penalties": 12.0,
               "estimated_tax_penalty": 7.0},
        config={}),
    "single_use_tax_over_payments": dict(
        status=FilingStatus.SINGLE, withheld=0.0, ca540={"use_tax": 60.0},
        config={}),
}


def real_emit_values():
    """name -> the f540 values dict each real emit filled the form from."""
    rows = {}
    for year in _YEARS:
        for name, v in VARIANTS.items():
            scn = make_ca_scenario(year, v["status"], w2s=[_w2(v["withheld"])])
            if v["config"]:
                scn = dataclasses.replace(scn, config=dataclasses.replace(
                    scn.config, **v["config"]))
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                ca_yaml = _write_ca_yaml({"ca540": {
                    "estimated_payments": 0.0, "use_tax": 0.0,
                    "interest_and_penalties": 0.0, **v["ca540"]}}, tmp_dir=td)
                orch = ReturnOrchestrator(
                    spreadsheets_dir=REPO_ROOT / "spreadsheets",
                    work_dir=td / "work")
                _res, pdfs = orch.run_full_california_return(
                    scenario=scn, ca_yaml_path=ca_yaml, output_dir=td)
                (rec,) = [r for r in pdfs.record
                          if r.form == ("california", "f540")]
                rows[f"{name}__{year}"] = dict(rec.values)
    return rows


def chain_values():
    """name -> the merged CA values of each hand-worked case's production
    chain, with the printed-line keys the computation now emits."""
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
            merged = {**sch, **f540}
            rows[f"{case.name}__{year}"] = {
                **merged, **form_f540.printed_line_keys(year, merged)}
    return rows


def _derive(year, values):
    return {cell: fn(values) for cell, fn in
            sorted(PdfF540.get_derivations(year).items())}


class _Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = json.loads(_BEFORE.read_text())
        cls.rows = {"real_emit": real_emit_values(),
                    "hand_worked_chain": chain_values()}

    def each(self):
        for source, rows in sorted(self.rows.items()):
            for name, values in sorted(rows.items()):
                yield source, name, int(name.rsplit("__", 1)[1]), values


class NewKeysMatchOldDerivationTests(_Rows):
    """Every printed cell equals what the pre-move derivation produced."""

    def test_every_cell_equals_its_before_value(self):
        n = 0
        for source, name, year, values in self.each():
            with self.subTest(source=source, row=name):
                self.assertEqual(_derive(year, values),
                                 self.before[source][name])
                n += 1
        self.assertEqual(n, sum(len(r) for r in self.before.values()))


class PrintedValuesComeFromComputeKeysTests(_Rows):
    """PROVENANCE: each moved line's compute key carries exactly the value
    the cell prints -- the number is the computation's, not the mapping's."""

    def test_line_keys_carry_the_printed_values(self):
        for source, name, year, values in self.each():
            before = self.before[source][name]
            for line, cell in sorted(CELLS[year].items()):
                if line in BOOL_KEYS:
                    continue
                key = KEYS[line]
                with self.subTest(row=name, line=line):
                    printed = before[cell]
                    if printed is None:
                        self.assertIsNone(values.get(key))
                    elif line == "15":
                        v = values[key]
                        self.assertEqual(f"({abs(v)})" if v < 0 else str(v),
                                         printed)
                    else:
                        self.assertEqual(values[key], printed)

    def test_bool_keys_carry_the_printed_marks(self):
        for source, name, year, values in self.each():
            before = self.before[source][name]
            for line, key in BOOL_KEYS.items():
                cell = CELLS[year][line]
                with self.subTest(row=name, line=line):
                    expected = (before[cell] == "/Yes" if line == "tax_table"
                                else before[cell] is not None)
                    self.assertIs(values.get(key), expected)

    def test_cell_table_is_the_moved_census(self):
        # Every moved cell is in CELLS, once, for every year.
        for year in _YEARS:
            with self.subTest(year=year):
                cells = list(CELLS[year].values())
                self.assertEqual(len(cells), len(set(cells)))
                self.assertLessEqual(set(cells),
                                     set(PdfF540.get_derivations(year)))


class Line47IdentityTests(_Rows):
    """Line 47 (lines 40-46 as printed) is NOT f540_total_credits, which
    also holds the line 32 exemption credits. While the unmodeled lines
    contribute 0: line 47 == f540_total_credits - f540_exemption_credit.
    A merge of the two keys would fail here."""

    def test_line_47_is_total_credits_less_exemption_credits(self):
        for source, name, year, values in self.each():
            with self.subTest(row=name):
                self.assertEqual(
                    values[KEYS["47"]],
                    values["f540_total_credits"] - values["f540_exemption_credit"])

    def test_unmodeled_lines_have_no_keys(self):
        # Absent because unmodeled stays ABSENT as a key (0 only as a term).
        unmodeled = ("f540_line40_child_dep_care", "f540_line43_credit_amount",
                     "f540_line44_credit_amount", "f540_line45_sch_p_credits",
                     "f540_line61_amt", "f540_line62_behavioral_health",
                     "f540_line63_other_taxes", "f540_line64_apas_repayment",
                     "f540_line73_592b_593_withholding",
                     "f540_line74_program_40_motion_picture",
                     "f540_line75_eitc", "f540_line76_yctc", "f540_line77_fytc",
                     "f540_line92_isr_penalty")
        for source, name, year, values in self.each():
            with self.subTest(row=name):
                self.assertEqual([k for k in unmodeled if k in values], [])


class TaxTableThresholdFromParamsTests(unittest.TestCase):
    def test_threshold_is_a_param_not_a_mapping_literal(self):
        self.assertNotIn("100_000", inspect.getsource(pdf_f540))
        self.assertNotIn("100000", inspect.getsource(pdf_f540))

    def test_line_31_branch_reads_the_params_ceiling(self):
        for year in _YEARS:
            ceiling = params_california.load(
                year).tax_table_taxable_income_ceiling
            with self.subTest(year=year):
                for taxable, table in ((ceiling, True), (ceiling + 1, False)):
                    keys = form_f540.printed_line_keys(year, {
                        "f540_taxable_income": taxable,
                        "f540_federal_agi": 0, "sch_ca_total_subtractions": 0,
                        "f540_ca_tax": 0, "f540_exemption_credit": 0,
                        "f540_renter_credit": 0, "f540_ptet_credit": 0,
                        "f540_estimated_payments": 0, "f540_use_tax": 0,
                        "f540_voluntary_contributions": 0,
                        "f540_estimated_tax_penalty": 0})
                    self.assertIs(keys[BOOL_KEYS["tax_table"]], table)


class MappingHasNoArithmeticTests(unittest.TestCase):
    """The Form 540 mapping does no arithmetic: no arithmetic operator, no
    max/min/sum, and comparisons only inside the approved translations (the
    2021-2023 filing-status checkboxes, `== _status`; the line 15 negative
    formatter, `< 0`)."""

    APPROVED_COMPARES = {"c['f540_filing_status'] == _s", "v < 0"}
    # Installers only build field paths (`prefix + "2021"`) and register
    # lambdas; their lambdas are scanned on their own.
    INSTALLERS = {"_install_presentation", "_install_amount_due",
                  "_install_direct_deposit"}

    def _scanned_bodies(self):
        tree = ast.parse(inspect.getsource(pdf_f540))
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                yield "lambda", node.body
        for node in tree.body:   # module-level functions (not class methods)
            if (isinstance(node, ast.FunctionDef)
                    and node.name not in self.INSTALLERS):
                yield node.name, node

    def test_no_arithmetic_and_only_approved_comparisons(self):
        arith, compares, calls = [], set(), []
        for where, body in self._scanned_bodies():
            for node in ast.walk(body):
                if isinstance(node, ast.BinOp):
                    arith.append(f"{where}: {ast.unparse(node)}")
                elif isinstance(node, ast.Compare):
                    compares.add(ast.unparse(node))
                elif (isinstance(node, ast.Call) and getattr(
                        node.func, "id", None) in ("max", "min", "sum")):
                    calls.append(f"{where}: {ast.unparse(node)}")
        self.assertEqual(arith, [])
        self.assertEqual(calls, [])
        self.assertLessEqual(compares, self.APPROVED_COMPARES)


if __name__ == "__main__":
    unittest.main()
