"""Federal Schedule B (Form 1040) emit declarations, TY2021-2025.

Author "c"'s declaration (the adjudicated base,
/private/tmp/pilot-packet-sch_b/ADJUDICATION.md): bindings, kinds, states,
mef elements and descriptions converged 100% between the two authors. Keys
carry no line numbers; bound by meaning. Every explicit anchor phrase ends
on a pdftotext token boundary and prints exactly once on its page.

Payer grids (lines 1 and 5): the paper prints 14 interest rows and 16
(2021) / 15 (2022-2025) dividend rows, unlabeled, and tenforty fills every
one (forms/sch_b.compute returns the payer lists; the orchestrator writes
interest_payer_<i> / dividend_payer_<i> for each). Row 1: the bare
inventory line binds the payer name; the amount is a composed sub-line
labeled with the printed column caption "Amount". Rows 2..N (payer-row
ruling 2026-10-19, S2, superseding the single-row ruling, whose premise
"row 1 only" came from a probe that sampled single-payer scenarios): each
row is declared under a POSITIONAL locator, "1[<i>]" / "5[<i>]" for the
payer and "1[<i>](Amount)" / "5[<i>](Amount)" for the amount. The bracket
is a locator, not printed text: the rows carry no printed identity, and
they are declared because real keys serve them. Every row cell is
two-state (absent when the return has fewer payers) and carries an
inventory exemption naming the ruling.

Measured geometry: "baseline" = text-row yMax, "box" = widget top-bottom,
top-left origin, points.
"""
import dataclasses

from tenforty.declarations.anchors import (
    FieldRelation,
    LabelRelation,
    NearField,
    NearLabel,
)
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "sch_b")

P1, P2, P3 = "Part I", "Part II", "Part III"

_Q1 = ("payer-row shape ruling 2026-10-18 (single row) with the Q1 composed "
       "sub-line convention: row-1 amount cell of inventory line {line}; "
       "label is the printed column caption 'Amount'")


# Posture, grounded in the producer (forms/sch_b.compute and
# orchestrator._flatten_sch_b_rows): the four totals are set on every
# Schedule B, zero included (value-only). The row-1 payer and amount keys
# exist only when the return has an interest (resp. dividend) payer: a
# dividends-only Schedule B has no interest row, so those lines are
# two-state.
_EMITTED = ("forms/sch_b.compute sets this key on every Schedule B, zero "
            "included, so its nothing state is unreachable")
_TWO_STATE = frozenset({
    f"{stem}_{cell}_{i}" for stem, rows in (("interest", 14), ("dividend", 16))
    for cell in ("payer", "amount") for i in range(1, rows + 1)})


def _bound(section, line, description, key, kind="amount", *, mef=None,
           anchor=None, exemption=None):
    value_only = key not in _TWO_STATE
    return DeclaredLine(line=line, description=description, key=key,
                        kind=kind, section=section, anchor=anchor,
                        mef_element=mef, inventory_exemption=exemption,
                        single_state="value" if value_only else None,
                        single_state_reason=_EMITTED if value_only else None)


def _unserved(section, line, description, meaning, kind):
    return DeclaredLine(line=line, description=description, key="",
                        kind=kind, section=section, single_state="nothing",
                        single_state_reason=f"unmodeled: {meaning}")


_ROW = ("payer-row ruling 2026-10-19 (S2): positional locator {loc} for "
        "unlabeled payer row {i} of inventory line {line}; the bracketed "
        "index is a locator, not printed text")


