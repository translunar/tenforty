"""Independent reference (oracle) for California Form 100S S-corporation tax.

This module is an AIR-GAPPED, hand-derived reference implementation used to
cross-check a separate production implementation. Every rule and constant below
is derived directly from primary sources -- the official FTB Form 100S booklets
and the California Revenue and Taxation Code (R&TC) -- and is cited inline with a
source URL and a verbatim quote. It intentionally does NOT import from or consult
any other code in this repository; divergence from production is the signal we
want.

Covered tax years: 2021, 2022, 2023, 2024, 2025.

Primary sources (all fetched from ftb.ca.gov / leginfo.legislature.ca.gov):
  - 2021 Form 100S Booklet: https://www.ftb.ca.gov/forms/2021/2021-100s-booklet.pdf
  - 2022 Form 100S Booklet: https://www.ftb.ca.gov/forms/2022/2022-100s-booklet.pdf
  - 2023 Form 100S Booklet: https://www.ftb.ca.gov/forms/2023/2023-100s-booklet.pdf
  - 2024 Form 100S Booklet: https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf
  - 2025 Form 100S Booklet: https://www.ftb.ca.gov/forms/2025/2025-100s-booklet.pdf
  - R&TC Section 23802 (S corporation tax rate):
    https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=23802.
  - R&TC Section 23153 (minimum franchise tax; first-year exemption):
    https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=23153.
"""

from decimal import Decimal, ROUND_HALF_UP


# --- Tax rate ---------------------------------------------------------------
# The S corporation franchise/income tax rate is 1.5% for ALL of tax years
# 2021-2025. The rate constant is identical in each year's booklet.
#
# Source: 2024 Form 100S Booklet, General Information B, "Tax Rate and Minimum
# Franchise Tax" (https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf):
#   "The following tax rates apply to S corporations subject to either the
#    corporation franchise tax or the corporation income tax.
#    * S corporations . . . 1.5%"
# (The identical "S corporations . . . 1.5%" line appears in the 2021, 2022,
#  2023, and 2025 booklets in the same General Information B section.)
#
# Statutory basis -- R&TC Section 23802(b)(1)
# (https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=23802.):
#   "The tax imposed under Section 23151 or 23501 shall be imposed at a rate of
#    1 1/2 percent rather than the rate specified in those sections."
S_CORP_TAX_RATE = Decimal("0.015")


# --- Minimum franchise tax --------------------------------------------------
# The minimum franchise tax is $800 for ALL of tax years 2021-2025, unchanged.
#
# Source: 2024 Form 100S Booklet, General Information B, "Minimum Franchise Tax"
# (https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf):
#   "The minimum franchise tax is $800 and must be paid whether the
#    S corporation is active, inactive, operates at a loss, or files a return
#    for a short-period of less than 12 months."
# (The identical "tax is $800 and must be paid whether the" sentence appears in
#  the 2021, 2022, 2023, and 2025 booklets in the same section.)
#
# Statutory basis -- R&TC Section 23153(d)(1)
# (https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=23153.):
#   "corporations subject to the minimum franchise tax shall pay annually to the
#    state a minimum franchise tax of eight hundred dollars ($800)."
MINIMUM_FRANCHISE_TAX = 800


# --- First-year rule --------------------------------------------------------
# A corporation is NOT subject to the minimum franchise tax for its first
# taxable year; instead it computes its tax purely as rate x net income. This
# rule is identical across 2021-2025.
#
# Source: 2024 Form 100S Booklet, General Information B, "Minimum Franchise Tax"
# (https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf):
#   "A corporation that incorporated or qualified through the California
#    Secretary of State (SOS) to do business in California is not subject to the
#    minimum franchise tax for its first taxable year and will compute its tax
#    liability by multiplying its state net income by the appropriate tax rate.
#    The corporation will become subject to minimum franchise tax beginning in
#    its second taxable year."
# (The identical "first taxable year and will compute its tax liability by
#  multiplying its state net income by the appropriate tax rate" language
#  appears in the 2021, 2022, 2023, and 2025 booklets.)
#
# Statutory basis -- R&TC Section 23153(f)(1)
# (https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=23153.):
#   "every corporation that incorporates or qualifies to do business in this
#    state on or after January 1, 2000, shall not be subject to the minimum
#    franchise tax for its first taxable year."


