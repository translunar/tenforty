"""Air-gapped attestation of CALIFORNIA params, tax year 2023.

Independently transcribed from official FTB publications ONLY (on-disk FTB
PDFs) — see SOURCES. Transcribed with no reference to tenforty's own params,
tests, or any derived tax table; the rate schedule is taken from the primary
2023 California Tax Rate Schedules, not from the binned tax table.
"""

SOURCES: tuple[str, ...] = (
    "FTB 2023 Personal Income Tax Booklet (pdfs/california/2023/booklet.pdf), "
    "p. 13 (California Standard Deduction Chart for Most People, Form 540 line 18 instructions)",
    "FTB 2023 Personal Income Tax Booklet (pdfs/california/2023/booklet.pdf), "
    "p. 14 (Line 32 Exemption Credits — AGI Limitation Worksheet, per-status thresholds)",
    "FTB 2023 Personal Income Tax Booklet (pdfs/california/2023/booklet.pdf), "
    "p. 25 (Nonrefundable Renter's Credit Qualification Record: AGI limits Q2)",
    "FTB 2023 Personal Income Tax Booklet (pdfs/california/2023/booklet.pdf), "
    "p. 26 (Nonrefundable Renter's Credit Qualification Record continued, Q11: credit amounts)",
    "FTB 2023 Form 540 (pdfs/california/2023/f540.pdf), Side 1 line 7 (personal "
    "exemption credit, $144/exemption)",
    "FTB 2023 Form 540 (pdfs/california/2023/f540.pdf), Side 2 line 10 (dependent "
    "exemption, $446/dependent)",
    "2023 California Tax Rate Schedules (pdfs/california/2023/tax_rate_schedules.pdf), "
    "Schedules X, Y, Z (Personal Income Tax Booklet 2023 Page 75)",
)

ATTESTED: dict[str, object] = {
    "year": 2023,
    "standard_deduction": {
        # Booklet p.13, "California Standard Deduction Chart for Most People"
        "single": 5363,              # 1 – Single: $5,363
        "married_jointly": 10726,    # 2 – Married/RDP filing jointly: $10,726
        "married_separately": 5363,  # 3 – Married/RDP filing separately: $5,363
        "head_of_household": 10726,  # 4 – Head of household: $10,726
        "qualifying_widow": 10726,   # 5 – Qualifying surviving spouse/RDP: $10,726
    },
    "exemption_credit": {
        # Form 540 Side 1, line 7: $144 per exemption. Single/MFS/HoH = 1x; MFJ/QSS = 2x.
        "single": 144,               # 1 exemption x $144
        "married_separately": 144,   # 1 exemption x $144
        "head_of_household": 144,    # 1 exemption x $144
        "married_jointly": 288,      # 2 exemptions x $144
        "qualifying_widow": 288,     # 2 exemptions x $144
    },
    "dependent_exemption_amount": 446,   # Form 540 Side 2, line 10: X $446 per dependent
    "agi_phaseout_threshold": 237035,    # Booklet p.14 AGI Limitation Wksht line b, SINGLE/MFS: $237,035
                                         #   (MFJ/QSS: $474,075; HoH: $355,558)
    "rate_schedule": {
        # 2023 California Tax Rate Schedules, "over –" (lower bound) column + marginal rate.
        "single": (               # Schedule X (Single or MFS)
            (0, 0.01),
            (10412, 0.02),
            (24684, 0.04),
            (38959, 0.06),
            (54081, 0.08),
            (68350, 0.093),
            (349137, 0.103),
            (418961, 0.113),
            (698271, 0.123),
        ),
        "married_separately": (   # Schedule X (same as Single)
            (0, 0.01),
            (10412, 0.02),
            (24684, 0.04),
            (38959, 0.06),
            (54081, 0.08),
            (68350, 0.093),
            (349137, 0.103),
            (418961, 0.113),
            (698271, 0.123),
        ),
        "married_jointly": (      # Schedule Y (MFJ or QSS)
            (0, 0.01),
            (20824, 0.02),
            (49368, 0.04),
            (77918, 0.06),
            (108162, 0.08),
            (136700, 0.093),
            (698274, 0.103),
            (837922, 0.113),
            (1396542, 0.123),
        ),
        "qualifying_widow": (     # Schedule Y (same as MFJ)
            (0, 0.01),
            (20824, 0.02),
            (49368, 0.04),
            (77918, 0.06),
            (108162, 0.08),
            (136700, 0.093),
            (698274, 0.103),
            (837922, 0.113),
            (1396542, 0.123),
        ),
        "head_of_household": (    # Schedule Z (Head of Household)
            (0, 0.01),
            (20839, 0.02),
            (49371, 0.04),
            (63644, 0.06),
            (78765, 0.08),
            (93037, 0.093),
            (474824, 0.103),
            (569790, 0.113),
            (949649, 0.123),
        ),
    },
    "renter_credit_agi_threshold": {
        # Booklet p.25, Renter's Credit Qualification Record, Q2 (CA AGI on line 17).
        "single": 50746,              # $50,746 or less (single/MFS)
        "married_separately": 50746,  # $50,746 or less (single/MFS)
        "married_jointly": 101492,    # $101,492 or less (MFJ/HoH/QSS)
        "head_of_household": 101492,  # $101,492 or less (MFJ/HoH/QSS)
        "qualifying_widow": 101492,   # $101,492 or less (MFJ/HoH/QSS)
    },
    "renter_credit_amount": {
        # Booklet p.26, Renter's Credit Qualification Record continued, Q11.
        "single": 60,               # Single: $60
        "married_separately": 60,   # MFS: half of $120 = $60 (per-filer)
        "married_jointly": 120,     # MFJ: $120
        "head_of_household": 120,   # HoH: $120
        "qualifying_widow": 120,    # QSS: $120
    },
}
