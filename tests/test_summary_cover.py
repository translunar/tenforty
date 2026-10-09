"""Results snapshots + the one-page columnar cover sheet (tenforty.summary).

Every results dict here is SYNTHETIC — round figures invented for the test,
keyed the way the orchestrator's compute paths key them.
"""
import datetime
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from tenforty import summary


def _native_results(**overrides) -> dict:
    """A native-spine-shaped federal results dict (single filer, W-2 + a
    business), internally consistent so the rows foot."""
    results = {
        "wages": 80000,
        "taxable_interest": 500,
        "interest_income": 500,
        "ordinary_dividends": 0,
        "dividend_income": 0,
        "capital_gain_loss": None,
        "sch_1_line_1_taxable_refunds": 0,
        "sch_1_line_3_business_income": 20000,
        "sch_1_line_4_other_gains": 0,
        "sch_1_line_5_rental_re_royalty": 0,
        "sch_1_line_6_farm_income": 0,
        "sch_1_line_7_unemployment": 0,
        "sch_1_line_10": 20000,
        "total_income": 100500,
        "adjustments": 1413,
        "agi": 99087,
        "standard_deduction": 14600,
        "schedule_a_total": 0,
        "total_deductions": 14600,
        "applied_deduction": 14600,
        "qbi_deduction": 3717,
        "_qbi_deduction_1040": 3717,
        "taxable_income": 80770,
        "total_tax": 12800,
        "schedule2_tax": 0,
        "tax_plus_schedule2": 12800,
        "total_credits": 0,
        "tax_after_credits": 12800,
        "other_taxes": 2826,
        "total_payments": 14000,
        "overpaid": 0,
        "refund": 0,
        "amount_owed": 1626,
    }
    results.update(overrides)
    return results


def _snap(results: dict, year: int = 2024, label: str = "Sch C") -> dict:
    return {
        "schema": summary.SNAPSHOT_SCHEMA,
        "year": year,
        "label": label,
        "results": results,
    }


def _rows(columns, extra_rows=None) -> dict[str, list[str]]:
    """Printed table as {row label: [cell text per column]} (header dropped)."""
    table = summary.cover_table(columns, extra_rows=extra_rows)
    return {row[0]: row[1:] for row in table[1:]}


class SnapshotRoundTripTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_full_results_dict_round_trips_with_metadata(self):
        results = _native_results(some_future_key_no_row_reads=42)
        path = summary.write_results_snapshot(
            results, self.tmp / "snap.json", year=2024, label="K-1")
        self.assertEqual(path, self.tmp / "snap.json")
        loaded = summary.load_results_snapshot(path)
        self.assertEqual(loaded["results"], results)
        self.assertEqual(loaded["year"], 2024)
        self.assertEqual(loaded["label"], "K-1")
        self.assertEqual(loaded["schema"], summary.SNAPSHOT_SCHEMA)
        self.assertIsNone(loaded["scenario"])
        self.assertEqual(loaded["emitted"], [])
        # ISO timestamp, parseable.
        datetime.datetime.fromisoformat(loaded["created_at"])

    def test_non_json_values_are_coerced_to_strings(self):
        results = {
            "a_path": Path("/tmp/x.pdf"),
            "a_date": datetime.date(2024, 4, 15),
            "a_decimal": Decimal("12.50"),
            "a_number": 7,
        }
        path = summary.write_results_snapshot(
            results, self.tmp / "snap.json", year=2023, label="x")
        loaded = json.loads(path.read_text())["results"]
        self.assertEqual(loaded["a_path"], "/tmp/x.pdf")
        self.assertEqual(loaded["a_date"], "2024-04-15")
        self.assertEqual(loaded["a_decimal"], "12.50")
        self.assertEqual(loaded["a_number"], 7)

    def test_scenario_path_and_sha256_are_recorded(self):
        scenario = self.tmp / "scenario.yaml"
        scenario.write_bytes(b"config:\n  year: 2024\n")
        path = summary.write_results_snapshot(
            {"agi": 1}, self.tmp / "snap.json", year=2024, label="x",
            scenario_path=scenario)
        loaded = summary.load_results_snapshot(path)
        self.assertEqual(loaded["scenario"]["path"], str(scenario))
        self.assertEqual(
            loaded["scenario"]["sha256"],
            hashlib.sha256(b"config:\n  year: 2024\n").hexdigest())

    def test_emitted_form_names_from_mapping_or_iterable(self):
        emitted = {"sch_c": Path("/out/sch_c.pdf"), "f1040": Path("/out/f1040.pdf")}
        path = summary.write_results_snapshot(
            {"agi": 1}, self.tmp / "a.json", year=2024, label="x",
            emitted=emitted)
        self.assertEqual(
            summary.load_results_snapshot(path)["emitted"], ["f1040", "sch_c"])
        path = summary.write_results_snapshot(
            {"agi": 1}, self.tmp / "b.json", year=2024, label="x",
            emitted=["sch_1", "f1040"])
        self.assertEqual(
            summary.load_results_snapshot(path)["emitted"], ["f1040", "sch_1"])

    def test_load_refuses_a_file_that_is_not_a_snapshot(self):
        bogus = self.tmp / "bogus.json"
        bogus.write_text(json.dumps({"agi": 5}))
        with self.assertRaises(ValueError):
            summary.load_results_snapshot(bogus)