def _payer_rows(section, line, stem, rows, payer_mef, amount_mef):
    """Rows 2..``rows`` of a payer grid. Every row is 12.0 pt below the one
    above (measured, all years), cells abutting. Each amount chains below
    the previous row's amount (one column, x 489.6, all rows); each payer
    below the previous row's payer.
    column unconstrained: anchor vocabulary has no column relation."""
    out = []
    for i in range(2, rows + 1):
        loc = f"{line}[{i}]"
        above = line if i == 2 else f"{line}[{i - 1}]"
        exemption = _ROW.format(loc=loc, i=i, line=line)
        out.append(DeclaredLine(
            line=loc, description=f"payer row {i} (unlabeled)",
            key=f"{stem}_payer_{i}", kind="text", section=section,
            anchor=NearField(above, FieldRelation.NEXT_ROW_BELOW),
            mef_element=payer_mef, inventory_exemption=exemption))
        out.append(DeclaredLine(
            line=f"{loc}(Amount)",
            description=f"payer row {i} (unlabeled): Amount",
            key=f"{stem}_amount_{i}", kind="amount", section=section,
            anchor=NearField(f"{above}(Amount)",
                             FieldRelation.NEXT_ROW_BELOW),
            mef_element=amount_mef, inventory_exemption=exemption))
    return tuple(out)


_LINES_2021 = (
    # --- Part I: Interest ---------------------------------------------------
    # Row 1 of 14 unlabeled payer rows (rows 2-14 follow). The 3-row
    # label ends on "... show that buyer's social security number and
    # address"; the row-1 name box (x 129.6-460.8, 144-156) is the row
    # below: edge gap 2.5 (2021: phrase 141.5) / 0.6 (2022+: 143.4).
    # column unconstrained: anchor vocabulary has no column relation.
    _bound(P1, "1", "List name of payer. If any interest is from a "
           "seller-financed mortgage and the", "interest_payer_1", "text",
           mef="InterestPayerName/BusinessNameLine1Txt",
           anchor=NearLabel("show that buyer’s social security number",
                            LabelRelation.AFTER_WRAPPED)),
    # Row-1 amount box (x 489.6-576, 144-156), right of the name box.
    _bound(P1, "1(Amount)", "Amount", "interest_amount_1", mef="InterestAmt",
           anchor=NearField("1", FieldRelation.SAME_ROW_RIGHT_OF),
           exemption=_Q1.format(line="1")),
    *_payer_rows(P1, "1", "interest", 14,
                 "InterestPayerName/BusinessNameLine1Txt", "InterestAmt"),
    _bound(P1, "2", "Add the amounts on line 1", "total_interest",
           mef="TaxableInterestSubtotalAmt"),
    # Wrapped: label 336.6, box 336-348 beside the wrap row 347.4 (field
    # overlaps the phrase row).
    _bound(P1, "3", "Excludable interest on series EE and I U.S. savings "
           "bonds issued after 1989.", "excludable_savings_bond",
           mef="ExcludableSavingsBondIntAmt",
           anchor=NearLabel("Excludable interest on series EE",
                            LabelRelation.AFTER_WRAPPED)),
    # 2021 wrapped: label 360.0, box 360-372 beside wrap row 369.5.
    _bound(P1, "4", "Subtract line 3 from line 2. Enter the result here and "
           "on Form 1040 or 1040-SR,", "taxable_interest",
           mef="CalculatedTotalTaxableIntAmt",
           anchor=NearLabel("Subtract line 3 from line 2.",
                            LabelRelation.AFTER_WRAPPED)),
    # --- Part II: Ordinary Dividends ----------------------------------------
    # Row 1 of 16 (2021) / 15 (2022-2025) unlabeled payer rows (rows 2..N
    # follow). Row 1's short
    # name box (x 209.1-460.8, 384-396) sits on the label row (395.4).
    # column unconstrained: anchor vocabulary has no column relation.
    _bound(P2, "5", "List name of payer", "dividend_payer_1", "text",
           mef="DividendPayerNameBusiness/BusinessNameLine1Txt"),
    _bound(P2, "5(Amount)", "Amount", "dividend_amount_1", mef="DividendAmt",
           anchor=NearField("5", FieldRelation.SAME_ROW_RIGHT_OF),
           exemption=_Q1.format(line="5")),
    *_payer_rows(P2, "5", "dividend", 16,
                 "DividendPayerNameBusiness/BusinessNameLine1Txt",
                 "DividendAmt"),
    # 2021 wrapped: label 588.2, box 588-600 beside wrap row 597.5.
    _bound(P2, "6", "Add the amounts on line 5. Enter the total here and on "
           "Form 1040 or 1040-SR,", "total_ordinary_dividends",
           mef="TotalOrdinaryDividendsAmt",
           anchor=NearLabel("Add the amounts on line 5.",
                            LabelRelation.AFTER_WRAPPED)),
    # --- Part III: Foreign Accounts and Trusts (no keys) --------------------
    # Unserved, so no anchors: the Yes/No boxes sit under the Part III
    # "Yes"/"No" column captions (629.9 in 2021), not beside per-line ones.
    _unserved(P3, "7a", "At any time during 2021, did you have a financial "
              "interest in or signature authority over",
              "Yes/No: financial interest in or signature authority over a "
              "foreign financial account; and Yes/No: required to file "
              "FinCEN Form 114", "checkbox"),
    _unserved(P3, "7b", "If you are required to file FinCEN Form 114, enter "
              "the name of the foreign country",
              "name of the foreign country where the account is located",
              "text"),
    _unserved(P3, "8", "During 2021, did you receive a distribution from, or "
              "were you the grantor of, or transferor",
              "Yes/No: distribution from, grantor of, or transferor to a "
              "foreign trust", "checkbox"),
)

