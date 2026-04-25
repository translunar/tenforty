"""Shared fixtures for Sub-plan 2 / 1120-S tests.

Non-test helper module. The leading underscore prevents pytest from
collecting it as a test file. Tests across Tasks 1-19 import from here
instead of from each other to avoid test-to-test import dependencies.
"""

import datetime

from tenforty.models import (
    AccountingMethod,
    Address,
    SCorpDeductions,
    SCorpIncome,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpShareholder,
)


def _example_address() -> Address:
    return Address(
        street="1 Example Ave",
        city="Example City",
        state="EX",
        zip_code="00000",
    )


def _make_scorp_return() -> SCorpReturn:
    return SCorpReturn(
        name="Example S-Corp Inc.",
        ein="00-0000000",
        address=_example_address(),
        date_incorporated=datetime.date(2020, 1, 1),
        s_election_effective_date=datetime.date(2020, 1, 1),
        total_assets=50000.0,
        income=SCorpIncome(100000.0, 0.0, 0.0, 0.0, 0.0),
        deductions=SCorpDeductions(
            30000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ),
        schedule_b_answers=SCorpScheduleBAnswers(
            accounting_method=AccountingMethod.CASH,
            business_activity_code="541990",
            business_activity_description="Services",
            product_or_service="Consulting",
            any_c_corp_subsidiaries=False,
            has_any_foreign_shareholders=False,
            owns_foreign_entity=False,
        ),
        shareholders=[
            SCorpShareholder(
                name="Taxpayer A",
                ssn_or_ein="000-00-0000",
                address=_example_address(),
                ownership_percentage=100.0,
            ),
        ],
    )
