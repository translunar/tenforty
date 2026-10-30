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
- `ordinary_brackets` is status-keyed (schema re-keyed 2026-10 in the
  filing-statuses round; the original transcription was the SINGLE schedule as
  a bare tuple, values unchanged under the "single" key). MFJ and HoH columns
  added 2026-10-14 by independent Transcriber B (Rev. Proc. 2024-40 §2.01
  Tables 1 and 2); adjudicated against Transcriber A with full agreement.
- `salt_phaseout_threshold` is a single int in the schema, but the statute uses
  $500,000 for most filers and $250,000 for MFS. Attested $500,000 (the primary
  threshold); MFS $250,000 noted inline for the controller.
- `eic_income_ceiling` (dict keyed by children only): per the clarified schema,
  this is the LARGEST AGI at which ANY status can claim the EITC = the MFJ-column
  maximum by construction. Transcribed the MFJ column of the official EITC table.
- `qualifying_widow` (QSS) = MFJ for standard deduction, brackets, and QDCGT
  (sources say so explicitly); for QBI, official Form 8995 puts QSS under "all
  other returns" (single amount) — transcribed accordingly and flagged.
- EIC zero-qualifying-children fields (`eic_credit_pct`, `eic_phaseout_pct`,
  `eic_earned_income_amount`, `eic_max_credit`, `eic_phaseout_threshold`,
  `eic_completed_phaseout`, `eic_investment_income_limit`,
  `eic_min_earned_income`, `eic_min_age`, `eic_max_age`): added 2026-10-21
  from an independent free-form transcription (sources fetched 2026-10-21:
  IRC §32 GPO 2024 ed. + LII cross-check, Pub. L. 119-21, Rev. Proc. 2024-40,
  2025 Form 1040 instructions, Pub. 596 (2025)). Conflicts reported by the
  transcriber, NOT resolved here (flagged inline for controller adjudication):
    * `eic_max_credit`: statute arithmetic (7.65% x $8,490) = $649.485; IRS
      gives $649 and §32 has no credit-rounding rule.
    * `eic_completed_phaseout`: statute arithmetic gives $19,110 / $26,220;
      every IRS source gives $19,104 / $26,214 (phasing out the
      already-rounded $649). Attested the IRS figures.
    * `eic_min_age` / `eic_max_age`: statute uses one "attained age" concept;
      Pub. 596 reaches 25 the day before the birthday but 65 ON the birthday
      (born after 1960-12-31 and before 2001-01-02). No statutory basis given.
    * Statute currency: OLRC current §32 could not be fetched, so no other
      2025 amendment to §32 could be ruled out (none found in Pub. L. 119-21).
      ADJUDICATED 2026-10-22 (R-T2): accepted as a standing note; Pub. L. 119-21 checked and the 2025 Pub. 596 What's New silent is adequate evidence for 2025.
