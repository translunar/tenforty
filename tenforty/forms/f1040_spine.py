"""Form 1040 native spine assembly.

Replaces the Excel-workbook evaluation path with native Python. Mirrors
the 1040 line flow year-agnostically: every year-specific value comes
from ``params`` (a ``FederalParams`` instance). No ``if year ==`` branches
and no year-specific numeric literals here.

Scoped path: single filers only. Non-single status raises NotImplementedError
at entry. Multi-status support is a guarded follow-up.

``compute_spine`` does NOT invoke the schedules itself; the orchestrator
calls each schedule's ``compute`` and passes the results as
``schedule_results: dict[str, dict]``.  Key contract for each schedule's
sub-dict (the orchestrator is responsible for providing these keys):

    schedule_results["sch_1"]  — Schedule 1 Part I / Part II line totals
        "sch_1_line_10_total_additional_income"   — Sch 1 line 10 total
        "sch_1_line_26_total_adjustments"          — Sch 1 line 26 total
        per-line breakdown keys (see OUTPUTS[2025])

    schedule_results["sch_a"]  — Schedule A itemized total
        "sch_a_line_17_total"  — line 17 total itemized deductions
        "sch_a_line_5e_salt_capped"

    schedule_results["sch_d"]  — Schedule D cap-gain/loss
        "sch_d_line_15_net_long"  — net long-term capital gain (line 15)
        "sch_d_line_16_total"     — net capital gain/loss (line 16)

    schedule_results["sch_e"]  — Schedule E Part I / Part II totals
        "sch_e_line_26_total"       — Part I rental net total (line 26)
        "sch_e_line_41_total_pte"   — Part II K-1 pass-through total (line 41)

    schedule_results["f8959"]  — Form 8959 additional Medicare
        "f8959_line_18"        — total additional Medicare tax
        "f8959_line_24"        — additional Medicare withheld

    schedule_results["f8995"]  — Form 8995 QBI deduction
        "f8995_line_15_qbi_deduction" — QBI deduction (1040 line 13)

    schedule_results["f8582"]  — Form 8582 passive activity
        "f8582_line_11_allowed_loss"

Output keys match ``F1040.OUTPUTS[2025]`` exactly so PDF mappings and
CA consumers are unaffected.
"""

from dataclasses import dataclass

from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import FilingStatus, K1FanoutData, Scenario
from tenforty.params.federal import FederalParams
from tenforty.rounding import irs_round


@dataclass(frozen=True)
class IncomePreamble:
    """Form 1040 income/AGI figures derived once from inputs + schedule results.

    Single source of truth for the line 1-15 arithmetic so the orchestrator's
    f8995/f8582 pre-pass stub and ``compute_spine`` cannot drift. The
    orchestrator computes Schedule A first — it depends only on AGI, and QBI
    is below-the-line on 1040 line 13, so there is no circularity — then
    ``resolve_deductions`` feeds f8995/f8582 the ACTUAL (itemized-aware)
    deduction via the stub's ``taxable_income_before_qbi_deduction``.
    ``compute_spine`` takes its deduction-SELECTION fields (std vs.
    itemized, ``total_deductions``) from that same ``resolve_deductions``
    call, but it deliberately RECOMPUTES taxable-income-before-QBI itself,
    UNFLOORED — the helper's ``taxable_income_before_qbi`` field is floored
    at zero (needed for f8995/f8582's income-limit gates), while the
    spine's own 1040 line-15 math requires the unfloored value. Feeding
    the spine the helper's floored field instead of its own unfloored
    local reintroduces the bug the tests in
    ``tests/test_compute_spine_unfloored_taxable_income.py`` guard against.

    Attributes:
        wages:               1040 line 1a (sum of W-2 box 1).
        taxable_interest:    1040 line 2b component from 1099-INT box 1 only.
            NOT the authoritative line 2b — see taxable_interest_total.
        taxable_interest_k1: 1040 line 2b component from the K-1s' interest
            (IRC 1366(b) conduit treatment), consumed from the fanout.
        taxable_interest_total: 1040 line 2b authoritative TOTAL
            (taxable_interest + taxable_interest_k1).
        ordinary_divs:       1040 line 3b component from 1099-DIV box 1a only.
            NOT the authoritative line 3b — see ordinary_divs_total.
        ordinary_divs_k1:    1040 line 3b component from the K-1s' ordinary
            dividends (IRC 1366(b)), consumed from the fanout.
        ordinary_divs_total: 1040 line 3b authoritative TOTAL
            (ordinary_divs + ordinary_divs_k1).
        qualified_divs:      1040 line 3a component from 1099-DIV box 1b only.
        qualified_divs_k1:   1040 line 3a component from K-1 box 5b
            (IRC 1366(b) conduit treatment), consumed from the fanout.
        qualified_divs_total: 1040 line 3a authoritative TOTAL
            (qualified_divs + qualified_divs_k1).
        schd_line16:         Schedule D line 16 net capital gain/loss (TRUE
            uncapped total — this is what Schedule D itself reports; it is
            NOT what reaches 1040 line 7/line 9, see schd_line21_allowed).
        schd_line21_allowed: Schedule D line 21 — the §1211(b)-capped amount
            (net capital loss limited to $3,000 / $1,500 MFS; equals
            schd_line16 whenever there's a gain or the loss is within the
            cap). This is what actually reaches 1040 line 7 and feeds
            total_income/line 9. Defaults to schd_line16 when sch_d omits
            the key (no Sch D block at all).
        sch_1_line_10:       Schedule 1 line 10 total additional income.
        sch_1_line_26:       Schedule 1 line 26 total adjustments.
        total_income:        1040 line 9.
        agi:                 1040 line 11.
        magi:                Modified AGI (= AGI in v1 single-filer scope).
        net_capital_gain:    QDCGT net capital gain =
            max(0, min(Sch D line 15, line 16)). The IRS QDCGT worksheet
            caps the preferential base at line 15 (net LONG-TERM gain) —
            a net SHORT-TERM gain (which inflates line 16 = line 7 + line
            15 above line 15) must stay ORDINARY income, not preferential.
            (Bug #10, found 2026-07-18: this previously used line 16 alone,
            over-including a net ST gain and undertaxing such returns.)
            Equals the workbook's NetCapitalGain named range. Qualified
            dividends are NOT included here — they are added separately,
            downstream, by consumers that each receive the authoritative
            ``qualified_divs_total`` computed by this preamble: qdcgt_tax
            (as the ``qualified_dividends`` argument) and f8995 (via the
            orchestrator's f1040 stub, i.e. ``upstream["f1040"]
            ["qualified_dividends"]`` — NOT ``fanout.qualified_dividends_
            aggregate``, which is only the K-1 component; see the guard
            comment on ``K1FanoutData.qualified_dividends_aggregate`` in
            tenforty/models.py). Keeping qualified dividends separate here
            prevents double-counting when qdcgt_tax computes
            ``preferential = qualified_dividends + net_capital_gain``.
        taxable_income_before_qbi_std:  AGI − standard deduction, floored at 0.
            No longer what feeds f8995/f8582 — the orchestrator's pre-pass
            feeds those forms the ACTUAL (itemized-aware) deduction via
            ``resolve_deductions`` instead (see the deduction-resolution
            step in ``ReturnOrchestrator._compute_native_schedules``). Retained for
            its one remaining consumer, ``tests/test_pdf_1040_mapping.py``;
            removing the field entirely is a separate, out-of-scope proposal.
    """
    wages: int
    taxable_interest: int
    ordinary_divs: int
    qualified_divs: int
    qualified_divs_k1: int
    qualified_divs_total: int
    taxable_interest_k1: int
    taxable_interest_total: int
    ordinary_divs_k1: int
    ordinary_divs_total: int
    schd_line16: int
    schd_line21_allowed: int
    sch_1_line_10: int
    sch_1_line_26: int
    total_income: int
    agi: int
    magi: int
    net_capital_gain: int
    taxable_income_before_qbi_std: int


