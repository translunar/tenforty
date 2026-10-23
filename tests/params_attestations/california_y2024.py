"""Air-gapped attestation of CALIFORNIA params, tax year 2024.

Independently transcribed from official FTB publications ONLY (on-disk FTB
PDFs) — see SOURCES. Transcribed with no reference to tenforty's own params,
tests, or any derived tax table; the rate schedule is taken from the primary
2024 California Tax Rate Schedules, not from the binned tax table.
"""

import datetime

SOURCES: tuple[str, ...] = (
    "FTB 2024 Personal Income Tax Booklet (pdfs/california/2024/booklet.pdf), "
    "p. 12 (California Standard Deduction Chart for Most People)",
    "FTB 2024 Form 540 (pdfs/california/2024/f540.pdf), Side 1 lines 7 & 10 "
    "(personal exemption credit $149/exemption; dependent exemption $461), "
    "line 32 (exemption-credit AGI phaseout threshold printed as $244,857)",
    "FTB 2024 Personal Income Tax Booklet, p. 12 Line 32 instructions "
    "(exemption-credit phaseout thresholds by filing status)",
    "FTB 2024 California Tax Rate Schedules "
    "(pdfs/california/2024/tax_rate_schedules.pdf), Schedules X, Y, Z",
    "FTB 2024 Personal Income Tax Booklet, pp. 25-26 (Nonrefundable Renter's "
    "Credit Qualification Record: AGI limits and credit amounts)",
    "FTB CalEITC 'Eligibility and credit information' page "
    "(https://www.ftb.ca.gov/file/personal/credits/caleitc/eligibility-and-credit-information.html, "
    "retrieved via curl, last updated 04/16/2026), '2024 CalEITC credit' table, "
    "column 'CalEITC, YCTC, FYTC max income' (caleitc_max_earned_income); and FTB 2024 "
    "FTB 3514 booklet (https://www.ftb.ca.gov/forms/2024/2024-3514-booklet.html), "
    "'B. Differences in California and Federal Law' / Step 1 (exclusive-bound wording "
    "cross-check) and Earned Income Tax Credit Table last bracket.",
)

