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
import contextlib
import contextvars
import dataclasses
import datetime
from collections.abc import Callable, Mapping
from types import MappingProxyType

from tenforty.models import EntityType

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
    # Whether a return's numbers flow through this position. Input
    # contract: the EFFECTIVE scenario (orchestrator._build_effective_
    # scenario), whose K-1s include those the S corporation pipeline
    # synthesizes at compute time. An election for a position the return
    # never reaches is refused: it would do nothing.
    reached_when: Callable[[object], bool]
    # The load-time view: False only when the loaded scenario DEFINITELY
    # never reaches the position (reached_when on its effective scenario
    # must imply this). Elections are re-checked exactly at compute.
    may_reach: Callable[[object], bool]
    # True once a computation consults this position (election()). Until
    # then the computation refuses the return whatever is elected, so an
    # election is itself refused: it would do nothing.
    wired: bool = False


def _sehi(scenario) -> bool:
    return bool(scenario.config.self_employed_health_insurance_deduction)


def _s_corp_shape(scenario) -> bool:
    # The shape that can carry S-corporation-sourced SEHI (phase-2 ruling;
    # the source is unmodeled, so it is read by shape): no Schedule C
    # business and no K-1 with QBI other than an S corporation's. With a
    # Schedule C business, which business established the plan is
    # unmodeled; a partnership K-1 with QBI is not this question. Form 8995
    # refuses both.
    return not scenario.schedule_c_businesses and not any(
        k1.qbi_amount for k1 in scenario.schedule_k1s
        if k1.entity_type != EntityType.S_CORP)


def _sehi_and_s_corp_k1_qbi(scenario) -> bool:
    # Ruled shape gate: a nonzero self-employed health insurance deduction,
    # at least one S corporation K-1 carrying QBI, and the S corporation
    # shape above (under which any K-1 carrying QBI is an S corporation's).
    return _sehi(scenario) and _s_corp_shape(scenario) and any(
        k1.qbi_amount for k1 in scenario.schedule_k1s)


def _sehi_and_possible_s_corp_k1_qbi(scenario) -> bool:
    # At load an S corporation return's K-1 does not exist yet; its QBI is
    # known only after the corporate pipeline runs. That pipeline only
    # appends S corporation K-1s, so the shape test is already exact here.
    return _sehi(scenario) and _s_corp_shape(scenario) and (
        _sehi_and_s_corp_k1_qbi(scenario)
        or scenario.s_corp_return is not None)


