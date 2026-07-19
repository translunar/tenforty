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
        # Bucket-D line move (adjudication 2026-07-19): §179A clean-fuel-vehicle
        # deduction prints at Part I, line 26, column B in FTB Pub 1001 (2025 ed.).
        "Part I line 26",
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
        # 2025 CONTENT-AUDIT: CA itemized-deduction phaseout (Sch CA Part II
        # line 29, Itemized Deductions Worksheet), instructions-sourced.
        "Part II 29",
        "Part II 4",
        "Part II 5a",
        "Part II 5e",
        "Part II 6",
        "Part II 8",
        "Part II 9",
        "Sch D 540",
    }
)

# The nine still-operative TY2025 rows found in NEITHER 2025 source (FTB Pub 1001
# 2025 edition NOR the 2025 Schedule CA (540) instructions). Ruled by the
# CONTENT-AUDIT (adjudication 2026-07-19): keep the rows (Pub 1001 is
# self-described non-exhaustive, so absence is not proof of conformity), re-cite
# each to its 2024-edition Pub page with an explicit "absent from 2025 edition"
# note, and pin the SET here as a frozenset literal so every future year-port
# re-examines them. §1031 is additionally Sch-D-540-routed (instructions-absence
# is expected there; only Pub-edition presence is meaningful future evidence).
UNSOURCED_IN_CURRENT_EDITION_2025 = frozenset(
    {
        "business-interest-cap-30-ati-federal-tcja-ca-doesn-t",
        "sexual-harassment-nda-legal-fees-disallowed-federally-ca",
        "msa-distributions-for-menstrual-care-ca-doesn-t-conform",
        "deferral-election-for-qualified-equity-grants-83-i-tcja",
        "tcja-eliminated-3k-members-of-congress-living-expense",
        "repealed-federal-age-70-traditional-ira-cap-secure-ca",
        "indexed-1-000-catch-up-and-expanded-age-50-caa-2023-ca",
        "college-athletic-seating-rights-disallowed-federally-tcja",
        "1031-exchange-federal-limited-to-real-property-ca",
    }
)

# The marker phrase every `unsourced-in-current-edition` recitation carries in
# its source_citation (and that NO other row carries).
_UNSOURCED_MARKER = "absent from 2025 edition"


class UnsourcedInCurrentEditionTests(unittest.TestCase):
    """Pin the 2025 `unsourced-in-current-edition` keep-set (real gate).

    These rows are absent from both 2025 sources but kept and re-cited; the pin
    both fixes the exact membership and asserts the recitation shape, so a future
    port that silently drops, re-pages, or mis-cites one of them fails here.
    """

    def test_pinned_set_present_and_recited(self):
        entries = {e.id: e for e in load_catalog(2025)}
        for uid in UNSOURCED_IN_CURRENT_EDITION_2025:
            with self.subTest(id=uid):
                self.assertIn(uid, entries)
                entry = entries[uid]
                # Absent from the 2025 Pub edition -> no 2025 page.
                self.assertIsNone(entry.pub1001_page)
                # Re-cited to the 2024-edition page with the absence note.
                self.assertIsInstance(entry.source_citation, str)
                self.assertIn(_UNSOURCED_MARKER, entry.source_citation)

    def test_marker_phrase_pins_exactly_the_set(self):
        # The recitation marker appears on EXACTLY these nine ids — no more, no
        # fewer. Guards against a new keep being added without updating the pin,
        # or an instructions-sourced row accidentally borrowing the phrasing.
        recited = {
            e.id
            for e in load_catalog(2025)
            if e.source_citation and _UNSOURCED_MARKER in e.source_citation
        }
        self.assertEqual(recited, UNSOURCED_IN_CURRENT_EDITION_2025)


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
                    # pub1001_page is an int page number, a documented non-empty
                    # string sentinel (see PUB1001_STRING_SENTINEL), OR null for
                    # instructions-sourced / unsourced-in-current-edition rows
                    # (2025 CONTENT-AUDIT). A null page MUST carry a non-empty
                    # source_citation — the loader's at-least-one-source gate.
                    self.assertIsInstance(entry.pub1001_page, (int, str, type(None)))
                    if isinstance(entry.pub1001_page, str):
                        self.assertTrue(entry.pub1001_page.strip())
                    elif entry.pub1001_page is None:
                        self.assertIsInstance(entry.source_citation, str)
                        self.assertTrue(entry.source_citation.strip())
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
                page = entry.pub1001_page
                if isinstance(page, str):
                    sentinel_counts[year] = sentinel_counts.get(year, 0) + 1
                    with self.subTest(year=year, id=entry.id):
                        self.assertEqual(page, PUB1001_STRING_SENTINEL, guidance)
                elif page is None:
                    # Instructions-sourced rows and the `unsourced-in-current-
                    # edition` keeps (2025 CONTENT-AUDIT) carry a null page and
                    # MUST supply a non-empty source_citation — the real
                    # at-least-one-source gate the loader enforces. A null page
                    # is NOT the statute-window sentinel; it does not count here.
                    with self.subTest(year=year, id=entry.id):
                        self.assertTrue(
                            isinstance(entry.source_citation, str)
                            and bool(entry.source_citation.strip()),
                            "a null pub1001_page requires a non-empty "
                            "source_citation",
                        )
                else:
                    with self.subTest(year=year, id=entry.id):
                        self.assertIsInstance(page, int, guidance)
        # Pin that ONLY those 8 rows use the STRING sentinel: exactly 4 in 2021
        # and 4 in 2022, and no sentinel rows in any other year. (Null pages,
        # introduced by the 2025 CONTENT-AUDIT, are a distinct case handled
        # above and are deliberately NOT the statute-window sentinel.)
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
        # Pins the real data across five years. Re-pinned by the 2025
        # CONTENT-AUDIT (adjudication 2026-07-19): from 296/314/402 to
        # 299/320/404. Net TY2025 delta = +3 Add, +6 Both, +2 Sub (8 direction
        # flips are net-zero reassignments; 3 drops = -3 Sub; 14 adds = +3 Add,
        # +5 Both, +6 Sub).
        counts = {CatalogDirection.ADD: 0, CatalogDirection.BOTH: 0, CatalogDirection.SUB: 0}
        for year in YEARS:
            for entry in load_catalog(year):
                counts[entry.direction] += 1
        self.assertEqual(counts[CatalogDirection.ADD], 299)
        self.assertEqual(counts[CatalogDirection.BOTH], 320)
        self.assertEqual(counts[CatalogDirection.SUB], 404)


