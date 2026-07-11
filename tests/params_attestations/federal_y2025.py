"""Air-gapped attestation of FEDERAL params, tax year 2025.

Independently transcribed from official IRS/SSA publications ONLY — see SOURCES.
This module exists to cross-check tenforty's own federal params; it was written
without reading any tenforty param value, test, tax-table CSV, or git history.

TY2025 is affected by the One Big Beautiful Bill (OBBBA / "Working Families Tax
Cuts"), which changed two things transcribed here relative to the original
Rev. Proc. 2024-40 amounts:
  1. Standard deduction was raised (single/MFS $15,750, MFJ/QSS $31,500,
     HoH $23,625) — the in-effect 2025 amounts, sourced from the IRS OBBBA
     "New and enhanced deductions" page, NOT the superseded Rev. Proc. amounts.
  2. SALT cap raised to $40,000 ($20,000 MFS) with a MAGI-based phase-down
     above $500,000 ($250,000 MFS) at 30%, floored at $10,000 ($5,000 MFS).
Tax brackets, QDCGT breakpoints, §199A QBI threshold, and EIC ceilings for 2025
were NOT changed by OBBBA and remain the Rev. Proc. 2024-40 inflation amounts.

Notes on judgment calls / air-gap gaps (flagged for controller adjudication):
- `ordinary_brackets` is a SINGLE (upper_bound, rate) tuple, NOT status-keyed.
  Transcribed the SINGLE-filer 2025 schedule as the unqualified default; if
  tenforty keys on a different status the controller must adjudicate.
- `salt_phaseout_threshold` is a single int in the schema, but the statute uses
  $500,000 for most filers and $250,000 for MFS. Attested $500,000 (the primary
  threshold); MFS $250,000 noted inline for the controller.
- `eic_income_ceiling` (dict keyed by children only): per the clarified schema,
  this is the LARGEST AGI at which ANY status can claim the EITC = the MFJ-column
  maximum by construction. Transcribed the MFJ column of the official EITC table.
- `qualifying_widow` (QSS) = MFJ for standard deduction, brackets, and QDCGT
  (sources say so explicitly); for QBI, official Form 8995 puts QSS under "all
  other returns" (single amount) — transcribed accordingly and flagged.
"""
import math

SOURCES: tuple[str, ...] = (
    "IRS news release 'IRS releases tax inflation adjustments for tax year "
    "2025' (IR-2024-273, "
    "irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2025)"
    ": TY2025 income tax rate brackets (Rev. Proc. 2024-40 amounts).",
    "IRS Topic no. 409, Capital Gains and Losses (irs.gov/taxtopics/tc409): "
    "TY2025 0%/15% maximum-capital-gains-rate taxable-income breakpoints "
    "(Rev. Proc. 2024-40).",
    "IRS 2025 Instructions for Form 8995 (irs.gov/instructions/i8995): TY2025 "
    "§199A QBI threshold $394,600 MFJ / $197,300 all other returns.",
    "IRS Earned Income Tax Credit tables page (irs.gov/credits-deductions/"
    "individuals/earned-income-tax-credit/earned-income-and-earned-income-tax-"
    "credit-eitc-tables): TY2025 maximum-AGI (completed-phaseout) ceilings.",
    "IRS 'New and enhanced deductions for individuals' "
    "(irs.gov/newsroom/new-and-enhanced-deductions-for-individuals): OBBBA "
    "TY2025 standard deduction $15,750 single/MFS, $31,500 MFJ/QSS, "
    "$23,625 HoH.",
    "IRS 2025 Instructions for Schedule A (Form 1040) "
    "(irs.gov/pub/irs-pdf/i1040sca.pdf) and IRS Topic no. 503 "
    "(irs.gov/taxtopics/tc503): OBBBA TY2025 SALT cap $40,000 ($20,000 MFS), "
    "phase-down when MAGI > $500,000 ($250,000 MFS) at 30% (0.30), floored at "
    "$10,000 ($5,000 MFS).",
    "IRS 2024 Instructions for Schedule A (Form 1040) "
    "(irs.gov/pub/irs-prior/i1040sca--2024.pdf): TY2024 SALT cap $10,000 "
    "($5,000 MFS) — for prior_year_salt_cap lookback.",
    "IRS Topic no. 560, Additional Medicare Tax (irs.gov/taxtopics/tc560): "
    "0.9% Additional Medicare Tax filing-status thresholds (statutory).",
    "IRS Topic no. 502, Medical and Dental Expenses (irs.gov/taxtopics/tc502): "
    "7.5%-of-AGI medical expense floor (§213(a), statutory).",
    "SSA OASDI contribution and benefit base 2025 = $176,100; human-verified "
    "by Juno via browser 2026-07-11 (ssa.gov blocks automated WebFetch/curl "
    "access) — for ss_wage_base.",
    "QSS QBI (§199A) threshold adjudicated by Juno against Rev. Proc. 2023-34 "
    "§3.27 verbatim, 2026-07-11: QSS falls under 'All Other Returns' "
    "($197,300), not the MFJ row — a Layer-1 attestation catch of a params bug.",
)

