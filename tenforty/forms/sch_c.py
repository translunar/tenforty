"""Schedule C -- Profit or Loss From Business (sole proprietorship).

Compute-first, per-business, ending in net profit (line 31). PDF mapping is a
follow-on unit; keys are named by form line so mapping adds no compute change.

v1 scope: gross receipts (line 1/7) minus deductible Part II expense categories
(line 28) -> tentative profit (line 29) -> net profit or (loss) (line 31). Cost
of goods sold / inventory (Part III), home office (Form 8829, line 30), vehicle
expenses, depletion (line 12), returns & allowances (line 2), and the
statutory-employee flag are UNMODELED and refuse loudly (nonzero ->
NotImplementedError) -- there is no correct net profit for those inputs
without the unmodeled math, so fail closed rather than silently drop them.

LINE 13 (depreciation) prints and counts the business's RESOLVED depreciation
(forms/depreciation/resolver.py): its asset list, or its stated amount with
the per-business acknowledgment. The section 179 deduction, which shares the
line on the form, is NOT modeled and has no input: an asset with section 179
or bonus history refuses at load, and there is no field through which a
current-year election could be stated.

NET LOSS (line 31 below zero). Line 32 then asks whether all investment in the
activity is at risk (box 32a) or not (box 32b, Form 6198). Form 6198 is
unmodeled, so a loss computes ONLY when the filer attests
`acknowledges_sch_c_all_investment_at_risk`; box 32a is then marked for that
business and the loss flows to Schedule 1 line 3. Without the attestation the
loss refuses. A loss owes no self-employment tax (forms/sch_se.py), enters
Form 8995 as a negative QBI component (forms/f8995.py), and is counted by the
excess-business-loss guard in the orchestrator.
"""
from tenforty.forms.depreciation.resolver import resolve
from tenforty.models import Scenario, ScheduleCBusiness
from tenforty.rounding import irs_round

# The 12 Part II expense categories (Schedule C lines 8-27a) a P&L export
# covers, read straight off the business.
_EXPENSE_FIELDS = (
    "advertising", "insurance", "legal_professional", "office_expense",
    "rent_lease", "supplies", "taxes_licenses", "travel", "deductible_meals",
    "utilities", "wages", "other_expenses",
)

LINE_13_KEY = "sch_c_line_13_depreciation"


def part_ii_lines(biz: ScheduleCBusiness, tax_year: int) -> dict[str, float]:
    """Every modeled Part II amount for one business, UNROUNDED, keyed by
    the value key it prints under: the 12 stated categories plus line 13
    from the depreciation resolver.

    SINGLE SOURCE OF TRUTH. Line 28, `net_profit_estimate`,
    `printed_net_profit` and the emitted values all derive from this one
    mapping, so a line cannot be in the page total but out of the routing
    estimate or the loss guard (the partial-total failure). Adding a line
    here adds it to all four at once.
    """
    lines = {
        f"sch_c_expense_{name}": getattr(biz, name) for name in _EXPENSE_FIELDS}
    lines[LINE_13_KEY] = resolve(biz, tax_year).amount
    return lines


def net_profit_estimate(biz: ScheduleCBusiness, tax_year: int) -> float:
    """Cheap net-profit estimate for the EIC-scope routing gate.

    Returns ``gross_receipts - sum(part_ii_lines)``. A pre-compute estimate:
    it has NO at-risk or unmodeled-feature refusals, because it runs BEFORE
    ``compute`` fires those -- the routing gate must be able to estimate
    income for an input ``compute`` will later refuse. (The depreciation
    resolver's own refusals do apply; the orchestrator runs that ledger
    before any estimate is taken.)
    """
    return biz.gross_receipts - sum(part_ii_lines(biz, tax_year).values())


def printed_net_profit(biz: ScheduleCBusiness, tax_year: int) -> int:
    """Line 31 exactly as the form prints it: rounded line 1 less the sum of
    the individually rounded expense lines (unmodeled lines ignored --
    `compute` refuses those). Because entry lines round one by one, this can
    differ from the raw `net_profit_estimate` by a dollar or more.
    `_compute_business` and the excess-business-loss guard both use it, so
    the guard compares the same figure the page shows."""
    return irs_round(biz.gross_receipts) - sum(
        irs_round(amount) for amount in part_ii_lines(biz, tax_year).values())


_REFUSED_AMOUNT_FIELDS = (
    ("cost_of_goods_sold", "Part III cost of goods sold"),
    ("inventory", "Part III inventory"),
    ("home_office", "line 30 home office (Form 8829)"),
    ("vehicle_expenses", "line 9 car & truck / vehicle expenses"),
    ("depletion", "line 12 depletion"),
    ("returns_and_allowances", "line 2 returns and allowances"),
)


def _guard_unmodeled(biz: ScheduleCBusiness, idx: int) -> None:
    for field_name, label in _REFUSED_AMOUNT_FIELDS:
        if getattr(biz, field_name):
            raise NotImplementedError(
                f"Schedule C business #{idx} ({biz.description!r}) has a nonzero "
                f"{field_name} ({label}); tenforty v1 does not model it. There is "
                f"no correct net profit without the unmodeled computation, so this "
                f"return cannot be produced by v1. Remove the amount or file by hand."
            )
    if biz.statutory_employee:
        raise NotImplementedError(
            f"Schedule C business #{idx} ({biz.description!r}) sets statutory_employee; "
            f"statutory-employee returns are not modeled in tenforty v1."
        )


