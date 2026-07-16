"""PDF field mapping for IRS Schedule E (Supplemental Income and Loss).

v1 scope: single rental property (slot A on Page 1). Property slots B
and C exist on the form but are not populated by v1 compute.

Part II (partnerships, S-corps via K-1) shares the Page 2 table frame.
The page-2 header fields (taxpayer_name_page2 / taxpayer_ssn_page2)
are mapping-layer concerns — the orchestrator derives them from the compute
outputs (taxpayer_name / taxpayer_ssn) when merging Part I + Part II values.
That way compute never leaks PDF-template structure.

Field names enumerated from ``pdfs/federal/2025/f1040se.pdf``.

Page 2 field discovery notes (2025 form; confirmed via `pdftotext -layout`
against pdfs/federal/2025/f1040se.pdf and cross-checked by widget x-position
against pdfs/federal/2021/f1040se.pdf — both share the same left-to-right
column order):
  - Table_Line28a-f: per-row (a) name f2_(3,6,9,12) [TEXT], (b) "Enter P for
    partnership; S for S corporation" f2_(4,7,10,13) [TEXT], (c) foreign-
    partnership checkbox c2_(2,5,8,11) [CHECKBOX, unmapped], (d) EIN
    f2_(5,8,11,14) [TEXT], (e) basis-computation-required checkbox
    c2_(3,6,9,12) [CHECKBOX, unmapped], (f) not-at-risk checkbox
    c2_(4,7,10,13) [CHECKBOX, unmapped]. Only (a)/(b)/(d) are modeled by
    compute; (c)/(e)/(f) have no corresponding compute inputs.
  - Table_Line28g-k:  five numeric columns per row at x≈65,187,288,389,490.
    Column order: (e) passive loss allowed, (f) passive income,
    (g) nonpassive loss, (h) §179 (skipped in v1), (i) nonpassive income.
  - Line 29a/b totals at y≈480/468 (f2_35–f2_44, five cols each).
  - Lines 30/31/32 single-column totals (f2_45/f2_46/f2_47).
  - Line 37 estate/trust total (f2_68) — always 0: estate_trust K-1s are rejected at load.
  - Line 41 total pass-through (f2_76).
"""

import re

from tenforty.mappings.registry import PdfFormMapping

_P2 = "topmostSubform[0].Page2[0]"
_T28AF = f"{_P2}.Table_Line28a-f[0]"
_T28GK = f"{_P2}.Table_Line28g-k[0]"

_ROWS = ("A", "B", "C", "D")


def _row_mapping(row_letter: str) -> dict[str, str]:
    """Return the PDF field entries for one Part II Line 28 row (A–D).

    Real IRS Line 28 column layout (confirmed via `pdftotext -layout`
    against pdfs/federal/2025/f1040se.pdf, Page 2): (a) Name, (b) Enter P
    for partnership; S for S corporation [TEXT], (c) Check if foreign
    partnership [CHECKBOX], (d) Employer identification number [TEXT],
    (e) Check if basis computation is required [CHECKBOX], (f) Check if
    any amount is not at risk [CHECKBOX]. Field-number strides within the
    form (verified per-row against each field's x-position, left to
    right — text and checkbox leaves interleave a/b/c/d/e/f in that exact
    order on every row):
      AF sub-table — +3 per row:
        name (a) f2_(3,6,9,12), entity_code (b) f2_(4,7,10,13),
        foreign-partnership checkbox (c) c2_(2,5,8,11) [UNMAPPED],
        ein (d) f2_(5,8,11,14),
        basis-required checkbox (e) c2_(3,6,9,12) [UNMAPPED],
        not-at-risk checkbox (f) c2_(4,7,10,13) [UNMAPPED, always was]
      GK sub-table (income/loss columns) — +5 per row:
        passive_loss f2_(15,20,25,30), passive_income f2_(16,21,26,31),
        nonpassive_loss f2_(17,22,27,32),
        nonpassive_income f2_(19,24,29,34)  ← skips §179 at offset +2
    To add Row E: append "E" to _ROWS; strides extend automatically.
    """
    i = _ROWS.index(row_letter)
    row = row_letter.lower()
    af = f"{_T28AF}.Row{row_letter}[0]"
    gk = f"{_T28GK}.Row{row_letter}[0]"
    return {
        f"sch_e_part_ii_row_{row}_name":                     f"{af}.f2_{3 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_entity_code":               f"{af}.f2_{4 + 3 * i}[0]",
        # DELIBERATELY UNMAPPED: col (c) c2_{2 + 3 * i} (foreign-partnership
        # checkbox) and col (e) c2_{3 + 3 * i} (basis-required checkbox) are
        # not modeled by compute (col (f) c2_{4 + 3 * i}, not-at-risk, was
        # already unmapped before this fix and stays so).
        f"sch_e_part_ii_row_{row}_ein":                      f"{af}.f2_{5 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_loss":             f"{gk}.f2_{15 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_income":           f"{gk}.f2_{16 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_loss":          f"{gk}.f2_{17 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_income":        f"{gk}.f2_{19 + 5 * i}[0]",
    }


