"""Independent (Transcriber B) attestation of federal tax-year 2022 parameters.

Transcribed AIR-GAPPED from official IRS/SSA publications fetched directly by
this transcriber: IRS Rev. Proc. 2021-45 (2022 inflation adjustments), the 2022
Instructions for Schedule A (Form 1040), the 2022 Instructions for Form 8959,
and IRS Publication 15 (Circular E), 2022 revision. No other transcription,
attestation, params module, oracle, or secondary/summary source was consulted;
every dollar figure below was read verbatim from the official document text.

Each value carries an inline citation to the exact document and section/table.
"""

import math

ATTESTED: dict[str, object] = {
    "year": 2022,  # Rev. Proc. 2021-45 §3 "2022 Adjusted Items" (taxable years beginning in 2022)
    "standard_deduction": {
        # Rev. Proc. 2021-45 §3.15(1) Standard Deduction table (§63(c)(2))
        "single": 12950,             # "Unmarried Individuals (other than Surviving Spouses and Heads of Households)"
        "married_jointly": 25900,    # "Married Individuals Filing Joint Returns and Surviving Spouses"
        "married_separately": 12950, # "Married Individuals Filing Separate Returns"
        "head_of_household": 19400,  # "Heads of Households"
        "qualifying_widow": 25900,   # QSS shares the MFJ / "Surviving Spouses" row per §3.15(1)
    },
    "nonitemizer_charitable_cap": None,  # Provision expired after 2021 (see NOT_APPLICABLE)
    "ordinary_brackets": (
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
    "qdcgt_breakpoints": {
        # Rev. Proc. 2021-45 §3.03 Maximum Capital Gains Rate (§1(h)):
        # (Maximum Zero Rate Amount, Maximum 15-percent Rate Amount)
        "single": (41675, 459750),            # "any other individual (other than an estate or trust)"
        "married_jointly": (83350, 517200),   # "joint return or surviving spouse"
        "married_separately": (41675, 258600),# "married individual filing a separate return"
        "head_of_household": (55800, 488500), # "individual who is the head of a household"
        "qualifying_widow": (83350, 517200),  # QSS shares the "surviving spouse" (joint) figures per §3.03
    },
    "addl_medicare_threshold": {
        # 2022 Instructions for Form 8959, "Threshold Amounts for Additional Medicare Tax"
        # (§3101(b)(2)/§1411; note: not indexed for inflation)
        "single": 200000,             # "Single ... $200,000"
        "married_jointly": 250000,    # "Married filing jointly ... $250,000"
        "married_separately": 125000, # "Married filing separately ... $125,000"
        "head_of_household": 200000,  # "Head of household ... $200,000"
        "qualifying_widow": 200000,   # "Qualifying surviving spouse ... $200,000"
    },
    "ss_wage_base": 147000,  # IRS Pub. 15 (Circular E) 2022, Social Security & Medicare Taxes: "wage base limit is $147,000"
    "qbi_threshold": {
        # Rev. Proc. 2021-45 §3.27 Qualified Business Income, Threshold amount (§199A(e)(2))
        "single": 170050,             # "All Other Returns ... $170,050"
        "married_jointly": 340100,    # "Married Individuals Filing Joint Returns ... $340,100"
        "married_separately": 170050, # "Married Individuals Filing Separate Returns ... $170,050"
        "head_of_household": 170050,  # "All Other Returns ... $170,050"
        "qualifying_widow": 170050,   # QSS takes the "All Other Returns" (single-side) value; §199A is joint-return-keyed
    },
    "salt_cap_starting": {
        # IRC §164(b)(6) flat cap, confirmed by 2022 Instructions for Schedule A (Form 1040),
        # Line 5: "generally limited to $10,000 ($5,000 if married filing separately)"
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "salt_phaseout_threshold": None,  # No SALT phaseout under the 2022 flat cap (see NOT_APPLICABLE)
    "salt_phaseout_rate": None,       # No SALT phaseout under the 2022 flat cap (see NOT_APPLICABLE)
    "salt_cap_floor": {
        # IRC §164(b)(6): the 2022 cap is a flat pre-OBBBA amount with no income phase-down,
        # so the floor equals the flat cap itself ($5,000 MFS). Confirmed by 2022 Sch. A instr., Line 5.
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
        "head_of_household": 10000,
        "qualifying_widow": 10000,
    },
    "medical_agi_floor_pct": 0.075,  # 2022 Instructions for Schedule A (Form 1040), Line 1: "exceeds 7.5% of ... adjusted gross income" (§213(a), permanent 7.5%)
    "prior_year_salt_cap": {
        # 2021 (prior-year) SALT cap: same flat IRC §164(b)(6) structure, $10,000 ($5,000 MFS)
        "single": 10000,
        "married_jointly": 10000,
        "married_separately": 5000,
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
    "IRS Rev. Proc. 2021-45 (2022 inflation adjustments), https://www.irs.gov/pub/irs-drop/rp-21-45.pdf: "
    "§3.01 Table 3 (single ordinary rate schedule / ordinary_brackets); "
    "§3.03 Maximum Capital Gains Rate (qdcgt_breakpoints); "
    "§3.06(1) Earned Income Credit table, MFJ completed-phaseout row (eic_income_ceiling); "
    "§3.15(1) Standard Deduction (standard_deduction); "
    "§3.27 Qualified Business Income (qbi_threshold); §3 header (year).",
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
