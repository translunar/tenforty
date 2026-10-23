from typing import NamedTuple

from tenforty.mappings.registry import FormMapping


# Form 8949 XLS row slots: each subsection box gets 11 lot rows on its sheet.
# The input columns (AJ=description, AK=date_acquired, etc.) are the same in
# both years; only the row_base and checkbox_cell differ by year.
#
# 2025 layout: ST lot rows start at 41, LT lot rows start at 91.
# 2024 layout: ST lot rows start at 35, LT lot rows start at 88.
#   (The 2024 workbook has more physical lot rows — 20 ST, 28 LT — but we
#   only need 11 rows for the parity battery, which uses at most 1 lot.)
#
# Boxes C/F ("no 1099-B received") are out of scope — Form1099B implies a
# 1099-B was received.
_F8949_LOT_ROWS = 11
_F8949_LOT_COLS = {
    "description":       "AJ",
    "date_acquired":     "AK",
    "date_sold":         "AL",
    "proceeds":          "AM",
    "basis":             "AN",
    "adjustment_code":   "AO",
    "adjustment_amount": "AP",
}


class _F8949BoxSlot(NamedTuple):
    letter: str
    sheet: str
    row_base: int        # first lot data row for this box's section
    checkbox_cell: str   # per-box "X" gate read by Sch. D rollup formulas


# 2025: ST Part I lot rows start at 41, LT Part II lot rows start at 91.
# LT checkboxes (Box D/E) are at C75/C77.
_F8949_BOX_SLOTS_2025: tuple[_F8949BoxSlot, ...] = (
    _F8949BoxSlot("a", "8949A", 41, "C25"),  # short-term, basis reported
    _F8949BoxSlot("b", "8949B", 41, "C27"),  # short-term, basis not reported
    _F8949BoxSlot("d", "8949A", 91, "C75"),  # long-term,  basis reported
    _F8949BoxSlot("e", "8949B", 91, "C77"),  # long-term,  basis not reported
)

# 2024: ST Part I lot rows start at 35, LT Part II lot rows start at 88.
# LT checkboxes (Box D/E) are at C78/C80 in the 2024 workbook layout.
_F8949_BOX_SLOTS_2024: tuple[_F8949BoxSlot, ...] = (
    _F8949BoxSlot("a", "8949A", 35, "C25"),  # short-term, basis reported
    _F8949BoxSlot("b", "8949B", 35, "C27"),  # short-term, basis not reported
    _F8949BoxSlot("d", "8949A", 88, "C78"),  # long-term,  basis reported
    _F8949BoxSlot("e", "8949B", 88, "C80"),  # long-term,  basis not reported
)

# Backward-compatible alias (used by existing callers that don't pass a year).
_F8949_BOX_SLOTS = _F8949_BOX_SLOTS_2025


def _f8949_box_inputs(slot: _F8949BoxSlot) -> dict[str, str]:
    out: dict[str, str] = {}
    out[f"f8949_box_{slot.letter}_checkbox"] = slot.checkbox_cell
    for i in range(_F8949_LOT_ROWS):
        idx = i + 1
        row = slot.row_base + i
        for field, col in _F8949_LOT_COLS.items():
            out[f"f8949_box_{slot.letter}_lot_{idx}_{field}"] = f"{col}{row}"
    return out


def _f8949_box_sheet_map(slot: _F8949BoxSlot) -> dict[str, str]:
    out: dict[str, str] = {}
    out[f"f8949_box_{slot.letter}_checkbox"] = slot.sheet
    for i in range(_F8949_LOT_ROWS):
        idx = i + 1
        for field in _F8949_LOT_COLS:
            out[f"f8949_box_{slot.letter}_lot_{idx}_{field}"] = slot.sheet
    return out


def _f8949_all_inputs(slots: tuple = _F8949_BOX_SLOTS_2025) -> dict[str, str]:
    out: dict[str, str] = {}
    for slot in slots:
        out |= _f8949_box_inputs(slot)
    return out


def _f8949_all_sheet_map(slots: tuple = _F8949_BOX_SLOTS_2025) -> dict[str, str]:
    out: dict[str, str] = {}
    for slot in slots:
        out |= _f8949_box_sheet_map(slot)
    return out


# Form 8962 (Premium Tax Credit) monthly-grid rows: Part II "Monthly
# Calculation" (lines 12-23, Jan..Dec). Columns are IDENTICAL across all 5
# years — (a) enrollment premium = G, (b) SLCSP = L, (f) APTC = AF — verified
# ALL-blank/writable on the '8962' sheet for every year. Only the ROW range
# drifts (docs/plans/f8962-probe-tables.md, 'Workbook 8962-tab layout' recon).
_F8962_ROWS_2021 = tuple(range(52, 64))
_F8962_ROWS_2022_2024 = tuple(range(48, 60))
_F8962_ROWS_2025 = tuple(range(50, 62))

_F8962_MONTH_COLS = {
    "premium": "G",
    "slcsp": "L",
    "aptc": "AF",
}


def _f8962_inputs(rows: tuple) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, row in enumerate(rows):
        n = i + 1
        for field, col in _F8962_MONTH_COLS.items():
            out[f"f8962_month_{n}_{field}"] = f"{col}{row}"
    return out


def _f8962_sheet_map(rows: tuple) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(len(rows)):
        n = i + 1
        for field in _F8962_MONTH_COLS:
            out[f"f8962_month_{n}_{field}"] = "8962"
    return out


class _Probe(NamedTuple):
    """A 2025 workbook cell read only to refuse on text (see below)."""
    sheet: str
    cell: str
    defined_name: str   # "" when the cell has none; " / "-joined if several


# --- Workbook numeric-cell probes (2025) -------------------------------------
#
# Cells whose healthy value is a NUMBER (or blank) but which can hold a
# plain-English diagnostic ("Filing status?", "Answer question.", ...) that a
# downstream SUM/MIN/arithmetic then silently skips -- the partial-total
# species. Each is harvested ONLY so forms/f1040.py::workbook_probe_refusal can
# refuse when it holds non-empty text or an error marker; there is no string
# allowlist (a numeric cell's allowlist is empty). Read by cell address via
# SHEET_MAP; a defined name, where one exists, is recorded for the refusal
# text, not used to resolve.
#
# The set is mechanical (workbook-health-2025, team-lead ruled 2026-10-14):
# the string-yielding formula cells downstream of a filing-status / spouse /
# HoH input whose text can reach a harvested OUTPUT through a numeric
# consumption position (docs/plans/2026-10-13-briefs/workbook-health-2025-
# numeric-cut.md, gitignored), less three cells recorded-not-harvested
# because they hold text in normal operation and every numeric consumer is
# behind a textual guard: 'Line 6ab (SS Bene)'!L23, '2441'!V111,
# 'Sch. 1, Line 20 (IRA)'!Q21.
#
# DISPATCH-FAMILY MEMBERSHIP CORRECTION (team-lead ruling after the step-3
# probe-value dump; 73 - 29 - 3 = 41 probes). The 'Line 16 (QDCG Tax)' and
# 'Sch. D WS' tax worksheets (and '1040'!BI99/BI100) compute tax twice per
# status -- a Tax Table LOOKUP and a schedule that prints "---" below its
# floor -- and a selector IF(income>100000, ROUND(schedule), ROUND(table))
# picks one. On a worksheet the return does not use, the income operand is
# "", so the unchosen and unused cells hold "---" / "#N/A" / "#VALUE!" on
# EVERY return; their real guard is the worksheet-used flag (CGTW /
# SchDTW_Used / FEI_Tax_Worksheet), not the threshold. Removed: the 29 cells
# texty on every workbook row of the dump, plus the three table-side
# dispatch cells of the same structure ('1040'!BI99, QDCG U164, W105) --
# losing nothing, because the kept selectors read them inside ROUND, so real
# table corruption still surfaces as an error in a kept probe. Kept: the
# selector '1040'!BM100 (its operand Taxable_Inc is always numeric) and every
# gated pass-through/selector that reads "" when its worksheet is unused --
# the only detection left for text on a worksheet that IS in use. This is a
# MEMBERSHIP correction on structural + empirical grounds, NOT a string
# allowlist: "---" and "#N/A" still refuse in every probe that remains.
# Evidence: docs/plans/2026-10-13-briefs/workbook-health-2025-numeric-cut.md.
# Pinned by tests/test_workbook_probes.py.
WORKBOOK_PROBES_2025: dict[str, _Probe] = {
    # --- 1040 ---
    "workbook_probe__1040__al71": _Probe("1040", "AL71", "SocSecBenefits_Taxable"),
    "workbook_probe__1040__bm100": _Probe("1040", "BM100", ""),
    # --- 6251 ---
    "workbook_probe__6251__ac27": _Probe("6251", "AC27", ""),
    "workbook_probe__6251__ac39": _Probe("6251", "AC39", ""),
    "workbook_probe__6251__m89": _Probe("6251", "M89", ""),
    "workbook_probe__6251__m95": _Probe("6251", "M95", ""),
    "workbook_probe__6251__m102": _Probe("6251", "M102", ""),
    "workbook_probe__6251__m104": _Probe("6251", "M104", ""),
    "workbook_probe__6251__m111": _Probe("6251", "M111", ""),
    # --- 8582 ---
    "workbook_probe__8582__at18": _Probe("8582", "AT18", ""),
    "workbook_probe__8582__x33": _Probe("8582", "X33", ""),
    # --- 8812 ---
    "workbook_probe__8812__al30": _Probe("8812", "AL30", ""),
    # --- 8863 ---
    "workbook_probe__8863__x16": _Probe("8863", "X16", ""),
    # --- 8959 ---
    "workbook_probe__8959__k24": _Probe("8959", "K24", ""),
    "workbook_probe__8959__k34": _Probe("8959", "K34", ""),
    "workbook_probe__8959__k46": _Probe("8959", "K46", ""),
    # --- 8960 ---
    "workbook_probe__8960__l44": _Probe("8960", "L44", ""),
    # --- Line 16 (QDCG Tax) ---
    "workbook_probe__line_16_qdcg_tax__n67": _Probe("Line 16 (QDCG Tax)", "N67", ""),
    "workbook_probe__line_16_qdcg_tax__n71": _Probe("Line 16 (QDCG Tax)", "N71", "CGTW_Line24"),
    "workbook_probe__line_16_qdcg_tax__n95": _Probe("Line 16 (QDCG Tax)", "N95", ""),
    "workbook_probe__line_16_qdcg_tax__n99": _Probe("Line 16 (QDCG Tax)", "N99", ""),
    "workbook_probe__line_16_qdcg_tax__aa106": _Probe("Line 16 (QDCG Tax)", "AA106", ""),
    "workbook_probe__line_16_qdcg_tax__v111": _Probe("Line 16 (QDCG Tax)", "V111", ""),
    "workbook_probe__line_16_qdcg_tax__x131": _Probe("Line 16 (QDCG Tax)", "X131", ""),
    "workbook_probe__line_16_qdcg_tax__x142": _Probe("Line 16 (QDCG Tax)", "X142", ""),
    "workbook_probe__line_16_qdcg_tax__x160": _Probe("Line 16 (QDCG Tax)", "X160", ""),
    "workbook_probe__line_16_qdcg_tax__y165": _Probe("Line 16 (QDCG Tax)", "Y165", ""),
    # --- Line 6ab (SS Bene) ---
    "workbook_probe__line_6ab_ss_bene__l29": _Probe("Line 6ab (SS Bene)", "L29", ""),
    "workbook_probe__line_6ab_ss_bene__l49": _Probe("Line 6ab (SS Bene)", "L49", "Tax_SS_Benefits"),
    # --- Sch. 1, Line 21 (Stu Loan) ---
    "workbook_probe__sch_1_line_21_stu_loan__j20": _Probe("Sch. 1, Line 21 (Stu Loan)", "J20", ""),
    # --- Sch. 1-A ---
    # VENDOR BUG (not a diagnostic): AU30 reads 'W-2s'!F$39 -- the
    # "Spouse's Employer #4" CAPTION -- where every sibling row (AU27-AU29,
    # AU31-AU32) reads the row-46 SS-tips amount; AY30 passes it on, and the
    # AV33/AY33 SUMs skip the text, dropping that employer's tips from the
    # qualified-tips total. Healthy value is "" or a number; the caption is
    # exactly the corrupting value. NEVER allowlist it.
    "workbook_probe__sch_1_a__au30": _Probe("Sch. 1-A", "AU30", ""),
    "workbook_probe__sch_1_a__ay30": _Probe("Sch. 1-A", "AY30", ""),
    # --- Sch. A ---
    "workbook_probe__sch_a__ai10": _Probe("Sch. A", "AI10", ""),
    # --- Sch. D WS ---
    "workbook_probe__sch_d_ws__l91": _Probe("Sch. D WS", "L91", "SchDTW_Line15"),
    "workbook_probe__sch_d_ws__l92": _Probe("Sch. D WS", "L92", ""),
    "workbook_probe__sch_d_ws__l98": _Probe("Sch. D WS", "L98", "SchDTW_Line19"),
    "workbook_probe__sch_d_ws__l110": _Probe("Sch. D WS", "L110", "SchDTW_Line24 / SchDTW_Line26"),
    "workbook_probe__sch_d_ws__l111": _Probe("Sch. D WS", "L111", ""),
    "workbook_probe__sch_d_ws__r134": _Probe("Sch. D WS", "R134", ""),
    "workbook_probe__sch_d_ws__r137": _Probe("Sch. D WS", "R137", ""),
    # --- Sch. SE ---
    "workbook_probe__sch_se__x20": _Probe("Sch. SE", "X20", ""),
}

