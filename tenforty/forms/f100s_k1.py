"""California Schedule K-1 (100S) — per-shareholder allocation of the S
corporation's CA items.

Mirrors the federal Schedule K-1 (1120-S) allocation machinery
(forms/f1120s._compute_schedule_k1_allocations): each shareholder's CA
ordinary income is their pro-rata share (by ownership percentage) of the
Form 100S net income for tax, and the federal column mirrors the federal
K-1 box 1 share. Same plain pro-rata convention as the federal allocator
(no rounding, no residual-to-largest), so the CA and federal columns foot
by construction.
"""


def compute(scenario, upstream) -> dict:
    federal_allocs = upstream["f1120s"]["f1120s_sch_k1_allocations"]
    ca_net_income = upstream["f100s"]["f100s_net_income_for_tax"]
    allocations = []
    for index, alloc in enumerate(federal_allocs):
        fraction = alloc.ownership_percentage / 100.0
        allocations.append({
            "shareholder_index": index,
            "ownership_fraction": fraction,
            "federal_ordinary_income": alloc.box_1_ordinary_business_income,
            "ca_ordinary_income": ca_net_income * fraction,
        })
    return {"f100s_k1_allocations": allocations}
