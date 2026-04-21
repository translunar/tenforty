from dataclasses import dataclass, field
from datetime import date as _date
from enum import Enum


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
    entity_type: EntityType
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

    def __post_init__(self) -> None:
        # YAML loaders yield plain strings; coerce to the typed enum so all
        # downstream comparisons work against EntityType members, not raw strings.
        if isinstance(self.entity_type, str):
            self.entity_type = EntityType(self.entity_type)


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


class EntityType(str, Enum):
    """Pass-through entity type carried on ScheduleK1. YAML fixtures yield
    strings; str-Enum lets them compare equal to their value string and
    round-trip through a YAML boundary without a custom resolver."""
    S_CORP = "s_corp"
    PARTNERSHIP = "partnership"
    ESTATE_TRUST = "estate_trust"


class AccountingMethod(str, Enum):
    """Entity-level accounting method. Declared now for Sub-plan 2's 1120-S
    Schedule B; no Pass 1 consumer."""
    CASH = "cash"
    ACCRUAL = "accrual"
    OTHER = "other"


@dataclass(frozen=True)
class PayerAmount:
    """A payer-and-amount line item — K-1-derived Sch B interest/dividend
    additions, and any place where income is attributed to a named source.

    Replaces the 2-tuple / 2-key-dict {"payer", "amount"} shape that flowed
    through multiple forms in Plan D."""
    payer: str
    amount: float


@dataclass(frozen=True)
class K1FanoutActivity:
    """One passive-activity row for Form 8582 and related passive-loss
    predicates. Populated by sch_e_part_ii.compute for every K-1 whose
    material_participation is False.

    Sign convention: income, loss, and prior_carryforward are all positive
    magnitudes (>= 0). The loss field being nonzero is itself the direction
    signal — consumers do not negate."""
    entity_name: str
    entity_ein: str
    entity_type: "EntityType"
    income: float
    loss: float
    prior_carryforward: float


@dataclass(frozen=True)
class K1FanoutData:
    """Typed sidecar result of sch_e_part_ii.compute. Replaces the
    underscore-prefixed `_k1_fanout` dict that Plan D threaded through
    upstream. Consumers (sch_b, sch_d, f8995, f8582) read fields by name,
    not by positional index or string key.

    qualified_dividends_aggregate matches what Plan D called "qualified_dividends_total"
    in the old sidecar dict — renamed here to match the "aggregate" suffix
    used by qbi_aggregate for consistency."""
    sch_b_interest_additions: tuple[PayerAmount, ...]
    sch_b_dividend_additions: tuple[PayerAmount, ...]
    sch_d_short_term_additions: tuple[float, ...]
    sch_d_long_term_additions: tuple[float, ...]
    qbi_aggregate: float
    qualified_dividends_aggregate: float
    passive_activities: tuple[K1FanoutActivity, ...]

    @classmethod
    def empty(cls) -> "K1FanoutData":
        """Returned when no K-1s are present so downstream consumers can
        unconditionally read upstream['k1_fanout'] without guarding every
        access."""
        return cls(
            sch_b_interest_additions=(),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(),
            sch_d_long_term_additions=(),
            qbi_aggregate=0.0,
            qualified_dividends_aggregate=0.0,
            passive_activities=(),
        )


@dataclass(frozen=True)
class VoluntaryContribution:
    """A single CA 540 voluntary-contribution line item. Declared in Pass 1
    for Sub-plan 3's CA540PersonalOverlay; no Pass 1 consumer.

    fund_code follows FTB-defined fund abbreviations (e.g. "WLD" = California
    Seniors Special Fund; "KID" = Child Victims of Human Trafficking Fund).
    """
    fund_code: str
    amount: float


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

    @property
    def full_name(self) -> str:
        """Single source of 'First Last' formatting consumed by every form's
        PDF-header emission. Stripped at each half so trailing whitespace in
        one field doesn't leave a stray space when the other is empty."""
        first = self.first_name.strip()
        last = self.last_name.strip()
        return f"{first} {last}".strip()


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
