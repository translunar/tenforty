# tenforty/params/california/y2022.py
"""FTB-published 2022 California parameters.

Migrated verbatim from tenforty/constants/california_y2022.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2022), pdfs/california/2022/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 multipliers at $140
  per person; side 2 line 10 at $433 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2022/tax_rate_schedules.pdf (2022
  California Tax Rate Schedules, Personal Income Tax Booklet 2022 page
  93); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $20,212 vs
  SINGLE×2 = $20,198, a $14 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2022),
  pdfs/california/2022/booklet.pdf p.23, "Nonrefundable Renter's Credit
  Qualification Record" Q2 (AGI threshold) and Q11 (amount).
"""
from tenforty.models import FilingStatus
from tenforty.params.california import CaliforniaParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
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
    agi_phaseout_threshold=229_908,
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
)
