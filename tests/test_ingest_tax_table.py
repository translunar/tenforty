# tests/test_ingest_tax_table.py
"""Parser + normalization + sanity checks for tax-table ingestion.

The real IRS/FTB PDFs lay three side-by-side table blocks per visual line and
break the sub-$25 federal bins across stacked text fragments differently from
year to year, so the parser reads word COORDINATES (`pdftotext -bbox`) rather
than `-layout` text. These fixtures therefore mirror the real layout at the
coordinate level: numeric words carry (x, y) positions, several 6- or 5-column
blocks share a y (one visual line), low bins appear stacked at stepped y, and
header / section-label / "$100,000 or over" noise words sit at their own y (and
sometimes at the SAME y as a real row) — exactly the shapes that defeated the
old whole-text regex.
"""
import unittest

from scripts.ingest_tax_table import (
    normalize_california,
    parse_rows,
    sanity_check,
)


def _line(y, tokens):
    """Build (x, y, text) word tuples for one visual line: tokens=[(x, text)]."""
    return [(float(x), float(y), text) for x, text in tokens]


def _block(x0, values, step=30):
    """Lay `values` left-to-right starting at x0, `step` apart -> [(x, text)]."""
    return [(x0 + i * step, str(v)) for i, v in enumerate(values)]


class ParseRowsFederalTests(unittest.TestCase):
    """Federal-shaped (6-col) extraction from realistic multi-block coordinates."""

    def _words(self):
        words = []
        # Header line: prose words + a stray "15" from "If line 15" — no bins.
        words += _line(10, [(10, "At"), (40, "least"), (70, "But"),
                            (100, "less"), (400, "15")])
        # Section sub-labels ("1,000" / "2,000") on their own line — no bins.
        words += _line(20, [(250, "1,000"), (490, "2,000")])
        # One visual line with THREE side-by-side 6-col blocks.
        words += _line(30, _block(10, [0, 5, 0, 0, 0, 0])
                       + _block(250, [1000, 1025, 101, 101, 101, 101])
                       + _block(490, [2000, 2025, 201, 201, 201, 201]))
        # Stacked low bins: block1-only rows at stepped y (as -bbox renders them).
        words += _line(44, _block(10, [5, 15, 1, 1, 1, 1]))
        words += _line(51, _block(10, [15, 25, 2, 2, 2, 2]))
        # A real row with the "$100,000 or over" trailer number glued at the
        # same y (x far right): greedy resync must keep the row, drop the stray.
        words += _line(58, _block(10, [25, 50, 4, 4, 4, 4]) + [(700.0, "$100,000")])
        # "$100,000 or over — use the Tax Computation Worksheet" prose — no bins.
        words += _line(70, [(10, "$100,000"), (60, "or"), (90, "over")])
        return words

    def test_extracts_only_real_bins_from_multiblock_and_stacked_layout(self):
        rows = parse_rows(self._words(), columns=6)
        self.assertEqual(
            sorted(set(rows)),
            sorted({
                (0, 5, 0, 0, 0, 0),
                (5, 15, 1, 1, 1, 1),
                (15, 25, 2, 2, 2, 2),
                (25, 50, 4, 4, 4, 4),
                (1000, 1025, 101, 101, 101, 101),
                (2000, 2025, 201, 201, 201, 201),
            }),
        )

    def test_header_and_prose_lines_yield_no_rows(self):
        noise = (_line(10, [(10, "At"), (40, "least"), (400, "15")])
                 + _line(20, [(250, "1,000"), (490, "2,000")])
                 + _line(70, [(10, "$100,000"), (60, "or"), (90, "over")]))
        self.assertEqual(parse_rows(noise, columns=6), [])


