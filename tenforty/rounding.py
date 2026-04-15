"""IRS whole-dollar rounding helper.

Per the 1040 instructions, taxpayers who elect to round must round
amounts under 50 cents down and amounts from 50 to 99 cents up to the
next dollar. Python's built-in ``round`` uses banker's rounding
(half-to-even) which diverges from the IRS rule at .5 boundaries —
e.g. ``round(20.5) == 20`` while the IRS expects 21.
"""

import math
from decimal import Decimal, ROUND_HALF_UP


def irs_round(amount: float) -> int:
    """Round to the nearest whole dollar using the IRS half-up convention."""
    if amount >= 0:
        return math.floor(amount + 0.5)
    return -math.floor(-amount + 0.5)


def round4(amount: float) -> float:
    """Quantize to 4 decimal places using IRS / Pub 946 half-up rounding.

    Used by the MACRS A-1 (200%-DB) table generator — published to 4
    places in Pub 946 Appendix A. Reusable for any 4-decimal quantize.
    """
    return float(Decimal(repr(amount)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def round5(amount: float) -> float:
    """Quantize to 5 decimal places using IRS / Pub 946 half-up rounding.

    Used by the MACRS A-6 / A-7a (mid-month SL real-property) table
    generators — published to 5 places in Pub 946 Appendix A. Reusable
    for any 5-decimal quantize.
    """
    return float(Decimal(repr(amount)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP))
