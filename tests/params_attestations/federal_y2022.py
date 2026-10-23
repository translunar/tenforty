"""Independent (Transcriber B) attestation of federal tax-year 2022 parameters.

Transcribed AIR-GAPPED from official IRS/SSA publications fetched directly by
this transcriber: IRS Rev. Proc. 2021-45 (2022 inflation adjustments), the 2022
Instructions for Schedule A (Form 1040), the 2022 Instructions for Form 8959,
and IRS Publication 15 (Circular E), 2022 revision. No other transcription,
attestation, params module, oracle, or secondary/summary source was consulted;
every dollar figure below was read verbatim from the official document text.

Each value carries an inline citation to the exact document and section/table.
"""

import datetime
import math

ATTESTED: dict[str, object] = {
    "year": 2022,  # Rev. Proc. 2021-45 §3 "2022 Adjusted Items" (taxable years beginning in 2022)
    "standard_deduction": {
        # Rev. Proc. 2021-45 §3.15(1) Standard Deduction table (§63(c)(2))
        "single": 12950,             # "Unmarried Individuals (other than Surviving Spouses and Heads of Households)"
        "married_filing_jointly": 25900,    # "Married Individuals Filing Joint Returns and Surviving Spouses"
        "married_filing_separately": 12950, # "Married Individuals Filing Separate Returns"
        "head_of_household": 19400,  # "Heads of Households"
        "qualifying_widow": 25900,   # QSS shares the MFJ / "Surviving Spouses" row per §3.15(1)
    },
    "nonitemizer_charitable_cap": None,  # Provision expired after 2021 (see NOT_APPLICABLE)
    # MFJ (§3.01 Table 1) and HoH (§3.01 Table 2) added 2026-10-15 by dual
    # transcription (A: worktree params fill; B: isolated scratch, pasted here
    # by team-lead; mechanical adjudication: full agreement, brackets 7/7 both
    # statuses). Both sides pinned identical editions:
    #   rp-21-45.pdf  sha256 405535647b6287103f5392258d4342cdb70535bf07ff05d89eebc71768083627
    #   i1040gi--2022.pdf  sha256 fcd5f84c414ca4d9553779bb558172554299807b3fe2649825aa2c06723de4c9
    # No internal source inconsistency (base-tax arithmetic checked by both
    # transcribers independently).
    "ordinary_brackets": {
        "single": (
            # Rev. Proc. 2021-45 §3.01 TABLE 3 - Section 1(j)(2)(C) - Unmarried Individuals
            # (other than Surviving Spouses and Heads of Households) — the single schedule
            (10275, 0.10),     # Not over $10,275
            (41775, 0.12),     # Over $10,275 but not over $41,775
            (89075, 0.22),     # Over $41,775 but not over $89,075
            (170050, 0.24),    # Over $89,075 but not over $170,050
            (215950, 0.32),    # Over $170,050 but not over $215,950
            (539900, 0.35),    # Over $215,950 but not over $539,900
            (math.inf, 0.37),  # Over $539,900
        ),
        "married_filing_jointly": (
            (20550, 0.1),
            (83550, 0.12),
            (178150, 0.22),
            (340100, 0.24),
            (431900, 0.32),
            (647850, 0.35),
            (math.inf, 0.37),
        ),
        "head_of_household": (
            (14650, 0.1),
            (55900, 0.12),
            (89050, 0.22),
            (170050, 0.24),
            (215950, 0.32),
            (539900, 0.35),
            (math.inf, 0.37),
        ),
    },
    "qdcgt_breakpoints": {
        # MFJ and HoH RE-VERIFIED 2026-10-15 by fresh dual transcription from
        # the pinned editions cited at ordinary_brackets (R-attest-reuse):
        # fresh B == committed params == this attestation on both statuses;
        # citation upgraded, values unchanged. (This year's §3.03 is prose,
        # not a table; it maps one-to-one onto the pair shape.)
        # Rev. Proc. 2021-45 §3.03 Maximum Capital Gains Rate (§1(h)):
        # (Maximum Zero Rate Amount, Maximum 15-percent Rate Amount)
        "single": (41675, 459750),            # "any other individual (other than an estate or trust)"
        "married_filing_jointly": (83350, 517200),   # "joint return or surviving spouse"
        "married_filing_separately": (41675, 258600),# "married individual filing a separate return"
        "head_of_household": (55800, 488500), # "individual who is the head of a household"
        "qualifying_widow": (83350, 517200),  # QSS shares the "surviving spouse" (joint) figures per §3.03
    },
    "capital_loss_limit": {
        # IRC §1211(b), STATUTORY and NOT inflation-indexed: the section has no
        # cost-of-living provision, has not been amended since Pub. L. 99-514
        # (1986), and does not appear in Rev. Proc. 2021-45 (the 2022
        # inflation-adjustment revenue procedure). Read verbatim off the face
        # of the 2022 Schedule D (Form 1040), Line 21: "the smaller of:
        # • The loss on line 16; or • ($3,000), or if married filing
        # separately, ($1,500)". 2022 Instr. Sch. D, "Capital Losses" (page 4)
        # agrees: "$3,000 ($1,500 if married filing separately)".
        "single": 3000,
        "married_filing_jointly": 3000,
        "married_filing_separately": 1500,  # only MFS differs, per §1211(b)(1)
        "head_of_household": 3000,
        "qualifying_widow": 3000,    # QSS is not MFS -> full $3,000
    },
    "addl_medicare_threshold": {
        # 2022 Instructions for Form 8959, "Threshold Amounts for Additional Medicare Tax"
        # (§3101(b)(2)/§1411; note: not indexed for inflation)
        "single": 200000,             # "Single ... $200,000"
        "married_filing_jointly": 250000,    # "Married filing jointly ... $250,000"
        "married_filing_separately": 125000, # "Married filing separately ... $125,000"
        "head_of_household": 200000,  # "Head of household ... $200,000"
        "qualifying_widow": 200000,   # "Qualifying surviving spouse ... $200,000"
    },
    "ss_wage_base": 147000,  # IRS Pub. 15 (Circular E) 2022, Social Security & Medicare Taxes: "wage base limit is $147,000"
    "qbi_threshold": {
        # Rev. Proc. 2021-45 §3.27 Qualified Business Income, Threshold amount (§199A(e)(2))
        "single": 170050,             # "All Other Returns ... $170,050"
        "married_filing_jointly": 340100,    # "Married Individuals Filing Joint Returns ... $340,100"
        "married_filing_separately": 170050, # "Married Individuals Filing Separate Returns ... $170,050"
        "head_of_household": 170050,  # "All Other Returns ... $170,050"
        "qualifying_widow": 170050,   # QSS takes the "All Other Returns" (single-side) value; §199A is joint-return-keyed
    },
    "salt_cap_starting": {
        # IRC §164(b)(6) flat cap, confirmed by 2022 Instructions for Schedule A (Form 1040),
        # Line 5: "generally limited to $10,000 ($5,000 if married filing separately)"
        "single": 10000,
        "married_filing_jointly": 10000,
        "married_filing_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "salt_phaseout_threshold": None,  # No SALT phaseout under the 2022 flat cap (see NOT_APPLICABLE)
    "salt_phaseout_rate": None,       # No SALT phaseout under the 2022 flat cap (see NOT_APPLICABLE)
    "salt_cap_floor": {
        # IRC §164(b)(6): the 2022 cap is a flat pre-OBBBA amount with no income phase-down,
        # so the floor equals the flat cap itself ($5,000 MFS). Confirmed by 2022 Sch. A instr., Line 5.
        "single": 10000,
        "married_filing_jointly": 10000,
        "married_filing_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "medical_agi_floor_pct": 0.075,  # 2022 Instructions for Schedule A (Form 1040), Line 1: "exceeds 7.5% of ... adjusted gross income" (§213(a), permanent 7.5%)
    "prior_year_salt_cap": {
        # 2021 (prior-year) SALT cap: same flat IRC §164(b)(6) structure, $10,000 ($5,000 MFS)
        "single": 10000,
        "married_filing_jointly": 10000,
        "married_filing_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "eic_income_ceiling": {
        # Rev. Proc. 2021-45 §3.06(1) EIC table, "Completed Phaseout Amount (Married Filing Jointly)" row
        # (MFJ column = maximum AGI at which any filing status can still claim the EITC)
        0: 22610,  # "None ... $22,610"
        1: 49622,  # "One ... $49,622"
        2: 55529,  # "Two ... $55,529"
        3: 59187,  # "Three or More ... $59,187"
    },

    # IRC §461(l) excess-business-loss threshold — 2022 Form 461, line 15:
    # "Enter $270,000 (or $540,000 if married filing jointly)". Supplied by
    # team-lead from an independent read (blind transcription agent),
    # NOT from the params author. Every status other than married filing
    # jointly takes the single amount.
    "excess_business_loss_threshold": {
        "single": 270000,
        "married_filing_jointly": 540000,
        "married_filing_separately": 270000,
        "head_of_household": 270000,
        "qualifying_widow": 270000,
    },
    # Attested 2026-10-14 (Transcriber B paste; dual transcription adjudicated
    # vs Transcriber A with full agreement, incl. team-lead third readings).
    # Amounts source 2022: Rev. Proc. 2021-45 — https://www.irs.gov/pub/irs-drop/rp-21-45.pdf — sha256 405535647b6287103f5392258d4342cdb70535bf07ff05d89eebc71768083627
    # Date source 2022: 2022 Instructions for Form 1040 (and 1040-SR) — https://www.irs.gov/pub/irs-prior/i1040gi--2022.pdf — sha256 fcd5f84c414ca4d9553779bb558172554299807b3fe2649825aa2c06723de4c9
    "additional_standard_deduction": {
        "single": 1750,
        "married_filing_jointly": 1400,
        "married_filing_separately": 1400,
        "head_of_household": 1750,
        "qualifying_widow": 1400,
    },
    "aged_born_before": datetime.date(1958, 1, 2),
}

NOT_APPLICABLE: dict[str, str] = {
    "salt_phaseout_threshold": (
        "No SALT phaseout exists for TY2022: IRC §164(b)(6) imposes a flat "
        "$10,000 ($5,000 MFS) cap. The income-based phaseout regime begins with "
        "OBBBA in 2025, so there is no threshold to attest."
    ),
    "salt_phaseout_rate": (
        "No SALT phaseout exists for TY2022: the flat IRC §164(b)(6) cap does not "
        "reduce with income, so there is no phaseout rate. The phaseout regime "
        "begins with OBBBA in 2025."
    ),
    "nonitemizer_charitable_cap": (
        "No non-itemizer charitable cash deduction exists for TY2022. The "
        "temporary CARES Act / TCDTRA provision (Form 1040 line 12b, up to $300 "
        "single / $600 MFJ) applied only to tax years 2020 and 2021 and expired "
        "thereafter. In the 2022 Instructions for Form 1040 there is no line 12b "
        "and no such deduction — Line 12 is simply 'Itemized Deductions or "
        "Standard Deduction.' Attested as None (provision not in effect)."
    ),
}

SOURCES: tuple[str, ...] = (
    "IRS Form 461 (2022), Limitation on Business Losses (irs.gov/pub/irs-prior/"
    "f461--2022.pdf), line 15 — for excess_business_loss_threshold.",
    "IRS Rev. Proc. 2021-45 (2022 inflation adjustments), https://www.irs.gov/pub/irs-drop/rp-21-45.pdf: "
    "§3.01 Table 3 (single ordinary rate schedule / ordinary_brackets); "
    "§3.03 Maximum Capital Gains Rate (qdcgt_breakpoints); "
    "§3.06(1) Earned Income Credit table, MFJ completed-phaseout row (eic_income_ceiling); "
    "§3.15(1) Standard Deduction (standard_deduction); "
    "§3.27 Qualified Business Income (qbi_threshold); §3 header (year).",
    "26 U.S.C. §1211(b), https://www.law.cornell.edu/uscode/text/26/1211: "
    "'... the lower of— (1) $3,000 ($1,500 in the case of a married individual "
    "filing a separate return), or (2) the excess of such losses over such "
    "gains.' STATUTORY, not inflation-indexed (no cost-of-living provision; "
    "unamended since Pub. L. 99-514, 1986) (capital_loss_limit).",
    "2022 Schedule D (Form 1040), https://www.irs.gov/pub/irs-prior/f1040sd--2022.pdf: "
    "Line 21 on the face of the form — '($3,000), or if married filing separately, "
    "($1,500)' (capital_loss_limit).",
    "2022 Instructions for Schedule D (Form 1040), https://www.irs.gov/pub/irs-prior/i1040sd--2022.pdf: "
    "'Capital Losses' (page 4) — 'You can deduct capital losses up to the amount of your "
    "capital gains plus $3,000 ($1,500 if married filing separately)' (capital_loss_limit).",
    "2022 Instructions for Form 8959, https://www.irs.gov/pub/irs-prior/i8959--2022.pdf: "
    "'Threshold Amounts for Additional Medicare Tax' (addl_medicare_threshold; §3101(b)(2)/§1411).",
    "IRS Publication 15 (Circular E), 2022 revision, https://www.irs.gov/pub/irs-prior/p15--2022.pdf: "
    "Social Security and Medicare Taxes section, 'wage base limit is $147,000' (ss_wage_base).",
    "2022 Instructions for Schedule A (Form 1040), https://www.irs.gov/pub/irs-prior/i1040sca--2022.pdf: "
    "Line 1 medical/dental 7.5%-of-AGI floor (medical_agi_floor_pct; §213(a)); "
    "Line 5 state-and-local-tax $10,000/$5,000 flat cap (salt_cap_starting, salt_cap_floor, prior_year_salt_cap; IRC §164(b)(6)).",
    "2022 Instructions for Form 1040 (and 1040-SR), https://www.irs.gov/pub/irs-prior/i1040gi--2022.pdf: "
    "Line 12 is 'Itemized Deductions or Standard Deduction' with no line 12b and no non-itemizer "
    "charitable cash deduction (nonitemizer_charitable_cap None — the 2020-2021-only provision expired).",
)

PENDING_TRANSCRIPTION: dict[str, str] = {
}


# Childless (zero qualifying children) earned income credit, TY2022.
# Independent free-form transcription; sources: 26 U.S.C. §32 (2022 ed.,
# govinfo), 2022 Instructions for Form 1040, IRS Pub. 596 (2022), Rev. Proc.
# 2021-45 §3.06. Filing-status note: the sources' "single" column covers
# Single / HOH / Qualifying surviving spouse; MFJ has its own column.
ATTESTED.update({
    "eic_credit_pct": 0.0765,  # 26 U.S.C. §32(b)(1) table, "No qualifying children", credit percentage "7.65"
    "eic_phaseout_pct": 0.0765,  # §32(b)(1) table, same row, phaseout percentage "7.65"
    "eic_earned_income_amount": 7320,  # Rev. Proc. 2021-45 §3.06(1), column "None", "earned income amount" (indexed; statute base is unindexed)
    # Rev. Proc. 2021-45 §3.06(1) "maximum amount of credit". NOTE (transcription
    # conflict note 3): §32(a)(1) formula, 7.65% x 7,320, gives 559.98; the
    # sources do not state the rounding step that yields the printed value.
    "eic_max_credit": 560,
    # Rev. Proc. 2021-45 §3.06(1), column "None", "threshold phaseout amount".
    # AMBIGUITY FLAG (transcription conflict note 2): 2022 Form 1040
    # Instructions, EIC Worksheet A line 5 uses a different trigger ("$9,200
    # ($15,300 if married filing jointly)"); the sources do not explain the
    # difference. Attested here is the Rev. Proc. value, the higher-precedence source.
    "eic_phaseout_threshold": {
        "single": 9160,
        "married_filing_jointly": 15290,  # includes the §32(b)(2)(B) joint-return increase, indexed
    },
    # Rev. Proc. 2021-45 §3.06(1), column "None", "completed phaseout amount"
    # (amount at or above which no credit is allowed); same figures as the
    # 1040 instructions Step 1 q.1 / Step 5 q.3 and Pub. 596 Rules 1 and 15.
    "eic_completed_phaseout": {
        "single": 16480,
        "married_filing_jointly": 22610,
    },
    "eic_investment_income_limit": 10300,  # Rev. Proc. 2021-45 §3.06(2); Pub. 596 Rule 6 "$10,300 or less"; credit denied above this (statute base $10,000, §32(i)(1))
    # Lower bound of the first EIC Table row (no-child column) in the 2022 Form
    # 1040 instructions. The transcription states "the lowest table row starts
    # at $1" (and the first row is 1 to 50) but gives no dedicated minimum.
    "eic_min_earned_income": 1,
    "eic_min_age": 25,  # §32(c)(1)(A)(ii)(II) "has attained age 25"; Pub. 596 Rule 11; 2022 1040 instr. Step 4 q.2
    "eic_max_age": 65,  # §32(c)(1)(A)(ii)(II) "not attained age 65 before the close of the taxable year" (must NOT have attained)
})
SOURCES += (
    "26 U.S.C. §32 (2022 Edition), govinfo.gov USCODE-2022-title26 sec32: "
    "§32(b)(1) percentages table, §32(c)(1)(A)(ii)(II) age test (eic_credit_pct, "
    "eic_phaseout_pct, eic_min_age, eic_max_age); §32(i)(1) investment income "
    "base. (uscode.house.gov returned a server error; Cornell LII summary not used.)",
    "2022 Instructions for Form 1040, irs.gov/pub/irs-pdf (\"2022 Instruction 1040\"): "
    "EIC Steps 1, 2, 4, 5, Worksheet A, 2022 EIC Table (eic_min_earned_income, "
    "completed phaseout, investment income, age cross-checks).",
    "IRS Publication 596 (2022 edition, irs.gov/pub/irs-prior/p596--2022.pdf): Rules 1, 6, 11, 15 "
    "(cross-checks). The irs-pdf/p596.pdf URL served a later-year edition and was discarded.",
    "IRS Rev. Proc. 2021-45 §3.06(1)-(2), https://www.irs.gov/pub/irs-drop/rp-21-45.pdf: "
    "EIC table column \"None\" (eic_earned_income_amount, eic_max_credit, "
    "eic_phaseout_threshold, eic_completed_phaseout) and investment income limit "
    "(eic_investment_income_limit).",
)
