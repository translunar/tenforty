"""Form 8995 (qualified business income deduction, simplified computation)
emit declarations, TY2021-2025.

Written from two independent author files and team-lead's adjudication
(/private/tmp/pilot-packet-f8995/ADJUDICATION.md). The authors worked only
from the official forms, the line inventories, the stylesheet and the
computation's output-key names. Their line sets and key bindings agree on
every line in every year; this module is the adjudicated union, written by
neither author.

THE SEAM. Four keys carry line numbers that are not their printed line; each
binds by MEANING against the official line text (both authors, blind):
    f8995_line_3_component           -> printed 5  (QBI component)
    f8995_line_4_reit_ptp            -> printed 6  (REIT/PTP income)
    f8995_line_5_reit_ptp_component  -> printed 9  (REIT/PTP component)
    f8995_line_6_total_before_limit  -> printed 10 (deduction before limit)
and the number-matching lines 3 and 4 bind the keys whose names say exactly
their meaning (the prior-year carryforward; the total QBI).

LINE 1 GRID. The paper prints a column-caption row "1" and five business
rows i-v, each with three cells: (a) name, (b) taxpayer identification
number, (c) qualified business income or (loss). Each QBI source gets its
own row (Juno's per-source-rows ruling, superseding the single-row
aggregate): row r binds f8995_line_1{r}_name / _tin / _qbi. The 15 cells
are plain lines with literal anchors (ruled option (A): Repeat does not
substitute anchors). The aggregate f8995_line_1_qbi is line 2's feed, not
printed on its own.

Descriptions are the stylesheet text where it matches the paper, the paper
otherwise (line 15 every year; line 12 in 2023). The line-1 cells exist in
neither witness and take the paper's column headings verbatim.

Anchors only where the label row cannot locate the field: lines 2, 6, 7, 8
and 15 every year and line 12 from 2023 wrap (AFTER_WRAPPED, a whole-token
phrase of the label's first printed row that prints exactly once); row i's
three cells share one row, so each row's (a) is RIGHT_OF its row label and
(b), (c) chain from it with NearField SAME_ROW_RIGHT_OF.

Every bound line is value-only, grounded in the producer: Form 8995 is
emitted only when line 15 or 16 is nonzero, and forms/f8995.compute assigns
every printed key on each call (row i from the first source with nonzero
QBI, which every emitted form has). Rows ii-v are two-state: they print only
when the return has that many sources. Every line-1 cell carries an
inventory exemption (the inventory prints bare row ids) and is still placed
by its explicit anchor. WITNESS_DISCREPANCIES holds only the stylesheet
cross-check's raw findings; WITNESS_NOTES documents what suppresses nothing.

2021 is the base year; 2022-2025 are ``derive`` diffs.
"""
from tenforty.declarations.anchors import (FieldRelation, LabelRelation,
                                           NearField, NearLabel)
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "f8995")
S = ""  # Form 8995 has no Part headings; both witnesses use section "".
YEARS = (2021, 2022, 2023, 2024, 2025)

COL_A = "(a) Trade, business, or aggregation name"
COL_B = "(b) Taxpayer identification number"
COL_C = "(c) Qualified business income or (loss)"
ROWS = ("i", "ii", "iii", "iv", "v")


# Every bound line is value-only (R3 ruling), grounded in the PRODUCER, not
# in battery observation: the orchestrator emits Form 8995 only when line 15
# or line 16 is nonzero (_should_emit_8995), and forms/f8995.compute assigns
# every printed key on each call, except the row-i name and TIN, which it
# assigns from the first source with nonzero QBI. A nonzero line 15 or 16
# needs nonzero QBI, so every emitted form has that source.
_EMITTED = ("Form 8995 is emitted only when its line 15 or line 16 is "
            "nonzero (orchestrator _should_emit_8995)")
_ROW_I_SOURCE = frozenset({"f8995_line_1i_name", "f8995_line_1i_tin",
                           "f8995_line_1i_qbi"})
_CELL_EXEMPTION = ("the inventory prints bare row ids (1i..1v), not the "
                   "three cells the paper prints per row; the cell is "
                   "placed by its explicit anchor")


def _always(line, description, key, kind):
    if key in _ROW_I_SOURCE:
        produced = (f"forms/f8995.compute assigns {key} from the first QBI "
                    "source (the Schedule C business with nonzero net "
                    "profit, else the first K-1 with nonzero QBI); a nonzero "
                    "line 15 or 16 needs nonzero QBI, so every emitted form "
                    "has that source")
    else:
        produced = f"forms/f8995.compute assigns {key} unconditionally"
    zero = "; zero is a value" if kind == "amount" else ""
    return (f"{_EMITTED}; {produced}, so every emitted form prints line "
            f"{line} ({description}){zero}")


