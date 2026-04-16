from dataclasses import dataclass, field
from datetime import date as _date
from enum import Enum
from typing import Literal


@dataclass
class W2:
    employer: str
    wages: float
    federal_tax_withheld: float
    ss_wages: float
    ss_tax_withheld: float
    medicare_wages: float
    medicare_tax_withheld: float
    state_wages: float = 0.0
    state_tax_withheld: float = 0.0
    local_tax_withheld: float = 0.0


@dataclass
class Form1099INT:
    payer: str
    interest: float
    federal_tax_withheld: float = 0.0
    tax_exempt_interest: float = 0.0


@dataclass
class Form1099DIV:
    payer: str
    ordinary_dividends: float
    qualified_dividends: float = 0.0
    capital_gain_distributions: float = 0.0
    federal_tax_withheld: float = 0.0
    foreign_tax_paid: float = 0.0


@dataclass
class Form1099B:
    broker: str
    description: str
    date_acquired: str
    date_sold: str
    proceeds: float
    cost_basis: float
    gain_loss: float = 0.0
    short_term: bool = True
    basis_reported_to_irs: bool = True
    has_adjustments: bool = False


@dataclass
class Form1098:
    lender: str
    mortgage_interest: float
    property_tax: float = 0.0
    mortgage_insurance_premiums: float = 0.0


@dataclass
class ScheduleK1:
    """A pass-through K-1 normalized into tenforty's unified shape.

    IMPORTANT — per-entity box-number caller contract:
    The caller is responsible for routing K-1 box values into the
    correct dataclass field for the entity type:

    - 1120-S K-1 box 1 ("Ordinary business income") -> ordinary_business_income
    - 1065 K-1 box 1 ("Ordinary business income")   -> ordinary_business_income
    - 1041 K-1 box 1 ("Interest income")            -> interest_income
      (NOT ordinary_business_income -- 1041 box 1 is interest, which fans
      out to Sch B, not Sch E Part II.)

    Validation in tenforty.scenario enforces this by rejecting any
    estate_trust K-1 with nonzero ordinary_business_income at load time.
    """
    entity_name: str
    entity_ein: str
    entity_type: Literal["s_corp", "partnership", "estate_trust"]
    material_participation: bool
    ordinary_business_income: float = 0.0
    net_rental_real_estate: float = 0.0
    other_net_rental: float = 0.0
    interest_income: float = 0.0
    ordinary_dividends: float = 0.0
    qualified_dividends: float = 0.0
    royalties: float = 0.0
    net_short_term_capital_gain: float = 0.0
    net_long_term_capital_gain: float = 0.0
    other_income: float = 0.0
    qbi_amount: float = 0.0
    prior_year_passive_loss_carryforward: float = 0.0
    # Scope-out fields -- non-zero + False attestation raises NotImplementedError:
    section_1231_gain: float = 0.0
    section_179_deduction: float = 0.0
    partnership_self_employment_earnings: float = 0.0


@dataclass
class Form1099G:
    payer: str
    unemployment_compensation: float = 0.0
    state_tax_refund: float = 0.0
    state_tax_refund_tax_year: int | None = None
    federal_tax_withheld: float = 0.0
    rtaa_payments: float = 0.0
    taxable_grants: float = 0.0
    agriculture_payments: float = 0.0
    market_gain: float = 0.0


@dataclass
class RentalProperty:
    address: str
    property_type: int
    fair_rental_days: int
    personal_use_days: int
    rents_received: float
    advertising: float = 0.0
    auto_and_travel: float = 0.0
    cleaning_and_maintenance: float = 0.0
    commissions: float = 0.0
    insurance: float = 0.0
    legal_and_professional_fees: float = 0.0
    management_fees: float = 0.0
    mortgage_interest: float = 0.0
    other_interest: float = 0.0
    repairs: float = 0.0
    supplies: float = 0.0
    taxes: float = 0.0
    utilities: float = 0.0
    depreciation: float = 0.0
    other_expenses: float = 0.0

    @property
    def property_type_code(self) -> str:
        """Schedule E line 1b form code as a string (1..8)."""
        return str(self.property_type)


class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_JOINTLY = "married_jointly"
    MARRIED_SEPARATELY = "married_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"

    @classmethod
    def _missing_(cls, value):
        """Accept common short aliases for filing statuses.

        Oracle reference code and some YAML fixtures use compact forms
        like "mfs" for married_separately. Normalize them here so
        load_scenario and FilingStatus(...) accept either spelling.
        """
        aliases = {
            "mfj": cls.MARRIED_JOINTLY,
            "mfs": cls.MARRIED_SEPARATELY,
            "hoh": cls.HEAD_OF_HOUSEHOLD,
            "qss": cls.QUALIFYING_WIDOW,
            "qw": cls.QUALIFYING_WIDOW,
        }
        if isinstance(value, str):
            return aliases.get(value.lower())
        return None