# --- Workbook numeric-cell probes (2024) -------------------------------------
#
# Same purpose and semantics as WORKBOOK_PROBES_2025 above; keys carry the year
# (`workbook_probe__y2024__...`) because several cells are probes in both years
# at different meanings/addresses. Set (workbook-health-2024, team-lead ruled
# 2026-10-15; docs/plans/2026-10-13-briefs/workbook-health-2024-numeric-cut.md,
# gitignored): the 77 numeric-path cells of the 2024 inventory, less
#   * 32 DISPATCH-FAMILY cells (QDCG / Sch. D WS table-vs-schedule dispatch,
#     unused-worksheet selectors and their bare pass-throughs, the 1040 pair
#     AY78/AY79) -- removed by a STRUCTURAL rule that reproduces 2025's
#     dump-ruled removal exactly (32 = 32). For 2024 this is a PREDICTION: the
#     empirical confirmation is team-lead's 2024 probe dump + oracle run, and a
#     single texty value among these 39 on a computing row reopens the set;
#   * 6 RECORDED-NOT-HARVESTED cells holding text in normal operation behind a
#     textual/ISERROR guard: 'Line 6ab (SS Bene)'!J28 "Stop", '2441'!V112
#     "STOP", 'Sch. 1, Line 20 (IRA)'!Q22 "Age > 70 1/2", and '1099-R'!O32 /
#     '8606'!AE76 / '8606'!AE185 (the "- - - -" sentinel, text on EVERY
#     return). As in 2025 this is a MEMBERSHIP decision, not a string
#     allowlist: any text in a remaining probe refuses.
WORKBOOK_PROBES_2024: dict[str, _Probe] = {
    # --- 1040 ---
    "workbook_probe__y2024__1040__ad60": _Probe("1040", "AD60", "SocSecBenefits_Taxable"),
    "workbook_probe__y2024__1040__bc79": _Probe("1040", "BC79", ""),
    # --- 6251 ---
    "workbook_probe__y2024__6251__ac26": _Probe("6251", "AC26", ""),
    "workbook_probe__y2024__6251__ac38": _Probe("6251", "AC38", ""),
    "workbook_probe__y2024__6251__m88": _Probe("6251", "M88", ""),
    "workbook_probe__y2024__6251__m94": _Probe("6251", "M94", ""),
    "workbook_probe__y2024__6251__m101": _Probe("6251", "M101", ""),
    "workbook_probe__y2024__6251__m103": _Probe("6251", "M103", ""),
    "workbook_probe__y2024__6251__m110": _Probe("6251", "M110", ""),
    # --- 8582 ---
    "workbook_probe__y2024__8582__at18": _Probe("8582", "AT18", ""),
    "workbook_probe__y2024__8582__x33": _Probe("8582", "X33", ""),
    # --- 8812 ---
    "workbook_probe__y2024__8812__al30": _Probe("8812", "AL30", ""),
    # --- 8863 ---
    "workbook_probe__y2024__8863__x16": _Probe("8863", "X16", ""),
    # --- 8959 ---
    "workbook_probe__y2024__8959__k24": _Probe("8959", "K24", ""),
    "workbook_probe__y2024__8959__k34": _Probe("8959", "K34", ""),
    "workbook_probe__y2024__8959__k46": _Probe("8959", "K46", ""),
    # --- 8960 ---
    "workbook_probe__y2024__8960__l44": _Probe("8960", "L44", ""),
    # --- Line 16 (QDCG Tax) ---
    "workbook_probe__y2024__line_16_qdcg_tax__n65": _Probe("Line 16 (QDCG Tax)", "N65", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__n69": _Probe("Line 16 (QDCG Tax)", "N69", "CGTW_Line24"),
    "workbook_probe__y2024__line_16_qdcg_tax__n93": _Probe("Line 16 (QDCG Tax)", "N93", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__n97": _Probe("Line 16 (QDCG Tax)", "N97", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__aa104": _Probe("Line 16 (QDCG Tax)", "AA104", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__v109": _Probe("Line 16 (QDCG Tax)", "V109", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__x129": _Probe("Line 16 (QDCG Tax)", "X129", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__x140": _Probe("Line 16 (QDCG Tax)", "X140", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__x158": _Probe("Line 16 (QDCG Tax)", "X158", ""),
    "workbook_probe__y2024__line_16_qdcg_tax__y163": _Probe("Line 16 (QDCG Tax)", "Y163", ""),
    # --- Line 6ab (SS Bene) ---
    "workbook_probe__y2024__line_6ab_ss_bene__j34": _Probe("Line 6ab (SS Bene)", "J34", ""),
    "workbook_probe__y2024__line_6ab_ss_bene__j54": _Probe("Line 6ab (SS Bene)", "J54", "Tax_SS_Benefits"),
    # --- Sch. 1, Line 21 (Stu Loan) ---
    "workbook_probe__y2024__sch_1_line_21_stu_loan__j20": _Probe("Sch. 1, Line 21 (Stu Loan)", "J20", ""),
    # --- Sch. A ---
    "workbook_probe__y2024__sch_a__ai10": _Probe("Sch. A", "AI10", ""),
    # --- Sch. D WS ---
    "workbook_probe__y2024__sch_d_ws__l91": _Probe("Sch. D WS", "L91", "SchDTW_Line15"),
    "workbook_probe__y2024__sch_d_ws__l92": _Probe("Sch. D WS", "L92", ""),
    "workbook_probe__y2024__sch_d_ws__l98": _Probe("Sch. D WS", "L98", "SchDTW_Line19"),
    "workbook_probe__y2024__sch_d_ws__l110": _Probe("Sch. D WS", "L110", "SchDTW_Line24 / SchDTW_Line26"),
    "workbook_probe__y2024__sch_d_ws__l111": _Probe("Sch. D WS", "L111", ""),
    "workbook_probe__y2024__sch_d_ws__p134": _Probe("Sch. D WS", "P134", ""),
    "workbook_probe__y2024__sch_d_ws__p137": _Probe("Sch. D WS", "P137", ""),
    # --- Sch. SE ---
    "workbook_probe__y2024__sch_se__x20": _Probe("Sch. SE", "X20", ""),
}

# --- Workbook numeric-cell probes (2023) -------------------------------------
#
# Same purpose and semantics as WORKBOOK_PROBES_2025/2024; keys carry the year
# (`workbook_probe__y2023__...`). Set (workbook-health-2023, team-lead ruled
# 2026-10-15; docs/plans/2026-10-13-briefs/workbook-health-2023-numeric-cut.md,
# gitignored): 77 numeric-path cells of the 2023 inventory, less
#   * 32 DISPATCH-FAMILY cells, removed by the same STRUCTURAL rule as 2024
#     (generalized for 2023's bare `IF(income>100000, schedule, table)`
#     selector -- no NumFileStatusBoxes guard, no ROUND -- and re-validated:
#     2025's dump-ruled removal still reproduced exactly, no merged 2024
#     probe changes class). For 2023 a PREDICTION until team-lead's 2023
#     probe dump + battery run; one texty value among these 39 on a computing
#     row reopens the set. Floor note: 2023's Section A schedule tests
#     SectA_a3 for its "---" floor where Sections B-D test SectX_a2 (2024/2025
#     use a2 throughout); every floor VALUE is 100,000 = the selector
#     threshold (verified), so a kept selector's chosen side is numeric;
#   * 6 RECORDED-NOT-HARVESTED cells, exactly the 2024-ratified species:
#     'Line 6ab (SS Bene)'!J25 "Stop", '2441'!V112 "STOP",
#     'Sch. 1, Line 20 (IRA)'!Q22 "Age > 70 1/2", and the "- - - -" sentinel
#     cells '1099-R'!O32 / '8606'!AE76 / '8606'!AE184. Membership, not a
#     string allowlist: any text in a remaining probe refuses.
WORKBOOK_PROBES_2023: dict[str, _Probe] = {
    # --- 1040 ---
    "workbook_probe__y2023__1040__ad57": _Probe("1040", "AD57", "SocSecBenefits_Taxable"),
    "workbook_probe__y2023__1040__bc76": _Probe("1040", "BC76", ""),
    # --- 6251 ---
    "workbook_probe__y2023__6251__ac26": _Probe("6251", "AC26", ""),
    "workbook_probe__y2023__6251__ac38": _Probe("6251", "AC38", ""),
    "workbook_probe__y2023__6251__m88": _Probe("6251", "M88", ""),
    "workbook_probe__y2023__6251__m94": _Probe("6251", "M94", ""),
    "workbook_probe__y2023__6251__m101": _Probe("6251", "M101", ""),
    "workbook_probe__y2023__6251__m103": _Probe("6251", "M103", ""),
    "workbook_probe__y2023__6251__m110": _Probe("6251", "M110", ""),
    # --- 8582 ---
    "workbook_probe__y2023__8582__at18": _Probe("8582", "AT18", ""),
    "workbook_probe__y2023__8582__x33": _Probe("8582", "X33", ""),
    # --- 8812 ---
    "workbook_probe__y2023__8812__al30": _Probe("8812", "AL30", ""),
    # --- 8863 ---
    "workbook_probe__y2023__8863__x16": _Probe("8863", "X16", ""),
    # --- 8959 ---
    "workbook_probe__y2023__8959__k24": _Probe("8959", "K24", ""),
    "workbook_probe__y2023__8959__k34": _Probe("8959", "K34", ""),
    "workbook_probe__y2023__8959__k46": _Probe("8959", "K46", ""),
    # --- 8960 ---
    "workbook_probe__y2023__8960__l44": _Probe("8960", "L44", ""),
    # --- Line 16 (QDCG Tax) ---
    "workbook_probe__y2023__line_16_qdcg_tax__n65": _Probe("Line 16 (QDCG Tax)", "N65", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__n69": _Probe("Line 16 (QDCG Tax)", "N69", "CGTW_Line24"),
    "workbook_probe__y2023__line_16_qdcg_tax__n93": _Probe("Line 16 (QDCG Tax)", "N93", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__n97": _Probe("Line 16 (QDCG Tax)", "N97", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__aa104": _Probe("Line 16 (QDCG Tax)", "AA104", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__v109": _Probe("Line 16 (QDCG Tax)", "V109", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__x129": _Probe("Line 16 (QDCG Tax)", "X129", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__x140": _Probe("Line 16 (QDCG Tax)", "X140", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__x158": _Probe("Line 16 (QDCG Tax)", "X158", ""),
    "workbook_probe__y2023__line_16_qdcg_tax__y163": _Probe("Line 16 (QDCG Tax)", "Y163", ""),
    # --- Line 6ab (SS Bene) ---
    "workbook_probe__y2023__line_6ab_ss_bene__j31": _Probe("Line 6ab (SS Bene)", "J31", ""),
    "workbook_probe__y2023__line_6ab_ss_bene__j51": _Probe("Line 6ab (SS Bene)", "J51", "Tax_SS_Benefits"),
    # --- Sch. 1, Line 21 (Stu Loan) ---
    "workbook_probe__y2023__sch_1_line_21_stu_loan__j20": _Probe("Sch. 1, Line 21 (Stu Loan)", "J20", ""),
    # --- Sch. A ---
    "workbook_probe__y2023__sch_a__ah10": _Probe("Sch. A", "AH10", ""),
    # --- Sch. D WS ---
    "workbook_probe__y2023__sch_d_ws__l91": _Probe("Sch. D WS", "L91", "SchDTW_Line15"),
    "workbook_probe__y2023__sch_d_ws__l92": _Probe("Sch. D WS", "L92", ""),
    "workbook_probe__y2023__sch_d_ws__l98": _Probe("Sch. D WS", "L98", "SchDTW_Line19"),
    "workbook_probe__y2023__sch_d_ws__l110": _Probe("Sch. D WS", "L110", "SchDTW_Line24 / SchDTW_Line26"),
    "workbook_probe__y2023__sch_d_ws__l111": _Probe("Sch. D WS", "L111", ""),
    "workbook_probe__y2023__sch_d_ws__p134": _Probe("Sch. D WS", "P134", ""),
    "workbook_probe__y2023__sch_d_ws__p137": _Probe("Sch. D WS", "P137", ""),
    # --- Sch. SE ---
    "workbook_probe__y2023__sch_se__x20": _Probe("Sch. SE", "X20", ""),
}

# --- Workbook numeric-cell probes (2022) -------------------------------------
#
# Same purpose and semantics as WORKBOOK_PROBES_2025/2024/2023; keys carry the
# year (`workbook_probe__y2022__...`). Set (workbook-health-2022, team-lead
# ruled 2026-10-15; docs/plans/2026-10-13-briefs/workbook-health-2022-numeric-
# cut.md, gitignored): 74 numeric-path cells of the 2022 inventory, less
#   * 32 DISPATCH-FAMILY cells, removed by the same STRUCTURAL rule as 2023
#     (2022 has 2023's bare `IF(income>100000, schedule, table)` selector;
#     rule applied unchanged). For 2022 a PREDICTION until team-lead's 2022
#     probe dump + battery run; one texty value among these 38 on a computing
#     row reopens the set. Floors as 2023: Section A tests SectA_a3, B-D
#     SectX_a2, every floor VALUE 100,000 = the selector threshold (verified);
#   * 4 RECORDED-NOT-HARVESTED cells: the three ratified species
#     'Line 6ab (SS Bene)'!J25 "Stop", '2441'!V116 "STOP",
#     'Sch. 1, Line 20 (IRA)'!Q22 "Age > 70 1/2" (2022 has no "- - - -"
#     sentinel cells), plus '6251'!P2, a display prompt that holds text in
#     normal operation. P2's only numeric consumer is a 2022-only VENDOR BUG:
#     '6251'!M22's override branch rounds P2 instead of its own override input
#     P22 (2021/2023/2024/2025 each round their own input). Reached only when
#     P22 is non-empty, which tenforty never writes. TRIPWIRE: if 2022 6251
#     override support ever lands, M22 computes from the wrong cell -- revisit
#     this probe/refusal design then. Membership, not a string allowlist: any
#     text in a remaining probe refuses.
WORKBOOK_PROBES_2022: dict[str, _Probe] = {
    # --- 1040 ---
    "workbook_probe__y2022__1040__ac51": _Probe("1040", "AC51", "SocSecBenefits_Taxable"),
    "workbook_probe__y2022__1040__bb70": _Probe("1040", "BB70", ""),
    # --- 6251 ---
    "workbook_probe__y2022__6251__ac26": _Probe("6251", "AC26", ""),
    "workbook_probe__y2022__6251__ac38": _Probe("6251", "AC38", ""),
    "workbook_probe__y2022__6251__m88": _Probe("6251", "M88", ""),
    "workbook_probe__y2022__6251__m94": _Probe("6251", "M94", ""),
    "workbook_probe__y2022__6251__m101": _Probe("6251", "M101", ""),
    "workbook_probe__y2022__6251__m103": _Probe("6251", "M103", ""),
    "workbook_probe__y2022__6251__m110": _Probe("6251", "M110", ""),
    # --- 8582 ---
    "workbook_probe__y2022__8582__at18": _Probe("8582", "AT18", ""),
    # --- 8812 ---
    "workbook_probe__y2022__8812__al28": _Probe("8812", "AL28", ""),
    # --- 8863 ---
    "workbook_probe__y2022__8863__x16": _Probe("8863", "X16", ""),
    # --- 8959 ---
    "workbook_probe__y2022__8959__k24": _Probe("8959", "K24", ""),
    "workbook_probe__y2022__8959__k34": _Probe("8959", "K34", ""),
    "workbook_probe__y2022__8959__k46": _Probe("8959", "K46", ""),
    # --- 8960 ---
    "workbook_probe__y2022__8960__l44": _Probe("8960", "L44", ""),
    # --- Line 16 (QDCG Tax) ---
    "workbook_probe__y2022__line_16_qdcg_tax__n64": _Probe("Line 16 (QDCG Tax)", "N64", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__n68": _Probe("Line 16 (QDCG Tax)", "N68", "CGTW_Line24"),
    "workbook_probe__y2022__line_16_qdcg_tax__n92": _Probe("Line 16 (QDCG Tax)", "N92", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__n96": _Probe("Line 16 (QDCG Tax)", "N96", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__aa104": _Probe("Line 16 (QDCG Tax)", "AA104", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__v109": _Probe("Line 16 (QDCG Tax)", "V109", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__x129": _Probe("Line 16 (QDCG Tax)", "X129", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__x140": _Probe("Line 16 (QDCG Tax)", "X140", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__x158": _Probe("Line 16 (QDCG Tax)", "X158", ""),
    "workbook_probe__y2022__line_16_qdcg_tax__y163": _Probe("Line 16 (QDCG Tax)", "Y163", ""),
    # --- Line 6ab (SS Bene) ---
    "workbook_probe__y2022__line_6ab_ss_bene__j31": _Probe("Line 6ab (SS Bene)", "J31", ""),
    "workbook_probe__y2022__line_6ab_ss_bene__j51": _Probe("Line 6ab (SS Bene)", "J51", "Tax_SS_Benefits"),
    # --- Sch. 1, Line 21 (Stu Loan) ---
    "workbook_probe__y2022__sch_1_line_21_stu_loan__j20": _Probe("Sch. 1, Line 21 (Stu Loan)", "J20", ""),
    # --- Sch. A ---
    "workbook_probe__y2022__sch_a__ah10": _Probe("Sch. A", "AH10", ""),
    # --- Sch. D WS ---
    "workbook_probe__y2022__sch_d_ws__l91": _Probe("Sch. D WS", "L91", "SchDTW_Line15"),
    "workbook_probe__y2022__sch_d_ws__l92": _Probe("Sch. D WS", "L92", ""),
    "workbook_probe__y2022__sch_d_ws__l98": _Probe("Sch. D WS", "L98", "SchDTW_Line19"),
    "workbook_probe__y2022__sch_d_ws__l110": _Probe("Sch. D WS", "L110", "SchDTW_Line24 / SchDTW_Line26"),
    "workbook_probe__y2022__sch_d_ws__l111": _Probe("Sch. D WS", "L111", ""),
    "workbook_probe__y2022__sch_d_ws__p134": _Probe("Sch. D WS", "P134", ""),
    "workbook_probe__y2022__sch_d_ws__p137": _Probe("Sch. D WS", "P137", ""),
    # --- Sch. SE ---
    "workbook_probe__y2022__sch_se__x20": _Probe("Sch. SE", "X20", ""),
}

# --- Workbook numeric-cell probes (2021) -------------------------------------
#
# Same purpose and semantics as WORKBOOK_PROBES_2025/2024/2023/2022; keys carry
# the year (`workbook_probe__y2021__...`). Set (workbook-health-2021, team-lead
# ruled 2026-10-15; docs/plans/2026-10-13-briefs/workbook-health-2021-numeric-
# cut.md, gitignored): 77 numeric-path cells of the 2021 inventory, less
#   * 32 DISPATCH-FAMILY cells, removed by the same STRUCTURAL rule as 2022
#     (2021 has the bare `IF(income>100000, schedule, table)` selector; rule
#     applied unchanged and re-validated on 2022-2025). For 2021 a PREDICTION
#     until team-lead's 2021 probe dump + battery run; one texty value among
#     these 42 on a computing row reopens the set. Floors as 2022: Section A
#     tests SectA_a3, B-D SectX_a2, every floor VALUE 100,000 = the selector
#     threshold (verified);
#   * 3 RECORDED-NOT-HARVESTED cells, the ratified species re-verified on
#     2021's own formulas: 'Line 6ab (SS Bene)'!J25 "Stop", '2441'!R117
#     "STOP" (the 2022 V116 analog), 'Sch. 1, Line 20 (IRA)'!Q22
#     "Age > 70 1/2". 2021 has no "- - - -" sentinel cells and no 6251 P2
#     trigger. The five 2021-only status diagnostics ('Line 30 (Rebate
#     Credit)' AH47/AH66/AH75, '8812' AK163/AK170) are probes (8863 X16
#     precedent). Membership, not a string allowlist: any text in a remaining
#     probe refuses.
WORKBOOK_PROBES_2021: dict[str, _Probe] = {
    # --- 1040 ---
    "workbook_probe__y2021__1040__ac42": _Probe("1040", "AC42", "SocSecBenefits_Taxable"),
    "workbook_probe__y2021__1040__bb55": _Probe("1040", "BB55", ""),
    # --- 6251 ---
    "workbook_probe__y2021__6251__ac25": _Probe("6251", "AC25", ""),
    "workbook_probe__y2021__6251__ac37": _Probe("6251", "AC37", ""),
    "workbook_probe__y2021__6251__m87": _Probe("6251", "M87", ""),
    "workbook_probe__y2021__6251__m93": _Probe("6251", "M93", ""),
    "workbook_probe__y2021__6251__m100": _Probe("6251", "M100", ""),
    "workbook_probe__y2021__6251__m102": _Probe("6251", "M102", ""),
    "workbook_probe__y2021__6251__m109": _Probe("6251", "M109", ""),
    # --- 8812 ---
    "workbook_probe__y2021__8812__al28": _Probe("8812", "AL28", ""),
    "workbook_probe__y2021__8812__ak163": _Probe("8812", "AK163", ""),
    "workbook_probe__y2021__8812__ak170": _Probe("8812", "AK170", ""),
    # --- 8863 ---
    "workbook_probe__y2021__8863__x16": _Probe("8863", "X16", ""),
    # --- 8959 ---
    "workbook_probe__y2021__8959__k24": _Probe("8959", "K24", ""),
    "workbook_probe__y2021__8959__k34": _Probe("8959", "K34", ""),
    "workbook_probe__y2021__8959__k46": _Probe("8959", "K46", ""),
    # --- 8960 ---
    "workbook_probe__y2021__8960__l44": _Probe("8960", "L44", ""),
    # --- Line 16 (QDCG Tax) ---
    "workbook_probe__y2021__line_16_qdcg_tax__n61": _Probe("Line 16 (QDCG Tax)", "N61", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__n65": _Probe("Line 16 (QDCG Tax)", "N65", "CGTW_Line24"),
    "workbook_probe__y2021__line_16_qdcg_tax__n89": _Probe("Line 16 (QDCG Tax)", "N89", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__n93": _Probe("Line 16 (QDCG Tax)", "N93", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__aa101": _Probe("Line 16 (QDCG Tax)", "AA101", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__v106": _Probe("Line 16 (QDCG Tax)", "V106", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__x126": _Probe("Line 16 (QDCG Tax)", "X126", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__x137": _Probe("Line 16 (QDCG Tax)", "X137", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__x155": _Probe("Line 16 (QDCG Tax)", "X155", ""),
    "workbook_probe__y2021__line_16_qdcg_tax__y160": _Probe("Line 16 (QDCG Tax)", "Y160", ""),
    # --- Line 30 (Rebate Credit) ---
    "workbook_probe__y2021__line_30_rebate_credit__ah47": _Probe("Line 30 (Rebate Credit)", "AH47", ""),
    "workbook_probe__y2021__line_30_rebate_credit__ah66": _Probe("Line 30 (Rebate Credit)", "AH66", ""),
    "workbook_probe__y2021__line_30_rebate_credit__ah75": _Probe("Line 30 (Rebate Credit)", "AH75", ""),
    # --- Line 6ab (SS Bene) ---
    "workbook_probe__y2021__line_6ab_ss_bene__j31": _Probe("Line 6ab (SS Bene)", "J31", ""),
    "workbook_probe__y2021__line_6ab_ss_bene__j51": _Probe("Line 6ab (SS Bene)", "J51", "Tax_SS_Benefits"),
    # --- Sch. 1, Line 21 (Stu Loan) ---
    "workbook_probe__y2021__sch_1_line_21_stu_loan__j20": _Probe("Sch. 1, Line 21 (Stu Loan)", "J20", ""),
    # --- Sch. A ---
    "workbook_probe__y2021__sch_a__ah10": _Probe("Sch. A", "AH10", ""),
    # --- Sch. D WS ---
    "workbook_probe__y2021__sch_d_ws__l91": _Probe("Sch. D WS", "L91", "SchDTW_Line15"),
    "workbook_probe__y2021__sch_d_ws__l92": _Probe("Sch. D WS", "L92", ""),
    "workbook_probe__y2021__sch_d_ws__l98": _Probe("Sch. D WS", "L98", "SchDTW_Line19"),
    "workbook_probe__y2021__sch_d_ws__l110": _Probe("Sch. D WS", "L110", "SchDTW_Line24 / SchDTW_Line26"),
    "workbook_probe__y2021__sch_d_ws__l111": _Probe("Sch. D WS", "L111", ""),
    "workbook_probe__y2021__sch_d_ws__p134": _Probe("Sch. D WS", "P134", ""),
    "workbook_probe__y2021__sch_d_ws__p137": _Probe("Sch. D WS", "P137", ""),
    # --- Sch. SE ---
    "workbook_probe__y2021__sch_se__x20": _Probe("Sch. SE", "X20", ""),
}

class F1040(FormMapping):
    """Mapping for the entire federal 1040 workbook (all sheets).

    Input keys use the convention: {form}_{field}_{index}.
    - W-2 fields: w2_{field}_{employer_number} (1-6 supported by XLS)
    - 1099 fields: {form_type}_{field}_{payer_number}
    - Schedule E: sche_{field}_{property_letter}

    Values are either named ranges (e.g., "File_Single") or direct cell
    references on a specific sheet (e.g., "C3" on the W-2s sheet). Named
    ranges are resolved by openpyxl automatically. Direct cell references
    require the sheet name prefix in the engine (stored in SHEET_MAP).
    """

    SHEET_MAP: dict[int, dict[str, str]] = {
        2024: {
            # Form 1040 line 32 (total other payments and refundable
            # credits): unnamed in every year; direct cell ref on 1040.
            "total_other_payments": "1040",
            "w2_wages_1": "W-2s",
            "w2_fed_withheld_1": "W-2s",
            "w2_ss_wages_1": "W-2s",
            "w2_ss_withheld_1": "W-2s",
            "w2_medicare_wages_1": "W-2s",
            "w2_medicare_withheld_1": "W-2s",
            "w2_state_wages_1": "W-2s",
            "w2_state_withheld_1": "W-2s",
            "interest_1": "1099-INT",
            "ordinary_dividends_1": "1099-DIV",
            "qualified_dividends_1": "1099-DIV",
            "capital_gain_distributions_1": "1099-DIV",
            "sche_rents_a": "Sch. E",
            "sche_property_type_a": "Sch. E",
            "sche_fair_rental_days_a": "Sch. E",
            "sche_personal_use_days_a": "Sch. E",
            "sche_advertising_a": "Sch. E",
            "sche_auto_and_travel_a": "Sch. E",
            "sche_cleaning_and_maintenance_a": "Sch. E",
            "sche_commissions_a": "Sch. E",
            "sche_insurance_a": "Sch. E",
            "sche_legal_and_professional_fees_a": "Sch. E",
            "sche_management_fees_a": "Sch. E",
            "sche_mortgage_interest_a": "Sch. E",
            "sche_other_interest_a": "Sch. E",
            "sche_repairs_a": "Sch. E",
            "sche_supplies_a": "Sch. E",
            "sche_taxes_a": "Sch. E",
            "sche_utilities_a": "Sch. E",
            "sche_depreciation_a": "Sch. E",
            "sche_other_expenses_a": "Sch. E",
            "mortgage_interest": "Sch. A",
            "property_tax": "Sch. A",
            "k1_a_entity_name": "Sch. E",
            "k1_a_entity_type_s_corp": "Sch. E",
            "k1_a_entity_type_partnership": "Sch. E",
            "k1_a_entity_ein": "Sch. E",
            "k1_b_entity_name": "Sch. E",
            "k1_b_entity_type_s_corp": "Sch. E",
            "k1_b_entity_type_partnership": "Sch. E",
            "k1_b_entity_ein": "Sch. E",
            "k1_c_entity_name": "Sch. E",
            "k1_c_entity_type_s_corp": "Sch. E",
            "k1_c_entity_type_partnership": "Sch. E",
            "k1_c_entity_ein": "Sch. E",
            "k1_d_entity_name": "Sch. E",
            "k1_d_entity_type_s_corp": "Sch. E",
            "k1_d_entity_type_partnership": "Sch. E",
            "k1_d_entity_ein": "Sch. E",
            "k1_a_passive_loss": "Sch. E",
            "k1_a_passive_income": "Sch. E",
            "k1_a_nonpassive_loss": "Sch. E",
            "k1_a_nonpassive_income": "Sch. E",
            "k1_b_passive_loss": "Sch. E",
            "k1_b_passive_income": "Sch. E",
            "k1_b_nonpassive_loss": "Sch. E",
            "k1_b_nonpassive_income": "Sch. E",
            "k1_c_passive_loss": "Sch. E",
            "k1_c_passive_income": "Sch. E",
            "k1_c_nonpassive_loss": "Sch. E",
            "k1_c_nonpassive_income": "Sch. E",
            "k1_d_passive_loss": "Sch. E",
            "k1_d_passive_income": "Sch. E",
            "k1_d_nonpassive_loss": "Sch. E",
            "k1_d_nonpassive_income": "Sch. E",
            "k1_a_qbi_amount": "8995",
            "k1_b_qbi_amount": "8995",
            "k1_c_qbi_amount": "8995",
            "k1_d_qbi_amount": "8995",
            # SALT refund tax-benefit-rule worksheet (same sheet name in 2024).
            "prior_year_itemized_deduction": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_single": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfj": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfs": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_hoh": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_qw": "Sch 1, Line 1 (SALT)",
            # Form 1099-G
            "g_unemployment_1": "1099-G",
            "g_state_refund_1": "1099-G",
            "g_fed_withheld_1": "1099-G",
            "g_rtaa_1": "1099-G",
            "g_taxable_grants_1": "1099-G",
            "g_ag_1": "1099-G",
            "g_market_gain_1": "1099-G",
            "g_unemployment_2": "1099-G",
            "g_state_refund_2": "1099-G",
            "g_fed_withheld_2": "1099-G",
            "g_rtaa_2": "1099-G",
            "g_taxable_grants_2": "1099-G",
            "g_ag_2": "1099-G",
            "g_market_gain_2": "1099-G",
            "g_unemployment_3": "1099-G",
            "g_state_refund_3": "1099-G",
            "g_fed_withheld_3": "1099-G",
            "g_rtaa_3": "1099-G",
            "g_taxable_grants_3": "1099-G",
            "g_ag_3": "1099-G",
            "g_market_gain_3": "1099-G",
            "g_unemployment_4": "1099-G",
            "g_state_refund_4": "1099-G",
            "g_fed_withheld_4": "1099-G",
            "g_rtaa_4": "1099-G",
            "g_taxable_grants_4": "1099-G",
            "g_ag_4": "1099-G",
            "g_market_gain_4": "1099-G",
            "g_unemployment_5": "1099-G",
            "g_state_refund_5": "1099-G",
            "g_fed_withheld_5": "1099-G",
            "g_rtaa_5": "1099-G",
            "g_taxable_grants_5": "1099-G",
            "g_ag_5": "1099-G",
            "g_market_gain_5": "1099-G",
            "g_unemployment_6": "1099-G",
            "g_state_refund_6": "1099-G",
            "g_fed_withheld_6": "1099-G",
            "g_rtaa_6": "1099-G",
            "g_taxable_grants_6": "1099-G",
            "g_ag_6": "1099-G",
            "g_market_gain_6": "1099-G",
            # Schedule 1 line 4 (other gains/losses): 2024 uses the named
            # range OtherGainsLosses = 'Sch. 1'!AL20, so no SHEET_MAP entry
            # needed (named range resolves the sheet automatically).
            # Schedule A line 5e SALT capped: direct cell ref N29 on Sch. A.
            "sch_a_line_5e_salt_capped": "Sch. A",
            # Form 8582 line 11: direct cell ref AE43 on 8582.
            "f8582_line_11_oracle": "8582",
            # Schedule 1 line 26: direct cell ref AC98 on Sch. 1.
            "sch_1_line_26": "Sch. 1",
            # Form 8962 (Premium Tax Credit) monthly-grid inputs: bare cell
            # refs on the '8962' sheet (columns fixed, rows drift by year —
            # see _F8962_ROWS_* above).
            **_f8962_sheet_map(_F8962_ROWS_2022_2024),
            # Form 8582 Part IV input cells: no named ranges in 2024; all are
            # direct cell refs on the '8582' sheet.
            "sche_8582_net_income": "8582",
            "sche_8582_net_loss": "8582",
            "k1_a_8582_net_income": "8582",
            "k1_a_8582_net_loss": "8582",
            "k1_a_8582_prior_year_loss": "8582",
            "k1_b_8582_net_income": "8582",
            "k1_b_8582_net_loss": "8582",
            "k1_b_8582_prior_year_loss": "8582",
            "k1_c_8582_net_income": "8582",
            "k1_c_8582_net_loss": "8582",
            "k1_c_8582_prior_year_loss": "8582",
            "k1_d_8582_net_income": "8582",
            "k1_d_8582_net_loss": "8582",
            "k1_d_8582_prior_year_loss": "8582",
            **_f8949_all_sheet_map(_F8949_BOX_SLOTS_2024),
        },
        2025: {
            # Form 1040 line 32 (total other payments and refundable
            # credits): unnamed in every year; direct cell ref on 1040.
            "total_other_payments": "1040",
            "w2_wages_1": "W-2s",
            "w2_fed_withheld_1": "W-2s",
            "w2_ss_wages_1": "W-2s",
            "w2_ss_withheld_1": "W-2s",
            "w2_medicare_wages_1": "W-2s",
            "w2_medicare_withheld_1": "W-2s",
            "w2_state_wages_1": "W-2s",
            "w2_state_withheld_1": "W-2s",
            "interest_1": "1099-INT",
            "ordinary_dividends_1": "1099-DIV",
            "qualified_dividends_1": "1099-DIV",
            "capital_gain_distributions_1": "1099-DIV",
            "sche_rents_a": "Sch. E",
            "sche_property_type_a": "Sch. E",
            "sche_fair_rental_days_a": "Sch. E",
            "sche_personal_use_days_a": "Sch. E",
            "sche_advertising_a": "Sch. E",
            "sche_auto_and_travel_a": "Sch. E",
            "sche_cleaning_and_maintenance_a": "Sch. E",
            "sche_commissions_a": "Sch. E",
            "sche_insurance_a": "Sch. E",
            "sche_legal_and_professional_fees_a": "Sch. E",
            "sche_management_fees_a": "Sch. E",
            "sche_mortgage_interest_a": "Sch. E",
            "sche_other_interest_a": "Sch. E",
            "sche_repairs_a": "Sch. E",
            "sche_supplies_a": "Sch. E",
            "sche_taxes_a": "Sch. E",
            "sche_utilities_a": "Sch. E",
            "sche_depreciation_a": "Sch. E",
            "sche_other_expenses_a": "Sch. E",
            "mortgage_interest": "Sch. A",
            "property_tax": "Sch. A",
            # Sch. E Part II (K-1 pass-through entities). Per-row cells for
            # name (col C), P/S entity-type box (col O), and EIN (col Y) at
            # rows 80..83 for K-1 letters A..D. Income/loss column mappings
            # are intentionally deferred: the form's Part II table aggregates
            # K-1 income into four columns (passive/nonpassive * income/loss)
            # that require per-K-1 routing based on material_participation
            # and box type; aggregation is deferred until that routing is implemented.
            "k1_a_entity_name": "Sch. E",
            "k1_a_entity_type_s_corp": "Sch. E",
            "k1_a_entity_type_partnership": "Sch. E",
            "k1_a_entity_ein": "Sch. E",
            "k1_b_entity_name": "Sch. E",
            "k1_b_entity_type_s_corp": "Sch. E",
            "k1_b_entity_type_partnership": "Sch. E",
            "k1_b_entity_ein": "Sch. E",
            "k1_c_entity_name": "Sch. E",
            "k1_c_entity_type_s_corp": "Sch. E",
            "k1_c_entity_type_partnership": "Sch. E",
            "k1_c_entity_ein": "Sch. E",
            "k1_d_entity_name": "Sch. E",
            "k1_d_entity_type_s_corp": "Sch. E",
            "k1_d_entity_type_partnership": "Sch. E",
            "k1_d_entity_ein": "Sch. E",
            # Sch. E Part II K-1 income/loss per-row cells (rows 88..91 = A..D).
            # Passive loss (g) = col C, passive income (h) = col K,
            # nonpassive loss (i) = col S, nonpassive income (k) = col AH.
            "k1_a_passive_loss": "Sch. E",
            "k1_a_passive_income": "Sch. E",
            "k1_a_nonpassive_loss": "Sch. E",
            "k1_a_nonpassive_income": "Sch. E",
            "k1_b_passive_loss": "Sch. E",
            "k1_b_passive_income": "Sch. E",
            "k1_b_nonpassive_loss": "Sch. E",
            "k1_b_nonpassive_income": "Sch. E",
            "k1_c_passive_loss": "Sch. E",
            "k1_c_passive_income": "Sch. E",
            "k1_c_nonpassive_loss": "Sch. E",
            "k1_c_nonpassive_income": "Sch. E",
            "k1_d_passive_loss": "Sch. E",
            "k1_d_passive_income": "Sch. E",
            "k1_d_nonpassive_loss": "Sch. E",
            "k1_d_nonpassive_income": "Sch. E",
            # Form 8995 K-1 QBI input cells. Each K-1's QBI amount is entered
            # in column AB at rows 14/16/18/20 (lines i–iv). These have no
            # named range; the sheet name is in SHEET_MAP.
            "k1_a_qbi_amount": "8995",
            "k1_b_qbi_amount": "8995",
            "k1_c_qbi_amount": "8995",
            "k1_d_qbi_amount": "8995",
            # SALT refund tax-benefit-rule worksheet: prior-year itemized
            # deduction amount goes in cell J45 on the SALT worksheet.
            # The SALT worksheet has its own filing-status checkboxes
            # (P6/P8/P10/P12/P14) independent of the main 1040 sheet.
            "prior_year_itemized_deduction": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_single": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfj": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfs": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_hoh": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_qw": "Sch 1, Line 1 (SALT)",
            # Form 1099-G (filer's copy — 6 payers supported in cols D..I).
            "g_unemployment_1": "1099-G",
            "g_state_refund_1": "1099-G",
            "g_fed_withheld_1": "1099-G",
            "g_rtaa_1": "1099-G",
            "g_taxable_grants_1": "1099-G",
            "g_ag_1": "1099-G",
            "g_market_gain_1": "1099-G",
            "g_unemployment_2": "1099-G",
            "g_state_refund_2": "1099-G",
            "g_fed_withheld_2": "1099-G",
            "g_rtaa_2": "1099-G",
            "g_taxable_grants_2": "1099-G",
            "g_ag_2": "1099-G",
            "g_market_gain_2": "1099-G",
            "g_unemployment_3": "1099-G",
            "g_state_refund_3": "1099-G",
            "g_fed_withheld_3": "1099-G",
            "g_rtaa_3": "1099-G",
            "g_taxable_grants_3": "1099-G",
            "g_ag_3": "1099-G",
            "g_market_gain_3": "1099-G",
            "g_unemployment_4": "1099-G",
            "g_state_refund_4": "1099-G",
            "g_fed_withheld_4": "1099-G",
            "g_rtaa_4": "1099-G",
            "g_taxable_grants_4": "1099-G",
            "g_ag_4": "1099-G",
            "g_market_gain_4": "1099-G",
            "g_unemployment_5": "1099-G",
            "g_state_refund_5": "1099-G",
            "g_fed_withheld_5": "1099-G",
            "g_rtaa_5": "1099-G",
            "g_taxable_grants_5": "1099-G",
            "g_ag_5": "1099-G",
            "g_market_gain_5": "1099-G",
            "g_unemployment_6": "1099-G",
            "g_state_refund_6": "1099-G",
            "g_fed_withheld_6": "1099-G",
            "g_rtaa_6": "1099-G",
            "g_taxable_grants_6": "1099-G",
            "g_ag_6": "1099-G",
            "g_market_gain_6": "1099-G",
            # Schedule 1 line 4 (other gains/losses): direct cell ref
            # because the value isn't named in the workbook. Cell AJ19
            # holds ROUND(AC19,0); line 10's SUM references the same
            # rounded expression inline.
            "sch_1_line_4_other_gains": "Sch. 1",
            # Form 8962 (Premium Tax Credit) monthly-grid inputs: bare cell
            # refs on the '8962' sheet (columns fixed, rows drift by year —
            # see _F8962_ROWS_* above).
            **_f8962_sheet_map(_F8962_ROWS_2025),
            **_f8949_all_sheet_map(),
        },
    }

    INPUTS: dict[int, dict[str, str]] = {
        2024: {
            "filing_status_single": "File_Single",
            "filing_status_married_filing_jointly": "File_Marr_Joint",
            "filing_status_married_filing_separately": "File_Marr_Sep",
            "filing_status_head_of_household": "File_Head",
            "filing_status_qualifying_widow": "File_Qual_Widow",
            "birthdate_month": "YourBirthMonth",
            "birthdate_day": "YourBirthDay",
            "birthdate_year": "YourBirthYear",
            # Workbook-scoped names, present 2021-2025; the address drifts.
            "spouse_birthdate_month": "SpouseBirthMonth",
            "spouse_birthdate_day": "SpouseBirthDay",
            "spouse_birthdate_year": "SpouseBirthYear",
            "w2_wages_1": "C3",
            "w2_fed_withheld_1": "C4",
            "w2_ss_wages_1": "C5",
            "w2_ss_withheld_1": "C6",
            "w2_medicare_wages_1": "C7",
            "w2_medicare_withheld_1": "C8",
            # In 2024 the W-2s sheet has 6 fewer rows before state fields;
            # state wages (box 16) = row 22, state income tax (box 17) = row 23.
            "w2_state_wages_1": "C22",
            "w2_state_withheld_1": "C23",
            # Estimated tax payments (Form 1040 line 26): named range present
            # in every year's workbook, pointing at that year's own line-26
            # cell (verified: 2021 AC71, 2022 AC80, 2023 AD86, 2024 AD89,
            # 2025 AL110). Resolves per-workbook automatically — no
            # SHEET_MAP entry needed.
            "estimated_tax_payments": "EstimatedTaxPayments",
            "interest_1": "D6",
            "ordinary_dividends_1": "D6",
            "qualified_dividends_1": "D7",
            "capital_gain_distributions_1": "D8",
            "mortgage_interest": "T37",
            "property_tax": "N25",
            "sche_property_type_a": "D21",
            "sche_fair_rental_days_a": "AA21",
            "sche_personal_use_days_a": "AF21",
            "sche_rents_a": "V30",
            "sche_advertising_a": "V33",
            "sche_auto_and_travel_a": "V34",
            "sche_cleaning_and_maintenance_a": "V35",
            "sche_commissions_a": "V36",
            "sche_insurance_a": "V37",
            "sche_legal_and_professional_fees_a": "V38",
            "sche_management_fees_a": "V39",
            "sche_mortgage_interest_a": "V40",
            "sche_other_interest_a": "V41",
            "sche_repairs_a": "V42",
            "sche_supplies_a": "V43",
            "sche_taxes_a": "V44",
            "sche_utilities_a": "V45",
            "sche_depreciation_a": "V46",
            "sche_other_expenses_a": "V47",
            # Sch. E Part II K-1 per-row cells (rows 80..83 = A..D).
            "k1_a_entity_name": "C80",
            "k1_a_entity_type_s_corp": "O80",
            "k1_a_entity_type_partnership": "O80",
            "k1_a_entity_ein": "Y80",
            "k1_b_entity_name": "C81",
            "k1_b_entity_type_s_corp": "O81",
            "k1_b_entity_type_partnership": "O81",
            "k1_b_entity_ein": "Y81",
            "k1_c_entity_name": "C82",
            "k1_c_entity_type_s_corp": "O82",
            "k1_c_entity_type_partnership": "O82",
            "k1_c_entity_ein": "Y82",
            "k1_d_entity_name": "C83",
            "k1_d_entity_type_s_corp": "O83",
            "k1_d_entity_type_partnership": "O83",
            "k1_d_entity_ein": "Y83",
            # Sch. E Part II K-1 income/loss cells (rows 88..91 = A..D).
            "k1_a_passive_loss": "C88",
            "k1_a_passive_income": "K88",
            "k1_a_nonpassive_loss": "S88",
            "k1_a_nonpassive_income": "AH88",
            "k1_b_passive_loss": "C89",
            "k1_b_passive_income": "K89",
            "k1_b_nonpassive_loss": "S89",
            "k1_b_nonpassive_income": "AH89",
            "k1_c_passive_loss": "C90",
            "k1_c_passive_income": "K90",
            "k1_c_nonpassive_loss": "S90",
            "k1_c_nonpassive_income": "AH90",
            "k1_d_passive_loss": "C91",
            "k1_d_passive_income": "K91",
            "k1_d_nonpassive_loss": "S91",
            "k1_d_nonpassive_income": "AH91",
            # Form 8995 K-1 QBI input cells (column AB, lines i–iv at rows
            # 14/16/18/20). Same layout as 2025.
            "k1_a_qbi_amount": "AB14",
            "k1_b_qbi_amount": "AB16",
            "k1_c_qbi_amount": "AB18",
            "k1_d_qbi_amount": "AB20",
            # SALT refund tax-benefit-rule worksheet. In 2024 the prior-year
            # itemized deduction input is at J51 (2025 moved it to J45 when
            # the worksheet gained new lines 5–7 above it).
            "prior_year_itemized_deduction": "J51",
            "salt_filing_status_single": "P6",
            "salt_filing_status_mfj": "P8",
            "salt_filing_status_mfs": "P10",
            "salt_filing_status_hoh": "P12",
            "salt_filing_status_qw": "P14",
            # Form 8582 Part IV input cells. The 2024 workbook uses the same
            # cell addresses (N49/R49/V49..V53) as 2025 but lacks named ranges
            # for them; direct cell refs are used here.
            "sche_8582_net_income": "N49",
            "sche_8582_net_loss": "R49",
            "k1_a_8582_net_income": "N50",
            "k1_a_8582_net_loss": "R50",
            "k1_a_8582_prior_year_loss": "V50",
            "k1_b_8582_net_income": "N51",
            "k1_b_8582_net_loss": "R51",
            "k1_b_8582_prior_year_loss": "V51",
            "k1_c_8582_net_income": "N52",
            "k1_c_8582_net_loss": "R52",
            "k1_c_8582_prior_year_loss": "V52",
            "k1_d_8582_net_income": "N53",
            "k1_d_8582_net_loss": "R53",
            "k1_d_8582_prior_year_loss": "V53",
            # Form 1099-G filer cells (same layout as 2025).
            "g_unemployment_1": "D6",
            "g_state_refund_1": "D7",
            "g_fed_withheld_1": "D9",
            "g_rtaa_1": "D10",
            "g_taxable_grants_1": "D11",
            "g_ag_1": "D12",
            "g_market_gain_1": "D15",
            "g_unemployment_2": "E6",
            "g_state_refund_2": "E7",
            "g_fed_withheld_2": "E9",
            "g_rtaa_2": "E10",
            "g_taxable_grants_2": "E11",
            "g_ag_2": "E12",
            "g_market_gain_2": "E15",
            "g_unemployment_3": "F6",
            "g_state_refund_3": "F7",
            "g_fed_withheld_3": "F9",
            "g_rtaa_3": "F10",
            "g_taxable_grants_3": "F11",
            "g_ag_3": "F12",
            "g_market_gain_3": "F15",
            "g_unemployment_4": "G6",
            "g_state_refund_4": "G7",
            "g_fed_withheld_4": "G9",
            "g_rtaa_4": "G10",
            "g_taxable_grants_4": "G11",
            "g_ag_4": "G12",
            "g_market_gain_4": "G15",
            "g_unemployment_5": "H6",
            "g_state_refund_5": "H7",
            "g_fed_withheld_5": "H9",
            "g_rtaa_5": "H10",
            "g_taxable_grants_5": "H11",
            "g_ag_5": "H12",
            "g_market_gain_5": "H15",
            "g_unemployment_6": "I6",
            "g_state_refund_6": "I7",
            "g_fed_withheld_6": "I9",
            "g_rtaa_6": "I10",
            "g_taxable_grants_6": "I11",
            "g_ag_6": "I12",
            "g_market_gain_6": "I15",
            # Form 8962 (Premium Tax Credit) monthly-grid inputs (Part II,
            # lines 12-23, Jan..Dec). Columns fixed across all years —
            # (a) premium=G, (b) SLCSP=L, (f) APTC=AF; 2022-2024 rows 48-59.
            **_f8962_inputs(_F8962_ROWS_2022_2024),
            **_f8949_all_inputs(_F8949_BOX_SLOTS_2024),
        },
        2025: {
            "filing_status_single": "File_Single",
            "filing_status_married_filing_jointly": "File_Marr_Joint",
            "filing_status_married_filing_separately": "File_Marr_Sep",
            "filing_status_head_of_household": "File_Head",
            "filing_status_qualifying_widow": "File_Qual_Widow",
            "birthdate_month": "YourBirthMonth",
            "birthdate_day": "YourBirthDay",
            "birthdate_year": "YourBirthYear",
            # Workbook-scoped names, present 2021-2025; the address drifts.
            "spouse_birthdate_month": "SpouseBirthMonth",
            "spouse_birthdate_day": "SpouseBirthDay",
            "spouse_birthdate_year": "SpouseBirthYear",
            "w2_wages_1": "C3",
            "w2_fed_withheld_1": "C4",
            "w2_ss_wages_1": "C5",
            "w2_ss_withheld_1": "C6",
            "w2_medicare_wages_1": "C7",
            "w2_medicare_withheld_1": "C8",
            "w2_state_wages_1": "C28",
            "w2_state_withheld_1": "C29",
            # Estimated tax payments (Form 1040 line 26): named range present
            # in every year's workbook, pointing at that year's own line-26
            # cell (verified: 2021 AC71, 2022 AC80, 2023 AD86, 2024 AD89,
            # 2025 AL110). Resolves per-workbook automatically — no
            # SHEET_MAP entry needed.
            "estimated_tax_payments": "EstimatedTaxPayments",
            "interest_1": "D6",
            "ordinary_dividends_1": "D6",
            "qualified_dividends_1": "D7",
            "capital_gain_distributions_1": "D8",
            "mortgage_interest": "T37",
            "property_tax": "N25",
            "sche_property_type_a": "D21",
            "sche_fair_rental_days_a": "AA21",
            "sche_personal_use_days_a": "AF21",
            "sche_rents_a": "V30",
            "sche_advertising_a": "V33",
            "sche_auto_and_travel_a": "V34",
            "sche_cleaning_and_maintenance_a": "V35",
            "sche_commissions_a": "V36",
            "sche_insurance_a": "V37",
            "sche_legal_and_professional_fees_a": "V38",
            "sche_management_fees_a": "V39",
            "sche_mortgage_interest_a": "V40",
            "sche_other_interest_a": "V41",
            "sche_repairs_a": "V42",
            "sche_supplies_a": "V43",
            "sche_taxes_a": "V44",
            "sche_utilities_a": "V45",
            "sche_depreciation_a": "V46",
            "sche_other_expenses_a": "V47",
            # Sch. E Part II K-1 per-row cells (rows 80..83 = A..D).
            "k1_a_entity_name": "C80",
            "k1_a_entity_type_s_corp": "O80",
            "k1_a_entity_type_partnership": "O80",
            "k1_a_entity_ein": "Y80",
            "k1_b_entity_name": "C81",
            "k1_b_entity_type_s_corp": "O81",
            "k1_b_entity_type_partnership": "O81",
            "k1_b_entity_ein": "Y81",
            "k1_c_entity_name": "C82",
            "k1_c_entity_type_s_corp": "O82",
            "k1_c_entity_type_partnership": "O82",
            "k1_c_entity_ein": "Y82",
            "k1_d_entity_name": "C83",
            "k1_d_entity_type_s_corp": "O83",
            "k1_d_entity_type_partnership": "O83",
            "k1_d_entity_ein": "Y83",
            # Sch. E Part II K-1 income/loss cells (rows 88..91 = A..D).
            # (g) passive loss = col C, (h) passive income = col K,
            # (i) nonpassive loss = col S, (k) nonpassive income = col AH.
            "k1_a_passive_loss": "C88",
            "k1_a_passive_income": "K88",
            "k1_a_nonpassive_loss": "S88",
            "k1_a_nonpassive_income": "AH88",
            "k1_b_passive_loss": "C89",
            "k1_b_passive_income": "K89",
            "k1_b_nonpassive_loss": "S89",
            "k1_b_nonpassive_income": "AH89",
            "k1_c_passive_loss": "C90",
            "k1_c_passive_income": "K90",
            "k1_c_nonpassive_loss": "S90",
            "k1_c_nonpassive_income": "AH90",
            "k1_d_passive_loss": "C91",
            "k1_d_passive_income": "K91",
            "k1_d_nonpassive_loss": "S91",
            "k1_d_nonpassive_income": "AH91",
            # Form 8995 K-1 QBI input cells (column AB, lines i–iv at rows
            # 14/16/18/20). No named range; resolved via SHEET_MAP → "8995".
            "k1_a_qbi_amount": "AB14",
            "k1_b_qbi_amount": "AB16",
            "k1_c_qbi_amount": "AB18",
            "k1_d_qbi_amount": "AB20",
            # SALT refund tax-benefit-rule (Sch 1, Line 1 worksheet).
            # J45 = prior year total itemized deductions (line 4).
            # P6/P8/P10/P12/P14 = filing status checkboxes (independent
            # of the main 1040 named ranges).
            "prior_year_itemized_deduction": "J45",
            "salt_filing_status_single": "P6",
            "salt_filing_status_mfj": "P8",
            "salt_filing_status_mfs": "P10",
            "salt_filing_status_hoh": "P12",
            "salt_filing_status_qw": "P14",
            # Form 8582 Part IV input cells (rental real estate activities).
            # Slot A = Sch E Part I rental (row 49); slots B-E = K-1 a-d
            # rental RE (rows 50-53). Income (col N) and loss (col R) are
            # separate positive-amount entries; prior-year carryforward is
            # col V. Named ranges resolve to '8582' sheet without SHEET_MAP.
            "sche_8582_net_income": "F8582_P4A_NetIncome",
            "sche_8582_net_loss": "F8582_P4A_NetLoss",
            "k1_a_8582_net_income": "F8582_P4B_NetIncome",
            "k1_a_8582_net_loss": "F8582_P4B_NetLoss",
            "k1_a_8582_prior_year_loss": "F8582_P4B_PriorLoss",
            "k1_b_8582_net_income": "F8582_P4C_NetIncome",
            "k1_b_8582_net_loss": "F8582_P4C_NetLoss",
            "k1_b_8582_prior_year_loss": "F8582_P4C_PriorLoss",
            "k1_c_8582_net_income": "F8582_P4D_NetIncome",
            "k1_c_8582_net_loss": "F8582_P4D_NetLoss",
            "k1_c_8582_prior_year_loss": "F8582_P4D_PriorLoss",
            "k1_d_8582_net_income": "F8582_P4E_NetIncome",
            "k1_d_8582_net_loss": "F8582_P4E_NetLoss",
            "k1_d_8582_prior_year_loss": "F8582_P4E_PriorLoss",
            # Form 1099-G filer cells (payer N in column {D,E,F,G,H,I}[N-1]).
            # Row 6: unemployment compensation (box 1)
            # Row 7: state or local income tax refund (box 2)
            # Row 9: federal income tax withheld (box 4)
            # Row 10: RTAA payments (box 5)
            # Row 11: taxable grants (box 6)
            # Row 12: agriculture payments (box 7a, disaster)
            # Row 15: market gain (box 9)
            "g_unemployment_1": "D6",
            "g_state_refund_1": "D7",
            "g_fed_withheld_1": "D9",
            "g_rtaa_1": "D10",
            "g_taxable_grants_1": "D11",
            "g_ag_1": "D12",
            "g_market_gain_1": "D15",
            "g_unemployment_2": "E6",
            "g_state_refund_2": "E7",
            "g_fed_withheld_2": "E9",
            "g_rtaa_2": "E10",
            "g_taxable_grants_2": "E11",
            "g_ag_2": "E12",
            "g_market_gain_2": "E15",
            "g_unemployment_3": "F6",
            "g_state_refund_3": "F7",
            "g_fed_withheld_3": "F9",
            "g_rtaa_3": "F10",
            "g_taxable_grants_3": "F11",
            "g_ag_3": "F12",
            "g_market_gain_3": "F15",
            "g_unemployment_4": "G6",
            "g_state_refund_4": "G7",
            "g_fed_withheld_4": "G9",
            "g_rtaa_4": "G10",
            "g_taxable_grants_4": "G11",
            "g_ag_4": "G12",
            "g_market_gain_4": "G15",
            "g_unemployment_5": "H6",
            "g_state_refund_5": "H7",
            "g_fed_withheld_5": "H9",
            "g_rtaa_5": "H10",
            "g_taxable_grants_5": "H11",
            "g_ag_5": "H12",
            "g_market_gain_5": "H15",
            "g_unemployment_6": "I6",
            "g_state_refund_6": "I7",
            "g_fed_withheld_6": "I9",
            "g_rtaa_6": "I10",
            "g_taxable_grants_6": "I11",
            "g_ag_6": "I12",
            "g_market_gain_6": "I15",
            # Form 8962 (Premium Tax Credit) monthly-grid inputs (Part II,
            # lines 12-23, Jan..Dec). Columns fixed across all years —
            # (a) premium=G, (b) SLCSP=L, (f) APTC=AF; 2025 rows 50-61.
            **_f8962_inputs(_F8962_ROWS_2025),
            **_f8949_all_inputs(),
        },
    }

    OUTPUTS: dict[int, dict[str, str]] = {
        2024: {
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "Standard",
            "taxable_income": "Taxable_Inc",
            # `total_tax` IS IRS Form 1040 LINE 16, on every path. The native
            # spine emits line-16 income tax under this key (f1040_spine.py),
            # every year block of pdf_1040.py maps it to the line-16 box, and
            # f1040x line 6 composes on a line-16 base, adding the excess-APTC
            # repayment (Schedule 2 LINE 2) itself — and ONLY that. It does NOT
            # add the AMT component (Schedule 2 line 1), so line 6 is NOT
            # Part-I-complete; see f1040x.py's module docstring for the precise
            # statement. This mapping formerly pointed at `Tax`, which is line
            # 18 — the SUM of line 16 and the line-17 CELL, that cell being
            # `IF(<override><>"", ROUND(<override>,0), Schedule2_Tax)` in
            # 2022-2025, i.e. `Schedule2_Tax` absent a manual override
            # tenforty never writes. 2021 IS THE SAME CELL UNDER A DIFFERENT
            # NAME: '1040'!AC58 reads `Schedule2`, a separate defined name
            # that resolves to the same 'Sch. 2'!AC13 as `Schedule2_Tax`.
            # Nothing computational turns on that — but a reader grepping the
            # 2021 workbook for `Schedule2_Tax` at line 17 will not find it.
            # Pointing here printed an overstated line 16 whenever Schedule 2
            # Part I was nonzero and made f1040x double-count the excess-APTC
            # repayment.
            "total_tax": "Tax_SubTotal",
            # Line 17 — Schedule 2 line 3 (Part I: AMT + excess APTC) — and
            # line 18 — "Add lines 16 and 17". Both keys were mapped to their
            # PDF boxes but produced by nothing, so both lines printed blank
            # on every emitted 1040. `Tax` is exactly line 18, so it is the
            # honest producer for `tax_plus_schedule2`.
            "schedule2_tax": "Schedule2_Tax",
            "tax_plus_schedule2": "Tax",
            # 1040 LINE 24 — "Add lines 22 and 23. This is your total tax."
            # The `Tot_Tax` named range, present in all five workbooks:
            #   2021 '1040'!AC65   2022 AC74   2023 AD80
            #   2024 '1040'!AD83   2025 AL104
            # Every year is `=SUM(<line 22>, <line 23>)`, where line 22 is
            # `MAX(0, SUM(Tax, -<line 21 credits>))` and line 23 is
            # `TotalOtherTaxes` (Schedule 2 Part II). Pinned per-year — cell,
            # name resolution, and formula shape — by tests/
            # test_f1040_mapping.py::TestF1040TotalTaxLiabilityLine24.
            #
            # WHO CONSUMES IT: Form 4868 line 4, "Estimate of Total Tax
            # Liability", whose instruction names 1040 line 24 explicitly
            # (pdfs/federal/2025/f4868.pdf). f4868 previously read `total_tax`
            # raw, which is line 16, so line 4, the balance due AND the
            # payment voucher all came out short by the whole of Schedule 2.
            #
            # HARVESTED, NOT COMPOSED, on this path — deliberately asymmetric
            # with the native path, which has no line-24 producer and must
            # compose. The harvest inherits what the workbook ACTUALLY
            # computes (including NIIT, which the native side cannot), resolves
            # by name so it survives vendor cell moves, and skips the
            # arithmetic where composition goes wrong. See forms/f4868.py.
            #
            # ON THE `_line24` SUFFIX. A sibling key `total_tax_line16` was
            # RETIRED on the grounds that suffixed keys invite drift; do NOT
            # cite that retirement as grounds to drop this suffix. They were
            # different situations. `total_tax_line16` was a DUPLICATE — it
            # pointed at the same named range as `total_tax` (`Tax_SubTotal`)
            # and named the same quantity twice, which is exactly how one name
            # regrows two meanings. Its absence from every year's resolved
            # OUTPUTS is pinned by tests/test_f1040_mapping.py::
            # TestF1040TaxBandOutputsEveryYear. `tax_liability_line24` names a
            # DIFFERENT QUANTITY that has no other key. The suffix is doing
            # semantic work, not disambiguating a duplicate.
            #
            # NO SEPARATE DIAGNOSTIC GUARD IS NEEDED for this key: the
            # `deduction_diagnostic` refusal below fires in forms/f1040.py
            # before any harvested tax figure is consumed, for every MFJ/MFS
            # filer. Do not add a redundant one.
            "tax_liability_line24": "Tot_Tax",
            # THE WORKBOOK'S OWN REFUSAL CHANNEL, and the ONLY OUTPUT key that
            # legitimately holds a STRING. `Deduction` is the Form 1040 line-12
            # CAPTION cell: on a return the sheet computed it names the
            # deduction SOURCE ("Standard Deduction", "Schedule A", ...), but
            # on one it declined to compute it holds a plain-English DIAGNOSTIC
            # ("Birthdate(s) needed.", "Filing status error.", ...). In those
            # branches the sheet also forces line 12 to 0 and blanks
            # `Tax_SubTotal` (line 16), so harvesting the number WITHOUT the
            # diagnostic reads a REFUSAL as data. forms/f1040.py::
            # workbook_refusal turns it back into a refusal; see that function
            # for the branch enumeration and the fail-closed rule.
            #
            # By NAME, never by address: this cell moves every single year
            # (2021 '1040'!AJ51, 2022 AJ58, 2023 AK64, 2024 AK67, 2025 AU91)
            # while the name resolves in all five workbooks. Mind the
            # singular/plural trap -- `Deductions` is a DIFFERENT named range
            # holding the line-12 DOLLAR AMOUNT (the value the diagnostic
            # zeroes); `Deduction` is the caption. Pinned per-year by
            # tests/test_f1040_mapping.py::TestF1040TaxBandOutputsEveryYear.
            "deduction_diagnostic": "Deduction",
            "federal_withheld": "W2_FedTaxWH",
            "additional_medicare_withheld": "F8959_WH",
            "f8959_tax_total": "F8959_Tax",
            "f8959_required": "F8959_Reqd",
            "overpaid": "Overpaid",
            "sche_line26": "SchE1_Line26",
            "sch_1_line_10": "Additional_Income",
            # Schedule 1 line 26 (Total Adjustments): 2024 uses the named
            # range AdjustToIncome = 'Sch. 1'!AC98. SHEET_MAP routes the
            # engine to 'Sch. 1' for the fallback read path.
            "sch_1_line_26": "AC98",
            "sch_1_line_1_taxable_refunds": "Sch1_Line1",
            "sch_1_line_3_business_income": "BusinessIncomeLoss",
            # Line 4 (other gains/losses): 2024 has the named range
            # OtherGainsLosses = 'Sch. 1'!AL20 — the rounded display value,
            # equivalent to 2025's direct ref AJ19.
            "sch_1_line_4_other_gains": "OtherGainsLosses",
            "sch_1_line_5_rental_re_royalty": "SchE_IncomeLoss",
            "sch_1_line_6_farm_income": "FarmIncomeLoss",
            "sch_1_line_7_unemployment": "UnEmploymentComp",
            "sch_1_line_11_educator": "EducatorExpenses",
            "sch_1_line_13_hsa": "HSA_Deduct",
            "sch_1_line_15_se_tax": "SE_Deduct",
            "sch_1_line_17_se_health": "SEHealthInsDeduct",
            "sch_1_line_20_ira": "IRADeduct",
            "sch_1_line_21_student_loan_interest": "StudentLoanIntDeduct",
            "sche_line41": "SchE1_Line41",
            "schd_line16": "SchDLine16",
            # 1040 line 7a — the IRC §1211(b)-CAPPED capital gain/loss actually
            # TRANSFERRED from Schedule D line 21. Deliberately distinct from
            # `schd_line16` above, which is the TRUE, UNCAPPED Schedule D line
            # 16 total; the two diverge whenever a net loss exceeds the $3,000
            # ($1,500 MFS) cap. This mirrors the capped/uncapped split the
            # native spine already makes (f1040_spine.py emits both keys).
            # Without this output nothing read the workbook's capped value and
            # line 7a printed the UNCAPPED loss while line 9 (total income)
            # printed the capped one — an internally inconsistent PDF.
            #
            # Read BY NAME, not by cell address. The underlying cell moves in
            # EVERY year — '1040'!AC43 (2021), AC53 (2022), AD59 (2023), AD62
            # (2024), AL74 (2025) — so an address mapping would need five
            # separate entries and would rot silently on the next workbook. The
            # NAME is stable and verified present in all five workbooks.
            #
            # Formula shape is consistent year to year: manual-override ->
            # '1099-DIV' direct when Schedule D isn't required -> the
            # loss-limited chain. For 2024 that chain ends at 'Sch. D'!O88 =
            # IF(N58<0,-MIN(-N58,-S91),""), which is §1211(b); S91 carries the
            # married-filing-separately halving.
            #
            # 2021 VARIANT (2021 inherits this block via 2022/2023): 2021's
            # CapitalGains reads the `SchDLine16` named range DIRECTLY on its
            # gain branch. That is harmless, not a bug — cap and uncapped
            # coincide for a gain — and 2021's LOSS branch still routes to its
            # own capped cell, 'Sch. D'!O89. So 2021 is capped correctly too.
            #
            # A blank result (empty Schedule D) surfaces as None and is left
            # as None ON PURPOSE — see the note in forms/f1040.py where the
            # old `schd_line16 -> capital_gain_loss` alias used to live.
            "capital_gain_loss": "CapitalGains",
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
            "schedule_a_total": "Tot_Item_Deduct",
            # Schedule A line 5e (SALT capped): 2024 has no SALT_Limited named
            # range. Cell N29 on 'Sch. A' holds MIN(total SALT, $10k cap).
            # SHEET_MAP routes the engine to 'Sch. A'.
            "sch_a_line_5e_salt_capped": "N29",
            "magi": "ModAdjGrossInc",
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
            "f8995_line_15_oracle": "QBID",
            "net_capital_gain": "NetCapitalGain",
            # 1040 line 3a (qualified dividends). Form 8995 line 12 needs the
            # authoritative total on the workbook-routed emit path; the
            # `Qualified_Dividends` named range exists in every year workbook.
            "qualified_dividends": "Qualified_Dividends",
            "_qbi_deduction_1040": "QBID_1040",
            # Form 8582 line 11: 2024 has no F8582_Line11 named range. Cell
            # AE43 on '8582' holds the line 11 total (same formula as 2025,
            # same row — the named range was added in the 2025 workbook only).
            # SHEET_MAP routes the engine to '8582'.
            "f8582_line_11_oracle": "AE43",
            "f8949_box_a_total_proceeds":   "F8949ASTD",
            "f8949_box_a_total_basis":      "F8949ASTE",
            "f8949_box_a_total_adjustment": "F8949ASTG",
            "f8949_box_a_total_gain":       "F8949ASTH",
            "f8949_box_b_total_proceeds":   "F8949BSTD",
            "f8949_box_b_total_basis":      "F8949BSTE",
            "f8949_box_b_total_adjustment": "F8949BSTG",
            "f8949_box_b_total_gain":       "F8949BSTH",
            "f8949_box_d_total_proceeds":   "F8949ALTD",
            "f8949_box_d_total_basis":      "F8949ALTE",
            "f8949_box_d_total_adjustment": "F8949ALTG",
            "f8949_box_d_total_gain":       "F8949ALTH",
            "f8949_box_e_total_proceeds":   "F8949BLTD",
            "f8949_box_e_total_basis":      "F8949BLTE",
            "f8949_box_e_total_adjustment": "F8949BLTG",
            "f8949_box_e_total_gain":       "F8949BLTH",
            # Form 8962 (Premium Tax Credit): net PTC (line 26) and
            # excess-APTC repayment (line 29). Both are workbook-global
            # named ranges resolving to '8962' cells directly — year-stable
            # (the underlying cell address drifts per year but the named
            # range resolves automatically), so no SHEET_MAP entry needed.
            "f8962_net_ptc": "PTC_Net",
            "f8962_repayment": "PTC_Excess",
            # Form 1040 line 27 (earned income credit). Workbook-scoped name
            # in every year (the 1040 sheet's line-27 cell; the address
            # drifts). Tot_Payments already sums it through line 32, so
            # without this key the credit reached line 33 while line 27
            # printed blank.
            "eic": "EIC",
            # Form 1040 line 26 (estimated tax payments): the same
            # workbook-scoped name the INPUT writes, read back so line 26
            # prints. Tot_Payments sums it, so without this the page did
            # not foot (ruling R-S4-3; the eic / line-32 disease).
            "estimated_tax_payments": "EstimatedTaxPayments",
            # Form 1040 line 32 = SUM(EIC, lines 28-31) on the 1040 sheet,
            # harvested by address (no named range). Its terms are pinned
            # in tests/test_eic_harvest.py; the emit refuses when it does
            # not equal the line-32 components tenforty prints.
            "total_other_payments": "AD95",
        },
        2025: {
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "Standard",
            "taxable_income": "Taxable_Inc",
            # `total_tax` IS IRS 1040 line 16 (`Tax_SubTotal`) — see the 2024
            # block for the full rationale. It formerly pointed at `Tax`, which
            # is line 18.
            "total_tax": "Tax_SubTotal",
            # Lines 17 and 18 — previously orphan keys with no producer, so both
            # lines printed blank. See the 2024 block.
            "schedule2_tax": "Schedule2_Tax",
            "tax_plus_schedule2": "Tax",
            # 1040 LINE 24 (total tax) — the `Tot_Tax` named range,
            # '1040'!AL104 here. Consumed by Form 4868 line 4, harvested
            # rather than composed, and the `_line24` suffix is load-bearing
            # rather than a duplicate-disambiguator. See the 2024 block for
            # all three arguments in full.
            "tax_liability_line24": "Tot_Tax",
            # The workbook's own refusal channel — the line-12 CAPTION cell,
            # which holds a plain-English DIAGNOSTIC on any return the sheet
            # declined to compute (and blanks `Tax_SubTotal` when it does).
            # The only OUTPUT key that legitimately holds a string. Harvested
            # by NAME because the address drifts every year (2025 is
            # '1040'!AU91). See the 2024 block for the full rationale, and
            # forms/f1040.py::workbook_refusal for the decision it feeds.
            "deduction_diagnostic": "Deduction",
            "federal_withheld": "W2_FedTaxWH",
            # Form 8959 Part III: Additional Medicare Tax withheld by employers
            # on wages exceeding the $200k/$250k threshold (IRC §3101(b)(2)).
            # Flows to 1040 line 25c via Form 8959.
            "additional_medicare_withheld": "F8959_WH",
            # Form 8959 line 18: total Additional Medicare Tax. Used as the
            # oracle cross-check target for forms.f8959.compute's native math.
            "f8959_tax_total": "F8959_Tax",
            # Oracle-authoritative gate for whether Form 8959 must be filed.
            # Preferred over the wage-threshold heuristic in the orchestrator
            # predicate so we don't emit a zero-valued form.
            "f8959_required": "F8959_Reqd",
            "overpaid": "Overpaid",
            "sche_line26": "SchE1_Line26",
            # Schedule 1 line 10 (Total Additional Income). Oracle cross-check
            # target for forms.sch_1.compute's native math.
            "sch_1_line_10": "Additional_Income",
            # Schedule 1 line 26 (Total Adjustments to Income). Oracle
            # cross-check target for forms.sch_1.compute's native math.
            "sch_1_line_26": "Sch1A_Deductions",
            # Schedule 1 Part I per-line breakdowns (XLS-sourced; named
            # ranges in the Sch. 1 sheet). These keys feed downstream
            # Sch CA kernel auto-derive and other state-return
            # consumers that need per-line granularity.
            "sch_1_line_1_taxable_refunds": "Sch1_Line1",
            "sch_1_line_3_business_income": "BusinessIncomeLoss",
            # Line 4 has no named range; direct cell ref to AJ19
            # (rounded display of AC19). SHEET_MAP routes to "Sch. 1".
            "sch_1_line_4_other_gains": "AJ19",
            "sch_1_line_5_rental_re_royalty": "SchE_IncomeLoss",
            "sch_1_line_6_farm_income": "FarmIncomeLoss",
            "sch_1_line_7_unemployment": "UnEmploymentComp",
            # Schedule 1 Part II per-line breakdowns (XLS-sourced;
            # named ranges in the Sch. 1 sheet).
            "sch_1_line_11_educator": "EducatorExpenses",
            "sch_1_line_13_hsa": "HSA_Deduct",
            "sch_1_line_15_se_tax": "SE_Deduct",
            "sch_1_line_17_se_health": "SEHealthInsDeduct",
            "sch_1_line_20_ira": "IRADeduct",
            "sch_1_line_21_student_loan_interest": "StudentLoanIntDeduct",
            "sche_line41": "SchE1_Line41",
            "schd_line16": "SchDLine16",
            # 1040 line 7a — the §1211(b)-CAPPED transfer from Schedule D line
            # 21, as opposed to `schd_line16`'s TRUE uncapped line-16 total.
            # See the 2024 block for the full rationale (why by NAME and not by
            # address, the per-year cell drift, and the 2021 gain-branch
            # variant). 2025's loss-limited cell is 'Sch. D'!P87 =
            # IF(O57<0,-MIN(-O57,-T90),""), with T90 =
            # IF(File_Marr_Sep="",-T88,-T89) carrying the MFS halving.
            "capital_gain_loss": "CapitalGains",
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
            "schedule_a_total": "Tot_Item_Deduct",
            # Schedule A line 5e (SALT capped). Oracle cross-check target for
            # forms.sch_a.compute's native OBBBA cap.
            "sch_a_line_5e_salt_capped": "SALT_Limited",
            # MAGI for phaseout math (IRC §164(b)(6) phaseout threshold).
            "magi": "ModAdjGrossInc",
            # --- Totals ---
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
            # --- Form 8995 oracle cross-check ---
            # Form 8995 line 15: Qualified Business Income Deduction.
            # Oracle authoritative output for cross-checking forms.f8995.compute.
            "f8995_line_15_oracle": "QBID",
            # Form 8995 line 12: net capital gain (qualified dividends +
            # net LTCG) as computed on the worksheet.
            "net_capital_gain": "NetCapitalGain",
            # 1040 line 3a (qualified dividends). Form 8995 line 12 needs the
            # authoritative total on the workbook-routed emit path; the
            # `Qualified_Dividends` named range exists in every year workbook.
            "qualified_dividends": "Qualified_Dividends",
            # QBI deduction as entered on 1040 line 13 (= QBID). Used in
            # f1040.compute to derive taxable_income_before_qbi_deduction
            # (no single named range exists for the pre-QBI figure).
            "_qbi_deduction_1040": "QBID_1040",
            # Form 8582 line 11: total losses allowed from all passive
            # activities. Oracle cross-check target for forms.f8582.compute.
            "f8582_line_11_oracle": "F8582_Line11",
            # Form 8949 per-subsection totals. Each physical sheet (8949A,
            # 8949B) carries one ST box (top-of-sheet checkbox = A or B) and
            # one LT box (mid-sheet checkbox = D or E) — ST sums Part I row 52,
            # LT sums Part II row 102. Suffixes: D=proceeds, E=basis,
            # G=adjustment, H=gain. Used as oracle cross-check targets for
            # forms.f8949.compute native math.
            "f8949_box_a_total_proceeds":   "F8949ASTD",
            "f8949_box_a_total_basis":      "F8949ASTE",
            "f8949_box_a_total_adjustment": "F8949ASTG",
            "f8949_box_a_total_gain":       "F8949ASTH",
            "f8949_box_b_total_proceeds":   "F8949BSTD",
            "f8949_box_b_total_basis":      "F8949BSTE",
            "f8949_box_b_total_adjustment": "F8949BSTG",
            "f8949_box_b_total_gain":       "F8949BSTH",
            "f8949_box_d_total_proceeds":   "F8949ALTD",
            "f8949_box_d_total_basis":      "F8949ALTE",
            "f8949_box_d_total_adjustment": "F8949ALTG",
            "f8949_box_d_total_gain":       "F8949ALTH",
            "f8949_box_e_total_proceeds":   "F8949BLTD",
            "f8949_box_e_total_basis":      "F8949BLTE",
            "f8949_box_e_total_adjustment": "F8949BLTG",
            "f8949_box_e_total_gain":       "F8949BLTH",
            # Form 8962 (Premium Tax Credit): net PTC (line 26) and
            # excess-APTC repayment (line 29). Named ranges — year-stable,
            # no SHEET_MAP entry needed (see 2024 note above).
            "f8962_net_ptc": "PTC_Net",
            "f8962_repayment": "PTC_Excess",
            # Form 1040 line 27 (earned income credit). Workbook-scoped name
            # in every year (the 1040 sheet's line-27 cell; the address
            # drifts). Tot_Payments already sums it through line 32, so
            # without this key the credit reached line 33 while line 27
            # printed blank.
            "eic": "EIC",
            # Form 1040 line 26 (estimated tax payments): the same
            # workbook-scoped name the INPUT writes, read back so line 26
            # prints. Tot_Payments sums it, so without this the page did
            # not foot (ruling R-S4-3; the eic / line-32 disease).
            "estimated_tax_payments": "EstimatedTaxPayments",
            # Form 1040 line 32 by address; see the 2024 block.
            "total_other_payments": "AL123",
        },
    }


# 2025 numeric-cell probes (see WORKBOOK_PROBES_2025): harvested by cell
# address, routed to their sheet by SHEET_MAP. 2025 only; no prior year
# inherits from 2025.
for _key, _probe in WORKBOOK_PROBES_2025.items():
    F1040.OUTPUTS[2025][_key] = _probe.cell
    F1040.SHEET_MAP[2025][_key] = _probe.sheet
del _key, _probe

# --- W-2 employers 2..6 and the spouse's W-2 block (2021-2025) --------------
#
# The 'W-2s' sheet holds six employers per person in columns C..H: the
# taxpayer's block, and the SPOUSE's block -- same row labels, captioned with
# the spouse's name (Name_1st_Sp) -- at a fixed row offset below it. Before
# this mapping only the taxpayer's employer #1 (column C) was written, so a
# spouse's W-2 or a second employer's never reached the sheet: the engine
# skips unmapped input keys, and the workbook computed a partial total.
# The flattener numbers W-2s per owner (`w2_<field>_<n>`,
# `w2_spouse_<field>_<n>`); every taxpayer field gets its spouse twin.
# Every federal year (2025 in declare-fallout, 2021-2024 in
# w2-blocks-backyears). The orchestrator still REFUSES any W-2 key a year does
# not map (`_refuse_unmapped_w2_inputs`) -- e.g. a seventh employer. Offsets
# verified from each year's workbook labels (2021 +29, 2022-2024 +31, 2025
# +37); each year's addresses are generated from ITS OWN employer-#1 anchors
# (2021's state rows sit one row above 2022's), AFTER every year's maps are
# built (end of module), so no year inherits another year's generated cells.
# Pinned per year by tests/test_w2_workbook_mapping.py.
_W2_FIELDS: tuple[str, ...] = (
    "wages", "fed_withheld", "ss_wages", "ss_withheld", "medicare_wages",
    "medicare_withheld", "state_wages", "state_withheld",
)
_W2_EMPLOYER_COLUMNS = "CDEFGH"
_W2_SPOUSE_ROW_OFFSET = {2021: 29, 2022: 31, 2023: 31, 2024: 31, 2025: 37}


def _w2_block_inputs(year: int) -> dict[str, str]:
    """Taxpayer employers 1..6 and spouse employers 1..6, every field, from
    the year's employer-#1 anchors (`w2_<field>_1`) and spouse row offset."""
    out: dict[str, str] = {}
    offset = _W2_SPOUSE_ROW_OFFSET[year]
    for field in _W2_FIELDS:
        anchor = F1040.INPUTS[year][f"w2_{field}_1"]
        assert anchor[0] == "C" and anchor[1:].isdigit(), anchor
        row = int(anchor[1:])
        for n, column in enumerate(_W2_EMPLOYER_COLUMNS, start=1):
            out[f"w2_{field}_{n}"] = f"{column}{row}"
            out[f"w2_spouse_{field}_{n}"] = f"{column}{row + offset}"
    return out


# --- Federal 2023 workbook wiring -------------------------------------------
# 2023 inherits the 2024 XLS cell/named-range mapping: the 2024 workbook carries
# the pre-2025 layout (the W-2 sheet's 6-fewer-rows-before-state-fields shift and
# the F8949 box slots at rows 35/88), which the TY2023 workbook from the same
# vendor lineage shares. Two families of per-year drift were found empirically
# (native-vs-oracle smoke + the full parity sweep) and are handled here:
#
# 1. Stray vendor data: the distributed workbook shipped with a hardcoded
#    -2,800 "amount of adjustment" at 8949A!AP115 (the last, otherwise-empty
#    row of the box-D long-term sum range Q88:Q115), which understated capital
#    gain by $2,800. Cleared in the committed workbook (surgical XML edit; no
#    formula/structure touched).
#
# 2. The 'Sch. A' sheet is shifted ONE COLUMN LEFT vs 2024 (verified: 2023 M29
#    holds 2024 N29's formula with every column -1 — R->Q, N->M, P->O; the
#    mortgage debt-limit cells and "Home mortgage interest" label move T->S;
#    property-tax reader O26='=ROUND(M25,0)' mirrors 2024 P26='=ROUND(N25,0)').
#    The named-range outputs (Standard/TotalDeductions/QBID) resolve by NAME so
#    they need no override, but the three Schedule A cell-ADDRESS references do:
#    mortgage_interest T37->S37 and property_tax N25->M25 (inputs), and the
#    sch_a_line_5e_salt_capped output N29->M29. The 'Sch 1, Line 1 (SALT)'
#    worksheet did NOT shift (O6/O8 still read P6/P8), so its filing-status
#    inputs are unchanged. With these three overrides the itemizer scenario
#    itemizes to 30,000 (line 5e capped at 10,000) and every scenario's line-5e
#    output reads 0 instead of None — native==oracle across the battery.
F1040.INPUTS[2023] = F1040.inherit(2024, {
    "mortgage_interest": "S37",   # 'Sch. A' col -1 (2024 T37)
    "property_tax": "M25",        # 'Sch. A' col -1 (2024 N25)
}, source="inputs")
F1040.OUTPUTS[2023] = F1040.inherit(2024, {
    "sch_a_line_5e_salt_capped": "M29",   # 'Sch. A' col -1 (2024 N29)
    "total_other_payments": "AD92",       # 1040 line 32 (2024 AD95)
}, source="outputs")
F1040.SHEET_MAP[2023] = dict(F1040.SHEET_MAP[2024])

# 2022's workbook matches 2023's layout EXCEPT the 'Sch. A' sheet, which the
# vendor reorganized vs 2023. Only the three 'Sch. A' cell-ADDRESS references
# need overrides (the named-range outputs Standard/TotalDeductions/QBID resolve
# by name); each verified per-cell against spreadsheets/federal/{2022,2023}/1040.xlsx:
#  - property_tax input +1 row (2023 M25 -> 2022 M26): 2022 reader
#    O27='=ROUND(M26,0)' mirrors 2023 O26='=ROUND(M25,0)'.
#  - sch_a_line_5e_salt_capped output +1 row (2023 M29 -> 2022 M30): 2022
#    M30='=IF(Q30<>"",ROUND(Q30,0),MIN(M28,O22))' mirrors 2023 M29's MIN(M27,O21).
#  - mortgage_interest input: the mortgage debt-limit block shifted -2 rows, so
#    2023 S37 -> 2022 S35. The 2022 deduction reader M38='=MIN(S43,ROUND(S35,0))'
#    consumes S35 exactly as 2023 M37='=MIN(S42,ROUND(S37,0))' consumes S37; the
#    debt limits (2023 S35/S36=1M/500k) sit at 2022 S33/S34.
# The 'Sch 1, Line 1 (SALT)' worksheet and all other input sheets align with
# 2023 (spot-checked). The cell-drift smoke over the itemizer scenario confirms.
# The 2022 '8582' sheet's passive-activity property table is shifted +1 ROW vs
# 2023 (proven: the column-sum consumer moved from 2023 N54='=SUM(N49..N53)' to
# 2022 N55='=SUM(N50..N54)', so the five property rows N49-N53 became N50-N54).
# Two consequences: (a) the Schedule-E row's net-income/net-loss cells (2023
# N49/R49) are absorbed into the 2022 header merge N48:Q49 / R48:U49, so they are
# read-only MergedCells and writing them raises AttributeError; (b) the K-1 rows
# (2023 N50-N53) stay writable but at 2022 would land one property row too high.
# Every 8582 cell-address reference therefore needs +1 row (all targets verified
# writable). Line-11 output likewise: 2023 AE43='=IF(AO21,"",SUM(AE39,AE41))' ->
# 2022 AE44='=IF(AO21,"",SUM(AE40,AE42))'.
_SCHE_8582_2022 = {
    "sche_8582_net_income": "N50", "sche_8582_net_loss": "R50",
    "k1_a_8582_net_income": "N51", "k1_a_8582_net_loss": "R51",
    "k1_a_8582_prior_year_loss": "V51",
    "k1_b_8582_net_income": "N52", "k1_b_8582_net_loss": "R52",
    "k1_b_8582_prior_year_loss": "V52",
    "k1_c_8582_net_income": "N53", "k1_c_8582_net_loss": "R53",
    "k1_c_8582_prior_year_loss": "V53",
    "k1_d_8582_net_income": "N54", "k1_d_8582_net_loss": "R54",
    "k1_d_8582_prior_year_loss": "V54",
}
F1040.INPUTS[2022] = F1040.inherit(2023, {
    "mortgage_interest": "S35",   # 'Sch. A' mortgage block -2 rows (2023 S37)
    "property_tax": "M26",        # 'Sch. A' +1 row (2023 M25)
    **_SCHE_8582_2022,            # '8582' property table +1 row (see note above)
}, source="inputs")
F1040.OUTPUTS[2022] = F1040.inherit(2023, {
    "sch_a_line_5e_salt_capped": "M30",   # 'Sch. A' +1 row (2023 M29)
    "f8582_line_11_oracle": "AE44",       # '8582' +1 row (2023 AE43)
    "total_other_payments": "AC86",       # 1040 line 32 (2023 AD92)
}, source="outputs")
F1040.SHEET_MAP[2022] = dict(F1040.SHEET_MAP[2023])


# --- Federal 2021 workbook wiring (BOUNDED PARTIAL WIRE) --------------------
# The TY2021 vendor workbook STRUCTURALLY OMITS the Form 8582 tab (passive-
# activity loss limitation): proven by named-range absence — F8582_Line9 /
# F8582_MAGI exist in the 2022 workbook and are gone in 2021, with no renamed
# equivalent. The passive-activity key group therefore has NO oracle target in
# 2021 no matter how it is wired. Rather than an ad-hoc drop, those keys are
# declared in the explicit WORKBOOK_KEY_EXCLUSIONS registry below, which:
#   (1) the parity harness READS and surfaces as explicit skips-with-reason
#       (never silently absent),
#   (2) is typo-guarded — a test asserts every excluded key exists in another
#       workbook year's map, and
#   (3) is governed by the restated invariant: a workbook year yields full
#       penny-parity over its DECLARED surface; exclusions are explicit,
#       reasoned, and gated.
# Every OTHER surface is wired off 2022 with full drift discipline — each moved
# cell is proven by a CONSUMER formula in the 2021 workbook, never by value-
# equality on a blank data-entry cell. Two sheets drifted vs 2022; the rest are
# identical (named-range outputs resolve by name and were verified present):
#
#  - 'W-2s': the state-tax rows shifted UP 1 (fewer intermediate rows in 2021).
#    Proven by the box-label column: box 16 label A22->A21, box 17 label
#    A23->A22 (boxes 1-6 labels at rows 3-8 are unchanged, so C3..C8 are
#    stable). So w2_state_wages_1 C22->C21 and w2_state_withheld_1 C23->C22.
#
#  - 'Sch. E': TWO different shifts in one sheet (a value-equality inference
#    would have gotten this wrong). The property-header row moved UP 1 while
#    the income+expense block moved UP 3. Both proven by the same consumer
#    formula: 2022 AZ24 '=IF(D21<>6,V30,0)' -> 2021 AZ23 '=IF(D20<>6,V27,0)'
#    (property_type D21->D20 is -1; rents V30->V27 is -3 in the SAME formula),
#    corroborated by the expense subtotal 2022 V48 '...SUM(V33:AC47)...' ->
#    2021 V45 '...SUM(V30:AC44)...' (the 15-row expense block -3) and the
#    depreciation rollups 2022 SUM(V40..)/SUM(V46..) -> 2021 SUM(V37..)/
#    SUM(V43..). So property cells (D/AA/AF)21 -> (…)20, and the income+
#    expense cells V30/V33..V47 -> V27/V30..V44.
#
#  - 'Sch. A': IDENTICAL to 2022 — mortgage reader MIN(S..,ROUND(S35,0)),
#    property reader O27='=ROUND(M26,0)', line-5e M30='=…MIN(M28,O22)' all
#    match, so the three 2022 cell-address overrides (S35/M26/M30) carry
#    unchanged.
#  - '8949A'/'8949B': IDENTICAL — F8949 box/total named ranges resolve to the
#    same cells (C25/C27/C78/C80 checkboxes; Q55/Q116 totals) and the section
#    headers sit at the same rows, so the 2022 F8949 box slots apply as-is.
#  - '1099-INT'/'1099-DIV': IDENTICAL — labels at the same rows (D6; 1a/1b/2a
#    at rows 6/7/8).
#
# The 33 named ranges present in 2022 but absent in 2021 (F2555 foreign-income
# family, IRA-distribution split, the F8582_* set) are scope-documented in the
# followups ledger; only the 8582 set is referenced by our maps and needs the
# exclusion. The Sch. E Part II K-1 cells ALSO drifted -3 (same as the income/
# expense block) and are overridden below — the battery populates no K-1s, but
# the merged-cell guard requires every input cell be writable, so they are
# re-homed onto their 2021 anchor cells. 1099-G cells are inherited unchanged
# (the battery populates no 1099-G, so they are never written); the soffice
# parity gate is the backstop for any cell we moved.

# (year, key) -> human reason. A workbook year yields full penny-parity over
# its DECLARED surface; where a vendor workbook structurally omits a form, that
# form's keys are excluded here — explicitly, with a reason, and gated. NOT an
# ad-hoc skip. Consumed by tests/test_f1040_spine_oracle.py.
WORKBOOK_KEY_EXCLUSIONS: dict[tuple[int, str], str] = {}
_F8582_KEYS_2022 = tuple(
    k for k, v in F1040.SHEET_MAP[2022].items() if v == "8582")
for _key in _F8582_KEYS_2022:
    WORKBOOK_KEY_EXCLUSIONS[(2021, _key)] = (
        "TY2021 vendor workbook omits the Form 8582 tab (passive-activity "
        "loss limitation) — no oracle target exists for this key")

_SCHE_2021 = {
    # property-header region: -1 row (proven by AZ23 IF(D20<>6,...) + row-21->20
    # property-column consumers).
    "sche_property_type_a": "D20",
    "sche_fair_rental_days_a": "AA20",
    "sche_personal_use_days_a": "AF20",
    # income + expense region: -3 rows (rents V30->V27 from the same AZ23
    # formula; the 15-row expense block V33..V47 -> V30..V44 from SUM range).
    "sche_rents_a": "V27",
    "sche_advertising_a": "V30",
    "sche_auto_and_travel_a": "V31",
    "sche_cleaning_and_maintenance_a": "V32",
    "sche_commissions_a": "V33",
    "sche_insurance_a": "V34",
    "sche_legal_and_professional_fees_a": "V35",
    "sche_management_fees_a": "V36",
    "sche_mortgage_interest_a": "V37",
    "sche_other_interest_a": "V38",
    "sche_repairs_a": "V39",
    "sche_supplies_a": "V40",
    "sche_taxes_a": "V41",
    "sche_utilities_a": "V42",
    "sche_depreciation_a": "V43",
    "sche_other_expenses_a": "V44",
    # Sch. E Part II (K-1 pass-through) is the SAME -3 shift as the income/
    # expense block. Proven by the printed entity-letter row markers (col B:
    # 'A' at 2022 row 80 -> 2021 row 77; income 'A' at 2022 row 88 -> 2021
    # row 85) and merge-geometry alignment (the entity-name merge C{r}:N{r}
    # and income merges C{r}:J{r}/K{r}:R{r} each shift -3 onto their writable
    # anchor cell). Without this override the inherited 2022 rows land on 2021
    # NON-anchor MergedCells (writes raise) — caught by the merged-cell guard.
    # The battery exercises no K-1s, so these are wired for map-writability +
    # completeness, not for parity coverage (K-1 income is not in PARITY_KEYS).
    "k1_a_entity_name": "C77",
    "k1_a_entity_type_s_corp": "O77",
    "k1_a_entity_type_partnership": "O77",
    "k1_a_entity_ein": "Y77",
    "k1_b_entity_name": "C78",
    "k1_b_entity_type_s_corp": "O78",
    "k1_b_entity_type_partnership": "O78",
    "k1_b_entity_ein": "Y78",
    "k1_c_entity_name": "C79",
    "k1_c_entity_type_s_corp": "O79",
    "k1_c_entity_type_partnership": "O79",
    "k1_c_entity_ein": "Y79",
    "k1_d_entity_name": "C80",
    "k1_d_entity_type_s_corp": "O80",
    "k1_d_entity_type_partnership": "O80",
    "k1_d_entity_ein": "Y80",
    "k1_a_passive_loss": "C85",
    "k1_a_passive_income": "K85",
    "k1_a_nonpassive_loss": "S85",
    "k1_a_nonpassive_income": "AH85",
    "k1_b_passive_loss": "C86",
    "k1_b_passive_income": "K86",
    "k1_b_nonpassive_loss": "S86",
    "k1_b_nonpassive_income": "AH86",
    "k1_c_passive_loss": "C87",
    "k1_c_passive_income": "K87",
    "k1_c_nonpassive_loss": "S87",
    "k1_c_nonpassive_income": "AH87",
    "k1_d_passive_loss": "C88",
    "k1_d_passive_income": "K88",
    "k1_d_nonpassive_loss": "S88",
    "k1_d_nonpassive_income": "AH88",
}


def _wire_2021() -> None:
    """Build 2021 maps off 2022 with the proven drift overrides, then drop the
    exclusion-registry keys from every map (inherit() merges but cannot remove,
    so the removal is explicit here and single-sourced from the registry)."""
    excluded = {k for (yr, k) in WORKBOOK_KEY_EXCLUSIONS if yr == 2021}
    inputs = F1040.inherit(2022, {
        "w2_state_wages_1": "C21",     # 'W-2s' box-16 row -1 (2022 C22)
        "w2_state_withheld_1": "C22",  # 'W-2s' box-17 row -1 (2022 C23)
        **_SCHE_2021,
        # Form 8962 monthly grid: 2021 rows are 52-63 (2022-2024 use
        # 48-59) — see _F8962_ROWS_2021 above.
        **_f8962_inputs(_F8962_ROWS_2021),
        # 2021-only UI-rule input: Part-A unemployment-compensation checkbox.
        # Any non-empty marker triggers the flat-133 household-income-pct
        # rule (8962 line 5 formula: IF(AI14<>"",133,...)). Absent in
        # 2022-2025 (the rule was a one-year ARPA provision).
        "f8962_ui_checkbox": "AI14",
        # 2021-only line 12b (CARES/CAA non-itemizer charitable). The `Charitable`
        # named range exists ONLY in the 2021 workbook (provision expired), so this
        # input is 2021-scoped here and deliberately NOT inherited into later years.
        "charitable_nonitemizer": "Charitable",
    }, source="inputs")
    outputs = F1040.inherit(2022, {  # Sch.A M30 unchanged
        "total_other_payments": "AC82",  # 1040 line 32 (2022 AC86)
    }, source="outputs")
    F1040.INPUTS[2021] = {k: v for k, v in inputs.items() if k not in excluded}
    F1040.OUTPUTS[2021] = {k: v for k, v in outputs.items()
                           if k not in excluded}
    F1040.SHEET_MAP[2021] = {
        **{k: v for k, v in F1040.SHEET_MAP[2022].items() if k not in excluded},
        "f8962_ui_checkbox": "8962",
    }


_wire_2021()


# W-2 blocks, every year -- here, after every year's maps exist (see the W-2
# section above for why the order matters).
for _year in _W2_SPOUSE_ROW_OFFSET:
    for _key, _address in _w2_block_inputs(_year).items():
        F1040.INPUTS[_year][_key] = _address
        F1040.SHEET_MAP[_year][_key] = "W-2s"
del _year, _key, _address


# 2024 numeric-cell probes (see WORKBOOK_PROBES_2024) -- wired HERE, after every
# year's maps exist: 2023 (and through it 2022/2021) is built by inheriting
# 2024's OUTPUTS, so wiring earlier would leak 2024's probes into those years.
for _key, _probe in WORKBOOK_PROBES_2024.items():
    F1040.OUTPUTS[2024][_key] = _probe.cell
    F1040.SHEET_MAP[2024][_key] = _probe.sheet
del _key, _probe


# 2023 numeric-cell probes (see WORKBOOK_PROBES_2023) -- also wired here, after
# every year's maps exist: 2022 (and through it 2021) is built by inheriting
# 2023's OUTPUTS, so wiring earlier would leak 2023's probes downward.
for _key, _probe in WORKBOOK_PROBES_2023.items():
    F1040.OUTPUTS[2023][_key] = _probe.cell
    F1040.SHEET_MAP[2023][_key] = _probe.sheet
del _key, _probe


# 2022 numeric-cell probes (see WORKBOOK_PROBES_2022) -- also wired here, after
# every year's maps exist: 2021 is built by inheriting 2022's OUTPUTS, so
# wiring earlier would leak 2022's probes into 2021.
for _key, _probe in WORKBOOK_PROBES_2022.items():
    F1040.OUTPUTS[2022][_key] = _probe.cell
    F1040.SHEET_MAP[2022][_key] = _probe.sheet
del _key, _probe


# 2021 numeric-cell probes (see WORKBOOK_PROBES_2021) -- wired here with the
# others, after every year's maps exist. 2021 is the oldest year (nothing
# inherits from it); end-of-module placement keeps the pattern uniform.
for _key, _probe in WORKBOOK_PROBES_2021.items():
    F1040.OUTPUTS[2021][_key] = _probe.cell
    F1040.SHEET_MAP[2021][_key] = _probe.sheet
del _key, _probe


# --- EIC Step 2 question 3 (Form 4797), 2021-2025 (ruling R-S7-6a) ----------
#
# When investment income exceeds the limit the sheet asks "Are you filing
# Form 4797?" (Q3); "No" means STOP, and only then. The "No" cell sits in
# NoEICredit's OR-chain unconditionally (A1 ... <no cell><>"" ...), so a bare
# "X" would deny every return. Unanswered, the stop never fires and the table
# credit flows through. tenforty never produces Form 4797 (the
# unreachability proof: tests/test_eic_grid_gates.py UNREACHABLE_ITEMS
# "form_4797"), so the workbook path answers "No" exactly when the sheet
# asks: a formula keyed to the year's own Q2 "Yes" cell. Addresses read by
# formula consumers; pinned per year by tests/test_eic_form_4797_answer.py.
class _EicForm4797Question(NamedTuple):
    sheet: str
    q2_yes: str   # Step 2 Q2 "Yes" (investment income over the limit)
    q3_yes: str   # Q3 "Yes, filing Form 4797" (left blank)
    q3_no: str    # "No" -- the STOP cell in NoEICredit (A1)


EIC_FORM_4797_QUESTION: dict[int, _EicForm4797Question] = {
    2025: _EicForm4797Question("Line 27a (EIC)", "B60", "B65", "H65"),
    2024: _EicForm4797Question("Line 27 (EIC)", "B60", "B65", "H65"),
    2023: _EicForm4797Question("Line 27 (EIC)", "B59", "B64", "H64"),
    2022: _EicForm4797Question("Line 27 (EIC)", "B59", "B64", "H64"),
    2021: _EicForm4797Question("Line 27a (EIC)", "B59", "B63", "H63"),
}
EIC_FORM_4797_NO_KEY = "eic_form_4797_no"


def eic_form_4797_no_answer(year: int) -> str:
    """The Q3 "No" cell's value: "X" exactly when Q2 is answered Yes."""
    return f'=IF({EIC_FORM_4797_QUESTION[year].q2_yes}<>"","X","")'


for _year, _q in EIC_FORM_4797_QUESTION.items():
    # Per-year copies: some years' maps were built from another's.
    F1040.INPUTS[_year] = {**F1040.INPUTS[_year],
                           EIC_FORM_4797_NO_KEY: _q.q3_no}
    F1040.SHEET_MAP[_year] = {**F1040.SHEET_MAP[_year],
                              EIC_FORM_4797_NO_KEY: _q.sheet}
del _year, _q


# --- EIC NoEICredit harvest, 2021-2025 (ruling R-S7-10) ----------------------
#
# The sheet's own "no credit" verdict (named range NoEICredit, A1 of the EIC
# sheet in every year). Line 27 never reads it — in every year the Step 2
# stop is display-only — so the workbook path harvests it and refuses a
# return whose line 27 contradicts it (orchestrator
# refuse_inconsistent_workbook_eic). Consumed there and dropped: it never
# reaches the results.
EIC_NO_CREDIT_DECLARED_KEY = "eic_no_credit_declared"

for _year in EIC_FORM_4797_QUESTION:
    F1040.OUTPUTS[_year] = {**F1040.OUTPUTS[_year],
                            EIC_NO_CREDIT_DECLARED_KEY: "NoEICredit"}
del _year


# --- EIC Step 1 question 4 (nonresident alien), 2022 only (catalog #10,
# ruling R-S8-11) --------------------------------------------------------------
#
# The 2022 template's derived "No" answer is inverted:
# H38 '=IF(AND(B38="",EIC_Check),"X","")' (2023: '=IF(B38="","X","")'; 2025:
# NOT(EIC_Check)). On an ordinary return Q4 is left unanswered, so
# EIC_Started (A38) is FALSE and E48:E50 drop taxable interest, dividends and
# capital gains from investment income — the Step 2 gate never fires and the
# R-S7-10 refusal is never armed. The workbook path restores the derive the
# other years carry: "No" exactly when "Yes" (B38) is not answered.
# (R-S7-2 refuses a stated nonresident-alien fact before this is written.)
EIC_Q4_NO_KEY = "eic_q4_nonresident_alien_no"
EIC_Q4_NO_CELL: dict[int, tuple[str, str]] = {
    2022: ("Line 27 (EIC)", "H38"),
}


def eic_q4_no_answer(year: int) -> str:
    """The restored Q4 "No" derive for ``year`` (keyed to its "Yes" cell)."""
    sheet, cell = EIC_Q4_NO_CELL[year]
    return f'=IF(B{cell[1:]}="","X","")'


for _year, (_sheet, _cell) in EIC_Q4_NO_CELL.items():
    F1040.INPUTS[_year] = {**F1040.INPUTS[_year], EIC_Q4_NO_KEY: _cell}
    F1040.SHEET_MAP[_year] = {**F1040.SHEET_MAP[_year], EIC_Q4_NO_KEY: _sheet}
del _year, _sheet, _cell