def compute_income_preamble(
    scenario: Scenario,
    params: FederalParams,
    schedule_results: dict[str, dict],
    k1_fanout: "K1FanoutData | None" = None,
) -> IncomePreamble:
    """Compute the shared 1040 income → AGI preamble (lines 1-11 + helpers).

    Called from both the orchestrator's f8995/f8582 pre-pass (to build the
    upstream f1040 stub) and ``compute_spine`` so the AGI/total-income math has
    a single definition.  ``schedule_results`` need only contain ``sch_1`` and
    ``sch_d`` for this computation; missing keys default to 0.

    Args:
        scenario: The tax scenario (filer inputs).
        params: Year-specific federal parameters.
        schedule_results: Keyed dict of schedule return dicts (sch_1, sch_d, …).

    Returns:
        IncomePreamble with the line 1-11 figures, plus
        ``taxable_income_before_qbi_std`` (a std-deduction-based figure kept
        only for its one remaining test consumer — see that field's
        docstring above; it is not what feeds f8995/f8582).
    """
    sch_1 = schedule_results.get("sch_1", {})
    sch_d = schedule_results.get("sch_d", {})

    wages = irs_round(sum(w.wages for w in scenario.w2s))
    taxable_interest = irs_round(sum(f.interest for f in scenario.form1099_int))
    ordinary_divs = irs_round(
        sum(f.ordinary_dividends for f in scenario.form1099_div)
    )
    qualified_divs = irs_round(
        sum(f.qualified_dividends for f in scenario.form1099_div)
    )
    # 1040 line 3a is the TOTAL of qualified dividends from every source.
    # 1099-DIV box 1b is one component; a K-1's box 5b is another (IRC 1366(b)
    # conduit treatment — S-corp items keep their character in the
    # shareholder's hands). The K-1 component is CONSUMED from the fanout,
    # never re-summed here, so each component is aggregated exactly once.
    _fanout = k1_fanout if k1_fanout is not None else K1FanoutData.empty()
    qualified_divs_k1 = irs_round(_fanout.qualified_dividends_aggregate)
    qualified_divs_total = irs_round(qualified_divs + qualified_divs_k1)
    # 1040 lines 2b and 3b are likewise TOTALS across every source. A 1099-INT
    # / 1099-DIV is one component; a K-1's interest / ordinary dividends is
    # another (IRC 1366(b) conduit treatment — S-corp items keep their
    # character in the shareholder's hands). Both K-1 components are CONSUMED
    # from the fanout, never re-summed here, so each is aggregated exactly
    # once.
    #
    # Rounding: each payer's amount is rounded to whole dollars and the
    # ROUNDED figures are summed, matching how Schedule B totals the very
    # same fanout additions (see tenforty/forms/sch_b.py — each addition is
    # appended as irs_round(pa.amount), then total_interest sums those). One
    # round at the end over the raw amounts is a different function once
    # cents are involved, and would leave the 1040 and its own Schedule B a
    # dollar apart on the same return.
    taxable_interest_k1 = sum(
        irs_round(pa.amount) for pa in _fanout.sch_b_interest_additions
    )
    taxable_interest_total = irs_round(taxable_interest + taxable_interest_k1)
    ordinary_divs_k1 = sum(
        irs_round(pa.amount) for pa in _fanout.sch_b_dividend_additions
    )
    ordinary_divs_total = irs_round(ordinary_divs + ordinary_divs_k1)
    schd_line15 = sch_d.get("sch_d_line_15_net_long", 0)
    schd_line16 = sch_d.get("sch_d_line_16_total", 0)
    # IRC §1211(b): the net capital LOSS deductible against ordinary income
    # in-year is capped ($3,000 / $1,500 MFS). Schedule D line 21 is the
    # ALLOWED figure post-cap (equals line 16 when there's a gain, or when a
    # loss is within the cap); it is what actually reaches 1040 line 7 / line
    # 9 total income. Line 16 itself stays the true uncapped Schedule D total
    # (see schd_line16 usage below and in compute_spine's output keys) — only
    # this total_income transfer is capped. Defaults to schd_line16 when
    # absent (e.g. no sch_d block at all) so gain-only / no-Sch-D returns are
    # numerically unperturbed.
    schd_line21_allowed = sch_d.get("sch_d_line_21_allowed_loss", schd_line16)
    sch_1_line_10 = sch_1.get("sch_1_line_10_total_additional_income", 0)
    sch_1_line_26 = sch_1.get("sch_1_line_26_total_adjustments", 0)

    total_income = irs_round(
        wages
        + taxable_interest_total
        + ordinary_divs_total
        + schd_line21_allowed
        + sch_1_line_10
    )
    agi = irs_round(total_income - sch_1_line_26)
    # MAGI: for v1 single-filer scope, MAGI = AGI (no foreign income exclusion
    # or other MAGI-specific add-backs apply in the supported scenario set).
    magi = agi

    # Net capital gain for the QDCGT worksheet: max(0, min(line 15, line 16)).
    # Sch D line 16 = line 7 (net SHORT-term) + line 15 (net LONG-term). The
    # IRS QDCGT worksheet's preferential base is capped at line 15 — a net
    # ST gain stays ORDINARY income, it does not get the preferential rate.
    # min(line 15, line 16) enforces that cap: when there's a net ST GAIN,
    # line 16 > line 15, so min() picks line 15 (excludes the ST gain, as
    # required). When there's a net ST LOSS, line 16 < line 15 (the loss
    # drags the total below the LT figure), so min() picks line 16 — which
    # is *also* correct, because a net ST loss legitimately reduces the
    # amount taxed preferentially. Either way min() lands on the right
    # figure; a bare max(0, line 16) (the pre-fix code) got the ST-loss case
    # right by coincidence but over-included a net ST gain, undertaxing such
    # returns (Bug #10, found 2026-07-18).
    # Qualified dividends are NOT added here; they are a separate input to
    # qdcgt_tax and f8995. Adding them here would double-count them because
    # qdcgt_tax's own formula is: preferential = qualified_dividends + net_capital_gain.
    # This matches the workbook's NetCapitalGain named range.
    net_capital_gain = irs_round(max(0, min(schd_line15, schd_line16)))

    # Std-deduction-based pre-QBI taxable income. NOT what feeds f8995/f8582
    # — the orchestrator computes Schedule A first (AGI-only, no circularity
    # with the below-the-line QBI deduction) and feeds those forms the
    # ACTUAL deduction via resolve_deductions. Kept only for its one
    # remaining test consumer (tests/test_pdf_1040_mapping.py).
    std_deduction = params.standard_deduction[scenario.config.filing_status.value]
    taxable_income_before_qbi_std = max(0, irs_round(agi - std_deduction))

    return IncomePreamble(
        wages=wages,
        taxable_interest=taxable_interest,
        ordinary_divs=ordinary_divs,
        qualified_divs=qualified_divs,
        qualified_divs_k1=qualified_divs_k1,
        qualified_divs_total=qualified_divs_total,
        taxable_interest_k1=taxable_interest_k1,
        taxable_interest_total=taxable_interest_total,
        ordinary_divs_k1=ordinary_divs_k1,
        ordinary_divs_total=ordinary_divs_total,
        schd_line16=schd_line16,
        schd_line21_allowed=schd_line21_allowed,
        sch_1_line_10=sch_1_line_10,
        sch_1_line_26=sch_1_line_26,
        total_income=total_income,
        agi=agi,
        magi=magi,
        net_capital_gain=net_capital_gain,
        taxable_income_before_qbi_std=taxable_income_before_qbi_std,
    )


