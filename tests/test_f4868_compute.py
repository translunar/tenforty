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


from types import SimpleNamespace

from tenforty.forms.f4868 import compute


def _scenario(**overrides):
    config = SimpleNamespace(
        first_name="Ada",
        last_name="Lovelace",
        ssn="000-45-6789",
        spouse_ssn="",
        address="1 Analytical Engine Way",
        address_city="London",
        address_state="",
        address_zip="",
        **overrides,
    )
    return SimpleNamespace(config=config)


def test_f4868_compute_produces_pdf_ready_keys():
    scenario = _scenario()
    upstream = {"f1040": {"total_tax": 5000, "total_payments": 3000}}
    result = compute(scenario, upstream)
    assert result["full_name"] == "Ada Lovelace"
    assert result["ssn"] == "000-45-6789"
    assert result["spouse_ssn"] == ""
    assert result["address"] == "1 Analytical Engine Way"
    assert result["address_city"] == "London"
    assert result["address_state"] == ""
    assert result["address_zip"] == ""
    assert result["estimated_total_tax"] == 5000
    assert result["total_payments"] == 3000
    assert result["balance_due"] == 2000
    assert result["amount_paying_with_extension"] == 0
    assert result["voucher_amount"] == 2000


def test_f4868_compute_refund_case_zeroes_balance():
    scenario = _scenario()
    upstream = {"f1040": {"total_tax": 3000, "total_payments": 5000}}
    result = compute(scenario, upstream)
    assert result["balance_due"] == 0
    assert result["voucher_amount"] == 0
