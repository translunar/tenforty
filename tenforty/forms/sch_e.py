"""Schedule E — Supplemental Income and Loss, Part I (page 1).

Up to three rental properties print, one per column (A, B, C), in
``scenario.rental_properties`` order; a fourth is refused (there is no
second page). Page 2 (K-1 flow-throughs) is computed elsewhere
(``sch_e_part_ii``).

Per-expense amounts for each property come from the scenario's
``RentalProperty`` (they're user inputs, not computed values — the
oracle workbook consumes them rather than exposing them as named
ranges). The exception is line 18 (depreciation), which comes from the
depreciation resolver: the property's asset list, or its stated amount.
The 40% mid-quarter answer the resolver needs is taxpayer-wide: it is
computed once from the whole scenario and handed to every column.
Lines 20 (total expenses) and 21 (income/loss) are summed locally per
column, and the page totals on lines 23a/23c/23d/23e, 24, 25 and 26 are
summed across the printed columns' whole-dollar lines, so the page foots.
The oracle's ``f1040['sche_line26']`` is kept only as a cross-check on the
locally-summed line 26.
"""

import logging

from tenforty.attestations import raise_scoped_refusal
from tenforty.forms.depreciation.resolver import (
    _RECON_SECTION_SLUGS, mid_quarter_applies, resolve,
)
from tenforty.models import RentalProperty, Scenario
from tenforty.rounding import irs_round

log = logging.getLogger(__name__)


# One letter per printed property column, in rental_properties order.
COLUMN_LETTERS: tuple[str, ...] = ("a", "b", "c")

# (RentalProperty attribute, column key suffix) for the entered expense
# lines 5-17 and 19.
_EXPENSE_FIELDS = (
    ("advertising", "advertising"),
    ("auto_and_travel", "auto_and_travel"),
    ("cleaning_and_maintenance", "cleaning_and_maintenance"),
    ("commissions", "commissions"),
    ("insurance", "insurance"),
    ("legal_and_professional_fees", "legal_and_professional_fees"),
    ("management_fees", "management_fees"),
    ("mortgage_interest", "mortgage_interest"),
    ("other_interest", "other_interest"),
    ("repairs", "repairs"),
    ("supplies", "supplies"),
    ("taxes", "taxes"),
    ("utilities", "utilities"),
    ("other_expenses", "other_expenses"),
)


def _key(letter: str, suffix: str) -> str:
    return f"sch_e_property_{letter}_{suffix}"


def line_18_key(letter: str) -> str:
    """The result key of one column's line 18 (depreciation)."""
    return f"sch_e_property_{letter}_depreciation"


def line_21_key(letter: str) -> str:
    """The result key of one column's line 21 (income or loss)."""
    return f"sch_e_property_{letter}_income_loss"


# Line 18 (depreciation) is deliberately NOT in _EXPENSE_FIELDS: it is not a
# raw field read. It comes from the depreciation resolver -- the one door --
# through `_line_18`, which every function below uses.
_LINE_18_KEY = line_18_key("a")


def _line_18(rp: RentalProperty, tax_year: int, *,
             mid_quarter: bool) -> float:
    """The property's depreciation as resolved for ``tax_year`` (the stated
    scalar as stated, or the asset-mode / overridden figure)."""
    return resolve(rp, tax_year, mid_quarter=mid_quarter).amount


def printed_columns(scenario: Scenario) -> list[tuple[str, RentalProperty]]:
    """``(column letter, property)`` for each rental, in scenario order.

    Schedule E has three property columns on its one page. A return with a
    fourth rental is refused here as well as at load, so a Scenario built in
    code and handed straight to `compute` can never print three properties
    and silently drop the rest."""
    rentals = scenario.rental_properties
    if len(rentals) > len(COLUMN_LETTERS):
        slug = _RECON_SECTION_SLUGS["rental_properties"]
        raise_scoped_refusal("more_than_three_rental_properties", [
            f"{slug}_{i} (rental property #{i}, {rp.address!r})"
            for i, rp in enumerate(rentals) if i >= len(COLUMN_LETTERS)])
    return list(zip(COLUMN_LETTERS, rentals))


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream.get("f1040", {})
    result: dict = {**scenario.config.pdf_header()}
    columns = printed_columns(scenario)
    if not columns:
        return result

    # The 40% test is taxpayer-wide: answered ONCE from the whole scenario
    # and handed to every column, never re-asked per property.
    mid_quarter = mid_quarter_applies(scenario)
    letters = []
    for letter, rp in columns:
        result.update(_property_fields(
            rp, scenario.config.year, letter, mid_quarter=mid_quarter))
        letters.append(letter)

    # printed-chain ruling (SE line 12 lineage), 2026-10-04: line 26 is
    # arithmetic over the printed line 21s, so it is the printed-chain total
    # -- NOT the workbook's cents-carried figure rounded independently,
    # which can differ by $1 from what the page's own lines sum to. The
    # oracle value is kept only as a cross-check.
    result.update(_totals_block(result, letters))
    local_total = result["sch_e_line_26_total"]
    line_26_oracle = f1040.get("sche_line26")
    if line_26_oracle is not None and irs_round(line_26_oracle) != local_total:
        log.warning(
            "Sch E line 26 oracle total %s diverges from the printed-chain "
            "line 21 %s; using the printed-chain value.",
            irs_round(line_26_oracle), local_total,
        )
    return result


