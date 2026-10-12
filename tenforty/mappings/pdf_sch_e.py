"""PDF field mapping for IRS Schedule E (Supplemental Income and Loss).

Page 1 carries three property columns (A, B, C) for lines 1a-22; all three
are mapped, on every template 2021-2025 (see _COLUMN_CELLS).

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
        basis-required checkbox (e) c2_(3,6,9,12) [see _BASIS_CELLS],
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
        # checkbox) and col (f) c2_{4 + 3 * i} (not-at-risk) are not modeled
        # by compute. Col (e) c2_{3 + 3 * i} (basis-required checkbox) is
        # written through get_basis_computation_cells, not this value map.
        f"sch_e_part_ii_row_{row}_ein":                      f"{af}.f2_{5 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_loss":             f"{gk}.f2_{15 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_income":           f"{gk}.f2_{16 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_loss":          f"{gk}.f2_{17 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_income":        f"{gk}.f2_{19 + 5 * i}[0]",
    }


# Page 1 property columns, lines 1a-22: (key suffix, container, column A's
# leaf number, leaf stride from one column to the next). Column B's leaf is
# A's plus the stride and column C's is A's plus twice the stride; the stride
# is 1 everywhere except line 2, whose two day counts alternate along each
# property row (A f1_9/f1_10, B f1_11/f1_12, C f1_13/f1_14). Lines 1a, 1b
# and 2 sit in one row subform per property ("{row}" is A, B or C); lines
# 3-22 sit in one subform per line holding the three column cells. Enumerated
# from each template's widget Rects; the leaf numbers are the same on the
# 2021, 2022, 2023, 2024 and 2025 templates.
# DELIBERATELY UNMAPPED: line 4 (royalties, f1_19..f1_21) -- compute prints
# nothing there; line 19's description cell (f1_64); the line 2 QJV
# checkboxes (c1_3..c1_5).
_COLUMN_LETTERS = ("a", "b", "c")
_COLUMN_CELLS: tuple[tuple[str, str, int, int], ...] = (
    ("address", "Table_Line1a[0].Row{row}[0]", 3, 1),
    ("type_code", "Table_Line1b[0].Row{row}[0]", 6, 1),
    ("fair_rental_days", "Table_Line2[0].Row{row}[0]", 9, 2),
    ("personal_use_days", "Table_Line2[0].Row{row}[0]", 10, 2),
    ("rents", "Table_Income[0].Line3[0]", 16, 1),
    ("advertising", "Table_Expenses[0].Line5[0]", 22, 1),
    ("auto_and_travel", "Table_Expenses[0].Line6[0]", 25, 1),
    ("cleaning_and_maintenance", "Table_Expenses[0].Line7[0]", 28, 1),
    ("commissions", "Table_Expenses[0].Line8[0]", 31, 1),
    ("insurance", "Table_Expenses[0].Line9[0]", 34, 1),
    ("legal_and_professional_fees", "Table_Expenses[0].Line10[0]", 37, 1),
    ("management_fees", "Table_Expenses[0].Line11[0]", 40, 1),
    ("mortgage_interest", "Table_Expenses[0].Line12[0]", 43, 1),
    ("other_interest", "Table_Expenses[0].Line13[0]", 46, 1),
    ("repairs", "Table_Expenses[0].Line14[0]", 49, 1),
    ("supplies", "Table_Expenses[0].Line15[0]", 52, 1),
    ("taxes", "Table_Expenses[0].Line16[0]", 55, 1),
    ("utilities", "Table_Expenses[0].Line17[0]", 58, 1),
    ("depreciation", "Table_Expenses[0].Line18[0]", 61, 1),
    ("other_expenses", "Table_Expenses[0].Line19[0]", 65, 1),
    ("total_expenses", "Table_Expenses[0].Line20[0]", 68, 1),
    ("income_loss", "Table_Expenses[0].Line21[0]", 71, 1),
    ("deductible_loss", "Table_Expenses[0].Line22[0]", 74, 1),
)


def _column_mapping() -> dict[str, str]:
    """The lines 1a-22 entries for property columns A, B and C (2022-2025
    container tree; 2021 is the literal transcription in _FIELDS_2021)."""
    return {
        f"sch_e_property_{letter}_{suffix}": (
            "topmostSubform[0].Page1[0]."
            f"{container.format(row=letter.upper())}"
            f".f1_{leaf + stride * column}[0]")
        for suffix, container, leaf, stride in _COLUMN_CELLS
        for column, letter in enumerate(_COLUMN_LETTERS)
    }


# Page 1 totals block, lines 23a-25. The leaf names and their top-to-bottom
# order are the same on the 2021, 2022, 2023, 2024 and 2025 templates
# (enumerated per year from each template's widget Rects; only the y-offsets
# differ in 2021). 2022's zero-padding touches single-digit leaves only, so
# these two-digit leaves are unchanged there.
#   f1_77 line 23a   f1_78 line 23b   f1_79 line 23c   f1_80 line 23d
#   f1_81 line 23e   f1_82 line 24    f1_83 line 25    f1_84 line 26
# DELIBERATELY UNMAPPED: f1_78 (line 23b, royalties) -- compute prints nothing
# on line 4, so there is no royalty total to print.
# Line 22 has one cell per property column; those are column cells (see
# _COLUMN_CELLS), not part of this block.
_TOTALS_BLOCK: dict[str, str] = {
    "sch_e_line_25_losses": "topmostSubform[0].Page1[0].f1_83[0]",
    "sch_e_line_23a_total_rents": "topmostSubform[0].Page1[0].f1_77[0]",
    "sch_e_line_23c_total_mortgage_interest":
        "topmostSubform[0].Page1[0].f1_79[0]",
    "sch_e_line_23d_total_depreciation": "topmostSubform[0].Page1[0].f1_80[0]",
    "sch_e_line_23e_total_expenses": "topmostSubform[0].Page1[0].f1_81[0]",
    "sch_e_line_24_income": "topmostSubform[0].Page1[0].f1_82[0]",
}


def _build_fields() -> dict:
    """Build the Schedule E mapping dict (identical for 2024 and 2025)."""
    return {
        "scalars": {
            # ── Page 1 header ─────────────────────────────────────────────
            "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
            "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",

            # Lines 1a-22 — property columns A, B and C (generated).
            **_column_mapping(),

            # Lines 23a/23c/23d/23e, 24 and 25 — page 1 totals block. Leaves
            # f1_77..f1_84 run 23a, 23b, 23c, 23d, 23e, 24, 25, 26 top to
            # bottom on every template 2021-2025 (see _TOTALS_BLOCK).
            **_TOTALS_BLOCK,

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
            # f2_70 is line 37; f2_68 is line 35 (was mis-bound there).
            "sch_e_line_37_total_estate_trust": f"{_P2}.f2_70[0]",

            # ── Line 41 — total income/(loss), the form-true grand total
            # (line 26 + line 32 + 37/39/40) that flows to Schedule 1 line 5.
            # f2_78 is line 41; f2_76 is line 39 (REMIC), where the pte-only
            # subtotal was wrongly printed. See sch_e_part_ii.merge_with_part_i.
            "sch_e_line_41_total_income": f"{_P2}.f2_78[0]",
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
        "sch_e_property_a_deductible_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line22[0].f1_74[0]",
        # Property column B, lines 1a-22.
        "sch_e_property_b_address":
            "topmostSubform[0].Page1[0].Line1[0].Table1a[0].RowB[0].f1_4[0]",
        "sch_e_property_b_type_code":
            "topmostSubform[0].Page1[0].Line1[0].Table1b[0].RowB[0].f1_7[0]",
        "sch_e_property_b_fair_rental_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowB[0].f1_11[0]",
        "sch_e_property_b_personal_use_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowB[0].f1_12[0]",
        "sch_e_property_b_rents":
            "topmostSubform[0].Page1[0].Table_Income[0].Income[0].Line3[0].f1_17[0]",
        "sch_e_property_b_advertising":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line5[0].f1_23[0]",
        "sch_e_property_b_auto_and_travel":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line6[0].f1_26[0]",
        "sch_e_property_b_cleaning_and_maintenance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line7[0].f1_29[0]",
        "sch_e_property_b_commissions":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line8[0].f1_32[0]",
        "sch_e_property_b_insurance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line9[0].f1_35[0]",
        "sch_e_property_b_legal_and_professional_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line10[0].f1_38[0]",
        "sch_e_property_b_management_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line11[0].f1_41[0]",
        "sch_e_property_b_mortgage_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line12[0].f1_44[0]",
        "sch_e_property_b_other_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line13[0].f1_47[0]",
        "sch_e_property_b_repairs":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line14[0].f1_50[0]",
        "sch_e_property_b_supplies":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line15[0].f1_53[0]",
        "sch_e_property_b_taxes":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line16[0].f1_56[0]",
        "sch_e_property_b_utilities":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_59[0]",
        "sch_e_property_b_depreciation":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_62[0]",
        "sch_e_property_b_other_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line19[0].f1_66[0]",
        "sch_e_property_b_total_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_69[0]",
        "sch_e_property_b_income_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_72[0]",
        "sch_e_property_b_deductible_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line22[0].f1_75[0]",
        # Property column C, lines 1a-22.
        "sch_e_property_c_address":
            "topmostSubform[0].Page1[0].Line1[0].Table1a[0].RowC[0].f1_5[0]",
        "sch_e_property_c_type_code":
            "topmostSubform[0].Page1[0].Line1[0].Table1b[0].RowC[0].f1_8[0]",
        "sch_e_property_c_fair_rental_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowC[0].f1_13[0]",
        "sch_e_property_c_personal_use_days":
            "topmostSubform[0].Page1[0].Table_Line2[0].RowC[0].f1_14[0]",
        "sch_e_property_c_rents":
            "topmostSubform[0].Page1[0].Table_Income[0].Income[0].Line3[0].f1_18[0]",
        "sch_e_property_c_advertising":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line5[0].f1_24[0]",
        "sch_e_property_c_auto_and_travel":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line6[0].f1_27[0]",
        "sch_e_property_c_cleaning_and_maintenance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line7[0].f1_30[0]",
        "sch_e_property_c_commissions":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line8[0].f1_33[0]",
        "sch_e_property_c_insurance":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line9[0].f1_36[0]",
        "sch_e_property_c_legal_and_professional_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line10[0].f1_39[0]",
        "sch_e_property_c_management_fees":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line11[0].f1_42[0]",
        "sch_e_property_c_mortgage_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line12[0].f1_45[0]",
        "sch_e_property_c_other_interest":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line13[0].f1_48[0]",
        "sch_e_property_c_repairs":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line14[0].f1_51[0]",
        "sch_e_property_c_supplies":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line15[0].f1_54[0]",
        "sch_e_property_c_taxes":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line16[0].f1_57[0]",
        "sch_e_property_c_utilities":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_60[0]",
        "sch_e_property_c_depreciation":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_63[0]",
        "sch_e_property_c_other_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line19[0].f1_67[0]",
        "sch_e_property_c_total_expenses":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_70[0]",
        "sch_e_property_c_income_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_73[0]",
        "sch_e_property_c_deductible_loss":
            "topmostSubform[0].Page1[0].Table_Expenses[0].Line22[0].f1_76[0]",
        **_TOTALS_BLOCK,
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
        # Line 41 grand total (line 26 + line 32) -> f2_69 (verified line 41 on
        # the 2021 template); binds the grand-total key, not the pte subtotal.
        "sch_e_line_41_total_income": "topmostSubform[0].Page2[0].f2_69[0]",
    },
    "repeaters": {},
}


# Page 1 lines A and B (the Form 1099 questions), federal TY2022-2025. Yes box
# left (export /1), No box right (export /2), one two-widget checkbox group per
# line (c1_1 = line A, c1_2 = line B). Verified separately against the 2022,
# 2023, 2024 and 2025 templates (widget Rects and the printed Yes/No caption
# positions agree and are identical in those years). The 2021 template has
# different geometry and is out of scope.
_P1 = "topmostSubform[0].Page1[0]."
_Q1099_CELLS: dict[str, dict[bool, tuple[str, str]]] = {
    "payments_requiring_1099s": {
        True: (_P1 + "c1_1[0]", "/1"), False: (_P1 + "c1_1[1]", "/2")},
    "filed_required_1099s": {
        True: (_P1 + "c1_2[0]", "/1"), False: (_P1 + "c1_2[1]", "/2")},
}
_Q1099_BY_YEAR: dict[int, dict[str, dict[bool, tuple[str, str]]]] = {
    y: _Q1099_CELLS for y in (2022, 2023, 2024, 2025)}


# Page 2 line 27 ("Are you reporting any loss not allowed in a prior year
# ...?"), federal TY2021-2025: one two-widget checkbox group, c2_1. Yes box
# left (c2_1[0], export /1), No box right (c2_1[1], export /2), each just left
# of its printed caption on line 27's last text row. Same path and on-states
# on all five templates (enumerated per year; the 2021 Rects differ, the
# names do not).
_LINE_27_CELLS: dict[bool, tuple[str, str]] = {
    True: (f"{_P2}.c2_1[0]", "/1"),
    False: (f"{_P2}.c2_1[1]", "/2"),
}
_LINE_27_YEARS = (2021, 2022, 2023, 2024, 2025)


# Page 2 line 28 column (e) "Check if basis computation is required", federal
# TY2022-2025: one checkbox per row, c2_(3,6,9,12), export state /1, inside the
# Table_Line28a-f row subform (same tree in all four years; 2022 pads only
# single-digit TEXT leaves, never checkbox leaves). Position verified by render
# against each year's template. The 2021 template has a different line 28
# table (Table_Line28a-e) and is not mapped.
_BASIS_CELLS: dict[str, tuple[str, str]] = {
    row.lower(): (f"{_T28AF}.Row{row}[0].c2_{3 + 3 * i}[0]", "/1")
    for i, row in enumerate(_ROWS)
}
_BASIS_YEARS = (2022, 2023, 2024, 2025)


class PdfSchE(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule E"

    # 2023's field tree is byte-identical to 2024's (verified: identical
    # AcroForm field-path sets), so one payload serves all three years. 2022
    # zero-pads single-digit text-field leaves (see _to_2022).
    _MAPPINGS: dict[int, dict] = {
        2021: _FIELDS_2021,
        2022: _FIELDS_2022, 2023: _FIELDS, 2024: _FIELDS, 2025: _FIELDS}

    @classmethod
    def get_line_27_cells(cls, year: int) -> dict[bool, tuple[str, str]]:
        """{answer: (field_path, on_state)} for the line 27 Yes/No pair.
        Additive to the value mapping, like the line A/B cells: the
        orchestrator writes only the chosen answer's on-state."""
        if year not in _LINE_27_YEARS:
            raise ValueError(
                f"No Schedule E line 27 (prior-year unallowed loss question) "
                f"cells for year {year}")
        return _LINE_27_CELLS

    @classmethod
    def get_basis_computation_cells(
        cls, year: int,
    ) -> dict[str, tuple[str, str]]:
        """{row letter: (field_path, on_state)} for line 28 column (e).
        Additive to the value mapping, like the line A/B cells: the
        orchestrator writes the on-state only for rows whose compute carries
        ``sch_e_part_ii_row_<letter>_basis_computation_required``."""
        if year not in _BASIS_YEARS:
            raise NotImplementedError(
                f"Schedule E line 28 column (e) (basis computation required) "
                f"is not mapped for tax year {year}; an S corporation K-1 "
                f"loss must check it, so this Schedule E cannot be emitted. "
                f"The compute path still produces the numbers; complete the "
                f"form by hand.")
        return _BASIS_CELLS

    @classmethod
    def get_1099_question_cells(
        cls, year: int,
    ) -> dict[str, dict[bool, tuple[str, str]]]:
        """{question: {answer: (field_path, on_state)}} for lines A
        (``payments_requiring_1099s``) and B (``filed_required_1099s``).
        Additive to the value mapping: the orchestrator writes only the CHOSEN
        answer's on-state, so a Yes/No pair can never carry two marks."""
        if year not in _Q1099_BY_YEAR:
            raise ValueError(
                f"No Schedule E line A/B (1099 question) cells for year {year}")
        return _Q1099_BY_YEAR[year]
