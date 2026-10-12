"""One Form 4562 per activity that places property in service this year.

Every test here goes through the orchestrator's emit path and reads the
filled PDFs: which copies exist, what each is called, and what each prints.
Nothing calls `f4562.compute_for` with a hand-picked 40% answer -- that would
prove nothing about who supplied it.

THE TWO SHAPES. All property is 5-year personal property; the rental is
"100 Example Street" and the business is "Consulting".

  under  rental: 9,000 placed March
         business: 1,000 placed November (alone: 100% in the last quarter)
         pooled: 1,000 of 10,000 -> the RETURN is half-year
  over   rental: 6,000 placed March + 3,000 placed November (alone: 33 1/3%)
         business: 3,000 placed December
         pooled: 6,000 of 12,000 -> the RETURN is mid-quarter

Expected figures are Publication 946 first-year rates times basis, typed from
the publication: Table A-1 half-year 20.00%, Table A-2 mid-quarter first
quarter 35.00%, Table A-5 mid-quarter fourth quarter 5.00%.

  under  rental copy row 19b:   basis 9,000  HY  1,800
         business copy row 19b: basis 1,000  HY    200
  over   rental copy row 19b:   basis 9,000  MQ  2,250 (2,100 + 150)
         business copy row 19b: basis 3,000  MQ    150

Field paths are 2025 LITERALS, as anchored to the blank templates in
tests/test_f4562_emit_gate.py (line 22), tests/test_f4562_header.py (the
activity box, Schedule E line 1a), tests/test_f4562_mid_quarter.py (row 19b),
tests/test_f4562_prior_asset_line17.py (line 17) and
tests/test_depreciation_emit_pins.py (Schedule C line 13) -- never looked up
through the mapping under test.
"""

import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tenforty import pdf_packet
from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms import f4562
from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.resolver import resolve
from tenforty.models import DepreciableAsset, ScheduleCBusiness
from tests import _audit_workbook_fixtures as fx
from tests import test_f4562_emit_gate as gate

YEAR = 2025
ADDRESS = "100 Example Street"

_P1 = "topmostSubform[0].Page1[0]"
ACTIVITY_BOX = f"{_P1}.f1_2[0]"
LINE_17 = f"{_P1}.f1_25[0]"
ROW_19B_BASIS = f"{_P1}.SectionBTable[0].Line19b[0].f1_33[0]"
ROW_19B_CONVENTION = f"{_P1}.SectionBTable[0].Line19b[0].f1_35[0]"
ROW_19B_DEDUCTION = f"{_P1}.SectionBTable[0].Line19b[0].f1_37[0]"
LINE_22 = "topmostSubform[0].Page2[0].f2_2[0]"
SCH_E_LINE_1A_PROPERTY_A = f"{_P1}.Table_Line1a[0].RowA[0].f1_3[0]"
SCH_E_LINE_18_PROPERTY_A = f"{_P1}.Table_Expenses[0].Line18[0].f1_61[0]"
SCH_C_LINE_13 = f"{_P1}.Lines8-17[0].f1_22[0]"

_read = gate._read


def _equipment(basis: float, month: int) -> DepreciableAsset:
    return DepreciableAsset(
        description="Equipment", date_placed_in_service=date(YEAR, month, 15),
        basis=basis, recovery_class="5-year",
        no_bonus_or_section_179_history=True)


def _business(*assets, description: str = "Consulting") -> ScheduleCBusiness:
    return ScheduleCBusiness(
        description=description, gross_receipts=50_000.0,
        depreciable_assets=tuple(assets))


def _under(business_description: str = "Consulting"):
    return gate._scenario(
        rentals=[gate._rental(_equipment(9_000.0, 3))],
        businesses=[_business(
            _equipment(1_000.0, 11), description=business_description)])


def _over():
    return gate._scenario(
        rentals=[gate._rental(
            _equipment(6_000.0, 3), _equipment(3_000.0, 11))],
        businesses=[_business(_equipment(3_000.0, 12))])


def _copy_keys(emitted) -> list[str]:
    return sorted(key for key in emitted if key.startswith("f4562"))


def _row_19b(pdf_path) -> tuple[str, str, str]:
    """(basis, convention, deduction) as printed on row 19b."""
    return (_read(pdf_path, ROW_19B_BASIS),
            _read(pdf_path, ROW_19B_CONVENTION),
            _read(pdf_path, ROW_19B_DEDUCTION))


