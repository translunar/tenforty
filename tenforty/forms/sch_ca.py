"""Schedule CA (540) generic compute kernel.

Routes a list of CASchCAAdjustment entries to their respective Sch CA
lines, sums into Col B (subtractions) and Col C (additions) per line,
and computes CA AGI = federal AGI - Σ subtractions + Σ additions.

Produces compute output keys:
- sch_ca_line_<normalized_line>_col_a: per-line Col A federal passthrough
  (only emitted for lines listed in `_FEDERAL_TO_SCH_CA_COL_A_MAP`)
- sch_ca_line_<normalized_line>_subtractions: per-line Col B sum
- sch_ca_line_<normalized_line>_additions: per-line Col C sum
- sch_ca_total_subtractions: Σ all Col B
- sch_ca_total_additions: Σ all Col C
- sch_ca_federal_agi: federal AGI passthrough for Line 27 Col A
- sch_ca_ca_agi: federal_agi - Σ subtractions + Σ additions
"""

from collections import defaultdict
from tenforty.models import CASchCAAdjustment, DivergenceDirection, DivergenceSource
from tenforty.rounding import irs_round


# Federal compute key → Sch CA line label (Col A passthrough source).
# Maps every federal compute output that has a 1:1 line on Sch CA Part I.
# Section A draws from Form 1040 (consumed via f1040.compute output keys);
# Sections B and C draw from Schedule 1 (consumed via sch_1.compute output
# keys, which are line-keyed `sch_1_line_<N>_<category>`). The kernel
# emits `sch_ca_line_<line>_col_a` for each present-and-truthy federal
# value at compute time; pdf_sch_ca routes those keys to per-line Col A
# cells.
#
# Section B alimony (Line 2a) has no federal compute key — alimony income
# is TCJA-era and not separately reported by the existing federal compute
# layer. Sections of Sch CA that carry only worksheet-supplied values
# (most of §C lines 12, 14, 16, 18, 19a, 23, plus §A line 1 sub-letters)
# are not entered here; their Col A values come from worksheet imports.
_FEDERAL_TO_SCH_CA_COL_A_MAP: dict[str, str] = {
    # Section A — federal Form 1040 income (line-keyed in 1040 output)
    "wages":                                "Part I §A 1z",
    "taxable_interest":                     "Part I §A 2",
    "ordinary_dividends":                   "Part I §A 3",
    "ira_taxable":                          "Part I §A 4",
    "pensions_taxable":                     "Part I §A 5b",
    "social_security_taxable":              "Part I §A 6",
    "capital_gain_loss":                    "Part I §A 7",
    # Section B — federal Schedule 1 additional income
    "sch_1_line_1_taxable_refunds":         "Part I §B 1",
    "sch_1_line_3_business_income":         "Part I §B 3",
    "sch_1_line_4_other_gains":             "Part I §B 4",
    "sch_1_line_5_rental_re_royalty":       "Part I §B 5",
    "sch_1_line_6_farm_income":             "Part I §B 6",
    "sch_1_line_7_unemployment":            "Part I §B 7",
    "sch_1_line_8z_other_income":           "Part I §B 8z",
    # Section C — federal Schedule 1 adjustments to income
    "sch_1_line_11_educator":               "Part I §C 11",
    "sch_1_line_13_hsa":                    "Part I §C 13",
    "sch_1_line_15_se_tax":                 "Part I §C 15",
    "sch_1_line_17_se_health":              "Part I §C 17",
    "sch_1_line_20_ira":                    "Part I §C 20",
    "sch_1_line_21_student_loan_interest":  "Part I §C 21",
}


def _normalize_line(sch_ca_line: str) -> str:
    """Convert 'Part I §B 8z' style to 'part_i_b_8z' for compute key suffix."""
    return (sch_ca_line.lower()
            .replace("§", "")
            .replace(" ", "_")
            .strip("_"))


