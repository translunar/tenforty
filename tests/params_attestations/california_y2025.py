"""Air-gapped attestation of CALIFORNIA params, tax year 2025.

Independently transcribed from official FTB publications ONLY — see SOURCES.
Transcribed with no reference to tenforty's own params, tests, or any derived
tax table; the rate schedule is taken from the primary 2025 California Tax Rate
Schedules, not from the binned tax table.

On-disk PDFs for 2025 are the Form 540 (f540.pdf), the Tax Rate Schedules,
Schedule CA (sch_ca.pdf), and the Form 540 2EZ Tax Booklet (booklet_2ez.pdf).
The 2EZ booklet does not cover Married/RDP filing separately (2EZ is unavailable
to MFS); each MFS-specific value was verbatim-sourced from an official document:
the MFS standard deduction from Schedule CA (540) line 30 worksheet and the
ftb.ca.gov 2025 Form 540 instructions, and the MFS renter's-credit AGI limit and
amount from the ftb.ca.gov Nonrefundable Renter's Credit page (both ftb.ca.gov
pages retrieved read-only via curl; nothing saved to disk).
"""

import datetime

SOURCES: tuple[str, ...] = (
    "FTB 2025 Form 540 2EZ Tax Booklet (pdfs/california/2025/booklet_2ez.pdf), "
    "2EZ table header notes ($5,706 std/$153 personal for Single; "
    "$11,412 std/$306 for MFJ-QSS; $11,412 std/$153 for HOH)",
    "FTB 2025 Form 540 (pdfs/california/2025/f540.pdf), Side 1 lines 7 & 10 "
    "(personal exemption credit $153/exemption; dependent exemption $475), "
    "line 32 (exemption-credit AGI phaseout threshold printed as $252,203)",
    "FTB 2025 California Tax Rate Schedules "
    "(pdfs/california/2025/tax_rate_schedules.pdf), Schedules X, Y, Z",
    "FTB 2025 Form 540 2EZ Tax Booklet, p. 13 (Nonrefundable Renter's Credit "
    "Qualification Record: AGI limits $53,994 single / $107,988 MFJ-HOH-QSS; "
    "amounts $60 single, $120 MFJ/HOH/QSS)",
    "FTB 2025 Schedule CA (540) (pdfs/california/2025/sch_ca.pdf), line 30 "
    "standard-deduction worksheet: 'Single or married/RDP filing separately "
    "... $5,706' (verbatim MFS standard deduction)",
    "ftb.ca.gov 2025 Form 540 instructions "
    "(https://www.ftb.ca.gov/forms/2025/2025-540-instructions.html, retrieved "
    "read-only via curl): 'Single or married/RDP filing separately, enter $5,706'",
    "ftb.ca.gov Nonrefundable Renter's Credit page "
    "(https://www.ftb.ca.gov/file/personal/credits/nonrefundable-renters-credit.html, "
    "retrieved read-only via curl, last updated 02/20/2026): verbatim "
    "'$53,994 or less if ... single or married/RDP filing separately' and "
    "'$60 credit if you are: Single, Married/RDP filing separately'",
    "FTB CalEITC 'Eligibility and credit information' page "
    "(https://www.ftb.ca.gov/file/personal/credits/caleitc/eligibility-and-credit-information.html, "
    "retrieved via curl, last updated 04/16/2026), '2025 CalEITC credit' table and "
    "requirements list (caleitc_max_earned_income); and FTB 2025 FTB 3514 booklet "
    "(https://www.ftb.ca.gov/forms/2025/2025-3514-booklet.html), 'B. Differences in "
    "California and Federal Law' / Step 1 (exclusive-bound wording cross-check) and "
    "Earned Income Tax Credit Table last bracket.",
)

