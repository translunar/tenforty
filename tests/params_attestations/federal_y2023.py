"""TY2023 federal tax-parameter ATTESTATION (Transcriber B, air-gapped).

Independently transcribed from official IRS/SSA publications, without reading
tenforty/params/federal/y2023.py (or any params/*/y*.py) or anything under
tests/. See tenforty/params/federal/__init__.py for the FederalParams schema
this mirrors field-for-field. Every value below carries an inline citation to
the specific document + section it was read from.

Primary source for inflation-adjusted amounts: IRS Rev. Proc. 2022-38 (the
annual inflation-adjustment revenue procedure for tax year 2023), fetched from
https://www.irs.gov/pub/irs-drop/rp-22-38.pdf and read with pdftotext (the
WebFetch HTML extractor cannot parse this PDF's compressed streams).

QSS ("qualifying_widow" in FilingStatus) mapping was read per each table's row
labels, not assumed equal to MFJ:
  - Standard deduction (Rev. Proc. 2022-38 §3.15): "Married Individuals Filing
    Joint Returns AND Surviving Spouses" is a single combined row -> QSS takes
    the MFJ value ($27,700).
  - Capital gains breakpoints (§3.03): "Married Individuals Filing Joint
    Returns and Surviving Spouse" is a single combined row -> QSS takes the
    MFJ value ((89250, 553850)).
  - QBI threshold (§3.27): rows are "Married Individuals Filing Joint
    Returns", "Married Individuals Filing Separate Returns", and "All Other
    Returns" -> QSS falls in "All Other Returns" ($182,100), NOT the MFJ
    value ($364,200).
  - Additional Medicare Tax threshold (statutory, IRC §3101(b)(2), confirmed
    against IRS's Additional Medicare Tax FAQ page): QSS is listed under
    "Qualifying widow(er) with dependent child" at $200,000, grouped with
    single/HoH, NOT the MFJ $250,000 value.

ssa.gov was unreachable from this environment for every path tried (root
domain, /oact/cola/cbb.html, /news/press/factsheets/colafacts2023.pdf,
robots.txt) -- all returned HTTP 403 "Access Denied" (Akamai edge block) via
both curl and WebFetch, with multiple user agents and HTTP/1.1 fallback.
ss_wage_base is instead sourced from an irs.gov document (2023 IRS Publication
15) that states the same statutory figure, satisfying the "official sources
only: irs.gov, ssa.gov" rule via the irs.gov leg.
"""
import math

# Fields that are None because they are DELIBERATELY NOT APPLICABLE for this
# tax year (as opposed to None = "could not source"). Lets the gate distinguish
# the two. TY2023 predates OBBBA, so the SALT deduction is a flat statutory cap
# (IRC §164(b)(6)) with no income-based phaseout — the phaseout regime begins
# in 2025. salt_phaseout_rate is a real 0.0 value (no reduction), not None, so
# it needs no not-applicable declaration.
NOT_APPLICABLE: dict[str, str] = {
    "salt_phaseout_threshold": "No SALT phaseout under the 2023 flat cap (IRC §164(b)(6)); the phaseout regime begins with OBBBA in 2025.",
    "nonitemizer_charitable_cap": (
        "No non-itemizer charitable cash deduction exists for TY2023. The "
        "temporary above-the-standard-deduction provision (Form 1040 line 12b, "
        "up to $300 single / $600 MFJ) applied only to 2020-2021 and expired. "
        "The 2023 Instructions for Form 1040 have no line 12b — Line 12 is "
        "'Itemized Deductions or Standard Deduction'. Attested None."
    ),
}

