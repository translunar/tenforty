# tenforty/params/california/y2025.py
"""FTB-published 2025 California parameters.

Migrated verbatim from tenforty/constants/california_y2025.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2025), pdfs/california/2025/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 multipliers at $153
  per person; side 2 line 10 at $475 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2025/tax_rate_schedules.pdf
  (Schedules X / Y / Z; Schedule Z is FTB-published independently and
  does NOT equal Schedule X × 2 — e.g. HoH first non-zero threshold
  $22,173 vs SINGLE×2 = $22,158).
- Renter's credit: FTB 2025 540-2EZ Booklet p.13 Q2/Q11 (the regular
  TY2025 540 booklet was unpublished at extraction time; the credit is
  form-agnostic per FTB §17053.5 — re-source when the booklet lands).
"""
from tenforty.models import FilingStatus
from tenforty.params.california import CaliforniaParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

_SCHEDULE_X = (  # Single / MFS
    (0, 0.01), (11_079, 0.02), (26_264, 0.04), (41_452, 0.06),
    (57_542, 0.08), (72_724, 0.093), (371_479, 0.103),
    (445_771, 0.113), (742_953, 0.123),
)
_SCHEDULE_Y = (  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01), (22_158, 0.02), (52_528, 0.04), (82_904, 0.06),
    (115_084, 0.08), (145_448, 0.093), (742_958, 0.103),
    (891_542, 0.113), (1_485_906, 0.123),
)
_SCHEDULE_Z = (  # HoH — FTB-published independently; ≠ X × 2
    (0, 0.01), (22_173, 0.02), (52_530, 0.04), (67_716, 0.06),
    (83_805, 0.08), (98_990, 0.093), (505_208, 0.103),
    (606_251, 0.113), (1_010_417, 0.123),
)

PARAMS = CaliforniaParams(
    year=2025,
    standard_deduction={
        _S: 5_706, _MFS: 5_706, _MFJ: 11_412, _HOH: 11_412, _QW: 11_412,
    },
    exemption_credit={
        _S: 153, _MFS: 153, _HOH: 153, _MFJ: 306, _QW: 306,
    },
    dependent_exemption_amount=475,
    agi_phaseout_threshold=252_203,
    rate_schedule={
        _S: _SCHEDULE_X, _MFS: _SCHEDULE_X,
        _MFJ: _SCHEDULE_Y, _QW: _SCHEDULE_Y,
        _HOH: _SCHEDULE_Z,
    },
    renter_credit_agi_threshold={
        _S: 53_994, _MFS: 53_994,
        _MFJ: 107_988, _HOH: 107_988, _QW: 107_988,
    },
    renter_credit_amount={
        _S: 60, _MFS: 60, _MFJ: 120, _HOH: 120, _QW: 120,
    },
)