def _b(line, description, key, mef, kind="amount", anchor=None,
       exemption=None):
    return DeclaredLine(line=line, description=description, key=key,
                        kind=kind, section=S, mef_element=mef, anchor=anchor,
                        single_state="value",
                        single_state_reason=_always(line, description, key,
                                                    kind),
                        inventory_exemption=exemption)


def _wrapped(phrase):
    """The field sits on the row after the label row printing ``phrase``."""
    return NearLabel(phrase=phrase, relation=LabelRelation.AFTER_WRAPPED)


_MEF = {"a": "TradeOrBusinessName/BusinessNameLine1Txt", "b": None,
        "c": "QlfyBusinessIncomeOrLossAmt"}
_COLUMNS = (("a", COL_A, "name", "text"), ("b", COL_B, "tin", "text"),
            ("c", COL_C, "qbi", "amount"))


def _row(row):
    """Row ``row``'s three cells. (a) is RIGHT_OF the row label; (b) and (c)
    chain along the row. (b) holds an SSN (a Schedule C source: the
    taxpayer's own, never an LLC's EIN) or an EIN (a K-1 source), so kind
    "text". Row i prints on every emitted form (value-only); rows ii-v only
    when the return has that many sources (two-state).

    GAP-BLIND PLACEMENT (registered design item): every row label prints
    once, so (a) places through the single-print RIGHT_OF path, which does
    not enforce LABEL_GAP_PT. The label-to-cell gaps are 15.4 pt every row
    2021-2023 and 14.2 / 13.1 / 11.9 / 11.9 / 13.1 pt (rows i-v) 2024-2025:
    over LABEL_GAP_PT 12 except rows iii and iv from 2024, the check-suite
    calibration case."""
    cells = []
    for col, description, suffix, kind in _COLUMNS:
        line, key = f"1{row}({col})", f"f8995_line_1{row}_{suffix}"
        anchor = (NearLabel(row, LabelRelation.RIGHT_OF) if col == "a" else
                  NearField(f"1{row}({chr(ord(col) - 1)})",
                            FieldRelation.SAME_ROW_RIGHT_OF))
        if row == "i":
            cells.append(_b(line, description, key, _MEF[col], kind=kind,
                            anchor=anchor, exemption=_CELL_EXEMPTION))
        else:
            cells.append(DeclaredLine(
                line=line, description=description, key=key, kind=kind,
                section=S, mef_element=_MEF[col], anchor=anchor,
                inventory_exemption=_CELL_EXEMPTION))
    return tuple(cells)


F8995_2021 = FormDeclaration(
    form=FORM,
    key=2021,
    lines=(
        DeclaredLine(
            line="1", description=" ".join((COL_A, COL_B, COL_C)), key="",
            kind="text", section=S,
            single_state="nothing",
            single_state_reason="caption: column-caption row for the line-1 "
            "grid; no entry space"),
        # Line 1: one row per QBI source, rows i-v (see _row).
        *(cell for row in ROWS for cell in _row(row)),
        _b("2", "Total qualified business income or (loss). Combine lines 1i "
           "through 1v, column (c)", "f8995_line_2_total_qbi",
           "TotQlfyBusinessIncomeOrLossAmt",
           anchor=_wrapped("Total qualified business income or (loss).")),
        _b("3", "Qualified business net (loss) carryforward from the prior "
           "year", "f8995_line_3_prior_qbi_loss_carryforward",
           "PYQlfyBusinessNetLossCfwdAmt"),
        _b("4", "Total qualified business income. Combine lines 2 and 3. If "
           "zero or less, enter -0-", "f8995_line_4_total_qbi",
           "TotQualifiedBusinessIncomeAmt"),
        _b("5", "Qualified business income component. Multiply line 4 by 20% "
           "(0.20)", "f8995_line_3_component", "QBIComponentAmt"),
        _b("6", "Qualified REIT dividends and publicly traded partnership "
           "(PTP) income or (loss) (see instructions)",
           "f8995_line_4_reit_ptp", "QlfyREITDivPTPIncomeLossAmt",
           anchor=_wrapped("Qualified REIT dividends and publicly traded "
                           "partnership")),
        _b("7", "Qualified REIT dividends and qualified PTP (loss) "
           "carryforward from the prior year",
           "f8995_line_7_prior_reit_ptp_loss_carryforward",
           "PYQlfyREITDivPTPLossCfwdAmt",
           anchor=_wrapped("Qualified REIT dividends and qualified PTP")),
        _b("8", "Total qualified REIT dividends and PTP income. Combine lines "
           "6 and 7. If zero or less, enter -0-",
           "f8995_line_8_total_reit_ptp", "TotQlfyREITDivPTPIncomeAmt",
           anchor=_wrapped("Total qualified REIT dividends and PTP income.")),
        _b("9", "REIT and PTP component. Multiply line 8 by 20% (0.20)",
           "f8995_line_5_reit_ptp_component", "REITPTPComponentAmt"),
        _b("10", "Qualified business income deduction before the income "
           "limitation. Add lines 5 and 9", "f8995_line_6_total_before_limit",
           "QBIDedBfrIncomeLimitationAmt"),
        _b("11", "Taxable income before qualified business income deduction",
           "f8995_line_11_taxable_income", "TaxableIncomeBeforeQBIDedAmt"),
        _b("12", "Net capital gain (see instructions)",
           "f8995_line_12_net_capital_gain", "NetCapitalGainAmt"),
        _b("13", "Subtract line 12 from line 11. If zero or less, enter -0-",
           "f8995_line_13_subtract", "AdjustedTaxableIncomeAmt"),
        _b("14", "Income limitation. Multiply line 13 by 20% (0.20)",
           "f8995_line_14_income_limit", "IncomeLimitationAmt"),
        _b("15", "Qualified business income deduction. Enter the smaller of "
           "line 10 or line 14. Also enter this amount on the applicable line "
           "of your return (see instructions)", "f8995_line_15_qbi_deduction",
           "QualifiedBusinessIncomeDedAmt",
           anchor=_wrapped("Qualified business income deduction. Enter the "
                           "smaller")),
        _b("16", "Total qualified business (loss) carryforward. Combine lines "
           "2 and 3. If greater than zero, enter -0-",
           "f8995_line_16_qbi_loss_carryforward",
           "TotQlfyBusLossCarryforwardAmt"),
        DeclaredLine(
            line="17", description="Total qualified REIT dividends and PTP "
            "(loss) carryforward. Combine lines 6 and 7. If greater than "
            "zero, enter -0-", key="", kind="amount", section=S,
            mef_element="TotQlfyREITDivPTPLossCfwdAmt",
            single_state="nothing",
            single_state_reason="unmodeled: Total qualified REIT dividends "
            "and PTP (loss) carryforward"),
    ),
    not_printed={
        "f8995_line_1_qbi": ("intermediate: the sum of the line-1 rows' "
                             "whole-dollar QBI, line 2's feed; each row's "
                             "own QBI prints in its column (c)"),
        "taxpayer_name": ("presentation-only: header 'Name(s) shown on "
                          "return', outside the line inventory"),
        "taxpayer_ssn": ("presentation-only: header 'Your taxpayer "
                         "identification number', outside the line "
                         "inventory"),
    },
)

