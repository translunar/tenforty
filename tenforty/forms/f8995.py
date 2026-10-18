"""Form 8995 — Qualified Business Income Deduction (simplified).

Scope: v1 simple path only. Over-threshold scenarios with nonzero QBI
require Form 8995-A (not implemented) and raise NotImplementedError at
compute time — the gate message carries the full explanation.

net_capital_gain simplification: v1 uses `qualified_dividends + max(0,
net_LTCG)` in place of `qualified_dividends + net_LTCG − net_STCL`.
K-1-only scenarios rarely realize a meaningful STCL worth netting; a
scenario with a meaningful STCL will slightly under-state the deduction.
"""

from tenforty.params.federal import load as load_federal_params
from tenforty.models import K1FanoutData, Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    params = load_federal_params(scenario.config.year)
    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()
    f1040 = upstream.get("f1040", {})

    taxable_income = float(f1040.get("taxable_income_before_qbi_deduction", 0))
    net_cap_gain = float(f1040.get("net_capital_gain", 0))
    threshold = params.for_status(scenario.config.filing_status).qbi_threshold

    # Schedule C QBI component (aggregated, computed once — plan D5). Each
    # sole-proprietor business contributes QBI = net profit less the allocable
    # §164(f) half-SE-tax deduction and the §162(l) SE-health deduction (both
    # reduce QBI); because Form 8995 aggregates every component before the 20%
    # limit, the aggregate Schedule C QBI equals Σ(net profit) − (total
    # half-SE-tax) − (SE-health), which is what we add here alongside the K-1
    # fanout's qbi_aggregate.
    #
    # NO floor: a Schedule C net loss is a NEGATIVE QBI component. It nets
    # against the other components on line 1/2, the 20% component is taken on
    # the floored line 4, and whatever is left negative carries forward on
    # line 16 (see below). Flooring the component here would print a zero on
    # line 1 and silently drop the carryforward. In a profit year the
    # component cannot go negative from the subtractions: half-SE-tax is a
    # fraction of the profit, and the §162(l) guard in forms/sch_1.py refuses
    # an SE-health deduction above (net profit − half-SE-tax).
    #
    # D5 + D4 — SE-health attribution is safe: subtracting the WHOLE
    # scenario-level self_employed_health_insurance_deduction from this single
    # aggregated Schedule C component is correct precisely because Task 7's
    # §162(l) guard refuses whenever SE-health is nonzero AND there are two or
    # more businesses. So a nonzero se_health here always attributes to exactly
    # one business — there is no multi-business allocation to get wrong.
    sch_c = upstream.get("sch_c", {})
    sch_se = upstream.get("sch_se", {})
    sch_c_net = float(sch_c.get("sch_c_line_31_net_profit_total", 0.0))
    half_se = float(sch_se.get("sch_se_line_13_half_deduction", 0.0))
    se_health = float(scenario.config.self_employed_health_insurance_deduction)
    sch_c_qbi = sch_c_net - half_se - se_health
    qbi_total = fanout.qbi_aggregate + sch_c_qbi
    # 1040 line 3a TOTAL (1099-DIV + K-1). Previously this read
    # fanout.qualified_dividends_aggregate, which carries ONLY the K-1
    # component — so line 12 omitted every 1099-DIV qualified dividend and
    # the line-14 income limit came out too high.
    #
    # STRICT read (no silent default): upstream["f1040"] must carry
    # "qualified_dividends", the authoritative 1040 line 3a total. The two
    # legitimate producers are the orchestrator's compute-time stub
    # (orchestrator.py, f1040_stub) and forms.f1040_spine.compute_spine's
    # output dict (the emit path's upstream). A silent `.get(..., 0)`
    # default is exactly what let the emit path — whose upstream is built
    # from the finished 1040 results dict — quietly compute Form 8995 line
    # 12 as 0 while the compute path got the real number. With a silent
    # default, ANY upstream that lacks this key quietly reproduces that
    # bug; with a strict read, such a gap becomes a loud error instead of a
    # wrong number.
    if "qualified_dividends" not in f1040:
        raise KeyError(
            "upstream[\"f1040\"] is missing \"qualified_dividends\" (the "
            "authoritative 1040 line 3a total: 1099-DIV + K-1 qualified "
            "dividends). Form 8995 line 12 requires this figure. Legitimate "
            "producers are the orchestrator's compute-time f1040 stub and "
            "forms.f1040_spine.compute_spine's output dict (the emit "
            "path's upstream). Do not default this to 0 — a silent default "
            "is what previously let the PDF-emit path compute line 12 as 0 "
            "while the compute path computed the correct nonzero total."
        )
    qualified_divs = float(f1040["qualified_dividends"])

    if (qbi_total > 0
            and taxable_income > threshold
            and not scenario.config.acknowledges_qbi_below_threshold):
        raise NotImplementedError(
            f"Taxable income before QBI ({taxable_income:.0f}) exceeds the "
            f"Form 8995 simple-path threshold ({threshold}) for filing "
            f"status {scenario.config.filing_status.value}, and the "
            f"scenario has {qbi_total:.0f} of QBI. Form 8995-A "
            "is not implemented in tenforty v1. Set "
            "`acknowledges_qbi_below_threshold: true` ONLY if you have "
            "confirmed that the simple-path formula is correct for your "
            "return; otherwise this return cannot be produced by v1."
        )

    rows = _source_rows(scenario, sch_c, fanout, sch_c_qbi)
    # Line 2 combines lines 1i-1v AS PRINTED: the sum of each row's
    # whole-dollar QBI (ruled: the vendor workbook's own line-2 formula
    # rounds each row, then sums). line_1 is that total, the line-2 feed.
    line_1 = sum(qbi for _, _, qbi in rows)
    # IRS Form 8995 line 2: "Total qualified business income or (loss).
    # Combine lines 1i through 1v." This is a PRINTED line (PDF-mapped in
    # tenforty/mappings/pdf_f8995.py, field f1_18) -- it must show the true,
    # UNFLOORED combine of line 1, even in a loss year, or the filed form
    # contradicts itself (line 1 shows a loss but line 2 claims the combine
    # is zero). combined_qbi is the same unfloored total; it is NOT line_2
    # itself, it is the value line_2 *would feed forward as* on the real
    # form's line 4 ("Total qualified business income. Combine lines 2 and
    # 3. If zero or less, enter -0-.") -- line 3 there is the prior-year QBI
    # loss carryforward IN, an input channel v1 does not model yet (see
    # program ledger; deliberately out of scope for this fix), so the
    # combine tenforty models is just line_1 alone. Floor THAT at 0 before it
    # feeds the 20% component below: an unfloored negative combine would
    # otherwise flow straight through line_3 -> line_6 -> line_15 and
    # produce a QBI deduction that is negative -- i.e. one that *increases*
    # taxable income, which is the defect this fix corrects. The floor must
    # apply downstream of the printed line_2, not to it.
    combined_qbi = line_1
    line_2 = combined_qbi
    floored_qbi = max(0, combined_qbi)
    line_3 = irs_round(0.20 * floored_qbi)
    line_4 = 0
    line_5 = 0
    line_6 = line_3 + line_5

    # FORM lines 3, 4, 7, 8 (the combine lines). The compute keys above are one
    # tier off their printed lines (ticket (cc)), so these NEW values are keyed
    # by their TRUE form line numbers (see the seam table in
    # mappings/pdf_f8995.py).
    #   form 3: prior-year QBI (loss) carryforward IN. NO input channel exists
    #           for it yet (see the line-16 note above), so v1 prints 0.
    #   form 4: combine(form 2, form 3), "If zero or less, enter -0-".
    #   form 7: prior-year REIT/PTP (loss) carryforward IN — likewise 0.
    #   form 8: combine(form 6, form 7), floored at 0 — form 6 is `line_4` above.
    form_line_3 = 0
    form_line_4 = max(0, line_2 + form_line_3)
    form_line_7 = 0
    form_line_8 = max(0, line_4 + form_line_7)

    # IRS Form 8995 line 16: "Total qualified business (loss) carryforward.
    # Combine lines 2 and 3. If greater than zero, enter -0-." This is the
    # mirror image of the floored_qbi floor above: whatever the floor
    # applied to combined_qbi removes becomes the loss carried to next year.
    # SIGN CONVENTION:
    # stored NEGATIVE (or 0), matching how the IRS form itself reports this
    # carryforward -- a loss year yields a negative number here, e.g. -30,000
    # QBI carries forward as -30,000, not +30,000. Write-only in v1: computed
    # and surfaced in the returned dict, consumed by nothing downstream yet
    # (the matching prior-year-loss INPUT channel is the deferred follow-up
    # noted above). Mirrors the existing write-only-carryforward pattern in
    # forms/f8582.py's `per_activity_carryforwards`.
    line_16_qbi_loss_carryforward = min(0, combined_qbi)

    # i8995 (2024), Line 11: "...line 11, minus... line 12", no floor;
    # adjudicated 2026-10-04. The zero floor belongs to line 13's "If zero or
    # less, enter -0-" (applied below). Producers that only supply the
    # floored figure (workbook path, direct callers) fall back to it.
    line_11 = irs_round(float(f1040.get(
        "taxable_income_before_qbi_deduction_unfloored", taxable_income)))
    # max(0, ...) is a boundary contract on `upstream`, not a redundant guard:
    # `upstream` is a public dict any caller can populate, and today's
    # producers (both the compute path's `_preamble.net_capital_gain` and the
    # emit path) already floor net_capital_gain at 0 before it reaches here,
    # so this branch is unreachable *through today's producers* alone. It also
    # matches the form: a net capital LOSS contributes nothing to line 12, it
    # never subtracts qualified dividends. Pinned by
    # F8995NetCapitalGainFloorBoundaryTests.test_negative_net_capital_gain_floored_at_upstream_boundary
    # in tests/test_f8995_compute.py, which populates upstream directly.
    line_12 = irs_round(max(0, net_cap_gain) + qualified_divs)
    line_13 = max(0, line_11 - line_12)
    line_14 = irs_round(0.20 * line_13)

    line_15 = min(line_6, line_14)

    out = {
        **scenario.config.pdf_header(),
        "f8995_line_1_qbi": line_1,
        "f8995_line_2_total_qbi": line_2,
        "f8995_line_3_component": line_3,
        "f8995_line_4_reit_ptp": line_4,
        "f8995_line_5_reit_ptp_component": line_5,
        "f8995_line_6_total_before_limit": line_6,
        "f8995_line_11_taxable_income": line_11,
        "f8995_line_12_net_capital_gain": line_12,
        "f8995_line_13_subtract": line_13,
        "f8995_line_14_income_limit": line_14,
        "f8995_line_15_qbi_deduction": line_15,
        "f8995_line_16_qbi_loss_carryforward": line_16_qbi_loss_carryforward,
    }
    # Keys named by TRUE FORM line (not the tier-off names above).
    out["f8995_line_3_prior_qbi_loss_carryforward"] = form_line_3
    out["f8995_line_4_total_qbi"] = form_line_4
    out["f8995_line_7_prior_reit_ptp_loss_carryforward"] = form_line_7
    out["f8995_line_8_total_reit_ptp"] = form_line_8
    for row, (name, tin, qbi) in zip(ROWS, rows):
        out[f"f8995_line_1{row}_name"] = name
        out[f"f8995_line_1{row}_tin"] = tin
        out[f"f8995_line_1{row}_qbi"] = qbi
    return out


