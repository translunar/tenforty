"""Schedule 2 (Form 1040) emit declarations, TY2021-2025.

The adjudicated union of two independent authors
(/private/tmp/pilot-packet-sch_2/ADJUDICATION.md): author A's structure,
not_printed entries and MeF elements (the union: A's fill B's Nones), author
B's line-21 anchor, and on each differing description the paper-accurate
variant (verified against the official template text: line 3 in 2021-2023
and line 1e in 2024 and 2025 follow author B).

Conventions (standing rulings): line universe = the official paper form,
each printed (section, line) once; unserved lines key="", single_state=
"nothing", reason "unmodeled: <meaning>"; descriptions = stylesheet text
verbatim, official PDF text where the stylesheet is wrong or stale (each
case in WITNESS_DISCREPANCIES); anchors only where the default label row
fails.

LAYOUT SEAM (TY2024): Part I was restructured. 2021-2023: line 1 =
alternative minimum tax, line 2 = excess advance premium tax credit (APTC)
repayment, line 3 = add 1 and 2. 2024-2025: line 1 = caption "Additions to
tax:", 1a = excess APTC repayment, 1b-1f/1y = new additions, 1z = add 1a-1y,
line 2 = alternative minimum tax, line 3 = add 1z and 2 (39 lines -> 47).
Keys bind by MEANING, never by name: the line-2 APTC key binds line 2 only
through 2023; from 2024 paper line 2 is the AMT and is unserved.
"""
import dataclasses

from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "sch_2")
P1, P2 = "Part I", "Part II"

_APTC_1A = "sch_2_line_1a_excess_aptc_repayment"
_APTC_2 = "sch_2_line_2_excess_aptc_repayment"
_TOT_1Z = "sch_2_line_1z_total_additions"


def _bound(section, line, d, key, mef, anchor=None, always=None):
    """``always``: the reason the line is value-only (single_state="value")."""
    return DeclaredLine(line=line, description=d[(section, line)], key=key,
                        kind="amount", section=section, anchor=anchor,
                        mef_element=mef,
                        single_state="value" if always else None,
                        single_state_reason=always)


# Value-only totals: the computation emits them on every Schedule 2
# (forms/sch_2.py sets both keys unconditionally), and on the paper they are
# the Part I and Part II totals every filer completes: zero is a value.
_TOTAL = ("the computation emits this total on every Schedule 2 "
          "(forms/sch_2.py sets it unconditionally), and on the paper it is "
          "the part total every filer completes: zero is a value")


def _unserved(section, line, d, meaning, mef=None, kind="amount"):
    return DeclaredLine(line=line, description=d[(section, line)], key="",
                        kind=kind, section=section, mef_element=mef,
                        single_state="nothing",
                        single_state_reason="unmodeled: " + meaning)