class PooledConventionTwinTests(gate._EmitCase):
    """The 40% answer is the RETURN's, on every copy. Each test names an
    activity whose own placements would answer the other way."""

    def test_business_over_alone_prints_half_year_when_the_return_is_under(
            self):
        emitted = self._emit(_under())
        self.assertEqual(
            _row_19b(emitted["f4562_sch_c_0"]), ("1000", "HY", "200"))
        self.assertEqual(
            _row_19b(emitted["f4562_rental_0"]), ("9000", "HY", "1800"))

    def test_rental_under_alone_prints_mid_quarter_when_the_return_is_over(
            self):
        emitted = self._emit(_over())
        self.assertEqual(
            _row_19b(emitted["f4562_rental_0"]), ("9000", "MQ", "2250"))
        self.assertEqual(
            _row_19b(emitted["f4562_sch_c_0"]), ("3000", "MQ", "150"))


class PerCopyEmitTests(gate._EmitCase):
    def test_copy_count_equals_qualifying_activity_count_and_names_are_recon_keys(
            self):
        emitted = self._emit(_under())
        self.assertEqual(
            _copy_keys(emitted), ["f4562_rental_0", "f4562_sch_c_0"])
        self.assertNotIn("f4562", emitted)
        self.assertEqual(
            emitted["f4562_rental_0"].name, "f4562_2025_rental_0.pdf")
        self.assertEqual(
            emitted["f4562_sch_c_0"].name, "f4562_2025_sch_c_0.pdf")
        for key in ("f4562_rental_0", "f4562_sch_c_0"):
            with self.subTest(key=key):
                self.assertTrue(emitted[key].is_file())

    def test_each_copys_line_22_equals_its_schedules_printed_line(self):
        emitted = self._emit(_under())
        rental = _read(emitted["f4562_rental_0"], LINE_22)
        business = _read(emitted["f4562_sch_c_0"], LINE_22)
        self.assertEqual(rental, "1800")
        self.assertEqual(
            rental, _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A))
        self.assertEqual(business, "200")
        self.assertEqual(business, _read(emitted["sch_c_1"], SCH_C_LINE_13))
        self.assertNotEqual(rental, business)

    def test_each_copys_header_names_its_own_activity(self):
        emitted = self._emit(_under())
        rental = _read(emitted["f4562_rental_0"], ACTIVITY_BOX)
        self.assertEqual(rental, ADDRESS)
        self.assertEqual(
            rental, _read(emitted["sch_e"], SCH_E_LINE_1A_PROPERTY_A))
        self.assertEqual(
            _read(emitted["f4562_sch_c_0"], ACTIVITY_BOX), "Consulting")

    def test_an_activity_with_only_prior_year_assets_gets_no_copy_but_its_line_prints(
            self):
        """Ruling A: a copy only for an activity that itself places property
        in service this year. The business holds one 5-year asset placed in
        2023 (1,920 this year)."""
        emitted = self._emit(gate._scenario(
            rentals=[gate._rental(_equipment(9_000.0, 3))],
            businesses=[_business(fx.APPLIANCE)]))
        self.assertEqual(_copy_keys(emitted), ["f4562"])
        self.assertEqual(emitted["f4562"].name, "f4562_2025.pdf")
        # The business's depreciation still prints on its own schedule...
        self.assertEqual(_read(emitted["sch_c_1"], SCH_C_LINE_13), "1920")
        # ...and is nowhere on the one copy, which is the rental's.
        self.assertEqual(_read(emitted["f4562"], LINE_17), "")
        self.assertEqual(_read(emitted["f4562"], LINE_22), "1800")
        self.assertEqual(_read(emitted["f4562"], ACTIVITY_BOX), ADDRESS)
        # Twin: the same business with a placement this year HAS a copy.
        self.assertIn("f4562_sch_c_0", self._emit(_under()))

    def test_two_activities_with_one_printed_name_get_two_files(self):
        emitted = self._emit(gate._scenario(businesses=[
            _business(_equipment(1_000.0, 3)),
            _business(_equipment(2_000.0, 3))]))
        self.assertEqual(
            _copy_keys(emitted), ["f4562_sch_c_0", "f4562_sch_c_1"])
        first, second = emitted["f4562_sch_c_0"], emitted["f4562_sch_c_1"]
        self.assertNotEqual(first, second)
        self.assertEqual(first.name, "f4562_2025_sch_c_0.pdf")
        self.assertEqual(second.name, "f4562_2025_sch_c_1.pdf")
        self.assertTrue(first.is_file())
        self.assertTrue(second.is_file())
        # Same name in the box, different assets on the rows: neither file
        # overwrote the other.
        self.assertEqual(_read(first, ACTIVITY_BOX), "Consulting")
        self.assertEqual(_read(second, ACTIVITY_BOX), "Consulting")
        self.assertEqual(_row_19b(first), ("1000", "HY", "200"))
        self.assertEqual(_row_19b(second), ("2000", "HY", "400"))

    def test_a_nameless_activity_still_gets_its_copy(self):
        emitted = self._emit(_under(business_description="  "))
        self.assertEqual(
            _copy_keys(emitted), ["f4562_rental_0", "f4562_sch_c_0"])
        self.assertTrue(emitted["f4562_sch_c_0"].is_file())
        self.assertEqual(_read(emitted["f4562_sch_c_0"], ACTIVITY_BOX), "")
        self.assertEqual(
            _row_19b(emitted["f4562_sch_c_0"]), ("1000", "HY", "200"))
        # Twin: the named activity's box on the same return is filled.
        self.assertEqual(
            _read(emitted["f4562_rental_0"], ACTIVITY_BOX), ADDRESS)

    def test_the_packet_stacks_every_copy_where_the_single_form_sat(self):
        real = self._emit(_under())
        # Business copy first in the dict: the packet's order is its own.
        emitted = {
            "f3115": Path("/x/f3115.pdf"),
            "f4562_sch_c_0": real["f4562_sch_c_0"],
            "f4562_rental_0": real["f4562_rental_0"],
            "f8582": Path("/x/f8582.pdf"),
            "1040": real["1040"],
        }
        names = [path.name for path in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, [
            real["1040"].name, "f8582.pdf", "f4562_2025_rental_0.pdf",
            "f4562_2025_sch_c_0.pdf", "f3115.pdf"])
        self.assertEqual(
            pdf_packet.classify_key("f4562_sch_c_0"), "federal_individual")
        self.assertEqual(
            pdf_packet.classify_key("f4562_rental_0"), "federal_individual")
        self.assertEqual(
            pdf_packet.classify_key("f4562"), "federal_individual")
        self.assertIsNone(pdf_packet.classify_key("f4562x_sch_c_0"))
        for key in real:
            with self.subTest(key=key):
                self.assertIsNotNone(pdf_packet.classify_key(key))

    def test_the_packet_orders_copies_rentals_first_then_by_number(self):
        keys = ["f4562_sch_c_10", "f4562_sch_c_2", "f4562_rental_1",
                "f4562_rental_0", "f8582", "f3115"]
        emitted = {key: Path(f"/x/{key}.pdf") for key in keys}
        self.assertEqual(
            [path.stem for path in pdf_packet.ordered_members(
                emitted, pdf_packet.FEDERAL_INDIVIDUAL)],
            ["f8582", "f4562_rental_0", "f4562_rental_1", "f4562_sch_c_2",
             "f4562_sch_c_10", "f3115"])
        # A single-copy return's key holds the same slot.
        self.assertEqual(
            [path.stem for path in pdf_packet.ordered_members(
                {"f3115": Path("/x/f3115.pdf"), "f4562": Path("/x/f4562.pdf"),
                 "f8582": Path("/x/f8582.pdf")},
                pdf_packet.FEDERAL_INDIVIDUAL)],
            ["f8582", "f4562", "f3115"])


