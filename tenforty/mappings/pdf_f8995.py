"""PDF field mapping for IRS Form 8995 (QBI Deduction Simplified Computation).

Scalars only in v1. Line 1 is a SINGLE-ROW approximation: row i carries the
aggregate QBI in col (c) and the FIRST QBI source's name / TIN in cols (a) / (b)
(``f8995_line_1i_name`` / ``f8995_line_1i_tin``); rows ii-v are blank by design
(per-row tuples are out of scope).

Field names enumerated from ``pdfs/federal/2025/f8995.pdf``:

  f1_01  Name
  f1_02  SSN
  f1_03..f1_17  Line 1 table (5 rows × 3 cols: name, TIN, QBI) — v1 maps row i only; rows ii-v blank by design
  f1_18  Line 2 — Total qualified business income or (loss). Combine lines 1i through 1v…
  f1_19  Line 3 — Qualified business net (loss) carryforward from the prior year
  f1_20  Line 4 — Total qualified business income. Combine lines 2 and 3. If zero or less, enter -0-
  f1_21  Line 5 — Qualified business income component. Multiply line 4 by 20% (0.20)
  f1_22  Line 6 — Qualified REIT dividends and publicly traded partnership (PTP) income or (loss)
  f1_23  Line 7 — Qualified REIT dividends and qualified PTP (loss) carryforward from the prior…
  f1_24  Line 8 — Total qualified REIT dividends and PTP income. Combine lines 6 and 7. If zero…
  f1_25  Line 9 — REIT and PTP component. Multiply line 8 by 20% (0.20)
  f1_26  Line 10 — Qualified business income deduction before the income limitation. Add lines 5 and 9
  f1_27  Line 11 — Taxable income before qualified business income deduction (see instructions)
  f1_28  Line 12 — Enter your net capital gain, if any, increased by any qualified dividends (2021–22: "Net capital gain (see instructions)")
  f1_29  Line 13 — Subtract line 12 from line 11. If zero or less, enter -0-
  f1_30  Line 14 — Income limitation. Multiply line 13 by 20% (0.20)
  f1_31  Line 15 — Qualified business income deduction. Enter the smaller of line 10 or line 14. Also enter this…
  f1_32  Line 16 — Total qualified business (loss) carryforward. Combine lines 2 and 3. If greater than zero, enter…
  f1_33  Line 17 — Total qualified REIT dividends and PTP (loss) carryforward. Combine lines 6 and 7. If greater…

Compute-key ↔ FORM-line seam
----------------------------
The compute layer (``tenforty/forms/f8995.py``) names four values one
conceptual tier too HIGH: it computes ``line_3 = 0.20 * floored_qbi`` (which
is the form's line 5), ``line_6 = line_3 + line_5`` (form line 10), and so on.
So the compute KEY NAMES lie about their printed line. This mapping was
derived from the compute layer's ARITHMETIC — ``line_6 = line_3 + line_5``;
``line_15 = min(line_6, line_14)`` — matched against the form's printed
captions, NOT from the key names. A future reader must NOT re-trust the names;
the key rename is deferred ticket (cc).

The keys for form lines 1i(a)/(b), 3, 4, 7, 8 are NEW and are named by their TRUE
FORM line numbers (not one tier off); only the four older keys flagged in bold
above carry a misleading name.

  compute key                            | FORM line | printed caption (abbrev)
  ---------------------------------------|-----------|-------------------------
  f8995_line_1i_name                     |  **1i(a)**| Trade, business, or aggregation name (first QBI source)
  f8995_line_1i_tin                      |  **1i(b)**| Taxpayer identification number (Sch C: taxpayer SSN)
  f8995_line_2_total_qbi                 |     2     | Total qualified business income or (loss)
  f8995_line_3_prior_qbi_loss_carryforward |   3     | Qualified business net (loss) carryforward from the prior year
  f8995_line_4_total_qbi                 |     4     | Total qualified business income. Combine lines 2 and 3 (floored at 0)
  f8995_line_3_component                 |   **5**   | Qualified business income component. Multiply line 4 by 20%
  f8995_line_4_reit_ptp                  |   **6**   | Qualified REIT dividends and PTP income
  f8995_line_7_prior_reit_ptp_loss_carryforward | 7  | Qualified REIT dividends and PTP (loss) carryforward from the prior year
  f8995_line_8_total_reit_ptp            |     8     | Total qualified REIT dividends and PTP income. Combine lines 6 and 7 (floored at 0)
  f8995_line_5_reit_ptp_component        |   **9**   | REIT and PTP component. Multiply line 8 by 20%
  f8995_line_6_total_before_limit        |  **10**   | QBI deduction before the income limitation. Add lines 5 and 9
  f8995_line_11_taxable_income           |    11     | Taxable income before QBI deduction
  f8995_line_12_net_capital_gain         |    12     | (year-dependent) net capital gain
  f8995_line_13_subtract                 |    13     | Subtract line 12 from line 11
  f8995_line_14_income_limit             |    14     | Income limitation. Multiply line 13 by 20%
  f8995_line_15_qbi_deduction            |    15     | Enter the smaller of line 10 or line 14
  f8995_line_16_qbi_loss_carryforward    |  **16**   | Total qualified business (loss) carryforward

Lines 3, 7, 16 and 17 sit in PREPRINTED parentheses; see ``presentation_values``.
"""

