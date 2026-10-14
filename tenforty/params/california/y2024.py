# tenforty/params/california/y2024.py
"""FTB-published 2024 California parameters.

Migrated verbatim from tenforty/constants/california_y2024.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2024), pdfs/california/2024/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 per-person multipliers
  (amounts: see exemption_credit provenance); side 2 line 10 at $461 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2024/tax_rate_schedules.pdf (2024
  California Tax Rate Schedules, Personal Income Tax Booklet 2024 page
  75); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $21,527 vs
  SINGLE×2 = $21,512, a $15 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2024),
  pdfs/california/2024/booklet.pdf p.25, "Nonrefundable Renter's Credit
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
    (0, 0.01), (10_756, 0.02), (25_499, 0.04), (40_245, 0.06),
    (55_866, 0.08), (70_606, 0.093), (360_659, 0.103),
    (432_787, 0.113), (721_314, 0.123),
)
_SCHEDULE_Y = (  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01), (21_512, 0.02), (50_998, 0.04), (80_490, 0.06),
    (111_732, 0.08), (141_212, 0.093), (721_318, 0.103),
    (865_574, 0.113), (1_442_628, 0.123),
)
_SCHEDULE_Z = (  # HoH — FTB-published independently; ≠ X × 2
    (0, 0.01), (21_527, 0.02), (51_000, 0.04), (65_744, 0.06),
    (81_364, 0.08), (96_107, 0.093), (490_493, 0.103),
    (588_593, 0.113), (980_987, 0.123),
)

PARAMS = CaliforniaParams(
    year=2024,
    standard_deduction={
        _S: 5_540, _MFS: 5_540, _MFJ: 11_080, _HOH: 11_080, _QW: 11_080,
    },
    exemption_credit={
        _S: 149, _MFS: 149, _HOH: 149, _MFJ: 298, _QW: 298,
    },
    dependent_exemption_amount=461,
    # 2024 Personal Income Tax Booklet (Form 540), Line 32 – Exemption
    # Credits table, p.14.
    # https://www.ftb.ca.gov/forms/2024/2024-540-booklet.pdf
    # REV stamp: none printed on Line 32 page; no REV stamp anywhere.
    # sha256 446372719f6e1ce90132d550c268d7804fc44cefcf13514e09bf9ac9907ee374
    agi_phaseout_threshold={
        _S: 244_857,
        _MFJ: 489_719,
        _MFS: 244_857,
        _HOH: 367_291,
        _QW: 489_719,
    },
    rate_schedule={
        _S: _SCHEDULE_X, _MFS: _SCHEDULE_X,
        _MFJ: _SCHEDULE_Y, _QW: _SCHEDULE_Y,
        _HOH: _SCHEDULE_Z,
    },
    renter_credit_agi_threshold={
        _S: 52_421, _MFS: 52_421,
        _MFJ: 104_842, _HOH: 104_842, _QW: 104_842,
    },
    renter_credit_amount={
        _S: 60, _MFS: 60, _MFJ: 120, _HOH: 120, _QW: 120,
    },
    # 2024 Personal Income Tax Booklet (Form 540).
    # https://www.ftb.ca.gov/forms/2024/2024-540-booklet.pdf
    # sha256 446372719f6e1ce90132d550c268d7804fc44cefcf13514e09bf9ac9907ee374
    # REV stamp: none printed on the senior-exemption pages (instructions p.12, form
    # side 1); none anywhere.
    # senior_exemption_credit: Form 540 side 1 (booklet PDF page 39),
    # line 9 "X $" box; box assigned by rendered-page position (same row as the line 9
    # label; text layer detaches the boxes from their labels).
    # The Line 9 instructions (p.12) print no amount.
    # senior_born_before: no born-before date printed; condition recorded
    # verbatim below, date left for adjudication.
    # Line 9 – Senior Exemptions (instructions p.12), verbatim:
    # If you were 65 years of age or older by December 31, 2024*, you should
    # claim an additional exemption credit on line 9. If you are married/or
    # an RDP, each spouse/RDP 65 years of age or older should claim an
    # additional credit.
    # *If your 65th birthday is on January 1, 2025, you are considered to be
    # age 65 on December 31, 2024.
    # form-page label:
    # 9 Senior: If you (or your spouse/RDP) are 65 or older, enter 1;
    # if both are 65 or older, enter 2. See instructions.
    # Excluded: the Voluntary Contribution Fund Descriptions (code 400) also
    # restate an age condition; that is a different provision, not a source.
    senior_exemption_credit=149,
    senior_born_before=None,
)
