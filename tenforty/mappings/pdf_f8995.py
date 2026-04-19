"""PDF field mapping for IRS Form 8995 (QBI Deduction Simplified Computation).

Scalars only in v1. Line 1 per-entity rows are unmapped (the compute layer
returns a single summed ``f8995_line_1_qbi`` rather than per-row tuples).

Field names enumerated from ``pdfs/federal/2025/f8995.pdf``:

  f1_01  Name
  f1_02  SSN
  f1_03..f1_17  Line 1 table (5 rows × 3 cols: name, EIN, QBI) — unmapped v1
  f1_18  Line 2 (total QBI)
  f1_19  Line 3 (20% QBI component)
  f1_20  Line 4 (REIT/PTP dividends — zero in v1)
  f1_21  Line 5 (20% REIT/PTP component — zero in v1)
  f1_22  Line 6 (total before income limit)
  f1_23  Line 7 (prior-year QBI loss carryforward — zero in v1)
  f1_24  Line 8 (net QBI loss — zero in v1)
  f1_25  Line 9 (total QBI after losses — zero in v1)
  f1_26  Line 10 (20% of line 9 — zero in v1)
  f1_27  Line 11 (taxable income)
  f1_28  Line 12 (net capital gain)
  f1_29  Line 13 (taxable income minus net capital gain)
  f1_30  Line 14 (20% income limit)
  f1_31  Line 15 (QBI deduction)
  f1_32  Line 16 (carryforward — zero in v1)
  f1_33  Line 17 (net QBI loss carryforward — zero in v1)
"""


class PdfF8995:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_01[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_02[0]",
                # Line 1 table row (i) col c — first entity QBI total:
                # v1 maps the summed line-1 total to the first table cell (col c of row i)
                # as a single-entity approximation; per-row tuples are out of scope.
                "f8995_line_1_qbi": "topmostSubform[0].Page1[0].Table[0].Row1i[0].f1_05[0]",
                # Line 2: total QBI
                "f8995_line_2_total_qbi": "topmostSubform[0].Page1[0].Line2_ReadOrder[0].f1_18[0]",
                # Line 3: 20% QBI component
                "f8995_line_3_component": "topmostSubform[0].Page1[0].f1_19[0]",
                # Line 4: REIT/PTP dividends
                "f8995_line_4_reit_ptp": "topmostSubform[0].Page1[0].f1_20[0]",
                # Line 5: 20% REIT/PTP component
                "f8995_line_5_reit_ptp_component": "topmostSubform[0].Page1[0].f1_21[0]",
                # Line 6: total before income limit
                "f8995_line_6_total_before_limit": "topmostSubform[0].Page1[0].Line6_ReadOrder[0].f1_22[0]",
                # Line 11: taxable income
                "f8995_line_11_taxable_income": "topmostSubform[0].Page1[0].f1_27[0]",
                # Line 12: net capital gain
                "f8995_line_12_net_capital_gain": "topmostSubform[0].Page1[0].f1_28[0]",
                # Line 13: taxable income minus net capital gain
                "f8995_line_13_subtract": "topmostSubform[0].Page1[0].f1_29[0]",
                # Line 14: 20% income limit
                "f8995_line_14_income_limit": "topmostSubform[0].Page1[0].f1_30[0]",
                # Line 15: QBI deduction
                "f8995_line_15_qbi_deduction": "topmostSubform[0].Page1[0].f1_31[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Form 8995 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