ATTESTED: dict[str, object] = {
    "year": 2023,

    # IRS Rev. Proc. 2022-38 §3.15 "Standard Deduction", table (1) "In
    # general". Rows: "Married Individuals Filing Joint Returns and Surviving
    # Spouses" $27,700; "Heads of Households" $20,800; "Unmarried Individuals
    # (other than Surviving Spouses and Heads of Households)" $13,850;
    # "Married Individuals Filing Separate Returns" $13,850. QSS takes the
    # combined MFJ/surviving-spouse row value ($27,700) per the row label.
    "standard_deduction": {
        "single": 13850,
        "married_jointly": 27700,
        "married_separately": 13850,
        "head_of_household": 20800,
        "qualifying_widow": 27700,
    },

    # Non-itemizer charitable cash-contribution deduction: NOT APPLICABLE for
    # TY2023 (see NOT_APPLICABLE). The 2020-2021-only line 12b provision expired.
    "nonitemizer_charitable_cap": None,

    # IRS Rev. Proc. 2022-38 §3.01, TABLE 3 - Section 1(j)(2)(C), "Unmarried
    # Individuals (other than Surviving Spouses and Heads of Households)"
    # (i.e. the SINGLE-filer schedule, as instructed). Upper bounds and
    # marginal rates read directly off the "If Taxable Income Is / The Tax
    # Is" table:
    #   not over 11,000            -> 10%
    #   11,000  - 44,725           -> 12%
    #   44,725  - 95,375           -> 22%
    #   95,375  - 182,100          -> 24%
    #   182,100 - 231,250          -> 32%
    #   231,250 - 578,125          -> 35%
    #   over 578,125               -> 37%
    "ordinary_brackets": (
        (11000, 0.10),
        (44725, 0.12),
        (95375, 0.22),
        (182100, 0.24),
        (231250, 0.32),
        (578125, 0.35),
        (math.inf, 0.37),
    ),

    # IRS Rev. Proc. 2022-38 §3.03 "Maximum Capital Gains Rate", table of
    # "Maximum Zero Rate Amount" / "Maximum 15% Rate Amount" by filing status:
    #   Married Filing Joint Returns and Surviving Spouse: 89,250 / 553,850
    #   Married Filing Separate Returns:                   44,625 / 276,900
    #   Heads of Household:                                59,750 / 523,050
    #   All Other Individuals (single):                    44,625 / 492,300
    # QSS takes the combined MFJ/surviving-spouse row value per the row
    # label (same as standard deduction's row grouping).
    "qdcgt_breakpoints": {
        "single": (44625, 492300),
        "married_jointly": (89250, 553850),
        "married_separately": (44625, 276900),
        "head_of_household": (59750, 523050),
        "qualifying_widow": (89250, 553850),
    },

    # STATUTORY, not inflation-adjusted: IRC §1211(b) (limitation on capital
    # losses of non-corporate taxpayers). The section contains no cost-of-
    # living/indexing provision and has not been amended since Pub. L. 99-514
    # (1986); it appears nowhere in Rev. Proc. 2022-38, the TY2023 inflation-
    # adjustment revenue procedure. §1211(b) allows losses "to the extent of
    # the gains ..., plus (if such losses exceed such gains) the lower of—
    # (1) $3,000 ($1,500 in the case of a married individual filing a separate
    # return), or (2) the excess of such losses over such gains."
    # Confirmed on the face of the 2023 Schedule D (Form 1040), Line 21:
    # "the smaller of: • The loss on line 16; or • ($3,000), or if married
    # filing separately, ($1,500)"; and in the 2023 Instructions for Schedule D,
    # "Capital Losses" (page 4). MFS is the ONLY status the statute halves;
    # single/HoH/MFJ/QSS all take the full $3,000.
    "capital_loss_limit": {
        "single": 3000,
        "married_jointly": 3000,
        "married_separately": 1500,
        "head_of_household": 3000,
        "qualifying_widow": 3000,
    },

    # STATUTORY, not inflation-adjusted: IRC §3101(b)(2) (Additional Medicare
    # Tax). Confirmed against IRS's "Questions and Answers for the Additional
    # Medicare Tax" FAQ page (irs.gov/businesses/small-businesses-self-employed/
    # questions-and-answers-for-the-additional-medicare-tax), "Basic FAQs"
    # section, table answering "When are individuals liable for Additional
    # Medicare Tax?":
    #   Married filing jointly: $250,000
    #   Married filing separately: $125,000
    #   Single: $200,000
    #   Head of household (with qualifying person): $200,000
    #   Qualifying widow(er) with dependent child: $200,000
    # QSS is grouped with single/HoH at $200,000, NOT the MFJ $250,000 value.
    "addl_medicare_threshold": {
        "single": 200000,
        "married_jointly": 250000,
        "married_separately": 125000,
        "head_of_household": 200000,
        "qualifying_widow": 200000,
    },

    # ssa.gov was unreachable (HTTP 403 "Access Denied" from every path
    # tried: www.ssa.gov/, /oact/cola/cbb.html, /news/press/factsheets/
    # colafacts2023.pdf, /robots.txt -- via curl with multiple user agents
    # and HTTP/1.1, and via WebFetch). Sourced instead from IRS Publication
    # 15 (Circular E), Employer's Tax Guide, 2023 revision (rev. Dec 13,
    # 2022; irs.gov/pub/irs-prior/p15--2023.pdf), "Social Security and
    # Medicare Taxes" section: "The social security wage base limit is
    # $160,200." This is the same SSA-set OASDI figure, cited via the
    # irs.gov leg of the "irs.gov, ssa.gov" official-sources rule.
    "ss_wage_base": 160200,

    # IRS Rev. Proc. 2022-38 §3.27 "Qualified Business Income" (§199A),
    # "Threshold amount" column:
    #   Married Individuals Filing Joint Returns: $364,200
    #   Married Individuals Filing Separate Returns: $182,100
    #   All Other Returns: $182,100
    # Per the QSS gloss, QBI groups QSS under "All Other Returns" ($182,100),
    # NOT the MFJ value ($364,200).
    "qbi_threshold": {
        "single": 182100,
        "married_jointly": 364200,
        "married_separately": 182100,
        "head_of_household": 182100,
        "qualifying_widow": 182100,
    },

    # IRC §164(b)(6), flat SALT cap (pre-OBBBA structure, unchanged 2018-2025):
    # $10,000 ($5,000 MFS). Confirmed against the 2023 Instructions for
    # Schedule A (Form 1040) (irs.gov/pub/irs-prior/i1040sca--2023.pdf), "Line
    # 5" section: "The deduction for state and local taxes is generally
    # limited to $10,000 ($5,000 if married filing separately)."
    "salt_cap_starting": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # No income-based SALT phaseout existed under the pre-OBBBA IRC §164(b)(6)
    # flat-cap structure in effect for TY2023 -- flat cap, no phaseout.
    "salt_phaseout_threshold": None,
    "salt_phaseout_rate": 0.0,

    # Same flat cap as salt_cap_starting for TY2023 -- IRC §164(b)(6), $10,000
    # ($5,000 MFS); confirmed via the same 2023 Schedule A instructions "Line
    # 5" text cited above. The cap floor equals the flat cap because there is
    # no phaseout in this pre-OBBBA year.
    "salt_cap_floor": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # IRC §213(a), permanent 7.5% AGI floor. Confirmed against the 2023
    # Instructions for Schedule A (Form 1040), "Medical and Dental Expenses"
    # section: "You can deduct only the part of your medical and dental
    # expenses that exceeds 7.5% of the amount of your adjusted gross income
    # on Form 1040 or 1040-SR, line 11."
    "medical_agi_floor_pct": 0.075,

    # TY2022 SALT cap (the year a TY2023 return's state-refund look-back would
    # reference) -- IRC §164(b)(6), same flat $10,000 ($5,000 MFS) structure.
    # Confirmed against the 2022 Instructions for Schedule A (Form 1040)
    # (irs.gov/pub/irs-prior/i1040sca--2022.pdf): "generally limited to
    # $10,000 ($5,000 if married filing separately)."
    "prior_year_salt_cap": {
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },

    # IRS Rev. Proc. 2022-38 §3.06 "Earned Income Credit", table (1) "In
    # general": per the schema's docstring, this field holds the "completed
    # phaseout amount" -- the largest AGI at which the credit is still
    # allowed for ANY filing status -- i.e. the MFJ-column maximum by
    # construction (MFJ has the highest ceiling). Read the "Completed
    # Phaseout Amount ... (Married Filing Jointly)" row, by number of
    # qualifying children:
    #   0 children: $17,640 (Single/HoH/QSS row) / $24,210 (MFJ row)
    #   1 child:    $46,560 (Single/HoH/QSS row) / $53,120 (MFJ row)
    #   2 children: $52,918 (Single/HoH/QSS row) / $59,478 (MFJ row)
    #   3+ children:$56,838 (Single/HoH/QSS row) / $63,398 (MFJ row)
    # Values below are the MFJ-row maxima, per the docstring's instruction.
    "eic_income_ceiling": {
        0: 24210,
        1: 53120,
        2: 59478,
        3: 63398,
    },
}