from tenforty.mappings.registry import PdfFormMapping


# Compute keys whose cell has PREPRINTED parentheses on the form. The compute
# value is signed (a loss is negative); the cell must receive the MAGNITUDE,
# or the page reads "( -70 )". Line 16 is the only such key that can be
# nonzero today: lines 3 and 7 (prior-year carryforwards IN) have no input
# channel and print 0, and line 17 (REIT/PTP carryforward) has no compute key.
_PARENTHESIZED_KEYS = (
    "f8995_line_16_qbi_loss_carryforward",
    "f8995_line_3_prior_qbi_loss_carryforward",
    "f8995_line_7_prior_reit_ptp_loss_carryforward",
)


class PdfF8995(PdfFormMapping[dict]):
    _FORM_NAME = "Form 8995"

    @staticmethod
    def presentation_values(values: dict) -> dict:
        """The fill payload for a computed Form 8995: a copy of ``values``
        with every preprinted-parentheses cell carrying its magnitude.
        Compute keys stay signed everywhere else (gates, snapshots)."""
        out = dict(values)
        for key in _PARENTHESIZED_KEYS:
            if isinstance(out.get(key), (int, float)):
                out[key] = abs(out[key])
        return out

    _MAPPINGS: dict[int, dict] = {
        2024: {
            "scalars": {
                # Header — 2024 uses non-zero-padded field names (f1_1, f1_2).
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",
                # Line 1 table row: 2024 uses Ln1A_Row1 subform (vs Row1i in 2025).
                # Col c (QBI amount) is the 3rd field (f1_5) in the 3-column row.
                "f8995_line_1_qbi": "topmostSubform[0].Page1[0].Table[0].Ln1A_Row1[0].f1_5[0]",
                # Row i cols a/b: first QBI source's name / TIN (single-row v1).
                "f8995_line_1i_name": "topmostSubform[0].Page1[0].Table[0].Ln1A_Row1[0].f1_3[0]",
                "f8995_line_1i_tin": "topmostSubform[0].Page1[0].Table[0].Ln1A_Row1[0].f1_4[0]",
                # Line 2: total QBI — 2024 uses ReadOrderSubForm[0] (vs Line2_ReadOrder in 2025).
                "f8995_line_2_total_qbi": "topmostSubform[0].Page1[0].ReadOrderSubForm[0].f1_18[0]",
                # Keys repointed to their arithmetic-correct FORM lines (names
                # are one tier high — see module docstring seam table, ticket (cc)).
                # Same paths as 2025.
                "f8995_line_3_component": "topmostSubform[0].Page1[0].f1_21[0]",  # FORM line 5 (f1_21, direct)
                "f8995_line_4_reit_ptp": "topmostSubform[0].Page1[0].Line6_ReadOrder[0].f1_22[0]",  # FORM line 6 (f1_22, Line6_ReadOrder-wrapped in 2023–25)
                "f8995_line_5_reit_ptp_component": "topmostSubform[0].Page1[0].f1_25[0]",  # FORM line 9 (f1_25, direct)
                "f8995_line_6_total_before_limit": "topmostSubform[0].Page1[0].f1_26[0]",  # FORM line 10 (f1_26, DIRECT — carries no wrapper to its new home)
                # Lines 11–15: same direct paths as 2025.
                # FORM lines 3, 4, 7, 8 (combine lines; direct fields in all years).
                "f8995_line_3_prior_qbi_loss_carryforward": "topmostSubform[0].Page1[0].f1_19[0]",
                "f8995_line_4_total_qbi": "topmostSubform[0].Page1[0].f1_20[0]",
                "f8995_line_7_prior_reit_ptp_loss_carryforward": "topmostSubform[0].Page1[0].f1_23[0]",
                "f8995_line_8_total_reit_ptp": "topmostSubform[0].Page1[0].f1_24[0]",
                "f8995_line_11_taxable_income": "topmostSubform[0].Page1[0].f1_27[0]",
                "f8995_line_12_net_capital_gain": "topmostSubform[0].Page1[0].f1_28[0]",
                "f8995_line_13_subtract": "topmostSubform[0].Page1[0].f1_29[0]",
                "f8995_line_14_income_limit": "topmostSubform[0].Page1[0].f1_30[0]",
                "f8995_line_15_qbi_deduction": "topmostSubform[0].Page1[0].f1_31[0]",
                "f8995_line_16_qbi_loss_carryforward": "topmostSubform[0].Page1[0].f1_32[0]",  # FORM line 16 (f1_32, direct)
            },
            "repeaters": {},
        },
        2025: {
            "scalars": {
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_01[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_02[0]",
                # Line 1 table row (i) col c — first entity QBI total:
                # v1 maps the summed line-1 total to the first table cell (col c of row i)
                # as a single-entity approximation; per-row tuples are out of scope.
                "f8995_line_1_qbi": "topmostSubform[0].Page1[0].Table[0].Row1i[0].f1_05[0]",
                # Row i cols a/b: first QBI source's name / TIN (single-row v1).
                "f8995_line_1i_name": "topmostSubform[0].Page1[0].Table[0].Row1i[0].f1_03[0]",
                "f8995_line_1i_tin": "topmostSubform[0].Page1[0].Table[0].Row1i[0].f1_04[0]",
                # Line 2: total QBI
                "f8995_line_2_total_qbi": "topmostSubform[0].Page1[0].Line2_ReadOrder[0].f1_18[0]",
                # Keys repointed to their arithmetic-correct FORM lines (names
                # are one tier high — see module docstring seam table, ticket (cc)).
                # FORM line 5: QBI component (compute key named line_3)
                "f8995_line_3_component": "topmostSubform[0].Page1[0].f1_21[0]",
                # FORM line 6: REIT/PTP dividends (compute key named line_4);
                # f1_22 carries the Line6_ReadOrder accessibility wrapper here.
                "f8995_line_4_reit_ptp": "topmostSubform[0].Page1[0].Line6_ReadOrder[0].f1_22[0]",
                # FORM line 9: REIT/PTP component (compute key named line_5)
                "f8995_line_5_reit_ptp_component": "topmostSubform[0].Page1[0].f1_25[0]",
                # FORM line 10: QBI deduction before income limit (compute key
                # named line_6); f1_26 is a DIRECT field — no wrapper travels here.
                "f8995_line_6_total_before_limit": "topmostSubform[0].Page1[0].f1_26[0]",
                # Line 11: taxable income
                # FORM lines 3, 4, 7, 8 (combine lines; direct fields in all years).
                "f8995_line_3_prior_qbi_loss_carryforward": "topmostSubform[0].Page1[0].f1_19[0]",
                "f8995_line_4_total_qbi": "topmostSubform[0].Page1[0].f1_20[0]",
                "f8995_line_7_prior_reit_ptp_loss_carryforward": "topmostSubform[0].Page1[0].f1_23[0]",
                "f8995_line_8_total_reit_ptp": "topmostSubform[0].Page1[0].f1_24[0]",
                "f8995_line_11_taxable_income": "topmostSubform[0].Page1[0].f1_27[0]",
                # Line 12: net capital gain
                "f8995_line_12_net_capital_gain": "topmostSubform[0].Page1[0].f1_28[0]",
                # Line 13: taxable income minus net capital gain
                "f8995_line_13_subtract": "topmostSubform[0].Page1[0].f1_29[0]",
                # Line 14: 20% income limit
                "f8995_line_14_income_limit": "topmostSubform[0].Page1[0].f1_30[0]",
                # Line 15: QBI deduction
                "f8995_line_15_qbi_deduction": "topmostSubform[0].Page1[0].f1_31[0]",
                # FORM line 16: QBI loss carryforward (f1_32, direct)
                "f8995_line_16_qbi_loss_carryforward": "topmostSubform[0].Page1[0].f1_32[0]",
            },
            "repeaters": {},
        },
    }


# 2023's Form 8995 field tree is byte-identical to 2024's (verified: identical
# AcroForm field-path sets), so 2023 reuses the 2024 payload unchanged. The
# fields-on-template gate re-verifies existence; the 2023 emit + parity gates
# verify positions.
PdfF8995._MAPPINGS[2023] = PdfF8995._MAPPINGS[2024]

# 2022's Form 8995 differs from 2023 in exactly one mapped field: the FORM line-6
# box (f1_22) drops the Line6_ReadOrder accessibility wrapper that 2023–2025 place
# around it, so f1_22 sits directly under Page1[0]. After the key repoint, FORM
# line 6 is `f8995_line_4_reit_ptp`'s box (not `line_6`'s) — so the 2022 override
# now targets `f8995_line_4_reit_ptp`, dropping its wrapper. (`line_6` moved to
# f1_26 on FORM line 10, a direct field identical across all years, so it needs
# no override.)
#
# What the marker probe on pdfs/federal/2022/f8995.probe.pdf actually
# established: each PDF FIELD NAME (f1_18, f1_19, …, f1_31) renders on the printed
# line its name suggests (f1_18 on line 2, f1_19 on line 3, …), and f1_22 renders
# on line 6 without the wrapper. That is a FIELD-NAME ↔ printed-line fact and it
# is true. The probe is structurally INCAPABLE of speaking to compute-KEY-meaning
# ↔ printed-line — i.e. whether the value the compute layer stores under
# `f8995_line_3_component` actually belongs on the line its mapped field prints
# on. That mismatch is exactly the defect Task 3 fixed (the compute keys were one
# tier high; see the module docstring seam table). Every other mapped field's
# full path is byte-identical to 2023's (verified against the 2022 template's
# AcroForm inventory); the header uses the non-zero-padded f1_1/f1_2 like
# 2023/2024.
PdfF8995._MAPPINGS[2022] = {
    "scalars": {
        **PdfF8995._MAPPINGS[2023]["scalars"],
        # FORM line 6 box (f1_22) is a direct field in 2021–2022 — no wrapper.
        "f8995_line_4_reit_ptp":
            "topmostSubform[0].Page1[0].f1_22[0]",
    },
    "repeaters": {},
}

# 2021 field tree is IDENTICAL to 2022 (diff_pdf_fields, controller-verified); the
# fields-on-template gate re-verifies every path against the 2021 template and the
# emit round-trip test verifies values land.
PdfF8995._MAPPINGS[2021] = PdfF8995._MAPPINGS[2022]