"""
import datetime
import math

SOURCES: tuple[str, ...] = (
    "IRS Form 461 (2025), Limitation on Business Losses (irs.gov/pub/irs-prior/"
    "f461--2025.pdf), line 15 — for excess_business_loss_threshold.",
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
    "26 U.S.C. §1211(b) (law.cornell.edu/uscode/text/26/1211): capital-loss "
    "limitation — '$3,000 ($1,500 in the case of a married individual filing "
    "a separate return)'. Statutory, NOT inflation-indexed (no cost-of-living "
    "provision; unamended since Pub. L. 99-514, 1986; absent from Rev. Proc. "
    "2024-40; untouched by OBBBA).",
    "IRS 2025 Schedule D (Form 1040) (irs.gov/pub/irs-pdf/f1040sd.pdf), Line "
    "21 on the face of the form: 'If line 16 is a loss, enter here and on Form "
    "1040, 1040-SR, or 1040-NR, line 7a, the smaller of: • The loss on line "
    "16; or • ($3,000), or if married filing separately, ($1,500)'; and IRS "
    "2025 Instructions for Schedule D (Form 1040) (irs.gov/pub/irs-pdf/"
    "i1040sd.pdf), 'Capital Losses' (page 3) — for capital_loss_limit.",
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
    "IRS 2025 Instructions for Form 1040 (and 1040-SR) "
    "(irs.gov/pub/irs-pdf/i1040gi.pdf): Line 12 is 'Standard deduction or "
    "itemized deductions' with NO non-itemizer charitable cash deduction "
    "line — for nonitemizer_charitable_cap = None. (OBBBA's new permanent "
    "IRC §170(p) non-itemizer charitable deduction takes effect for tax "
    "years beginning after 2025, i.e. TY2026, not TY2025.)",
    "26 U.S.C. §32, United States Code 2024 Edition (GPO/govinfo, "
    "govinfo.gov/content/pkg/USCODE-2024-title26/html/USCODE-2024-title26-"
    "subtitleA-chap1-subchapA-partIV-subpartC-sec32.htm), fetched 2026-10-21; "
    "cross-checked against law.cornell.edu/uscode/text/26/32 (LII; last "
    "amendment Pub. L. 117-2) — §32(b)(1) 7.65% credit/phaseout percentage "
    "(no qualifying children), §32(b)(2), §32(c)(1)(A)(ii)(II) age 25-65, "
    "§32(i), §32(j) — for the eic_* zero-children fields. §32(n) is "
    "2021-only and does not apply to 2025.",
    "Public Law 119-21 (H.R. 1, July 4, 2025) enrolled text "
    "(govinfo.gov/content/pkg/PLAW-119publ21/pdf/PLAW-119publ21.pdf): "
    "searched, contains no amendment to IRC §32. OLRC prelim §32 "
    "(uscode.house.gov) could NOT be fetched ('Page Not Found'), so no other "
    "2025 amendment to §32 could be independently ruled out.",
    "Rev. Proc. 2024-40 (irs.gov/pub/irs-drop/rp-24-40.pdf) §2.06(1) table, "
    "column 'None' (printed p. 10 / PDF p. 9): TY2025 EIC earned income "
    "amount, maximum credit, threshold and completed phaseout amounts; "
    "§2.06(2): excessive investment income limit — for the eic_* fields.",
    "IRS 2025 Instructions for Form 1040 (and 1040-SR) "
    "(irs.gov/pub/irs-pdf/i1040gi.pdf), line 27a Steps 1-5 (pp. 40-42), EIC "
    "Worksheets A/B (pp. 46-48), EIC Table (pp. 49-60) — cross-check of the "
    "eic_* zero-children fields.",
    "IRS Publication 596 (2025), Earned Income Credit "
    "(irs.gov/pub/irs-pdf/p596.pdf): Rules 1, 6, 11, 15, EIC Eligibility "
    "Checklist (p. 24), EIC Table (pp. 29-40) — cross-check of the eic_* "
    "zero-children fields.",
)

# The only deliberately not-applicable field for 2025 is
# nonitemizer_charitable_cap: the temporary 2020-2021 line-12b deduction had
# expired and OBBBA's replacement (§170(p)) does not begin until TY2026, so
# no such cap exists for 2025. OBBBA gives 2025 a real SALT phaseout
# (threshold, rate, floor all attested); ss_wage_base is human-verified.
NOT_APPLICABLE: dict[str, str] = {
    "nonitemizer_charitable_cap": (
        "No non-itemizer charitable cash deduction exists for TY2025. The "
        "temporary CARES/TCDTRA provision (Form 1040 line 12b, up to $300 "
        "single / $600 MFJ) applied only to tax years 2020-2021 and expired. "
        "OBBBA created a new permanent above-the-line charitable deduction for "
        "non-itemizers (IRC §170(p)), but it is effective for taxable years "
        "beginning after December 31, 2025 (TY2026), NOT TY2025. The 2025 "
        "Instructions for Form 1040 show Line 12 as 'Standard deduction or "
        "itemized deductions' with no such cap. Attested None."
    ),
}

ATTESTED: dict[str, object] = {
    "year": 2025,

    # OBBBA-amended TY2025 standard deduction (in effect for 2025 returns).
    # Source: IRS "New and enhanced deductions for individuals". QSS = MFJ.
    "standard_deduction": {
        "single": 15750,
        "married_filing_jointly": 31500,
        "married_filing_separately": 15750,
        "head_of_household": 23625,
        "qualifying_widow": 31500,  # QSS = MFJ standard deduction
    },

    # Non-itemizer charitable cash-contribution deduction: NOT APPLICABLE for
    # TY2025 (see NOT_APPLICABLE). The 2020-2021 line-12b provision expired and
    # OBBBA's replacement (IRC §170(p)) does not begin until TY2026.
    "nonitemizer_charitable_cap": None,

    # Rev. Proc. 2024-40 TY2025 Tax Rate Tables (via IR-2024-273).
    # Status-keyed. Single column: original SINGLE-filer 2025 transcription.
    # See module docstring note. (upper_bound, marginal_rate).
    # MFJ/HoH columns: Transcriber B, 2026-10-14 —
    #   Rev. Proc. 2024-40 §2.01 Table 1 (MFJ) / Table 2 (HoH),
    #   https://www.irs.gov/pub/irs-drop/rp-24-40.pdf
    #   sha256 4de9db6b6662b5c305a59100a027051628823b42fd5817ea4e383ad4c302af1f
    #   Cross-check: 2025 Instructions for Form 1040, i1040gi.pdf
    #   sha256 482e9c487c608f1bbeaceef35bc3c0933e8b35443cfff447e4279d590468364a
    "ordinary_brackets": {
        "single": (
            (11925.0, 0.10),
            (48475.0, 0.12),
            (103350.0, 0.22),
            (197300.0, 0.24),
            (250525.0, 0.32),
            (626350.0, 0.35),
            (math.inf, 0.37),
        ),
        "married_filing_jointly": (
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (math.inf, 0.37),
        ),
        "head_of_household": (
            (17000, 0.10),
            (64850, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (math.inf, 0.37),
        ),
    },

    # IRS Topic no. 409 / Rev. Proc. 2024-40 §2.03 Maximum Capital Gains Rate,
    # TY2025 (rp-24-40.pdf, sha256 4de9db6b…c302af1f).
    # (0%-rate maximum taxable income, 15%-rate maximum taxable income).
    # R-attest-reuse closure 2026-10-14: MFJ/HoH re-verified by independent
    # Transcriber B from the Rev. Proc. itself; full agreement with the
    # existing entries, which stand unchanged.
    "qdcgt_breakpoints": {
        "single": (48350, 533400),
        "married_filing_jointly": (96700, 600050),
        "married_filing_separately": (48350, 300000),
        "head_of_household": (64750, 566700),
        "qualifying_widow": (96700, 600050),  # QSS = MFJ
    },

    # IRC §1211(b) — STATUTORY, NOT inflation-indexed. No cost-of-living
    # provision appears in §1211; the section has not been amended since
    # Pub. L. 99-514 (1986) and OBBBA did not touch it; §1211 appears nowhere
    # in Rev. Proc. 2024-40 (the TY2025 inflation-adjustment revenue
    # procedure). Statute: losses allowed to the extent of gains "plus (if
    # such losses exceed such gains) the lower of— (1) $3,000 ($1,500 in the
    # case of a married individual filing a separate return), or (2) the
    # excess of such losses over such gains." Confirmed on the face of the
    # 2025 Schedule D (Form 1040), Line 21 — note the 2025 form carries this
    # to Form 1040 line 7a (renumbered from line 7 in 2021-2024). MFS is the
    # only halved status.
    "capital_loss_limit": {
        "single": 3000,
        "married_filing_jointly": 3000,
        "married_filing_separately": 1500,
        "head_of_household": 3000,
        "qualifying_widow": 3000,  # QSS is not MFS -> full $3,000
    },

    # IRS Topic no. 560 — statutory 0.9% Additional Medicare Tax thresholds
    # (NOT inflation-adjusted): $250k MFJ, $125k MFS, $200k all others.
    # Citation UPGRADED 2026-10-14 (R-attest-reuse): fresh dual transcription
    # from IRC §3101(b)(2), uscode.house.gov release point PL 119-120
    # (xml_usc26@119-120.zip, zip sha256 84af19d59b5b6ee347c14da510d4a97f
    # 6d1d4187e138481352aed0be139b796d; source credits show (b)(2) in force
    # unchanged for 2025) — A/B adjudicated with full agreement, and both
    # agree with this pre-existing Topic-560 attestation.
    "addl_medicare_threshold": {
        "single": 200000,
        "married_filing_jointly": 250000,
        "married_filing_separately": 125000,
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
        "married_filing_jointly": 394600,
        "married_filing_separately": 197300,
        "head_of_household": 197300,
        "qualifying_widow": 197300,  # QSS = "all other returns" per Form 8995
    },

    # OBBBA TY2025 SALT cap: $40,000 ($20,000 MFS). Source: 2025 Sch A instr.
    "salt_cap_starting": {
        "single": 40000,
        "married_filing_jointly": 40000,
        "married_filing_separately": 20000,
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
        "married_filing_jointly": 10000,
        "married_filing_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # IRS Topic no. 502 / §213(a): 7.5% of AGI. Unchanged for 2025.
    "medical_agi_floor_pct": 0.075,

    # prior_year_salt_cap: a 2025 return looks back to the 2024 SALT cap.
    # TY2024 cap = $10,000 ($5,000 MFS). Source: 2024 Instructions for Sch A.
    "prior_year_salt_cap": {
        "single": 10000,
        "married_filing_jointly": 10000,
        "married_filing_separately": 5000,
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

    # ---- EIC, ZERO qualifying children (single / MFJ only). Independent
    # transcription 2026-10-21; see module docstring notes and SOURCES. ----
    # IRC §32(b)(1) table, row "No qualifying children": credit percentage
    # 7.65 and phaseout percentage 7.65. Same for both statuses. NOT stated in
    # Rev. Proc. 2024-40 / Form 1040 instr. / Pub. 596 (they give only the
    # resulting dollar amounts). The 15.3% of §32(n)(3) was 2021-only.
    "eic_credit_pct": 0.0765,
    "eic_phaseout_pct": 0.0765,
    # Rev. Proc. 2024-40 §2.06(1), column "None", row "Earned Income Amount"
    # (statutory base $4,220, §32(b)(2)(A), indexed from 1995, rounded to
    # nearest $10 per §32(j)(2)(A)). Same for both statuses. Corroborated by
    # Pub. 596 (2025) ch. 4 "Nontaxable combat pay", p. 20.
    "eic_earned_income_amount": 8490,
    # Rev. Proc. 2024-40 §2.06(1), column "None", row "Maximum Amount of
    # Credit"; EIC Table "0" columns show 649 for both Single and MFJ.
    # CONFLICT (reported, not resolved): §32(a) arithmetic 7.65% x $8,490 =
    # $649.485; §32 contains no rounding rule for the credit. The table also
    # shows $649 in the 8,450-8,500 bracket, where the transcriber's
    # midpoint-rule reconstruction gives $648 (inference, not a source).
    # ADJUDICATED 2026-10-22 (team-lead ruling R-T2): The IRS-published figures
    # govern: they are what Rev. Proc. 2024-40 and the 2025 Form 1040
    # instructions bind filers to, both independent readings attested them, and
    # production reads the published EIC Table. The statute-arithmetic delta
    # stays documented in the flag above; this resolves it.
    "eic_max_credit": 649,
    # Rev. Proc. 2024-40 §2.06(1), column "None", rows "Threshold Phaseout
    # Amount (All other filing statuses)" / "(Married Filing Jointly)"; MFJ
    # includes the inflation-adjusted §32(b)(2)(B) joint-return increase
    # (statutory $5,000, 2008 base). Corroborated by Form 1040 instr. EIC
    # Worksheet A line 5 (p. 46) / Worksheet B line 10 (p. 48). Statutory
    # base phaseout amount $5,280 (§32(b)(2)(A)).
    "eic_phaseout_threshold": {
        "single": 10620,
        "married_filing_jointly": 17730,
    },
    # Rev. Proc. 2024-40 §2.06(1), column "None", rows "Completed Phaseout
    # Amount" — AGI (or, if greater, earned income) at or above which no
    # credit is allowed. Also the AGI limit and the earned-income limit
    # ("must be less than"): Form 1040 instr. line 27a Step 1 Q1 (p. 40) and
    # Step 5 Q3 (p. 42); Pub. 596 Rule 1 (p. 4), Rule 15 (p. 19).
    # CONFLICT (reported, not resolved): literal §32(a)(2) arithmetic reaches
    # zero at $19,110 (single) / $26,220 (MFJ), $6 higher; the IRS figures
    # equal threshold + $649/0.0765 rounded, i.e. they phase out the already
    # rounded $649 rather than $649.485. No source explains this. Attested the
    # IRS-published figures.
    # ADJUDICATED 2026-10-22 (team-lead ruling R-T2): The IRS-published figures
    # govern: they are what Rev. Proc. 2024-40 and the 2025 Form 1040
    # instructions bind filers to, both independent readings attested them, and
    # production reads the published EIC Table. The statute-arithmetic delta
    # stays documented in the flag above; this resolves it.
    "eic_completed_phaseout": {
        "single": 19104,
        "married_filing_jointly": 26214,
    },
    # Rev. Proc. 2024-40 §2.06(2): credit not allowed if aggregate investment
    # income EXCEEDS this amount (statutory base $10,000, §32(i)(1); rounded
    # to next lowest $50 per §32(j)(2)(B)). Same for both statuses. Form 1040
    # instr. Step 2 Q2 ("more than"), Pub. 596 Rule 6 ("or less") — same test.
    "eic_investment_income_limit": 11950,
    # Pub. 596 (2025) EIC Eligibility Checklist Q6 (p. 24): total earned
    # income must be "at least $1"; EIC Table's first row "At least 1";
    # Form 1040 instr. Worksheet B line 4b: zero or less -> no credit. IRS
    # publications only, no statutory citation given. Same for both statuses.
    "eic_min_earned_income": 1,
    # IRC §32(c)(1)(A)(ii)(II): "has attained age 25 but not attained age 65
    # before the close of the taxable year"; on MFJ EITHER spouse may meet the
    # test (statute; Pub. 596 Rule 11, p. 17; Form 1040 instr. Step 4 Q2).
    # Same for both statuses (min age attained; max age NOT attained).
    # CONFLICT (reported, not resolved): IRS birth-date range "born after
    # December 31, 1960, and before January 2, 2001" applies two conventions —
    # Pub. 596 p. 17: age 25 reached the day before the 25th birthday, age 65
    # reached ON the 65th birthday. The statute applies a single "attained"
    # concept; no fetched source gives a statutory basis for the asymmetry.
    # (The 2021-only §32(n) ages 19/24/18 and no-maximum rule do not apply.)
    # ADJUDICATED 2026-10-22 (team-lead ruling R-T2): Params stay as attested.
    # The eligibility code implements the instructions' birth-date range
    # verbatim (born after December 31, 1960 and before January 2, 2001 for
    # 2025), not an integer age comparison; the day-before-birthday convention
    # only matters at the Dec-31/Jan-1 boundary and the IRS range is the
    # operational rule. The statute ambiguity noted above is carried into the
    # eligibility code.
    "eic_min_age": 25,
    "eic_max_age": 65,

    # IRC §461(l) excess-business-loss threshold — 2025 Form 461, line 15:
    # "Enter $313,000 (or $626,000 if married filing jointly)". Supplied by
    # team-lead from an independent read (blind transcription agent),
    # NOT from the params author. Every status other than married filing
    # jointly takes the single amount.
    "excess_business_loss_threshold": {
        "single": 313000,
        "married_filing_jointly": 626000,
        "married_filing_separately": 313000,
        "head_of_household": 313000,
        "qualifying_widow": 313000,
    },
    # Attested 2026-10-14 (Transcriber B paste; dual transcription adjudicated
    # vs Transcriber A with full agreement, incl. team-lead third readings).
    # Amounts source 2025: Rev. Proc. 2024-40 — https://www.irs.gov/pub/irs-drop/rp-24-40.pdf — sha256 4de9db6b6662b5c305a59100a027051628823b42fd5817ea4e383ad4c302af1f
    # Date source 2025: 2025 Instructions for Form 1040 (and 1040-SR) — https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf — sha256 482e9c487c608f1bbeaceef35bc3c0933e8b35443cfff447e4279d590468364a
    "additional_standard_deduction": {
        "single": 2000,
        "married_filing_jointly": 1600,
        "married_filing_separately": 1600,
        "head_of_household": 2000,
        "qualifying_widow": 1600,
    },
    "aged_born_before": datetime.date(1961, 1, 2),
}

PENDING_TRANSCRIPTION: dict[str, str] = {
}
