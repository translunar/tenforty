"""Schedule SE (Form 1040) emit declarations, TY2021-2025.

Written from two independent author files and team-lead's adjudication of
their differences (emit-verification protocol steps 2-4). The authors worked
only from the official forms, the line inventories and the computation's
output-key names. Their bindings agree on every line in every year. This
module is the adjudicated union, and was not written by either author.

Every printed line appears once per year: bound to its compute key, or
declared with ``key=""`` and ``single_state="nothing"`` and a reason.
Sub-lines carry their full printed label ("1b", "4c", "8d"). Descriptions
are the official line text, verbatim from the MeF stylesheet extraction,
including where that text is stale against the year's official PDF (2023
line 12; 2025 lines 8a and 15).

An anchor is declared only where the line's printed label row cannot locate
its entry field: lines 2, 4c, 7, 8a and 13 every year, and line 12 from 2023,
when its label wraps. Anchor phrases end on token boundaries as printed,
trailing punctuation included ("line 31;"): the evaluator matches whole
``pdftotext`` words, so a phrase cut inside a token prints zero times.

2021 is the base year; 2022-2025 are ``derive`` diffs. A line whose text or
anchor changes is dropped and re-added with the same binding.
"""
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "sch_se")
P1, P2 = "Part I", "Part II"


def _bound(section, line, description, key, anchor=None):
    return DeclaredLine(line=line, description=description, key=key,
                        kind="amount", section=section, anchor=anchor)


def _unserved(section, line, description, reason, kind="amount",
              anchor=None):
    return DeclaredLine(line=line, description=description, key="",
                        kind=kind, section=section, anchor=anchor,
                        single_state="nothing",
                        single_state_reason="unmodeled: " + reason)


def _wrapped(phrase):
    """The entry field sits on the row after the label row printing
    ``phrase``."""
    return NearLabel(phrase=phrase, relation=LabelRelation.AFTER_WRAPPED)


_LINE_7 = ("Maximum amount of combined wages and self-employment earnings "
           "subject to social security tax or the 6.2% portion of the 7.65% "
           "railroad retirement (tier 1) tax for {year}")
_LINE_8A = ("Total social security wages and tips (total of boxes 3 and 7 on "
            "Form(s) W-2) and railroad retirement (tier 1) compensation. If "
            "{base} or more, skip lines 8b through 10, and go to line 11")
_LINE_15 = ("Enter the smaller of: two-thirds ( 2 / 3 ) of gross farm income "
            "1 (not less than zero) or {cap}. Also include this amount on "
            "line 4b above")
_LINE_1B = ("If you received social security retirement or disability "
            "benefits, enter the amount of Conservation Reserve Program "
            "payments included on Schedule F, line 4b, or listed on Schedule "
            "K-1 (Form 1065), box 20, code {code}")
_LINE_12_2021 = ("Self-employment tax. Add lines 10 and 11. Enter here and on "
                 "Schedule 2 (Form 1040), line 4.")
_LINE_12_2024 = ("Self-employment tax. Add lines 10 and 11. Enter here and on "
                 "Schedule 2 (Form 1040), line 4 , or Form 1040-SS, Part I, "
                 "line 3")

_OPTIONAL = "optional methods (Part II farm/nonfarm): "


def _line_7(year):
    # The official template preprints the year's wage base on a read-only
    # field, so nothing is filled here; the key is in not_printed (ruling).
    # The anchor is kept: the label wraps to the field's row.
    return DeclaredLine(
        line="7", description=_LINE_7.format(year=year), key="",
        kind="amount", section=P1,
        anchor=_wrapped("Maximum amount of combined wages and "
                        "self-employment earnings"),
        single_state="nothing",
        single_state_reason=(
            "preprinted: the official template prints the year's wage base; "
            "the field is read-only"))


