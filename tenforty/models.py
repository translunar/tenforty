from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


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
    # CA-withholding channel, schema layer: which state this W-2's box-17
    # `state_tax_withheld` was withheld to. None means "not attributed" --
    # fine for a non-CA return, but a California Form 540 return refuses
    # (see Scenario.__post_init__) if a withholding W-2 is left unattributed,
    # since only CA-attributed withholding may be claimed on 540 line 71.
    # Deliberately NOT normalized/coerced (no lowercasing) -- loud refusal on
    # garbage input rather than silent correction.
    state: str | None = None
    # Path to this W-2's evidence document — normally the employer-issued
    # Copy B PDF, or a Form 4852 substitute when the issuer copy is missing.
    # Resolved relative to the scenario YAML's directory at load. Optional at
    # the schema layer BY DESIGN: compute-only scenarios never produce filing
    # packets and must not carry attachment paths. The mandatory-ness lives
    # at the packet-emit gate (acknowledges_no_source_documents) — do not
    # tighten this field.
    pdf: str | None = None

    def __post_init__(self) -> None:
        if self.state is not None and (
            len(self.state) != 2
            or not self.state.isascii()
            or not self.state.isalpha()
            or not self.state.isupper()
        ):
            raise ValueError(
                f"W2.state must be None or a 2-letter uppercase state code "
                f"(e.g. 'CA'), got {self.state!r}."
            )


@dataclass(frozen=True)
class SourceDocument:
    """A real issued document (W-2 Copy B today) spliced into filing packets.

    Normalized at load from `W2.pdf`: `path` is resolved+validated,
    `packets` is derived from the W-2's own declared data (see
    scenario._load_source_documents). tenforty never parses the document's
    contents — this record exists purely for packet assembly.
    """

    path: Path
    kind: str  # only "w2" this round; future modeled types add kinds
    packets: tuple[str, ...]  # pdf_packet packet names


@dataclass
class Form1099INT:
    payer: str
    interest: float
    federal_tax_withheld: float = 0.0
    # NOT consumed by the spine — Form 1040 line 2a (tax-exempt interest) is
    # unmodeled. For Premium Tax Credit MAGI, the sanctioned knob is
    # Form1095A.tax_exempt_interest. A guard in orchestrator
    # ._compute_native_schedules Step 7b refuses if this field is nonzero
    # together with a Form 1095-A. Do not wire this field into PTC MAGI
    # additively without revisiting that guard (double-count risk).
    tax_exempt_interest: float = 0.0


@dataclass
class Form1099DIV:
    payer: str
    ordinary_dividends: float
    qualified_dividends: float = 0.0
    capital_gain_distributions: float = 0.0
    federal_tax_withheld: float = 0.0
    foreign_tax_paid: float = 0.0


_LOT_ADJUSTMENT_FIELDS: tuple[str, ...] = (
    "wash_sale_loss_disallowed",
    "other_basis_adjustment",
    "is_28_rate_collectible",
    "is_section_1250",
)


@dataclass
class Form1099B:
    broker: str
    description: str
    date_acquired: str
    date_sold: str
    proceeds: float
    cost_basis: float
    short_term: bool = True
    basis_reported_to_irs: bool = True
    # Per-IRS-instruction lot-level adjustment fields. Any nonzero/True is
    # gated by its corresponding _ATTESTATIONS entry — ack=False + nonzero
    # raises NotImplementedError at compute time. Both signed per IRS
    # Form 8949 col (g) convention (positive increases gain, negative
    # decreases); wash-sale disallowed loss (code W) is always entered
    # positive, other_basis_adjustment (code O) is user-signed.
    wash_sale_loss_disallowed: float = 0.0
    other_basis_adjustment: float = 0.0
    is_28_rate_collectible: bool = False
    is_section_1250: bool = False

    @property
    def has_adjustments(self) -> bool:
        return any(getattr(self, f) for f in _LOT_ADJUSTMENT_FIELDS)

    @property
    def gain_loss(self) -> float:
        return (self.proceeds - self.cost_basis
                + self.other_basis_adjustment
                + self.wash_sale_loss_disallowed)


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


