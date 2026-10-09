"""Schedule 2 (Form 1040) -- Additional Taxes.

Thin compute: every component is already computed by the 1040 pipeline, so
this module only places them on Schedule 2's lines and totals the two parts.
Keys are named by the form line they print on.

PART I WAS RENUMBERED. In 2021-2023 line 1 is the alternative minimum tax and
line 2 the excess advance premium tax credit repayment. From 2024 the
repayment is line 1a, line 1z totals the "additions to tax" block, and the
alternative minimum tax is line 2. PART_I_LAYOUT records which layout a year
uses; Part II's lines 4, 11 and 21 did not move.

UNMODELED, left blank: the alternative minimum tax (no Form 6251 anywhere in
tenforty) and every Part II line other than 4 and 11. Line 3 and line 21 are
therefore totals of the MODELED components only.

A component line is emitted only when nonzero, so an inapplicable line prints
blank; the two part totals are always emitted.
"""
from tenforty.models import Scenario
from tenforty.rounding import irs_round

PART_I_LAYOUT: dict[int, str] = {
    2021: "amt_first",
    2022: "amt_first",
    2023: "amt_first",
    2024: "additions_first",
    2025: "additions_first",
}


def compute(scenario: Scenario, upstream: dict) -> dict:
    year = scenario.config.year
    if year not in PART_I_LAYOUT:
        raise ValueError(
            f"No Schedule 2 layout for tax year {year}; supported years are "
            f"{', '.join(str(y) for y in sorted(PART_I_LAYOUT))}."
        )
    f1040 = upstream.get("f1040", {})
    repayment = irs_round(f1040.get("f8962_repayment") or 0)
    se_tax = irs_round(f1040.get("sch_se_line_12_se_tax") or 0)
    addl_medicare = irs_round(f1040.get("f8959_tax_total") or 0)

    out: dict = {**scenario.config.pdf_header()}
    if repayment:
        if PART_I_LAYOUT[year] == "amt_first":
            out["sch_2_line_2_excess_aptc_repayment"] = repayment
        else:
            out["sch_2_line_1a_excess_aptc_repayment"] = repayment
            out["sch_2_line_1z_total_additions"] = repayment
    out["sch_2_line_3_part_i_total"] = repayment
    if se_tax:
        out["sch_2_line_4_se_tax"] = se_tax
    if addl_medicare:
        out["sch_2_line_11_additional_medicare_tax"] = addl_medicare
    out["sch_2_line_21_total_other_taxes"] = se_tax + addl_medicare
    return out
