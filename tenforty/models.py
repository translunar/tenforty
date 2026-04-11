from dataclasses import dataclass, field
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


@dataclass
class Form1098:
    lender: str
    mortgage_interest: float
    property_tax: float = 0.0
    mortgage_insurance_premiums: float = 0.0


@dataclass
class ScheduleK1:
    entity_name: str
    entity_ein: str
    ordinary_income: float = 0.0
    rental_income: float = 0.0
    interest_income: float = 0.0
    dividend_income: float = 0.0
    short_term_capital_gain: float = 0.0
    long_term_capital_gain: float = 0.0
    section_179_deduction: float = 0.0
    other_deductions: float = 0.0


class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_JOINTLY = "married_jointly"
    MARRIED_SEPARATELY = "married_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


@dataclass
class TaxReturnConfig:
    year: int
    filing_status: FilingStatus
    birthdate: str
    state: str
    dependents: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.filing_status, str):
            self.filing_status = FilingStatus(self.filing_status)


@dataclass
class Scenario:
    config: TaxReturnConfig
    w2s: list[W2] = field(default_factory=list)
    form1099_int: list[Form1099INT] = field(default_factory=list)
    form1099_div: list[Form1099DIV] = field(default_factory=list)
    form1099_b: list[Form1099B] = field(default_factory=list)
    form1098s: list[Form1098] = field(default_factory=list)
    schedule_k1s: list[ScheduleK1] = field(default_factory=list)
