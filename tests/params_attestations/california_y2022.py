"""AIR-GAPPED oracle attestation for California (Form 540) tax year 2022.

Independently transcribed from the official FTB 2022 Personal Income Tax
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
distinct schedules (X/Y/Z) covering the five statuses. For 2022 the FTB renamed
"qualifying widow(er)" to "qualifying surviving spouse/RDP"; the params status
key remains `qualifying_widow`.
"""

SOURCES: tuple[str, ...] = (
    # Primary source for every 2022 value below: the FTB 2022 Personal Income
    # Tax Booklet (Form 540 + instructions), fetched directly from ftb.ca.gov.
    "FTB 2022 Personal Income Tax Booklet (Form 540), "
    "https://www.ftb.ca.gov/forms/2022/2022-540-booklet.pdf: "
    "'California Standard Deduction Chart for Most People' (standard_deduction); "
    "Form 540 Side 1 lines 7-10 exemptions boxes '× $140' / '× $433' "
    "(exemption_credit, dependent_exemption_amount); "
    "Line 32 'Exemption Credits' AGI-limitation table 'Is Form 540, line 13 "
    "more than:' (agi_phaseout_threshold); "
    "'2022 California Tax Rate Schedules', Page 93, Schedules X/Y/Z (rate_schedule); "
    "'Nonrefundable Renter's Credit Qualification Record', questions 2 & 11 "
    "(renter_credit_agi_threshold, renter_credit_amount).",
)

