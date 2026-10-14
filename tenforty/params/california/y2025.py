# tenforty/params/california/y2025.py
"""FTB-published 2025 California parameters.

Migrated verbatim from tenforty/constants/california_y2025.py. Sources:
- STANDARD_DEDUCTION / EXEMPTION_CREDIT / DEPENDENT_EXEMPTION / AGI
  phaseout: FTB Form 540 (TY2025), pdfs/california/2025/f540.pdf
  (side 2 line 18 worksheet; side 1 lines 7-10 per-person multipliers
  (amounts: see exemption_credit provenance); side 2 line 10 at $475 each; side 2 line 32 threshold).
- Rate schedules: pdfs/california/2025/tax_rate_schedules.pdf
  (Schedules X / Y / Z; Schedule Z is FTB-published independently and
  does NOT equal Schedule X × 2 — e.g. HoH first non-zero threshold
  $22,173 vs SINGLE×2 = $22,158).
- Renter's credit: FTB 2025 540-2EZ Booklet p.13 Q2/Q11 (the regular
  TY2025 540 booklet was unpublished at extraction time; the credit is
  form-agnostic per FTB §17053.5 — re-source when the booklet lands).
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
    # 2025 Personal Income Tax Booklet (Form 540), Line 32 – Exemption
    # Credits table, p.14.
    # https://www.ftb.ca.gov/forms/2025/2025-540-booklet.pdf
    # REV stamp: none printed on Line 32 page; elsewhere: REV 02-26,
    # REV 04-26.
    # sha256 b48ee24bd2f9b9e74fe9a5bbc548d15bae0bd1ce53306bef1ff33fc76f8078c1
    agi_phaseout_threshold={
        _S: 252_203,
        _MFJ: 504_411,
        _MFS: 252_203,
        _HOH: 378_310,
        _QW: 504_411,
    },
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
    # 2025 Personal Income Tax Booklet (Form 540).
    # https://www.ftb.ca.gov/forms/2025/2025-540-booklet.pdf
    # sha256 b48ee24bd2f9b9e74fe9a5bbc548d15bae0bd1ce53306bef1ff33fc76f8078c1
    # REV stamp: none printed on the senior-exemption pages (instructions p.12, form
    # side 1); elsewhere: REV 02-26, REV 04-26.
    # senior_exemption_credit: Form 540 side 1 (booklet PDF page 39),
    # line 9 "X $" box; box assigned by rendered-page position (same row as the line 9
    # label; text layer detaches the boxes from their labels).
    # The Line 9 instructions (p.12) print no amount.
    # senior_born_before: no born-before date printed; condition recorded
    # verbatim below, date left for adjudication.
    # Line 9 – Senior Exemptions (instructions p.12), verbatim:
    # If you were 65 years of age or older by December 31, 2025*, you should
    # claim an additional exemption credit on line 9. If you are married/or
    # an RDP, each spouse/RDP 65 years of age or older should claim an
    # additional credit.
    # *If your 65th birthday is on January 1, 2026, you are considered to be
    # age 65 on December 31, 2025.
    # form-page label:
    # 9 Senior: If you (or your spouse/RDP) are 65 or older, enter 1;
    # if both are 65 or older, enter 2. See instructions.
    # Excluded: the Voluntary Contribution Fund Descriptions (code 400) also
    # restate an age condition; that is a different provision, not a source.
    senior_exemption_credit=153,
    senior_born_before=None,
)
