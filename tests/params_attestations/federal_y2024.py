"""Air-gapped attestation of FEDERAL params, tax year 2024.

Independently transcribed from official IRS/SSA publications ONLY — see SOURCES.
This module exists to cross-check tenforty's own federal params; it was written
without reading any tenforty param value, test, tax-table CSV, or git history.

Notes on judgment calls / air-gap gaps (flagged for controller adjudication):
- `ordinary_brackets` in the schema is a SINGLE (upper_bound, rate) tuple, NOT
  status-keyed. Federal brackets differ by filing status, so a single stored
  schedule is ambiguous. Transcribed the SINGLE-filer 2024 schedule as the
  unqualified default. If tenforty keys this on a different status (e.g. MFJ),
  the controller must adjudicate — this is a keying question I cannot resolve
  without reading tenforty (forbidden).
- `eic_income_ceiling` (dict keyed by children only): per the clarified schema,
  this field is the LARGEST AGI at which ANY filing status can still claim the
  EITC = the MFJ-column maximum by construction. Transcribed the MFJ column of
  the official EITC completed-phaseout amounts.
- `qualifying_widow` (qualifying surviving spouse, QSS): sources explicitly give
  QSS = MFJ amounts for standard deduction, tax brackets, and QDCGT breakpoints.
  For QBI (§199A) the official Form 8995 text puts QSS under "all other returns"
  (single amount), NOT the MFJ amount — transcribed accordingly and flagged.
"""
import math

SOURCES: tuple[str, ...] = (
    "IRS Rev. Proc. 2023-34 (Internal Revenue Bulletin 2023-48, "
    "irs.gov/irb/2023-48_IRB): Tax Rate Tables, Maximum Capital Gains Rate, "
    "Qualified Business Income (§199A) threshold, Earned Income Credit, "
    "Standard Deduction — TY2024 inflation-adjusted amounts.",
    "IRS Topic no. 560, Additional Medicare Tax (irs.gov/taxtopics/tc560): "
    "0.9% Additional Medicare Tax filing-status thresholds (statutory, not "
    "inflation-adjusted).",
    "IRS Topic no. 502, Medical and Dental Expenses (irs.gov/taxtopics/tc502): "
    "7.5%-of-AGI medical expense floor (§213(a), statutory).",
    "IRS 2024 Instructions for Schedule A (Form 1040) "
    "(irs.gov/pub/irs-prior/i1040sca--2024.pdf): TY2024 SALT deduction cap "
    "$10,000 ($5,000 MFS).",
    "IRS 2023 Instructions for Schedule A (Form 1040) "
    "(irs.gov/pub/irs-prior/i1040sca--2023.pdf): TY2023 SALT deduction cap "
    "$10,000 ($5,000 MFS) — for prior_year_salt_cap lookback.",
    "IRC §164(b)(6): SALT deduction cap floor of $10,000 ($5,000 MFS), the "
    "flat cap for 2024 (Schedule A line 5e) — for salt_cap_floor.",
    "SSA OASDI contribution and benefit base 2024 = $168,600; human-verified "
    "by Juno via browser 2026-07-11 (ssa.gov blocks automated WebFetch/curl "
    "access) — for ss_wage_base.",
    "QSS QBI (§199A) threshold adjudicated by Juno against Rev. Proc. 2023-34 "
    "§3.27 verbatim, 2026-07-11: QSS falls under 'All Other Returns' "
    "($191,950), not the MFJ row — a Layer-1 attestation catch of a params bug.",
)

# Fields that are None because they are DELIBERATELY NOT APPLICABLE for this
# tax year (as opposed to None = "could not source"). Lets the gate distinguish
# the two. (ss_wage_base was a couldn't-source None; it is now human-verified
# by Juno and carries a real value.)
NOT_APPLICABLE: dict[str, str] = {
    "salt_phaseout_threshold": "No SALT phaseout under the 2024 flat cap (IRC §164(b)(6)); the phaseout regime begins with OBBBA in 2025.",
    "salt_phaseout_rate": "No phaseout rate under the 2024 flat cap — no income-based reduction exists to rate-limit.",
}

