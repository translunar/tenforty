"""AIR-GAPPED oracle attestation for California (Form 540) tax year 2021.

Independently transcribed from the official FTB 2021 Personal Income Tax
Booklet (Form 540) by a transcriber who did NOT read tenforty/params/,
tenforty/forms/, tenforty/mappings/, or any California implementation module,
and who consulted no git history. Its sole purpose is to catch transcription
errors by being derived separately from the primary FTB source. One citation
comment per value.

California levies income tax via a rate SCHEDULE and grants personal/dependent
exemptions as nonrefundable CREDITS (dollar amounts), not deductions. The
exemption credits phase out above a federal-AGI threshold (Form 540 line 13).
Per-filing-status structures use the same status-key convention as the federal
attestation files. The rate schedule is encoded as (LOWER_BOUND, marginal_rate)
pairs starting at (0, 0.01), keyed per status because California publishes three
distinct schedules (X/Y/Z) covering the five statuses.
"""

SOURCES: tuple[str, ...] = (
    # Primary source for every 2021 value below: the FTB 2021 Personal Income
    # Tax Booklet (Form 540 + instructions), fetched directly from ftb.ca.gov.
    "FTB 2021 Personal Income Tax Booklet (Form 540), "
    "https://www.ftb.ca.gov/forms/2021/2021-540-booklet.pdf: "
    "'California Standard Deduction Chart for Most People' (standard_deduction); "
    "Form 540 Side 1 lines 7-10 exemptions boxes '× $129' / '× $400' "
    "(exemption_credit, dependent_exemption_amount); "
    "Line 32 'Exemption Credits' AGI-limitation table 'Is Form 540, line 13 "
    "more than:' (agi_phaseout_threshold); "
    "'2021 California Tax Rate Schedules', Page 93, Schedules X/Y/Z (rate_schedule); "
    "'Nonrefundable Renter's Credit Qualification Record', Page 23, questions 2 & 11 "
    "(renter_credit_agi_threshold, renter_credit_amount).",
)

