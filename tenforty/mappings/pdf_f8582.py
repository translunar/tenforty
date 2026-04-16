"""PDF field mapping for IRS Form 8582 (Passive Activity Loss Limitations).

Scalars only in v1. Per-activity worksheet rows (Part IV–VIII tables) are
unmapped — compute returns per_activity_carryforwards as a list, which the
filler will silently skip.

Field names enumerated from ``pdfs/federal/2025/f8582.pdf``:

  f1_01  Name (taxpayer_name)
  f1_02  SSN (taxpayer_ssn)

  Part I — Rental Real Estate Activities with Active Participation
  f1_03  Line 1a — net income from activities with overall net income
  f1_04  Line 1b — net loss from activities with overall net loss
  f1_05  Line 1c — prior year unallowed losses
  f1_06  Line 1d — combine lines 1a, 1b, 1c

  f1_07  Line 2a — net income (other passive activities)
  f1_08  Line 2b — net loss (other passive activities)
  f1_09  Line 2c — prior year unallowed losses (other)
  f1_10  Line 2d — combine lines 2a, 2b, 2c

  f1_11  Line 3  — combine lines 1d and 2d

  Part II — Special Allowance for Rental Real Estate with Active Participation
  f1_12  Line 4  — enter $25,000 (or $12,500 if MFS)
  f1_13  Line 5  — enter MAGI
  f1_14  Line 6  — subtract $100,000 (or $50,000) from line 5
  f1_15  Line 7  — multiply line 6 by 50%
  f1_16  Line 8  — subtract line 7 from line 4
  f1_17  Line 9  — enter smaller of line 3 loss or line 8
  f1_18  Line 10 — enter net income from non-rental activities (if any)
  f1_19  Line 11 — allowed loss
"""


class PdfF8582:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_01[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_02[0]",
                # Part I — Rental Real Estate Activities with Active Participation
                "f8582_line_1a_activities_with_income": "topmostSubform[0].Page1[0].f1_03[0]",
                "f8582_line_1b_activities_with_loss": "topmostSubform[0].Page1[0].f1_04[0]",
                "f8582_line_1c_prior_year_unallowed_loss": "topmostSubform[0].Page1[0].f1_05[0]",
                "f8582_line_1d_combine": "topmostSubform[0].Page1[0].f1_06[0]",
                # Line 11 — allowed passive loss (Part II total)
                "f8582_line_11_allowed_loss": "topmostSubform[0].Page1[0].f1_19[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Form 8582 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
