# tenforty/params/california/y2023.py
"""FTB-published 2023 California parameters.

Migrated verbatim from tenforty/constants/california_y2023.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2023), pdfs/california/2023/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 per-person multipliers
  (amounts: see exemption_credit provenance); side 2 line 10 at $446 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2023/tax_rate_schedules.pdf (2023
  California Tax Rate Schedules, Personal Income Tax Booklet 2023 page
  75); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $20,839 vs
  SINGLE×2 = $20,824, a $15 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2023),
  pdfs/california/2023/booklet.pdf p.25, "Nonrefundable Renter's Credit
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
    (0, 0.01), (10_412, 0.02), (24_684, 0.04), (38_959, 0.06),
    (54_081, 0.08), (68_350, 0.093), (349_137, 0.103),
    (418_961, 0.113), (698_271, 0.123),
)
_SCHEDULE_Y = (  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01), (20_824, 0.02), (49_368, 0.04), (77_918, 0.06),
    (108_162, 0.08), (136_700, 0.093), (698_274, 0.103),
    (837_922, 0.113), (1_396_542, 0.123),
)
_SCHEDULE_Z = (  # HoH — FTB-published independently; ≠ X × 2
    (0, 0.01), (20_839, 0.02), (49_371, 0.04), (63_644, 0.06),
    (78_765, 0.08), (93_037, 0.093), (474_824, 0.103),
    (569_790, 0.113), (949_649, 0.123),
)

PARAMS = CaliforniaParams(
    year=2023,
    standard_deduction={
        _S: 5_363, _MFS: 5_363, _MFJ: 10_726, _HOH: 10_726, _QW: 10_726,
    },
    exemption_credit={
        _S: 144, _MFS: 144, _HOH: 144, _MFJ: 288, _QW: 288,
    },
    dependent_exemption_amount=446,
    # 2023 Personal Income Tax Booklet (Form 540), Line 32 – Exemption
    # Credits table, p.14.
    # https://www.ftb.ca.gov/forms/2023/2023-540-booklet.pdf
    # REV stamp: none printed on Line 32 page; no REV stamp anywhere.
    # sha256 e2d8ef0ba279abf65eec7941a77de6604af9186226e1e79cc80a8ecd2a14d4b9
    agi_phaseout_threshold={
        _S: 237_035,
        _MFJ: 474_075,
        _MFS: 237_035,
        _HOH: 355_558,
        _QW: 474_075,
    },
    rate_schedule={
        _S: _SCHEDULE_X, _MFS: _SCHEDULE_X,
        _MFJ: _SCHEDULE_Y, _QW: _SCHEDULE_Y,
        _HOH: _SCHEDULE_Z,
    },
    renter_credit_agi_threshold={
        _S: 50_746, _MFS: 50_746,
        _MFJ: 101_492, _HOH: 101_492, _QW: 101_492,
    },
    renter_credit_amount={
        _S: 60, _MFS: 60, _MFJ: 120, _HOH: 120, _QW: 120,
    },
    # 2023 Personal Income Tax Booklet (Form 540).
    # https://www.ftb.ca.gov/forms/2023/2023-540-booklet.pdf
    # sha256 e2d8ef0ba279abf65eec7941a77de6604af9186226e1e79cc80a8ecd2a14d4b9
    # REV stamp: none printed on the senior-exemption pages (instructions p.12, form
    # side 1); none anywhere.
    # senior_exemption_credit: Form 540 side 1 (booklet PDF page 39),
    # line 9 "X $" box; box on the same text-layer line as the line 9 label; confirmed
    # by rendered-page position.
    # The Line 9 instructions (p.12) print no amount.
    # senior_born_before: no born-before date printed; condition recorded
    # verbatim below, date left for adjudication.
    # Line 9 – Senior Exemptions (instructions p.12), verbatim:
    # If you were 65 years of age or older by December 31, 2023*, you should
    # claim an additional exemption credit on line 9. If you are married/or
    # an RDP, each spouse/RDP 65 years of age or older should claim an
    # additional credit.
    # *If your 65th birthday is on January 1, 2024, you are considered to be
    # age 65 on December 31, 2023.
    # form-page label:
    # 9 Senior: If you (or your spouse/RDP) are 65 or older, enter 1;
    # if both are 65 or older, enter 2. See instructions.
    # Excluded: the Voluntary Contribution Fund Descriptions (code 400) also
    # restate an age condition; that is a different provision, not a source.
    senior_exemption_credit=144,
    # senior_born_before RULED by team-lead 2026-10-14 (words-to-date
    # adjudication per plan: both transcribers deferred): the booklet's
    # "65 years of age or older by December 31, 2023" plus its footnote
    # (65th birthday on January 1, 2024 counts as 65 on December 31,
    # 2023) means born on or before January 1, 1959 -- exclusive
    # born-before cutoff January 2, 1959. Verbatim wording above.
    senior_born_before=datetime.date(1959, 1, 2),
    # Form 540 line 31: FTB 2023 booklet p.13, "Line 31 - Tax": "Tax Table -
    # If your taxable income on line 19 is $100,000 or less, use the tax
    # table beginning on page 69. ... Tax Rate Schedules - If your taxable
    # income on line 19 is over $100,000, use the tax rate schedule"
    # (restated p.75). Inclusive: line 19 <= ceiling uses the table.
    tax_table_taxable_income_ceiling=100_000,
    # CalEITC (FTB 3514 instructions, 2023):
    # "... must be less than $30,951 to qualify for the California
    # credit."
    # https://www.ftb.ca.gov/forms/2023/2023-3514-booklet.pdf
    # sha256 a7a591e82fb3201506c2e45c0631378154fa9c8852644f7ce030ba644e6dd8b1
    # Inclusive maximum = that bound less $1.
    # Conflict (R-S8-13): the same booklet says the credit "completely
    # phases out at $30,932"; the eligibility wording governs.
    caleitc_max_earned_income=30_950,
)
