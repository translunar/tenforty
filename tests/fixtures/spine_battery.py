"""Synthetic scenario battery for the penny-parity gate (2025 and 2024).

Each builder returns a single-filer Scenario whose income is high enough to
clear the EIC scope-gate (wages ≥ the MFJ no-child EIC ceiling for that year),
so _compute_1040_pipeline routes to the native spine rather than the workbook.

All identities and amounts are fully synthetic — no real personal data.

Key 2025 boundaries exercised:
  - canonical_wage_investment_rental: wage + interest + qdivs + LTCG + rental
  - qdcgt_15_to_20_boundary:          QDCGT shifts into 20% band (income > $533,400)
  - qbi_threshold_boundary:            income near QBI phase-out threshold ($197,300)
  - addl_medicare_boundary:            wages just above $200,000 Additional Medicare
  - zero_tax_refund:                   withholding > tax → overpaid / refund
  - owes_tax:                          withholding < tax → amount owed

Key 2024 boundaries exercised (same branches, 2024 params):
  - canonical_wage_investment_rental_2024: wage + interest + qdivs + LTCG + rental
  - qdcgt_15_to_20_boundary_2024:          QDCGT into 20% band (income > $518,900)
  - qbi_threshold_boundary_2024:           income near 2024 QBI threshold ($191,950)
  - addl_medicare_boundary_2024:           wages just above $200,000 threshold
  - zero_tax_refund_2024:                  withholding > tax → overpaid / refund
  - owes_tax_2024:                         withholding < tax → amount owed
"""

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
from tests.helpers import scope_out_attestation_defaults


def _base_config(**overrides) -> TaxReturnConfig:
    """Return a single-filer TaxReturnConfig with all attestations set.

    All scope-out attestations use their test-posture defaults (see
    tests.helpers.scope_out_attestation_defaults) plus prior_year_itemized=False
    so the state-refund tax-benefit-rule short-circuits cleanly.
    """
    defaults = scope_out_attestation_defaults()
    # prior_year_itemized is already in scope_out_attestation_defaults(); set it
    # False here (the test-posture default is False, but make it explicit so the
    # state-refund tax-benefit-rule short-circuits cleanly in all battery scenarios).
    defaults["prior_year_itemized"] = False
    # overrides win — merge after defaults so callers can change any field.
    merged = {**defaults, **overrides}
    return TaxReturnConfig(
        year=2025,
        filing_status="single",
        birthdate="1985-03-01",
        state="CA",
        first_name="Example",
        last_name="Filer",
        ssn="000-00-0000",
        **merged,
    )


def _base_config_2024(**overrides) -> TaxReturnConfig:
    """Return a single-filer TaxReturnConfig for tax year 2024.

    Mirrors _base_config but with year=2024 so both the native params lookup
    and the workbook path use the 2024 workbook (spreadsheets/federal/2024/1040.xlsx).
    """
    defaults = scope_out_attestation_defaults()
    defaults["prior_year_itemized"] = False
    merged = {**defaults, **overrides}
    return TaxReturnConfig(
        year=2024,
        filing_status="single",
        birthdate="1985-03-01",
        state="CA",
        first_name="Example",
        last_name="Filer",
        ssn="000-00-0000",
        **merged,
    )


def build_canonical_wage_investment_rental() -> Scenario:
    """Canonical shape: wages + interest + qualified dividends + LTCG + rental.

    Income ~$195,000. Exercises:
    - Sch B interest (< threshold, but present)
    - QDCGT with both 0% and 15% bands active
    - Rental property flowing through Sch E → Sch 1 → AGI
    - Standard deduction (no itemizing)
    - No Additional Medicare (wages below $200k)
    """
    return Scenario(
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer A",
                wages=150_000.0,
                federal_tax_withheld=28_000.0,
                ss_wages=150_000.0,
                ss_tax_withheld=9_300.0,
                medicare_wages=150_000.0,
                medicare_tax_withheld=2_175.0,
            ),
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
                date_sold="2025-06-01",
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


