"""IRS whole-dollar rounding helper.

Per the 1040 instructions, taxpayers who elect to round must round
amounts under 50 cents down and amounts from 50 to 99 cents up to the
next dollar. Python's built-in ``round`` uses banker's rounding
(half-to-even) which diverges from the IRS rule at .5 boundaries —
e.g. ``round(20.5) == 20`` while the IRS expects 21.
"""

import math


def irs_round(amount: float) -> int:
    """Round to the nearest whole dollar using the IRS half-up convention."""
    if amount >= 0:
        return math.floor(amount + 0.5)
    return -math.floor(-amount + 0.5)