# ------------------------------------------------- descriptions (verbatim)
_D21 = {
    ('Part I', '1'): 'Alternative minimum tax. Attach Form 6251',
    ('Part I', '2'): 'Excess advance premium tax credit repayment. Attach Form 8962',
    ('Part I', '3'): 'Add lines 1 and 2. Enter here and on Form 1040, 1040-SR, or 1040-NR, line 17',
    ('Part II', '4'): 'Self-employment tax. Attach Schedule SE',
    ('Part II', '5'): 'Social security and Medicare tax on unreported tip income. Attach Form 4137',
    ('Part II', '6'): 'Uncollected social security and Medicare tax on wages. Attach Form 8919',
    ('Part II', '7'): 'Total additional social security and Medicare tax. Add lines 5 and 6',
    ('Part II', '8'): 'Additional tax on IRAs or other tax-favored accounts. Attach Form 5329 if required',
    ('Part II', '9'): 'Household employment taxes. Attach Schedule H',
    ('Part II', '10'): 'Repayment of first-time homebuyer credit. Attach Form 5405 if required',
    ('Part II', '11'): 'Additional Medicare Tax. Attach Form 8959',
    ('Part II', '12'): 'Net investment income tax. Attach Form 8960',
    ('Part II', '13'): 'Uncollected social security and Medicare or RRTA tax on tips or group-term life insurance from Form W-2, box 12',
    ('Part II', '14'): 'Interest on tax due on installment income from the sale of certain residential lots and timeshares',
    ('Part II', '15'): 'Interest on the deferred tax on gain from certain installment sales with a sales price over $150,000',
    ('Part II', '16'): 'Recapture of low-income housing credit. Attach Form 8611',
    ('Part II', '17'): 'Other additional taxes:',
    ('Part II', '17a'): 'Recapture of other credits. List type, form number, and amount',
    ('Part II', '17b'): 'Recapture of federal mortgage subsidy. If you sold your home in 2021, see instructions',
    ('Part II', '17c'): 'Additional tax on HSA distributions. Attach Form 8889',
    ('Part II', '17d'): "Additional tax on an HSA because you didn't remain an eligible individual. Attach Form 8889",
    ('Part II', '17e'): 'Additional tax on Archer MSA distributions. Attach Form 8853',
    ('Part II', '17f'): 'Additional tax on Medicare Advantage MSA distributions. Attach Form 8853',
    ('Part II', '17g'): 'Recapture of a charitable contribution deduction related to a fractional interest in tangible personal property',
    ('Part II', '17h'): 'Income you received from a nonqualified deferred compensation plan that fails to meet the requirements of section 409A',
    ('Part II', '17i'): 'Compensation you received from a nonqualified deferred compensation plan described in section 457A',
    ('Part II', '17j'): 'Section 72(m)(5) excess benefits tax',
    ('Part II', '17k'): 'Golden parachute payments',
    ('Part II', '17l'): 'Tax on accumulation distribution of trusts',
    ('Part II', '17m'): 'Excise tax on insider stock compensation from an expatriated corporation',
    ('Part II', '17n'): 'Look-back interest under section 167(g) or 460(b) from Form 8697 or 8866',
    ('Part II', '17o'): 'Tax on non-effectively connected income for any part of the year you were a nonresident alien from Form 1040-NR',
    ('Part II', '17p'): 'Any interest from Form 8621, line 16f, relating to distributions from, and dispositions of, stock of a section 1291 fund',
    ('Part II', '17q'): 'Any interest from Form 8621, line 24',
    ('Part II', '17z'): 'Any other taxes. List type and amount',
    ('Part II', '18'): 'Total additional taxes. Add lines 17a through 17z',
    ('Part II', '19'): 'Additional tax from Schedule 8812',
    ('Part II', '20'): 'Section 965 net tax liability installment from Form 965-A',
    ('Part II', '21'): 'Add lines 4, 7 through 16, 18 and 19. These are your total other taxes. Enter here and on Form 1040 or 1040-SR, line 23, or Form 1040-NR, line 23b',
}
_TEXT_2022 = {  # description changes vs 2021 (existing lines)
    ('Part II', '8'): 'Additional tax on IRAs or other tax-favored accounts. Attach Form 5329 if required. If not required, check here',
    ('Part II', '17b'): 'Recapture of federal mortgage subsidy, if you sold your home, see instructions',
    ('Part II', '19'): 'Reserved for future use',
    ('Part II', '21'): 'Add lines 4, 7 through 16, and 18. These are your total other taxes. Enter here and on Form 1040 or 1040-SR, line 23, or Form 1040-NR, line 23b',
}
_TEXT_2023 = {  # description changes vs 2022 (existing lines)
}
_TEXT_2024 = {  # description changes vs 2023 (existing lines)
    ('Part I', '1'): 'Additions to tax:',
    ('Part I', '2'): 'Alternative minimum tax. Attach Form 6251',
    ('Part I', '3'): 'Add lines 1z and 2. Enter here and on Form 1040, 1040-SR, or 1040-NR, line 17',
    ('Part II', '17a'): 'Recapture of other credits. List type, form number, and amount:',
    ('Part II', '17z'): 'Any other taxes. List type and amount:',
    ('Part II', '19'): 'Recapture of net EPE from Form 4255, line 1d, column (l)',
    ('Part II', '21'): 'Add lines 4, 7 through 16, 18, and 19. These are your total other taxes. Enter here and on Form 1040 or 1040-SR, line 23, or Form 1040-NR, line 23b',
}
_NEW_2024 = {  # lines first printed in 2024
    ('Part I', '1a'): 'Excess advance premium tax credit repayment. Attach Form 8962',
    ('Part I', '1b'): 'Repayment of new clean vehicle credit(s) transferred to a registered dealer from Schedule A (Form 8936), Part II. Attach Form 8936 and Schedule A (Form 8936)',
    ('Part I', '1c'): 'Repayment of previously owned clean vehicle credit(s) transferred to a registered dealer from Schedule A (Form 8936), Part IV. Attach Form 8936 and Schedule A (Form 8936)',
    ('Part I', '1d'): 'Recapture of net EPE from Form 4255, line 2a, column (l)',
    ('Part I', '1e'): 'Excessive payments (EP) from Form 4255. Check applicable box and enter amount. (i) Line 1a, column (n) (ii) Line 1c, column (n) (iii) Line 1d, column (n) (iv) Line 2a, column (n)',
    ('Part I', '1f'): '20% EP from Form 4255. Check applicable box and enter amount. See instructions. (i) Line 1a, column (o) (ii) Line 1c, column (o) (iii) Line 1d, column (o) (iv) Line 2a, column (o)',
    ('Part I', '1y'): 'Other additions to tax (see instructions):',
    ('Part I', '1z'): 'Add lines 1a through 1y',
}
_TEXT_2025 = {  # description changes vs 2024 (existing lines)
    ('Part I', '1e'): 'Excessive payments (EPs) on gross EPE from Form 4255. Check applicable box and enter amount. See instructions. (i) Line 1a (ii) Line 1c (iii) Line 1d (iv) Line 2a',
    ('Part I', '1f'): '20% EP from Form 4255. Check applicable box and enter amount. See instructions. (i) Line 1a (ii) Line 1c (iii) Line 1d (iv) Line 2a',
    ('Part II', '4'): 'Self-employment tax. Attach Schedule SE. Check if any exemption from (see instructions): 1 4361 2 4029 3',
    ('Part II', '10'): 'Reserved for future use',
    ('Part II', '21'): 'Add lines 4, 7 through 16, 18 and 19. These are your total other taxes. Enter here and on Form 1040 or 1040-SR, line 23, or Form 1040-NR, line 23b',
}