def build_qdcgt_15_to_20_boundary() -> Scenario:
    """QDCGT 15% → 20% boundary: taxable income above $533,400 single breakpoint.

    Wages $500k + $50k LTCG + $20k qualified dividends pushes preferential
    income into the 20% band. Exercises the 20% QDCGT slice.
    """
    return Scenario(
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer B",
                wages=500_000.0,
                federal_tax_withheld=150_000.0,
                ss_wages=176_100.0,  # 2025 SS wage base
                ss_tax_withheld=10_918.0,
                medicare_wages=500_000.0,
                medicare_tax_withheld=7_250.0,
            ),
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
                date_sold="2025-09-15",
                proceeds=80_000.0,
                cost_basis=30_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_qbi_threshold_boundary() -> Scenario:
    """QBI threshold boundary: income at the $197,300 single-filer QBI threshold.

    Wages $180k + rental income of ~$10k brings total near QBI threshold.
    acknowledges_qbi_below_threshold=True because no K-1 QBI is present and
    the scenario has no QBI-generating pass-through — this attestation just
    affirms no 8995-A computation is needed.
    """
    return Scenario(
        config=_base_config(acknowledges_qbi_below_threshold=True),
        w2s=[
            W2(
                employer="Synthetic Employer C",
                wages=180_000.0,
                federal_tax_withheld=38_000.0,
                ss_wages=176_100.0,
                ss_tax_withheld=10_918.0,
                medicare_wages=180_000.0,
                medicare_tax_withheld=2_610.0,
            ),
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


def build_addl_medicare_boundary() -> Scenario:
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
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer D",
                wages=210_000.0,
                federal_tax_withheld=48_000.0,
                ss_wages=176_100.0,
                ss_tax_withheld=10_918.0,
                medicare_wages=210_000.0,
                medicare_tax_withheld=3_045.0,
            ),
        ],
    )


def build_zero_tax_refund() -> Scenario:
    """Over-withheld scenario: large withholding relative to tax → refund.

    Wages $130,000 (clears EIC gate of $68,676), modest interest.
    Taxable income = $130,500 − $15,750 std deduction = $114,750, which is
    above the IRS $100,000 tax-table cutoff. Above $100k the IRS uses the
    rate schedule directly (no $50-bracket rounding), so the native spine's
    continuous formula agrees with the workbook. Below $100k taxable income
    the IRS publishes a discrete tax table (midpoint-of-$50-bracket) that
    the workbook uses; using the continuous rate schedule produces a $6
    difference for that range. Keeping taxable income above $100k avoids
    that discrepancy without implementing the full tax table here.

    Withholding ($30,000) exceeds expected tax (~$22k) → refund scenario.
    """
    return Scenario(
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer E",
                wages=130_000.0,
                federal_tax_withheld=30_000.0,
                ss_wages=130_000.0,
                ss_tax_withheld=8_060.0,
                medicare_wages=130_000.0,
                medicare_tax_withheld=1_885.0,
            ),
        ],
        form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=500.0),
        ],
    )


def build_owes_tax() -> Scenario:
    """Under-withheld scenario: withholding well below tax liability → owes.

    Wages $130k + LTCG $25k + qualified divs $8k. Withholding $15,000 is
    deliberately low relative to the expected tax (~$30k+) → amount owed.
    """
    return Scenario(
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer F",
                wages=130_000.0,
                federal_tax_withheld=15_000.0,
                ss_wages=130_000.0,
                ss_tax_withheld=8_060.0,
                medicare_wages=130_000.0,
                medicare_tax_withheld=1_885.0,
            ),
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
                date_sold="2025-11-10",
                proceeds=45_000.0,
                cost_basis=20_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_itemizer_with_w2_state_tax() -> Scenario:
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
        config=_base_config(),
        w2s=[
            W2(
                employer="Synthetic Employer G",
                wages=150_000.0,
                federal_tax_withheld=28_000.0,
                ss_wages=150_000.0,
                ss_tax_withheld=9_300.0,
                medicare_wages=150_000.0,
                medicare_tax_withheld=2_175.0,
                state_tax_withheld=9_000.0,  # W-2 box 17 — feeds Sch A line 5a
            ),
        ],
        form1098s=[
            Form1098(
                lender="Synthetic Mortgage Co",
                mortgage_interest=20_000.0,
                property_tax=6_000.0,
            ),
        ],
    )


