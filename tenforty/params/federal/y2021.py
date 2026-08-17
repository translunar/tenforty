"""Federal tax-year 2021 parameters (officially sourced, dual-transcription).

Every value below is transcribed verbatim from an official IRS publication.
Sources:
  - Rev. Proc. 2020-45 (TY2021 annual inflation adjustments):
    https://www.irs.gov/pub/irs-drop/rp-20-45.pdf
    - §.16 Standard Deduction
    - §.01 Tax Rate Tables, Table 3 (Unmarried Individuals / Single schedule)
    - §.03 Maximum Capital Gains Rate (zero-rate / 15%-rate breakpoints)
    - §.27 Qualified Business Income (§199A(e)(2) threshold)
    - §.07 Earned Income Credit (completed-phaseout amounts; pre-ARPA)
  - Pub. 596 (2021), Earned Income Credit — ARPA-expanded 2021 EITC income
    limits (the childless completed-phaseout amount that supersedes the
    pre-ARPA Rev. Proc. 2020-45 figure):
    https://www.irs.gov/pub/irs-prior/p596--2021.pdf
  - 2021 Instructions for Schedule A (Form 1040):
    https://www.irs.gov/pub/irs-prior/i1040sca--2021.pdf
    - Line 5 (SALT cap) and Line 1 medical worksheet (7.5% AGI floor)
  - Pub. 15 (Circular E), 2021 revision — Social Security wage base:
    https://www.irs.gov/pub/irs-prior/p15--2021.pdf
  - IRC §1401(b)(2) / §1411 — statutory (non-indexed) Additional Medicare
    thresholds.
  - IRC §164(b)(6) — statutory flat SALT cap (pre-OBBBA).
"""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QSS = FilingStatus.QUALIFYING_WIDOW.value


