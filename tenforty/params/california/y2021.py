# tenforty/params/california/y2021.py
"""FTB-published 2021 California parameters.

Migrated verbatim from tenforty/constants/california_y2021.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2021), pdfs/california/2021/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 per-person multipliers
  (amounts: see exemption_credit provenance); side 2 line 10 at $400 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2021/tax_rate_schedules.pdf (2021
  California Tax Rate Schedules, Personal Income Tax Booklet 2021 page
  93); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $18,663 vs
  SINGLE×2 = $18,650, a $13 quirk. Note: TY2021 FTB form still used the
  older "Qualifying Widow(er)" terminology; tenforty maps QSS to
  QUALIFYING_WIDOW.
- Renter's credit: FTB Personal Income Tax Booklet (TY2021),
  pdfs/california/2021/booklet.pdf p.23, "Nonrefundable Renter's Credit
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
    (0, 0.01), (9_325, 0.02), (22_107, 0.04), (34_892, 0.06),
    (48_435, 0.08), (61_214, 0.093), (312_686, 0.103),
    (375_221, 0.113), (625_369, 0.123),
)
_SCHEDULE_Y = (  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01), (18_650, 0.02), (44_214, 0.04), (69_784, 0.06),
    (96_870, 0.08), (122_428, 0.093), (625_372, 0.103),
    (750_442, 0.113), (1_250_738, 0.123),
)
_SCHEDULE_Z = (  # HoH — FTB-published independently; ≠ X × 2
    (0, 0.01), (18_663, 0.02), (44_217, 0.04), (56_999, 0.06),
    (70_542, 0.08), (83_324, 0.093), (425_251, 0.103),
    (510_303, 0.113), (850_503, 0.123),
)

PARAMS = CaliforniaParams(
    year=2021,
    standard_deduction={
        _S: 4_803, _MFS: 4_803, _MFJ: 9_606, _HOH: 9_606, _QW: 9_606,
    },
    exemption_credit={
        _S: 129, _MFS: 129, _HOH: 129, _MFJ: 258, _QW: 258,
    },
    dependent_exemption_amount=400,
    # 2021 Personal Income Tax Booklet (Form 540), Line 32 – Exemption
    # Credits table, p.14.
    # https://www.ftb.ca.gov/forms/2021/2021-540-booklet.pdf
    # REV stamp: none printed on Line 32 page; elsewhere: REV 02-22,
    # REV 02-23, REV 05-23, REV 07-22.
    # sha256 88d1d720f72013beb9e6f6928a86fe783d143f760a455485a34bfe6424f52072
    agi_phaseout_threshold={
        _S: 212_288,
        _MFJ: 424_581,
        _MFS: 212_288,
        _HOH: 318_437,
        _QW: 424_581,
    },
    rate_schedule={
        _S: _SCHEDULE_X, _MFS: _SCHEDULE_X,
        _MFJ: _SCHEDULE_Y, _QW: _SCHEDULE_Y,
        _HOH: _SCHEDULE_Z,
    },
    renter_credit_agi_threshold={
        _S: 45_448, _MFS: 45_448,
        _MFJ: 90_896, _HOH: 90_896, _QW: 90_896,
    },
    renter_credit_amount={
        _S: 60, _MFS: 60, _MFJ: 120, _HOH: 120, _QW: 120,
    },
    # 2021 Personal Income Tax Booklet (Form 540).
    # https://www.ftb.ca.gov/forms/2021/2021-540-booklet.pdf
    # sha256 88d1d720f72013beb9e6f6928a86fe783d143f760a455485a34bfe6424f52072
    # REV stamp: none printed on the senior-exemption pages (instructions p.12, form
    # side 1); elsewhere: REV 02-22, REV 02-23, REV 05-23, REV 07-22.
    # senior_exemption_credit: Form 540 side 1 (booklet PDF page 31),
    # line 9 "X $" box; box on the same text-layer line as the line 9 label; confirmed
    # by rendered-page position.
    # The Line 9 instructions (p.12) print no amount.
    # senior_born_before: no born-before date printed; condition recorded
    # verbatim below, date left for adjudication.
    # Line 9 – Senior Exemptions (instructions p.12), verbatim:
    # If you were 65 years of age or older by December 31, 2021*, you should
    # claim an additional exemption credit on line 9. If you are married/or
    # an RDP, each spouse/RDP 65 years of age or older should claim an
    # additional credit.
    # *If your 65th birthday is on January 1, 2022, you are considered to be
    # age 65 on December 31, 2021.
    # form-page label:
    # 9 Senior: If you (or your spouse/RDP) are 65 or older, enter 1;
    # if both are 65 or older, enter 2. See instructions.
    # Excluded: the Voluntary Contribution Fund Descriptions (code 400) also
    # restate an age condition; that is a different provision, not a source.
    senior_exemption_credit=129,
    # senior_born_before RULED by team-lead 2026-10-14 (words-to-date
    # adjudication per plan: both transcribers deferred): the booklet's
    # "65 years of age or older by December 31, 2021" plus its footnote
    # (65th birthday on January 1, 2022 counts as 65 on December 31,
    # 2021) means born on or before January 1, 1957 — exclusive
    # born-before cutoff January 2, 1957. Verbatim wording above.
    senior_born_before=datetime.date(1957, 1, 2),
    # Form 540 line 31: FTB 2021 booklet p.13, "Line 31 - Tax": "Tax Table -
    # If your taxable income on line 19 is $100,000 or less, use the tax
    # table beginning on page 87. ... Tax Rate Schedules - If your taxable
    # income on line 19 is over $100,000, use the tax rate schedule"
    # (restated p.93). Inclusive: line 19 <= ceiling uses the table.
    tax_table_taxable_income_ceiling=100_000,
)
