"""EIC Table ingestion (scripts/ingest_eic_table.py) and lookup
(tenforty/eic_table.py). Parser tests run on synthetic page text shaped like
the published layout; the asset tests pin the committed CSV to its source by
sha256. The params cross-check lives in tests/test_eic_table_crosscheck.py.
"""
import csv
import hashlib
import json
import shutil
import unittest
from pathlib import Path

from scripts.ingest_eic_table import (
    COLUMNS,
    parse_page,
    rows_for,
    sanity_check,
    source_pdf,
)
from tenforty.eic_table import eic_from_table, load_table
from tenforty.models import FilingStatus

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets" / "eic_tables"
INGESTED_YEARS = (2025,)


def _line(*blocks) -> str:
    return "   ".join("  ".join(str(c) for c in block) for block in blocks)


_FOOT = ("{m} If the amount you are looking up from the worksheet is at least "
         "${a} but less than ${b}, and you have {k} qualifying children who "
         "have valid\nSSNs, your credit is ${c}.\nIf the amount you are "
         "looking up from the worksheet is ${b} or more, and you have {k} "
         "qualifying children who have valid SSNs, you can't take the credit.")


class ParsePageTests(unittest.TestCase):

    def test_two_blocks_per_line_and_the_worked_example_is_skipped(self):
        text = "\n".join([
            "2,400   2,450   186   825   970   1,091",  # page-1 example
            _line([1, 50, 2, 9, 10, 11, 2, 9, 10, 11],
                  ["2,800", "2,850", 216, 961, "1,130", "1,271",
                   216, 961, "1,130", "1,271"]),
        ])
        self.assertEqual(parse_page(text), [
            (1, 50, [2, 9, 10, 11, 2, 9, 10, 11]),
            (2800, 2850, [216, 961, 1130, 1271, 216, 961, 1130, 1271]),
        ])

    def test_a_marked_cell_splits_its_bin_per_the_footnote(self):
        text = "\n".join([
            _line(["19,100", "19,150", "*", "4,328", "7,152", "8,046",
                   542, "4,328", "7,152", "8,046"]),
            _FOOT.format(m="*", a="19,100", b="19,104", k="no", c=0),
        ])
        self.assertEqual(parse_page(text), [
            (19100, 19104, [0, 4328, 7152, 8046, 542, 4328, 7152, 8046]),
            (19104, 19150, [0, 4328, 7152, 8046, 542, 4328, 7152, 8046]),
        ])

    def test_the_marked_column_must_match_the_footnote_child_count(self):
        text = "\n".join([
            _line([100, 150, 0, "*", 0, 0, 0, 0, 0, 0]),
            _FOOT.format(m="*", a="100", b="104", k="no", c=1),
        ])
        with self.assertRaisesRegex(ValueError, "1-child column"):
            parse_page(text)

    def test_an_unresolved_marker_refuses(self):
        with self.assertRaisesRegex(ValueError, "unresolved"):
            parse_page(_line([100, 150, "*", 0, 0, 0, 0, 0, 0, 0]))

    def test_an_unused_footnote_refuses(self):
        text = "\n".join([
            _line([100, 150, 0, 0, 0, 0, 0, 0, 0, 0]),
            _FOOT.format(m="*", a="100", b="104", k="no", c=1),
        ])
        with self.assertRaisesRegex(ValueError, "never used"):
            parse_page(text)

    def test_a_footnote_for_another_bin_refuses(self):
        text = "\n".join([
            _line([100, 150, "*", 0, 0, 0, 0, 0, 0, 0]),
            _FOOT.format(m="*", a="150", b="154", k="no", c=1),
        ])
        with self.assertRaisesRegex(ValueError, "not this bin"):
            parse_page(text)


class SanityCheckTests(unittest.TestCase):

    def _rows(self, series):
        return [(lo, lo + 50, [v] * len(COLUMNS))
                for lo, v in zip(range(0, 50 * len(series), 50), series)]

    def test_accepts_rise_plateau_fall_to_zero(self):
        sanity_check(self._rows([1, 5, 9, 9, 4, 0]))

    def test_rejects_a_gap(self):
        rows = self._rows([1, 5, 0])
        rows[1] = (60, 100, rows[1][2])
        with self.assertRaisesRegex(ValueError, "coverage break"):
            sanity_check(rows)

    def test_rejects_a_dip_before_the_peak(self):
        with self.assertRaisesRegex(ValueError, "non-decreasing"):
            sanity_check(self._rows([1, 5, 3, 9, 0]))

    def test_rejects_a_rise_after_the_peak(self):
        with self.assertRaisesRegex(ValueError, "non-increasing"):
            sanity_check(self._rows([1, 9, 4, 6, 0]))

    def test_rejects_a_nonzero_last_bin(self):
        with self.assertRaisesRegex(ValueError, "last bin"):
            sanity_check(self._rows([1, 9, 4]))