def _line_8a(base):
    # Three-row label; the phrase is the continuation row, unique on the
    # page (the bare "8a" token also prints on a different row).
    return _bound(P1, "8a", _LINE_8A.format(base=base),
                  "sch_se_line_8a_ss_wages_and_tips",
                  anchor=_wrapped(
                      "and railroad retirement (tier 1) compensation."))


def _line_15(cap):
    return _unserved(P2, "15", _LINE_15.format(cap=cap),
                     _OPTIONAL + "farm optional method amount")


def _line_1b(code):
    return _unserved(P1, "1b", _LINE_1B.format(code=code),
                     "Conservation Reserve Program payments of a social "
                     "security retirement/disability recipient")


_LINE_12_ANCHOR = _wrapped("Self-employment tax. Add lines 10 and 11.")

SCH_SE_2021 = FormDeclaration(
    form=FORM,
    key=2021,
    lines=(
        _unserved(
            P1, "A",
            "If you are a minister, member of a religious order, or Christian "
            "Science practitioner and you filed Form 4361, but you had $400 "
            "or more of other net earnings from self-employment, check here "
            "and continue with Part I",
            "Form 4361 filer (minister / religious order / Christian Science "
            "practitioner) with $400 or more of other SE earnings checkbox",
            kind="checkbox"),
        _unserved(
            P1, "1a",
            "Net farm profit or (loss) from Schedule F, line 34, and farm "
            "partnerships, Schedule K-1 (Form 1065), box 14, code A.",
            "net farm profit or (loss), Schedule F line 34 and farm K-1 "
            "(Form 1065) box 14 code A"),
        _line_1b("AH"),
        # The label wraps: the field is on the row after "2".
        _bound(P1, "2",
               "Net profit or (loss) from Schedule C, line 31; and Schedule "
               "K-1 (Form 1065), box 14, code A (other than farming). See "
               "instructions for other income to report or if you are a "
               "minister or member of a religious order.",
               "sch_se_line_2_net_profit",
               anchor=_wrapped(
                   "Net profit or (loss) from Schedule C, line 31;")),
        _bound(P1, "3", "Combine lines 1a, 1b, and 2",
               "sch_se_line_3_net_profit"),
        _bound(P1, "4a",
               "If line 3 is more than zero, multiply line 3 by 92.35% "
               "(0.9235). Otherwise, enter amount from line 3",
               "sch_se_line_4a_net_earnings"),
        _unserved(
            P1, "4b",
            "If you elect one or both of the optional methods, enter the "
            "total of lines 15 and 17 here",
            _OPTIONAL + "total of lines 15 and 17"),
        # The label wraps: the field is on the row after "c".
        _bound(P1, "4c",
               "Combine lines 4a and 4b. If less than $400, stop; you don't "
               "owe self-employment tax. Exception: If less than $400 and you "
               "had church employee income, enter -0- and continue",
               "sch_se_line_4c_net_earnings",
               anchor=_wrapped(
                   "Combine lines 4a and 4b. If less than $400, stop;")),
        _unserved(
            P1, "5a",
            "Enter your church employee income from Form W-2. See "
            "instructions for definition of church employee income",
            "church employee income from Form W-2"),
        _unserved(
            P1, "5b",
            "Multiply line 5a by 92.35% (0.9235). If less than $100, enter "
            "-0-",
            "line 5a x 92.35% (church employee income)"),
        _bound(P1, "6", "Add lines 4c and 5b",
               "sch_se_line_6_total_net_earnings"),
        _line_7(2021),
        _line_8a("$142,800"),
        _unserved(
            P1, "8b",
            "Unreported tips subject to social security tax from Form 4137, "
            "line 10",
            "unreported tips subject to social security tax from Form 4137, "
            "line 10"),
        _unserved(
            P1, "8c",
            "Wages subject to social security tax from Form 8919, line 10",
            "wages subject to social security tax from Form 8919, line 10"),
        _bound(P1, "8d", "Add lines 8a, 8b, and 8c",
               "sch_se_line_8d_wages_subject_to_ss"),
        _bound(P1, "9",
               "Subtract line 8d from line 7. If zero or less, enter -0- "
               "here and on line 10 and go to line 11",
               "sch_se_line_9_ss_earnings_remaining"),
        _bound(P1, "10",
               "Multiply the smaller of line 6 or line 9 by 12.4% (0.124)",
               "sch_se_line_10_ss_portion"),
        _bound(P1, "11", "Multiply line 6 by 2.9% (0.029)",
               "sch_se_line_11_medicare_portion"),
        # One label row in 2021-2022; it wraps from 2023 (anchored there).
        _bound(P1, "12", _LINE_12_2021, "sch_se_line_12_se_tax"),
        # Three-row label; the phrase is the second row.
        _bound(P1, "13", "Deduction for one-half of self-employment tax.",
               "sch_se_line_13_half_deduction",
               anchor=_wrapped("Multiply line 12 by 50% (0.50).")),
        _unserved(
            P2, "14", "Maximum income for optional methods.",
            _OPTIONAL + "maximum income for optional methods (amount "
            "preprinted on the form)"),
        _line_15("$5,880"),
        _unserved(P2, "16", "Subtract line 15 from line 14",
                  _OPTIONAL + "line 14 minus line 15"),
        _unserved(
            P2, "17",
            "Enter the smaller of: two-thirds ( 2 / 3 ) of gross nonfarm "
            "income 4 (not less than zero) or the amount on line 16. Also "
            "include this amount on line 4b above",
            _OPTIONAL + "nonfarm optional method amount"),
    ),
    not_printed={
        "sch_se_line_7_ss_wage_base": (
            "intermediate: feeds lines 8d/9; the official template preprints "
            "the figure on a read-only field, so no fill occurs"),
        # Header prints have no inventory line; a header mechanism is an
        # open pilot question (ruling: not_printed for now).
        "taxpayer_name": (
            "presentation-only: header fields outside the line inventory"),
        "taxpayer_ssn": (
            "presentation-only: header fields outside the line inventory"),
    },
)