class RetirementProofTests(gate._EmitCase):
    """The shapes the two retired merged-form refusals refused now emit."""

    def _overridden_rental(self):
        return gate._rental(gate._old_building(), override_amount=7_000.0)

    def test_placement_on_one_activity_and_override_on_another_now_emits(
            self):
        """The shape the retired merged-form override refusal fired on: an
        overridden rental beside a business that places equipment this
        year."""
        scenario = gate._scenario(
            rentals=[self._overridden_rental()],
            businesses=[_business(gate._new_equipment())])
        enforce_scoped_refusals(scenario, "load")
        emitted = self._emit(scenario)
        # One copy, and it is the placing business's.
        self.assertEqual(_copy_keys(emitted), ["f4562"])
        self.assertEqual(_read(emitted["f4562"], ACTIVITY_BOX), "Consulting")
        self.assertEqual(
            _row_19b(emitted["f4562"]), ("10000", "HY", "2000"))
        self.assertEqual(_read(emitted["f4562"], LINE_22), "2000")
        self.assertEqual(_read(emitted["sch_c_1"], SCH_C_LINE_13), "2000")
        # The overridden rental prints its override amount on its own
        # schedule and none of its assets on the copy.
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), "7000")
        self.assertEqual(_read(emitted["f4562"], LINE_17), "")

    def test_assets_placed_on_two_activities_emit_two_copies(self):
        """The shape the never-merged across-activities refusal refused."""
        scenario = _under()
        enforce_scoped_refusals(scenario, "load")
        self.assertEqual(len(_copy_keys(self._emit(scenario))), 2)

    def test_override_with_a_placement_on_the_same_activity_still_refuses(
            self):
        """The neighbouring refusal is not loosened."""
        rental = gate._rental(
            gate._old_building(), gate._new_building(),
            override_amount=7_000.0)
        with self.assertRaisesRegex(
                NotImplementedError,
                r"carries a `depreciation_override` and placed"):
            enforce_scoped_refusals(gate._scenario(rentals=[rental]), "load")
        # Twin: the same override with no placement on its activity loads.
        enforce_scoped_refusals(
            gate._scenario(rentals=[self._overridden_rental()]), "load")

    def test_resolving_the_overridden_activity_alone_does_not_refuse(self):
        """Re-homed from the retired refusal's test class: resolving the
        overridden rental directly gives its override amount."""
        self.assertEqual(
            resolve(self._overridden_rental(), YEAR, mid_quarter=False).amount,
            7_000.0)

    def test_override_with_no_placement_anywhere_emits_no_copy(self):
        emitted = self._emit(gate._scenario(
            rentals=[self._overridden_rental()], businesses=[_business()]))
        self.assertEqual(_copy_keys(emitted), [])
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), "7000")

    def test_placement_with_no_override_anywhere_emits_the_placing_copy(
            self):
        building = gate._old_building()
        expected = macrs_deduction(
            building, YEAR, return_year=YEAR, mid_quarter=False)
        emitted = self._emit(gate._scenario(
            rentals=[gate._rental(building)],
            businesses=[_business(gate._new_equipment())]))
        self.assertEqual(_copy_keys(emitted), ["f4562"])
        self.assertEqual(_read(emitted["f4562"], ACTIVITY_BOX), "Consulting")
        self.assertEqual(_read(emitted["f4562"], LINE_22), "2000")
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), str(expected))


