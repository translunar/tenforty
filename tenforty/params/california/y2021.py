# tenforty/params/california/y2021.py
"""FTB-published 2021 California parameters.

Migrated verbatim from tenforty/constants/california_y2021.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2021), pdfs/california/2021/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 multipliers at $129
  per person; side 2 line 10 at $400 each; side 2 line 32 threshold).
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
from tenforty.models import FilingStatus
from tenforty.params.california import CaliforniaParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
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
    agi_phaseout_threshold=212_288,
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
)