# Form 8995 line 1 prints five business rows, i-v.
ROWS = ("i", "ii", "iii", "iv", "v")


def _source_rows(scenario: Scenario, sch_c: dict, fanout: K1FanoutData,
                 sch_c_qbi: float) -> list[tuple[str, str, int]]:
    """Form 8995 line 1, one row per QBI source (Juno's ruling): (a) name,
    (b) TIN, (c) that source's OWN qualified business income, whole dollars.

    Filing order: the Schedule C business (with nonzero net profit) first,
    then each K-1 with nonzero QBI.
      Schedule C: business description + the TAXPAYER'S SSN (Schedule C
        instructions: never an LLC EIN); its QBI is the Schedule C QBI
        component (net profit - half-SE-tax - SE-health), which is that one
        business's QBI when it is the only one.
      K-1: entity_name + entity_ein; its QBI is its own qbi_amount.
    Two or more Schedule C businesses need the half-SE-tax allocated across
    them, and more than five sources need an attached statement: both are
    refused until built."""
    per_business = sch_c.get("sch_c_businesses", [])
    businesses = [biz for biz, result in zip(scenario.schedule_c_businesses,
                                             per_business)
                  if result.get("sch_c_line_31_net_profit")]
    if len(businesses) > 1:
        raise NotImplementedError(
            f"Form 8995 per-source rows: {len(businesses)} Schedule C "
            "businesses each need their own line-1 row, which needs the "
            "deductible half of self-employment tax allocated across them. "
            "That allocation is pending a ruling (lane f8995 multi-source "
            "row 1, phase C); until it lands, a return with more than one "
            "Schedule C business with nonzero net profit cannot be produced.")
    sources: list[tuple[str, str, float]] = []
    if businesses:
        sources.append((str(businesses[0].description),
                        str(scenario.config.ssn), sch_c_qbi))
    elif sch_c_qbi:
        raise ValueError(
            f"Form 8995: a Schedule C QBI component of {sch_c_qbi} with no "
            "Schedule C business of nonzero net profit to print it on: "
            "upstream['sch_c'] disagrees with the scenario's businesses.")
    k1_rows = [(str(k1.entity_name), str(k1.entity_ein), k1.qbi_amount)
               for k1 in scenario.schedule_k1s if k1.qbi_amount]
    if abs(sum(q for _, _, q in k1_rows) - fanout.qbi_aggregate) > 0.005:
        raise ValueError(
            "Form 8995: the K-1 fanout's qbi_aggregate "
            f"({fanout.qbi_aggregate}) is not the sum of the scenario's K-1 "
            "qbi_amount values, so line 2 would contradict the printed rows.")
    sources += k1_rows
    if len(sources) > len(ROWS):
        raise NotImplementedError(
            f"Form 8995 per-source rows: {len(sources)} QBI sources exceed "
            "line 1's five rows. The sources beyond five belong on an "
            "attached statement, which is not built yet (lane f8995 "
            "multi-source row 1, phase S).")
    return [(name, tin, irs_round(qbi)) for name, tin, qbi in sources]
