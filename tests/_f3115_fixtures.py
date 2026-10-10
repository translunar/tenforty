"""Synthetic Form 3115 scenario builder shared by the Form 3115 tests.

Every name, address and figure here is invented. The block below is the ONE
answer pattern v1 prints; refusal tests mutate a copy of it.
"""
import copy
import datetime
from pathlib import Path

import yaml

from tenforty.models import Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR

YEAR = 2025

IDENTITY = {
    "first_name": "Marlow",
    "middle_initial": "Q",
    "last_name": "Testcase",
    "ssn": "000-00-0000",
    "address": "410 Fixture Lane",
    "address_city": "Sampleton",
    "address_state": "CA",
    "address_zip": "90000",
    "digital_assets": False,
    # No W-2 source PDFs in a synthetic fixture.
    "acknowledges_no_source_documents": True,
}

ASSET_BUILDING = {
    "description": "Synthetic rental building",
    "property_type": "Residential rental property",
    "date_placed_in_service": datetime.date(2019, 3, 1),
    "use_in_activity": "Held for rental (Schedule E)",
    "tax_credits_or_grants": "None",
    "unadjusted_basis": 240000.0,
    "depreciation_claimed_present_method": 41538.0,
    "present_method": "Straight line",
    "present_recovery_period": "39 years",
    "present_convention": "Mid-month",
    "proposed_method": "Straight line, section 168(b)(3)",
    "proposed_recovery_period": "27.5 years",
    "proposed_convention": "Mid-month",
    "code_section": "168",
    "asset_class": "None assigned (residential rental property)",
    "special_depreciation_allowance_claimed": False,
    "asset_account": "single",
}

ASSET_APPLIANCE = {
    **ASSET_BUILDING,
    "description": "Synthetic appliance set",
    "property_type": "Tangible personal property",
    "date_placed_in_service": datetime.date(2020, 7, 15),
    "unadjusted_basis": 6200.0,
    "depreciation_claimed_present_method": 795.0,
    "present_recovery_period": "39 years",
    "proposed_method": "200% declining balance, section 168(b)(1)",
    "proposed_recovery_period": "5 years",
    "proposed_convention": "Half-year",
    "asset_class": "57.0",
}

BASE_BLOCK = {
    "year_of_change": YEAR,
    "designated_change_number": 7,
    "section_481a_adjustment": 31250.0,
    "elect_one_year_spread": False,
    "tax_year_begins": datetime.date(YEAR, 1, 1),
    "tax_year_ends": datetime.date(YEAR, 12, 31),
    "principal_business_activity_code": "531110",
    "contact_person": "Marlow Q Testcase",
    "contact_phone": "555-0100",
    "applicant_type": "individual",
    "type_of_change": "depreciation_or_amortization",
    "wants_correspondence_by_fax_or_email": False,
    "eligibility_rules_restrict_automatic_change": False,
    "all_required_information_provided": True,
    "ceases_trade_or_terminates_in_year_of_change": False,
    "changing_to_section_381_principal_method": False,
    "under_examination": False,
    "audit_protection_applies": True,
    "before_appeals_or_federal_court": False,
    "prior_method_change_within_five_years": False,
    "pending_ruling_or_method_change_request": False,
    "changing_overall_method": False,
    "proposed_method_used_for_books": True,
    "requests_conference_if_adverse": False,
    "cut_off_basis": False,
    "prior_section_481a_adjustment_remaining": False,
    "adjustment_from_related_party_transactions": False,
    "depreciation_under_cladr": False,
    "depreciation_capitalized_under_another_section": False,
    "depreciation_election_made": False,
    "lived_in_residential_rental_before_renting": False,
    "public_utility_property": False,
    "assets": [ASSET_BUILDING, ASSET_APPLIANCE],
}


def scenario_dict(block: dict | None = None, **config_overrides) -> dict:
    """The raw scenario mapping: tests/fixtures/simple_w2.yaml plus a
    synthetic identity and a `form_3115` block (BASE_BLOCK by default;
    pass ``block`` to substitute a mutated copy, or ``{}``-like values)."""
    data = yaml.safe_load((FIXTURES_DIR / "simple_w2.yaml").read_text())
    data["config"].update(IDENTITY)
    data["config"].update(config_overrides)
    data["form_3115"] = copy.deepcopy(BASE_BLOCK if block is None else block)
    return data


def base_block(**overrides) -> dict:
    block = copy.deepcopy(BASE_BLOCK)
    block.update(overrides)
    return block


def load(tmp_dir: Path, data: dict) -> Scenario:
    """Round-trip ``data`` through a YAML file and the real loader."""
    path = Path(tmp_dir) / "scenario.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_scenario(path)


def orchestrator(tmp_dir: Path) -> ReturnOrchestrator:
    work = Path(tmp_dir) / "work"
    work.mkdir(exist_ok=True)
    return ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR, work_dir=work)