ATTESTED: dict[str, object] = {
    "year": 2024,

    # Rev. Proc. 2023-34, Standard Deduction section (§2.15). QSS = MFJ.
    "standard_deduction": {
        "single": 14600,
        "married_jointly": 29200,
        "married_separately": 14600,
        "head_of_household": 21900,
        "qualifying_widow": 29200,  # QSS = MFJ standard deduction
    },

    # Rev. Proc. 2023-34, Tax Rate Tables (§2.01). SCHEMA STORES ONE SCHEDULE
    # (not status-keyed) — transcribed the SINGLE-filer 2024 schedule.
    # See module docstring note. (upper_bound, marginal_rate).
    "ordinary_brackets": (
        (11600.0, 0.10),
        (47150.0, 0.12),
        (100525.0, 0.22),
        (191950.0, 0.24),
        (243725.0, 0.32),
        (609350.0, 0.35),
        (math.inf, 0.37),
    ),

    # Rev. Proc. 2023-34, Maximum Capital Gains Rate (§2.03).
    # (0%-rate maximum taxable income, 15%-rate maximum taxable income).
    "qdcgt_breakpoints": {
        "single": (47025, 518900),
        "married_jointly": (94050, 583750),
        "married_separately": (47025, 291850),
        "head_of_household": (63000, 551350),
        "qualifying_widow": (94050, 583750),  # QSS = MFJ
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

    # SSA OASDI contribution & benefit base for 2024. ssa.gov blocked all
    # automated retrieval (WebFetch + browser-UA curl both 403 on cbb.html /
    # cbbdet.html / maxtax.html); human-verified by Juno via browser
    # 2026-07-11 — see the SOURCES entry.
    "ss_wage_base": 168_600,

    # Rev. Proc. 2023-34, §199A QBI "threshold amount": $383,900 MFJ,
    # $191,950 all other returns. Per Form 8995 text, QSS/HoH/MFS/single all
    # fall under "all other returns" ($191,950); only MFJ gets $383,900.
    "qbi_threshold": {
        "single": 191950,
        "married_jointly": 383900,
        "married_separately": 191950,
        "head_of_household": 191950,
        "qualifying_widow": 191950,  # QSS = "all other returns" per Form 8995
    },

    # TY2024 SALT cap (TCJA): flat $10,000 ($5,000 MFS). No income-based
    # phaseout in 2024. Source: 2024 Instructions for Schedule A (line 5e).
    "salt_cap_starting": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    # 2024 had a FLAT SALT cap with no MAGI-based phase-down. Per the schema
    # comment, salt_phaseout_threshold = None means "flat cap" — positively
    # correct for 2024.
    "salt_phaseout_threshold": None,
    # No statutory phase-down rate exists for the 2024 flat-cap regime; the
    # official law does not publish a rate for this field as the schema defines
    # it. Air-gap rule: unattestable -> None with note (not a guessed 0.0).
    "salt_phaseout_rate": None,
    # SALT cap floor = the officially published cap amount (IRC §164(b)(6)).
    # For 2024 this simply IS the flat cap: $10,000 ($5,000 MFS).
    # Source: 2024 Instructions for Schedule A (line 5e).
    "salt_cap_floor": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # IRS Topic no. 502 / §213(a): 7.5% of AGI. Unchanged for 2024.
    "medical_agi_floor_pct": 0.075,

    # prior_year_salt_cap: a 2024 return looks back to the 2023 SALT cap.
    # TY2023 cap = $10,000 ($5,000 MFS). Source: 2023 Instructions for Sch A.
    "prior_year_salt_cap": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # EIC income ceiling = LARGEST AGI at which ANY status can claim the EITC =
    # the MFJ-column completed-phaseout maximum (per clarified schema). TY2024
    # MFJ column, Rev. Proc. 2023-34 Earned Income Credit section.
    "eic_income_ceiling": {
        0: 25511,
        1: 56004,
        2: 62688,
        3: 66819,  # 3 or more qualifying children
    },
}