# Line 21 wraps every year: the entry box is on the label's second row. The
# phrase is the first row's prefix in every year, including the year-varying
# 2024-2025 sum text (adjudication ruling 2), and prints once on page 2. It
# ends on the printed token "16," (ruled: the comma is part of the token).
_A21 = NearLabel(phrase="Add lines 4, 7 through 16,",
                 relation=LabelRelation.AFTER_WRAPPED)


def _part_ii(d):
    return (
        # 4: auto_confirmed. MeF amount element is SelfEmploymentTaxAmt (the
        # proposal's evidence cited its exemption-code attribute instead).
        _bound(P2, "4", d, "sch_2_line_4_se_tax", "SelfEmploymentTaxAmt"),
        _unserved(P2, "5", d, "social security and Medicare tax on unreported "
                  "tip income (Form 4137)", "SocSecMedicareTaxUnrptdTipAmt"),
        _unserved(P2, "6", d, "uncollected social security and Medicare tax "
                  "on wages (Form 8919)", "UncollectedSocSecMedTaxAmt"),
        _unserved(P2, "7", d, "total additional social security and Medicare "
                  "tax, lines 5 + 6", "UnrprtdSocSecAndMedcrTaxAmt"),
        _unserved(P2, "8", d, "additional tax on IRAs or other tax-favored "
                  "accounts (Form 5329)", "TaxOnIRAsAmt"),
        _unserved(P2, "9", d, "household employment taxes (Schedule H)",
                  "HouseholdEmploymentTaxAmt"),
        _unserved(P2, "10", d, "repayment of first-time homebuyer credit "
                  "(Form 5405)", "FirstTimeHmByrRepaymentAmt"),
        _bound(P2, "11", d, "sch_2_line_11_additional_medicare_tax",
               "TotalAMRRTTaxAmt"),                             # auto_confirmed
        _unserved(P2, "12", d, "net investment income tax (Form 8960)",
                  "IndivNetInvstIncomeTaxAmt"),
        _unserved(P2, "13", d, "uncollected social security and Medicare or "
                  "RRTA tax on tips or group-term life insurance (W-2 box 12)",
                  "UncollSSMedcrRRTAGrpInsTxAmt"),
        _unserved(P2, "14", d, "interest on tax due on installment income "
                  "from certain residential lots and timeshares",
                  "IntTaxDueInstalSaleIncmAmt"),
        _unserved(P2, "15", d, "interest on deferred tax on gain from certain "
                  "installment sales over $150,000",
                  "IntDefrdTaxGainInstalSalesAmt"),
        _unserved(P2, "16", d, "recapture of low-income housing credit "
                  "(Form 8611)", "RecaptureTaxAmt"),
        _unserved(P2, "17", d, "caption only ('Other additional taxes:'); "
                  "amounts go on 17a-17z"),
        _unserved(P2, "17a", d, "recapture of other credits (type, form "
                  "number, amount)", "TotalRecaptureOtherCreditsAmt"),
        _unserved(P2, "17b", d, "recapture of federal mortgage subsidy",
                  "MortgSbsdyRecaptureTaxAmt"),
        _unserved(P2, "17c", d, "additional tax on HSA distributions",
                  "HSADistriAddnlPercentTaxAmt"),
        _unserved(P2, "17d", d, "additional tax on an HSA (eligibility not "
                  "maintained)", "HDHPCoverageAddnlTaxAmt"),
        _unserved(P2, "17e", d, "additional tax on Archer MSA distributions",
                  "ArcherMSAAddnlDistriTaxAmt"),
        _unserved(P2, "17f", d, "additional tax on Medicare Advantage MSA "
                  "distributions", "MedicareMSAAddnlDistriTaxAmt"),
        _unserved(P2, "17g", d, "recapture of charitable deduction for a "
                  "fractional interest in tangible personal property",
                  "RecaptureChrtblContriDedAmt"),
        _unserved(P2, "17h", d, "income from a nonqualified deferred "
                  "compensation plan failing section 409A",
                  "IncmNonqlfyDefrdCompPlanAmt"),
        _unserved(P2, "17i", d, "compensation from a section 457A "
                  "nonqualified deferred compensation plan",
                  "CompNonqlfyDefrdCompPlanAmt"),
        _unserved(P2, "17j", d, "section 72(m)(5) excess benefits tax",
                  "Sect72m5ExcessBenefitsTaxAmt"),
        _unserved(P2, "17k", d, "golden parachute payments",
                  "ExcessParachutePaymentAmt"),
        _unserved(P2, "17l", d, "tax on accumulation distribution of trusts",
                  "PartialTaxOnAccumDistriAmt"),
        _unserved(P2, "17m", d, "excise tax on insider stock compensation "
                  "from an expatriated corporation",
                  "InsiderStockCompExciseTaxAmt"),
        _unserved(P2, "17n", d, "look-back interest (Form 8697 or 8866)",
                  "LookBackIntSect167gOr460bAmt"),
        _unserved(P2, "17o", d, "tax on non-effectively connected income "
                  "(nonresident alien part-year, Form 1040-NR)",
                  "IncomeNotUSBusinessTaxAmt"),
        _unserved(P2, "17p", d, "interest from Form 8621 line 16f (section "
                  "1291 fund)", "InterestOnEachNetIncrInTaxAmt"),
        _unserved(P2, "17q", d, "interest from Form 8621 line 24",
                  "AccruedInterestDueThisRetAmt"),
        _unserved(P2, "17z", d, "any other taxes (type and amount)",
                  "TotalAnyOtherTaxesAmt"),
        _unserved(P2, "18", d, "total additional taxes, lines 17a-17z",
                  "TotalOtherAdditionalTaxesAmt"),
        _unserved(P2, "19", d, "additional tax from Schedule 8812 (TY2021 "
                  "advance child tax credit)", "AdvncCTCAdditionalTaxAmt"),
        _unserved(P2, "20", d, "section 965 net tax liability installment "
                  "(Form 965-A); not part of line 21's sum",
                  "Section965TaxInstallmentAmt"),
        # 21 (proposal 'disagree' in 2021-23; auto_confirmed 2024): official
        # "Add lines 4, 7 through 16, 18, and 19 [2022-23: 4, 7 through 16,
        # and 18]. These are your total other taxes." Key name matches.
        # PARTIAL-TOTAL RISK: only lines 4 and 11 of the summed lines carry
        # keys; line 21 must still total every summed line (7-10, 12-16, 18,
        # 19) including the unmodeled ones. Line 20 is NOT in the sum.
        _bound(P2, "21", d, "sch_2_line_21_total_other_taxes",
               "TotalOtherTaxesAmt", anchor=_A21, always=_TOTAL),
    )


