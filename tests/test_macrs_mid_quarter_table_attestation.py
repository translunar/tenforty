"""Always-on pin: the two independent transcriptions of Pub 946 Appendix A
Tables A-2, A-3, A-4 and A-5 (mid-quarter convention, property placed in
service in the first, second, third and fourth quarter) must agree cell for
cell, with exact equality (no tolerance), and must agree on which cells are
blank. A disagreement is surfaced for human adjudication, never resolved by
editing the easier side.

One printed oddity is in both copies as printed: Table A-5's 15-year column
reads 5.90 for years 7, 8 and 9, where A-2..A-4 alternate 5.90 / 5.91."""
import unittest

from tenforty.params import macrs_mid_quarter as primary
from tests.params_attestations import macrs_mid_quarter_pub946 as second

CLASSES = (3, 5, 7, 10, 15, 20)
YEARS = range(1, 22)
# (primary table, second copy's rows, placement quarter)
TABLES = (
    ("TABLE_A_2", "A2_ROWS", 1),
    ("TABLE_A_3", "A3_ROWS", 2),
    ("TABLE_A_4", "A4_ROWS", 3),
    ("TABLE_A_5", "A5_ROWS", 4),
)
# The last recovery year each class's column prints.
LAST_YEAR = {3: 4, 5: 6, 7: 8, 10: 11, 15: 16, 20: 21}


def _from_rows(rows):
    """{class: {year: value}} from row tuples; None cells are blank."""
    out = {c: {} for c in CLASSES}
    for row in rows:
        year, cells = row[0], row[1:]
        assert len(cells) == len(CLASSES)
        for cls, value in zip(CLASSES, cells):
            if value is not None:
                assert year not in out[cls], f"duplicate year {year}"
                out[cls][year] = value
    return out


def _flat(table):
    return {(c, y): v for c, ys in table.items() for y, v in ys.items()}


def _blank(flat):
    return {(c, y) for c in CLASSES for y in YEARS} - set(flat)


class SourcesTests(unittest.TestCase):
    def test_both_sides_cite_sources(self):
        for side in (primary, second):
            with self.subTest(side=side.__name__):
                self.assertTrue(side.SOURCES)
                cited = " ".join(side.SOURCES)
                for needle in ("Publication 946", "2025", "A-2 (p. 71)",
                               "A-3 (p. 72)", "A-4 (p. 72)", "A-5 (p. 73)"):
                    self.assertIn(needle, cited)


class MidQuarterTablePinTests(unittest.TestCase):
    def test_class_sets_equal(self):
        for name, _rows, _quarter in TABLES:
            with self.subTest(table=name):
                self.assertEqual(set(getattr(primary, name)), set(CLASSES))

    def test_cells_exactly_equal(self):
        for name, rows, _quarter in TABLES:
            a = _flat(getattr(primary, name))
            b = _flat(_from_rows(getattr(second, rows)))
            self.assertEqual(set(a), set(b), name)
            for key in sorted(a):
                with self.subTest(table=name, cls=key[0], year=key[1]):
                    self.assertEqual(a[key], b[key])

    def test_blank_cell_sets_equal(self):
        for name, rows, _quarter in TABLES:
            with self.subTest(table=name):
                self.assertEqual(
                    _blank(_flat(getattr(primary, name))),
                    _blank(_flat(_from_rows(getattr(second, rows)))))

    def test_each_column_runs_from_year_one_to_its_last_year(self):
        for name, _rows, _quarter in TABLES:
            for cls, years in getattr(primary, name).items():
                with self.subTest(table=name, cls=cls):
                    self.assertEqual(
                        sorted(years), list(range(1, LAST_YEAR[cls] + 1)))

    def test_cells_are_plain_floats(self):
        for name, _rows, _quarter in TABLES:
            for key, value in _flat(getattr(primary, name)).items():
                with self.subTest(table=name, cell=key):
                    self.assertIs(type(value), float)


class QuarterIndexTests(unittest.TestCase):
    """What the engine reads: placement quarter -> that quarter's table."""

    def test_each_quarter_is_its_own_table(self):
        self.assertEqual(sorted(primary.TABLES_BY_QUARTER), [1, 2, 3, 4])
        for name, _rows, quarter in TABLES:
            with self.subTest(quarter=quarter):
                self.assertIs(
                    primary.TABLES_BY_QUARTER[quarter],
                    getattr(primary, name))

    def test_the_four_tables_differ(self):
        firsts = {primary.TABLES_BY_QUARTER[q][5][1] for q in (1, 2, 3, 4)}
        self.assertEqual(len(firsts), 4)


class CellCountTests(unittest.TestCase):
    def test_non_blank_cell_total(self):
        total = sum(
            len(_flat(getattr(primary, name))) for name, _r, _q in TABLES)
        self.assertEqual(total, 264)

    def test_second_copy_cell_total(self):
        total = sum(
            len(_flat(_from_rows(getattr(second, rows))))
            for _n, rows, _q in TABLES)
        self.assertEqual(total, 264)


if __name__ == "__main__":
    unittest.main()
