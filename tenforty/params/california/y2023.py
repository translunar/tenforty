# tenforty/params/california/y2023.py
"""FTB-published 2023 California parameters.

Migrated verbatim from tenforty/constants/california_y2023.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2023), pdfs/california/2023/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 multipliers at $144
  per person; side 2 line 10 at $446 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2023/tax_rate_schedules.pdf (2023
  California Tax Rate Schedules, Personal Income Tax Booklet 2023 page
  75); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $20,839 vs
  SINGLE×2 = $20,824, a $15 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2023),
  pdfs/california/2023/booklet.pdf p.25, "Nonrefundable Renter's Credit
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
    agi_phaseout_threshold=237_035,
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
)