_NOT_PRINTED = {
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "return', outside the line inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
}

_D2021 = FormDeclaration(form=FORM, key=2021, lines=_LINES_2021,
                         not_printed=_NOT_PRINTED)


def _redescribe(base, key, descriptions, *, anchors=None):
    """Year diff: lines whose inventory text changed are dropped and re-added
    with the new verbatim text; ``anchors`` replaces a line's anchor the same
    way (None = back to the default label-row anchor)."""
    anchors = anchors or {}
    by_id = {ln.line_id: ln for ln in base.lines}
    ids = list(dict.fromkeys([*descriptions, *anchors]))
    new = []
    for lid in ids:
        changes = {}
        if lid in descriptions:
            changes["description"] = descriptions[lid]
        if lid in anchors:
            changes["anchor"] = anchors[lid]
        new.append(dataclasses.replace(by_id[lid], **changes))
    return derive(base, key, drop=ids, add=new)


def _year_text(year):
    return {
        (P3, "7a"): (f"At any time during {year}, did you have a financial "
                     "interest in or signature authority over"),
        (P3, "8"): (f"During {year}, did you receive a distribution from, or "
                    "were you the grantor of, or transferor"),
    }


# 2022: re-layout of Part I lines 4-6 and Part III.
#  * Line 4 no longer wraps (label 358.9, box 348-360): explicit anchor
#    DROPPED. Line 6 no longer wraps (562.9, box 552-564): DROPPED.
#  * Dividend grid moves up 12pt and loses one row (16 -> 15: payer row 16
#    is dropped); row 1's short
#    name box (x 201.6-460.8, 372-384) stays on the label row (383.0).
#  * Line 3 still wraps (same anchor). Line 1 label's last row moves to
#    143.4 (edge gap to row 1 now 0.6).
#  * Texts: 4/5/6/7b change; 7a/8 carry the year.
_D2022_ROWS = derive(_D2021, 2022, drop=((P2, "5[16]"),
                                          (P2, "5[16](Amount)")))
_D2022 = _redescribe(_D2022_ROWS, 2022, {
    (P1, "4"): ("Subtract line 3 from line 2. Enter the result here and on "
                "Form 1040 or 1040-SR, line 2b"),
    (P2, "5"): "List name of payer:",
    (P2, "6"): ("Add the amounts on line 5. Enter the total here and on Form "
                "1040 or 1040-SR, line 3b"),
    (P3, "7b"): ("If you are required to file FinCEN Form 114, list the "
                 "name(s) of the foreign country(-ies)"),
    **_year_text(2022),
}, anchors={
    (P1, "4"): None,
    (P2, "6"): None,
})

