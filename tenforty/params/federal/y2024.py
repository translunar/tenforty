"""IRS-published 2024 federal parameters (Rev. Proc. 2023-34, Form 1040 instr.)."""
import datetime
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY.value
_MFS = FilingStatus.MARRIED_FILING_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

# 2024 MFJ EITC maximum-AGI limits keyed by number of qualifying children
# (0, 1, 2, 3+). The largest AGI at which any filing status can claim EITC.
# Conservative scope-gate threshold only; no credit math in the native spine.
_EIC_CEILING = {0: 25_511, 1: 56_004, 2: 62_688, 3: 66_819}

PARAMS = FederalParams(
    year=2024,
    standard_deduction={
        _S: 14_600, _MFJ: 29_200, _MFS: 14_600, _HOH: 21_900, _QW: 29_200,
    },
    # 2024 single tax-rate schedule: (upper_bound, marginal_rate).
    ordinary_brackets={_S: (
        (11_600.0, 0.10),
        (47_150.0, 0.12),
        (100_525.0, 0.22),
        (191_950.0, 0.24),
        (243_725.0, 0.32),
        (609_350.0, 0.35),
        (math.inf, 0.37),
    ),
        # Rev. Proc. 2023-34 §3.01 Table 1 (MFJ / surviving spouses),
        # cross-checked vs 2024 Instructions for Form 1040 Schedule Y-1:
        # https://www.irs.gov/pub/irs-drop/rp-23-34.pdf
        # sha256 544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57
        # https://www.irs.gov/pub/irs-prior/i1040gi--2024.pdf
        # sha256 0ae53ed5020d69e6571d40cd7955b7735f44a28df483626d128628d2810e93d4
        _MFJ: (
            (23_200.0, 0.10),
            (94_300.0, 0.12),
            (201_050.0, 0.22),
            (383_900.0, 0.24),
            (487_450.0, 0.32),
            (731_200.0, 0.35),
            (math.inf, 0.37),
        ),
        # Rev. Proc. 2023-34 §3.01 Table 2 (heads of households),
        # cross-checked vs 2024 Instructions for Form 1040 Schedule Z
        # (same two files/sha256 as above).
        _HOH: (
            (16_550.0, 0.10),
            (63_100.0, 0.12),
            (100_500.0, 0.22),
            (191_950.0, 0.24),
            (243_700.0, 0.32),
            (609_350.0, 0.35),
            (math.inf, 0.37),
        ),
    },
    qdcgt_breakpoints={_S: (47_025, 518_900),
        # Rev. Proc. 2023-34 §3.03 (max zero-rate, max 15%-rate amounts),
        # cross-checked vs 2024 Instructions for Form 1040 QDCGT Worksheet
        # lines 6 and 13:
        # https://www.irs.gov/pub/irs-drop/rp-23-34.pdf
        # sha256 544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57
        # https://www.irs.gov/pub/irs-prior/i1040gi--2024.pdf
        # sha256 0ae53ed5020d69e6571d40cd7955b7735f44a28df483626d128628d2810e93d4
        _MFJ: (94_050, 583_750),
        _HOH: (63_000, 551_350),
    },
    addl_medicare_threshold={_S: 200_000,
        # IRC §3101(b)(2), United States Code 2024 Edition (govinfo):
        # https://www.govinfo.gov/content/pkg/USCODE-2024-title26/html/USCODE-2024-title26-subtitleC-chap21-subchapA-sec3101.htm
        # sha256 605deeac4af4495e76016a671d9bdb610f935f985ac71d94a423db83275cec0d
        _MFJ: 250_000,  # (A) joint return
        _MFS: 125_000,  # (B) ½ of (A)
        _HOH: 200_000,  # (C) any other case
        _QW: 200_000,   # (C) any other case
    },
    ss_wage_base=168_600,  # SSA 2024 OASDI wage base
    # Form 8995 simple-path threshold (Rev. Proc. 2023-34): single $191,950,
    # MFJ = 2× = $383,900 (confirmed against Rev. Proc. 2023-34).
    qbi_threshold={
        _S: 191_950, _MFS: 191_950, _HOH: 191_950,
        # QSS = Rev. Proc. 2023-34 §3.27 "All Other Returns" (191_950), NOT
        # the MFJ amount — adjudicated by Juno 2026-07-11 (Layer-1 catch).
        _MFJ: 383_900, _QW: 191_950,
    },
    # 2024 SALT cap: flat pre-OBBBA $10k / $5k MFS, no income phaseout.
    # salt_phaseout_threshold = None → flat cap, never raises for high MAGI.
    salt_cap_starting={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    salt_phaseout_threshold=None,
    salt_phaseout_rate=0.0,
    salt_cap_floor={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    medical_agi_floor_pct=0.075,  # IRC §213(a), unchanged
    # CARES/CAA above-the-line non-itemizer charitable deduction (Form 1040
    # line 12b) was a 2021-only provision, not extended to 2024.
    nonitemizer_charitable_cap=None,
    # Prior-year SALT cap: a 2024 return looks back at 2023 (also $10k/$5k).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
    # IRC §1211(b) net-capital-loss limitation: $3,000 ($1,500 MFS), NOT
    # inflation-indexed — identical across all supported years.
    capital_loss_limit={
        _S: 3_000, _MFJ: 3_000, _HOH: 3_000, _QW: 3_000, _MFS: 1_500,
    },
    # IRC §461(l) excess-business-loss threshold: 2024 Form 461 line 15,
    # "Enter $305,000 (or $610,000 if married filing jointly)".
    excess_business_loss_threshold={
        _S: 305_000, _MFJ: 610_000, _HOH: 305_000, _QW: 305_000,
        _MFS: 305_000,
    },
    # Rev. Proc. 2023-34, "Aged or blind" paragraph (per-box amount):
    # https://www.irs.gov/pub/irs-drop/rp-23-34.pdf
    # sha256 544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57
    # Increased amount = unmarried and not a surviving spouse.
    additional_standard_deduction={
        _S: 1_950, _HOH: 1_950,
        _MFJ: 1_550, _MFS: 1_550, _QW: 1_550,
    },
    # 2024 Instructions for Form 1040, Age/Blindness checkbox ("born before"):
    # https://www.irs.gov/pub/irs-prior/i1040gi--2024.pdf
    # sha256 0ae53ed5020d69e6571d40cd7955b7735f44a28df483626d128628d2810e93d4
    aged_born_before=datetime.date(1960, 1, 2),
    # Childless EIC (zero qualifying children). Statute first:
    # IRC §32(b)(1) table, "No qualifying children" row — credit percentage
    # 7.65, phaseout percentage 7.65 (§32(n)'s special rules cover only
    # taxable years beginning in 2021; 2024 Pub. 596 "What's New" lists only
    # inflation changes); §32(c)(1)(A)(ii)(II) — "has attained age 25 but not
    # attained age 65 before the close of the taxable year".
    # https://www.law.cornell.edu/uscode/text/26/32
    eic_credit_pct=0.0765,
    eic_phaseout_pct=0.0765,
    # Rev. Proc. 2023-34 §3.06(1) table, "None" column (sha256 above):
    # earned income amount, maximum amount of credit, threshold and
    # completed phaseout amounts (MFJ / all other filing statuses).
    eic_earned_income_amount=8_260,
    eic_max_credit=632,
    eic_phaseout_threshold={_S: 10_330, _MFJ: 17_250},
    eic_completed_phaseout={_S: 18_591, _MFJ: 25_511},
    # Rev. Proc. 2023-34 §3.06(2): not allowed if investment income
    # "exceeds $11,600" (§32(i)); 2024 Form 1040 instructions Step 2 Q2.
    eic_investment_income_limit=11_600,
    # 2024 EIC Table (Instructions for Form 1040 Tax Tables (2024), Cat. No.
    # 24327A): the first row is "At least 1, But less than 50"; Worksheets
    # A/B stop at zero. Ages: 2024 Form 1040 instructions, born after
    # December 31, 1959, and before January 2, 2000.
    eic_min_earned_income=1,
    eic_min_age=25,
    eic_max_age=65,
)
