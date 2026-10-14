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
        "married_filing_jointly": 10726,    # 2 – Married/RDP filing jointly: $10,726
        "married_filing_separately": 5363,  # 3 – Married/RDP filing separately: $5,363
        "head_of_household": 10726,  # 4 – Head of household: $10,726
        "qualifying_widow": 10726,   # 5 – Qualifying surviving spouse/RDP: $10,726
    },
    "exemption_credit": {
        # Form 540 Side 1, line 7: $144 per exemption. Single/MFS/HoH = 1x; MFJ/QSS = 2x.
        "single": 144,               # 1 exemption x $144
        "married_filing_separately": 144,   # 1 exemption x $144
        "head_of_household": 144,    # 1 exemption x $144
        "married_filing_jointly": 288,      # 2 exemptions x $144
        "qualifying_widow": 288,     # 2 exemptions x $144
    },
    "dependent_exemption_amount": 446,   # Form 540 Side 2, line 10: X $446 per dependent
    # Per-status columns attested 2026-10-14 (Transcriber B paste; dual
    # transcription adjudicated vs Transcriber A with full agreement).
    # Source: Line 32 table, booklet p.14; REV: none printed anywhere;
    # sha256 e2d8ef0ba279abf65eec7941a77de6604af9186226e1e79cc80a8ecd2a14d4b9
    "agi_phaseout_threshold": {
        "single": 237035,
        "married_filing_separately": 237035,
        "married_filing_jointly": 474075,
        "qualifying_widow": 474075,
        "head_of_household": 355558,
    },
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
        "married_filing_separately": (   # Schedule X (same as Single)
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
        "married_filing_jointly": (      # Schedule Y (MFJ or QSS)
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
        "married_filing_separately": 50746,  # $50,746 or less (single/MFS)
        "married_filing_jointly": 101492,    # $101,492 or less (MFJ/HoH/QSS)
        "head_of_household": 101492,  # $101,492 or less (MFJ/HoH/QSS)
        "qualifying_widow": 101492,   # $101,492 or less (MFJ/HoH/QSS)
    },
    "renter_credit_amount": {
        # Booklet p.26, Renter's Credit Qualification Record continued, Q11.
        "single": 60,               # Single: $60
        "married_filing_separately": 60,   # MFS: half of $120 = $60 (per-filer)
        "married_filing_jointly": 120,     # MFJ: $120
        "head_of_household": 120,   # HoH: $120
        "qualifying_widow": 120,    # QSS: $120
    },
    # Not yet transcribed (see PENDING_TRANSCRIPTION).
    "senior_exemption_credit": None,
    "senior_born_before": None,
}

PENDING_TRANSCRIPTION: dict[str, str] = {
    "senior_exemption_credit": (
        "Form 540 senior exemption credit per qualifying senior; awaiting "
        "dual transcription (native-filing-statuses round, age-65-params)."),
    "senior_born_before": (
        "Form 540 senior qualifying cutoff from the year's pinned FTB "
        "edition; awaiting dual transcription (native-filing-statuses round, "
        "age-65-params)."),
}