@dataclass(frozen=True)
class DeductionResolution:
    """Result of selecting standard vs. itemized deduction and deriving
    taxable income before the QBI deduction. Single source of truth shared
    by the orchestrator's f8995/f8582 pre-pass and ``compute_spine`` so the
    two cannot drift on which deduction was applied."""
    schedule_a_total: int
    standard_deduction_amount: int
    total_deductions: int
    standard_deduction_applied: bool
    charitable_nonitemizer: int
    taxable_income_before_qbi: int


def resolve_deductions(
    scenario: Scenario,
    params: FederalParams,
    agi: int,
    sch_a: dict,
) -> DeductionResolution:
    """Select std vs. itemized deduction and derive taxable income before QBI.

    Mirrors Form 1040 line 12: deduction = max(standard, itemized). Also
    applies the 2021 line-12b non-itemizer cash-charitable deduction
    (CARES §2204 / CAA 2021 §212) with the same refuse-don't-cap guards as
    ``compute_spine``. ``taxable_income_before_qbi`` is floored at 0.
    """
    std_deduction = params.standard_deduction[scenario.config.filing_status.value]
    schedule_a_total = sch_a.get("sch_a_line_17_total", 0)

    if schedule_a_total >= std_deduction:
        standard_deduction_amount = 0
        total_deductions = schedule_a_total
        standard_deduction_applied = False
    else:
        standard_deduction_amount = std_deduction
        total_deductions = std_deduction
        standard_deduction_applied = True

    charitable_nonitemizer = 0
    field = scenario.config.charitable_cash_nonitemizer
    if field:
        cap = params.nonitemizer_charitable_cap
        if not standard_deduction_applied:
            raise ValueError(
                "charitable_cash_nonitemizer is the 2021 line-12b deduction for "
                "NON-ITEMIZERS only; this return itemizes, so it cannot be claimed."
            )
        if cap is None or field > cap:
            raise ValueError(
                f"charitable_cash_nonitemizer ({field}) exceeds the 2021 "
                f"single-filer non-itemizer cap of ${cap}."
            )
        charitable_nonitemizer = irs_round(field)
        total_deductions += charitable_nonitemizer

    taxable_income_before_qbi = max(0, irs_round(agi - total_deductions))

    return DeductionResolution(
        schedule_a_total=schedule_a_total,
        standard_deduction_amount=standard_deduction_amount,
        total_deductions=total_deductions,
        standard_deduction_applied=standard_deduction_applied,
        charitable_nonitemizer=charitable_nonitemizer,
        taxable_income_before_qbi=taxable_income_before_qbi,
    )