class VocabularyMappingTests(unittest.TestCase):

    def test_header_row_is_year_dot_label_per_column(self):
        table = summary.cover_table([
            _snap(_native_results(), year=2023, label="K-1"),
            _snap(_native_results(), year=2024, label="Sch C"),
        ])
        self.assertEqual(table[0], ["", "TY2023 · K-1", "TY2024 · Sch C"])

    def test_native_rows_map_to_spine_keys(self):
        rows = _rows([_snap(_native_results())])
        self.assertEqual(rows["Wages"], ["80,000"])
        self.assertEqual(rows["Interest"], ["500"])
        self.assertEqual(rows["Business income (Sch C)"], ["20,000"])
        self.assertEqual(rows["Total income"], ["100,500"])
        self.assertEqual(rows["Adjustments"], ["1,413"])
        self.assertEqual(rows["AGI"], ["99,087"])
        self.assertEqual(rows["Deduction"], ["std 14,600"])
        self.assertEqual(rows["QBI deduction"], ["3,717"])
        self.assertEqual(rows["Taxable income"], ["80,770"])
        self.assertEqual(rows["Income tax"], ["12,800"])
        self.assertEqual(rows["Other taxes (Sch 2)"], ["2,826"])
        self.assertEqual(rows["Payments"], ["14,000"])

    def test_total_tax_is_line_24_not_the_line_16_total_tax_key(self):
        # `total_tax` is 1040 line 16. Line 24 = line 22 + line 23.
        rows = _rows([_snap(_native_results())])
        self.assertEqual(rows["Income tax"], ["12,800"])
        self.assertEqual(rows["Total tax"], ["15,626"])

    def test_workbook_path_total_tax_reads_the_harvested_line_24(self):
        results = _native_results(tax_liability_line24=15700)
        del results["tax_after_credits"], results["other_taxes"]
        rows = _rows([_snap(results)])
        self.assertEqual(rows["Total tax"], ["15,700"])

    def test_other_taxes_is_never_a_partial_total(self):
        # Part I present, Part II (other_taxes) absent → the row has no value
        # for that column rather than printing Part I alone as the total.
        partial = _native_results(schedule2_tax=400)
        del partial["other_taxes"]
        rows = _rows([_snap(_native_results()), _snap(partial)])
        self.assertEqual(rows["Other taxes (Sch 2)"], ["2,826", "—"])

    def test_itemized_deduction_is_labeled(self):
        rows = _rows([_snap(_native_results(
            standard_deduction=0, schedule_a_total=21000,
            total_deductions=21000, applied_deduction=21000))])
        self.assertEqual(rows["Deduction"], ["itemized 21,000"])

    def test_sch_e_capital_loss_and_other_income_rows(self):
        rows = _rows([_snap(_native_results(
            capital_gain_loss=-3000,
            sch_1_line_5_rental_re_royalty=7500,
            sch_1_line_7_unemployment=1200,
            sch_1_line_10=28700,
        ))])
        self.assertEqual(rows["Capital gain/loss (Sch D)"], ["(3,000)"])
        self.assertEqual(
            rows["Rentals, royalties & pass-throughs (Sch E)"], ["7,500"])
        # Residual of Sch 1 line 10 after lines 3 and 5: 28,700-20,000-7,500.
        self.assertEqual(rows["Unemployment/other income"], ["1,200"])

    def test_retirement_row_sums_the_1040_line_4_5_6_taxable_keys(self):
        rows = _rows([_snap(_native_results(
            ira_taxable=1000, pensions_taxable=2000,
            social_security_taxable=300))])
        self.assertEqual(rows["Retirement/Social Security"], ["3,300"])

    def test_row_absent_in_every_column_is_not_printed(self):
        rows = _rows([_snap(_native_results()), _snap(_native_results())])
        for label in (
            "Dividends",                       # zero in both
            "Capital gain/loss (Sch D)",       # None in both
            "Retirement/Social Security",      # keys absent in both
            "Credits",                         # zero in both
            "CA AGI", "CA bottom line",        # no CA results
            "1040-X bottom line", "Schedule X bottom line",
        ):
            self.assertNotIn(label, rows)
        # Reachability: the same labels DO print when a column carries them.
        rows = _rows([_snap(_native_results(
            ordinary_dividends=10, capital_gain_loss=5, ira_taxable=1,
            total_credits=2, f540_ca_agi=3, f540_total_liability=4,
            f1040x_line20_amount_owed=6, f1040x_line21=0,
            schedule_x_line7_amount_owed=7, schedule_x_line9=0))])
        for label in (
            "Dividends", "Capital gain/loss (Sch D)",
            "Retirement/Social Security", "Credits", "CA AGI",
            "CA bottom line", "1040-X bottom line", "Schedule X bottom line",
        ):
            self.assertIn(label, rows)

    def test_value_one_column_lacks_prints_a_dash(self):
        with_div = _native_results(ordinary_dividends=900)
        without = _native_results()
        del without["ordinary_dividends"], without["dividend_income"]
        rows = _rows([_snap(with_div), _snap(without)])
        self.assertEqual(rows["Dividends"], ["900", "—"])

    def test_present_zero_prints_zero_not_a_dash(self):
        rows = _rows([
            _snap(_native_results(ordinary_dividends=900)),
            _snap(_native_results()),  # ordinary_dividends == 0, present
        ])
        self.assertEqual(rows["Dividends"], ["900", "0"])

    def test_state_block_prints_only_for_columns_with_ca_results(self):
        ca = _native_results(
            f540_ca_agi=98000, f540_taxable_income=92000, f540_ca_tax=5100,
            f540_total_liability=-640)
        rows = _rows([_snap(_native_results()), _snap(ca)])
        self.assertEqual(rows["CA AGI"], ["—", "98,000"])
        self.assertEqual(rows["CA taxable"], ["—", "92,000"])
        self.assertEqual(rows["CA tax"], ["—", "5,100"])
        self.assertEqual(rows["CA bottom line"], ["—", "refund 640"])

    def test_extra_rows_are_caller_strings_by_column_index(self):
        rows = _rows(
            [_snap(_native_results()), _snap(_native_results())],
            extra_rows={"Statute": {1: "closed 4/26"}})
        self.assertEqual(rows["Statute"], ["—", "closed 4/26"])

    def test_extra_row_values_must_be_short_strings(self):
        with self.assertRaises(ValueError):
            summary.cover_table(
                [_snap(_native_results())],
                extra_rows={"Note": {0: "This sentence explains at length "
                                        "why the statute is closed."}})
        with self.assertRaises(ValueError):
            summary.cover_table(
                [_snap(_native_results())],
                extra_rows={"Note": {3: "x"}})  # no such column