def build_canonical_wage_investment_rental_2024() -> Scenario:
    """2024 canonical shape: wages + interest + qualified dividends + LTCG + rental.

    Income ~$195,000. Exercises:
    - Sch B interest (< threshold, but present)
    - QDCGT with both 0% and 15% bands active (2024 breakpoints: $0/$47,025/$518,900)
    - Rental property flowing through Sch E → Sch 1 → AGI
    - Standard deduction (2024: $14,600)
    - No Additional Medicare (wages below $200k)

    EIC gate: wages $150k >> $66,819 MFJ 3-child ceiling → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer A",
                wages=150_000.0,
                federal_tax_withheld=28_000.0,
                ss_wages=150_000.0,        # below 2024 SS wage base of $168,600
                ss_tax_withheld=9_300.0,
                medicare_wages=150_000.0,
                medicare_tax_withheld=2_175.0,
            ),
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
                date_sold="2024-06-01",
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


def build_qdcgt_15_to_20_boundary_2024() -> Scenario:
    """2024 QDCGT 15% → 20% boundary: taxable income above $518,900 single breakpoint.

    Wages $500k + $50k LTCG + $20k qualified dividends pushes preferential
    income into the 20% band. Exercises the 20% QDCGT slice.

    EIC gate: wages $500k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer B",
                wages=500_000.0,
                federal_tax_withheld=150_000.0,
                ss_wages=168_600.0,        # 2024 SS wage base
                ss_tax_withheld=10_453.0,
                medicare_wages=500_000.0,
                medicare_tax_withheld=7_250.0,
            ),
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
                date_sold="2024-09-15",
                proceeds=80_000.0,
                cost_basis=30_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_qbi_threshold_boundary_2024() -> Scenario:
    """2024 QBI threshold boundary: income near the $191,950 single-filer QBI threshold.

    Wages $180k + rental income ~$10k brings total near the 2024 QBI threshold.
    acknowledges_qbi_below_threshold=True because no K-1 QBI is present.

    EIC gate: wages $180k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(acknowledges_qbi_below_threshold=True),
        w2s=[
            W2(
                employer="Synthetic Employer C",
                wages=180_000.0,
                federal_tax_withheld=38_000.0,
                ss_wages=168_600.0,        # 2024 SS wage base
                ss_tax_withheld=10_453.0,
                medicare_wages=180_000.0,
                medicare_tax_withheld=2_610.0,
            ),
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


def build_addl_medicare_boundary_2024() -> Scenario:
    """2024 Additional Medicare Tax boundary: wages $210,000 > $200,000 threshold.

    The $10,000 excess × 0.9% = $90 Additional Medicare Tax on Form 8959.
    Wages-only scenario for clean isolation of the Additional-Medicare branch.

    EIC gate: wages $210k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer D",
                wages=210_000.0,
                federal_tax_withheld=48_000.0,
                ss_wages=168_600.0,        # 2024 SS wage base
                ss_tax_withheld=10_453.0,
                medicare_wages=210_000.0,
                medicare_tax_withheld=3_045.0,
            ),
        ],
    )


