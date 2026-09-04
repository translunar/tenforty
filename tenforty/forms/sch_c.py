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
    line_28 = (biz.advertising + biz.insurance + biz.legal_professional
               + biz.office_expense + biz.rent_lease + biz.supplies
               + biz.taxes_licenses + biz.travel + biz.deductible_meals
               + biz.utilities + biz.wages + biz.other_expenses)
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