SOURCES: tuple[str, ...] = (
    "IRS Rev. Proc. 2022-38, https://www.irs.gov/pub/irs-drop/rp-22-38.pdf "
    "-- SECTION 3.01 Table 3 (Unmarried Individuals other than Surviving "
    "Spouses and Heads of Households) for ordinary_brackets; SECTION 3.03 "
    "(Maximum Capital Gains Rate) for qdcgt_breakpoints; SECTION 3.06 "
    "(Earned Income Credit) for eic_income_ceiling; SECTION 3.15 (Standard "
    "Deduction) for standard_deduction; SECTION 3.27 (Qualified Business "
    "Income, IRC section 199A) for qbi_threshold.",
    "IRC section 1211(b) (limitation on capital losses), statutory, not "
    "inflation-indexed (no cost-of-living provision in the section; unamended "
    "since Pub. L. 99-514, 1986; absent from Rev. Proc. 2022-38) -- "
    "https://www.law.cornell.edu/uscode/text/26/1211 -- confirmed against the "
    "2023 Schedule D (Form 1040), https://www.irs.gov/pub/irs-prior/"
    "f1040sd--2023.pdf, Line 21 ('($3,000), or if married filing separately, "
    "($1,500)'), and the 2023 Instructions for Schedule D (Form 1040), "
    "https://www.irs.gov/pub/irs-prior/i1040sd--2023.pdf, 'Capital Losses' "
    "section (page 4), for capital_loss_limit.",
    "IRC section 3101(b)(2) (Additional Medicare Tax), statutory, not "
    "inflation-adjusted -- confirmed against IRS 'Questions and Answers for "
    "the Additional Medicare Tax', "
    "https://www.irs.gov/businesses/small-businesses-self-employed/"
    "questions-and-answers-for-the-additional-medicare-tax , 'Basic FAQs' "
    "table, for addl_medicare_threshold.",
    "IRS Publication 15 (Circular E), Employer's Tax Guide, 2023 revision, "
    "https://www.irs.gov/pub/irs-prior/p15--2023.pdf -- 'Social Security "
    "and Medicare Taxes' section, for ss_wage_base. (ssa.gov was "
    "unreachable from this environment: HTTP 403 'Access Denied' on every "
    "path tried, both curl and WebFetch; irs.gov leg of the official-"
    "sources rule used instead, same statutory SSA-set figure.)",
    "IRC section 164(b)(6) (SALT cap, pre-OBBBA flat structure), confirmed "
    "against the 2023 Instructions for Schedule A (Form 1040), "
    "https://www.irs.gov/pub/irs-prior/i1040sca--2023.pdf -- 'Line 5' "
    "section ($10,000/$5,000 cap) and 'Medical and Dental Expenses' "
    "section (7.5% AGI floor), for salt_cap_starting, salt_cap_floor, "
    "medical_agi_floor_pct.",
    "IRC section 164(b)(6), confirmed against the 2022 Instructions for "
    "Schedule A (Form 1040), "
    "https://www.irs.gov/pub/irs-prior/i1040sca--2022.pdf -- 'Line 5' "
    "section ($10,000/$5,000 cap), for prior_year_salt_cap.",
    "2023 Instructions for Form 1040 (and 1040-SR), "
    "https://www.irs.gov/pub/irs-prior/i1040gi--2023.pdf -- Line 12 is "
    "'Itemized Deductions or Standard Deduction' with no line 12b non-itemizer "
    "charitable cash deduction (nonitemizer_charitable_cap None; the 2020-2021 "
    "provision expired).",
)