_QBI_SEHI = ContestedPosition(
    slug="qbi-sehi-shareholder-reduction",
    question=(
        "Does a more-than-2% S corporation shareholder's self-employed "
        "health insurance deduction (section 162(l)) reduce the "
        "shareholder's qualified business income from that S corporation "
        "for the section 199A deduction?"),
    status=(
        "No binding authority either way. The IRS's informal FAQ says yes; "
        "the AICPA (known secondhand) argues no; the regulation's "
        "attribution clause and the statute's wage exclusion support that "
        "reading. No IRS response to the AICPA was found."),
    choices=(
        Choice(
            slug="irs-faq",
            position=(
                "Follow IRS FAQ A39: the deduction is a deduction in "
                "determining QBI."),
            consequence=(
                "The shareholder's QBI is reduced by the deduction, which "
                "can lower the section 199A deduction. With more than one S "
                "corporation K-1, how the reduction is allocated among them "
                "is unruled law; tenforty refuses that return under this "
                "election."),
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
                        "[The self-employed health insurance deduction is "
                        "attributable to a trade or business] to the "
                        "extent that the individual's gross income from "
                        "the trade or business is taken into account in "
                        "calculating the allowable deduction, on a "
                        "proportionate basis to the gross income received "
                        "from the trade or business."),
                    note=(
                        "Verbatim from the final-rule PDF, cross-checked at "
                        "Cornell LII. The bracketed subject is ours: the "
                        "paragraph names the deductible part of "
                        "self-employment tax, the self-employed health "
                        "insurance deduction and qualified retirement plan "
                        "contributions."),
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
    reached_when=_sehi_and_s_corp_k1_qbi,
    may_reach=_sehi_and_possible_s_corp_k1_qbi,
    # Consulted by Form 8995 (forms/f8995._k1_sehi_reduction).
    wired=True,
)

# Consumers must read positions.POSITIONS via the module: a from-import
# freezes the mapping as imported, so a patched registry (tests) is unseen.
POSITIONS: Mapping[str, ContestedPosition] = MappingProxyType({
    p.slug: p for p in (_QBI_SEHI,)
})


# The results-dict key carrying a run's consults (ruling 5): a list of
# {"slug", "choice", "reached"} entries, one per position the run reached
# and consulted, in consult order. A run that reaches no position carries
# no key at all: silence means never reached. Today an entry exists only
# for a reached position, so "reached" is always True; a later phase may
# add reached: False entries for elections declared but not reached.
RESULTS_KEY = "positions_consulted"

# The record of the run in progress; None outside a run (the emit path's
# recompute of a form consults, but records nowhere).
_RUN_RECORD: contextvars.ContextVar[list[dict] | None] = (
    contextvars.ContextVar("positions_run_record", default=None))


@contextlib.contextmanager
def recording():
    """Collect the consults of one run into a fresh list (yielded).

    One record per pipeline run: runs must not nest. An inner run would
    take every consult made while it is open, and the outer run's record
    would silently miss them. The amended-return path is two SEQUENTIAL
    runs (amended, then original), each with its own record. A change that
    nests runs must decide where consults belong; it must not inherit this
    silently."""
    record: list[dict] = []
    token = _RUN_RECORD.set(record)
    try:
        yield record
    finally:
        _RUN_RECORD.reset(token)


def validate_elections(scenario, *, exact: bool = False) -> None:
    """Refuse (ValueError) a malformed ``positions`` block, an unknown
    position, an unknown choice, or an election for a position this return
    never reaches. At load (``exact=False``) "never reaches" is decided by
    ``may_reach``; at compute, on the effective scenario (``exact=True``),
    by ``reached_when``. Without an S corporation return the two views
    coincide (the loaded scenario is the effective one), so the compute
    re-check runs on the S corporation build path only."""
    elections = scenario.positions
    if not isinstance(elections, Mapping) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in elections.items()):
        raise ValueError(
            "`positions` must map a position slug to the chosen side, e.g. "
            "positions: {qbi-sehi-shareholder-reduction: no-reduction}; got "
            f"{elections!r}.")
    for slug, choice in elections.items():
        pos = POSITIONS.get(slug)
        if pos is None:
            raise ValueError(
                f"`positions` names {slug!r}, which is not a registered "
                f"contested position. Registered: {sorted(POSITIONS)}.")
        valid = [c.slug for c in pos.choices]
        if choice not in valid:
            raise ValueError(
                f"`positions: {slug}` is {choice!r}, which is not one of its "
                f"choices: {valid}.")
        if not pos.wired:
            raise ValueError(
                f"`positions` elects {slug!r}, which is registered but not "
                "yet consulted by the computation. Until a computation "
                "consults it, the computation refuses this return "
                "whatever is elected, so the election would do nothing. "
                "Remove it.")
        reaches = pos.reached_when if exact else pos.may_reach
        if not reaches(scenario):
            raise ValueError(
                f"`positions` elects {slug!r}, but this return never reaches "
                "that position, so the election would do nothing. Remove it.")


def refusal_message(slug: str) -> str:
    """The standard refusal for a return that reaches ``slug`` without an
    election: the controversy and both options."""
    pos = POSITIONS[slug]
    options = "\n".join(
        f"  - {c.slug}: {c.position} {c.consequence}" for c in pos.choices)
    return (
        f"This return reaches a contested position of law ({slug}): "
        f"{pos.question} {pos.status}\n"
        f"tenforty will not choose for you. Elect one side in the scenario:\n"
        f"{options}\n"
        f"e.g. positions: {{{slug}: {pos.choices[0].slug}}}")


def election(scenario, slug: str) -> str:
    """The return's election for ``slug``, recorded in the run in progress;
    refuses (NotImplementedError, the standard message) when none is given.
    An unregistered slug, or a consult on a return that never reaches the
    position, is a programming error (LookupError, RuntimeError)."""
    if slug not in POSITIONS:
        raise LookupError(f"{slug!r} is not a registered contested position.")
    if not POSITIONS[slug].reached_when(scenario):
        raise RuntimeError(
            f"{slug!r} consulted on a return that never reaches it: the "
            "consulting path must gate on the position's reached_when.")
    choice = scenario.positions.get(slug)
    if choice is None:
        raise NotImplementedError(refusal_message(slug))
    # Construction validated it; this catches a positions dict mutated
    # afterwards (filer input gone bad, so ValueError).
    valid = [c.slug for c in POSITIONS[slug].choices]
    if choice not in valid:
        raise ValueError(
            f"`positions: {slug}` is {choice!r}, which is not one of its "
            f"choices: {valid}.")
    record = _RUN_RECORD.get()
    entry = {"slug": slug, "choice": choice, "reached": True}
    if record is not None and entry not in record:
        record.append(entry)
    return choice
