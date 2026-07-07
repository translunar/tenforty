# tenforty/params/california/y2024.py
"""FTB-published 2024 California parameters.

Migrated verbatim from tenforty/constants/california_y2024.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2024), pdfs/california/2024/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 multipliers at $149
  per person; side 2 line 10 at $461 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2024/tax_rate_schedules.pdf (2024
  California Tax Rate Schedules, Personal Income Tax Booklet 2024 page
  75); Schedule Z is FTB-published independently and does NOT equal
  Schedule X × 2 — e.g. HoH first non-zero threshold $21,527 vs
  SINGLE×2 = $21,512, a $15 quirk.
- Renter's credit: FTB Personal Income Tax Booklet (TY2024),
  pdfs/california/2024/booklet.pdf p.25, "Nonrefundable Renter's Credit
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
    agi_phaseout_threshold=244_857,
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
)