class SourceCitationSchemaTests(unittest.TestCase):
    """`source_citation` field + the at-least-one-source fail-closed gate.

    Real catalog rows do not exercise these paths yet (every packaged row still
    carries an int/sentinel `pub1001_page` and no `source_citation`), so these
    tests drive the loader through a monkeypatched raw YAML document.
    """

    _FAKE_YEAR = 4242

    def _load_rows(self, body: str):
        import tenforty.ca_divergences as mod

        original = mod._read_catalog_text
        try:
            mod._read_catalog_text = lambda year: body
            return load_catalog(self._FAKE_YEAR)
        finally:
            mod._read_catalog_text = original

    def test_null_page_with_citation_loads(self):
        body = (
            "- id: cited-row\n"
            '  sch_ca_line: "Part I §A 1a"\n'
            '  section_title: "Instructions-sourced divergence"\n'
            '  description: "Documented only in the Sch CA (540) instructions"\n'
            "  direction: Add\n"
            "  common: false\n"
            "  pub1001_page: null\n"
            '  ircrtc: "R&TC 17131"\n'
            '  source_citation: "2025 Sch CA (540) instructions, line 8z"\n'
        )
        entries = self._load_rows(body)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0].pub1001_page)
        self.assertEqual(
            entries[0].source_citation,
            "2025 Sch CA (540) instructions, line 8z",
        )

    def test_page_without_citation_loads_backcompat(self):
        body = (
            "- id: paged-row\n"
            '  sch_ca_line: "Part I §A 1a"\n'
            '  section_title: "Pub 1001 sourced divergence"\n'
            '  description: "Today\'s rows: a page and no citation"\n'
            "  direction: Sub\n"
            "  common: true\n"
            "  pub1001_page: 7\n"
            '  ircrtc: "R&TC 17131"\n'
        )
        entries = self._load_rows(body)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].pub1001_page, 7)
        self.assertIsNone(entries[0].source_citation)

    def test_no_source_raises(self):
        body = (
            "- id: sourceless-row\n"
            '  sch_ca_line: "Part I §A 1a"\n'
            '  section_title: "No source at all"\n'
            '  description: "Neither a page nor a citation"\n'
            "  direction: Both\n"
            "  common: false\n"
            "  pub1001_page: null\n"
            '  ircrtc: "R&TC 17131"\n'
        )
        with self.assertRaises(CatalogError) as ctx:
            self._load_rows(body)
        message = str(ctx.exception)
        self.assertIn("no source", message)
        self.assertIn("sourceless-row", message)

    def test_empty_citation_with_null_page_raises(self):
        body = (
            "- id: empty-citation-row\n"
            '  sch_ca_line: "Part I §A 1a"\n'
            '  section_title: "Empty citation is not a source"\n'
            '  description: "Blank source_citation must not satisfy the gate"\n'
            "  direction: Add\n"
            "  common: false\n"
            "  pub1001_page: null\n"
            '  ircrtc: "R&TC 17131"\n'
            '  source_citation: "   "\n'
        )
        with self.assertRaises(CatalogError):
            self._load_rows(body)


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