# rate_schedule canonical shape (per schema docstring +
# forms.f540._walk_rate_schedule): each status maps to an ASCENDING tuple of
# (threshold_low_inclusive, marginal_rate_at_or_above_that_threshold) pairs.
# The bracket starting at threshold[i] runs until threshold[i+1] (exclusive);
# the top bracket has no upper bound and there is NO math.inf terminator entry.
# Thresholds are the "over –" (lower-bound) column of the FTB Tax Rate Schedules.
ATTESTED: dict[str, object] = {
    "year": 2025,

    "standard_deduction": {
        "single": 5706,               # 2EZ Single table note ($5,706)
        "married_filing_jointly": 11412,      # 2EZ MFJ/QSS table note ($11,412)
        "married_filing_separately": 5706,    # sch_ca.pdf line 30 worksheet: "Single or married/RDP filing separately ... $5,706" (verbatim); + ftb.ca.gov 2025 540 instructions "enter $5,706"
        "head_of_household": 11412,    # 2EZ HOH table note ($11,412)
        "qualifying_widow": 11412,     # 2EZ MFJ/QSS table note ($11,412)
    },

    # Personal exemption credit. Form 540 line 7: $153 per exemption; statuses
    # 1/3/4 (single, MFS, HOH) claim 1 ($153); statuses 2/5 (MFJ, QSS) claim 2.
    "exemption_credit": {
        "single": 153,                 # f540 line 7: 1 x $153
        "married_filing_jointly": 306,        # f540 line 7: 2 x $153
        "married_filing_separately": 153,     # f540 line 7: 1 x $153
        "head_of_household": 153,      # f540 line 7: 1 x $153
        "qualifying_widow": 306,       # f540 line 7: 2 x $153
    },

    "dependent_exemption_amount": 475,  # f540 line 10: X $475 per dependent

    # Per-status columns attested 2026-10-14 (Transcriber B paste; dual
    # transcription adjudicated vs Transcriber A with full agreement).
    # Source: Line 32 table, booklet p.14; REV: none printed on Line 32 page
    # (elsewhere 02-26, 04-26);
    # sha256 b48ee24bd2f9b9e74fe9a5bbc548d15bae0bd1ce53306bef1ff33fc76f8078c1
    "agi_phaseout_threshold": {
        "single": 252203,
        "married_filing_separately": 252203,
        "married_filing_jointly": 504411,
        "qualifying_widow": 504411,
        "head_of_household": 378310,
    },

    # 2025 California Tax Rate Schedules (tax_rate_schedules.pdf).
    "rate_schedule": {
        # Schedule X – Single or Married/RDP filing separately
        "single": (
            (0, 0.01), (11079, 0.02), (26264, 0.04), (41452, 0.06),
            (57542, 0.08), (72724, 0.093), (371479, 0.103), (445771, 0.113),
            (742953, 0.123),
        ),  # tax_rate_schedules.pdf Schedule X
        # Schedule Y – Married/RDP filing jointly or Qualifying surviving spouse/RDP
        "married_filing_jointly": (
            (0, 0.01), (22158, 0.02), (52528, 0.04), (82904, 0.06),
            (115084, 0.08), (145448, 0.093), (742958, 0.103), (891542, 0.113),
            (1485906, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Y
        # Schedule X – shared by MFS
        "married_filing_separately": (
            (0, 0.01), (11079, 0.02), (26264, 0.04), (41452, 0.06),
            (57542, 0.08), (72724, 0.093), (371479, 0.103), (445771, 0.113),
            (742953, 0.123),
        ),  # tax_rate_schedules.pdf Schedule X
        # Schedule Z – Head of household
        "head_of_household": (
            (0, 0.01), (22173, 0.02), (52530, 0.04), (67716, 0.06),
            (83805, 0.08), (98990, 0.093), (505208, 0.103), (606251, 0.113),
            (1010417, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Z
        # Schedule Y – shared by QSS
        "qualifying_widow": (
            (0, 0.01), (22158, 0.02), (52528, 0.04), (82904, 0.06),
            (115084, 0.08), (145448, 0.093), (742958, 0.103), (891542, 0.113),
            (1485906, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Y
    },

    # Nonrefundable Renter's Credit Qualification Record (2EZ booklet p. 13,
    # q.2). MFS confirmed to share the single limit via ftb.ca.gov 540 instr.
    "renter_credit_agi_threshold": {
        "single": 53994,              # "$53,994 or less if single"
        "married_filing_jointly": 107988,     # "$107,988 or less if MFJ, HOH, or QSS"
        "married_filing_separately": 53994,   # ftb.ca.gov renter's-credit page (curl, verbatim): "$53,994 or less if ... single or married/RDP filing separately"
        "head_of_household": 107988,   # "$107,988 ... MFJ, HOH, or QSS"
        "qualifying_widow": 107988,    # "$107,988 ... MFJ, HOH, or QSS"
    },

    # Renter's credit amount (2EZ booklet p. 13, q.11; MFS via ftb.ca.gov).
    "renter_credit_amount": {
        "single": 60,                  # "Single, enter $60"
        "married_filing_jointly": 120,        # "Married/RDP filing jointly, enter $120"
        "married_filing_separately": 60,      # ftb.ca.gov renter's-credit page (curl, verbatim): "$60 credit if you are: Single, Married/RDP filing separately"
        "head_of_household": 120,      # "Head of household ... enter $120"
        "qualifying_widow": 120,       # "qualifying surviving spouse/RDP ... $120"
    },
    # Attested 2026-10-14 (Transcriber B paste; dual transcription adjudicated
    # vs Transcriber A with full agreement incl. a third reading of the
    # amount). Amount: Form 540 line 9 "x $" box (box assigned by
    # rendered-page position). Date: team-lead words-to-date ruling from the
    # verbatim Line 9 wording + footnote (both transcribers deferred, as the
    # booklet prints no born-before date): exclusive cutoff January 2, 1961.
    "senior_exemption_credit": 153,
    "senior_born_before": datetime.date(1961, 1, 2),
    # Form 540 line 31 tax-table / rate-schedule boundary. Attested
    # 2026-10-17 by an air-gapped transcriber (never read tenforty source)
    # from the pinned FTB 2025 540 booklet pdfs/california/2025/booklet.pdf,
    # sha256 b48ee24bd2f9b9e74fe9a5bbc548d15bae0bd1ce53306bef1ff33fc76f8078c1.
    # Booklet p.13, "Line 31 – Tax": "Tax Table – If your taxable income on
    # line 19 is $100,000 or less, use the tax table beginning on page 69.
    # ... Tax Rate Schedules – If your taxable income on line 19 is over
    # $100,000, use the tax rate schedule for your filing status on page 75."
    # Restated on p.75 ("2025 California Tax Rate Schedules"): "Use only if
    # your taxable income on Form 540, line 19 is more than $100,000. If
    # $100,000 or less, use the Tax Table." The tax table's final row is
    # "At least 99,951 But not over 100,000". INCLUSIVE ceiling: line 19 <=
    # 100,000 uses the table; > 100,000 uses the schedules. One amount for
    # all filing statuses (the text is not status-keyed). REV: none on
    # p.13 or p.75.
    "tax_table_taxable_income_ceiling": 100000,
    # caleitc_max_earned_income: maximum earned income with which a taxpayer can
    # qualify for CalEITC. Attested by an air-gapped transcriber from FTB web pages
    # (fetched via curl; WebFetch was 403) and the FTB 3514 instructions. The
    # statute (R&TC 17052 / 17052.1) could NOT be read from leginfo (HTTP 403) and
    # was seen only via the third-party mirror california.public.law, which shows
    # a single (current) version and dropped the (m)/(n)/(o) table cells; no
    # statute text is relied on for this value. Same limit for every filing
    # status and number of children.
    # Source wording: FTB eligibility page requirements list "earned income of at
    # least $1 and not more than" the figure ("up to" on the overview page);
    # 3514 instructions: "must be less than" the next whole dollar (exclusive
    # bound, minus $1). Inclusive wording used as stated.
    "caleitc_max_earned_income": 32900,
}

PENDING_TRANSCRIPTION: dict[str, str] = {
}