ATTESTED: dict[str, object] = {
    "year": 2021,  # 2021 Personal Income Tax Booklet, Form 540 tax year
    "standard_deduction": {
        # "California Standard Deduction Chart for Most People" (Enter On Line 18):
        "single": 4803,              # "1 - Single ... $4,803"
        "married_jointly": 9606,     # "2 - Married/RDP filing jointly ... $9,606"
        "married_separately": 4803,  # "3 - Married/RDP filing separately ... $4,803"
        "head_of_household": 9606,   # "4 - Head of household ... $9,606"
        "qualifying_widow": 9606,    # "5 - Qualifying widow(er) ... $9,606"
    },
    "exemption_credit": {
        # SOURCE publishes a PER-PERSON personal exemption CREDIT of $129
        # (Form 540 Side 1, line 7 box multiplier "X $129"). Form 540 line 7
        # instructs entering the number of personal exemptions ("box 2 or 5,
        # enter 2" for MFJ / Qualifying Widow(er); "1" for single/MFS/HoH), so
        # the attested per-status value is the LINE-7 TOTAL = $129 × count.
        "single": 129,               # 1 personal exemption × $129
        "married_separately": 129,   # 1 × $129
        "head_of_household": 129,    # 1 × $129
        "married_jointly": 258,      # 2 personal exemptions × $129
        "qualifying_widow": 258,     # 2 × $129 (line 7 "box 2 or 5, enter 2")
    },
    # Form 540 Side 1, line 10 "Total dependent exemptions ... X $400".
    # Dependent exemption CREDIT = $400 per dependent.
    "dependent_exemption_amount": 400,
    # Line 32 "Exemption Credits": "If your federal AGI on line 13 is more than
    # the amount shown below for your filing status, your credits will be
    # limited." The SOURCE publishes per-status thresholds:
    #   Single or married/RDP filing separately ... $212,288
    #   Married/RDP filing jointly or qualifying widow(er) ... $424,581
    #   Head of household ... $318,437
    # The library carries the MINIMUM (single/MFS) as a conservative refusal
    # gate: above it the return refuses computation rather than applying a
    # phaseout, so non-single filers between their true threshold and this one
    # over-refuse but can never be computed wrongly. Attested = the scalar
    # single/MFS minimum.
    "agi_phaseout_threshold": 212288,
    "rate_schedule": {
        # "2021 California Tax Rate Schedules", Page 93. Encoded as ascending
        # (LOWER_BOUND, marginal_rate) pairs starting at (0, 0.01). Rates from
        # the "+ n.nn%" marginal-rate column; lower bounds are the "over -"
        # column values.
        # Schedule X - Single or Married/RDP Filing Separately:
        "single": (
            (0, 0.01),         # $0 - $9,325 -> 1.00%
            (9325, 0.02),      # $9,325 - $22,107 -> 2.00%
            (22107, 0.04),     # $22,107 - $34,892 -> 4.00%
            (34892, 0.06),     # $34,892 - $48,435 -> 6.00%
            (48435, 0.08),     # $48,435 - $61,214 -> 8.00%
            (61214, 0.093),    # $61,214 - $312,686 -> 9.30%
            (312686, 0.103),   # $312,686 - $375,221 -> 10.30%
            (375221, 0.113),   # $375,221 - $625,369 -> 11.30%
            (625369, 0.123),   # $625,369 AND OVER -> 12.30%
        ),
        "married_separately": (  # Schedule X (same as single)
            (0, 0.01),
            (9325, 0.02),
            (22107, 0.04),
            (34892, 0.06),
            (48435, 0.08),
            (61214, 0.093),
            (312686, 0.103),
            (375221, 0.113),
            (625369, 0.123),
        ),
        # Schedule Y - Married/RDP Filing Jointly or Qualifying Widow(er):
        "married_jointly": (
            (0, 0.01),         # $0 - $18,650 -> 1.00%
            (18650, 0.02),     # $18,650 - $44,214 -> 2.00%
            (44214, 0.04),     # $44,214 - $69,784 -> 4.00%
            (69784, 0.06),     # $69,784 - $96,870 -> 6.00%
            (96870, 0.08),     # $96,870 - $122,428 -> 8.00%
            (122428, 0.093),   # $122,428 - $625,372 -> 9.30%
            (625372, 0.103),   # $625,372 - $750,442 -> 10.30%
            (750442, 0.113),   # $750,442 - $1,250,738 -> 11.30%
            (1250738, 0.123),  # $1,250,738 AND OVER -> 12.30%
        ),
        "qualifying_widow": (  # Schedule Y (same as MFJ)
            (0, 0.01),
            (18650, 0.02),
            (44214, 0.04),
            (69784, 0.06),
            (96870, 0.08),
            (122428, 0.093),
            (625372, 0.103),
            (750442, 0.113),
            (1250738, 0.123),
        ),
        # Schedule Z - Head of Household:
        "head_of_household": (
            (0, 0.01),         # $0 - $18,663 -> 1.00%
            (18663, 0.02),     # $18,663 - $44,217 -> 2.00%
            (44217, 0.04),     # $44,217 - $56,999 -> 4.00%
            (56999, 0.06),     # $56,999 - $70,542 -> 6.00%
            (70542, 0.08),     # $70,542 - $83,324 -> 8.00%
            (83324, 0.093),    # $83,324 - $425,251 -> 9.30%
            (425251, 0.103),   # $425,251 - $510,303 -> 10.30%
            (510303, 0.113),   # $510,303 - $850,503 -> 11.30%
            (850503, 0.123),   # $850,503 AND OVER -> 12.30%
        ),
    },
    "renter_credit_agi_threshold": {
        # Nonrefundable Renter's Credit Qualification Record, Page 23, Q2:
        # "Is your California adjusted gross income the amount on line 17:"
        "single": 45448,              # "$45,448 or less if single or married/RDP filing separately"
        "married_separately": 45448,  # same clause: "$45,448 or less if single or married/RDP filing separately"
        "married_jointly": 90896,     # "$90,896 or less if married/RDP filing jointly, head of household, or qualifying widow(er)"
        "head_of_household": 90896,   # same clause: $90,896
        "qualifying_widow": 90896,    # same clause: $90,896
    },
    "renter_credit_amount": {
        # Nonrefundable Renter's Credit Qualification Record, Page 23, Q11
        # ("If you are: ... enter $XX on Form 540, line 46"):
        "single": 60,               # "Single, enter $60"
        "married_separately": 60,   # "Married/RDP filing separately ... each spouse/RDP may claim half the amount ($60 each)"
        "married_jointly": 120,     # "Married/RDP filing jointly, enter $120"
        "head_of_household": 120,   # "Head of household or qualifying widow(er), enter $120"
        "qualifying_widow": 120,    # "Head of household or qualifying widow(er), enter $120"
    },
}
