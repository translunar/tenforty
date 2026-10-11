"""IRS whole-dollar rounding helper.

Per the 1040 instructions, taxpayers who elect to round must round
amounts under 50 cents down and amounts from 50 to 99 cents up to the
next dollar. Python's built-in ``round`` uses banker's rounding
(half-to-even) which diverges from the IRS rule at .5 boundaries —
e.g. ``round(20.5) == 20`` while the IRS expects 21.
"""

import math
from decimal import Decimal, ROUND_HALF_UP, localcontext


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


# Wide enough that no dollars-and-cents amount times a table percentage is
# ever rounded by the multiplication itself (the default context keeps 28
# significant digits; this does not depend on it).
_PRODUCT_PRECISION = 60


def irs_round_product(amount: float, rate: float) -> int:
    """``amount`` x ``rate`` rounded half-up to whole dollars, from the EXACT
    decimal product.

    Use this, never ``irs_round(amount * rate)``, wherever a dollar amount
    is multiplied by a published decimal rate and the result is rounded. A
    binary float cannot hold most decimal fractions exactly, so a product
    that is truly on the half dollar can come out a hair under it and round
    DOWN: 25,000 x 0.0197 is 492.50, but as floats it is 492.49999999999994.

    Each operand is read as the decimal it was written as (``str`` of a
    float is its shortest round-tripping decimal: 0.0197 -> "0.0197"), the
    two are multiplied exactly, and the product is rounded once. A negative
    product rounds half away from zero, as `irs_round` does."""
    with localcontext() as context:
        context.prec = _PRODUCT_PRECISION
        product = Decimal(str(amount)) * Decimal(str(rate))
        return int(product.quantize(Decimal(1), rounding=ROUND_HALF_UP))
