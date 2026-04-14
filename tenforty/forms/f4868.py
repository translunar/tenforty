"""Form 4868 (Automatic Extension) compute.

Folds in the balance-due helper formerly at tenforty/filing/balance_due.py.
The 4868 line 6 balance due is clamped at zero: if payments >= tax, the
form reports no balance due (even for a refund case).
"""


def compute_balance_due(total_tax, total_payments) -> int:
    """Compute 4868 line 6 balance due, floored at zero.

    `total_tax` and `total_payments` come from the 1040 compute. Either
    may be `None` if the engine did not emit them; treat as 0.
    """
    tax = total_tax or 0
    payments = total_payments or 0
    balance = tax - payments
    return balance if balance > 0 else 0