PARAMS = FederalParams(
    year=2021,
    # Rev. Proc. 2020-45 §.16(1) Standard Deduction. QSS shares the
    # "Married Individuals Filing Joint Returns and Surviving Spouses" row.
    standard_deduction={
        _S: 12_550,    # Unmarried Individuals (other than SS and HoH)
        _MFJ: 25_100,  # Married Filing Jointly and Surviving Spouses
        _MFS: 12_550,  # Married Individuals Filing Separate Returns
        _HOH: 18_800,  # Heads of Households
        _QSS: 25_100,  # Surviving Spouses (== MFJ row)
    },
    # Rev. Proc. 2020-45 §.01, Table 3 — Section 1(j)(2)(C), Unmarried
    # Individuals (other than Surviving Spouses and Heads of Households).
    # Single-scoped rate spine: (upper_bound, marginal_rate), ascending.
    ordinary_brackets=(
        (9_950.0, 0.10),     # Not over $9,950
        (40_525.0, 0.12),    # $9,950–$40,525
        (86_375.0, 0.22),    # $40,525–$86,375
        (164_925.0, 0.24),   # $86,375–$164,925
        (209_425.0, 0.32),   # $164,925–$209,425
        (523_600.0, 0.35),   # $209,425–$523,600
        (math.inf, 0.37),    # Over $523,600
    ),
    # Rev. Proc. 2020-45 §.03 Maximum Capital Gains Rate.
    # (Maximum Zero-Rate Amount [§1(h)(1)(B)(i)],
    #  Maximum 15%-Rate Amount [§1(h)(1)(C)(ii)(I)]).
    # QSS shares the "joint return or surviving spouse" figures.
    qdcgt_breakpoints={
        _S: (40_400, 445_850),     # any other individual
        _MFJ: (80_800, 501_600),   # joint return or surviving spouse
        _MFS: (40_400, 250_800),   # married filing separately
        _HOH: (54_100, 473_750),   # head of household
        _QSS: (80_800, 501_600),   # surviving spouse (== MFJ)
    },
    # Statutory Additional Medicare Tax thresholds, IRC §1401(b)(2) /
    # §1411 — fixed by statute, NOT inflation-adjusted (unchanged for 2021).
    # QSS is grouped with "all other" (200,000), NOT with MFJ.
    addl_medicare_threshold={
        _S: 200_000,
        _MFJ: 250_000,
        _MFS: 125_000,
        _HOH: 200_000,
        _QSS: 200_000,
    },
    # Pub. 15 (2021), "The social security wage base limit is $142,800."
    ss_wage_base=142_800,
    # Rev. Proc. 2020-45 §.27 — §199A(e)(2) threshold amount.
    # "$329,800 for married filing joint returns, $164,925 for married
    #  filing separate returns, and $164,900 for all other returns."
    # QSS grouped with "All Other Returns" ($164,900), NOT MFJ.
    qbi_threshold={
        _S: 164_900,
        _MFJ: 329_800,
        _MFS: 164_925,
        _HOH: 164_900,
        _QSS: 164_900,
    },
    # 2021 Instructions for Schedule A, Line 5: SALT deduction "generally
    # limited to $10,000 ($5,000 if married filing separately)."
    # IRC §164(b)(6), pre-OBBBA flat cap.
    salt_cap_starting={
        _S: 10_000,
        _MFJ: 10_000,
        _MFS: 5_000,
        _HOH: 10_000,
        _QSS: 10_000,
    },
    # 2021 is a FLAT cap with no income-based phaseout (OBBBA phaseout is a
    # 2025+ construct). None = documented no-op sentinel; rate 0.0.
    salt_phaseout_threshold=None,
    salt_phaseout_rate=0.0,
    # For a flat-cap year the floor simply IS the flat cap (IRC §164(b)(6)).
    salt_cap_floor={
        _S: 10_000,
        _MFJ: 10_000,
        _MFS: 5_000,
        _HOH: 10_000,
        _QSS: 10_000,
    },
    # 2021 Instructions for Schedule A, Line 1 medical worksheet: deductible
    # medical/dental expenses are those exceeding 7.5% of AGI (IRC §213(a)).
    medical_agi_floor_pct=0.075,
    # CARES Act §2204 / CAA 2021 §212 (as extended): 2021 above-the-line
    # cash-charitable deduction for filers who do NOT itemize (Form 1040
    # line 12b). Certifies the single-filer $300 cap only (attested).
    # Non-single 12b exists in the IRS workbook but is uncertified in
    # tenforty and refuses at load; per-status support requires attestation
    # + verified workbook over-cap semantics. MFJ $600 unmodeled.
    # One-year-only provision, not extended past 2021.
    nonitemizer_charitable_cap=300,
    # SALT cap that applied in the prior year (2020) for the state-refund
    # tax-benefit lookback. 2020 was also the pre-OBBBA flat cap
    # ($10,000; $5,000 MFS), IRC §164(b)(6).
    prior_year_salt_cap={
        _S: 10_000,
        _MFJ: 10_000,
        _MFS: 5_000,
        _HOH: 10_000,
        _QSS: 10_000,
    },
    # EITC completed-phaseout amounts (highest AGI ceiling = MFJ column).
    # Pub. 596 (2021) income limits, which reflect the ARPA temporary
    # expansion of the childless (0-child) EITC for 2021 — $27,380 MFJ,
    # materially higher than the pre-ARPA Rev. Proc. 2020-45 figure
    # ($21,920 MFJ). The 1/2/3+ figures match both Pub. 596 (2021) and
    # Rev. Proc. 2020-45 §.07.
    eic_income_ceiling={
        0: 27_380,   # Pub. 596 (2021): $27,380 MFJ (ARPA-expanded)
        1: 48_108,   # Pub. 596 (2021) / Rev. Proc. 2020-45: $48,108 MFJ
        2: 53_865,   # Pub. 596 (2021) / Rev. Proc. 2020-45: $53,865 MFJ
        3: 57_414,   # Pub. 596 (2021) / Rev. Proc. 2020-45: $57,414 MFJ
    },
    # IRC §1211(b) net-capital-loss limitation: $3,000 ($1,500 MFS). This
    # figure is STATUTORY, NOT inflation-indexed — identical across every
    # supported year (2021-2025). No year-by-year table exists for it.
    capital_loss_limit={
        _S: 3_000,
        _MFJ: 3_000,
        _MFS: 1_500,
        _HOH: 3_000,
        _QSS: 3_000,
    },
)
