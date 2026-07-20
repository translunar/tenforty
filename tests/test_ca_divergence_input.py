"""Tests for id-keyed CA Schedule CA (540) divergence scenario input (spec §2.2).

The user supplies only ``{id, amount, note?}`` (plus ``direction`` for BOTH
rows) and a ``reviewed:`` id list; the loader materializes
direction/line/description from the catalog entry. There is ONE input format —
the old free-form ``{source, sch_ca_line, direction, amount, description}`` path
is removed. These tests pin:

- ``resolve_divergence_id`` / ``UnknownDivergenceIdError`` with a did-you-mean
  suggestion (both the ``divergences`` and ``reviewed`` lists validate every id),
- ``materialize_user_divergence`` and its RULED direction rules (2026-07-19),
- ``scenario._load_ca540`` id-keyed parsing, duplicate detection, year-scoping,
- the ``sch_ca._is_section_c`` "Part I line 26" (§179A clean-fuel) fix.
"""

import unittest

from tenforty.ca_divergences import (
    UnknownDivergenceIdError,
    materialize_user_divergence,
    resolve_divergence_id,
)
from tenforty.forms.sch_ca import _is_section_c
from tenforty.forms.sch_ca import compute as sch_ca_compute
from tenforty.models import (
    CA540Return,
    CASchCAAdjustment,
    DivergenceDirection,
    DivergenceSource,
)
from tenforty.scenario import _load_ca540

# Real 2025 catalog ids used across the tests.
_SUB_ID = "native-american-reservation-income-exclusion-tribal"  # §A 1a, Sub
_SUB_LINE = "Part I §A 1a"
_SUB_DESC = "Native American reservation income exclusion (tribal members in CA Indian country)"
_ADD_ID = "moving-expense-suspended-federally-except-active-duty"  # §C 14, Add
_ADD_LINE = "Part I §C 14"
_BOTH_ID = "hsa-deduction-ca-disallows-also-adds-back-employer-hsa"  # §C 13, Both
_BOTH_LINE = "Part I §C 13"
# Valid in the 2024 catalog, ABSENT from 2025 (year-scoping anchor).
_ONLY_2024_ID = "ca-microbusiness-covid-19-relief-grant-ca-excludes"


class ResolveDivergenceIdTests(unittest.TestCase):
    def test_known_id_resolves_to_catalog_entry(self):
        entry = resolve_divergence_id(2025, _SUB_ID)
        self.assertEqual(entry.id, _SUB_ID)
        self.assertEqual(entry.sch_ca_line, _SUB_LINE)

    def test_unknown_id_raises_with_did_you_mean(self):
        typo = _SUB_ID[:-1]  # drop the trailing 'l'
        with self.assertRaises(UnknownDivergenceIdError) as ctx:
            resolve_divergence_id(2025, typo)
        msg = str(ctx.exception)
        self.assertIn(typo, msg)
        self.assertIn("2025", msg)
        self.assertIn(_SUB_ID, msg)  # the suggestion


class MaterializeDirectionRuleTests(unittest.TestCase):
    def _entry(self, catalog_id):
        return resolve_divergence_id(2025, catalog_id)

    def test_amount_must_be_positive(self):
        entry = self._entry(_ADD_ID)
        for bad in (0.0, -100.0):
            with self.assertRaises(ValueError) as ctx:
                materialize_user_divergence(entry, bad, None)
            self.assertIn(_ADD_ID, str(ctx.exception))

    def test_add_row_forbids_direction_key(self):
        entry = self._entry(_ADD_ID)
        with self.assertRaises(ValueError) as ctx:
            materialize_user_divergence(entry, 500.0, "add")
        self.assertIn(_ADD_ID, str(ctx.exception))

    def test_sub_row_forbids_direction_key(self):
        entry = self._entry(_SUB_ID)
        with self.assertRaises(ValueError) as ctx:
            materialize_user_divergence(entry, 500.0, "sub")
        self.assertIn(_SUB_ID, str(ctx.exception))

    def test_add_row_materializes_addition(self):
        entry = self._entry(_ADD_ID)
        adj = materialize_user_divergence(entry, 750.0, None)
        self.assertEqual(adj.source, DivergenceSource.USER)
        self.assertEqual(adj.catalog_id, _ADD_ID)
        self.assertEqual(adj.sch_ca_line, _ADD_LINE)
        self.assertEqual(adj.direction, DivergenceDirection.ADDITION)
        self.assertEqual(adj.amount, 750.0)
        self.assertEqual(adj.description, entry.description)

    def test_sub_row_materializes_subtraction(self):
        entry = self._entry(_SUB_ID)
        adj = materialize_user_divergence(entry, 900.0, None)
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.source, DivergenceSource.USER)
        self.assertEqual(adj.catalog_id, _SUB_ID)

    def test_both_row_requires_direction(self):
        entry = self._entry(_BOTH_ID)
        with self.assertRaises(ValueError) as ctx:
            materialize_user_divergence(entry, 4300.0, None)
        msg = str(ctx.exception)
        self.assertIn(_BOTH_ID, msg)
        self.assertIn("add", msg)
        self.assertIn("sub", msg)

    def test_both_row_direction_add_materializes_addition(self):
        entry = self._entry(_BOTH_ID)
        adj = materialize_user_divergence(entry, 4300.0, "add")
        self.assertEqual(adj.direction, DivergenceDirection.ADDITION)
        self.assertEqual(adj.catalog_id, _BOTH_ID)

    def test_both_row_direction_sub_materializes_subtraction(self):
        entry = self._entry(_BOTH_ID)
        adj = materialize_user_divergence(entry, 4300.0, "sub")
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.sch_ca_line, _BOTH_LINE)

    def test_both_row_bad_direction_value_raises(self):
        entry = self._entry(_BOTH_ID)
        with self.assertRaises(ValueError) as ctx:
            materialize_user_divergence(entry, 4300.0, "plus")
        self.assertIn(_BOTH_ID, str(ctx.exception))