class ParseRowsCaliforniaTests(unittest.TestCase):
    """CA-shaped (5-col) extraction, including the '$'-prefixed first row and
    the 'Filing status: 1 or 3 ... 2 or 5 ... 4' header noise."""

    def test_extracts_five_column_blocks_and_ignores_filing_status_header(self):
        words = []
        # "Filing status: 1 or 3 ... 2 or 5 ... 4" -> numbers 1,3,2,5,4 (no bins:
        # each candidate window is far too narrow to be a real income bin).
        words += _line(10, [(10, "1"), (40, "3"), (70, "2"), (100, "5"),
                            (130, "4")])
        # One visual line, three 5-col blocks; first block uses '$'-prefixed cells.
        words += _line(20, _block(10, ["$1", "$50", "$0", "$0", "$0"])
                       + _block(250, [6451, 6550, 65, 65, 65])
                       + _block(450, [12951, 13050, 152, 130, 130]))
        rows = parse_rows(words, columns=5)
        self.assertEqual(
            sorted(set(rows)),
            sorted({
                (1, 50, 0, 0, 0),
                (6451, 6550, 65, 65, 65),
                (12951, 13050, 152, 130, 130),
            }),
        )


class NormalizeCaliforniaTests(unittest.TestCase):
    """Pins the settled CA convention: +1 to every upper (top clamped to the
    ceiling), first bin extended down to 0 keeping its published $0 cells, and
    FTB 3 columns -> 4-column schema (single=col1, mfj=col2, mfs=col1, hoh=col3)."""

    _RAW = [
        (1, 50, 0, 0, 0),
        (51, 150, 1, 1, 1),
        (6451, 6550, 65, 65, 65),
        (99951, 100000, 5840, 3154, 3871),
    ]

    def test_inclusive_to_exclusive_and_first_bin_extended(self):
        out = normalize_california(self._RAW)
        self.assertEqual(out[0], (0, 51, 0, 0, 0, 0))
        self.assertEqual(out[1], (51, 151, 1, 1, 1, 1))
        self.assertEqual(out[2], (6451, 6551, 65, 65, 65, 65))
        # Top upper clamps to the ceiling (100000+1 would overshoot); mfs=col1.
        self.assertEqual(out[-1], (99951, 100000, 5840, 3154, 5840, 3871))

    def test_raises_when_first_bin_tax_nonzero(self):
        raw = [(1, 50, 0, 1, 0), (51, 150, 1, 1, 1)]
        with self.assertRaises(ValueError):
            normalize_california(raw)


class SanityCheckTests(unittest.TestCase):
    _GOOD = [
        (0, 50, 2, 2, 2, 2),
        (50, 100, 8, 7, 8, 7),
        (100, 100_000, 17_000, 15_000, 17_000, 16_000),
    ]

    def test_accepts_contiguous_monotonic_rows(self):
        sanity_check(self._GOOD, ceiling=100_000)  # no raise

    def test_rejects_gap_in_coverage(self):
        rows = [(0, 50, 2, 2, 2, 2), (60, 100_000, 9, 8, 9, 8)]
        with self.assertRaises(ValueError):
            sanity_check(rows, ceiling=100_000)

    def test_rejects_nonmonotonic_tax(self):
        rows = [(0, 50, 5, 5, 5, 5), (50, 100_000, 3, 3, 3, 3)]
        with self.assertRaises(ValueError):
            sanity_check(rows, ceiling=100_000)

    def test_rejects_wrong_ceiling(self):
        with self.assertRaises(ValueError):
            sanity_check(self._GOOD, ceiling=200_000)

    def test_accepts_real_california_low_secondary_columns(self):
        # CA top-bin MFJ/HoH taxes are legitimately sub-$5k; the column-aware
        # floor ($1k for non-single columns) must ACCEPT them.
        rows = [
            (0, 99_951, 5_000, 3_000, 3_000, 3_500),
            (99_951, 100_000, 5_840, 3_154, 3_154, 3_871),
        ]
        sanity_check(rows, ceiling=100_000)  # no raise

    def test_rejects_zeroed_secondary_column(self):
        # A garbled/zeroed MFJ column (top value 0, below the $1k floor) must
        # still RAISE — the 1% floor keeps guarding the secondary columns.
        rows = [
            (0, 99_951, 5_000, 0, 3_000, 3_500),
            (99_951, 100_000, 5_840, 0, 3_154, 3_871),
        ]
        with self.assertRaises(ValueError):
            sanity_check(rows, ceiling=100_000)


if __name__ == "__main__":
    unittest.main()
