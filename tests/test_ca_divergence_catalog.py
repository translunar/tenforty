"""Schema-gate and stability tests for the packaged CA divergence catalog.

These tests are the fail-closed contract for ``tenforty.ca_divergences``:
the packaged per-year YAML catalogs (``tenforty/params/california/divergences/
y<year>.yaml``) must load, validate, and remain id-stable across adjacent years.
"""

import dataclasses
import os
import re
import tempfile
import unittest

from tenforty import models
from tenforty.ca_divergences import (
    TRIGGER_PREDICATES,
    CatalogDirection,
    CatalogEntry,
    CatalogError,
    load_catalog,
)
from tenforty.forms import sch_1 as form_sch_1
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR

YEARS = (2021, 2022, 2023, 2024, 2025)

# The team-lead-ruled trigger/gate assignments (2026-07-19). Each maps a catalog
# id to its EXACT (triggers, gate) pair; these four ids carry them in ALL FIVE
# years and NO OTHER row carries a non-empty `triggers` or `gate: true`. Pinned
# by `test_ruled_trigger_gate_assignments`.
RULED_TRIGGER_GATE_ASSIGNMENTS = {
    "out-of-state-muni-interest-excluded-federally-ca-taxes": (
        ("has_tax_exempt_interest",),
        True,
    ),
    "mutual-fund-muni-interest-federal-fully-excludes-ca-only": (
        ("has_tax_exempt_interest",),
        False,
    ),
    "federal-k-1-items-differ-from-ca-k-1-ca-k-1-required": (
        ("has_k1",),
        False,
    ),
    "ric-undistributed-cap-gain-form-2439-federal-in-year": (
        ("has_capital_gain_distributions",),
        False,
    ),
}

# kebab-case: lowercase alnum segments joined by single hyphens.
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Ids are user-facing and capped for accessibility (spec §2.2).
MAX_ID_LEN = 60

# The single documented string sentinel used for `pub1001_page` on the four
# wildfire-settlement rows in TY2021/TY2022 whose basis is a statute's
# retroactive window rather than a Pub 1001 page. Every OTHER row carries an int.
PUB1001_STRING_SENTINEL = "n/a (statute window, not Pub 1001)"

