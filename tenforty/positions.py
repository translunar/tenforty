"""Contested-law positions (spec §13).

Some computations force a choice between readings of unresolved law.
tenforty never embeds such a choice silently: each one is registered here
with the question, each side's citation trail (authority vs commentary
labeled, and how faithfully the source text is reproduced), what each
choice does to the return, and the date it was recorded. A return whose
numbers flow through a registered position must elect a side explicitly.

Sources are public legal materials only. ``fidelity`` says how the
``text`` relates to the source: ``verbatim`` (the quoted words are the
source's own), ``paraphrased`` (substance confirmed against the source,
wording ours), or ``secondhand`` (known only through secondary summaries).
"""
import dataclasses
import datetime
from collections.abc import Mapping
from types import MappingProxyType

SOURCE_KINDS = frozenset({"authority", "commentary"})
FIDELITIES = frozenset({"verbatim", "paraphrased", "secondhand"})


@dataclasses.dataclass(frozen=True)
class Source:
    citation: str
    kind: str
    fidelity: str
    text: str
    note: str = ""


@dataclasses.dataclass(frozen=True)
class Choice:
    slug: str
    position: str
    consequence: str
    sources: tuple[Source, ...]


@dataclasses.dataclass(frozen=True)
class ContestedPosition:
    slug: str
    question: str
    status: str
    choices: tuple[Choice, ...]
    # Sources both sides rely on (where the figure comes from and its
    # conditions); they decide neither side.
    shared_sources: tuple[Source, ...]
    recorded: datetime.date


_QBI_SEHI = ContestedPosition(
    slug="qbi-sehi-shareholder-reduction",
    question=(
        "Does a more-than-2% S corporation shareholder's self-employed "
        "health insurance deduction (section 162(l)) reduce the "
        "shareholder's qualified business income from that S corporation "
        "for the section 199A deduction?"),
    status=(
        "No binding authority either way. The IRS's informal FAQ says yes; "
        "the AICPA, reading the regulation's attribution clause and the "
        "statute's wage exclusion, says no; no IRS response to the AICPA "
        "was found."),
    choices=(
        Choice(
            slug="irs-faq",
            position=(
                "Follow IRS FAQ A39: the deduction is a deduction in "
                "determining QBI."),
            consequence=(
                "The shareholder's QBI is reduced by the deduction, which "
                "can lower the section 199A deduction."),
            sources=(
                Source(
                    citation="IRS, Qualified business income deduction "
                             "FAQs, FAQ A39",
                    kind="commentary",
                    fidelity="verbatim",
                    text=(
                        "[The self-employed health insurance deduction] "
                        "will be a deduction in determining QBI. This may "
                        "result in QBI being reduced at both the entity "
                        "and the shareholder level."),
                    note=(
                        "On point for more-than-2% S corporation "
                        "shareholders. Formerly Q33; the page is now "
                        "marked historical, last reviewed 2026-05-12. Not "
                        "citable authority by its own terms. The bracketed "
                        "subject is ours."),
                ),
            ),
        ),
        Choice(
            slug="no-reduction",
            position=(
                "The deduction is attributable to the shareholder's wages, "
                "which are not QBI, so it does not reduce the "
                "shareholder's QBI."),
            consequence=(
                "The shareholder's QBI is not reduced by the deduction."),
            sources=(
                Source(
                    citation="Treas. Reg. §1.199A-3(b)(1)(vi) (T.D. 9847, "
                             "84 FR 2952)",
                    kind="authority",
                    fidelity="verbatim",
                    text=(
                        "Deductions such as the deductible portion of the "
                        "tax on self-employment income, the self-employed "
                        "health insurance deduction, and the deduction for "
                        "contributions to qualified retirement plans are "
                        "attributable to a trade or business \"to the "
                        "extent that the individual's gross income from "
                        "the trade or business is taken into account in "
                        "calculating the allowable deduction, on a "
                        "proportionate basis to the gross income received "
                        "from the trade or business.\""),
                    note=(
                        "Only the quoted clause is verbatim (final-rule "
                        "PDF, cross-checked at Cornell LII); the lead-in "
                        "summarizes the deductions the paragraph names."),
                ),
                Source(
                    citation="I.R.C. §199A(c)(4)",
                    kind="authority",
                    fidelity="paraphrased",
                    text=(
                        "QBI does not include reasonable compensation paid "
                        "to the taxpayer by the trade or business, or "
                        "guaranteed payments under section 707(c)."),
                    note="Substance confirmed; the statutory wording was "
                         "not fetched.",
                ),
                Source(
                    citation="AICPA comment letter to the IRS (March 2020)",
                    kind="commentary",
                    fidelity="secondhand",
                    text=(
                        "Argues that the self-employed health insurance "
                        "deduction attributable to S corporation wages is "
                        "not a reduction of QBI."),
                    note=(
                        "Known only through secondary summaries; no IRS "
                        "response found."),
                ),
            ),
        ),
    ),
    shared_sources=(
        Source(
            citation="I.R.C. §162(l)(1), (2)(A), (5)",
            kind="authority",
            fidelity="paraphrased",
            text=(
                "Section 162(l)(5) treats a more-than-2% shareholder's S "
                "corporation wages as earned income for the section 162(l) "
                "limit."),
            note=(
                "Governs the deduction's limit only; it says nothing "
                "about QBI."),
        ),
        Source(
            citation="I.R.C. §1372(a), (b)",
            kind="authority",
            fidelity="paraphrased",
            text=(
                "A more-than-2% shareholder is treated as a partner for "
                "fringe-benefit purposes."),
            note="Fringe benefits only.",
        ),
        Source(
            citation="Notice 2008-1, 2008-2 I.R.B.",
            kind="authority",
            fidelity="paraphrased",
            text=(
                "The shareholder's deduction requires that the S "
                "corporation pay or reimburse the premiums and include them "
                "in the shareholder's Form W-2 wages; premiums the "
                "shareholder pays personally without reimbursement give no "
                "deduction (Example 1)."),
            note="Read in full from the I.R.B. PDF.",
        ),
    ),
    recorded=datetime.date(2026, 10, 18),
)

POSITIONS: Mapping[str, ContestedPosition] = MappingProxyType({
    p.slug: p for p in (_QBI_SEHI,)
})