@dataclass(frozen=True)
class ScheduleCBusiness:
    """Sole-proprietor Schedule C businesses; each is one Schedule C.

    Expense fields are Part II categories a P&L export covers. COGS/inventory,
    depreciation, home office, vehicle, depletion, returns & allowances, and
    statutory-employee are UNMODELED -- nonzero refuses at compute (see
    forms/sch_c.py).
    """
    description: str = ""
    # Schedule C line B: the 6-digit principal business or professional
    # activity code. Printed verbatim; blank prints nothing.
    business_code: str = ""
    gross_receipts: float = 0.0
    # Part II expense categories (Schedule C lines 8-27a) a P&L export covers.
    advertising: float = 0.0
    insurance: float = 0.0
    legal_professional: float = 0.0
    office_expense: float = 0.0
    rent_lease: float = 0.0
    supplies: float = 0.0
    taxes_licenses: float = 0.0
    travel: float = 0.0
    deductible_meals: float = 0.0
    utilities: float = 0.0
    wages: float = 0.0
    other_expenses: float = 0.0
    # Schedule C Part V itemization: ONE aggregate row (description + amount ==
    # `other_expenses`). Required at EMIT when other_expenses is nonzero (the
    # paper form needs it); compute does not look at it. Multi-row
    # itemization is out of scope for v1.
    other_expenses_description: str = ""
    # UNMODELED features. A nonzero value here is refused at COMPUTE time (Task
    # 2, forms/sch_c.py) -- there is no correct net profit without the unmodeled
    # math, so fail closed rather than silently drop the input. This input model
    # carries them so the refusal has something to see; it does not enforce here.
    cost_of_goods_sold: float = 0.0
    inventory: float = 0.0
    depreciation: float = 0.0
    home_office: float = 0.0
    vehicle_expenses: float = 0.0
    depletion: float = 0.0
    returns_and_allowances: float = 0.0
    statutory_employee: bool = False


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
    through multiple forms before typed dataclasses were adopted."""
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
    """Typed sidecar produced by sch_e_part_ii.compute, carrying K-1-derived
    additions consumed by downstream form computes (sch_b, sch_d, f8995,
    f8582). Fields are read by name, not by positional index or string key.

    qualified_dividends_aggregate is aggregated from K-1s using the same
    "aggregate" suffix convention as qbi_aggregate for consistency."""
    sch_b_interest_additions: tuple[PayerAmount, ...]
    sch_b_dividend_additions: tuple[PayerAmount, ...]
    sch_d_short_term_additions: tuple[float, ...]
    sch_d_long_term_additions: tuple[float, ...]
    qbi_aggregate: float
    # K-1-ONLY COMPONENT of 1040 line 3a (qualified dividends) — NOT the
    # line 3a total. Line 3a also has a 1099-DIV box 1b component. This
    # field is summed once, here, from the K-1s' box 5b amounts, and
    # consumed exactly once: by compute_income_preamble
    # (tenforty/forms/f1040_spine.py), which adds it to the 1099-DIV
    # component to build the authoritative `qualified_divs_total`. Form
    # consumers (Form 8995 line 12; the QDCGT preferential-rate base) MUST
    # read that preamble total, never this field directly. A form never
    # sees an IncomePreamble object — the concrete idiom is to read the
    # total off the upstream stub the orchestrator builds, e.g.
    # `upstream["f1040"]["qualified_dividends"]` (see
    # tenforty/forms/f8995.py). Reading THIS field directly is exactly the
    # defect this unit (2026-08-14 f8995-line12-total-qualdivs) fixed: Form
    # 8995 line 12 silently dropped every 1099-DIV qualified dividend, and
    # the QDCGT worksheet taxed a K-1's qualified dividends as ordinary
    # income.
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
    # Middle initial: printed after the first name wherever a form shows the
    # name. Blank stays blank on the form (not a gate).
    middle_initial: str = ""
    ssn: str = ""
    spouse_first_name: str = ""
    spouse_last_name: str = ""
    spouse_middle_initial: str = ""
    spouse_ssn: str = ""
    address: str = ""
    address_city: str = ""
    address_state: str = ""
    address_zip: str = ""
    # CA Form 540 Side 1 "address above is the same as your principal/physical
    # residence address at the time of filing" box. False means UNSTATED: the
    # box is simply left unchecked (the separate physical-residence address
    # block is not modeled, so it cannot be filled either way).
    address_is_principal_residence: bool = False
    # CA Form 540 Side 1 "county at time of filing" (principal residence).
    # Free text; blank stays blank on the form (not a gate).
    county: str = ""
    # Form 1040 digital-assets question (2021: virtual currency). None means
    # UNANSWERED. Unlike the scope-out attestations below it is NOT required at
    # load time and NOT required by the native compute path (a compute-only
    # run never prints the question); it is required at PDF EMIT time for tax
    # year 2022 onward, where the orchestrator refuses an unanswered question
    # rather than print a signed return with the box left blank. True/False
    # check the form's Yes/No box.
    digital_assets: bool | None = None
    # Form 1040 (and CA 540) third party designee: "Do you want to allow another
    # person to discuss this return with the IRS / us?". None = unstated (1040
    # box blank). False checks "No". True is REFUSED (NotImplementedError): the
    # designee name / phone / PIN cells are unmodeled. The CA 540 already
    # hardwires "No" in its presentation layer; this field only gates True.
    third_party_designee: bool | None = None
    # Schedule E page 1 lines A and B (federal TY2022+): "Did you make any
    # payments that would require you to file Form(s) 1099?" and "If 'Yes,' did
    # you or will you file required Form(s) 1099?". None = UNSTATED (boxes left
    # blank). payments False -> line A "No", line B stays blank (filed_required
    # must then be unstated); payments True -> line A "Yes" and filed_required
    # is REQUIRED. See ``validate_sche_1099_answers``. (Distinct from the
    # S-corp Schedule B answers of the same names under s_corp_return.)
    payments_requiring_1099s: bool | None = None
    filed_required_1099s: bool | None = None
    # CA Form 540 line 92 "you and your household had full-year health care
    # coverage" box (the individual-mandate attestation). None means UNSTATED.
    # Like digital_assets it is NOT required at load time or by the compute
    # path; it is required at CA PDF EMIT time, where the orchestrator refuses
    # an unstated answer rather than print a signed 540 with the box blank and
    # no penalty. True checks the box. False is a coverage gap: the Individual
    # Shared Responsibility penalty (FTB 3853) is not modeled, so the CA
    # forms layer raises NotImplementedError instead of assuming a 0 penalty.
    full_year_health_care_coverage: bool | None = None
    # Sch B Part III (FBAR) scope-out attestation. None → scenario omitted it
    # and load_scenario raises; True → raises NotImplementedError; False → OK.
    has_foreign_accounts: bool | None = None
    # Sch A line 5a scope-out attestation. None → load_scenario raises. True →
    # scenario accepts the state-income-tax-only 5a path (sch_a.compute logs
    # INFO if state is in the no-income-tax set). False → sch_a.compute raises
    # NotImplementedError when state is in the no-income-tax set AND
    # itemizing would apply, preventing silent under/over-deduction.
    acknowledges_sch_a_sales_tax_unsupported: bool | None = None
    # --- K-1 scope-out attestations (9 unconditional + 1 factual bool) ---
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
    # --- Form 8949 scope-out attestations ---
    # Any 1099-B lot with nonzero wash_sale_loss_disallowed + False raises.
    acknowledges_no_wash_sale_adjustments: bool | None = None
    # Any 1099-B lot with nonzero other_basis_adjustment + False raises.
    acknowledges_no_other_basis_adjustments: bool | None = None
    # Any 1099-B lot with is_28_rate_collectible=True + False raises.
    acknowledges_no_28_rate_gain: bool | None = None
    # Any 1099-B lot with is_section_1250=True + False raises.
    acknowledges_no_unrecaptured_section_1250: bool | None = None
    # --- Schedule D prior-year capital-loss carryover scope-out ---
    # True affirms the filer has NO prior-year capital-loss carryforward.
    # False means one EXISTS: Sch D line 6 (short-term carryover) and line 14
    # (long-term carryover) are not modeled in tenforty v1, so compute REFUSES
    # unconditionally rather than silently treating the carryover as zero.
    # Unlike the 1099-B gates above this has no data-derived trigger — the
    # attestation itself is the only signal, so its trigger is `_always`.
    acknowledges_no_capital_loss_carryforward: bool | None = None
    # --- Federal alternative minimum tax (Form 6251) scope-out ---
    # True affirms the filer owes NO federal AMT. False means AMT may apply:
    # there is no Form 6251 anywhere in tenforty's native path, so AMT
    # (Schedule 2 line 1, flowing to 1040 line 17 -> line 18 -> line 24) is
    # silently zero and the computed tax is UNDERSTATED. Like the carryforward
    # gate above it has no data-derived trigger; the registry entry in
    # `attestations._ALWAYS_TAIL` records why the shape is `_always`.
    acknowledges_no_federal_amt: bool | None = None
    # Schedule C line 32 (at-risk). A business with a net loss must say
    # whether all of its investment is at risk (box 32a) or not (box 32b,
    # Form 6198 -- unmodeled). True affirms 32a for every loss business;
    # False + any Schedule C net loss refuses in forms/sch_c.py.
    acknowledges_sch_c_all_investment_at_risk: bool | None = None
    # Schedule E line 28 column (e): an S corporation loss requires the
    # shareholder's basis computation (Form 7203) to be attached. tenforty
    # does not produce Form 7203. True affirms it is prepared by hand and
    # attached; False + an S-corp K-1 net-loss row refuses. Distinct from
    # `basis_tracked_externally`, which attests the tracking, not the
    # attachment.
    acknowledges_form_7203_attached_separately: bool | None = None
    # --- 1120-S scope-out attestations (8 unconditional) ---
    # Sch L (balance sheet) is out of scope; total_assets >= $250,000 OR
    # gross_receipts >= $250,000 + False raises.
    acknowledges_no_1120s_schedule_l_needed: bool | None = None
    # Sch M-1 (book/tax reconciliation) and Sch M-2 (AAA) are out of scope;
    # same gate as Sch L (total_assets or gross_receipts >= $250,000) +
    # False raises.
    acknowledges_no_1120s_schedule_m_needed: bool | None = None
    # Mid-year shareholder ownership changes are out of scope; required at
    # load time so the user affirms ownership percentages are constant for
    # the full tax year.
    acknowledges_constant_shareholder_ownership: bool | None = None
    # §1375 Excess Net Passive Income Tax is out of scope; caller supplies
    # the amount on s_corp_return.scope_outs.net_passive_income_tax. Nonzero
    # + False raises.
    acknowledges_no_section_1375_tax: bool | None = None
    # §1374 Built-in Gains Tax is out of scope; caller supplies the amount
    # on s_corp_return.scope_outs.built_in_gains_tax. Nonzero + False raises.
    acknowledges_no_section_1374_tax: bool | None = None
    # Form 1125-A (COGS line-item detail) is out of scope; caller supplies
    # the aggregate on s_corp_return.income.cogs_aggregate. Required at
    # load time.
    acknowledges_cogs_aggregate_only: bool | None = None
    # Form 1125-E (officer compensation line-item detail) is out of scope;
    # caller supplies the aggregate on
    # s_corp_return.deductions.compensation_of_officers. Required at load time.
    acknowledges_officer_comp_aggregate_only: bool | None = None
    # Form 3800 elective payment election (IRC §6417) is out of scope; v1
    # does not compute or claim elective payment elections. Required at
    # load time so the user affirms awareness — the value reaches the PDF
    # via line 24d only when supplied externally on
    # `s_corp_return.scope_outs.refundable_credits` (mirroring §1374 /
    # §1375 caller-supplied amounts).
    acknowledges_no_elective_payment_election: bool | None = None
    # --- CA-specific scope-out attestations (11 unconditional) ---
    acknowledges_no_540nr_filing: bool | None = None
    acknowledges_no_ca_amt_preferences: bool | None = None
    acknowledges_no_ca_nol_carryover: bool | None = None
    acknowledges_no_ca_depreciation_divergence: bool | None = None
    acknowledges_no_ca_ira_basis_divergence: bool | None = None
    acknowledges_no_ca_rdp_status: bool | None = None
    acknowledges_no_excess_business_loss_carryover: bool | None = None
    acknowledges_no_1031_personal_property_divergence: bool | None = None
    acknowledges_no_ic_worker_reclassification: bool | None = None
    acknowledges_no_other_state_tax_credit: bool | None = None
    acknowledges_no_railroad_retirement_benefits: bool | None = None
    acknowledges_no_paid_family_leave_benefits: bool | None = None
    # Emit-time gate, NOT a load/compute attestation: packet emission refuses
    # when any W-2 lacks `pdf` (IRS Copy B attaches for EVERY W-2, not only
    # withholding-bearing ones) unless this is true. None/False at load and
    # compute is always fine — compute-only scenarios are never gated.
    acknowledges_no_source_documents: bool | None = None
    # Factual input (not an attestation): drives 1099-G state-refund
    # tax-benefit-rule compute. None at load raises.
    prior_year_itemized: bool | None = None
    # --- Conditional fields (validated only when sibling is set) ---
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
    # Prior-year state & local taxes actually PAID (pre-$10k-cap) — prior-year
    # Schedule A line 5d BEFORE the line-5e cap. Required only when
    # prior_year_itemized is True. Enables the true SALT-cap benefit limitation
    # on the Sch 1 line-1 recovery (vs the old flat-ceiling approximation).
    prior_year_salt_paid: float | None = None
    # Filer's stated total federal estimated tax payments (Form 1040 line
    # 26). Verbatim passthrough: carried through exactly as supplied, never
    # computed, capped, or clamped. A negative value is refused at load
    # time, not silently set to 0.
    estimated_tax_payments: float = 0.0
    # Filer's stated 2021 Form 1040 line 12b above-the-line cash-charitable
    # contribution for non-itemizers (CARES Act §2204 / CAA 2021 §212).
    # Verbatim passthrough: carried through exactly as supplied, or refused
    # at load time (negative, or nonzero outside the one year the provision
    # existed) — never silently capped or clamped. The field>cap and
    # itemizer-status guards are compute-time concerns handled elsewhere.
    charitable_cash_nonitemizer: float = 0.0
    # Filer's stated self-employed health-insurance deduction (Schedule 1
    # line 17). Verbatim passthrough: carried through exactly as supplied,
    # never computed, capped, or clamped. A negative value is refused at load
    # time, not silently set to 0. v1 is an INPUT CHANNEL — the §162(l) limit
    # math (premium caps, S-corp >2%-shareholder rules) is NOT modeled here.
    self_employed_health_insurance_deduction: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.filing_status, str):
            self.filing_status = FilingStatus(self.filing_status)

    @property
    def full_name(self) -> str:
        """Single source of 'First M Last' formatting consumed by every form's
        PDF-header emission. Stripped at each part so trailing whitespace in
        one field doesn't leave a stray space when another is empty (a blank
        middle initial gives 'First Last', never a double space)."""
        parts = (self.first_name, self.middle_initial, self.last_name)
        return " ".join(p.strip() for p in parts if p.strip())

    def pdf_header(self) -> Mapping[str, str]:
        return MappingProxyType({
            "taxpayer_name": self.full_name,
            "taxpayer_ssn": self.ssn,
        })


def validate_third_party_designee(cfg: "TaxReturnConfig") -> None:
    """``config.third_party_designee`` must be bool-or-None; True is refused
    because tenforty does not model the designee name / phone / PIN cells."""
    v = cfg.third_party_designee
    if v is not None and not isinstance(v, bool):
        raise ValueError(
            f"config.third_party_designee must be true, false, or null; "
            f"got {v!r}")
    if v is True:
        raise NotImplementedError(
            "config.third_party_designee is true, but the third party designee "
            "name, phone and PIN cells are not modeled by tenforty; a return "
            "naming a designee cannot be produced. Set it to false (no "
            "designee) or prepare this return outside tenforty.")


def validate_sche_1099_answers(cfg: "TaxReturnConfig") -> None:
    """Refuse an inconsistent Schedule E 1099-question answer set (lines A/B).

    Both unstated is fine (boxes stay blank). Otherwise: both values must be
    bool-or-None; line B depends on line A, so ``filed_required_1099s`` without
    ``payments_requiring_1099s`` is refused, ``payments_requiring_1099s: True``
    REQUIRES ``filed_required_1099s``, and ``payments_requiring_1099s: False``
    with a stated ``filed_required_1099s`` is contradictory (the form's line B
    only applies to a "Yes" on line A). TY2021 cannot print them (feature floor
    TY2022), so a stated answer there is refused rather than dropped."""
    a, b = cfg.payments_requiring_1099s, cfg.filed_required_1099s
    for name, val in (("payments_requiring_1099s", a),
                      ("filed_required_1099s", b)):
        if val is not None and not isinstance(val, bool):
            raise ValueError(
                f"config.{name} must be true, false, or null (unstated); "
                f"got {val!r}")
    if a is None and b is None:
        return
    if cfg.year < 2022:
        raise ValueError(
            "Schedule E lines A/B (Form 1099 questions) are supported for tax "
            f"year 2022 and later; tax year {cfg.year} cannot print them. "
            "Remove payments_requiring_1099s / filed_required_1099s.")
    if a is None:
        raise ValueError(
            "config.filed_required_1099s answers Schedule E line B, which "
            "applies only after a 'Yes' to line A: state "
            "payments_requiring_1099s: true or remove filed_required_1099s.")
    if a is True and b is None:
        raise ValueError(
            "config.payments_requiring_1099s is true (Schedule E line A "
            "'Yes'), so config.filed_required_1099s (line B) is required.")
    if a is False and b is not None:
        raise ValueError(
            "config.filed_required_1099s is stated but "
            "payments_requiring_1099s is false: Schedule E line B applies "
            "only after a 'Yes' to line A. Remove filed_required_1099s.")


def validate_tax_year_dates(r: "SCorpReturn", year: int) -> None:
    """Refuse an inconsistent short-year header: both or neither stated; ending
    is Dec 31 of ``year``; beginning is in ``year`` and not after the ending."""
    b, e = r.tax_year_beginning, r.tax_year_ending
    if b is None and e is None:
        return
    if b is None or e is None:
        raise ValueError(
            "s_corp_return.tax_year_beginning and tax_year_ending must be "
            "stated together (or neither, for a calendar year).")
    if (e.year, e.month, e.day) != (year, 12, 31):
        raise ValueError(
            f"s_corp_return.tax_year_ending must be Dec 31, {year} (the "
            f"scenario year); got {e.isoformat()}. Fiscal years are "
            "unsupported.")
    if b.year != year:
        raise ValueError(
            f"s_corp_return.tax_year_beginning must fall in {year}; got "
            f"{b.isoformat()}.")
    if b > e:
        raise ValueError(
            "s_corp_return.tax_year_beginning is after tax_year_ending.")


def validate_unclaimed_property(ca: "SCorpCAInputs") -> None:
    """Refuse an inconsistent Schedule Q item U answer set.

    All unstated is fine. A date or amount without a "Yes", or with a "No", is
    contradictory; a "Yes" REQUIRES both a valid mm/dd/yyyy date and a
    non-negative amount (0.00 is legal)."""
    import datetime as _dt
    import re as _re
    a = ca.filed_unclaimed_property_report
    d = ca.unclaimed_property_report_date
    amt = ca.unclaimed_property_amount_remitted
    if a is not None and not isinstance(a, bool):
        raise ValueError(
            "ca.filed_unclaimed_property_report must be true, false, or null; "
            f"got {a!r}")
    if a is not True:
        if d is not None or amt is not None:
            raise ValueError(
                "ca.unclaimed_property_report_date / "
                "unclaimed_property_amount_remitted answer item U(2)/(3), "
                "which apply only after a 'Yes' to U(1): state "
                "filed_unclaimed_property_report: true or remove them.")
        return
    if d is None or amt is None:
        raise ValueError(
            "ca.filed_unclaimed_property_report is true (item U(1) 'Yes'), so "
            "unclaimed_property_report_date and "
            "unclaimed_property_amount_remitted are both required.")
    if not (isinstance(d, str) and _re.fullmatch(r"\d{2}/\d{2}/\d{4}", d)):
        raise ValueError(
            "ca.unclaimed_property_report_date must be a string mm/dd/yyyy; "
            f"got {d!r}")
    try:
        _dt.datetime.strptime(d, "%m/%d/%Y")
    except ValueError:
        raise ValueError(
            f"ca.unclaimed_property_report_date {d!r} is not a real date") \
            from None
    if isinstance(amt, bool) or not isinstance(amt, (int, float)) or amt < 0:
        raise ValueError(
            "ca.unclaimed_property_amount_remitted must be a non-negative "
            f"number; got {amt!r}")


@dataclass
class ItemizedDeductions:
    medical_expenses: float = 0.0
    state_income_tax: float = 0.0
    property_tax: float = 0.0
    mortgage_interest: float = 0.0
    charitable_contributions: float = 0.0


_MONTH_KEYS = ("jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec")


@dataclass(frozen=True)
class Form1095AMonth:
    premium: float = 0.0
    slcsp: float = 0.0
    aptc: float = 0.0


@dataclass(frozen=True)
class Form1095A:
    months: tuple[Form1095AMonth, ...]          # exactly 12, jan..dec order
    received_unemployment_2021: bool = False
    tax_exempt_interest: float = 0.0


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
    date_placed_in_service: date
    basis: float
    recovery_class: str
    convention: str
    disposed: date | None = None


@dataclass
class Address:
    """Mailing-address record. Reusable across entity and shareholder
    contexts; future migrations of `TaxReturnConfig.address*` should
    consume this same dataclass (tracked as a follow-up cleanup issue
    rather than included in this sub-plan).
    """
    street: str
    city: str
    state: str
    zip_code: str


@dataclass
class SCorpShareholder:
    """Single shareholder identity and ownership stake for Schedule K-1 allocation.

    ``ownership_percentage`` is expressed as a percentage (0–100), not a
    proportion (0–1). A sole shareholder holds 100.0. Pro-rata allocation
    divides by 100 at compute time; keeping the percentage scale matches
    the IRS Schedule K-1 Part II box D literal.
    """
    name: str
    ssn_or_ein: str
    address: Address
    ownership_percentage: float
    # Schedule K-1 (1120-S) Part II face items the caller STATES (None leaves
    # the cell blank; tenforty never infers them): item H shares held at the
    # beginning / end of the tax year, item I loans from the shareholder at the
    # beginning / end of the tax year (dollars), and the "Final K-1" box
    # (this shareholder's last K-1 from the corporation).
    shares_beginning: float | None = None
    shares_end: float | None = None
    loans_beginning: float | None = None
    loans_end: float | None = None
    final_k1: bool = False
    # CA Schedule K-1 (100S) face items the caller STATES (None = blank):
    # line G "is this shareholder a resident of California?" and line F "what
    # type of entity is this shareholder?" — one of "individual",
    # "estate_trust", "qualified_exempt_organization", "single_member_llc".
    ca_resident: bool | None = None
    ca_entity_type: str | None = None


@dataclass
class SCorpScheduleBAnswers:
    """Schedule B answers and entity-description fields for Form 1120-S.

    ``business_activity_code`` is a six-digit NAICS code (e.g. "541990").
    It is passed verbatim to the PDF fill layer; no validation is performed here.

    Every Yes/No question on the form has its own field, named for the question
    it answers (the line number is in the comment). ``None`` means UNSTATED:
    the compute path never needs an answer, but PDF EMIT refuses an unstated
    answer rather than print a signed return with the question's boxes blank
    (see ``f1120s.check_schedule_b_for_emit``, which lists every missing field
    at once). ``True`` / ``False`` mark the form's Yes / No box.

    Several answers stand for an attachment tenforty does not model; a ``True``
    for those raises ``NotImplementedError`` at compute (Schedule B-1, the
    line 4a/4b detail tables, the line 5a/5b share counts, Form 8990, Form 8996,
    the line 12 amount). Line 11 ``False`` raises for the same reason (Schedules
    L and M-1). Line 14b exists to be answered only when line 14a is Yes; line 16
    (digital assets) exists on the 2023 and later forms only.
    """
    accounting_method: AccountingMethod
    business_activity_code: str
    business_activity_description: str
    product_or_service: str
    # Line 3: any shareholder a disregarded entity, a trust, an estate, or a
    # nominee or similar person?
    shareholder_disregarded_entity_trust_estate_or_nominee: bool | None = None
    # Line 4a: owns directly 20% or more, or indirectly 50% or more, of the
    # total stock of any foreign or domestic corporation?
    owns_20pct_stock_of_any_corporation: bool | None = None
    # Line 4b: owns directly 20% or more, or indirectly 50% or more, of the
    # profit, loss, or capital of any foreign or domestic partnership, or of the
    # beneficial interest of a trust?
    owns_20pct_interest_in_partnership_or_trust: bool | None = None
    # Line 5a: any outstanding shares of restricted stock?
    restricted_stock_outstanding: bool | None = None
    # Line 5b: any outstanding stock options, warrants, or similar instruments?
    stock_options_or_warrants_outstanding: bool | None = None
    # Line 6: filed, or required to file, Form 8918 (material advisor
    # disclosure)?
    filed_form_8918: bool | None = None
    # Line 7: the single box "issued publicly offered debt instruments with
    # original issue discount" (checked = True; a stated False leaves it clear).
    issued_oid_debt_instruments: bool | None = None
    # Line 8: net unrealized built-in gain (dollars). None leaves the line blank.
    net_unrealized_built_in_gain: float | None = None
    # Line 9: election under section 163(j) for any real property trade or
    # business or farming business in effect during the year?
    section_163j_election: bool | None = None
    # Line 10 (10a-10c share one Yes/No pair): satisfies one or more of the
    # Form 8990 business-interest-expense conditions?
    form_8990_conditions_met: bool | None = None
    # Line 11 (11a and 11b share one pair): total receipts AND total assets both
    # under $250,000?
    receipts_and_assets_under_250k: bool | None = None
    # Line 12: non-shareholder debt canceled, forgiven, or terms modified to
    # reduce principal?
    nonshareholder_debt_canceled: bool | None = None
    # Line 13: a qualified subchapter S subsidiary election terminated or revoked?
    qsub_election_terminated: bool | None = None
    # Line 14a: made payments that would require filing Form(s) 1099?
    payments_requiring_1099s: bool | None = None
    # Line 14b: filed, or will file, the required Form(s) 1099? Answered only
    # when 14a is Yes; must be None when 14a is No.
    filed_required_1099s: bool | None = None
    # Line 15: Qualified Opportunity Fund (2021-2024: attaching Form 8996 to
    # certify; 2025: intends to self-certify).
    qualified_opportunity_fund: bool | None = None
    # Line 16 (2023 and later forms only): received or disposed of a digital
    # asset during the year? Must be None for 2021 and 2022.
    digital_asset_transactions: bool | None = None


@dataclass
class SCorpIncome:
    """Caller-supplied amounts for Form 1120-S Income lines 1a–6.

    ``cogs_aggregate`` is the Form 1125-A line 8 total. Tenforty does not
    compute COGS line-item detail; Form 1125-A is out of scope for v1.
    """
    gross_receipts: float
    returns_and_allowances: float
    cogs_aggregate: float
    net_gain_loss_4797: float
    other_income: float


@dataclass(frozen=True)
class OtherDeductionComponent:
    """One row of the Form 1120-S line 19 'Other deductions' attached statement."""
    description: str
    amount: float


@dataclass
class SCorpDeductions:
    """Caller-supplied aggregates for Form 1120-S Deductions lines 7–19.

    ``compensation_of_officers`` is the Form 1125-E line 4 total; Form 1125-E
    line-item detail is out of scope for v1. ``depreciation`` is also a
    caller-supplied aggregate — tenforty does not automatically integrate
    Form 4562 / ``Scenario.depreciable_assets`` output into 1120-S deductions,
    so a caller using both must avoid double-counting.
    """
    compensation_of_officers: float
    salaries_wages: float
    repairs_maintenance: float
    bad_debts: float
    rents: float
    taxes_licenses: float
    interest: float
    depreciation: float
    depletion: float
    advertising: float
    pension_profit_sharing_plans: float
    employee_benefits: float
    other_deductions: float
    # Form 1120-S line 19 "Energy efficient commercial buildings deduction"
    # (section 179D, Form 7205), 2023+ forms. Must be 0: a nonzero claim cannot
    # be printed without the attached Form 7205, so compute refuses it.
    energy_efficient_buildings_deduction: float = 0.0
    # Itemization of ``other_deductions`` for the attached line 19 statement.
    # Empty = no statement can be generated (PDF emit refuses a nonzero
    # other_deductions without it). When present, the per-item-rounded sum
    # must equal the rounded ``other_deductions``.
    other_deductions_components: list[OtherDeductionComponent] = field(
        default_factory=list)


@dataclass
class SCorpScopeOuts:
    """Caller-supplied tax amounts that tenforty does not compute.

    Covers §1375 net passive income tax and §1374 built-in gains tax,
    which the caller supplies and the compute layer sums into Form 1120-S
    line 22c. `interest_on_453_deferred` is a fail-closed scope-out:
    §453(l)(3)/§453A(c) interest is a shareholder-level liability
    (Schedule K-1 box 17 codes M/N), so a nonzero value raises
    NotImplementedError in the 1120-S compute.
    """
    net_passive_income_tax: float = 0.0
    built_in_gains_tax: float = 0.0
    interest_on_453_deferred: float = 0.0


@dataclass
class SCorpPayments:
    estimated_tax_payments: float = 0.0
    prior_year_overpayment_credited: float = 0.0
    tax_deposited_with_7004: float = 0.0
    credit_for_federal_excise_tax: float = 0.0
    refundable_credits: float = 0.0


@dataclass
class SCorp199AInfo:
    """Entity-level §199A (QBI) information reported on Schedule K-1 box 17
    code V and its Statement A.

    ``qbi_override`` replaces the default QBI (Schedule K line 1, ordinary
    business income) when the caller's qualified business income differs from
    book ordinary income; ``None`` uses the line-1 default. ``w2_wages`` and
    ``ubia`` are the entity totals, allocated pro-rata to each shareholder's
    Statement A. Below the §199A taxable-income threshold — tenforty's only
    supported QBI scope (Form 8995 simplified) — W-2 wages and UBIA do not
    limit the deduction; they are reported for completeness and to support
    the shareholder's own above-threshold recomputation off-tenforty."""
    qbi_override: float | None = None
    w2_wages: float = 0.0
    ubia: float = 0.0


