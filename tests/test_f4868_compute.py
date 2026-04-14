from tenforty.forms.f4868 import compute_balance_due


def test_positive_balance_due():
    assert compute_balance_due(total_tax=5000, total_payments=3000) == 2000


def test_zero_when_overpaid():
    # Refund case: 4868 always reports 0, never a negative balance due.
    assert compute_balance_due(total_tax=3000, total_payments=5000) == 0


def test_zero_when_exactly_matched():
    assert compute_balance_due(total_tax=5000, total_payments=5000) == 0


def test_handles_none_total_payments():
    # Engine may return None for 1099/other withholding fields.
    assert compute_balance_due(total_tax=5000, total_payments=None) == 5000
