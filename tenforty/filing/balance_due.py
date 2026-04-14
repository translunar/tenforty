"""Helper for computing the 4868 line-6 balance-due amount."""

from tenforty.rounding import irs_round


def compute_balance_due(total_tax: float | int, total_payments: float | int) -> int:
    """Balance due = max(0, total_tax - total_payments), rounded to int.

    IRS instructions for Form 4868 line 6 say the result cannot be less than zero
    (overpayments don't turn into negative balance-due — they're a refund, not an
    extension obligation).
    """
    return max(0, irs_round(float(total_tax) - float(total_payments)))
