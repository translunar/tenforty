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

from tenforty.mappings.registry import PdfFormMapping


class PdfF8582(PdfFormMapping[dict]):
    _FORM_NAME = "Form 8582"

    _MAPPINGS: dict[int, dict] = {
        2024: {
            "scalars": {
                # Header — 2024 uses non-zero-padded field names (f1_1, f1_2).
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",
                # Part I — Rental Real Estate Activities with Active Participation
                # Field numbers match 2025 but without zero-padding for digits 1-9.
                "f8582_line_1a_activities_with_income": "topmostSubform[0].Page1[0].f1_3[0]",
                "f8582_line_1b_activities_with_loss": "topmostSubform[0].Page1[0].f1_4[0]",
                "f8582_line_1c_prior_year_unallowed_loss": "topmostSubform[0].Page1[0].f1_5[0]",
                "f8582_line_1d_combine": "topmostSubform[0].Page1[0].f1_6[0]",
                # Line 11 — allowed passive loss (same number, non-zero-padded)
                "f8582_line_11_allowed_loss": "topmostSubform[0].Page1[0].f1_19[0]",
            },
            "repeaters": {},
        },
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
        # 2023 uses the SAME zero-padded field names as 2025 (2024 was the
        # anomaly, dropping the zero-pad on digits 1-9). Every path
        # rendered-position probed against pdfs/federal/2023/f8582.probe.pdf.
        2023: {
            "scalars": {
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_01[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_02[0]",
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


# 2022's Form 8582 keeps 2023's identical field-NAME inventory and mapped paths;
# the only mapped nudge is the header SSN (+1pt x, cosmetic). 2022 reuses 2023.
PdfF8582._MAPPINGS[2022] = PdfF8582._MAPPINGS[2023]