def build_zero_tax_refund_2024() -> Scenario:
    """2024 over-withheld scenario: large withholding relative to tax → refund.

    Wages $130,000 (clears EIC gate of $66,819), modest interest.
    Taxable income = $130,500 − $14,600 std deduction = $115,900, which is
    above the $100,000 tax-table cutoff (avoids discrete table vs. schedule
    discrepancy).

    Withholding ($30,000) exceeds expected tax (~$22k) → refund scenario.

    EIC gate: wages $130k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer E",
                wages=130_000.0,
                federal_tax_withheld=30_000.0,
                ss_wages=130_000.0,
                ss_tax_withheld=8_060.0,
                medicare_wages=130_000.0,
                medicare_tax_withheld=1_885.0,
            ),
        ],
        form1099_int=[
            Form1099INT(payer="Synthetic Bank", interest=500.0),
        ],
    )


def build_owes_tax_2024() -> Scenario:
    """2024 under-withheld scenario: withholding well below tax liability → owes.

    Wages $130k + LTCG $25k + qualified divs $8k. Withholding $15,000 is
    deliberately low relative to the expected tax (~$30k+) → amount owed.

    EIC gate: wages $130k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer F",
                wages=130_000.0,
                federal_tax_withheld=15_000.0,
                ss_wages=130_000.0,
                ss_tax_withheld=8_060.0,
                medicare_wages=130_000.0,
                medicare_tax_withheld=1_885.0,
            ),
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
                date_sold="2024-11-10",
                proceeds=45_000.0,
                cost_basis=20_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_itemizer_with_w2_state_tax_2024() -> Scenario:
    """2024 single itemizer whose Sch A SALT includes W-2 box 17 state tax.

    Mirror of build_itemizer_with_w2_state_tax with 2024 params + workbook.
    2024 SALT cap is the flat $10,000 (single), so line 5d = 9,000 + 6,000 =
    15,000 caps to line 5e = 10,000; line 17 = 20,000 mortgage + 10,000 =
    30,000, above the 2024 standard deduction ($14,600). This also exercises
    the year-aware SALT cap (the cap binds here, unlike 2025's $40k cap).

    EIC gate: wages $150k >> $66,819 → routes native.
    """
    return Scenario(
        config=_base_config_2024(),
        w2s=[
            W2(
                employer="Synthetic Employer G",
                wages=150_000.0,
                federal_tax_withheld=28_000.0,
                ss_wages=150_000.0,
                ss_tax_withheld=9_300.0,
                medicare_wages=150_000.0,
                medicare_tax_withheld=2_175.0,
                state_tax_withheld=9_000.0,  # W-2 box 17 — feeds Sch A line 5a
            ),
        ],
        form1098s=[
            Form1098(
                lender="Synthetic Mortgage Co",
                mortgage_interest=20_000.0,
                property_tax=6_000.0,
            ),
        ],
    )


# Public battery: list of (name, builder) pairs iterated by the parity test.
BATTERY: list[tuple[str, object]] = [
    ("canonical_wage_investment_rental", build_canonical_wage_investment_rental),
    ("qdcgt_15_to_20_boundary", build_qdcgt_15_to_20_boundary),
    ("qbi_threshold_boundary", build_qbi_threshold_boundary),
    ("addl_medicare_boundary", build_addl_medicare_boundary),
    ("zero_tax_refund", build_zero_tax_refund),
    ("owes_tax", build_owes_tax),
    ("itemizer_with_w2_state_tax", build_itemizer_with_w2_state_tax),
]

# 2024 battery: same branches, 2024 params + 2024 workbook.
BATTERY_2024: list[tuple[str, object]] = [
    ("canonical_wage_investment_rental_2024", build_canonical_wage_investment_rental_2024),
    ("qdcgt_15_to_20_boundary_2024", build_qdcgt_15_to_20_boundary_2024),
    ("qbi_threshold_boundary_2024", build_qbi_threshold_boundary_2024),
    ("addl_medicare_boundary_2024", build_addl_medicare_boundary_2024),
    ("zero_tax_refund_2024", build_zero_tax_refund_2024),
    ("owes_tax_2024", build_owes_tax_2024),
    ("itemizer_with_w2_state_tax_2024", build_itemizer_with_w2_state_tax_2024),
]
