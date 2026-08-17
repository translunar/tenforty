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
    threshold = params.qbi_threshold[scenario.config.filing_status.value]

    qbi_total = fanout.qbi_aggregate
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

    line_1 = irs_round(qbi_total)
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

    line_11 = irs_round(taxable_income)
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

    return {
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