def _part_i_2021(d):
    return (
        _unserved(P1, "1", d, "alternative minimum tax (Form 6251)",
                  "AlternativeMinimumTaxAmt"),
        # 2: auto_confirmed (2021-23 layout: excess APTC repayment, Form 8962).
        _bound(P1, "2", d, _APTC_2, "PremiumTaxCreditTaxLiabAmt"),
        # 3 (seam): official "Add lines 1 and 2". Key name matches.
        # PARTIAL-TOTAL RISK: line 1 (AMT) is unmodeled, but line 3 must
        # still include it.
        _bound(P1, "3", d, "sch_2_line_3_part_i_total", "AdditionalTaxAmt",
               always=_TOTAL),
    )


# not_printed per layout, tag "other-year:" (team-lead ruling): each key
# names a line that exists only in the other layout's years.
_HEADER = {
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "Form 1040, 1040-SR, or 1040-NR', outside the line "
                      "inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
}
_NP_2021 = {
    **_HEADER,
    _APTC_1A: ("other-year: prints on line 1a only in 2024-2025; in "
               "2021-2023 excess APTC repayment prints on line 2 (key "
               + _APTC_2 + ")"),
    _TOT_1Z: ("other-year: prints on line 1z only in 2024-2025; 2021-2023 "
              "Part I has no additions subtotal"),
}
_NP_2024 = {
    **_HEADER,
    # SEAM: from TY2024 line 2 is the alternative minimum tax. The key's
    # name carries the old line number (2) but the old meaning (excess
    # APTC repayment), which now prints on line 1a under its own key. Name
    # and line conflict; binding it to line 2 would print an APTC amount on
    # the AMT line. Declared not printed; line 2 is unserved.
    _APTC_2: ("other-year: prints on line 2 only in 2021-2023; from 2024 "
              "line 2 is alternative minimum tax and excess APTC repayment "
              "prints on line 1a (key " + _APTC_1A + ")"),
}