def _build_fields() -> dict:
    """Build the Schedule E mapping dict (identical for 2024 and 2025)."""
    return {
        "scalars": {
            # ── Page 1 header ─────────────────────────────────────────────
            "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
            "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",

            # Line 1a — property A address
            "sch_e_property_a_address":
                "topmostSubform[0].Page1[0].Table_Line1a[0].RowA[0].f1_3[0]",

            # Line 1b — property A type code (1-8)
            "sch_e_property_a_type_code":
                "topmostSubform[0].Page1[0].Table_Line1b[0].RowA[0].f1_6[0]",

            # Line 2 — fair rental days / personal use days for A
            "sch_e_property_a_fair_rental_days":
                "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_9[0]",
            "sch_e_property_a_personal_use_days":
                "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_10[0]",

            # Line 3 — rents received A
            "sch_e_property_a_rents":
                "topmostSubform[0].Page1[0].Table_Income[0].Line3[0].f1_16[0]",

            # Lines 5–18: per-expense property-A amounts
            "sch_e_property_a_advertising":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line5[0].f1_22[0]",
            "sch_e_property_a_auto_and_travel":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line6[0].f1_25[0]",
            "sch_e_property_a_cleaning_and_maintenance":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line7[0].f1_28[0]",
            "sch_e_property_a_commissions":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line8[0].f1_31[0]",
            "sch_e_property_a_insurance":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line9[0].f1_34[0]",
            "sch_e_property_a_legal_and_professional_fees":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line10[0].f1_37[0]",
            "sch_e_property_a_management_fees":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line11[0].f1_40[0]",
            "sch_e_property_a_mortgage_interest":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line12[0].f1_43[0]",
            "sch_e_property_a_other_interest":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line13[0].f1_46[0]",
            "sch_e_property_a_repairs":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line14[0].f1_49[0]",
            "sch_e_property_a_supplies":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line15[0].f1_52[0]",
            "sch_e_property_a_taxes":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line16[0].f1_55[0]",
            "sch_e_property_a_utilities":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_58[0]",
            "sch_e_property_a_depreciation":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]",

            # Line 19 — "other" A amount
            "sch_e_property_a_other_expenses":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line19[0].f1_65[0]",

            # Line 20 — total expenses A
            "sch_e_property_a_total_expenses":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_68[0]",

            # Line 21 — income or (loss) A
            "sch_e_property_a_income_loss":
                "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_71[0]",

            # Line 26 — total rental real estate / royalty income (page 1 summary)
            "sch_e_line_26_total":
                "topmostSubform[0].Page1[0].f1_84[0]",

            # ── Page 2 header ──────────────────────────────────────────────
            "taxpayer_name_page2": f"{_P2}.f2_1[0]",
            "taxpayer_ssn_page2":  f"{_P2}.f2_2[0]",

            # ── Part II — Line 28, Rows A–D (generated via _row_mapping) ──────
            **{
                k: v
                for letter in _ROWS
                for k, v in _row_mapping(letter).items()
            },

            # ── Part II — Line 29 column totals ────────────────────────────
            "sch_e_line_29a_total_passive_loss":
                f"{_P2}.f2_35[0]",
            "sch_e_line_29a_total_passive_income":
                f"{_P2}.f2_36[0]",
            "sch_e_line_29a_total_nonpassive_loss":
                f"{_P2}.f2_37[0]",
            "sch_e_line_29a_total_nonpassive_income":
                f"{_P2}.f2_39[0]",
            "sch_e_line_29b_total_passive_loss":
                f"{_P2}.f2_40[0]",
            "sch_e_line_29b_total_passive_income":
                f"{_P2}.f2_41[0]",
            "sch_e_line_29b_total_nonpassive_loss":
                f"{_P2}.f2_42[0]",
            "sch_e_line_29b_total_nonpassive_income":
                f"{_P2}.f2_44[0]",

            # ── Part II — Lines 30 / 31 / 32 ───────────────────────────────
            "sch_e_line_30_total_income":    f"{_P2}.f2_45[0]",
            "sch_e_line_31_total_loss":      f"{_P2}.f2_46[0]",
            "sch_e_line_32_total_partnership_scorp": f"{_P2}.f2_47[0]",

            # ── Part III — Line 37 (estate/trust) — always 0 ────────────────
            "sch_e_line_37_total_estate_trust": f"{_P2}.f2_68[0]",

            # ── Line 41 — total pass-through income / (loss) ───────────────
            "sch_e_line_41_total_pte": f"{_P2}.f2_76[0]",
        },
        "repeaters": {},
    }