class FailClosedTests(gate._EmitCase):
    """A refusal while computing any copy aborts the whole emit: never a
    packet with some copies missing."""

    def _emit_refusing_on_call(self, number: int, error: Exception):
        real = f4562.compute_for
        calls = []

        def compute_for(*args, **kwargs):
            calls.append(args)
            if len(calls) == number:
                raise error
            return real(*args, **kwargs)

        scenario = _under()
        results = self.orchestrator.compute_federal(scenario)
        out = self.tmp / f"refused{number}{type(error).__name__}"
        with mock.patch.object(f4562, "compute_for", compute_for):
            with self.assertRaises(type(error)) as caught:
                self.orchestrator.emit_pdfs(scenario, results, out)
        written = sorted(p.name for p in out.glob("f4562*")) if (
            out.exists()) else []
        return caught.exception, written

    def test_a_refusal_on_the_second_copy_leaves_no_4562_file(self):
        error, written = self._emit_refusing_on_call(
            2, NotImplementedError("row conflict"))
        self.assertIs(type(error), NotImplementedError)
        self.assertRegex(
            str(error), r"^Form 4562 copy sch_c_0 \('Consulting'\): "
                        r"row conflict$")
        self.assertEqual(written, [])
        # Twin: unrefused, the same return writes both copies.
        emitted = self._emit(_under())
        self.assertEqual(
            sorted(p.name for p in emitted["1040"].parent.glob("f4562*")),
            ["f4562_2025_rental_0.pdf", "f4562_2025_sch_c_0.pdf"])

    def test_a_value_error_stays_a_value_error(self):
        error, written = self._emit_refusing_on_call(
            2, ValueError("row conflict"))
        self.assertIs(type(error), ValueError)
        self.assertNotIsInstance(error, NotImplementedError)
        self.assertRegex(
            str(error), r"^Form 4562 copy sch_c_0 \('Consulting'\): "
                        r"row conflict$")
        self.assertEqual(written, [])

    def test_a_refusal_on_the_first_copy_names_the_rental(self):
        error, written = self._emit_refusing_on_call(
            1, NotImplementedError("row conflict"))
        self.assertRegex(
            str(error), r"^Form 4562 copy rental_0 "
                        r"\('100 Example Street'\): row conflict$")
        self.assertEqual(written, [])


if __name__ == "__main__":
    unittest.main()