@dataclass
class TaxReturnConfig:
    year: int
    filing_status: FilingStatus
    birthdate: str
    state: str
    dependents: list[str] = field(default_factory=list)
    first_name: str = ""
    last_name: str = ""
    ssn: str = ""
    spouse_first_name: str = ""
    spouse_last_name: str = ""
    spouse_ssn: str = ""
    address: str = ""
    address_city: str = ""
    address_state: str = ""
    address_zip: str = ""
    # Sch B Part III (FBAR) scope-out attestation. None → scenario omitted it
    # and load_scenario raises; True → raises NotImplementedError; False → OK.
    has_foreign_accounts: bool | None = None
    # Form 8949 scope-out attestation. None → load_scenario raises; True → Sch D
    # compute drops 8949-required lots with a per-lot warning; False → Sch D
    # compute raises NotImplementedError on any 8949-required lot.
    acknowledges_form_8949_unsupported: bool | None = None
    # Sch A line 5a scope-out attestation. None → load_scenario raises. True →
    # scenario accepts the state-income-tax-only 5a path (sch_a.compute logs
    # INFO if state is in the no-income-tax set). False → sch_a.compute raises
    # NotImplementedError when state is in the no-income-tax set AND
    # itemizing would apply, preventing silent under/over-deduction.
    acknowledges_sch_a_sales_tax_unsupported: bool | None = None
    # --- Plan D scope-out attestations (9 unconditional + 1 factual bool) ---
    # All are `bool | None = None`; load_scenario raises ValueError if any is
    # left as None. Compute-time gates fire only when the predicate condition
    # is actually met (e.g., a K-1 is present, a nonzero field exists, etc.).
    # Form 8995-A (QBI full) is out of scope; True + above-threshold raises
    # at compute time.
    acknowledges_qbi_below_threshold: bool | None = None
    # Form 6198 (at-risk limits) is out of scope; any K-1 + False raises.
    acknowledges_unlimited_at_risk: bool | None = None
    # Basis tracking worksheets are out of scope; any K-1 + False raises.
    basis_tracked_externally: bool | None = None
    # Schedule SE is out of scope; partnership K-1 with nonzero
    # partnership_self_employment_earnings + False raises.
    acknowledges_no_partnership_se_earnings: bool | None = None
    # Form 4797 is out of scope; any K-1 with nonzero section_1231_gain +
    # False raises.
    acknowledges_no_section_1231_gain: bool | None = None
    # Sch E Part II continuation is out of scope; >4 K-1s + False raises.
    acknowledges_no_more_than_four_k1s: bool | None = None
    # K-1 box 13 / box 15 credits are out of scope; False + K-1 present at
    # compute time raises.
    acknowledges_no_k1_credits: bool | None = None
    # Section 179 deduction is out of scope; any K-1 with nonzero
    # section_179_deduction + False raises.
    acknowledges_no_section_179: bool | None = None
    # Sch E Part III (estate/trust income) is out of scope; any K-1 with
    # entity_type == "estate_trust" will raise NotImplementedError at compute
    # regardless of this value, but the attestation must still be declared
    # at load time.
    acknowledges_no_estate_trust_k1: bool | None = None
    # Factual input (not an attestation): drives 1099-G state-refund
    # tax-benefit-rule compute. None at load raises.
    prior_year_itemized: bool | None = None
    # --- Plan D conditional fields (validated only when sibling is set) ---
    # Required only when filing_status == MARRIED_SEPARATELY. Per IRC §469(i)(5),
    # MFS filers who lived with a spouse at any time during the year have a
    # $0 Form 8582 special allowance for rental real estate.
    mfs_lived_with_spouse_any_time: bool | None = None
    # Required only when prior_year_itemized is True. Used by state-refund
    # tax-benefit-rule (Sch 1 line 1) to cap taxable recovery.
    prior_year_itemized_deduction_amount: float | None = None
    # Required only when prior_year_itemized is True. Used to compute the
    # recovery limit (itemized_amount - standard_amount).
    prior_year_standard_deduction_amount: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.filing_status, str):
            self.filing_status = FilingStatus(self.filing_status)


@dataclass
class ItemizedDeductions:
    medical_expenses: float = 0.0
    state_income_tax: float = 0.0
    property_tax: float = 0.0
    mortgage_interest: float = 0.0
    charitable_contributions: float = 0.0


@dataclass
class DepreciableAsset:
    """An asset subject to MACRS depreciation (Form 4562 Part III row).

    ``recovery_class`` is the GDS class-life string ("3-year", "5-year",
    "7-year", "10-year", "15-year", "20-year", "27.5-year", "39-year").
    ``convention`` is one of "half-year", "mid-quarter", "mid-month"
    (mid-quarter unsupported in v1). ``disposed``, when not None,
    triggers NotImplementedError in v1 compute.
    """

    description: str
    date_placed_in_service: _date
    basis: float
    recovery_class: str
    convention: str
    disposed: _date | None = None


@dataclass
class Scenario:
    config: TaxReturnConfig
    w2s: list[W2] = field(default_factory=list)
    form1099_int: list[Form1099INT] = field(default_factory=list)
    form1099_div: list[Form1099DIV] = field(default_factory=list)
    form1099_b: list[Form1099B] = field(default_factory=list)
    form1099_g: list[Form1099G] = field(default_factory=list)
    form1098s: list[Form1098] = field(default_factory=list)
    schedule_k1s: list[ScheduleK1] = field(default_factory=list)
    rental_properties: list[RentalProperty] = field(default_factory=list)
    depreciable_assets: list[DepreciableAsset] = field(default_factory=list)
    itemized_deductions: ItemizedDeductions | None = None