# rate_schedule canonical shape (per schema docstring +
# forms.f540._walk_rate_schedule): each status maps to an ASCENDING tuple of
# (threshold_low_inclusive, marginal_rate_at_or_above_that_threshold) pairs.
# The bracket starting at threshold[i] runs until threshold[i+1] (exclusive);
# the top bracket has no upper bound and there is NO math.inf terminator entry.
# Thresholds are the "over –" (lower-bound) column of the FTB Tax Rate Schedules.
ATTESTED: dict[str, object] = {
    "year": 2024,

    # California Standard Deduction Chart for Most People (booklet p. 12).
    "standard_deduction": {
        "single": 5540,               # Chart line 1 – Single
        "married_filing_jointly": 11080,      # Chart line 2 – Married/RDP filing jointly
        "married_filing_separately": 5540,    # Chart line 3 – Married/RDP filing separately
        "head_of_household": 11080,    # Chart line 4 – Head of household
        "qualifying_widow": 11080,     # Chart line 5 – Qualifying surviving spouse/RDP
    },

    # Personal exemption credit. Form 540 line 7: $149 per exemption; filing
    # statuses 1/3/4 (single, MFS, HOH) claim 1 ($149); statuses 2/5 (MFJ,
    # QSS) claim 2 ($298).
    "exemption_credit": {
        "single": 149,                 # f540 line 7: 1 x $149
        "married_filing_jointly": 298,        # f540 line 7: 2 x $149
        "married_filing_separately": 149,     # f540 line 7: 1 x $149
        "head_of_household": 149,      # f540 line 7: 1 x $149
        "qualifying_widow": 298,       # f540 line 7: 2 x $149
    },

    "dependent_exemption_amount": 461,  # f540 line 10: X $461 per dependent

    # Per-status columns attested 2026-10-14 (Transcriber B paste; dual
    # transcription adjudicated vs Transcriber A with full agreement; the
    # prior transcription's prose figures here agreed as well).
    # Source: Line 32 table, booklet p.14; REV: none printed anywhere;
    # sha256 446372719f6e1ce90132d550c268d7804fc44cefcf13514e09bf9ac9907ee374
    "agi_phaseout_threshold": {
        "single": 244857,
        "married_filing_separately": 244857,
        "married_filing_jointly": 489719,
        "qualifying_widow": 489719,
        "head_of_household": 367291,
    },

    # 2024 California Tax Rate Schedules (tax_rate_schedules.pdf).
    "rate_schedule": {
        # Schedule X – Single or Married/RDP filing separately
        "single": (
            (0, 0.01), (10756, 0.02), (25499, 0.04), (40245, 0.06),
            (55866, 0.08), (70606, 0.093), (360659, 0.103), (432787, 0.113),
            (721314, 0.123),
        ),  # tax_rate_schedules.pdf Schedule X
        # Schedule Y – Married/RDP filing jointly or Qualifying surviving spouse/RDP
        "married_filing_jointly": (
            (0, 0.01), (21512, 0.02), (50998, 0.04), (80490, 0.06),
            (111732, 0.08), (141212, 0.093), (721318, 0.103), (865574, 0.113),
            (1442628, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Y
        # Schedule X – shared by MFS
        "married_filing_separately": (
            (0, 0.01), (10756, 0.02), (25499, 0.04), (40245, 0.06),
            (55866, 0.08), (70606, 0.093), (360659, 0.103), (432787, 0.113),
            (721314, 0.123),
        ),  # tax_rate_schedules.pdf Schedule X
        # Schedule Z – Head of household
        "head_of_household": (
            (0, 0.01), (21527, 0.02), (51000, 0.04), (65744, 0.06),
            (81364, 0.08), (96107, 0.093), (490493, 0.103), (588593, 0.113),
            (980987, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Z
        # Schedule Y – shared by QSS
        "qualifying_widow": (
            (0, 0.01), (21512, 0.02), (50998, 0.04), (80490, 0.06),
            (111732, 0.08), (141212, 0.093), (721318, 0.103), (865574, 0.113),
            (1442628, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Y
    },

    # Nonrefundable Renter's Credit Qualification Record (booklet p. 25, q.2):
    # AGI (Form 540 line 17) at or below these limits.
    "renter_credit_agi_threshold": {
        "single": 52421,               # "single or married/RDP filing separately"
        "married_filing_jointly": 104842,     # "MFJ, HOH, or QSS"
        "married_filing_separately": 52421,   # "single or married/RDP filing separately"
        "head_of_household": 104842,   # "MFJ, HOH, or QSS"
        "qualifying_widow": 104842,    # "MFJ, HOH, or QSS"
    },

    # Renter's credit amount entered on Form 540 line 46 (booklet p. 26, q.11).
    "renter_credit_amount": {
        "single": 60,                  # "Single, enter $60"
        "married_filing_jointly": 120,        # "Married/RDP filing jointly, enter $120"
        "married_filing_separately": 60,      # "MFS ... may claim half the amount ($60)"
        "head_of_household": 120,      # "Head of household ... enter $120"
        "qualifying_widow": 120,       # "qualifying surviving spouse/RDP ... $120"
    },
    # Attested 2026-10-14 (Transcriber B paste; dual transcription adjudicated
    # vs Transcriber A with full agreement incl. a third reading of the
    # amount). Amount: Form 540 line 9 "x $" box (box assigned by
    # rendered-page position). Date: team-lead words-to-date ruling from the
    # verbatim Line 9 wording + footnote (both transcribers deferred, as the
    # booklet prints no born-before date): exclusive cutoff January 2, 1960.
    "senior_exemption_credit": 149,
    "senior_born_before": datetime.date(1960, 1, 2),
    # Form 540 line 31 tax-table / rate-schedule boundary. Attested
    # 2026-10-17 by an air-gapped transcriber (never read tenforty source)
    # from the pinned FTB 2024 540 booklet pdfs/california/2024/booklet.pdf,
    # sha256 446372719f6e1ce90132d550c268d7804fc44cefcf13514e09bf9ac9907ee374.
    # Booklet p.13, "Line 31 – Tax": "Tax Table – If your taxable income on
    # line 19 is $100,000 or less, use the tax table beginning on page 69.
    # ... Tax Rate Schedules – If your taxable income on line 19 is over
    # $100,000, use the tax rate schedule for your filing status on page 75."
    # Restated on p.75 ("2024 California Tax Rate Schedules"): "Use only if
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
    # Source wording: FTB eligibility page 2024 table, column "CalEITC, YCTC, FYTC
    # max income" for all child counts; 3514 instructions: earned income and
    # federal AGI "must be less than" the next whole dollar (exclusive bound, so
    # maximum qualifying amount is that bound minus $1). Value attested =
    # published maximum.
    "caleitc_max_earned_income": 31950,
}

PENDING_TRANSCRIPTION: dict[str, str] = {
}