# The KNOWN Schedule CA (540) line-label set, PER YEAR. Enumerated by hand from
# the five pre-packaging catalogs (the DISTINCT ``sch_ca_line`` values present
# across TY2021-2025) and frozen here as literals. A future typo — any label not
# in that year's set — fails ``test_sch_ca_line_in_known_set``. Do NOT compute
# these sets from the files under validation; they are intentionally hard-coded.
#
# The gate is per-year because Schedule CA (540) line labels are YEAR-SCOPED: the
# form edition, its §B-8 sub-letters, and which lines a given credit/adjustment
# prints on drift across editions, so a label correct for one year can be wrong
# for another. ``_COMMON_SCH_CA_LINES`` holds the labels present in ALL five
# years; ``_YEAR_SPECIFIC_SCH_CA_LINES`` pins the per-year extras (labels NOT
# common to every year), and ``known_lines_for(year)`` unions the two. The
# reverse gate ``test_year_specific_lines_are_actually_used`` confirms each
# year-specific label is really used by a row that year (so stale extras rot
# loudly) — reading the catalog to confirm USAGE is allowed; computing the
# ALLOWED set from the catalog is not.
_COMMON_SCH_CA_LINES = frozenset(
    {
        "Part I §A 1a",
        "Part I §A 1d",
        "Part I §A 1h",
        "Part I §A 1i",
        "Part I §A 2",
        "Part I §A 3",
        "Part I §A 4",
        "Part I §A 5b",
        # §A 6 / §B 1 / §B 7 entered the common set with the Part AUTO migration:
        # the five auto-derived exclusions (SS §A 6, state refund §B 1, UI + PFL
        # §B 7) — formerly synthesized from hardcoded kernel tuples — are now real
        # `auto:` catalog rows present in ALL five years (§A 5b RRB was already
        # common). See the "AUTO ROWS (Part AUTO)" block at each catalog's tail.
        "Part I §A 6",
        "Part I §A 7",
        "Part I §B 1",
        "Part I §B 2a",
        "Part I §B 3",
        "Part I §B 5",
        "Part I §B 6",
        "Part I §B 7",  # Part AUTO: UI + PFL auto rows (see §A 6 note above)
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

# The year-scoped extras: labels NOT common to all five years, pinned per year.
# - "Part I §B 4": carried in 2022-2024, dropped by the 2025 edition. VACATED in
#   2021 by the full re-enum (adjudication 2026-07-19): §179A clean-fuel moved to
#   "Part I line 26" (its only user), so 2021 no longer carries §B 4.
# - "Part I §C 24c": carried in 2021-2024, dropped by the 2025 edition.
# - "Part I line 26": Bucket-D line move — §179A clean-fuel-vehicle deduction
#   prints at Part I, line 26, column B (2025 edition; and the 2021 re-enum).
# - "Part II 29": 2025 CONTENT-AUDIT — CA itemized-deduction phaseout (Sch CA
#   Part II line 29, Itemized Deductions Worksheet), instructions-sourced.
# 2021 full re-enum (adjudication 2026-07-19) introduces these 2021-only labels:
# - "Part I line 1": §A line-1 sub-letter anachronism swept to the single
#   un-lettered 2021 "line 1" (15 rows). "Part I §A 1e" is vacated by the same
#   sweep (its only user moved to line 1), so it is dropped from the 2021 set.
# - "Part I §B 8m": §B-8 numbering shift — 2021 edition numbers §951(a) at 8m.
# - "Part I §B 9b4": Bucket-A add — student-loan for-profit-closure discharge.
# - "Part II 8d": Bucket-A add — mortgage insurance premiums.
# - "Schedule D-1": form-label sweep — 2021 edition routes the three basis/1031/
#   CARS "Sch D 540" rows to Schedule D-1 (Other Gains/Losses).
# 2022 full re-enum (adjudication 2026-07-19) — SIMPLER than 2021 (no §A line-1
# anachronism, no §B-8 shift):
# - "Part I §B 4" is VACATED for 2022: §179A clean-fuel (its only 2022 user) moves
#   to "Part I line 26", so 2022 no longer carries §B 4.
# - "Part I line 26": §179A clean-fuel-vehicle deduction (2022 Pub 1001 line 26).
# - "Schedule D-1": form-label sweep — the three basis/1031/CARS "Sch D 540" rows
#   route to Schedule D-1 (Other Gains/Losses) in the 2022 edition.
# 2023 full re-enum (adjudication 2026-07-19) — cleanest year (mirrors 2022; no
# §A line-1 anachronism, no §B-8 shift):
# - "Part I §B 4" is VACATED for 2023: §179A clean-fuel (its only 2023 user) moves
#   to "Part I line 26", so 2023 no longer carries §B 4.
# - "Part I line 26": §179A clean-fuel-vehicle deduction (2023 Pub 1001 line 26).
# - "Schedule D-1": form-label sweep — the three basis/1031/CARS "Sch D 540" rows
#   route to Schedule D-1 (Other Gains/Losses) in the 2023 edition.
_YEAR_SPECIFIC_SCH_CA_LINES = {
    2021: frozenset(
        {
            "Part I §C 24c",
            "Part I line 1",
            "Part I line 26",
            "Part I §B 8m",
            "Part I §B 9b4",
            "Part II 8d",
            "Schedule D-1",
        }
    ),
    2022: frozenset(
        {
            "Part I §C 24c",
            "Part I line 26",
            "Schedule D-1",
        }
    ),
    2023: frozenset(
        {
            "Part I §C 24c",
            "Part I line 26",
            "Schedule D-1",
        }
    ),
    2024: frozenset({"Part I §B 4", "Part I §C 24c"}),
    2025: frozenset({"Part I line 26", "Part II 29"}),
}


def known_lines_for(year):
    """The allowed ``sch_ca_line`` labels for ``year``: the common set unioned
    with that year's year-specific extras. Hard-coded literals only — never
    derived from the catalog under validation."""
    return _COMMON_SCH_CA_LINES | _YEAR_SPECIFIC_SCH_CA_LINES[year]

# The `unsourced-in-current-edition` keep-sets, PER YEAR. Each year pins the
# operative rows found in NEITHER of that year's own sources: they are KEPT (Pub
# 1001 is self-described non-exhaustive, so absence is not proof of conformity),
# given a null pub1001_page, and re-cited with a source_citation carrying that
# year's OWN "absent from <year> edition" marker. Pinned here as frozenset
# literals so every future year-port re-examines them.
#
# 2025 (CONTENT-AUDIT, adjudication 2026-07-19): the nine TY2025 rows absent from
# both the 2025 Pub 1001 edition AND the 2025 Schedule CA (540) instructions;
# each re-cited to its 2024-edition Pub page. §1031 is additionally
# Sch-D-540-routed (instructions-absence is expected there; only Pub-edition
# presence is meaningful future evidence).
#
# 2021 (Stage-1 back-year batch, adjudication 2026-07-19): the film/TV §181
# current-expensing row is carried in the 2021 catalog, but the 2021 Pub edition
# does not describe §181; ruled a KEEP recited as unsourced-in-2021-edition
# (direction basis = the 2022-edition read), null page + "absent from 2021
# edition" marker.
UNSOURCED_IN_CURRENT_EDITION = {
    2021: frozenset(
        {
            "film-tv-current-expensing-pre-1-1-2026-ca-doesn-t-conform",
            "msa-distributions-for-menstrual-care-ca-doesn-t-conform",
            "conservation-easement-federal-50-agi-ca-30-agi",
            "conservation-easement-carryover-federal-15-yr-ca-5-yr",
        }
    ),
    # 2022 (full re-enum, adjudication 2026-07-19): three operative rows absent
    # from both 2022 sources, KEPT and re-cited unsourced-in-2022-edition:
    # guaranteed-income-pilot (R&TC 17131.12 statute-window exclusion opened
    # 6/30/2022, genuinely absent from the 2022 Pub — was carrying a WRONG page
    # 19) + the two conservation-easement sub-rules (re-cited to the 2023 page).
    2022: frozenset(
        {
            "guaranteed-income-pilot-payments-ca-other-income-2",
            "conservation-easement-federal-50-agi-ca-30-agi",
            "conservation-easement-carryover-federal-15-yr-ca-5-yr",
        }
    ),
    # 2023 (full re-enum, adjudication 2026-07-19): three operative rows absent
    # from the 2023 Pub edition, KEPT and re-cited unsourced-in-2023-edition:
    # the two conservation-easement sub-rules (re-cited to the 2024 page) + the
    # DTRA wildfire-relief row (re-cited to the 2025 edition p.18 that carries
    # it — the Disaster Tax Relief Act was named 2023 but ENACTED 12/12/2024,
    # retroactive to TY2023, so the 2023 Pub could not describe it).
    2023: frozenset(
        {
            "conservation-easement-federal-50-agi-ca-30-agi",
            "conservation-easement-carryover-federal-15-yr-ca-5-yr",
            "qualified-wildfire-relief-payments-excluded-federally",
        }
    ),
    2025: frozenset(
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
    ),
}

# The marker phrase each year's recitation carries in its source_citation (and
# that NO other row in that year carries). Each year names its OWN edition, so
# the pin stays a real gate against a mis-yeared recitation.
_UNSOURCED_MARKER = {
    2021: "absent from 2021 edition",
    2022: "absent from 2022 edition",
    2023: "absent from 2023 edition",
    2025: "absent from 2025 edition",
}


class UnsourcedInCurrentEditionTests(unittest.TestCase):
    """Pin the 2025 `unsourced-in-current-edition` keep-set (real gate).

    These rows are absent from both 2025 sources but kept and re-cited; the pin
    both fixes the exact membership and asserts the recitation shape, so a future
    port that silently drops, re-pages, or mis-cites one of them fails here.
    """

    def test_pinned_set_present_and_recited(self):
        for year, ids in UNSOURCED_IN_CURRENT_EDITION.items():
            entries = {e.id: e for e in load_catalog(year)}
            marker = _UNSOURCED_MARKER[year]
            for uid in ids:
                with self.subTest(year=year, id=uid):
                    self.assertIn(uid, entries)
                    entry = entries[uid]
                    # Absent from that year's Pub edition -> no page.
                    self.assertIsNone(entry.pub1001_page)
                    # Re-cited with the absence note for that year's own edition.
                    self.assertIsInstance(entry.source_citation, str)
                    self.assertIn(marker, entry.source_citation)

    def test_marker_phrase_pins_exactly_the_set(self):
        # Each year's recitation marker appears on EXACTLY that year's pinned ids
        # — no more, no fewer. Guards against a new keep being added without
        # updating the pin, an instructions-sourced row borrowing the phrasing,
        # or a recitation citing the wrong year's edition.
        for year, ids in UNSOURCED_IN_CURRENT_EDITION.items():
            marker = _UNSOURCED_MARKER[year]
            recited = {
                e.id
                for e in load_catalog(year)
                if e.source_citation and marker in e.source_citation
            }
            with self.subTest(year=year):
                self.assertEqual(recited, ids)


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
            allowed = known_lines_for(year)
            for entry in load_catalog(year):
                with self.subTest(year=year, id=entry.id):
                    self.assertIn(entry.sch_ca_line, allowed)

    def test_year_specific_lines_are_actually_used(self):
        # Reverse gate: every year-specific extra MUST appear on at least one row
        # in that year's catalog, so a stale/typo'd per-year label rots loudly
        # instead of silently widening the gate. (Reading the catalog to confirm
        # USAGE is allowed; computing the ALLOWED set from the catalog is not.)
        for year in YEARS:
            used = {entry.sch_ca_line for entry in load_catalog(year)}
            for label in _YEAR_SPECIFIC_SCH_CA_LINES[year]:
                with self.subTest(year=year, label=label):
                    self.assertIn(
                        label,
                        used,
                        f"year-specific label {label!r} is unused in TY{year}",
                    )

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
        sentinel_ids = {}
        for year in YEARS:
            for entry in load_catalog(year):
                page = entry.pub1001_page
                if isinstance(page, str):
                    sentinel_counts[year] = sentinel_counts.get(year, 0) + 1
                    sentinel_ids.setdefault(year, set()).add(entry.id)
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
        # Pin that ONLY these rows use the STRING sentinel: exactly 2 in 2021
        # (Kincade + Zogg) and NONE in any other year. The 2021 full re-enum
        # (adjudication 2026-07-19) found Fire Victims Trust and Thomas/Woolsey
        # ARE listed in the currently-posted 2021 Pub 1001 (REV 07-25, p17) —
        # source-of-record drift — so those two rows drop the sentinel for the
        # real page 17; only Kincade + Zogg (individually unlisted; statute-window
        # basis) keep it. The 2022 full re-enum (adjudication 2026-07-19) then
        # resolved ALL FOUR 2022 fire rows: the currently-posted 2022 Pub 1001
        # lists Kincade+Zogg at p17 and Fire-Victims-Trust+Thomas/Woolsey at p18,
        # so all four re-cite to real pages and 2022's sentinel collapses to ZERO
        # (no 2022 key). Guaranteed-income-pilot — genuinely absent from the 2022
        # edition — is represented as an UNSOURCED-RECITE (null page + citation),
        # NOT the statute-window sentinel. (Null pages, introduced by the 2025
        # CONTENT-AUDIT, are a distinct case handled above and are deliberately
        # NOT the sentinel.)
        self.assertEqual(sentinel_counts, {2021: 2}, guidance)
        # Identity pin (not just count): the two 2021 string sentinels are
        # EXACTLY Kincade + Zogg. A future swap that kept the count at 2 with a
        # different pair would pass the count check above but trip this.
        self.assertEqual(
            sentinel_ids.get(2021, set()),
            {
                "kincade-fire-2019-pg-and-e-settlement-ca-excludes-no",
                "zogg-fire-2020-pg-and-e-settlement-ca-excludes-no-federal",
            },
            guidance,
        )

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

    def test_triggers_in_registry(self):
        # Membership gate: every trigger name on every row (all years) must be a
        # key of the closed TRIGGER_PREDICATES registry.
        for year in YEARS:
            for entry in load_catalog(year):
                for name in entry.triggers:
                    with self.subTest(year=year, id=entry.id, trigger=name):
                        self.assertIn(name, TRIGGER_PREDICATES)

    def test_ruled_trigger_gate_assignments(self):
        # Pins the ruled set EXACTLY: the four ruled ids carry exactly their
        # ruled triggers tuple + gate value in ALL FIVE years, and NO OTHER row
        # in any year carries a non-empty `triggers` or `gate: true` (a stray
        # future assignment fails here).
        for year in YEARS:
            by_id = {entry.id: entry for entry in load_catalog(year)}
            for rid, (triggers, gate) in RULED_TRIGGER_GATE_ASSIGNMENTS.items():
                with self.subTest(year=year, id=rid):
                    self.assertIn(rid, by_id)
                    self.assertEqual(by_id[rid].triggers, triggers)
                    self.assertEqual(by_id[rid].gate, gate)
            for entry in by_id.values():
                if entry.id in RULED_TRIGGER_GATE_ASSIGNMENTS:
                    continue
                with self.subTest(year=year, id=entry.id):
                    self.assertEqual(entry.triggers, ())
                    self.assertFalse(entry.gate)

    def test_direction_totals_match_known_distribution(self):
        # Pins the real data across five years. Re-pinned by the 2023 full
        # re-enumeration reconciliation (adjudication 2026-07-19): from
        # 299/341/402 to 300/344/403. Net delta = Add +1, Both +3, Sub +1
        # (row count +5: -2 drops + 7 adds, all in 2023), reconciled as:
        #   Bucket C direction changes: NONE (2023 has no direction changes).
        #   Drops (2023, both were Sub): merchant-seamen nonresident wages (540NR
        #     scope) + §414(v) CAA-2023 catch-up (TY2024+ anachronism): Sub -2.
        #   Bucket-A adds x4: Sub +2, Both +1, Add +1
        #     (student-loan-closure/generic-wildfire = Sub; enhanced-oil = Both;
        #      conservation-easement 2.5x SECURE-2.0 = Add)
        #   Cross-source net-new adds x3: Both +2, Sub +1
        #     (Coverdell-diff/parents-election = Both; forest-landowner = Sub;
        #      directions mirror the 2021/2022 ruled analogues)
        #   The DTRA wildfire-relief row is KEPT (unsourced-recite), direction
        #     unchanged at Add -> no direction delta.
        #   Sum: Add +1, Both +3, Sub +1 (Sub: +2 adds +1 cross-source -2 drops).
        #
        # Re-pinned again by the CONTENT-AUDIT CLOSE-OUT (adjudication 2026-07-19):
        # 300/344/403 -> 300/344/399. Net delta = Sub -4, Add/Both unchanged.
        #   The merchant-seamen nonresident-wages row (a Schedule CA (540NR)
        #   nonresident-only item, 46 USC 11108; scope-class, year-independent) was
        #   dropped from the four remaining years that still carried it (2021 "Part
        #   I line 1"; 2022/2024/2025 "§A 1a") — already gone from 2023 since its
        #   2023 full re-enum. All four dropped rows were direction Sub => Sub -4.
        #
        # Re-pinned by the Part AUTO migration (2026-07-19): 300/344/399 ->
        # 300/344/424. The five auto-derived exclusions (UI, SS, state refund,
        # RRB, PFL) — formerly synthesized from the kernel's hardcoded tuples and
        # thus absent from the catalog census — became REAL catalog `auto:` rows,
        # 5 per year x 5 years = 25 new rows, ALL direction Sub (auto rows are
        # subtractions). Net delta: Sub +25 (Add/Both unchanged). Catalog
        # bookkeeping for a deliberate, behavior-preserving row addition, NOT a
        # divergence-content change: the emitted divergences (amount/line/
        # direction) are byte-for-byte identical to the pre-migration tuples.
        #
        # Re-pinned by the C-FRAME moving-expense direction ruling (2026-07-19):
        # 300/344/424 -> 306/344/418. Overturned ruling #1 (BOTH moving rows are
        # ADDITIONs): the moving-expense §A (wages "Part I §A 1h"; 2021 "Part I
        # line 1") and §C ("Part I §C 14") rows carry direction=Add in every
        # year. 2021/2022 were already Add; the 2023/2024/2025 pairs (6 rows)
        # flipped Sub->Add. Net delta: Add +6, Sub -6 (Both unchanged).
        counts = {CatalogDirection.ADD: 0, CatalogDirection.BOTH: 0, CatalogDirection.SUB: 0}
        for year in YEARS:
            for entry in load_catalog(year):
                counts[entry.direction] += 1
        self.assertEqual(counts[CatalogDirection.ADD], 306)
        self.assertEqual(counts[CatalogDirection.BOTH], 344)
        self.assertEqual(counts[CatalogDirection.SUB], 418)


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

    def test_unknown_trigger_name_raises(self):
        # The membership gate: a `triggers` name absent from TRIGGER_PREDICATES
        # is a fail-closed CatalogError naming the row and the bad name.
        body = (
            "- id: bad-trigger-row\n"
            '  sch_ca_line: "Part I §A 1a"\n'
            '  section_title: "Row with an unknown trigger"\n'
            '  description: "triggers naming a predicate not in the registry"\n'
            "  direction: Add\n"
            "  common: false\n"
            "  pub1001_page: 7\n"
            '  ircrtc: "R&TC 17131"\n'
            '  triggers: ["has_not_a_real_predicate"]\n'
        )
        with self.assertRaises(CatalogError) as ctx:
            self._load_rows(body)
        message = str(ctx.exception)
        self.assertIn("has_not_a_real_predicate", message)
        self.assertIn("bad-trigger-row", message)

    def test_known_trigger_name_loads(self):
        # A `triggers` name that IS in the registry loads and round-trips.
        body = (
            "- id: good-trigger-row\n"
            '  sch_ca_line: "Part I §A 2"\n'
            '  section_title: "Row with a known trigger"\n'
            '  description: "triggers naming a predicate in the registry"\n'
            "  direction: Add\n"
            "  common: false\n"
            "  pub1001_page: 7\n"
            '  ircrtc: "R&TC 17131"\n'
            '  triggers: ["has_tax_exempt_interest"]\n'
        )
        entries = self._load_rows(body)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].triggers, ("has_tax_exempt_interest",))


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