# --- Rounding ---------------------------------------------------------------
# All amounts on Form 100S are rounded to whole dollars, ties rounded up (away
# from zero). This governs the net income line (Form 100S, Side 2, line 20), the
# tax line (line 21), and every Schedule K-1 (100S) amount, which is part of the
# same return.
#
# Source: 2024 Form 100S Booklet, "When Completing the Form 100S:"
# (https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf):
#   "Round cents to the nearest whole dollar. For example, round $50.50 up to
#    $51 or round $25.49 down to $25."
# (The identical "Round cents to the nearest whole dollar." instruction appears
#  in the 2021, 2022, 2023, and 2025 booklets.)
#
# The example ($50.50 -> $51; $25.49 -> $25) is exactly ROUND_HALF_UP (round to
# nearest, ties away from zero), which is what Decimal's ROUND_HALF_UP provides.

_SUPPORTED_YEARS = (2021, 2022, 2023, 2024, 2025)


def _round_whole_dollar(value) -> int:
    """Round to the nearest whole dollar with ties going away from zero.

    Implements the FTB instruction "Round cents to the nearest whole dollar.
    For example, round $50.50 up to $51 or round $25.49 down to $25."
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def reference_franchise_tax(year: int, net_income: float, first_year: bool) -> int:
    """California Form 100S franchise/income tax, in whole dollars.

    Faithful to Form 100S, Side 2:
      * line 20 = net income for state purposes (entered in whole dollars), and
      * line 21 = 1.5% x line 20, at least the minimum franchise tax if
        applicable (also entered in whole dollars).

    Both lines are whole-dollar amounts, so this rounds twice: once for the net
    income line and once for the computed tax line, using the FTB round-half-up
    (ties away from zero) rule.

    Rules (2021-2025, identical each year):
      * Tax rate is 1.5% of California net income.
      * Non-first-year: tax is the greater of the 1.5% measured tax and the $800
        minimum franchise tax (so a loss/zero-income S corporation still owes
        $800).
      * First taxable year: no minimum franchise tax applies; tax is simply the
        1.5% measured tax. A first-year loss therefore produces $0 of tax (tax
        owed is never negative).
    """
    if year not in _SUPPORTED_YEARS:
        raise ValueError(
            f"year {year} is outside the supported range {_SUPPORTED_YEARS}"
        )

    # Line 20: net income entered in whole dollars.
    net_income_line = _round_whole_dollar(net_income)

    # Line 21: 1.5% x line 20, rounded to whole dollars.
    measured_tax = _round_whole_dollar(S_CORP_TAX_RATE * Decimal(net_income_line))

    if first_year:
        # No minimum franchise tax in the first taxable year; tax cannot be
        # negative, so a loss year yields $0.
        return max(measured_tax, 0)

    # Second and later taxable years: at least the $800 minimum franchise tax.
    return max(measured_tax, MINIMUM_FRANCHISE_TAX)


def reference_k1_share(total: float, fraction: float) -> int:
    """A single shareholder's share of a Schedule K-1 (100S) pass-through amount.

    Each Schedule K-1 (100S) amount is the shareholder's pro-rata share of a
    total S corporation item, allocated by stock ownership, then reported in
    whole dollars.

    Source -- allocation by stock ownership: 2024 Form 100S Booklet,
    "Instructions for Schedule K and Schedule K-1 (100S)"
    (https://www.ftb.ca.gov/forms/2024/2024-100s-booklet.pdf):
      "...they are allocated to the shareholders by their stock ownership."

    Source -- whole-dollar rounding (ties away from zero): same booklet,
    "When Completing the Form 100S:":
      "Round cents to the nearest whole dollar. For example, round $50.50 up to
       $51 or round $25.49 down to $25."
    The Schedule K-1 (100S) is part of the Form 100S return, so this whole-dollar
    rounding rule governs each shareholder's reported share.

    `fraction` is the ownership fraction in [0, 1]. The share is total x fraction,
    rounded to a whole dollar.
    """
    share = Decimal(str(total)) * Decimal(str(fraction))
    return _round_whole_dollar(share)
