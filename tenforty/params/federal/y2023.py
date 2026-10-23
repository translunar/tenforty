"""IRS-published 2023 federal parameters (Rev. Proc. 2022-38; SSA 2023 OASDI
wage-base table)."""
import datetime
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY.value
_MFS = FilingStatus.MARRIED_FILING_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

# 2023 MFJ EITC completed-phaseout (maximum) AGI limits keyed by number of
# qualifying children (0, 1, 2, 3+). Rev. Proc. 2022-38 §3.06, "Completed
# Phaseout Amount (Married Filing Jointly)" row: None=$24,210, One=$53,120,
# Two=$59,478, Three or More=$63,398. The largest AGI at which any filing
# status can claim EITC. Conservative scope-gate threshold only; no credit
# math in the native spine.
_EIC_CEILING = {0: 24_210, 1: 53_120, 2: 59_478, 3: 63_398}

PARAMS = FederalParams(
    year=2023,
    # Rev. Proc. 2022-38 §3.15(1): MFJ & Surviving Spouses $27,700; HOH
    # $20,800; Unmarried Individuals (other than SS/HOH) $13,850; MFS
    # $13,850. QSS is listed in the SAME ROW as MFJ ("...and Surviving
    # Spouses") -> QSS takes the MFJ value.
    standard_deduction={
        _S: 13_850, _MFJ: 27_700, _MFS: 13_850, _HOH: 20_800, _QW: 27_700,
    },
    # 2023 single tax-rate schedule: (upper_bound, marginal_rate).
    # Rev. Proc. 2022-38 §3.01, Table 3 (Section 1(j)(2)(C) — Unmarried
    # Individuals other than Surviving Spouses and Heads of Households).
    ordinary_brackets={_S: (
        (11_000.0, 0.10),
        (44_725.0, 0.12),
        (95_375.0, 0.22),
        (182_100.0, 0.24),
        (231_250.0, 0.32),
        (578_125.0, 0.35),
        (math.inf, 0.37),
    ),
        # Rev. Proc. 2022-38 §3.01 Table 1 (MFJ / surviving spouses),
        # cross-checked vs 2023 Instructions for Form 1040 Schedule Y-1 and
        # Tax Computation Worksheet Section B:
        # https://www.irs.gov/pub/irs-drop/rp-22-38.pdf
        # sha256 6c20f8a6c9a3bdf4251fcf50dbf2e2382abc8cbeb1e5e2d3eecdc38b2cbf6bbf
        # https://www.irs.gov/pub/irs-prior/i1040gi--2023.pdf
        # sha256 90c8759c7a829d8c74296187cdbdb47bc9025480fffc41ff5e7225889c8fea7e
        _MFJ: (
            (22_000.0, 0.10),
            (89_450.0, 0.12),
            (190_750.0, 0.22),
            (364_200.0, 0.24),
            (462_500.0, 0.32),
            (693_750.0, 0.35),
            (math.inf, 0.37),
        ),
        # Rev. Proc. 2022-38 §3.01 Table 2 (heads of households),
        # cross-checked vs 2023 Instructions for Form 1040 Schedule Z and
        # Tax Computation Worksheet Section D (same two files/sha256 as above).
        _HOH: (
            (15_700.0, 0.10),
            (59_850.0, 0.12),
            (95_350.0, 0.22),
            (182_100.0, 0.24),
            (231_250.0, 0.32),
            (578_100.0, 0.35),
            (math.inf, 0.37),
        ),
    },
    # Rev. Proc. 2022-38 §3.03 (Maximum Capital Gains Rate), each value is
    # (Maximum Zero Rate Amount, Maximum 15% Rate Amount). "Married
    # Individuals Filing Joint Returns and Surviving Spouse" row = MFJ & QSS
    # ($89,250 / $553,850); MFS row ($44,625 / $276,900); HOH row ($59,750 /
    # $523,050); "All Other Individuals" row = single ($44,625 / $492,300).
    qdcgt_breakpoints={
        _S: (44_625, 492_300),
        _MFJ: (89_250, 553_850),
        _MFS: (44_625, 276_900),
        _HOH: (59_750, 523_050),
        _QW: (89_250, 553_850),
    },
    # STATUTORY, IRC §3101(b)(2) / §1411 — not inflation-adjusted, same every
    # year. MFJ 250,000; MFS 125,000; single/HOH/QSS 200,000 (QSS grouped
    # with "all other" statuses per statute, NOT with MFJ).
    addl_medicare_threshold={
        _S: 200_000, _MFJ: 250_000, _MFS: 125_000, _HOH: 200_000, _QW: 200_000,
    },
    ss_wage_base=160_200,  # SSA OASDI contribution & benefit base table (ssa.gov/oact/cola/cbb.html), 2023 row = 160,200
    # Form 8995 simple-path threshold amount, Rev. Proc. 2022-38 §3.27
    # (§199A(e)(2)): MFJ $364,200; MFS $182,100; "All Other Returns"
    # $182,100. QSS is grouped with "All Other Returns" per the Rev. Proc.
    # row labels, NOT with MFJ.
    qbi_threshold={
        _S: 182_100, _MFS: 182_100, _HOH: 182_100, _MFJ: 364_200, _QW: 182_100,
    },
    # 2023 SALT cap: flat pre-OBBBA $10k / $5k MFS, no income phaseout.
    # IRC §164(b)(6). salt_phaseout_threshold = None -> flat cap, never
    # raises for high MAGI.
    salt_cap_starting={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    salt_phaseout_threshold=None,
    salt_phaseout_rate=0.0,
    salt_cap_floor={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    medical_agi_floor_pct=0.075,  # IRC §213(a), permanent 7.5% floor
    # CARES/CAA above-the-line non-itemizer charitable deduction (Form 1040
    # line 12b) was a 2021-only provision, not extended to 2023.
    nonitemizer_charitable_cap=None,
    # Prior-year SALT cap: a 2023 return looks back to 2022 (also flat
    # $10k/$5k pre-OBBBA, IRC §164(b)(6) unchanged since TCJA).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
    # IRC §1211(b) net-capital-loss limitation: $3,000 ($1,500 MFS), NOT
    # inflation-indexed — identical across all supported years.
    capital_loss_limit={
        _S: 3_000, _MFJ: 3_000, _HOH: 3_000, _QW: 3_000, _MFS: 1_500,
    },
    # IRC §461(l) excess-business-loss threshold: 2023 Form 461 line 15,
    # "Enter $289,000 (or $578,000 if married filing jointly)".
    excess_business_loss_threshold={
        _S: 289_000, _MFJ: 578_000, _HOH: 289_000, _QW: 289_000,
        _MFS: 289_000,
    },
    # Rev. Proc. 2022-38, "Aged or blind" paragraph (per-box amount):
    # https://www.irs.gov/pub/irs-drop/rp-22-38.pdf
    # sha256 6c20f8a6c9a3bdf4251fcf50dbf2e2382abc8cbeb1e5e2d3eecdc38b2cbf6bbf
    # Increased amount = unmarried and not a surviving spouse.
    additional_standard_deduction={
        _S: 1_850, _HOH: 1_850,
        _MFJ: 1_500, _MFS: 1_500, _QW: 1_500,
    },
    # 2023 Instructions for Form 1040, Age/Blindness checkbox ("born before"):
    # https://www.irs.gov/pub/irs-prior/i1040gi--2023.pdf
    # sha256 90c8759c7a829d8c74296187cdbdb47bc9025480fffc41ff5e7225889c8fea7e
    aged_born_before=datetime.date(1959, 1, 2),
    # Childless EIC (zero qualifying children). Statute first:
    # IRC §32(b)(1) table, "No qualifying children" row — credit percentage
    # 7.65, phaseout percentage 7.65 (§32(n)'s special rules cover only
    # taxable years beginning in 2021; 2023 Pub. 596 "What's New" lists only
    # inflation changes); §32(c)(1)(A)(ii)(II) — "has attained age 25 but not
    # attained age 65 before the close of the taxable year".
    # https://www.law.cornell.edu/uscode/text/26/32
    eic_credit_pct=0.0765,
    eic_phaseout_pct=0.0765,
    # Rev. Proc. 2022-38 §3.06(1) table, "None" column (sha256 above):
    # earned income amount, maximum amount of credit, threshold and
    # completed phaseout amounts (single etc. / married filing jointly).
    eic_earned_income_amount=7_840,
    eic_max_credit=600,
    eic_phaseout_threshold={_S: 9_800, _MFJ: 16_370},
    eic_completed_phaseout={_S: 17_640, _MFJ: 24_210},
    # Rev. Proc. 2022-38 §3.06(2): not allowed if investment income
    # "exceeds $11,000" (§32(i)); 2023 Form 1040 instructions Step 2 Q2.
    eic_investment_income_limit=11_000,
    # 2023 EIC Table (Tax and Earned Income Credit Tables (2023), Cat. No.
    # 24327A): the first row is "At least 1, But less than 50"; Worksheets
    # A/B stop at zero. Ages: 2023 Form 1040 instructions, born after
    # December 31, 1958, and before January 2, 1999.
    eic_min_earned_income=1,
    eic_min_age=25,
    eic_max_age=65,
)