class BottomLineSignTests(unittest.TestCase):

    def test_owe(self):
        rows = _rows([_snap(_native_results())])
        self.assertEqual(rows["BOTTOM LINE"], ["owe 1,626"])

    def test_refund(self):
        rows = _rows([_snap(_native_results(
            total_payments=17000, overpaid=1374, refund=1374, amount_owed=0))])
        self.assertEqual(rows["BOTTOM LINE"], ["refund 1,374"])

    def test_workbook_path_owe_is_derived_from_line_24_less_payments(self):
        # The workbook harvest has `overpaid` but no `amount_owed`.
        results = _native_results(tax_liability_line24=15700, overpaid=0)
        del results["amount_owed"], results["refund"]
        rows = _rows([_snap(results)])
        self.assertEqual(rows["BOTTOM LINE"], ["owe 1,700"])

    def test_no_settlement_keys_is_absent_not_zero(self):
        results = _native_results()
        for key in ("amount_owed", "refund", "overpaid"):
            del results[key]
        rows = _rows([_snap(_native_results()), _snap(results)])
        self.assertEqual(rows["BOTTOM LINE"], ["owe 1,626", "—"])

    def test_ca_bottom_line_sign_follows_the_signed_net_liability(self):
        owe = _rows([_snap(_native_results(f540_total_liability=250))])
        self.assertEqual(owe["CA bottom line"], ["owe 250"])
        refund = _rows([_snap(_native_results(f540_total_liability=-250))])
        self.assertEqual(refund["CA bottom line"], ["refund 250"])

    def test_amendment_bottom_lines(self):
        rows = _rows([
            _snap(_native_results(
                f1040x_line20_amount_owed=0, f1040x_line21=812,
                schedule_x_line7_amount_owed=95, schedule_x_line9=0)),
            _snap(_native_results(
                f1040x_line20_amount_owed=300, f1040x_line21=0,
                schedule_x_line7_amount_owed=0, schedule_x_line9=41)),
        ])
        self.assertEqual(rows["1040-X bottom line"], ["refund 812", "owe 300"])
        self.assertEqual(rows["Schedule X bottom line"], ["owe 95", "refund 41"])


    def test_even_bottom_lines_print_zero_instead_of_collapsing(self):
        # Nothing due, nothing refunded is the headline fact of a return:
        # bottom-line rows are exempt from zero-collapse.
        even = _native_results(
            total_payments=15626, overpaid=0, refund=0, amount_owed=0,
            f540_total_liability=0,
            f1040x_line20_amount_owed=0, f1040x_line21=0,
            schedule_x_line7_amount_owed=0, schedule_x_line9=0)
        rows = _rows([_snap(even), _snap(even)])
        for label in ("BOTTOM LINE", "CA bottom line", "1040-X bottom line",
                      "Schedule X bottom line"):
            self.assertEqual(rows[label], ["0", "0"])

    def test_bottom_line_no_column_carries_still_does_not_print(self):
        # The exemption is for an EVEN bottom line, not an absent one.
        rows = _rows([_snap(_native_results())])
        for label in ("CA bottom line", "1040-X bottom line",
                      "Schedule X bottom line"):
            self.assertNotIn(label, rows)

    def test_exemption_is_bottom_lines_only(self):
        rows = _rows([_snap(_native_results(total_credits=0))])
        self.assertNotIn("Credits", rows)


class RenderedCoverTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _text(self, pdf: Path) -> str:
        reader = PdfReader(str(pdf))
        self.assertEqual(len(reader.pages), 1)
        # Layout mode reassembles each table row onto one text line, so
        # left-to-right order within a line is the printed column order.
        return reader.pages[0].extract_text(extraction_mode="layout")

    def test_one_page_with_headers_and_a_row_in_column_order(self):
        a = summary.write_results_snapshot(
            _native_results(), self.tmp / "a.json", year=2023, label="K-1")
        b = _snap(_native_results(wages=91234), year=2024, label="Sch C")
        out = summary.compose_cover([a, b], self.tmp / "cover.pdf")
        self.assertEqual(out, self.tmp / "cover.pdf")
        text = self._text(out)
        self.assertLess(text.index("TY2023 · K-1"), text.index("TY2024 · Sch C"))
        wages_line = next(
            line for line in text.splitlines() if line.startswith("Wages"))
        self.assertLess(wages_line.index("80,000"), wages_line.index("91,234"))

    def test_collapsed_row_is_absent_from_the_rendered_text(self):
        both = [_snap(_native_results()), _snap(_native_results())]
        text = self._text(summary.compose_cover(both, self.tmp / "c.pdf"))
        self.assertNotIn("Dividends", text)
        self.assertIn("Wages", text)
        # Reachability: the label does render when one column carries it,
        # and the column lacking it shows the dash.
        lacking = _native_results()
        del lacking["ordinary_dividends"], lacking["dividend_income"]
        mixed = [_snap(_native_results(ordinary_dividends=900)), _snap(lacking)]
        text = self._text(summary.compose_cover(mixed, self.tmp / "d.pdf"))
        line = next(l for l in text.splitlines() if l.startswith("Dividends"))
        self.assertIn("900", line)
        self.assertIn("—", line)

    def test_too_many_columns_refuses_rather_than_overflowing(self):
        columns = [_snap(_native_results(), label=f"posture {i}")
                   for i in range(30)]
        out = self.tmp / "wide.pdf"
        with self.assertRaises(summary.CoverOverflowError) as ctx:
            summary.compose_cover(columns, out)
        self.assertIn("one page", str(ctx.exception))
        self.assertFalse(out.exists())

    def test_too_many_rows_refuses_rather_than_overflowing(self):
        extra = {f"Note {i}": {0: "x"} for i in range(80)}
        out = self.tmp / "tall.pdf"
        with self.assertRaises(summary.CoverOverflowError):
            summary.compose_cover(
                [_snap(_native_results())], out, extra_rows=extra)
        self.assertFalse(out.exists())

    def test_no_columns_is_refused(self):
        with self.assertRaises(ValueError):
            summary.compose_cover([], self.tmp / "empty.pdf")