F8995_2022 = derive(F8995_2021, 2022)

# 2023: line 12's paper text changes ("increased by any qualified
# dividends") and now wraps; its field is on the row after the phrase.
F8995_2023 = derive(F8995_2022, 2023, drop=[(S, "12")], add=[
    _b("12", "Enter your net capital gain, if any, increased by any "
       "qualified dividends (see instructions)",
       "f8995_line_12_net_capital_gain", "NetCapitalGainAmt",
       anchor=_wrapped("Enter your net capital gain, if any,"))])
F8995_2024 = derive(F8995_2023, 2024)
F8995_2025 = derive(F8995_2024, 2025)

DECLARATIONS = {decl.key: decl for decl in (
    F8995_2021, F8995_2022, F8995_2023, F8995_2024, F8995_2025)}


# Witness discrepancies (exact (section, line) -> (years, reason)): each
# suppresses exactly its own stylesheet cross-check finding in the years
# listed, and goes stale-red if the stylesheet agrees
# (tenforty.verification.crosscheck.discrepancies_in_force).
_NO_LINE_1 = ("the stylesheet lists no line-1 lines at all (it starts at "
              "line 2); the line-1 row elements (business name, SSN/EIN, "
              "QlfyBusinessIncomeOrLossAmt) appear only in line 17's "
              "trailing element list. The paper prints the caption row and "
              "five rows of three cells")
WITNESS_DISCREPANCIES = {
    (S, "1"): (YEARS, _NO_LINE_1),
    **{(S, f"1{row}({col})"): (YEARS, _NO_LINE_1)
       for row in ("i", "ii", "iii", "iv", "v") for col in ("a", "b", "c")},
    (S, "12"): ((2023,), "the 2023 stylesheet still reads 'Net capital gain "
                "(see instructions)' (the 2021-2022 wording); the 2023 paper "
                "reads 'Enter your net capital gain, if any, increased by any "
                "qualified dividends (see instructions)'. Paper text used; "
                "the 2024 stylesheet catches up"),
}
# Witness structure that suppresses no finding (no raw cross-check finding
# exists for it): documented so the declaration's choices are explained.
WITNESS_NOTES = {
    (S, "1i..1v"): (YEARS, "the PDF inventory encodes one id per business "
                    "ROW (1i..1v, empty text); the paper prints three cells "
                    "per row, which the instructions name 'line 1(b)', "
                    "'line 1(c)'. Declared per cell; every cell carries an "
                    "inventory exemption"),
    (S, "15"): (YEARS, "stylesheet 'Enter the lesser of line 10 or line 14 "
                "... of your return'; paper 'Enter the smaller of ... (see "
                "instructions)'. Paper text used; the text agreement still "
                "passes, so no cross-check finding exists"),
}