# ── Part AUTO: auto-row presence + resolvability gate ─────────────────────────
# The five auto-derived exclusions migrated from the kernel's hardcoded tuples
# (forms/sch_ca.py) into real catalog `auto:` rows. Pinned here: exact per-year
# membership (shape/id/line/direction/key) + the NEW resolvability gate — every
# auto row's `federal_key` resolves to a real federal-pipeline output key, and
# every `ca540_field` names a real CA540Return dataclass field. A typo in either
# rots loudly instead of silently firing (or not firing) at compute time.

# (id, sch_ca_line, direction, auto-kind, auto-target). Identical across all five
# years (descriptions/lines are FROZEN); pub1001_page is the only per-year field
# and is NOT pinned here (it does not affect compute; it is a citation).
EXPECTED_AUTO_ROWS = {
    "unemployment-compensation-ca-excludes-rtc-17083":
        ("Part I §B 7", CatalogDirection.SUB, "federal_key", "sch_1_line_7_unemployment"),
    "social-security-benefits-ca-excludes-rtc-17087":
        ("Part I §A 6", CatalogDirection.SUB, "federal_key", "social_security_taxable"),
    "state-income-tax-refund-not-taxed-ca-rtc-17131":
        ("Part I §B 1", CatalogDirection.SUB, "federal_key", "sch_1_line_1_taxable_refunds"),
    "railroad-retirement-tier-1-2-ca-excludes-rtc-17087":
        ("Part I §A 5b", CatalogDirection.SUB, "ca540_field", "rrb_tier_1_2_amount"),
    "paid-family-leave-benefits-ca-excludes-ftb-pub-1001":
        ("Part I §B 7", CatalogDirection.SUB, "ca540_field", "pfl_amount"),
}