@dataclass(frozen=True)
class SCorpCAInputs:
    """CA-side inputs for Form 100S, hung off ``SCorpReturn.ca`` when a CA
    S-corp return is requested.

    Balance-sheet scope-out (spec §1): no NEW CA gate is needed — the federal
    ``SCorpScopeOuts`` attestations already bound this corporation's
    size/complexity, and the 100S compute reads no balance-sheet inputs.
    """
    # True only for the corporation's first taxable year; combined with
    # ca_scorp params.first_year_minimum_tax_exempt to decide the
    # minimum-tax floor.
    first_year: bool
    estimated_tax_payments: float
    prior_year_overpayment_applied: float
    # Franchise/income tax deducted on the FEDERAL 1120-S (cash-basis: the
    # amount actually paid in-year and deducted federally). Added back on the
    # 100S. Explicit input, never inferred.
    state_tax_deducted_federally: float
    # Net CA depreciation adjustment (CA minus federal, signed) from the
    # caller's Form 3885-equivalent computation. Scope-out passthrough.
    depreciation_adjustment: float
    # v1 supports only 100% CA apportionment; False must raise at load.
    apportionment_ca_only: bool
    # Form 100S Schedule Q answers the caller STATES (None leaves the question's
    # boxes blank; never inferred).
    # Question J (Question I on the 2022 form): is the S corporation under audit
    # by the IRS, or audited in a prior year?
    under_irs_audit: bool | None = None
    # Question O: have all required information returns (Forms 1099, 8300, 592,
    # 592-B ...) been filed with the FTB? One of "yes", "no", "not_applicable".
    information_returns_filed: str | None = None
    # Question F "where incorporated": two-letter state abbreviation and country
    # (free text). None leaves the cell blank.
    state_of_incorporation: str | None = None
    country_of_incorporation: str | None = None
    # California corporation number (7 digits) or Secretary of State file
    # number (12 digits, LLCs taxed as corporations); digits only. Printed on
    # Form 100S and every Schedule K-1 (100S). None leaves it blank.
    corporation_number: str | None = None
    # Form 100S Schedule Q answers the caller STATES (None leaves blank).
    # Question G: maximum number of shareholders at any time during the year
    # (positive integer; stated, never derived from the shareholder list).
    max_shareholders: int | None = None
    # Question H: date business began in California or income was first
    # derived from California sources.
    date_business_began_in_ca: date | None = None
    # Question D: filing on a water's-edge basis?
    water_edge_basis: bool | None = None
    # Question E: does this return include Qualified Subchapter S Subsidiaries?
    includes_qsubs: bool | None = None
    # Question Q: a reportable transaction or listed transaction in this return?
    included_reportable_transaction: bool | None = None
    # Question R: did the corporation file the federal Schedule M-3?
    filed_federal_schedule_m3: bool | None = None
    # Question S: is FTB 3544 Side 2 Part B (assigned credits) attached?
    ftb_3544_attached: bool | None = None
    # Question I: was the S corporation an inactive business both within and
    # outside California during the year? (2023-2025 forms only; the 2021-2022
    # forms have no such question.)
    inactive_business: bool | None = None
    # Form 100S Side 3 "May the FTB discuss this return with the preparer shown
    # above?" (Yes/No; None = both boxes blank). Lives on the CA block because it
    # answers a CA-form question. Standing ruling: No.
    discuss_with_preparer: bool | None = None
    # Question U: has the entity previously filed an unclaimed property Holder
    # Remit Report with the State Controller's Office? (1) Yes/No; (2) date the
    # last report was filed, "mm/dd/yyyy"; (3) amount last remitted (>= 0, 0.00
    # legal). Dependent answers: see ``validate_unclaimed_property``.
    filed_unclaimed_property_report: bool | None = None
    unclaimed_property_report_date: str | None = None
    unclaimed_property_amount_remitted: float | None = None