ATTESTED: dict[str, object] = {
    "year": 2022,  # 2022 Personal Income Tax Booklet, Form 540 tax year
    "standard_deduction": {
        # "California Standard Deduction Chart for Most People" (Enter On Line 18):
        "single": 5202,               # "1 - Single ... $5,202"
        "married_jointly": 10404,     # "2 - Married/RDP filing jointly ... $10,404"
        "married_separately": 5202,   # "3 - Married/RDP filing separately ... $5,202"
        "head_of_household": 10404,   # "4 - Head of household ... $10,404"
        "qualifying_widow": 10404,    # "5 - Qualifying surviving spouse/RDP ... $10,404"
    },
    "exemption_credit": {
        # SOURCE publishes a PER-PERSON personal exemption CREDIT of $140
        # (Form 540 Side 1, line 7 box multiplier "X $140"). Form 540 line 7
        # instructs entering the number of personal exemptions ("box 2 or 5,
        # enter 2" for MFJ / Qualifying Surviving Spouse; "1" for
        # single/MFS/HoH), so the attested per-status value is the LINE-7 TOTAL
        # = $140 × count.
        "single": 140,               # 1 personal exemption × $140
        "married_separately": 140,   # 1 × $140
        "head_of_household": 140,    # 1 × $140
        "married_jointly": 280,      # 2 personal exemptions × $140
        "qualifying_widow": 280,     # 2 × $140 (line 7 "box 2 or 5, enter 2")
    },
    # Form 540 Side 1, line 10 "Total dependent exemptions ... X $433".
    # Dependent exemption CREDIT = $433 per dependent.
    "dependent_exemption_amount": 433,
    # Line 32 "Exemption Credits": "If your federal AGI on line 13 is more than
    # the amount shown below for your filing status, your credits will be
    # limited." The SOURCE publishes per-status thresholds:
    #   Single or married/RDP filing separately ... $229,908
    #   Married/RDP filing jointly or qualifying surviving spouse/RDP ... $459,821
    #   Head of household ... $344,867
    # The library carries the MINIMUM (single/MFS) as a conservative refusal
    # gate: above it the return refuses computation rather than applying a
    # phaseout, so non-single filers between their true threshold and this one
    # over-refuse but can never be computed wrongly. Attested = the scalar
    # single/MFS minimum.
    "agi_phaseout_threshold": 229908,
    "rate_schedule": {
        # "2022 California Tax Rate Schedules", Page 93. Encoded as ascending
        # (LOWER_BOUND, marginal_rate) pairs starting at (0, 0.01). Rates from
        # the "+ n.nn%" marginal-rate column; lower bounds are the "over -"
        # column values.
        # Schedule X - Single or Married/RDP Filing Separately:
        "single": (
            (0, 0.01),         # $0 - $10,099 -> 1.00%
            (10099, 0.02),     # $10,099 - $23,942 -> 2.00%
            (23942, 0.04),     # $23,942 - $37,788 -> 4.00%
            (37788, 0.06),     # $37,788 - $52,455 -> 6.00%
            (52455, 0.08),     # $52,455 - $66,295 -> 8.00%
            (66295, 0.093),    # $66,295 - $338,639 -> 9.30%
            (338639, 0.103),   # $338,639 - $406,364 -> 10.30%
            (406364, 0.113),   # $406,364 - $677,275 -> 11.30%
            (677275, 0.123),   # $677,275 AND OVER -> 12.30%
        ),
        "married_separately": (  # Schedule X (same as single)
            (0, 0.01),
            (10099, 0.02),
            (23942, 0.04),
            (37788, 0.06),
            (52455, 0.08),
            (66295, 0.093),
            (338639, 0.103),
            (406364, 0.113),
            (677275, 0.123),
        ),
        # Schedule Y - Married/RDP Filing Jointly or Qualifying Surviving Spouse/RDP:
        "married_jointly": (
            (0, 0.01),         # $0 - $20,198 -> 1.00%
            (20198, 0.02),     # $20,198 - $47,884 -> 2.00%
            (47884, 0.04),     # $47,884 - $75,576 -> 4.00%
            (75576, 0.06),     # $75,576 - $104,910 -> 6.00%
            (104910, 0.08),    # $104,910 - $132,590 -> 8.00%
            (132590, 0.093),   # $132,590 - $677,278 -> 9.30%
            (677278, 0.103),   # $677,278 - $812,728 -> 10.30%
            (812728, 0.113),   # $812,728 - $1,354,550 -> 11.30%
            (1354550, 0.123),  # $1,354,550 AND OVER -> 12.30%
        ),
        "qualifying_widow": (  # Schedule Y (same as MFJ)
            (0, 0.01),
            (20198, 0.02),
            (47884, 0.04),
            (75576, 0.06),
            (104910, 0.08),
            (132590, 0.093),
            (677278, 0.103),
            (812728, 0.113),
            (1354550, 0.123),
        ),
        # Schedule Z - Head of Household:
        "head_of_household": (
            (0, 0.01),         # $0 - $20,212 -> 1.00%
            (20212, 0.02),     # $20,212 - $47,887 -> 2.00%
            (47887, 0.04),     # $47,887 - $61,730 -> 4.00%
            (61730, 0.06),     # $61,730 - $76,397 -> 6.00%
            (76397, 0.08),     # $76,397 - $90,240 -> 8.00%
            (90240, 0.093),    # $90,240 - $460,547 -> 9.30%
            (460547, 0.103),   # $460,547 - $552,658 -> 10.30%
            (552658, 0.113),   # $552,658 - $921,095 -> 11.30%
            (921095, 0.123),   # $921,095 AND OVER -> 12.30%
        ),
    },
    "renter_credit_agi_threshold": {
        # Nonrefundable Renter's Credit Qualification Record, Q2:
        # "Is your California adjusted gross income the amount on line 17:"
        "single": 49220,              # "$49,220 or less if single or married/RDP filing separately"
        "married_separately": 49220,  # same clause: "$49,220 or less if single or married/RDP filing separately"
        "married_jointly": 98440,     # "$98,440 or less if married/RDP filing jointly, head of household, or qualifying surviving spouse/RDP"
        "head_of_household": 98440,   # same clause: $98,440
        "qualifying_widow": 98440,    # same clause: $98,440
    },
    "renter_credit_amount": {
        # Nonrefundable Renter's Credit Qualification Record, Q11
        # ("If you are: ... enter $XX on Form 540, line 46"):
        "single": 60,               # "Single, enter $60"
        "married_separately": 60,   # "Married/RDP filing separately ... each spouse/RDP may claim half the amount ($60 each)"
        "married_jointly": 120,     # "Married/RDP filing jointly, enter $120"
        "head_of_household": 120,   # "Head of household or qualifying surviving spouse/RDP, enter $120"
        "qualifying_widow": 120,    # "Head of household or qualifying surviving spouse/RDP, enter $120"
    },
}
