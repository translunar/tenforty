"""Air-gapped attestation of CALIFORNIA params, tax year 2024.

Independently transcribed from official FTB publications ONLY (on-disk FTB
PDFs) — see SOURCES. Transcribed with no reference to tenforty's own params,
tests, or any derived tax table; the rate schedule is taken from the primary
2024 California Tax Rate Schedules, not from the binned tax table.
"""

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
        "married_jointly": 11080,      # Chart line 2 – Married/RDP filing jointly
        "married_separately": 5540,    # Chart line 3 – Married/RDP filing separately
        "head_of_household": 11080,    # Chart line 4 – Head of household
        "qualifying_widow": 11080,     # Chart line 5 – Qualifying surviving spouse/RDP
    },

    # Personal exemption credit. Form 540 line 7: $149 per exemption; filing
    # statuses 1/3/4 (single, MFS, HOH) claim 1 ($149); statuses 2/5 (MFJ,
    # QSS) claim 2 ($298).
    "exemption_credit": {
        "single": 149,                 # f540 line 7: 1 x $149
        "married_jointly": 298,        # f540 line 7: 2 x $149
        "married_separately": 149,     # f540 line 7: 1 x $149
        "head_of_household": 149,      # f540 line 7: 1 x $149
        "qualifying_widow": 298,       # f540 line 7: 2 x $149
    },

    "dependent_exemption_amount": 461,  # f540 line 10: X $461 per dependent

    # Schema field is a single int. Form 540 line 32 prints $244,857 as the
    # federal-AGI gate (the Single / MFS threshold). Booklet Line 32
    # instructions list status-specific thresholds: Single/MFS $244,857,
    # MFJ/QSS $489,719, HOH $367,291 — see report concern about the scalar.
    "agi_phaseout_threshold": 244857,   # f540 line 32; booklet p. 12 Line 32

    # 2024 California Tax Rate Schedules (tax_rate_schedules.pdf).
    "rate_schedule": {
        # Schedule X – Single or Married/RDP filing separately
        "single": (
            (0, 0.01), (10756, 0.02), (25499, 0.04), (40245, 0.06),
            (55866, 0.08), (70606, 0.093), (360659, 0.103), (432787, 0.113),
            (721314, 0.123),
        ),  # tax_rate_schedules.pdf Schedule X
        # Schedule Y – Married/RDP filing jointly or Qualifying surviving spouse/RDP
        "married_jointly": (
            (0, 0.01), (21512, 0.02), (50998, 0.04), (80490, 0.06),
            (111732, 0.08), (141212, 0.093), (721318, 0.103), (865574, 0.113),
            (1442628, 0.123),
        ),  # tax_rate_schedules.pdf Schedule Y
        # Schedule X – shared by MFS
        "married_separately": (
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
        "married_jointly": 104842,     # "MFJ, HOH, or QSS"
        "married_separately": 52421,   # "single or married/RDP filing separately"
        "head_of_household": 104842,   # "MFJ, HOH, or QSS"
        "qualifying_widow": 104842,    # "MFJ, HOH, or QSS"
    },

    # Renter's credit amount entered on Form 540 line 46 (booklet p. 26, q.11).
    "renter_credit_amount": {
        "single": 60,                  # "Single, enter $60"
        "married_jointly": 120,        # "Married/RDP filing jointly, enter $120"
        "married_separately": 60,      # "MFS ... may claim half the amount ($60)"
        "head_of_household": 120,      # "Head of household ... enter $120"
        "qualifying_widow": 120,       # "qualifying surviving spouse/RDP ... $120"
    },
}
