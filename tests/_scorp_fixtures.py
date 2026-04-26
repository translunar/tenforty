"""Shared fixtures for Sub-plan 2 / 1120-S tests.

Non-test helper module. The leading underscore prevents pytest from
collecting it as a test file. Tests across Tasks 1-19 import from here
instead of from each other to avoid test-to-test import dependencies.
"""

import datetime

from tenforty.models import (
    AccountingMethod,
    Address,
    FilingStatus,
    Scenario,
    SCorpDeductions,
    SCorpIncome,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpShareholder,
    TaxReturnConfig,
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


def _scorp_attestation_defaults() -> dict[str, bool]:
    """The seven 1120-S-specific attestations Sub-plan 2 introduces, all
    set to True for a v1-profile fixture (sole-shareholder service S-corp,
    under $250k receipts/assets, no §1375/§1374, aggregate COGS/officer
    comp). Returned as a dict so callers can splat with `**`."""
    return {
        "acknowledges_no_1120s_schedule_l_needed": True,
        "acknowledges_no_1120s_schedule_m_needed": True,
        "acknowledges_constant_shareholder_ownership": True,
        "acknowledges_no_section_1375_tax": True,
        "acknowledges_no_section_1374_tax": True,
        "acknowledges_cogs_aggregate_only": True,
        "acknowledges_officer_comp_aggregate_only": True,
        "acknowledges_no_elective_payment_election": True,
    }


def _make_v1_scenario(
    gross_receipts: float = 100000.0,
    compensation_of_officers: float = 30000.0,
    other_deductions: float = 0.0,
) -> Scenario:
    """Build a v1-profile Scenario (single shareholder, all 1120-S attestations
    true). `plan_d_attestation_defaults()` carries safe-default values for all
    23 attestation fields (the 7 1120-S keys default False); merging
    `_scorp_attestation_defaults()` over it lets the 1120-S True values win —
    `validate_load_time` requires every attestation field to be non-None
    regardless of trigger.
    """
    from tests.helpers import plan_d_attestation_defaults
    attestations = {**plan_d_attestation_defaults(), **_scorp_attestation_defaults()}
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="01-01-1980", state="EX",
            first_name="Taxpayer", last_name="A", ssn="000-00-0000",
            **attestations,
        ),
        s_corp_return=SCorpReturn(
            name="Example S-Corp Inc.",
            ein="00-0000000",
            address=_example_address(),
            date_incorporated=datetime.date(2020, 1, 1),
            s_election_effective_date=datetime.date(2020, 1, 1),
            total_assets=50000.0,
            income=SCorpIncome(
                gross_receipts=gross_receipts,
                returns_and_allowances=0.0,
                cogs_aggregate=0.0,
                net_gain_loss_4797=0.0,
                other_income=0.0,
            ),
            deductions=SCorpDeductions(
                compensation_of_officers=compensation_of_officers,
                salaries_wages=0.0,
                repairs_maintenance=0.0,
                bad_debts=0.0,
                rents=0.0,
                taxes_licenses=0.0,
                interest=0.0,
                depreciation=0.0,
                depletion=0.0,
                advertising=0.0,
                pension_profit_sharing_plans=0.0,
                employee_benefits=0.0,
                other_deductions=other_deductions,
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
        ),
    )