def _compute_business(
    biz: ScheduleCBusiness, idx: int, all_investment_at_risk: bool | None,
    tax_year: int,
) -> dict:
    _guard_unmodeled(biz, idx)
    # Line 7 gross income = gross receipts (returns/allowances and COGS are
    # refused above, so both are 0 here by construction).
    #
    # printed-chain ruling (SE line 12 lineage), 2026-10-04: lines 3/5/7/28/
    # 29/31 are arithmetic over OTHER printed lines, so they compute from the
    # whole-dollar-ROUNDED operands and the filed page foots. Entry lines
    # (line 1, each expense category 8-27b) round individually.
    line_1 = irs_round(biz.gross_receipts)
    line_7 = line_1
    lines = part_ii_lines(biz, tax_year)
    line_13 = irs_round(lines[LINE_13_KEY])
    line_28 = sum(irs_round(amount) for amount in lines.values())
    # tentative profit (line 7 - line 28)
    line_29 = printed_net_profit(biz, tax_year)
    line_31 = line_29                    # line 30 home office refused -> 0
    is_loss = line_31 < 0
    if is_loss and all_investment_at_risk is not True:
        raise NotImplementedError(
            f"Schedule C business #{idx} ({biz.description!r}) computes a net LOSS "
            f"(line 31 = {line_31:.0f}). A loss must answer line 32: box 32a (all "
            f"investment is at risk) or box 32b (some investment is not at risk, "
            f"which requires Form 6198). Form 6198 is not modeled in tenforty v1. "
            f"Set `acknowledges_sch_c_all_investment_at_risk: true` to affirm that "
            f"ALL investment in every loss-making Schedule C business is at risk "
            f"(box 32a is then checked and the loss is allowed); otherwise this "
            f"return cannot be produced by v1."
        )
    # Lines 1, 3 and 5 are printed explicitly so the form's own chain is
    # complete. They all equal line 7 BY CONSTRUCTION: line 2 (returns and
    # allowances) and line 4 (cost of goods sold) are refused above, and
    # line 6 (other income) has no input channel.
    gross = line_7
    return {
        "sch_c_line_1_gross_receipts": gross,
        "sch_c_line_3_net_receipts": gross,
        "sch_c_line_5_gross_profit": gross,
        "sch_c_line_7_gross_income": gross,
        # Line 13 prints only when there is depreciation; a business with
        # none leaves the box blank, so the key is ABSENT (not 0).
        **({LINE_13_KEY: line_13} if line_13 else {}),
        "sch_c_line_28_total_expenses": line_28,
        "sch_c_line_29_tentative_profit": line_29,
        "sch_c_line_31_net_profit": line_31,
        # Line 32a is answered only on a loss; a profit business leaves line
        # 32 blank, so the key is ABSENT (not False) for it.
        **({"sch_c_line_32a_all_investment_at_risk": True} if is_loss else {}),
    }


def compute(scenario: Scenario, upstream: dict) -> dict:
    businesses = scenario.schedule_c_businesses
    if not businesses:
        return {}
    at_risk = scenario.config.acknowledges_sch_c_all_investment_at_risk
    per_business = [
        _compute_business(b, i, at_risk, scenario.config.year)
        for i, b in enumerate(businesses)]
    total = sum(b["sch_c_line_31_net_profit"] for b in per_business)
    return {
        "sch_c_businesses": per_business,
        "sch_c_line_31_net_profit_total": irs_round(total),
    }


def emit_values(scenario: Scenario, index: int, line_values: dict) -> dict:
    """PDF value dict for ONE Schedule C (business `index`, 0-based).

    Header + line A/B + the Part II expense amounts + Part V line 48 + this
    business's computed lines (`line_values` is `compute(...)["sch_c_businesses"][index]`).

    Blank text and zero expense amounts are OMITTED so the box prints blank
    rather than a literal 0. Expense amounts are passed through unrounded; the
    PDF filler applies the whole-dollar rounding at render.
    """
    biz = scenario.schedule_c_businesses[index]
    out: dict = {**scenario.config.pdf_header()}
    description = str(biz.description).strip()
    if description:
        out["sch_c_line_a_description"] = description
    code = str(biz.business_code).strip()
    if code:
        out["sch_c_line_b_business_code"] = code
    # The Part II amounts, from the single definition. Line 13 is carried by
    # `line_values` (the computed, whole-dollar figure), which overwrites the
    # unrounded entry below when present.
    for key, amount in part_ii_lines(biz, scenario.config.year).items():
        if amount:
            out[key] = amount
    # Part V line 48 is the total the "Other expenses (from line 48)" line
    # carries forward, so it prints the same amount. The itemization rows
    # above line 48 are left blank for hand-completion.
    if biz.other_expenses:
        # Emit-time refusal (NOT compute): the figure is computable, but the
        # filed paper requires Part V to itemize what line 48 totals.
        item = str(biz.other_expenses_description).strip()
        if not item:
            raise ValueError(
                f"Schedule C business {index + 1} ({description or 'unnamed'!r}) "
                f"has other_expenses of {biz.other_expenses} but no "
                "`other_expenses_description`: Part V must itemize the line 48 "
                "total on the filed form. Set `other_expenses_description` on "
                "that business (e.g. 'Software subscriptions')."
            )
        out["sch_c_line_48_total_other_expenses"] = biz.other_expenses
        # Part V, row 1 = the whole amount (single-aggregate v1: ONE row;
        # multi-row itemization is out of scope), so the total's addend is
        # visible on the paper.
        out["sch_c_part_v_row_1_description"] = item
        out["sch_c_part_v_row_1_amount"] = biz.other_expenses
    out.update(line_values)
    return out