def _computed_federal_reference_keys(year):
    """Keys the federal pipeline is known to emit, for `federal_key` resolvability.

    Soffice-free by construction:
    - Schedule-1-sourced keys (unemployment, state refund) come from a REAL
      native compute (`sch_1.compute`) over reference fixtures — the same
      federal-pipeline stage that feeds the Sch CA kernel at runtime.
    - Taxable Social Security (1040 line 6b, `social_security_taxable`) has no
      native producer in v1 (it is emitted only by the LibreOffice workbook
      engine, and there is no SS input fixture), so it is validated against the
      DECLARED 1040 output surface — the keys the Form 1040 PDF mapping consumes,
      which by construction are federal-pipeline output keys. This keeps the gate
      a real typo-catcher without launching soffice.
    """
    keys = set()
    for fixture in ("unemployment_withholding.yaml", "state_refund_benefit_rule.yaml"):
        scenario = load_scenario(FIXTURES_DIR / fixture)
        keys |= set(form_sch_1.compute(scenario, upstream={}))
    keys |= set(Pdf1040.get_mapping(year))
    return keys


class AutoRowMigrationTests(unittest.TestCase):
    """Pin the migrated `auto:` rows (5 per year) and their resolvability."""

    def test_each_year_has_exactly_the_expected_auto_rows(self):
        for year in YEARS:
            auto = {e.id: e for e in load_catalog(year) if e.auto is not None}
            with self.subTest(year=year):
                self.assertEqual(
                    set(auto), set(EXPECTED_AUTO_ROWS),
                    f"TY{year} auto-row id set drifted from the migrated 5",
                )
            for row_id, (line, direction, kind, target) in EXPECTED_AUTO_ROWS.items():
                with self.subTest(year=year, id=row_id):
                    entry = auto[row_id]
                    self.assertEqual(entry.sch_ca_line, line)
                    self.assertEqual(entry.direction, direction)
                    if kind == "federal_key":
                        self.assertEqual(entry.auto.federal_key, target)
                        self.assertIsNone(entry.auto.ca540_field)
                    else:
                        self.assertEqual(entry.auto.ca540_field, target)
                        self.assertIsNone(entry.auto.federal_key)

    def test_federal_key_resolves_to_a_computed_federal_output_key(self):
        for year in YEARS:
            reference = _computed_federal_reference_keys(year)
            for entry in load_catalog(year):
                if entry.auto is not None and entry.auto.federal_key is not None:
                    with self.subTest(year=year, id=entry.id):
                        self.assertIn(
                            entry.auto.federal_key, reference,
                            f"auto federal_key {entry.auto.federal_key!r} is not a "
                            f"federal-pipeline output key (typo / renamed producer?)",
                        )

    def test_ca540_field_resolves_to_a_real_ca540return_field(self):
        ca540_fields = {f.name for f in dataclasses.fields(models.CA540Return)}
        for year in YEARS:
            for entry in load_catalog(year):
                if entry.auto is not None and entry.auto.ca540_field is not None:
                    with self.subTest(year=year, id=entry.id):
                        self.assertIn(
                            entry.auto.ca540_field, ca540_fields,
                            f"auto ca540_field {entry.auto.ca540_field!r} is not a "
                            f"CA540Return field (typo / renamed field?)",
                        )


if __name__ == "__main__":
    unittest.main()