# 2023-2025: only the year inside 7a/8 changes. Widgets identical to 2022
# (header box x shifts only).
_D2023 = _redescribe(_D2022, 2023, _year_text(2023))
_D2024 = _redescribe(_D2023, 2024, _year_text(2024))
_D2025 = _redescribe(_D2024, 2025, _year_text(2025))

DECLARATIONS = {decl.key: decl for decl in
                (_D2021, _D2022, _D2023, _D2024, _D2025)}


# ---------------------------------------------------- witness records
_ALL = (2021, 2022, 2023, 2024, 2025)
_FIRST_ROW = ("the declaration carries the inventory's text for this line, "
              "its first printed row; the stylesheet carries the full "
              "multi-row label, so the word overlap falls below the "
              "cross-check threshold")
_LUMPED = ("the stylesheet has no label {line}: the {kind} payer elements "
           "({elements}) are lumped under label {under}, so the payer "
           "grid's row-1 {cell} is not a stylesheet line")
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force).
WITNESS_DISCREPANCIES = {
    (P1, "1"): (_ALL, _LUMPED.format(
        line="1", kind="interest", under="8", cell="payer name",
        elements="InterestPayerName/..., InterestAmt")),
    (P1, "1(Amount)"): (_ALL, _LUMPED.format(
        line="1", kind="interest", under="8", cell="amount",
        elements="InterestPayerName/..., InterestAmt")),
    (P2, "5"): (_ALL, _LUMPED.format(
        line="5", kind="dividend", under="4 and again under 8",
        cell="payer name",
        elements="DividendPayerNameBusiness/..., DividendAmt")),
    (P2, "5(Amount)"): (_ALL, _LUMPED.format(
        line="5", kind="dividend", under="4 and again under 8",
        cell="amount",
        elements="DividendPayerNameBusiness/..., DividendAmt")),
    (P3, "7a"): (_ALL, _FIRST_ROW),
    (P3, "8"): (_ALL, _FIRST_ROW),
    # Payer rows 2..N (S2 positional locators): lumped like row 1.
    **{(P1, f"1[{i}]{cell}"): (_ALL, _LUMPED.format(
        line="1", kind="interest", under="8",
        cell=f"row-{i} {'amount' if cell else 'payer name'}",
        elements="InterestPayerName/..., InterestAmt"))
       for i in range(2, 15) for cell in ("", "(Amount)")},
    **{(P2, f"5[{i}]{cell}"): (_ALL if i <= 15 else (2021,), _LUMPED.format(
        line="5", kind="dividend", under="4 and again under 8",
        cell=f"row-{i} {'amount' if cell else 'payer name'}",
        elements="DividendPayerNameBusiness/..., DividendAmt"))
       for i in range(2, 17) for cell in ("", "(Amount)")},
}
# Witness structure that suppresses no finding: documented so the
# declaration's choices are explained.
WITNESS_NOTES = {
    (P3, "7b"): (_ALL, "the stylesheet labels it bare 'b'; composed to 7b"),
    ("", "page_section"): (_ALL, "every stylesheet entry has an empty "
                           "page_section"),
    (P1, "3"): (_ALL, "the stylesheet reads 'series EE and l U.S.' "
                "(lower-case L); the paper reads 'I'. Within the "
                "cross-check threshold"),
    ("", "7a indicators"): (_ALL, "7a carries two indicators "
                            "(ForeignAccountsQuestionInd, FinCENForm114Ind): "
                            "the paper prints two Yes/No pairs under 7a "
                            "(boxes 661-671 and 697-707 in 2021). Both "
                            "unmodeled"),
    ("", "payer rows 2..N"): (_ALL, "the paper prints 14 interest rows and "
                              "16 (2021) / 15 (2022-2025) dividend rows, "
                              "unlabeled; rows 2..N are declared under "
                              "positional locators (S2 ruling 2026-10-19)"),
}
