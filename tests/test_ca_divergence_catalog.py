"""Schema-gate and stability tests for the packaged CA divergence catalog.

These tests are the fail-closed contract for ``tenforty.ca_divergences``:
the packaged per-year YAML catalogs (``tenforty/params/california/divergences/
y<year>.yaml``) must load, validate, and remain id-stable across adjacent years.
"""

import os
import re
import tempfile
import unittest

from tenforty.ca_divergences import (
    CatalogDirection,
    CatalogEntry,
    CatalogError,
    load_catalog,
)

YEARS = (2021, 2022, 2023, 2024, 2025)

# kebab-case: lowercase alnum segments joined by single hyphens.
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Ids are user-facing and capped for accessibility (spec §2.2).
MAX_ID_LEN = 60

# The single documented string sentinel used for `pub1001_page` on the four
# wildfire-settlement rows in TY2021/TY2022 whose basis is a statute's
# retroactive window rather than a Pub 1001 page. Every OTHER row carries an int.
PUB1001_STRING_SENTINEL = "n/a (statute window, not Pub 1001)"

# The KNOWN Schedule CA (540) line-label set. Enumerated by hand from the five
# pre-packaging catalogs (the DISTINCT ``sch_ca_line`` values present across
# TY2021-2025) and frozen here as a literal. A future typo — any label not in
# this set — fails ``test_sch_ca_line_in_known_set``. Do NOT compute this set
# from the files under validation; it is intentionally hard-coded.
KNOWN_SCH_CA_LINES = frozenset(
    {
        "Part I §A 1a",
        "Part I §A 1d",
        "Part I §A 1e",
        "Part I §A 1h",
        "Part I §A 1i",
        "Part I §A 2",
        "Part I §A 3",
        "Part I §A 4",
        "Part I §A 5b",
        "Part I §A 7",
        "Part I §B 2a",
        "Part I §B 3",
        "Part I §B 4",
        "Part I §B 5",
        "Part I §B 6",
        "Part I §B 8a",
        "Part I §B 8b",
        "Part I §B 8c",
        "Part I §B 8d",
        "Part I §B 8e",
        "Part I §B 8f",
        "Part I §B 8k",
        "Part I §B 8n",
        "Part I §B 8o",
        "Part I §B 8p",
        "Part I §B 8z",
        "Part I §B 9b1",
        "Part I §B 9b2",
        "Part I §B 9b3",
        "Part I §C 11",
        "Part I §C 12",
        "Part I §C 13",
        "Part I §C 14",
        "Part I §C 15",
        "Part I §C 17",
        "Part I §C 19a",
        "Part I §C 20",
        "Part I §C 21",
        "Part I §C 24b",
        "Part I §C 24c",
        "Part I §C 24d",
        "Part I §C 24f",
        "Part I §C 24g",
        "Part I §C 24i",
        "Part I §C 24j",
        "Part II 11",
        "Part II 12",
        "Part II 13",
        "Part II 15",
        "Part II 16",
        "Part II 19",
        "Part II 20",
        "Part II 21",
        "Part II 27",
        "Part II 4",
        "Part II 5a",
        "Part II 5e",
        "Part II 6",
        "Part II 8",
        "Part II 9",
        "Sch D 540",
    }
)


class CatalogLoadTests(unittest.TestCase):
    """Every packaged year loads and yields a non-empty tuple of entries."""

    def test_each_year_loads_non_empty(self):
        for year in YEARS:
            with self.subTest(year=year):
                entries = load_catalog(year)
                self.assertIsInstance(entries, tuple)
                self.assertGreater(len(entries), 0)
                for entry in entries:
                    self.assertIsInstance(entry, CatalogEntry)


