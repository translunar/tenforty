"""Schedule C -- Profit or Loss From Business (sole proprietorship).

Compute-first, per-business, ending in net profit (line 31). PDF mapping is a
follow-on unit; keys are named by form line so mapping adds no compute change.

v1 scope: gross receipts (line 1/7) minus deductible Part II expense categories
(line 28) -> tentative profit (line 29) -> net profit (line 31). Cost of goods
sold / inventory (Part III), depreciation (line 13), home office (Form 8829,
line 30), vehicle expenses, depletion (line 12), returns & allowances (line 2),
and the statutory-employee flag are UNMODELED and refuse loudly (nonzero ->
NotImplementedError) -- there is no correct net profit for those inputs without
the unmodeled math, so fail closed rather than silently drop them.
"""
from tenforty.models import Scenario, ScheduleCBusiness
from tenforty.rounding import irs_round

# The 12 Part II expense categories (Schedule C lines 8-27a) a P&L export
# covers. SINGLE SOURCE OF TRUTH: line_28 (below) sums exactly these, and
# `net_profit_estimate` subtracts exactly these -- keeping the total and the
# routing-gate estimate from drifting apart (the partial-total failure this
# tuple prevents from recurring).
_EXPENSE_FIELDS = (
    "advertising", "insurance", "legal_professional", "office_expense",
    "rent_lease", "supplies", "taxes_licenses", "travel", "deductible_meals",
    "utilities", "wages", "other_expenses",
)


def net_profit_estimate(biz: ScheduleCBusiness) -> float:
    """Cheap net-profit estimate for the EIC-scope routing gate.

    Returns ``gross_receipts - sum(the 12 Part II expense categories)``. This is
    a NON-RAISING pre-compute estimate: it has NO refusal guards (no net-loss /
    unmodeled-feature checks) BECAUSE it runs BEFORE ``compute`` fires those
    refusals -- the routing gate must be able to estimate income for any input,
    including one that ``compute`` will later refuse. Uses `_EXPENSE_FIELDS` so
    the estimate can never drift from the line-28 total.
    """
    return biz.gross_receipts - sum(getattr(biz, f) for f in _EXPENSE_FIELDS)


_REFUSED_AMOUNT_FIELDS = (
    ("cost_of_goods_sold", "Part III cost of goods sold"),
    ("inventory", "Part III inventory"),
    ("depreciation", "line 13 depreciation / §179"),
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


def _compute_business(biz: ScheduleCBusiness, idx: int) -> dict:
    _guard_unmodeled(biz, idx)
    # Line 7 gross income = gross receipts (returns/allowances and COGS are
    # refused above, so both are 0 here by construction).
    line_7 = biz.gross_receipts
    line_28 = sum(getattr(biz, f) for f in _EXPENSE_FIELDS)
    line_29 = line_7 - line_28           # tentative profit
    line_31 = line_29                    # line 30 home office refused -> 0
    if line_31 < 0:
        raise NotImplementedError(
            f"Schedule C business #{idx} ({biz.description!r}) computes a net LOSS "
            f"(line 31 = {line_31:.0f}). A Schedule C loss triggers the at-risk "
            f"limitation (Form 6198 / line 32), QBI negative-component netting "
            f"(Form 8995), and the §461(l) excess-business-loss limitation -- none "
            f"modeled in tenforty v1. This return cannot be produced by v1."
        )
    return {
        "sch_c_line_7_gross_income": irs_round(line_7),
        "sch_c_line_28_total_expenses": irs_round(line_28),
        "sch_c_line_29_tentative_profit": irs_round(line_29),
        "sch_c_line_31_net_profit": irs_round(line_31),
    }


def compute(scenario: Scenario, upstream: dict) -> dict:
    businesses = scenario.schedule_c_businesses
    if not businesses:
        return {}
    per_business = [_compute_business(b, i) for i, b in enumerate(businesses)]
    total = sum(b["sch_c_line_31_net_profit"] for b in per_business)
    return {
        "sch_c_businesses": per_business,
        "sch_c_line_31_net_profit_total": irs_round(total),
    }