_YEARLY = [(P1, "7"), (P1, "8a"), (P2, "15")]


def _yearly(year, base, cap):
    return [_line_7(year), _line_8a(base), _line_15(cap)]


SCH_SE_2022 = derive(SCH_SE_2021, 2022, drop=_YEARLY,
                     add=_yearly(2022, "$147,000", "$6,040"))

# 2023: line 1b's K-1 code changes AH -> AQ. The official 2023 form prints
# line 12's Form 1040-SS clause, which wraps its label, so line 12 gains an
# anchor; the 2023 inventory text still lacks the clause (kept verbatim).
SCH_SE_2023 = derive(
    SCH_SE_2022, 2023, drop=_YEARLY + [(P1, "1b"), (P1, "12")],
    add=_yearly(2023, "$160,200", "$6,560") + [
        _line_1b("AQ"),
        _bound(P1, "12", _LINE_12_2021, "sch_se_line_12_se_tax",
               anchor=_LINE_12_ANCHOR)])

# 2024: the inventory's line 12 text gains the Form 1040-SS clause.
SCH_SE_2024 = derive(
    SCH_SE_2023, 2024, drop=_YEARLY + [(P1, "12")],
    add=_yearly(2024, "$168,600", "$6,920") + [
        _bound(P1, "12", _LINE_12_2024, "sch_se_line_12_se_tax",
               anchor=_LINE_12_ANCHOR)])

# 2025: the inventory still carries the 2024 figures in lines 8a and 15
# (the official 2025 form prints $176,100 and $7,240); kept verbatim.
SCH_SE_2025 = derive(SCH_SE_2024, 2025, drop=_YEARLY,
                     add=_yearly(2025, "$168,600", "$6,920"))

DECLARATIONS = {decl.key: decl for decl in (
    SCH_SE_2021, SCH_SE_2022, SCH_SE_2023, SCH_SE_2024, SCH_SE_2025)}
