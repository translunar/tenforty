# tenforty/params/california/y2022.py
"""FTB-published 2022 California parameters.

Migrated verbatim from tenforty/constants/california_y2022.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2022), pdfs/california/2022/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 per-person multipliers
  (amounts: see exemption_credit provenance); side 2 line 10 at $433 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2022/tax_rate_schedules.pdf (2022
  California Tax Rate Schedules, Personal Income Tax Booklet 2022 page
  93); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $20,212 vs
  SINGLE×2 = $20,198, a $14 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2022),
  pdfs/california/2022/booklet.pdf p.23, "Nonrefundable Renter's Credit
  Qualification Record" Q2 (AGI threshold) and Q11 (amount).
"""
import datetime

from tenforty.models import FilingStatus
from tenforty.params.california import CaliforniaParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY.value
_MFS = FilingStatus.MARRIED_FILING_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

_SCHEDULE_X = (  # Single / MFS
    (0, 0.01), (10_099, 0.02), (23_942, 0.04), (37_788, 0.06),
    (52_455, 0.08), (66_295, 0.093), (338_639, 0.103),
    (406_364, 0.113), (677_275, 0.123),
)
_SCHEDULE_Y = (  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01), (20_198, 0.02), (47_884, 0.04), (75_576, 0.06),
    (104_910, 0.08), (132_590, 0.093), (677_278, 0.103),
    (812_728, 0.113), (1_354_550, 0.123),
)
_SCHEDULE_Z = (  # HoH — FTB-published independently; ≠ X × 2
    (0, 0.01), (20_212, 0.02), (47_887, 0.04), (61_730, 0.06),
    (76_397, 0.08), (90_240, 0.093), (460_547, 0.103),
    (552_658, 0.113), (921_095, 0.123),
)

PARAMS = CaliforniaParams(
    year=2022,
    standard_deduction={
        _S: 5_202, _MFS: 5_202, _MFJ: 10_404, _HOH: 10_404, _QW: 10_404,
    },
    exemption_credit={
        _S: 140, _MFS: 140, _HOH: 140, _MFJ: 280, _QW: 280,
    },
    dependent_exemption_amount=433,
    # 2022 Personal Income Tax Booklet (Form 540), Line 32 – Exemption
    # Credits table, p.14.
    # https://www.ftb.ca.gov/forms/2022/2022-540-booklet.pdf
    # REV stamp: none printed on Line 32 page; elsewhere: REV 02-23,
    # REV 06-23.
    # sha256 e7ae8a0a8e4dadf973cdb702b8f9deb1574969d0cda5c6e08882e42e966c804c
    agi_phaseout_threshold={
        _S: 229_908,
        _MFJ: 459_821,
        _MFS: 229_908,
        _HOH: 344_867,
        _QW: 459_821,
    },
    rate_schedule={
        _S: _SCHEDULE_X, _MFS: _SCHEDULE_X,
        _MFJ: _SCHEDULE_Y, _QW: _SCHEDULE_Y,
        _HOH: _SCHEDULE_Z,
    },
    renter_credit_agi_threshold={
        _S: 49_220, _MFS: 49_220,
        _MFJ: 98_440, _HOH: 98_440, _QW: 98_440,
    },
    renter_credit_amount={
        _S: 60, _MFS: 60, _MFJ: 120, _HOH: 120, _QW: 120,
    },
    # 2022 Personal Income Tax Booklet (Form 540).
    # https://www.ftb.ca.gov/forms/2022/2022-540-booklet.pdf
    # sha256 e7ae8a0a8e4dadf973cdb702b8f9deb1574969d0cda5c6e08882e42e966c804c
    # REV stamp: none printed on the senior-exemption pages (instructions p.12, form
    # side 1); elsewhere: REV 02-23, REV 06-23.
    # senior_exemption_credit: Form 540 side 1 (booklet PDF page 33),
    # line 9 "X $" box; box on the same text-layer line as the line 9 label; confirmed
    # by rendered-page position.
    # The Line 9 instructions (p.12) print no amount.
    # senior_born_before: no born-before date printed; condition recorded
    # verbatim below, date left for adjudication.
    # Line 9 – Senior Exemptions (instructions p.12), verbatim:
    # If you were 65 years of age or older by December 31, 2022*, you should
    # claim an additional exemption credit on line 9. If you are married/or
    # an RDP, each spouse/RDP 65 years of age or older should claim an
    # additional credit.
    # *If your 65th birthday is on January 1, 2023, you are considered to be
    # age 65 on December 31, 2022.
    # form-page label:
    # 9 Senior: If you (or your spouse/RDP) are 65 or older, enter 1;
    # if both are 65 or older, enter 2. See instructions.
    # Excluded: the Voluntary Contribution Fund Descriptions (code 400) also
    # restate an age condition; that is a different provision, not a source.
    senior_exemption_credit=140,
    # senior_born_before RULED by team-lead 2026-10-14 (words-to-date
    # adjudication per plan: both transcribers deferred): the booklet's
    # "65 years of age or older by December 31, 2022" plus its footnote
    # (65th birthday on January 1, 2023 counts as 65 on December 31,
    # 2022) means born on or before January 1, 1958 -- exclusive
    # born-before cutoff January 2, 1958. Verbatim wording above.
    senior_born_before=datetime.date(1958, 1, 2),
    # Form 540 line 31: FTB 2022 booklet p.13, "Line 31 - Tax": "Tax Table -
    # If your taxable income on line 19 is $100,000 or less, use the tax
    # table beginning on page 87. ... Tax Rate Schedules - If your taxable
    # income on line 19 is over $100,000, use the tax rate schedule"
    # (restated p.93). Inclusive: line 19 <= ceiling uses the table.
    tax_table_taxable_income_ceiling=100_000,
    # CalEITC (FTB 3514 instructions, 2022):
    # "Both your earned income and federal adjusted gross income (AGI)
    # must be less than $30,001 to qualify for the California credit."
    # https://www.ftb.ca.gov/forms/2022/2022-3514-instructions.html
    # Inclusive maximum = that bound less $1.
    caleitc_max_earned_income=30_000,
)