class AssetProvenanceTests(unittest.TestCase):

    def test_provenance_pins_source_and_csv(self):
        for year in INGESTED_YEARS:
            with self.subTest(year=year):
                prov = json.loads(
                    (ASSETS / f"{year}.provenance.json").read_text())
                source = REPO_ROOT / prov["source"]
                self.assertEqual(source, source_pdf(year))
                self.assertEqual(
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    prov["source_sha256"])
                self.assertEqual(hashlib.sha256(
                    (ASSETS / f"{year}.csv").read_bytes()).hexdigest(),
                    prov["csv_sha256"])
                self.assertRegex(prov["edition"],
                                 rf"^Publication 1040 \({year}\) Catalog")

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext not installed")
    def test_reingest_reproduces_the_committed_csv(self):
        for year in INGESTED_YEARS:
            with self.subTest(year=year):
                with open(ASSETS / f"{year}.csv", newline="") as fh:
                    committed = [[int(v) for v in row]
                                 for row in list(csv.reader(fh))[1:]]
                self.assertEqual(
                    [[lo, hi, *cells] for lo, hi, cells in rows_for(year)],
                    committed)


class LookupTests(unittest.TestCase):
    """Bin edges and footnote splits, read against the 2025 asset itself
    (never a transcribed amount)."""

    YEAR = 2025

    def _cell(self, lower, column):
        for lo, _, cells in load_table(self.YEAR):
            if lo == lower:
                return cells[column]
        raise AssertionError(f"no bin at {lower}")

    def test_lower_edge_inclusive_upper_exclusive(self):
        rows = load_table(self.YEAR)
        lo, hi, cells = rows[10]
        nxt = rows[11][2]
        single = FilingStatus.SINGLE
        self.assertEqual(eic_from_table(lo, self.YEAR, single), cells["single_0"])
        self.assertEqual(eic_from_table(hi - 1, self.YEAR, single),
                         cells["single_0"])
        self.assertEqual(eic_from_table(hi, self.YEAR, single), nxt["single_0"])

    def test_statuses_read_their_own_column(self):
        # A bin where the two zero-child columns differ, so a swapped
        # mapping cannot pass.
        lo = next(lo for lo, _, cells in load_table(self.YEAR)
                  if cells["single_0"] != cells["mfj_0"])
        for status, column in ((FilingStatus.SINGLE, "single_0"),
                               (FilingStatus.HEAD_OF_HOUSEHOLD, "single_0"),
                               (FilingStatus.QUALIFYING_WIDOW, "single_0"),
                               (FilingStatus.MARRIED_FILING_JOINTLY, "mfj_0")):
            with self.subTest(status=status):
                self.assertEqual(eic_from_table(lo, self.YEAR, status),
                                 self._cell(lo, column))

    def test_mfs_has_no_column(self):
        with self.assertRaises(ValueError):
            eic_from_table(1000, self.YEAR,
                           FilingStatus.MARRIED_FILING_SEPARATELY)

    def test_split_bins_are_their_own_rows(self):
        split = [(lo, hi) for lo, hi, _ in load_table(self.YEAR)
                 if hi - lo != 50 and lo != 1]
        self.assertEqual(len(split) % 2, 0)
        self.assertGreater(len(split), 0)

    def test_at_or_above_the_last_bin_is_zero(self):
        top = load_table(self.YEAR)[-1][1]
        for children in range(4):
            self.assertEqual(eic_from_table(top, self.YEAR,
                                            FilingStatus.SINGLE, children), 0)

    def test_below_the_first_bin_is_not_a_lookup(self):
        with self.assertRaises(ValueError):
            eic_from_table(0, self.YEAR, FilingStatus.SINGLE)

    def test_children_out_of_range_refuses(self):
        with self.assertRaises(ValueError):
            eic_from_table(1000, self.YEAR, FilingStatus.SINGLE, children=4)

    def test_missing_year_names_the_ingest_script(self):
        with self.assertRaisesRegex(FileNotFoundError, "ingest_eic_table"):
            load_table(2020)