DASH_CELL = "—"


def _whole(cell: str) -> int:
    """A printed money cell back to an int ("(3,000)" -> -3000)."""
    digits = cell.split()[-1].replace(",", "")
    return -int(digits.strip("()")) if digits.startswith("(") else int(digits)


class NativeSpineKeyContractTests(unittest.TestCase):
    """The synthetic dicts above ENCODE the key names; this drives the real
    native compute so a renamed spine key cannot leave them agreeing with a
    mapping that no longer reads anything. Asserts footing, not figures."""

    def setUp(self):
        from tenforty.orchestrator import ReturnOrchestrator
        from tests.fixtures import sch_c_battery
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        repo_root = Path(__file__).parent.parent
        orch = ReturnOrchestrator(
            spreadsheets_dir=repo_root / "spreadsheets",
            work_dir=Path(self._tmp.name),
        )
        results = orch.compute_federal(
            sch_c_battery.build("day-job-plus-consulting", 2024))
        path = summary.write_results_snapshot(
            results, Path(self._tmp.name) / "snap.json", year=2024,
            label="Sch C")
        self.rows = _rows([path])

    def test_every_expected_row_reads_a_real_value(self):
        for label in (
            "Wages", "Business income (Sch C)", "Total income", "Adjustments",
            "AGI", "Deduction", "QBI deduction", "Taxable income",
            "Income tax", "Other taxes (Sch 2)", "Total tax", "BOTTOM LINE",
        ):
            self.assertIn(label, self.rows)
            self.assertNotEqual(self.rows[label], [DASH_CELL])

    def test_income_rows_foot_to_total_income(self):
        income = (
            "Wages", "Interest", "Dividends", "Capital gain/loss (Sch D)",
            "Business income (Sch C)",
            "Rentals, royalties & pass-throughs (Sch E)",
            "Retirement/Social Security", "Unemployment/other income",
        )
        total = sum(_whole(self.rows[l][0]) for l in income if l in self.rows)
        self.assertEqual(total, _whole(self.rows["Total income"][0]))

    def test_computation_rows_foot_to_taxable_income(self):
        r = {k: _whole(v[0]) for k, v in self.rows.items()}
        self.assertEqual(r["Total income"] - r["Adjustments"], r["AGI"])
        self.assertEqual(
            r["AGI"] - r["Deduction"] - r["QBI deduction"],
            r["Taxable income"])

    def test_tax_rows_foot_to_the_bottom_line(self):
        r = {k: _whole(v[0]) for k, v in self.rows.items()}
        self.assertEqual(
            r["Income tax"] + r["Other taxes (Sch 2)"] - r.get("Credits", 0),
            r["Total tax"])
        # This scenario withholds nothing, so the whole liability is owed.
        self.assertNotIn("Payments", self.rows)
        self.assertEqual(
            self.rows["BOTTOM LINE"], [f"owe {r['Total tax']:,}"])