@dataclass
class SCorpReturn:
    name: str
    ein: str
    address: Address
    date_incorporated: date
    s_election_effective_date: date

    income: SCorpIncome
    deductions: SCorpDeductions
    schedule_b_answers: SCorpScheduleBAnswers

    # `total_assets` defaults to 0.0 so test scenarios that don't care
    # about Sch L gating can omit it. Real returns must supply the
    # actual figure; the Sch L attestation gate fires at >= $250,000.
    total_assets: float = 0.0
    shareholders: list[SCorpShareholder] = field(default_factory=list)

    scope_outs: SCorpScopeOuts = field(default_factory=SCorpScopeOuts)
    payments: SCorpPayments = field(default_factory=SCorpPayments)
    section_199a: SCorp199AInfo | None = None
    ca: SCorpCAInputs | None = None
    # §4a amended-return marks. When True, the emit path checks the
    # "Amended return" box on Form 1120-S (H(4)), each Schedule K-1
    # (1120-S) ("Amended K-1"), and each Schedule K-1 (100S) (line E
    # "amended"). CA S-corp amendments themselves file on Form 100X (not
    # emitted by tenforty); this flag marks the corrected 100S/K-1 set that
    # accompanies a preparer-completed 100X. Default False (an ordinary,
    # non-amended return).
    amended_return: bool = False
    # Schedule K-1 (1120-S) Part I item C: the IRS Center where the corporation
    # filed its return (free text, e.g. "Ogden, UT"). None leaves it blank.
    irs_center: str | None = None
    # Cash distributions to shareholders for the year (Schedule K line 16d;
    # K-1 box 16 code D, allocated by ownership). Printed only: shareholder
    # basis is tracked externally (standing attestation), so no basis or
    # excess-distribution computation. Must be >= 0.
    distributions_to_shareholders: float = 0.0
    # Title of the signing officer (e.g. "President"), printed in the Title cell
    # of the Form 1120-S page 1 and Form 100S signature blocks. None leaves it
    # blank. NOTE: tenforty must NEVER fill the signature or the signature-date
    # cells of any return; only the title is stated.
    officer_title: str | None = None
    # Form 1120-S page 1 "May the IRS discuss this return with the preparer shown
    # below?" (Yes/No; None = both boxes blank). Standing ruling: No.
    discuss_with_preparer: bool | None = None
    # Short tax year (e.g. a first year starting mid-year): the header date
    # boxes of the 1120-S, K-1 (1120-S), 100S and K-1 (100S) print these. Both or
    # neither; ending must be Dec 31 of the scenario year (fiscal years are
    # unsupported) and beginning must fall in the scenario year. None =
    # calendar year = boxes blank. See ``validate_tax_year_dates``.
    tax_year_beginning: date | None = None
    tax_year_ending: date | None = None
    # Form 1120-S page 1 item G: "Is the corporation electing to be an S
    # corporation beginning with this tax year?" (stated; None leaves both boxes
    # blank, True / False marks the chosen box).
    electing_s_this_year: bool | None = None
    # Item H "Check if:" boxes (1) Final return, (2) Name change, (3) Address
    # change, (5) S election termination or revocation. Check-if-applicable:
    # only True marks a box; False and None both leave it blank. (H(4) Amended
    # is ``amended_return``.)
    final_return: bool | None = None
    name_change: bool | None = None
    address_change: bool | None = None
    s_election_terminated: bool | None = None
    # Schedule K-1 (1120-S) Part I item D: the corporation's total number of
    # shares at the beginning / end of the tax year. Stated, never summed from
    # the shareholders' figures. None leaves the cell blank.
    total_shares_beginning: float | None = None
    total_shares_end: float | None = None


