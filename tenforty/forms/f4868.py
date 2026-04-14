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


def compute(scenario, upstream: dict[str, dict]) -> dict:
    """Compute Form 4868 fields in PDF-ready shape.

    `scenario` supplies identity and address fields. `upstream["f1040"]`
    supplies `total_tax` and `total_payments`; compute derives balance-due
    (floored at zero) and renames `total_tax` -> `estimated_total_tax` to
    match the 4868 PDF line names.
    """
    f1040 = upstream.get("f1040", {})
    config = scenario.config
    balance = compute_balance_due(
        f1040.get("total_tax"), f1040.get("total_payments")
    )
    return {
        "full_name": f"{config.first_name} {config.last_name}".strip(),
        "ssn": config.ssn,
        "spouse_ssn": config.spouse_ssn,
        "address": config.address,
        "address_city": config.address_city,
        "address_state": config.address_state,
        "address_zip": config.address_zip,
        "estimated_total_tax": f1040.get("total_tax", 0),
        "total_payments": f1040.get("total_payments", 0),
        "balance_due": balance,
        "amount_paying_with_extension": 0,
        "voucher_amount": balance,
    }