SCH_2_2021 = FormDeclaration(form=FORM, key=2021,
                             lines=_part_i_2021(_D21) + _part_ii(_D21),
                             not_printed=_NP_2021)


def _revise(base, key, text=None, reason=None, mef=None, anchor=None,
            drop=(), add=(), not_printed=None):
    """Field-level year diff: lines whose description/reason/mef/anchor
    change are dropped and re-added (moving to the end); ``drop``/``add``
    pass through; ``not_printed`` replaces the base mapping."""
    text, reason, mef, anchor = (text or {}, reason or {}, mef or {},
                                 anchor or {})
    by_id = {ln.line_id: ln for ln in base.lines}
    ids = [i for i in dict.fromkeys([*text, *reason, *mef, *anchor])
           if i not in drop]
    new = []
    for i in ids:
        upd = {}
        if i in text:
            upd["description"] = text[i]
        if i in reason:
            upd["single_state_reason"] = "unmodeled: " + reason[i]
        if i in mef:
            upd["mef_element"] = mef[i]
        if i in anchor:
            upd["anchor"] = anchor[i]
        new.append(dataclasses.replace(by_id[i], **upd))
    out = derive(base, key, drop=[*drop, *ids], add=[*new, *add])
    if not_printed is not None:
        out = dataclasses.replace(out, not_printed=dict(not_printed))
    return out