class DivergenceSource(str, Enum):
    # Two live provenance values remain after the FODS retirement (Part RETIRE,
    # spec §3). The historical AUTO_DERIVED and WORKSHEET members were removed:
    # no code stamped AUTO_DERIVED anymore, and WORKSHEET was stamped only by
    # the deleted .fods importer. The deserialization path that could have
    # revived them from an old snapshot is DEAD — ``<basename>.ca-resolved.yaml``
    # is write-only, and the free-form ``divergences:`` deserializer that once
    # read ``DivergenceSource(data["source"])`` was removed in Part INPUT.

    # Stamped by derive_auto_divergences on divergences sourced from the
    # packaged CA divergence catalog's `auto:` rows (Part AUTO).
    CATALOG_AUTO = "catalog_auto"
    # Stamped by materialize_user_divergence on divergences the user supplied
    # id-keyed in the scenario (Part INPUT). The user gives {id, amount, note?}
    # (+ direction for BOTH rows); line/direction/description are materialized
    # from the catalog entry so a user row can never disagree with the catalog.
    USER = "user"


class DivergenceDirection(str, Enum):
    SUBTRACTION = "subtraction"
    ADDITION = "addition"


@dataclass
class CASchCAAdjustment:
    """A single Schedule CA (540) federal-vs-CA adjustment.

    Each entry routes a dollar amount to a specific Sch CA line as either
    Col B (subtraction) or Col C (addition), preserving provenance via
    ``source`` for audit. Derived by the kernel from the catalog's ``auto:``
    rows against federal data when ``source=CATALOG_AUTO`` (UI exclusion, SS
    exemption, etc.); materialized from an id-keyed scenario divergence when
    ``source=USER``."""

    source: DivergenceSource
    sch_ca_line: str  # e.g., "Part I §B 7", "Part II line 5a"
    direction: DivergenceDirection
    amount: float
    description: str  # human-readable; FTB Pub 1001 phrasing preferred
    federal_source: str | None = None  # legacy; no longer populated — provenance now lives on catalog_id
    pub1001_ref: str | None = None  # legacy; no longer populated — provenance now lives on catalog_id
    catalog_id: str | None = None  # CA divergence catalog row id — CATALOG_AUTO / USER
    # User-facing provenance note carried from an id-keyed scenario divergence
    # ({id, amount, note?}). Optional; never consumed by compute.
    note: str | None = None