class SchemaGateTests(unittest.TestCase):
    """Per-year schema invariants enforced by the loader / asserted here."""

    def test_ids_unique_and_kebab(self):
        for year in YEARS:
            entries = load_catalog(year)
            ids = [e.id for e in entries]
            with self.subTest(year=year, check="unique"):
                self.assertEqual(len(ids), len(set(ids)))
            for entry in entries:
                with self.subTest(year=year, id=entry.id, check="kebab"):
                    self.assertRegex(entry.id, KEBAB_RE)
                # Ids are user-facing (typed in scenario YAML, named in refusal
                # messages, offered by did-you-mean) so they are capped at
                # MAX_ID_LEN chars for accessibility (spec §2.2).
                with self.subTest(year=year, id=entry.id, check="length"):
                    self.assertLessEqual(
                        len(entry.id),
                        MAX_ID_LEN,
                        f"id {entry.id!r} is {len(entry.id)} chars > {MAX_ID_LEN}",
                    )

    def test_sch_ca_line_in_known_set(self):
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    self.assertIn(entry.sch_ca_line, KNOWN_SCH_CA_LINES)

    def test_required_string_fields_non_empty(self):
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    for field in (
                        entry.sch_ca_line,
                        entry.section_title,
                        entry.description,
                        entry.ircrtc,
                    ):
                        self.assertIsInstance(field, str)
                        self.assertTrue(field.strip())
                    # pub1001_page is an int page number OR a documented
                    # non-empty string sentinel (see PUB1001_STRING_SENTINEL).
                    self.assertIsInstance(entry.pub1001_page, (int, str))
                    if isinstance(entry.pub1001_page, str):
                        self.assertTrue(entry.pub1001_page.strip())
                    else:
                        self.assertNotIsInstance(entry.pub1001_page, bool)
                    self.assertIsInstance(entry.common, bool)

    def test_pub1001_page_string_sentinel_is_the_only_non_int(self):
        # Pins reality: exactly the wildfire-settlement rows in 2021 & 2022 use
        # the documented string sentinel; every other row is an int. A stray
        # non-int page value (a typo) fails here.
        #
        # If a NEW row legitimately has no Pub 1001 page (its basis is a statute
        # window, not a page), extend this pin DELIBERATELY: add its year to the
        # expected set below and confirm its provenance header documents why it
        # is page-less. Do NOT casually reuse the "n/a (statute window, ...)"
        # sentinel for a row that merely happens to lack a page number — the
        # sentinel asserts a specific, documented reason, not "unknown".
        guidance = (
            "pub1001_page pin broke. Extend this pin deliberately for a NEW "
            "page-less row (add its year, document why in the provenance "
            "header); do NOT casually reuse the statute-window sentinel for a "
            "row that simply lacks a page."
        )
        sentinel_counts = {}
        for year in YEARS:
            for entry in load_catalog(year):
                if isinstance(entry.pub1001_page, str):
                    sentinel_counts[year] = sentinel_counts.get(year, 0) + 1
                    with self.subTest(year=year, id=entry.id):
                        self.assertEqual(
                            entry.pub1001_page, PUB1001_STRING_SENTINEL, guidance
                        )
                else:
                    with self.subTest(year=year, id=entry.id):
                        self.assertIsInstance(entry.pub1001_page, int, guidance)
        # Pin that ONLY those 8 rows use the sentinel: exactly 4 in 2021 and 4
        # in 2022, and no sentinel rows in any other year.
        self.assertEqual(sentinel_counts, {2021: 4, 2022: 4}, guidance)

    def test_direction_is_catalog_direction(self):
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    self.assertIsInstance(entry.direction, CatalogDirection)

    def test_auto_gate_mutual_exclusion(self):
        # Vacuous today (no auto/gate rows) — still a real gate.
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    self.assertFalse(entry.auto is not None and entry.gate)

    def test_auto_rows_not_both_direction(self):
        # Vacuous today — an auto rule needs a concrete direction.
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    if entry.auto is not None:
                        self.assertNotEqual(entry.direction, CatalogDirection.BOTH)

    def test_triggers_empty(self):
        for year in YEARS:
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    self.assertEqual(entry.triggers, ())

    def test_direction_totals_match_known_distribution(self):
        # Pins the real data: 296 Add / 314 Both / 402 Sub across five years.
        counts = {CatalogDirection.ADD: 0, CatalogDirection.BOTH: 0, CatalogDirection.SUB: 0}
        for year in YEARS:
            for entry in load_catalog(year):
                counts[entry.direction] += 1
        self.assertEqual(counts[CatalogDirection.ADD], 296)
        self.assertEqual(counts[CatalogDirection.BOTH], 314)
        self.assertEqual(counts[CatalogDirection.SUB], 402)


class ImportlibResourcesTests(unittest.TestCase):
    """The loader must resolve packaged data, not cwd-relative files."""

    def test_loads_when_cwd_is_not_repo_root(self):
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                entries = load_catalog(2025)
                self.assertGreater(len(entries), 0)
            finally:
                os.chdir(original)


class CrossYearStabilityTests(unittest.TestCase):
    """Same divergence -> same id across adjacent years (a real gate)."""

    @staticmethod
    def _key_to_ids(entries):
        mapping = {}
        for entry in entries:
            mapping.setdefault((entry.section_title, entry.description), []).append(entry.id)
        return {key: sorted(ids) for key, ids in mapping.items()}

    def test_adjacent_year_id_stability(self):
        for earlier, later in zip(YEARS, YEARS[1:]):
            a = self._key_to_ids(load_catalog(earlier))
            b = self._key_to_ids(load_catalog(later))
            for key in set(a) & set(b):
                with self.subTest(pair=(earlier, later), section=key[0]):
                    self.assertEqual(a[key], b[key])


class FailClosedTests(unittest.TestCase):
    """Missing file or malformed YAML raises CatalogError."""

    def test_missing_file_raises(self):
        with self.assertRaises(CatalogError):
            load_catalog(9999)

    def test_malformed_yaml_raises(self):
        import tenforty.ca_divergences as mod

        original = mod._read_catalog_text
        try:
            mod._read_catalog_text = lambda year: "- id: [unterminated\n  bad: :"
            with self.assertRaises(CatalogError):
                load_catalog(2025)
        finally:
            mod._read_catalog_text = original

    def test_non_list_yaml_raises(self):
        import tenforty.ca_divergences as mod

        original = mod._read_catalog_text
        try:
            mod._read_catalog_text = lambda year: "just_a_mapping: true"
            with self.assertRaises(CatalogError):
                load_catalog(2025)
        finally:
            mod._read_catalog_text = original


if __name__ == "__main__":
    unittest.main()
