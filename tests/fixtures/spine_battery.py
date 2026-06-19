"""Synthetic scenario battery for the 2025 penny-parity gate.

Each builder returns a single-filer Scenario whose income is high enough to
clear the EIC scope-gate (wages ≥ $68,676, the MFJ no-child ceiling), so
_compute_1040_pipeline routes to the native spine rather than the workbook.

All identities and amounts are fully synthetic — no real personal data.

Key 2025 boundaries exercised:
  - canonical_wage_investment_rental: wage + interest + qdivs + LTCG + rental
  - qdcgt_15_to_20_boundary:          QDCGT shifts into 20% band (income > $533,400)
  - qbi_threshold_boundary:            income near QBI phase-out threshold ($197,300)
  - addl_medicare_boundary:            wages just above $200,000 Additional Medicare
  - zero_tax_refund:                   withholding > tax → overpaid / refund
  - owes_tax:                          withholding < tax → amount owed
"""

from tenforty.models import (
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

    NO investment income: NIIT (Form 8960) is not implemented in the native
    spine but is computed by the oracle workbook. Including dividends with
    AGI > $200k would cause the oracle's overpaid to differ from native's
    by the NIIT amount. Keeping this scenario wages-only ensures the oracle
    and native agree on overpaid and total_tax (both line-16 income tax only).
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


# Public battery: list of (name, builder) pairs iterated by the parity test.
BATTERY: list[tuple[str, object]] = [
    ("canonical_wage_investment_rental", build_canonical_wage_investment_rental),
    ("qdcgt_15_to_20_boundary", build_qdcgt_15_to_20_boundary),
    ("qbi_threshold_boundary", build_qbi_threshold_boundary),
    ("addl_medicare_boundary", build_addl_medicare_boundary),
    ("zero_tax_refund", build_zero_tax_refund),
    ("owes_tax", build_owes_tax),
]