@dataclass
class CASchD540Adjustment:
    """A single Schedule D (540) federal-vs-CA capital-gains adjustment.

    Mirrors ``CASchCAAdjustment``'s shape (§1202 QSBS, §1045 rollover,
    §1400Z, pre-1987 inherited basis, Peace Corps PR, etc.).

    Retained schema for the future CA Schedule D (540) user-divergence
    compute follow-up. The FODS worksheet import that once populated it was
    retired (spec §3); no caller populates it today. ``sch_d_540.compute``
    keeps a dormant ``worksheet_adjustments`` hook for that follow-up."""

    source: DivergenceSource
    direction: DivergenceDirection
    amount: float
    description: str
    pub1001_ref: str | None = None


@dataclass
class CA540Return:
    """California 540 (resident, full-year) return data.

    Held on ``Scenario.ca540`` when present. Combines federal-derived
    auto divergences and user-supplied worksheet divergences in
    ``divergences``; structured fields cover the few non-divergence
    inputs (voluntary contributions, payments, PTET credit, use tax,
    estimated tax penalty)."""

    voluntary_contributions: list[VoluntaryContribution] = field(default_factory=list)
    estimated_payments: float = 0.0  # 540 line 71 (Form 540-ES quarterly)
    use_tax: float = 0.0  # 540 line 91 (use tax owed on out-of-state purchases)
    estimated_tax_penalty: float = 0.0  # 540 line 113 (FTB 5805 result)
    # 540 line 112 (interest, late-return and late-payment penalties). None
    # means UNSTATED; an explicit 0 states the return is filed and paid on
    # time; a positive amount prints on line 112 and enters line 114 / 115.
    # Not required by the compute path. At CA PDF EMIT time the orchestrator
    # refuses an unstated value on any return that is not a pure refund (an
    # amount on line 111, or anything on line 110 or 113), where a silent 0
    # would understate the total amount due.
    interest_and_penalties: float | None = None
    ptet_credit: float = 0.0  # 540 line 50 (Sub-plan 4 wires this; default $0)
    # Federal compute lumps RRB Tier 1/2 into 1040 line 5b (pensions_taxable)
    # without separating it; the taxpayer supplies the RRB-only amount here
    # so the Sch CA kernel can route it as an §A 5b Col B subtraction
    # (R&TC 17087, FTB Pub 1001 p.10).
    rrb_tier_1_2_amount: float | None = None
    # PFL benefits paid by the EDD are reported on Form 1099-G alongside
    # unemployment but tenforty v1's Form1099G dataclass does not separate
    # them; the taxpayer supplies the PFL-only amount here so the kernel
    # can route it as an §B 7 Col B subtraction (FTB Pub 1001 p.17).
    pfl_amount: float | None = None
    divergences: list[CASchCAAdjustment] = field(default_factory=list)
    # Catalog ids the user has explicitly reviewed (spec §2.2 `reviewed:` list).
    # Every id is validated against the year's catalog at load; carried for
    # audit/UX (a reviewed id need not appear in `divergences`).
    reviewed_divergence_ids: tuple[str, ...] = ()

    def with_extra_divergences(self, extra: list["CASchCAAdjustment"]) -> "CA540Return":
        return replace(self, divergences=[*self.divergences, *extra])