# 2024 and 2025 Schedule E PDFs share an identical field tree (pinned by
# tests/test_mapping_year_identity.py); one payload serves both.
_FIELDS: dict = _build_fields()


def _to_2022(fields: dict) -> dict:
    """2022 Schedule E zero-pads single-digit TEXT-field leaves (f1_3 -> f1_03)
    while leaving checkbox leaves (c2_2) and already-two-digit leaves unchanged.
    This asymmetry is an IRS naming quirk, not a structural change: the container
    tree is otherwise byte-identical to 2023. Verified two ways — every resulting
    path exists on the 2022 template's AcroForm inventory (single, unambiguous
    resolution: 60 same-leaf + 12 padded-leaf, 0 unresolved), and marker-probed
    (pdfs/federal/2022/f1040se.probe.pdf) with each field rendering on the same
    line as its 2023 counterpart across both pages (line 1a–26 Part I, line
    28–43 Parts II–V)."""
    def pad(path: str) -> str:
        head, _, leaf = path.rpartition(".")
        leaf = re.sub(r"^(f\d)_(\d)(\[0\])$",
                      lambda m: f"{m.group(1)}_0{m.group(2)}{m.group(3)}", leaf)
        return f"{head}.{leaf}"
    return {"scalars": {k: pad(v) for k, v in fields["scalars"].items()},
            "repeaters": {}}


_FIELDS_2022: dict = _to_2022(_FIELDS)