class LoadCa540IdKeyedTests(unittest.TestCase):
    def test_unknown_id_in_divergences_raises_with_suggestion(self):
        typo = _SUB_ID[:-1]
        data = {"divergences": [{"id": typo, "amount": 100.0}]}
        with self.assertRaises(UnknownDivergenceIdError) as ctx:
            _load_ca540(data, 2025)
        self.assertIn(_SUB_ID, str(ctx.exception))

    def test_unknown_id_in_reviewed_raises_with_suggestion(self):
        typo = _SUB_ID[:-1]
        data = {"reviewed": [typo]}
        with self.assertRaises(UnknownDivergenceIdError) as ctx:
            _load_ca540(data, 2025)
        self.assertIn(_SUB_ID, str(ctx.exception))

    def test_duplicate_id_in_divergences_raises_naming_id(self):
        data = {
            "divergences": [
                {"id": _ADD_ID, "amount": 100.0},
                {"id": _ADD_ID, "amount": 200.0},
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            _load_ca540(data, 2025)
        self.assertIn(_ADD_ID, str(ctx.exception))

    def test_year_scoped_id_valid_in_adjacent_year_rejected(self):
        # Valid in 2024, absent from 2025.
        resolve_divergence_id(2024, _ONLY_2024_ID)  # sanity: exists in 2024
        data = {"divergences": [{"id": _ONLY_2024_ID, "amount": 100.0}]}
        with self.assertRaises(UnknownDivergenceIdError) as ctx:
            _load_ca540(data, 2025)
        self.assertIn(_ONLY_2024_ID, str(ctx.exception))

    def test_happy_path_materializes_from_catalog(self):
        data = {"divergences": [{"id": _SUB_ID, "amount": 1234.0}]}
        ca540 = _load_ca540(data, 2025)
        self.assertEqual(len(ca540.divergences), 1)
        adj = ca540.divergences[0]
        self.assertEqual(adj.source, DivergenceSource.USER)
        self.assertEqual(adj.catalog_id, _SUB_ID)
        self.assertEqual(adj.sch_ca_line, _SUB_LINE)
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.description, _SUB_DESC)
        self.assertEqual(adj.amount, 1234.0)  # amount from user

    def test_note_passthrough(self):
        data = {
            "divergences": [
                {"id": _SUB_ID, "amount": 500.0, "note": "from the 2025 tribal statement"}
            ]
        }
        ca540 = _load_ca540(data, 2025)
        self.assertEqual(ca540.divergences[0].note, "from the 2025 tribal statement")

    def test_both_row_direction_sub_through_loader(self):
        data = {
            "divergences": [
                {"id": _BOTH_ID, "amount": 4300.0, "direction": "sub"}
            ]
        }
        ca540 = _load_ca540(data, 2025)
        adj = ca540.divergences[0]
        self.assertEqual(adj.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(adj.catalog_id, _BOTH_ID)

    def test_reviewed_ids_recorded(self):
        data = {"reviewed": [_SUB_ID, _ADD_ID]}
        ca540 = _load_ca540(data, 2025)
        self.assertEqual(ca540.reviewed_divergence_ids, (_SUB_ID, _ADD_ID))

    def test_empty_divergences_and_reviewed_byte_identical(self):
        # Today's behavior: no ca540 divergences, empty reviewed tuple.
        ca540 = _load_ca540({"estimated_payments": 100.0}, 2025)
        self.assertEqual(ca540.divergences, [])
        self.assertEqual(ca540.reviewed_divergence_ids, ())
        self.assertEqual(ca540.estimated_payments, 100.0)

    def test_none_block_returns_none(self):
        self.assertIsNone(_load_ca540(None, 2025))


class SectionCLine26ClassificationTests(unittest.TestCase):
    """The §179A clean-fuel row sits at 'Part I line 26' (the §C total line) and
    is an adjustment-to-income, so it must classify as Section C, not income."""

    def test_part_i_line_26_is_section_c(self):
        self.assertIs(_is_section_c("Part I line 26"), True)

    def test_regular_section_c_still_true(self):
        self.assertIs(_is_section_c("Part I §C 14"), True)

    def test_income_line_still_false(self):
        self.assertIs(_is_section_c("Part I §A 2"), False)

    def test_line_26_subtraction_raises_ca_agi(self):
        # A §179A-style Column-B subtraction on 'Part I line 26' is a §C
        # adjustment: it lands on line 26, is SUBTRACTED to form line 27, so the
        # netted Col B goes negative and CA AGI RISES (§C semantics).
        adj = CASchCAAdjustment(
            source=DivergenceSource.USER,
            sch_ca_line="Part I line 26",
            direction=DivergenceDirection.SUBTRACTION,
            amount=5_000.0,
            description="§179A clean-fuel adjustment",
            catalog_id="clean-fuel-179a-example",
        )
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[adj]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        self.assertEqual(result["sch_ca_total_subtractions"], -5_000.0)
        self.assertEqual(result["sch_ca_ca_agi"], 105_000.0)


if __name__ == "__main__":
    unittest.main()