@dataclass
class K1AllocationEntity:
    """Entity-side identity carried on a K-1 allocation. Distinguished
    from `SCorpReturn` (which holds the full corporate return inputs);
    `K1AllocationEntity` is a snapshot of just the fields a K-1 needs."""
    name: str
    ein: str
    address: Address


@dataclass
class K1AllocationShareholder:
    """Shareholder-side identity carried on a K-1 allocation."""
    name: str
    ssn_or_ein: str
    address: Address


@dataclass
class K1Allocation:
    """A single shareholder's pro-rata share of an S-corp's pass-through
    items: Sch K line 1 / box 1 (Ordinary Business Income) plus the box 17
    code V §199A items (QBI, W-2 wages, and UBIA of qualified property).

    This is the contract between `f1120s.compute` (producer) and the
    orchestrator (consumer for PDF emit + 1040 waterfall). Consumers
    access fields by attribute (e.g., `alloc.entity.name`); replacing
    or renaming fields is a typed change that surfaces at every call
    site, not silently in a string-key lookup."""
    entity: K1AllocationEntity
    shareholder: K1AllocationShareholder
    ownership_percentage: float
    box_1_ordinary_business_income: float
    box_17v_qbi: float = 0.0
    box_17v_w2_wages: float = 0.0
    box_17v_ubia: float = 0.0
    # Box 16 code D (distributions), the shareholder's pro-rata share of Sch K
    # line 16d. Printed only; basis is tracked externally.
    box_16d_distributions: int = 0


