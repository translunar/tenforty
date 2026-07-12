"""IRS-published 2022 federal parameters.

Inflation-adjusted amounts: Rev. Proc. 2021-45 (the TY2022 annual
inflation-adjustment revenue procedure, https://www.irs.gov/pub/irs-drop/rp-21-45.pdf).
Statutory (non-inflation-adjusted) amounts confirmed against the 2022
Instructions for Schedule A (https://www.irs.gov/pub/irs-prior/i1040sca--2022.pdf).
SSA OASDI wage base confirmed against IRS Pub. 15 (Circular E), 2022 revision
(https://www.irs.gov/pub/irs-prior/p15--2022.pdf).
"""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

# 2022 EITC "Completed Phaseout Amount (Married Filing Jointly)" keyed by number
# of qualifying children (0, 1, 2, 3+). Rev. Proc. 2021-45 §3.06(1), table:
# None=$22,610, One=$49,622, Two=$55,529, Three or More=$59,187. The largest AGI
# at which any filing status can claim EITC (MFJ column is the highest by
# construction). Conservative scope-gate threshold only; no credit math in the
# native spine.
_EIC_CEILING = {0: 22_610, 1: 49_622, 2: 55_529, 3: 59_187}

PARAMS = FederalParams(
    year=2022,
    # Rev. Proc. 2021-45 §3.15(1): MFJ & Surviving Spouses $25,900; HOH
    # $19,400; Unmarried Individuals (other than SS/HOH) $12,950; MFS $12,950.
    # QSS is listed in the SAME ROW as MFJ ("...and Surviving Spouses") -> QSS
    # takes the MFJ value.
    standard_deduction={
        _S: 12_950, _MFJ: 25_900, _MFS: 12_950, _HOH: 19_400, _QW: 25_900,
    },
    # 2022 single tax-rate schedule: (upper_bound, marginal_rate).
    # Rev. Proc. 2021-45 §3.01, TABLE 3 (Section 1(j)(2)(C) — Unmarried
    # Individuals other than Surviving Spouses and Heads of Households).
    ordinary_brackets=(
        (10_275.0, 0.10),
        (41_775.0, 0.12),
        (89_075.0, 0.22),
        (170_050.0, 0.24),
        (215_950.0, 0.32),
        (539_900.0, 0.35),
        (math.inf, 0.37),
    ),
    # Rev. Proc. 2021-45 §3.03 (Maximum Capital Gains Rate), each value is
    # (Maximum Zero Rate Amount, Maximum 15% Rate Amount). "Joint return or
    # surviving spouse" = MFJ & QSS ($83,350 / $517,200); MFS ($41,675 /
    # $258,600); HOH ($55,800 / $488,500); "any other individual" = single
    # ($41,675 / $459,750).
    qdcgt_breakpoints={
        _S: (41_675, 459_750),
        _MFJ: (83_350, 517_200),
        _MFS: (41_675, 258_600),
        _HOH: (55_800, 488_500),
        _QW: (83_350, 517_200),
    },
    # STATUTORY, IRC §3101(b)(2) / §1411 — not inflation-adjusted, same every
    # year. MFJ 250,000; MFS 125,000; single/HOH/QSS 200,000 (QSS grouped with
    # "all other" statuses per statute, NOT with MFJ).
    addl_medicare_threshold={
        _S: 200_000, _MFJ: 250_000, _MFS: 125_000, _HOH: 200_000, _QW: 200_000,
    },
    # IRS Pub. 15 (Circular E), 2022 revision, "Social security and Medicare tax
    # for 2022": "The social security wage base limit is $147,000."
    ss_wage_base=147_000,
    # Form 8995 simple-path threshold amount, Rev. Proc. 2021-45 §3.27
    # (§199A(e)(2)): MFJ $340,100; MFS $170,050; "All Other Returns" $170,050.
    # QSS is grouped with "All Other Returns" per the QSS mapping gloss, NOT
    # with MFJ.
    qbi_threshold={
        _S: 170_050, _MFS: 170_050, _HOH: 170_050, _MFJ: 340_100, _QW: 170_050,
    },
    # 2022 SALT cap: flat pre-OBBBA $10k / $5k MFS, no income phaseout.
    # IRC §164(b)(6). Confirmed by 2022 Instructions for Schedule A, Line 5e:
    # "generally limited to $10,000 ($5,000 if married filing separately)."
    # salt_phaseout_threshold = None -> flat cap, never raises for high MAGI.
    salt_cap_starting={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    salt_phaseout_threshold=None,
    salt_phaseout_rate=0.0,
    salt_cap_floor={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    # 2022 Instructions for Schedule A, Medical and Dental Expenses: "You can
    # deduct only the part of your medical and dental expenses that exceeds 7.5%
    # of the amount of your adjusted gross income." IRC §213(a), permanent 7.5%.
    medical_agi_floor_pct=0.075,
    # Prior-year SALT cap: a 2022 return looks back to 2021 (also flat $10k/$5k
    # pre-OBBBA, IRC §164(b)(6) unchanged since TCJA for 2018-2025).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
)
