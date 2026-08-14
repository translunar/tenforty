"""Synthetic scenario battery for the penny-parity gate, generated per year.

Each builder takes the tax year and returns a single-filer Scenario whose
income is high enough to clear the EIC scope-gate, so _compute_1040_pipeline
routes to the native spine rather than the workbook. battery_for(year)
yields the same eleven boundary scenarios for any supported year (plus a
2021-only twelfth, the ARPA unemployment-compensation special rule) —
adding a year adds zero code here.

All identities and amounts are fully synthetic — no real personal data.
"""
import functools
from collections.abc import Callable

from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Form1098,
    Form1099DIV,
    Form1099INT,
    Form1099B,
    RentalProperty,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)
from tenforty.params.federal import load as load_params
from tenforty.params import f8962 as f8962_params
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


def build_net_short_term_gain_with_ltcg_and_qualdiv(year: int) -> Scenario:
    """Net SHORT-term capital gain alongside net LONG-term gain and
    qualified dividends -- the shape that exposed bug #10 (found
    2026-07-18): the QDCGT worksheet's preferential base must be capped at
    Sch D line 15 (net LTCG), NOT line 16 (net ST + LT), so a net ST gain
    stays ORDINARY income rather than getting the 0/15/20% preferential
    rate. No prior battery scenario mixed a net ST gain with LTCG/qualified
    dividends in the same return, so the workbook-vs-native parity gate
    never exercised this branch -- this scenario closes that hole.

    Wages $130k (clears the EIC gate) + a short-term lot (gain $6,000) +
    a long-term lot (gain $15,000) + $5,000 qualified dividends (of $6,000
    ordinary). Both Sch D line 7 (net ST) and line 15 (net LT) are
    individually positive and material at once -- the exact shape the
    QDCGT worksheet must split correctly.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer I", wages=130_000.0,
                federal_tax_withheld=22_000.0),
        ],
        form1099_div=[
            Form1099DIV(
                payer="Synthetic Brokerage",
                ordinary_dividends=6_000.0,
                qualified_dividends=5_000.0,
            ),
        ],
        form1099_b=[
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Short-Term Lot",
                date_acquired=f"{year}-02-01",
                date_sold=f"{year}-08-01",
                proceeds=21_000.0,
                cost_basis=15_000.0,
                short_term=True,
                basis_reported_to_irs=True,
            ),
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Long-Term Lot",
                date_acquired=f"{year - 2}-04-01",
                date_sold=f"{year}-09-01",
                proceeds=55_000.0,
                cost_basis=40_000.0,
                short_term=False,
                basis_reported_to_irs=True,
            ),
        ],
    )


def build_capital_loss_over_cap(year: int) -> Scenario:
    """Net capital LOSS materially LARGER than the IRC §1211(b) limit — the
    BINDING case for `capital_loss_limit`.

    A single long-term lot sold at a $50,000 loss (proceeds $20,000 against
    a $70,000 basis) against wages of $130,000. Sch D line 16 is therefore
    about -$50,000, more than sixteen times the $3,000 single-filer cap, so
    the limitation binds by a wide margin rather than by a rounding hair: a
    cap that silently stopped applying would move taxable income by $47,000,
    not by pennies.

    Wages $130,000 clear every year's EIC ceiling, so the return routes to
    the native spine. Once the cap is honored, taxable income lands near
    $112,000-$114,000 depending on the year's standard deduction — above the
    $100,000 tax-table cutoff, where the rate schedule and the published
    table coincide (see build_zero_tax_refund for why that matters).

    NOTE: nothing consumes `capital_loss_limit` yet — the Sch D line-21 cap
    and its transfer to Form 1040 line 7 land in later commits. Until then
    this scenario carries the shape but the spine still deducts the loss in
    full; that ordering is deliberate.
    """
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer J", wages=130_000.0,
                federal_tax_withheld=24_000.0),
        ],
        form1099_b=[
            Form1099B(
                broker="Synthetic Broker",
                description="Synthetic Loss Lot",
                date_acquired=f"{year - 3}-04-01",
                date_sold=f"{year}-07-01",
                proceeds=20_000.0,
                cost_basis=70_000.0,
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


def build_qbi_k1_deduction(year: int) -> Scenario:
    """QBI deduction ACTIVE: single filer whose S-corp K-1 qualified business
    income produces a nonzero Section 199A (Form 8995) deduction.

    Distinct from qbi_threshold_boundary (which has NO K-1 and just attests
    below-threshold): here wages $80k + $20k K-1 QBI put AGI ~$100k — well
    clear of the EIC ceiling so the return stays on the native spine
    (see _scenario_in_spine_scope), yet taxable income (~$86k) is far below
    the lowest single-filer QBI threshold ($164,900, 2021), so the deduction
    is a clean 20% with no phase-in / W-2-wage-limitation complexity in any
    supported year. The parity gate proves the exact figure native-vs-oracle;
    this fixture only guarantees QBI is materially present.
    """
    return Scenario(
        config=_battery_config(
            year,
            acknowledges_qbi_below_threshold=True,
            acknowledges_unlimited_at_risk=True,
            basis_tracked_externally=True,
            acknowledges_no_partnership_se_earnings=True,
            acknowledges_no_section_1231_gain=True,
            acknowledges_no_more_than_four_k1s=True,
            acknowledges_no_k1_credits=True,
            acknowledges_no_section_179=True,
            acknowledges_no_estate_trust_k1=True,
            prior_year_itemized=False,
        ),
        w2s=[
            _w2(year, employer="Synthetic Employer QBI", wages=80_000.0,
                federal_tax_withheld=12_000.0),
        ],
        schedule_k1s=[ScheduleK1(
            entity_name="Synthetic S-Corp QBI Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=20_000.0, qbi_amount=20_000.0,
        )],
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


def build_wage_with_estimated_payments(year: int) -> Scenario:
    """Existing wage shape + a nonzero verbatim estimated tax payment (line
    26). Exercises the estimated-payments channel end-to-end through
    total_payments: native spine reads config.estimated_tax_payments
    directly, the workbook reads the EstimatedTaxPayments named range via
    the flattener's conditional emission.
    """
    return Scenario(
        config=_battery_config(year, estimated_tax_payments=8_000.0),
        w2s=[
            _w2(year, employer="Synthetic Employer A", wages=90_000.0,
                federal_tax_withheld=9_000.0),
        ],
    )


def _ptc_months(
    by_month: dict[int, tuple[float, float, float]],
) -> tuple[Form1095AMonth, ...]:
    """Build the 12-entry Form1095AMonth block. `by_month` maps 1-indexed
    month numbers to (premium, slcsp, aptc); months not given are
    all-zero — the correct workbook input for an uncovered month."""
    return tuple(
        Form1095AMonth(*by_month[n]) if n in by_month else Form1095AMonth()
        for n in range(1, 13)
    )


def build_ptc_net_credit(year: int) -> Scenario:
    """PTC entitlement exceeds APTC received → net credit (Form 8962 line
    26 > 0). Wages = 2.50x the year's FPL (household size 1), landing
    household income in the 200-300% FPL band. Full-year coverage,
    premium/SLCSP/APTC steady at $600/$550/$300 a month — the $300 APTC
    under-collects relative to the entitled credit at that FPL%, so line
    26 (net PTC) is positive and line 29 (repayment) is 0.
    """
    fpl = f8962_params.load(year).fpl_single_48
    wages = round(2.50 * fpl)
    months = _ptc_months({n: (600.0, 550.0, 300.0) for n in range(1, 13)})
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer PTC1", wages=float(wages),
                federal_tax_withheld=round(wages * 0.12)),
        ],
        form_1095a=Form1095A(months=months),
    )


def build_ptc_capped_repayment(year: int) -> Scenario:
    """Excess APTC repayment hits the 200-300% FPL band's statutory cap
    (Form 8962 line 28/29), rather than repaying the full excess. Same
    wages/FPL-band as ptc_net_credit (2.50x FPL, single filer), but
    APTC is bumped to $550/mo (matching SLCSP) so the taxpayer received
    more subsidy than they were entitled to — the repayment limitation
    caps the amount owed back instead of it being dollar-for-dollar.
    """
    fpl = f8962_params.load(year).fpl_single_48
    wages = round(2.50 * fpl)
    months = _ptc_months({n: (600.0, 550.0, 550.0) for n in range(1, 13)})
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer PTC2", wages=float(wages),
                federal_tax_withheld=round(wages * 0.12)),
        ],
        form_1095a=Form1095A(months=months),
    )


def build_ptc_partial_year_401(year: int) -> Scenario:
    """Household income lands over the 400%-FPL boundary (Form 8962 line 5
    == 401 in every supported year) AND coverage is partial-year (Aug-Dec
    only; Jan-Jul carry all-zero premium/SLCSP/APTC — the correct
    workbook input for uncovered months). Wages = 4.50x the year's FPL.
    Exercises both the 400%-boundary line-5 rule and the partial-year
    monthly-row shape in the same scenario.
    """
    fpl = f8962_params.load(year).fpl_single_48
    wages = round(4.50 * fpl)
    months = _ptc_months({n: (600.0, 550.0, 550.0) for n in range(8, 13)})
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer PTC3", wages=float(wages),
                federal_tax_withheld=round(wages * 0.15)),
        ],
        form_1095a=Form1095A(months=months),
    )


def build_ptc_2021_ui_flat133(year: int) -> Scenario:
    """2021-only ARPA unemployment-compensation special rule: a filer who
    received unemployment compensation during 2021 has Form 8962 line 5
    set flat to 133, bypassing the normal FPL% computation. Wages = 3.00x
    the year's FPL (which would otherwise land well inside the normal
    200-300% band) with full-year coverage and $0 APTC, so the scenario
    clearly demonstrates the flat-133 override rather than coincidentally
    landing there anyway.
    """
    assert year == 2021, "the 2021 UI flat-133 rule only applies in 2021"
    fpl = f8962_params.load(year).fpl_single_48
    wages = round(3.00 * fpl)
    months = _ptc_months({n: (600.0, 550.0, 0.0) for n in range(1, 13)})
    return Scenario(
        config=_battery_config(year),
        w2s=[
            _w2(year, employer="Synthetic Employer PTC4", wages=float(wages),
                federal_tax_withheld=round(wages * 0.10)),
        ],
        form_1095a=Form1095A(months=months, received_unemployment_2021=True),
    )


def build_charitable_nonitemizer_2021(year: int) -> Scenario:
    """2021-only line 12b: the CARES/CAA above-the-line cash-charitable
    deduction for NON-ITEMIZERS. Single filer, standard deduction (no
    itemized_deductions), a round $250 contribution (under the $300
    single-filer cap) — the only load-survivable combination (single +
    standard-deduction + amount <= cap; non-single, itemizing, and
    over-cap are all refused at load).
    """
    assert year == 2021, "line-12b non-itemizer charitable is 2021-only"
    return Scenario(
        config=_battery_config(year, charitable_cash_nonitemizer=250.0),
        w2s=[
            _w2(year, employer="Synthetic Employer A", wages=60_000.0,
                federal_tax_withheld=6_000.0),
        ],
    )


_BUILDERS: list[tuple[str, Callable[[int], Scenario]]] = [
    ("canonical_wage_investment_rental", build_canonical_wage_investment_rental),
    ("qdcgt_15_to_20_boundary", build_qdcgt_15_to_20_boundary),
    ("net_short_term_gain_with_ltcg_and_qualdiv",
     build_net_short_term_gain_with_ltcg_and_qualdiv),
    ("capital_loss_over_cap", build_capital_loss_over_cap),
    ("qbi_threshold_boundary", build_qbi_threshold_boundary),
    ("qbi_k1_deduction", build_qbi_k1_deduction),
    ("addl_medicare_boundary", build_addl_medicare_boundary),
    ("zero_tax_refund", build_zero_tax_refund),
    ("owes_tax", build_owes_tax),
    ("tax_table_band", build_tax_table_band),
    ("itemizer_with_w2_state_tax", build_itemizer_with_w2_state_tax),
    ("ptc_net_credit", build_ptc_net_credit),
    ("ptc_capped_repayment", build_ptc_capped_repayment),
    ("ptc_partial_year_401", build_ptc_partial_year_401),
    ("wage_with_estimated_payments", build_wage_with_estimated_payments),
]

# 2021-only: the ARPA unemployment-compensation special rule (Form 8962
# line 5 flat-133 override) is meaningless outside 2021, so it is NOT in
# _BUILDERS — battery_for() splices it in only when year == 2021.
_YEAR_2021_ONLY_BUILDERS: list[tuple[str, Callable[[int], Scenario]]] = [
    ("ptc_2021_ui_flat133", build_ptc_2021_ui_flat133),
    ("charitable_nonitemizer_2021", build_charitable_nonitemizer_2021),
]


def battery_for(year: int) -> list[tuple[str, Callable[[], Scenario]]]:
    """The parity battery for a year: (name, zero-arg builder) pairs.

    Every year gets the shared _BUILDERS set; 2021 additionally gets the
    2021-only ARPA unemployment-compensation scenario.
    """
    builders = _BUILDERS + (_YEAR_2021_ONLY_BUILDERS if year == 2021 else [])
    return [(name, functools.partial(build, year)) for name, build in builders]