def compute_spine(
    scenario: Scenario,
    params: FederalParams,
    schedule_results: dict[str, dict],
    k1_fanout: "K1FanoutData | None" = None,
) -> dict:
    """Assemble the 1040 lines from scenario inputs and schedule results.

    Args:
        scenario: The tax scenario (filer inputs).
        params: Year-specific federal parameters (from tenforty.params.federal).
        schedule_results: Keyed dict of pre-computed schedule return dicts.
            Each sub-dict may be absent; missing values default to 0.

    Returns:
        Dict of 1040 output fields using OUTPUTS[2025] production key names.

    Raises:
        NotImplementedError: For non-single filing status.
    """
    filing_status = scenario.config.filing_status
    if filing_status is not FilingStatus.SINGLE:
        raise NotImplementedError(
            f"compute_spine is scoped to single filers; "
            f"filing status {filing_status.value!r} is not supported."
        )

    # Convenience accessors for each schedule sub-dict.
    sch_a = schedule_results.get("sch_a", {})
    sch_e = schedule_results.get("sch_e", {})
    f8959 = schedule_results.get("f8959", {})
    f8995 = schedule_results.get("f8995", {})
    f8582 = schedule_results.get("f8582", {})
    # Form 8962 (PTC). Present only when the scenario carries a 1095-A; every
    # value defaults to 0 so no-block scenarios are numerically unperturbed.
    f8962 = schedule_results.get("f8962", {})
    f8962_net_ptc = f8962.get("f8962_line_26_net_ptc", 0)
    f8962_repayment = f8962.get("f8962_line_29_repayment", 0)

    # -----------------------------------------------------------------------
    # Page 1 — Income + Adjustments → AGI (shared preamble)
    # -----------------------------------------------------------------------
    # Lines 1-11 are computed by the shared preamble so the orchestrator's
    # f8995/f8582 pre-pass and this spine share one source of truth for AGI.
    preamble = compute_income_preamble(
        scenario, params, schedule_results, k1_fanout=k1_fanout,
    )
    wages = preamble.wages
    # 1040 lines 2b / 3b TOTALS — same reasoning as line 3a below: a K-1's
    # interest / ordinary dividends keep their character in the shareholder's
    # hands (IRC 1366(b)), so the LINE is the 1099 component plus the K-1
    # component. The 1099-only preamble fields (preamble.taxable_interest /
    # .ordinary_divs) are components, not lines, and are deliberately NOT
    # bound here — the emitted Schedule B totals the same K-1 additions, so a
    # spine that published the components would contradict its own Schedule B.
    taxable_interest_total = preamble.taxable_interest_total
    ordinary_divs_total = preamble.ordinary_divs_total
    # 1040 line 3a TOTAL — the QDCGT preferential base must include a K-1's
    # qualified dividends (IRC 1366(b)), not just the 1099-DIV component.
    # Reading the same preamble total that Form 8995 line 12 reads keeps the
    # two consumers structurally unable to disagree.
    qualified_divs = preamble.qualified_divs_total
    schd_line16 = preamble.schd_line16
    schd_line21_allowed = preamble.schd_line21_allowed
    sch_1_line_10 = preamble.sch_1_line_10
    sch_1_line_26 = preamble.sch_1_line_26
    total_income = preamble.total_income
    agi = preamble.agi
    magi = preamble.magi

    # Schedule 1 sub-dict still needed for the per-line breakdown pass-through.
    sch_1 = schedule_results.get("sch_1", {})

    # -----------------------------------------------------------------------
    # Page 2 — Deductions
    # -----------------------------------------------------------------------

    # Deduction selection (std vs itemized) + the 2021 line-12b non-itemizer
    # charitable add-on live in the shared resolve_deductions helper so the
    # orchestrator's f8995/f8582 pre-pass and this spine cannot drift on
    # which deduction was applied.
    _ded = resolve_deductions(scenario, params, agi, sch_a)
    schedule_a_total = _ded.schedule_a_total
    standard_deduction_amount = _ded.standard_deduction_amount
    total_deductions = _ded.total_deductions
    charitable_nonitemizer = _ded.charitable_nonitemizer

    # 1040 line 13 — QBI deduction from Form 8995 line 15.
    # Real producer key: "f8995_line_15_qbi_deduction" from forms.f8995.compute.
    qbi_deduction = f8995.get("f8995_line_15_qbi_deduction", 0)

    # 1040 line 15 — Taxable income before QBI deduction (no named range in XLS;
    # derived here as AGI − deduction).
    # DELIBERATELY UNFLOORED — do NOT substitute _ded.taxable_income_before_qbi
    # (which resolve_deductions floors at 0 for f8995/f8582's income-limit
    # gates). See tests/test_compute_spine_unfloored_taxable_income.py.
    taxable_income_before_qbi = irs_round(agi - total_deductions)

    # 1040 line 15 — Taxable income = taxable_income_before_qbi − QBI deduction.
    taxable_income = max(0, irs_round(taxable_income_before_qbi - qbi_deduction))

    # -----------------------------------------------------------------------
    # Page 2 — Tax and Credits
    # -----------------------------------------------------------------------

    # Net capital gain for QDCGT worksheet (max(0, min(Sch D line 15, line
    # 16)) — a net short-term gain stays ordinary, see compute_income_preamble)
    # comes from the shared preamble.
    net_capital_gain = preamble.net_capital_gain

    # 1040 line 16 — Tax from Qualified Dividends & Capital Gain Tax Worksheet.
    income_tax = qdcgt_tax(
        taxable_income=taxable_income,
        qualified_dividends=qualified_divs,
        net_capital_gain=net_capital_gain,
        params=params,
        filing_status=filing_status,
    )

    # -----------------------------------------------------------------------
    # Other Taxes (Schedule 2)
    # -----------------------------------------------------------------------

    # Form 8959 line 18 — Additional Medicare Tax.
    # Key: "f8959_line_18" from forms.f8959.compute.
    f8959_tax_total = f8959.get("f8959_line_18", 0)

    # 1040 line 16 — Tax (income tax from the QDCGT/rate-schedule worksheet).
    #
    # THE INVARIANT: `total_tax` means 1040 LINE 16 on every compute path, by
    # design and by test. It is not a coincidence between two producers that
    # happen to agree; it is a property something is holding.
    #
    # ITS WORKBOOK COUNTERPART IS `Tax_SubTotal`, NOT `Tax`. This comment said
    # "Matches the oracle workbook's `Tax` named range" until this unit, and
    # that was false: `Tax` is LINE 18. In all five shipped workbooks (2021-
    # 2025) the `Tax` cell is `IF(<override>, ..., SUM(Tax_SubTotal, <the
    # line-17 cell>))` and sits on the row captioned "Add lines 16 and 17";
    # `Tax_SubTotal` is the cell directly above it. So the sentence documenting
    # line 16 named line 18 — the exact conflation this unit exists to remove.
    # (Do not expect to confirm this by finding a printed "16" beside
    # `Tax_SubTotal`: only the 2025 workbook captions that row. In 2021-2024
    # the "Tax (see instructions)" caption prints one row BELOW it. Anchor on
    # the line-18 label row and the formula relationship instead.)
    # `mappings/f1040.py` maps `total_tax` -> `Tax_SubTotal` in every year, and
    # `mappings/pdf_1040.py` maps it to the line-16 amount box.
    #
    # Line 16 does NOT include Schedule 2 — neither Form 8959 (Additional
    # Medicare Tax, Part II) NOR the Form 8962 excess-APTC repayment (Part I,
    # Sch 2 line 2). Those are carried by `schedule2_tax` (line 17) and
    # `tax_plus_schedule2` (line 18) just below, and they join the
    # FULL-liability subtraction inside `overpaid` further down.
    #
    # WHAT HOLDS THE INVARIANT: tests/test_total_tax_semantics.py computes one
    # scenario BOTH ways and asserts the two paths name the same 1040 line, on
    # a fixture whose Schedule 2 Part I is nonzero so lines 16 and 18 are
    # different numbers and the two meanings are distinguishable. Consumers
    # rely on this: `forms/f1040x.py` builds 1040-X line 6 as `total_tax +
    # f8962_repayment`, which is right on a line-16 base and double-counts the
    # repayment on a line-18 one.
    total_tax = income_tax

    # 1040 line 17 — "Amount from Schedule 2, line 3", i.e. the whole of
    # Schedule 2 PART I. Part I has exactly two components: line 1 (Form 6251
    # alternative minimum tax) and line 2 (Form 8962 excess-advance-PTC
    # repayment). This assignment carries only the SECOND of them, because
    # there is no Form 6251 module in `tenforty/forms/` and the native spine
    # computes no federal AMT anywhere — AMT is zero here by ABSENCE, not by
    # computation. Do NOT read this line as a claim that Part I is complete.
    # The always-required `acknowledges_no_federal_amt` attestation
    # (`tenforty/attestations.py`, `_ALWAYS_TAIL`) is what makes that gap
    # explicit to the filer instead of silent; the two ship together on
    # purpose, so the key's name stops overclaiming the day it gains a
    # producer.
    #
    # ALWAYS A NUMBER, NEVER None. `f8962_repayment` defaults to 0 when the
    # scenario carries no 1095-A (see its assignment above), and
    # `filing/pdf.py::PdfFiller.resolve_fields` renders 0 but SKIPS None — so
    # line 17 prints a literal "0" rather than going blank. The workbook path
    # reaches the same convention from the other side, by normalizing a blank
    # `Schedule2_Tax` harvest to 0 in `forms/f1040.py::compute`. Matching it
    # here is the point: one key, one printed convention, on both paths.
    schedule2_tax = f8962_repayment

    # 1040 line 18 — "Add lines 16 and 17". Line 16 is `total_tax`; line 17 is
    # `schedule2_tax` above. Inherits line 17's AMT gap, necessarily.
    tax_plus_schedule2 = total_tax + schedule2_tax

    # -----------------------------------------------------------------------
    # Page 2 — Payments
    # -----------------------------------------------------------------------

    # 1040 line 25a — W-2 federal income tax withheld.
    fed_withheld_w2 = irs_round(sum(w.federal_tax_withheld for w in scenario.w2s))

    # 1040 line 25b — 1099 federal tax withheld (INT + DIV + G).
    fed_withheld_1099 = irs_round(
        sum(f.federal_tax_withheld for f in scenario.form1099_int)
        + sum(f.federal_tax_withheld for f in scenario.form1099_div)
        + sum(g.federal_tax_withheld for g in scenario.form1099_g)
    )

    # 1040 line 25c — Additional Medicare withheld (Form 8959 line 24).
    # Key: "f8959_line_24" from forms.f8959.compute.
    # Only include when F8959 is actually filed (line 18 > 0). The oracle
    # workbook returns F8959_WH = None when F8959 is not required; matching
    # that keeps line 25c blank and total_payments consistent with the
    # workbook path for scenarios below the Additional Medicare threshold.
    addl_medicare_withheld = (
        f8959.get("f8959_line_24", 0) if f8959_tax_total else 0
    )

    # 1040 line 25d — Total federal income tax withheld.
    federal_withheld = irs_round(
        fed_withheld_w2 + fed_withheld_1099 + addl_medicare_withheld
    )

    # 1040 line 26 — Estimated tax payments and amount applied from the prior
    # year's return. Verbatim passthrough of the filer's stated total: carried
    # exactly as supplied, never computed or clamped (a negative is refused at
    # scenario load — see scenario._validate_scenario_config).
    estimated_payments = irs_round(scenario.config.estimated_tax_payments)

    # 1040 line 33 — Total payments.
    # v1 scope: withholding + estimated payments + net Premium Tax Credit.
    # Withholding (line 25d) is fed_withheld_w2 + fed_withheld_1099 +
    # addl_medicare_withheld, summed above. Estimated tax payments (line 26)
    # is the verbatim passthrough computed just above. Net PTC (Form 8962
    # line 26) is a refundable credit; the printed 1040 routes it through
    # Schedule 3 line 9 → total other payments (line 31), which rolls into
    # total payments, so it ADDS here. f8962_net_ptc is 0 when no 1095-A is
    # present.
    # The native spine still does NOT compute the Earned Income Credit (line
    # 27a) — EIC-eligible scenarios fall back to the XLSX oracle in
    # _compute_1040_pipeline (see _scenario_in_spine_scope), so the spine never
    # reaches a filer who claims EIC.
    total_payments = federal_withheld + estimated_payments + f8962_net_ptc

    # 1040 line 35a — Amount overpaid.
    # Overpaid is computed against the FULL tax liability including Schedule 2:
    # both f8959 Additional Medicare Tax AND Form 8962 excess-APTC repayment
    # (Sch 2 line 2). f8962_repayment joins the subtraction exactly like
    # f8959_tax_total — it raises the liability that total_payments is measured
    # against, and is 0 when no 1095-A is present. The workbook's own `Overpaid`
    # named range is `IF(Tot_Payments > Tot_Tax, Tot_Payments - Tot_Tax, 0)` in
    # every year, i.e. it measures against 1040 LINE 24, the full liability.
    # The native spine mirrors that: compose the liability from parts here —
    # income_tax + f8959 + f8962 repayment — rather than reaching for
    # `total_tax`, which is line 16 only (see its assignment above).
    #
    # THAT COMPOSITION IS WHY THIS LINE WAS NEVER WRONG while `total_tax` meant
    # two different things on the two paths: it never trusted `total_tax` as a
    # liability in the first place. Form 4868's line-4 composition
    # (`forms/f4868.py::compose_line_24`) was built the same way and for the
    # same reason, so this is a pattern worth naming rather than two
    # coincidences — build a liability out of its parts; do not assume a key
    # whose name sounds like a total is one.
    #
    # NIIT (Form 8960) IS ASYMMETRIC BETWEEN THE PATHS, and this comment used
    # to claim the opposite. The native spine computes no NIIT. THE WORKBOOK
    # DOES: an `8960` sheet plus the named ranges F8960_Tax, F8960_Applicable,
    # File8960 and Form8960_Threshhold exist in all five workbooks, the sheet
    # self-arms off MAGI (`F8960_Applicable = ModAdjGrossInc >
    # Form8960_Threshhold`) with no input tenforty must supply, and
    # `'8960'!N48` flows through a Schedule 2 Part II row into
    # `TotalOtherTaxes`, 1040 line 23 and thence `Tot_Tax` (line 24). So the
    # claim that "the oracle workbook exports no Form 8960 named range" was
    # false in every year. The underlying gap — native NIIT is unmodeled — is
    # tracked as ticket (s), post-package; do NOT fix it here and do not add an
    # attestation for it, both are (s)'s scope.
    #
    # THE PARITY BATTERY STILL PASSES, for two reasons that are worth stating
    # because a green test resting on a false stated reason is one nobody can
    # re-derive when it goes red:
    #   1. `total_tax` compares line-16-only quantities on both sides (native
    #      `total_tax` vs the workbook's `Tax_SubTotal`). NIIT reaches the 1040
    #      at line 23, downstream of both line 16 and line 18, so it cannot
    #      enter the compared number at all.
    #   2. `overpaid` IS also compared, and the workbook's side of it DOES
    #      include NIIT via `Tot_Tax`. It agrees anyway because of the zero
    #      floor: the only battery scenario whose MAGI clears the NIIT
    #      threshold WITH net investment income (qdcgt_15_to_20_boundary, AGI
    #      ~$570k, ~$72k of dividends and long-term gain) computes `overpaid`
    #      as 0 natively in all five years — that filer owes — and adding NIIT
    #      only raises the workbook's liability, so its `Overpaid` is 0 too.
    # Neither reason is "both sides omit NIIT". Ticket (s) should expect the
    # second one to be the fragile one: a scenario that clears the NIIT
    # threshold AND overpays would diverge on `overpaid` today.
    overpaid = max(0, irs_round(
        total_payments - income_tax - f8959_tax_total - f8962_repayment
    ))

    # -----------------------------------------------------------------------
    # Schedule 1 per-line breakdown keys (pass-through from sch_1 results)
    # -----------------------------------------------------------------------

    sch_1_line_1_taxable_refunds = sch_1.get("sch_1_line_1_taxable_refunds", 0)
    sch_1_line_3_business_income = sch_1.get("sch_1_line_3_business_income", 0)
    sch_1_line_4_other_gains = sch_1.get("sch_1_line_4_other_gains", 0)
    sch_1_line_5_rental_re_royalty = sch_1.get("sch_1_line_5_rental_re_royalty", 0)
    sch_1_line_6_farm_income = sch_1.get("sch_1_line_6_farm_income", 0)
    sch_1_line_7_unemployment = sch_1.get("sch_1_line_7_unemployment", 0)
    sch_1_line_11_educator = sch_1.get("sch_1_line_11_educator", 0)
    sch_1_line_13_hsa = sch_1.get("sch_1_line_13_hsa", 0)
    sch_1_line_15_se_tax = sch_1.get("sch_1_line_15_se_tax", 0)
    sch_1_line_17_se_health = sch_1.get("sch_1_line_17_se_health", 0)
    # SE-HEALTH × PTC GUARD.
    # The self-employed health-insurance deduction (Schedule 1 line 17) is
    # currently hardcoded 0 at its source — see forms/sch_1.py, the
    # `self_employed_health_line_17 = 0` assignment. If it ever becomes
    # nonzero WHILE a Form 1095-A is present, the Premium Tax Credit and the
    # SE-health deduction are mutually dependent (each feeds the other's
    # MAGI / limitation) and must be reconciled by the Rev. Proc. 2014-41
    # iterative (or simplified) method, which is UNMODELED here. Fail closed
    # rather than emit a silently wrong deduction/credit.
    # Pointer (other direction): the Form 8962 wiring that this guards lives in
    # orchestrator._compute_native_schedules Step 7b, and the f8962_net_ptc /
    # f8962_repayment payment seams are above in this function.
    if sch_1_line_17_se_health and scenario.form_1095a is not None:
        raise NotImplementedError(
            "Self-employed health-insurance deduction (Schedule 1 line 17) is "
            "nonzero together with a Form 1095-A. The Premium Tax Credit and "
            "the SE-health deduction are circularly dependent (Rev. Proc. "
            "2014-41); that iterative reconciliation is not implemented."
        )
    sch_1_line_20_ira = sch_1.get("sch_1_line_20_ira", 0)
    sch_1_line_21_student_loan_interest = sch_1.get(
        "sch_1_line_21_student_loan_interest", 0
    )

    # Schedule E line 26 (Part I rental total) — oracle named range SchE1_Line26.
    # Key: "sch_e_line_26_total" from forms.sch_e.compute.
    # Renamed to "other_income" by f1040.py shim.
    sche_line26 = sch_e.get("sch_e_line_26_total", 0)

    # Schedule E line 41 (Part II K-1 pass-through total).
    # Real producer key: "sch_e_line_41_total_pte" from forms.sch_e_part_ii.compute.
    # The orchestrator merges sch_e_part_ii results into the "sch_e" slot.
    sche_line41 = sch_e.get("sch_e_line_41_total_pte", 0)

    # Schedule A line 5e (SALT capped) — pass-through from sch_a.
    sch_a_line_5e_salt_capped = sch_a.get("sch_a_line_5e_salt_capped", 0)

    # Form 8995 line 15 oracle (same value as f8995_line_15 — for cross-check).
    f8995_line_15_oracle = qbi_deduction

    # Form 8582 line 11 oracle — allowed passive loss.
    # Key: "f8582_line_11_allowed_loss" from forms.f8582.compute.
    f8582_line_11_oracle = f8582.get("f8582_line_11_allowed_loss", 0)

    # Form 8959 required gate: True if any f8959 tax was computed.
    f8959_required = bool(f8959_tax_total)

    # -----------------------------------------------------------------------
    # Assemble output dict — OUTPUTS[2025] production keys exactly.
    # -----------------------------------------------------------------------

    return {
        # Page 1 income lines — oracle/OUTPUTS[2025] key names
        "wages": wages,
        # Line 1z — Total of lines 1a-1h. Equals `wages` because W-2 box-1
        # (line 1a) is the only modeled line-1 component; lines 1b-1h have no
        # scenario inputs and refuse-by-absence (their mapping entries are
        # retired). Feeds line 9.
        "total_w2_income": wages,
        # 1040 lines 2b / 3b are TOTALS across every source, so these publish
        # the authoritative 1099+K-1 figures, not the 1099-only components.
        # Anything reading these keys (PDF line 2b/3b boxes, Sch CA Part I §A
        # lines 2/3, the CLI summary) is asking for the line, not the 1099
        # slice, and the emitted Schedule B totals the same fanout additions --
        # so publishing the 1099-only figure here left the 1040 and its own
        # Schedule B disagreeing on the same return, with tax understated.
        "interest_income": taxable_interest_total,
        "dividend_income": ordinary_divs_total,
        "total_income": total_income,
        # PDF-ready aliases: PDF mapping uses taxable_interest / ordinary_dividends
        # (f1040.compute renamed these in the oracle path).
        "taxable_interest": taxable_interest_total,
        "ordinary_dividends": ordinary_divs_total,
        # 1040 line 3a TOTAL (1099-DIV + K-1). Publishing this from the spine
        # (rather than leaving it only in the orchestrator's compute-time
        # stub) lets the PDF-emit path -- which builds its upstream from this
        # finished results dict -- read the same authoritative total that
        # forms.f8995.compute reads on the compute path. Without this, the
        # emit path's upstream["f1040"] lacked the key entirely, and f8995's
        # `.get(..., 0)` default silently zeroed line 12 on every emitted
        # packet. This also populates pdf_1040's existing "qualified_dividends"
        # -> line 3a mapping, which had nothing to read before.
        "qualified_dividends": qualified_divs,
        # AGI
        "agi": agi,
        "agi_page2": agi,
        "magi": magi,
        # Deductions
        "standard_deduction": standard_deduction_amount,
        "schedule_a_total": schedule_a_total,
        "sch_a_line_5e_salt_capped": sch_a_line_5e_salt_capped,
        "total_deductions": total_deductions,
        "charitable_nonitemizer": charitable_nonitemizer,  # 2021 line 12b
        # Form 1040 line 12 — the deduction actually applied (std or itemized).
        # `standard_deduction` above is 0 when itemizing, so the line-12 PDF
        # cell reads this instead (see pdf_1040 f2_02). Equals total_deductions.
        "applied_deduction": max(standard_deduction_amount, schedule_a_total),
        # Taxable income
        "taxable_income_before_qbi_deduction": taxable_income_before_qbi,
        "_qbi_deduction_1040": qbi_deduction,
        # line 13 QBI box (pdf_1040 keys on the plain name); _qbi_deduction_1040
        # stays for the oracle-translation shim.
        "qbi_deduction": qbi_deduction,
        # 1040 line 14 = line 12(c) deduction + line 13 QBI. `total_deductions`
        # is line 12(c) ONLY (excludes QBI), so line 14 needs its own key.
        "deductions_plus_qbi": total_deductions + qbi_deduction,
        "taxable_income": taxable_income,
        # Tax
        "total_tax": total_tax,
        # 1040 line 17 (Schedule 2 Part I) and line 18 (lines 16 + 17). Both
        # are derived a few dozen lines above `total_tax`'s own assignment;
        # read the comments there for the AMT gap and the print-"0"-not-blank
        # convention. Before these two keys existed, lines 17 and 18 were
        # mapped to PDF boxes in all five year blocks of `mappings/pdf_1040.py`
        # and produced by nothing on the native path, so both printed BLANK on
        # every 1040 the spine emitted — including returns that attach a
        # Schedule 2 for an excess-APTC repayment.
        "schedule2_tax": schedule2_tax,
        "tax_plus_schedule2": tax_plus_schedule2,
        # Capital gain — oracle key + PDF alias.
        # schd_line16 is the TRUE, uncapped Schedule D line 16 total — the
        # form itself always reports the real net gain/loss, uncapped.
        # capital_gain_loss maps to 1040 line 7a instead, which is the
        # TRANSFER from Schedule D line 21 — the §1211(b)-capped figure (a
        # net loss is limited to $3,000 / $1,500 MFS; a gain, or a loss
        # within the cap, passes through unchanged). These two keys
        # deliberately diverge whenever the loss exceeds the cap; see
        # schd_line21_allowed's docstring on IncomePreamble.
        # Omit (None) when zero so the PDF field stays blank for W-2-only
        # scenarios — matching the oracle's behavior where a blank Sch D
        # cell propagates as None (not 0) and PdfFiller skips None values.
        "net_capital_gain": net_capital_gain,
        "schd_line16": schd_line16,
        "capital_gain_loss": schd_line21_allowed if schd_line21_allowed else None,
        # Payments — split by source so PDF mapping can route each line
        "federal_withheld_w2": fed_withheld_w2,    # line 25a
        "federal_withheld_1099": fed_withheld_1099, # line 25b
        "federal_withheld_other": addl_medicare_withheld,  # line 25c
        "federal_withheld": federal_withheld,       # line 25d total
        "estimated_tax_payments": estimated_payments,  # line 26
        "additional_medicare_withheld": addl_medicare_withheld,
        "total_payments": total_payments,
        "overpaid": overpaid,
        # Schedule 1 line 10 and 26 totals — both short and long-form keys
        "sch_1_line_10": sch_1_line_10,
        "sch_1_line_10_total_additional_income": sch_1_line_10,  # long-form alias
        "sch_1_line_26": sch_1_line_26,
        "sch_1_line_26_total_adjustments": sch_1_line_26,        # long-form alias
        # Schedule E line 26 (Part I rental total) — oracle key + f1040.py rename
        "sche_line26": sche_line26,
        "other_income": sche_line26,  # f1040.compute rename used by Sch CA consumers
        # Schedule 1 Part I per-line breakdown
        "sch_1_line_1_taxable_refunds": sch_1_line_1_taxable_refunds,
        "sch_1_line_3_business_income": sch_1_line_3_business_income,
        "sch_1_line_4_other_gains": sch_1_line_4_other_gains,
        "sch_1_line_5_rental_re_royalty": sch_1_line_5_rental_re_royalty,
        "sch_1_line_6_farm_income": sch_1_line_6_farm_income,
        "sch_1_line_7_unemployment": sch_1_line_7_unemployment,
        # Schedule 1 Part II per-line breakdown
        "sch_1_line_11_educator": sch_1_line_11_educator,
        "sch_1_line_13_hsa": sch_1_line_13_hsa,
        "sch_1_line_15_se_tax": sch_1_line_15_se_tax,
        "sch_1_line_17_se_health": sch_1_line_17_se_health,
        "sch_1_line_20_ira": sch_1_line_20_ira,
        "sch_1_line_21_student_loan_interest": sch_1_line_21_student_loan_interest,
        # Schedule E line 41
        "sche_line41": sche_line41,
        # Form 8959
        "f8959_tax_total": f8959_tax_total,
        "f8959_required": f8959_required,
        # Form 8962 (PTC) — summary keys ALWAYS emitted (0 when no 1095-A),
        # mirroring how f8959_tax_total/f8959_required are always present.
        "f8962_net_ptc": f8962_net_ptc,
        "f8962_repayment": f8962_repayment,
        # Full f8962 detail key family (f8962_line_*, f8962_month_*), passed
        # through for the emit/mapping layer. Present ONLY when a 1095-A was
        # computed; the splat adds nothing when f8962 == {} so the detail keys
        # stay absent from no-block payloads.
        **f8962,
        # Form 8995 oracle
        "f8995_line_15_oracle": f8995_line_15_oracle,
        # Form 8582 oracle
        "f8582_line_11_oracle": f8582_line_11_oracle,
    }