@dataclass(frozen=True)
class AmendmentCase:
    """The narrative + prior-refund context for an amended return, supplied
    alongside a corrected scenario and the filed-values file. Carries no tax
    math — only the 1040-X explanation and the original refund figures needed
    to reconcile Columns A/B/C. `prior_amendment_note` is the sole optional
    NARRATIVE field (a filer amending a return that was itself already amended).

    CA analogues (`ca_original_refund_*`) carry the California Schedule X
    original-overpayment context — the CA original overpayment the filer
    received or applied forward (Schedule X line 2 = received + applied,
    mirroring federal line 18). They default to ``None`` rather than 0.0 so a
    FEDERAL-ONLY amendment case still loads without stating them, but
    ``schedule_x.assemble_ca`` FAILS CLOSED at the point of use if a CA
    amendment is assembled while either is None: the filer must ASSERT the CA
    original-payment context (even if it is 0), it is never inferred.

    `original_tax_paid` is the federal 1040-X line 16 amount — the total paid
    with a request for extension of time to file, paid with the ORIGINAL
    return, and any additional tax paid after it was filed. Like line 18 it is
    genuine post-filing money movement, not a recomputable figure, so it rides
    the case. It defaults to ``None`` ("not stated") rather than 0.0 so an
    amendment of a REFUND-year original loads and assembles without it (line
    16 = 0), but ``f1040x.assemble`` FAILS CLOSED at the point of use if the
    filed values show the original return had a balance due while it is None:
    the filer must ASSERT what was actually paid (0 if never paid), it is
    never inferred from the balance due."""

    year: int
    explanation: str
    original_refund_received: float
    original_refund_applied: float
    prior_amendment_note: str | None = None
    ca_original_refund_received: float | None = None
    ca_original_refund_applied: float | None = None
    original_tax_paid: float | None = None


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
    schedule_c_businesses: list[ScheduleCBusiness] = field(default_factory=list)
    depreciable_assets: list[DepreciableAsset] = field(default_factory=list)
    itemized_deductions: ItemizedDeductions | None = None
    form_1095a: Form1095A | None = None
    s_corp_return: SCorpReturn | None = None
    ca540: CA540Return | None = None
    # Kept in sync with w2s[*].pdf ONLY by load_scenario's normalization.
    # Programmatic callers that set W2.pdf directly must also populate this
    # list (via scenario._load_source_documents) or the emit gate will pass
    # while packet assembly splices nothing.
    source_documents: list[SourceDocument] = field(default_factory=list)

    def __post_init__(self) -> None:
        # CA-withholding channel, schema layer (state-attribution ruling):
        # a California Form 540 return is load-decidable via `ca540 is not
        # None`. Such a return must attribute every withholding W-2 to a
        # state (W2.state) so a future f540 compute can claim ONLY CA
        # withholding on line 71 -- an unattributed withholding W-2 is
        # ambiguous (is it CA withholding or another state's?) and is
        # refused here rather than silently assumed to be CA. This runs in
        # __post_init__ (not a load_scenario-only validator) so it catches
        # both YAML-loaded scenarios AND programmatic Scenario(...)
        # construction (e.g. in tests) alike.
        if self.ca540 is not None:
            for w in self.w2s:
                if w.state is None and w.state_tax_withheld > 0:
                    raise ValueError(
                        f"W-2 from {w.employer!r} has state tax withheld "
                        f"(${w.state_tax_withheld:.2f}) but no state "
                        f"attribution; a California Form 540 return must "
                        f"attribute each withholding W-2 to a state so only "
                        f"CA withholding is claimed on line 71 -- add "
                        f'state="CA" (or the actual 2-letter state code) to '
                        f"that W-2."
                    )
