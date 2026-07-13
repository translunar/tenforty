"""AIR-GAPPED oracle attestation for federal tax year 2021.

Independently transcribed from official IRS publications (see SOURCES) by a
transcriber who did NOT read tenforty/params/federal/y2021.py or any other
implementation module. Its sole purpose is to catch transcription errors by
being derived separately from the same primary sources. One citation comment
per value.
"""
import math

SOURCES: tuple[str, ...] = (
    # 2021 inflation adjustments: standard deduction, tax-rate schedules,
    # capital-gains breakpoints, §199A/QBI threshold.
    "Rev. Proc. 2020-45, https://www.irs.gov/pub/irs-drop/rp-20-45.pdf",
    # Statutory SALT cap (Line 5) and 7.5% medical-expense AGI floor (Line 1).
    "2021 Instructions for Schedule A (Form 1040), "
    "https://www.irs.gov/pub/irs-prior/i1040sca--2021.pdf",
    # Social Security (OASDI) wage base for 2021.
    "IRS Pub. 15 (Circular E) 2021, https://www.irs.gov/pub/irs-prior/p15--2021.pdf",
    # Additional Medicare Tax filing-status thresholds (not inflation-indexed).
    "2021 Instructions for Form 8959, https://www.irs.gov/pub/irs-prior/i8959--2021.pdf",
    # ARPA-expanded 2021 EITC completed-phaseout (max AGI) limits.
    "IRS Pub. 596 (2021), https://www.irs.gov/pub/irs-prior/p596--2021.pdf",
)

ATTESTED: dict[str, object] = {
    "year": 2021,  # tax year of Rev. Proc. 2020-45 (§ 3.01, "beginning in 2021")
    "standard_deduction": {
        # Rev. Proc. 2020-45 § 3.16(1), § 63(c)(2):
        "single": 12550,           # Unmarried Individuals (§ 1(j)(2)(C)): $12,550
        "married_jointly": 25100,  # MFJ and Surviving Spouses (§ 1(j)(2)(A)): $25,100
        "married_separately": 12550,  # MFS (§ 1(j)(2)(D)): $12,550
        "head_of_household": 18800,   # Heads of Households (§ 1(j)(2)(B)): $18,800
        "qualifying_widow": 25100,    # Surviving Spouse takes MFJ row (§ 1(j)(2)(A)): $25,100
    },
    # Rev. Proc. 2020-45 § 3.01, TABLE 3 — Unmarried Individuals (§ 1(j)(2)(C)),
    # the 2021 SINGLE rate schedule; (upper_bound, rate) ascending.
    "ordinary_brackets": (
        (9950.0, 0.10),     # Not over $9,950 -> 10%
        (40525.0, 0.12),    # Over $9,950, not over $40,525 -> 12%
        (86375.0, 0.22),    # Over $40,525, not over $86,375 -> 22%
        (164925.0, 0.24),   # Over $86,375, not over $164,925 -> 24%
        (209425.0, 0.32),   # Over $164,925, not over $209,425 -> 32%
        (523600.0, 0.35),   # Over $209,425, not over $523,600 -> 35%
        (math.inf, 0.37),   # Over $523,600 -> 37%
    ),
    "qdcgt_breakpoints": {
        # Rev. Proc. 2020-45 § 3.03 (Max Zero Rate Amt, Max 15% Rate Amt):
        "single": (40400, 445850),            # any other individual: $40,400 / $445,850
        "married_jointly": (80800, 501600),   # joint return: $80,800 / $501,600
        "married_separately": (40400, 250800),  # MFS: $40,400 / $250,800
        "head_of_household": (54100, 473750),   # head of household: $54,100 / $473,750
        "qualifying_widow": (80800, 501600),    # surviving spouse takes joint row: $80,800 / $501,600
    },
    "addl_medicare_threshold": {
        # 2021 Instructions for Form 8959, "Threshold Amounts for Additional
        # Medicare Tax" chart (note: amounts aren't indexed for inflation):
        "single": 200000,            # Single: $200,000
        "married_jointly": 250000,   # Married filing jointly: $250,000
        "married_separately": 125000,  # Married filing separately: $125,000
        "head_of_household": 200000,   # Head of household: $200,000
        "qualifying_widow": 200000,    # Qualifying widow(er): $200,000
    },
    # IRS Pub. 15 (Circular E) 2021: "The social security wage base limit is
    # $142,800."
    "ss_wage_base": 142800,
    "qbi_threshold": {
        # Rev. Proc. 2020-45 § 3.27, § 199A(e)(2) threshold amount:
        "single": 164900,            # all other returns: $164,900
        "married_jointly": 329800,   # married filing joint returns: $329,800
        "married_separately": 164925,  # married filing separate returns: $164,925
        "head_of_household": 164900,   # all other returns: $164,900
        "qualifying_widow": 164900,    # QSS takes "all other returns" row: $164,900
    },
    "salt_cap_starting": {
        # Flat pre-OBBBA cap, IRC § 164(b)(6); 2021 Instr. Sch A, Line 5:
        # "generally limited to $10,000 ($5,000 if married filing separately)."
        # No phasedown in 2021, so the starting cap equals the floor.
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    # See NOT_APPLICABLE: 2021 SALT is the flat § 164(b)(6) cap with no
    # MAGI-based phaseout (the phaseout structure did not exist until OBBBA).
    "salt_phaseout_threshold": None,
    # No phaseout in 2021 -> rate is 0.0 (IRC § 164(b)(6), flat cap).
    "salt_phaseout_rate": 0.0,
    "salt_cap_floor": {
        # IRC § 164(b)(6); 2021 Instr. Sch A, Line 5: $10,000 flat cap,
        # $5,000 if married filing separately. Flat cap IS the floor in 2021.
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    # 2021 Instr. Sch A, Line 1: medical/dental in excess of 7.5% of AGI
    # (IRC § 213(a)).
    "medical_agi_floor_pct": 0.075,
    "prior_year_salt_cap": {
        # A 2021 return's state-refund tax-benefit-rule looks back to 2020,
        # which was also under the flat TCJA § 164(b)(6) cap ($10,000;
        # $5,000 MFS), effective for tax years 2018-2025.
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "eic_income_ceiling": {
        # IRS Pub. 596 (2021), "Income (AGI) Limits" — MFJ column (highest
        # ceiling; AGI must be LESS THAN these amounts). The 0-child ceiling
        # reflects the ARPA (2021-only) childless-EITC expansion, materially
        # higher than the pre-ARPA Rev. Proc. 2020-45 figure of $21,920.
        0: 27380,  # no qualifying child (MFJ): $27,380
        1: 48108,  # one qualifying child (MFJ): $48,108
        2: 53865,  # two qualifying children (MFJ): $53,865
        3: 57414,  # three or more qualifying children (MFJ): $57,414
    },
}

NOT_APPLICABLE: dict[str, str] = {
    "salt_phaseout_threshold": (
        "2021 SALT is the flat pre-OBBBA IRC § 164(b)(6) cap ($10,000; "
        "$5,000 MFS) with NO MAGI-based phaseout. The income-based phaseout "
        "structure did not exist for 2021 — it was introduced by OBBBA for "
        "tax years 2025 and later. Attested as None (not a sourced value)."
    ),
}
