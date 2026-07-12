"""IRS-published 2023 federal parameters (Rev. Proc. 2022-38; SSA 2023 OASDI
wage-base table)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
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
    ordinary_brackets=(
        (11_000.0, 0.10),
        (44_725.0, 0.12),
        (95_375.0, 0.22),
        (182_100.0, 0.24),
        (231_250.0, 0.32),
        (578_125.0, 0.35),
        (math.inf, 0.37),
    ),
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
    # Prior-year SALT cap: a 2023 return looks back to 2022 (also flat
    # $10k/$5k pre-OBBBA, IRC §164(b)(6) unchanged since TCJA).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
)