# 2022: line 19 becomes "Reserved for future use" (was the Schedule 8812
# additional tax); line 21 drops 19 from its sum; line 8 gains its
# "If not required, check here" box.
SCH_2_2022 = _revise(SCH_2_2021, 2022, text=_TEXT_2022, reason={
    (P2, "19"): "reserved for future use; no entry"},
    # 17a: the 2022-2023 stylesheet lists only the RecaptureOtherCreditsGrp
    # elements, no total (ruling 3 amended: per-year witness-backed).
    mef={(P2, "19"): None, (P2, "17a"): None})

SCH_2_2023 = _revise(SCH_2_2022, 2023, text=_TEXT_2023)

# 2024: Part I restructure (see module docstring). Old lines 1-3 are dropped
# and the new Part I declared whole. Line 19 becomes recapture of net EPE
# (Form 4255) and line 21 sums 19 again.
_D24 = {**_D21, **_TEXT_2022, **_TEXT_2023, **_TEXT_2024, **_NEW_2024}
_PART_I_2024 = (
    _unserved(P1, "1", _D24, "caption only ('Additions to tax:'); amounts "
              "go on 1a-1y"),
    # 1a: auto_confirmed (2024 layout: excess APTC repayment, Form 8962).
    _bound(P1, "1a", _D24, _APTC_1A, "PremiumTaxCreditTaxLiabAmt"),
    _unserved(P1, "1b", _D24, "repayment of new clean vehicle credit(s) "
              "transferred to a registered dealer (Form 8936 Sch. A Part II)",
              "CrTrnsfrDlrSaleAmt"),
    _unserved(P1, "1c", _D24, "repayment of previously owned clean vehicle "
              "credit(s) transferred to a dealer (Form 8936 Sch. A Part IV)",
              "PrevOwnCrTrnsfrDlrSaleAmt"),
    _unserved(P1, "1d", _D24, "recapture of net EPE (Form 4255 line 2a, "
              "column (l))", "RcptrPrtnNetEPECrAmt"),
    _unserved(P1, "1e", _D24, "excessive payments from Form 4255 (option "
              "boxes (i)-(iv) + amount)",
              "ExcessivePymtFrom4255Grp/ExPymt100CrAmt"),
    _unserved(P1, "1f", _D24, "20% EP from Form 4255 (option boxes (i)-(iv) "
              "+ amount)",
              "IncreaseChapter1TaxFrom4255Grp/TotEx20PrvlWgAprntcshpPnltyAmt"),
    _unserved(P1, "1y", _D24, "other additions to tax",
              "TotalOtherTaxAdditionsAmt"),
    # 1z: auto_confirmed. Official "Add lines 1a through 1y".
    # PARTIAL-TOTAL RISK: only 1a carries a key; 1z must still include
    # 1b-1y.
    _bound(P1, "1z", _D24, _TOT_1Z, "TotalTaxAdditionsAmt"),
    # 2: SEAM -- see _NP_2024. Official 2024 line 2 is the AMT; no key names
    # the AMT, so the line is unserved.
    _unserved(P1, "2", _D24, "alternative minimum tax (Form 6251)",
              "AlternativeMinimumTaxAmt"),
    # 3 (seam): official "Add lines 1z and 2". Key name matches.
    # PARTIAL-TOTAL RISK: line 2 (AMT) and 1b-1y are unmodeled.
    _bound(P1, "3", _D24, "sch_2_line_3_part_i_total", "AdditionalTaxAmt",
           always=_TOTAL),
)
SCH_2_2024 = _revise(
    SCH_2_2023, 2024,
    text={k: v for k, v in _TEXT_2024.items() if k[0] == P2},
    reason={(P2, "19"): "recapture of net EPE (Form 4255 line 1d, column "
            "(l))"},
    mef={(P2, "19"): "Frm3468IVRcptrPrtnNetEPECrAmt",
         (P2, "17a"): "TotalRecaptureOtherCreditsAmt"},
    drop=[(P1, "1"), (P1, "2"), (P1, "3")], add=_PART_I_2024,
    not_printed=_NP_2024)