# ── 2021 ──────────────────────────────────────────────────────────────────
# The 2021 Schedule E template does NOT share the 2022-2025 field tree, so it
# is a literal transcription of the controller + team-lead render-VERIFIED map
# (.superpowers/sdd/probe/sch_e-2021-NESTED-FINAL.json), NOT derived from the
# _build_fields()/_row_mapping() generator. Key structural differences from the
# merged years: Part I uses Line1[0].Table1a/Table1b nesting; Part II Line 28 is
# Table_Line28a-e (not 28a-f); row-A EIN is f2_5 (col d), not f2_4; and the
# Line 29/30/31/32/37/41 leaves have entirely different numbering. All 60 paths
# were confirmed to exist on the 2021 template with no collisions; name→f2_3
# (col a) and ein→f2_5 (col d) are content-verified.
#
# FIXED HERE (2021) — entity_code (4 keys sch_e_part_ii_row_{a,b,c,d}_
# entity_code): line-28 col (b) is a single "Enter P/S" TEXT field; compute
# now derives one entity_code ("P"|"S") per row instead of the old two-
# boolean emit, so it maps directly onto col (b) f2_(4,7,10,13) — the same
# sch_e-line-28 follow-up plan that fixes the merged-2022-2025 mismapping
# bug (ein/entity_type routed to wrong cells). Col (c)/(e)/(f) checkboxes
# (foreign partnership / basis required / not at risk) remain unmapped —
# not modeled by compute. name + ein ARE mapped here (cols a/d), verified.
#
# DELIBERATELY UNMAPPED (2021) — line-29 cross keys (4:
# sch_e_line_29a_total_passive_loss, sch_e_line_29a_total_nonpassive_loss,
# sch_e_line_29b_total_passive_income, sch_e_line_29b_total_nonpassive_income):
# never emitted by compute (sch_e_part_ii.py emits income-on-29a, loss-on-29b
# only) AND the 2021 form's corresponding cells are IRS-shaded non-entry boxes.
_FIELDS_2021: dict = {
    "scalars": {
        "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
        "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",
        "sch_e_property_a_address":
            "topmostSubform[0].Page1[0].Line1[0].Table1a[0].RowA[0].f1_3[0]",
        "sch_e_property_a_type_code":
            "topmostSubform[0].Page1[0].Line1[0].Table1b[0].RowA[0].f1_6[0]",
        "sch_e_property_a_fair_rental_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_9[0]",
        "sch_e_property_a_personal_use_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_10[0]",
        "sch_e_property_a_rents":
            "topmostSubform[0].Page1[0].Table_Income[0].Income[0].Line3[0].f1_16[0]",
        "sch_e_property_a_advertising":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line5[0].f1_22[0]",
        "sch_e_property_a_auto_and_travel":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line6[0].f1_25[0]",
        "sch_e_property_a_cleaning_and_maintenance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line7[0].f1_28[0]",
        "sch_e_property_a_commissions":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line8[0].f1_31[0]",
        "sch_e_property_a_insurance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line9[0].f1_34[0]",
        "sch_e_property_a_legal_and_professional_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line10[0].f1_37[0]",
        "sch_e_property_a_management_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line11[0].f1_40[0]",
        "sch_e_property_a_mortgage_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line12[0].f1_43[0]",
        "sch_e_property_a_other_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line13[0].f1_46[0]",
        "sch_e_property_a_repairs":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line14[0].f1_49[0]",
        "sch_e_property_a_supplies":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line15[0].f1_52[0]",
        "sch_e_property_a_taxes":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line16[0].f1_55[0]",
        "sch_e_property_a_utilities":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_58[0]",
        "sch_e_property_a_depreciation":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]",
        "sch_e_property_a_other_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line19[0].f1_65[0]",
        "sch_e_property_a_total_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_68[0]",
        "sch_e_property_a_income_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_71[0]",
        "sch_e_line_26_total": "topmostSubform[0].Page1[0].f1_84[0]",
        "taxpayer_name_page2": "topmostSubform[0].Page2[0].f2_1[0]",
        "taxpayer_ssn_page2": "topmostSubform[0].Page2[0].f2_2[0]",
        "sch_e_part_ii_row_a_name":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_3[0]",
        "sch_e_part_ii_row_a_entity_code":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_4[0]",
        "sch_e_part_ii_row_a_ein":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_5[0]",
        "sch_e_part_ii_row_a_passive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_15[0]",
        "sch_e_part_ii_row_a_passive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_16[0]",
        "sch_e_part_ii_row_a_nonpassive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_17[0]",
        "sch_e_part_ii_row_a_nonpassive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_19[0]",
        "sch_e_part_ii_row_b_name":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowB[0].f2_6[0]",
        "sch_e_part_ii_row_b_entity_code":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowB[0].f2_7[0]",
        "sch_e_part_ii_row_b_ein":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowB[0].f2_8[0]",
        "sch_e_part_ii_row_b_passive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowB[0].f2_20[0]",
        "sch_e_part_ii_row_b_passive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowB[0].f2_21[0]",
        "sch_e_part_ii_row_b_nonpassive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowB[0].f2_22[0]",
        "sch_e_part_ii_row_b_nonpassive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowB[0].f2_24[0]",
        "sch_e_part_ii_row_c_name":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowC[0].f2_9[0]",
        "sch_e_part_ii_row_c_entity_code":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowC[0].f2_10[0]",
        "sch_e_part_ii_row_c_ein":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowC[0].f2_11[0]",
        "sch_e_part_ii_row_c_passive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowC[0].f2_25[0]",
        "sch_e_part_ii_row_c_passive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowC[0].f2_26[0]",
        "sch_e_part_ii_row_c_nonpassive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowC[0].f2_27[0]",
        "sch_e_part_ii_row_c_nonpassive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowC[0].f2_29[0]",
        "sch_e_part_ii_row_d_name":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowD[0].f2_12[0]",
        "sch_e_part_ii_row_d_entity_code":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowD[0].f2_13[0]",
        "sch_e_part_ii_row_d_ein":
            "topmostSubform[0].Page2[0].Table_Line28a-e[0].RowD[0].f2_14[0]",
        "sch_e_part_ii_row_d_passive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_30[0]",
        "sch_e_part_ii_row_d_passive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_31[0]",
        "sch_e_part_ii_row_d_nonpassive_loss":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_32[0]",
        "sch_e_part_ii_row_d_nonpassive_income":
            "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_34[0]",
        "sch_e_line_29a_total_passive_income":
            "topmostSubform[0].Page2[0].f2_35[0]",
        "sch_e_line_29a_total_nonpassive_income":
            "topmostSubform[0].Page2[0].f2_36[0]",
        "sch_e_line_29b_total_passive_loss":
            "topmostSubform[0].Page2[0].f2_37[0]",
        "sch_e_line_29b_total_nonpassive_loss":
            "topmostSubform[0].Page2[0].f2_38[0]",
        "sch_e_line_30_total_income": "topmostSubform[0].Page2[0].f2_40[0]",
        "sch_e_line_31_total_loss": "topmostSubform[0].Page2[0].f2_41[0]",
        "sch_e_line_32_total_partnership_scorp":
            "topmostSubform[0].Page2[0].f2_42[0]",
        "sch_e_line_37_total_estate_trust": "topmostSubform[0].Page2[0].f2_61[0]",
        "sch_e_line_41_total_pte": "topmostSubform[0].Page2[0].f2_69[0]",
    },
    "repeaters": {},
}


class PdfSchE(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule E"

    # 2023's field tree is byte-identical to 2024's (verified: identical
    # AcroForm field-path sets), so one payload serves all three years. 2022
    # zero-pads single-digit text-field leaves (see _to_2022).
    _MAPPINGS: dict[int, dict] = {
        2021: _FIELDS_2021,
        2022: _FIELDS_2022, 2023: _FIELDS, 2024: _FIELDS, 2025: _FIELDS}