def compute(ca540, federal_results: dict) -> dict:
    if ca540 is None:
        return {}
    auto = derive_auto_divergences(federal_results)
    all_divergences = list(ca540.divergences) + auto
    subtractions = defaultdict(float)
    additions = defaultdict(float)
    for adj in all_divergences:
        bucket = subtractions if adj.direction == DivergenceDirection.SUBTRACTION else additions
        bucket[adj.sch_ca_line] += adj.amount

    out = {}
    for line, amount in subtractions.items():
        key = f"sch_ca_line_{_normalize_line(line)}_subtractions"
        out[key] = irs_round(amount)
    for line, amount in additions.items():
        key = f"sch_ca_line_{_normalize_line(line)}_additions"
        out[key] = irs_round(amount)

    for fed_key, sch_ca_line in _FEDERAL_TO_SCH_CA_COL_A_MAP.items():
        amount = federal_results.get(fed_key, 0.0)
        if amount:
            key = f"sch_ca_line_{_normalize_line(sch_ca_line)}_col_a"
            out[key] = irs_round(amount)

    total_sub = sum(subtractions.values())
    total_add = sum(additions.values())
    out["sch_ca_total_subtractions"] = irs_round(total_sub)
    out["sch_ca_total_additions"] = irs_round(total_add)

    federal_agi = federal_results.get("agi", 0.0)
    out["sch_ca_federal_agi"] = irs_round(federal_agi)
    out["sch_ca_ca_agi"] = irs_round(federal_agi - total_sub + total_add)
    return out


def derive_auto_divergences(federal_results: dict) -> list[CASchCAAdjustment]:
    """Generate mechanical divergences from federal results.

    Each entry in this catalog represents a federal-vs-CA difference where
    the value is fully determined by federal data alone — no user input
    needed. The kernel adds these to user-supplied worksheet divergences
    before routing.
    """
    divergences = []

    if (ui := federal_results.get("schedule_1_unemployment_compensation", 0.0)) > 0:
        divergences.append(CASchCAAdjustment(
            source=DivergenceSource.AUTO_DERIVED,
            sch_ca_line="Part I §B 7",
            direction=DivergenceDirection.SUBTRACTION,
            amount=ui,
            description="Unemployment compensation excluded by CA per R&TC 17083",
            federal_source="Sch 1 line 7",
            pub1001_ref="p.17",
        ))

    if (ss := federal_results.get("form_1040_taxable_social_security", 0.0)) > 0:
        divergences.append(CASchCAAdjustment(
            source=DivergenceSource.AUTO_DERIVED,
            sch_ca_line="Part I §A 6",
            direction=DivergenceDirection.SUBTRACTION,
            amount=ss,
            description="Social Security benefits excluded by CA per R&TC 17087",
            federal_source="1040 line 6b (taxable portion)",
            pub1001_ref="p.10",
        ))

    if (refund := federal_results.get("schedule_1_state_local_tax_refund", 0.0)) > 0:
        divergences.append(CASchCAAdjustment(
            source=DivergenceSource.AUTO_DERIVED,
            sch_ca_line="Part I §B 1",
            direction=DivergenceDirection.SUBTRACTION,
            amount=refund,
            description="State income tax refund not taxed by CA per R&TC 17131",
            federal_source="Sch 1 line 1",
            pub1001_ref="p.11",
        ))

    if (rrb := federal_results.get("form_1040_railroad_retirement_tier_1_2", 0.0)) > 0:
        divergences.append(CASchCAAdjustment(
            source=DivergenceSource.AUTO_DERIVED,
            sch_ca_line="Part I §A 5b",
            direction=DivergenceDirection.SUBTRACTION,
            amount=rrb,
            description="Railroad retirement excluded by CA per R&TC 17087",
            federal_source="1040 line 5b (RRB component)",
            pub1001_ref="p.9",
        ))

    if (pfl := federal_results.get("schedule_1_pfl_benefits", 0.0)) > 0:
        divergences.append(CASchCAAdjustment(
            source=DivergenceSource.AUTO_DERIVED,
            sch_ca_line="Part I §B 7",
            direction=DivergenceDirection.SUBTRACTION,
            amount=pfl,
            description="Paid Family Leave benefits excluded by CA",
            federal_source="Sch 1 line 7 (PFL portion)",
            pub1001_ref="p.17",
        ))

    return divergences