# 2025: line 4 gains SE-exemption boxes (Form 4361 / 4029 / other) on a
# second row, and the amount entry moves to that row (label "4" y467, entry
# box label "4" y479). That row also holds the three exemption boxes and the
# other-exemption text entry, so a row-only anchor is ambiguous: the anchor
# is the box label "4" immediately left of the amount entry (gap 8 pt <
# LABEL_GAP_PT); the left-margin "4" (x45) has text, not an entry, to its
# right. Line 10 becomes "Reserved for future use".
SCH_2_2025 = _revise(
    SCH_2_2024, 2025, text=_TEXT_2025,
    reason={(P2, "10"): "reserved for future use; no entry"},
    mef={(P2, "10"): None},
    anchor={(P2, "4"): NearLabel(phrase="4",
                                 relation=LabelRelation.RIGHT_OF)})

DECLARATIONS = {d.key: d for d in
                (SCH_2_2021, SCH_2_2022, SCH_2_2023, SCH_2_2024, SCH_2_2025)}


# ---------------------------------------------------- witness records
_ALL = (2021, 2022, 2023, 2024, 2025)
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force).
WITNESS_DISCREPANCIES = {
    (P1, "1"): ((2024, 2025), "the stylesheet caption reads 'Addittions to "
                "tax:' (typo); the paper prints 'Additions to tax:'. "
                "Description from the paper"),
}
# Witness divergences that suppress no finding (the declared text still
# agrees with the stylesheet within the cross-check threshold): documented
# so the paper-over-stylesheet choices are explained.
WITNESS_NOTES = {
    (P2, "16"): (_ALL, "the stylesheet reads 'Recapture of low-interest "
                 "housing credit'; the paper prints 'low-income housing "
                 "credit' (Form 8611). Description from the paper"),
    (P2, "21"): ((2024,), "the 2024 stylesheet still reads 'Add lines 4, 7 "
                 "through 16, and 18' (the 2022-2023 sum); the 2024 paper "
                 "sums '4, 7 through 16, 18, and 19'. Description from the "
                 "paper"),
    (P1, "3"): ((2021, 2022, 2023), "the stylesheet reads 'Enter here and "
                "include on Form 1040'; the paper prints 'Enter here and on "
                "Form 1040'. Description from the paper"),
    (P1, "1e"): ((2024, 2025), "the stylesheet omits the paper's '(EP)' "
                 "(2024) and prints '(EP)' for the paper's '(EPs)' (2025). "
                 "Description from the paper"),
    (P2, "17*"): ((2021, 2022, 2023), "the inventory carries empty text on "
                  "the 17a-17z sub-lines (first-row truncation family); "
                  "descriptions from the paper and stylesheet"),
}

# ---------------------------------------------------- partial-total risks
# A total line whose summed lines are mostly unmodeled must still be the
# total of every summed line (the partial-total failure species). Each entry:
# (section, line) -> {year: the printed lines it sums}. Line 21's sum varies
# by year: 19 is in for 2021 and 2024-2025, out for 2022-2023; 20 never is.
_P2_SUM = ("4", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "18")
PARTIAL_TOTAL_RISKS = {
    (P2, "21"): {2021: _P2_SUM + ("19",), 2022: _P2_SUM, 2023: _P2_SUM,
                 2024: _P2_SUM + ("19",), 2025: _P2_SUM + ("19",)},
    (P1, "3"): {2021: ("1", "2"), 2022: ("1", "2"), 2023: ("1", "2"),
                2024: ("1z", "2"), 2025: ("1z", "2")},
    (P1, "1z"): {2024: ("1a", "1b", "1c", "1d", "1e", "1f", "1y"),
                 2025: ("1a", "1b", "1c", "1d", "1e", "1f", "1y")},
}
