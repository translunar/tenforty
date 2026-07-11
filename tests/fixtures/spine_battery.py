"""Synthetic scenario battery for the penny-parity gate, generated per year.

Each builder takes the tax year and returns a single-filer Scenario whose
income is high enough to clear the EIC scope-gate, so _compute_1040_pipeline
routes to the native spine rather than the workbook. battery_for(year)
yields the same eight boundary scenarios for any supported year — adding a
year adds zero code here.

All identities and amounts are fully synthetic — no real personal data.
"""
import functools
from collections.abc import Callable

from tenforty.models import (
    Form1098,
    Form1099DIV,
    Form1099INT,
    Form1099B,
    RentalProperty,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.params.federal import load as load_params
from tests.helpers import scope_out_attestation_defaults


def _battery_config(year: int, **overrides) -> TaxReturnConfig:
    """Single-filer config with all scope-out attestations set."""
    defaults = scope_out_attestation_defaults()
    # prior_year_itemized=False so the state-refund tax-benefit-rule
    # short-circuits cleanly in all battery scenarios.
    defaults["prior_year_itemized"] = False
    merged = {**defaults, **overrides}
    return TaxReturnConfig(
        year=year,
        filing_status="single",
        birthdate="1985-03-01",
        state="CA",
        first_name="Example",
        last_name="Filer",
        ssn="000-00-0000",
        **merged,
    )


def _w2(year: int, employer: str, wages: float, federal_tax_withheld: float,
        state_tax_withheld: float | None = None) -> W2:
    """Year-correct synthetic W-2: SS wages capped at the year's OASDI wage
    base, SS/Medicare withholding derived at the statutory rates so the
    fixture can't drift from the year it claims to model."""
    base = float(load_params(year).ss_wage_base)
    ss_wages = min(wages, base)
    extra = ({"state_tax_withheld": state_tax_withheld}
             if state_tax_withheld is not None else {})
    return W2(
        employer=employer,
        wages=wages,
        federal_tax_withheld=federal_tax_withheld,
        ss_wages=ss_wages,
        ss_tax_withheld=float(round(ss_wages * 0.062)),
        medicare_wages=wages,
        medicare_tax_withheld=round(wages * 0.0145, 2),
        **extra,
    )


def build_canonical_wage_investment_rental(year: int) -> Scenario:
    """Canonical shape: wages + interest + qualified dividends + LTCG + rental.

    Income ~$195,000. Exercises:
    - Sch B interest (< threshold, but present)
    - QDCGT with both 0% and 15% bands active
    - Rental property flowing through Sch E → Sch 1 → AGI
    - Standard deduction (no itemizing)
    - No Additional Medicare (wages below $200k)
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer A", wages=150_000.0,
                federal_tax_withheld=28_000.0),
        ],
        form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=2_000.0),
        ],
        form1099_div=[
            Form1099DIV(
                payer="Synthetic Brokerage",
                ordinary_dividends=5_000.0,
                qualified_dividends=4_000.0,
            ),
        ],
        form1099_b=[
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Stock Fund",
                date_acquired="2022-01-15",
                date_sold=f"{year}-06-01",
                proceeds=20_000.0,
                cost_basis=14_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
        rental_properties=[
            RentalProperty(
                address="100 Synthetic Ave",
                property_type=1,
                fair_rental_days=365,
                personal_use_days=0,
                rents_received=18_000.0,
                mortgage_interest=7_000.0,
                taxes=2_500.0,
                depreciation=4_500.0,
            ),
        ],
    )


def build_qdcgt_15_to_20_boundary(year: int) -> Scenario:
    """QDCGT 15% → 20% boundary: taxable income above the year's single-filer
    QDCGT 15%→20% breakpoint.

    Wages $500k + $50k LTCG + $20k qualified dividends pushes preferential
    income into the 20% band. Exercises the 20% QDCGT slice.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer B", wages=500_000.0,
                federal_tax_withheld=150_000.0),
        ],
        form1099_div=[
            Form1099DIV(
                payer="Synthetic Brokerage",
                ordinary_dividends=22_000.0,
                qualified_dividends=20_000.0,
            ),
        ],
        form1099_b=[
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Index Fund",
                date_acquired="2021-03-10",
                date_sold=f"{year}-09-15",
                proceeds=80_000.0,
                cost_basis=30_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_qbi_threshold_boundary(year: int) -> Scenario:
    """QBI threshold boundary: income near the year's single-filer QBI
    phase-out threshold.

    Wages $180k + rental income of ~$10k brings total near QBI threshold.
    acknowledges_qbi_below_threshold=True because no K-1 QBI is present and
    the scenario has no QBI-generating pass-through — this attestation just
    affirms no 8995-A computation is needed.
    """
    return Scenario(
        config=_battery_config(year, acknowledges_qbi_below_threshold=True),
        w2s=[
            _w2(year, employer="Synthetic Employer C", wages=180_000.0,
                federal_tax_withheld=38_000.0),
        ],
        form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=3_000.0),
        ],
        rental_properties=[
            RentalProperty(
                address="200 Synthetic Blvd",
                property_type=1,
                fair_rental_days=365,
                personal_use_days=0,
                rents_received=20_000.0,
                mortgage_interest=8_000.0,
                taxes=3_000.0,
                depreciation=5_000.0,
            ),
        ],
    )