# No fields are deliberately not-applicable for 2025: OBBBA gives 2025 a real
# SALT phaseout (threshold, rate, floor all attested). ss_wage_base was a
# couldn't-source None; it is now human-verified by Juno and carries a value.
NOT_APPLICABLE: dict[str, str] = {}

ATTESTED: dict[str, object] = {
    "year": 2025,

    # OBBBA-amended TY2025 standard deduction (in effect for 2025 returns).
    # Source: IRS "New and enhanced deductions for individuals". QSS = MFJ.
    "standard_deduction": {
        "single": 15750,
        "married_jointly": 31500,
        "married_separately": 15750,
        "head_of_household": 23625,
        "qualifying_widow": 31500,  # QSS = MFJ standard deduction
    },

    # Rev. Proc. 2024-40 TY2025 Tax Rate Tables (via IR-2024-273). SCHEMA
    # STORES ONE SCHEDULE (not status-keyed) — transcribed SINGLE-filer 2025.
    # See module docstring note. (upper_bound, marginal_rate).
    "ordinary_brackets": (
        (11925.0, 0.10),
        (48475.0, 0.12),
        (103350.0, 0.22),
        (197300.0, 0.24),
        (250525.0, 0.32),
        (626350.0, 0.35),
        (math.inf, 0.37),
    ),

    # IRS Topic no. 409 / Rev. Proc. 2024-40 Maximum Capital Gains Rate, TY2025.
    # (0%-rate maximum taxable income, 15%-rate maximum taxable income).
    "qdcgt_breakpoints": {
        "single": (48350, 533400),
        "married_jointly": (96700, 600050),
        "married_separately": (48350, 300000),
        "head_of_household": (64750, 566700),
        "qualifying_widow": (96700, 600050),  # QSS = MFJ
    },

    # IRS Topic no. 560 — statutory 0.9% Additional Medicare Tax thresholds
    # (NOT inflation-adjusted): $250k MFJ, $125k MFS, $200k all others.
    "addl_medicare_threshold": {
        "single": 200000,
        "married_jointly": 250000,
        "married_separately": 125000,
        "head_of_household": 200000,
        "qualifying_widow": 200000,  # "all other" case
    },

    # SSA OASDI contribution & benefit base for 2025. ssa.gov blocked all
    # automated retrieval (WebFetch + browser-UA curl both 403 on cbb.html /
    # cbbdet.html / maxtax.html); human-verified by Juno via browser
    # 2026-07-11 — see the SOURCES entry.
    "ss_wage_base": 176_100,

    # §199A QBI threshold, TY2025 (Form 8995 2025 instructions): $394,600 MFJ,
    # $197,300 all other returns. QSS/HoH/MFS/single = "all other returns".
    "qbi_threshold": {
        "single": 197300,
        "married_jointly": 394600,
        "married_separately": 197300,
        "head_of_household": 197300,
        "qualifying_widow": 197300,  # QSS = "all other returns" per Form 8995
    },

    # OBBBA TY2025 SALT cap: $40,000 ($20,000 MFS). Source: 2025 Sch A instr.
    "salt_cap_starting": {
        "single": 40000,
        "married_jointly": 40000,
        "married_separately": 20000,
        "head_of_household": 40000,
        "qualifying_widow": 40000,
    },
    # OBBBA phase-down begins when MAGI exceeds $500,000 ($250,000 MFS).
    # Schema is a single int; attested the primary $500,000 threshold.
    # MFS threshold ($250,000) NOT representable here — flagged for controller.
    "salt_phaseout_threshold": 500000,
    # Phase-down rate = 30% of MAGI excess over the threshold (2025 Sch A
    # instructions worksheet: multiply excess by 0.30).
    "salt_phaseout_rate": 0.30,
    # SALT cap floor (IRC §164(b)(6)) = the amount the OBBBA cap phases down to
    # and cannot drop below: $10,000 ($5,000 MFS). Source: 2025 Sch A instr.
    "salt_cap_floor": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # IRS Topic no. 502 / §213(a): 7.5% of AGI. Unchanged for 2025.
    "medical_agi_floor_pct": 0.075,

    # prior_year_salt_cap: a 2025 return looks back to the 2024 SALT cap.
    # TY2024 cap = $10,000 ($5,000 MFS). Source: 2024 Instructions for Sch A.
    "prior_year_salt_cap": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # EIC income ceiling = LARGEST AGI at which ANY status can claim the EITC =
    # the MFJ-column maximum (per clarified schema). TY2025 MFJ column, official
    # IRS EITC tables (Rev. Proc. 2024-40 amounts).
    "eic_income_ceiling": {
        0: 26214,
        1: 57554,
        2: 64430,
        3: 68675,  # 3 or more qualifying children
    },
}