# Lines 23a/23c/23d/23e: "Total of all amounts reported on line N for all
# ... properties". (total key, builder of the printed per-column line key it
# totals.) Line 23d totals line 18, whose key has one owner: line_18_key.
_LINE_23_TOTALS = (
    ("sch_e_line_23a_total_rents", lambda letter: _key(letter, "rents")),
    ("sch_e_line_23c_total_mortgage_interest",
     lambda letter: _key(letter, "mortgage_interest")),
    ("sch_e_line_23d_total_depreciation", line_18_key),
    ("sch_e_line_23e_total_expenses",
     lambda letter: _key(letter, "total_expenses")),
)


def _totals_block(printed: dict, letters: list[str]) -> dict:
    """Lines 22, 23a-23e, 24, 25 and 26, summed over the PRINTED whole-dollar
    lines of the filled columns (``letters``) so the block foots to the page.

    A line 23 total is absent exactly when no column prints its source line
    (lines 12 and 18 print nothing at zero). Line 24 -- "Add positive
    amounts shown on line 21. Do not include any losses" -- is absent when
    no column's line 21 is positive, and line 25 when no column has a loss.
    Line 26 combines them: the sum of every column's line 21. Line 23b
    (royalties, line 4) has no producer: nothing prints on line 4.
    """
    totals: dict = {}
    for total_key, line_key in _LINE_23_TOTALS:
        lines = [printed[line_key(letter)] for letter in letters
                 if line_key(letter) in printed]
        if lines:
            totals[total_key] = sum(lines)
    line_21s = {letter: printed[line_21_key(letter)] for letter in letters}
    income = sum(v for v in line_21s.values() if v > 0)
    if income > 0:
        totals["sch_e_line_24_income"] = income
    # Line 22 ("Deductible rental real estate loss after limitation, if
    # any, on Form 8582") is the column's whole line 21 loss. That is right
    # only when Form 8582 allows the whole loss -- and a return on which it
    # does not never prints: the passive_loss_limitation_not_applied
    # refusal stops it. Line 25 adds royalty losses from line 21 to the
    # line 22 losses; no royalty property is ever printed, so line 25 is
    # the line 22 total. These cells sit in preprinted parentheses: stored
    # positive.
    losses = 0
    for letter, line_21 in line_21s.items():
        if line_21 < 0:
            totals[_key(letter, "deductible_loss")] = -line_21
            losses += -line_21
    if losses:
        totals["sch_e_line_25_losses"] = losses
    totals["sch_e_line_26_total"] = income - losses
    return totals


def _property_fields(rp: RentalProperty, tax_year: int, letter: str, *,
                     mid_quarter: bool) -> dict:
    """One property's lines 1a-21 under column ``letter``'s keys."""
    fields: dict = {
        _key(letter, "address"): rp.address,
        _key(letter, "type_code"): rp.property_type_code,
        _key(letter, "fair_rental_days"): rp.fair_rental_days,
        _key(letter, "personal_use_days"): rp.personal_use_days,
        _key(letter, "rents"): irs_round(rp.rents_received),
    }
    # printed-chain ruling (SE line 12 lineage), 2026-10-04: lines 5-19 are
    # entries (rounded individually); line 20 sums the ROUNDED lines and
    # line 21 = rounded line 3 rents - printed line 20, so the page foots.
    total_expenses = 0
    for attr, suffix in _EXPENSE_FIELDS:
        rounded = irs_round(getattr(rp, attr))
        if rounded:
            fields[_key(letter, suffix)] = rounded
        total_expenses += rounded
    depreciation = irs_round(_line_18(rp, tax_year, mid_quarter=mid_quarter))
    if depreciation:
        fields[line_18_key(letter)] = depreciation
    total_expenses += depreciation
    fields[_key(letter, "total_expenses")] = total_expenses
    fields[line_21_key(letter)] = (
        irs_round(rp.rents_received) - total_expenses
    )
    return fields


def printed_rental_net(rp: RentalProperty, tax_year: int, *,
                       mid_quarter: bool) -> int:
    """One property's Schedule E line 21 (income or loss) exactly as the
    form prints it: rounded rents less the sum of the individually rounded
    expense lines. Consumed by the IRC §461(l) excess-business-loss guard
    (orchestrator.aggregate_business_losses)."""
    return _property_fields(
        rp, tax_year, "a", mid_quarter=mid_quarter)[line_21_key("a")]


def has_any_net_loss(scenario: Scenario) -> bool:
    """True when any Sch E Part I rental runs a net loss.

    Iterates _EXPENSE_FIELDS so that adding or removing an expense line
    here keeps the predicate in sync without a second edit; line 18 comes
    from the resolver, as everywhere else."""
    tax_year = scenario.config.year
    mid_quarter = mid_quarter_applies(scenario)
    for p in scenario.rental_properties:
        expense_total = sum(
            getattr(p, attr) for attr, _suffix in _EXPENSE_FIELDS
        ) + _line_18(p, tax_year, mid_quarter=mid_quarter)
        if p.rents_received < expense_total:
            return True
    return False