def build_addl_medicare_boundary(year: int) -> Scenario:
    """Additional Medicare Tax boundary: wages $210,000 > $200,000 threshold.

    The $10,000 excess × 0.9% = $90 Additional Medicare Tax on Form 8959.
    Exercises the f8959 line 18 flow.

    Wages-only (no investment income) to keep this scenario a clean isolation
    of the Additional-Medicare branch. (NIIT does not enter here regardless,
    since neither the native spine nor the oracle workbook computes Form 8960
    — see the qdcgt_15_to_20_boundary scenario, which DOES carry investment
    income at AGI > $200k and still passes because both sides omit NIIT
    symmetrically.)
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer D", wages=210_000.0,
                federal_tax_withheld=48_000.0),
        ],
    )


def build_zero_tax_refund(year: int) -> Scenario:
    """Over-withheld scenario: large withholding relative to tax → refund.

    Wages $130,000 (clears the EIC gate), modest interest. Taxable income =
    $130,500 − standard deduction is above the IRS $100,000 tax-table
    cutoff. Above $100k the IRS uses the rate schedule directly (no
    $50-bracket rounding), so the native spine's continuous formula agrees
    with the workbook. Below $100k taxable income the IRS publishes a
    discrete tax table (midpoint-of-$50-bracket) that the workbook uses;
    using the continuous rate schedule produces a $6 difference for that
    range. Keeping taxable income above $100k avoids that discrepancy
    without implementing the full tax table here.

    Withholding ($30,000) exceeds expected tax (~$22k) → refund scenario.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer E", wages=130_000.0,
                federal_tax_withheld=30_000.0),
        ],
        form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=500.0),
        ],
    )


def build_owes_tax(year: int) -> Scenario:
    """Under-withheld scenario: withholding well below tax liability → owes.

    Wages $130k + LTCG $25k + qualified divs $8k. Withholding $15,000 is
    deliberately low relative to the expected tax (~$30k+) → amount owed.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer F", wages=130_000.0,
                federal_tax_withheld=15_000.0),
        ],
        form1099_div=[
            Form1099DIV(
                payer="Synthetic Brokerage",
                ordinary_dividends=9_000.0,
                qualified_dividends=8_000.0,
            ),
        ],
        form1099_b=[
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Growth Fund",
                date_acquired="2020-05-20",
                date_sold=f"{year}-11-10",
                proceeds=45_000.0,
                cost_basis=20_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_tax_table_band(year: int) -> Scenario:
    """Taxable income inside the Tax Table's range (< $100k).

    Wages $90,000 (clears every EIC ceiling) minus the standard deduction
    lands taxable income around $75k — squarely in table territory. The
    workbook reads the same published table, so parity here proves the
    spine's table lookup end-to-end (the other scenarios deliberately sit
    above $100k, where table and schedule coincide).
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[_w2(year, employer="Synthetic Employer H", wages=90_000.0,
                 federal_tax_withheld=16_000.0)],
        form1099_int=[Form1099INT(payer="Synthetic Bank", interest=1_000.0)],
    )


def build_itemizer_with_w2_state_tax(year: int) -> Scenario:
    """Single itemizer whose Schedule A SALT includes W-2 box 17 state tax.

    Exercises the Sch A line 5a state-income-tax path, which is sourced from
    W-2 box 17 (`state_tax_withheld`), NOT from itemized_deductions. Mortgage
    interest + property tax (carried on Form 1098) push the itemized total
    above the standard deduction in both years, so the divergence binds on
    total_deductions / taxable_income as well as the Sch A keys.

    Inputs reach BOTH paths through channels each reads identically:
      - mortgage_interest + property_tax via form1098s (native bridges these
        into itemized_deductions; the flattener feeds them to the workbook);
      - state income tax via W-2 box 17 (the workbook's Sch A line 5a source).

    2025 SALT (cap $40k, under phaseout): line 5d = 9,000 + 6,000 = 15,000,
    line 5e = 15,000 (under cap); line 17 = 20,000 mortgage + 15,000 = 35,000.
    2024 SALT (flat cap $10k): line 5d = 15,000, line 5e = 10,000 (capped);
    line 17 = 20,000 + 10,000 = 30,000. Both clear the standard deduction.

    EIC gate: wages $150k >> the no-child EIC ceiling → routes native.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer G", wages=150_000.0,
                federal_tax_withheld=28_000.0, state_tax_withheld=9_000.0),
        ],
        form1098s=[
            Form1098(
                lender="Synthetic Mortgage Co",
                mortgage_interest=20_000.0,
                property_tax=6_000.0,
            ),
        ],
    )


_BUILDERS: list[tuple[str, Callable[[int], Scenario]]] = [
    ("canonical_wage_investment_rental", build_canonical_wage_investment_rental),
    ("qdcgt_15_to_20_boundary", build_qdcgt_15_to_20_boundary),
    ("qbi_threshold_boundary", build_qbi_threshold_boundary),
    ("addl_medicare_boundary", build_addl_medicare_boundary),
    ("zero_tax_refund", build_zero_tax_refund),
    ("owes_tax", build_owes_tax),
    ("tax_table_band", build_tax_table_band),
    ("itemizer_with_w2_state_tax", build_itemizer_with_w2_state_tax),
]


def battery_for(year: int) -> list[tuple[str, Callable[[], Scenario]]]:
    """The parity battery for a year: (name, zero-arg builder) pairs."""
    return [(name, functools.partial(build, year)) for name, build in _BUILDERS]
