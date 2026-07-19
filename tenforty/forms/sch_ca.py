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
from tenforty.ca_divergences import CatalogDirection, load_catalog
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


def compute(ca540, federal_results: dict, year: int) -> dict:
    if ca540 is None:
        return {}
    auto = derive_auto_divergences(federal_results, year, ca540=ca540)
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


def federal_itemization_applied(federal_results: dict) -> bool:
    """True iff the federal return APPLIED itemized deductions.

    ``schedule_a_total`` is the RAW Schedule A total and is emitted even when
    the standard deduction won (a filer with a little mortgage interest below
    the standard deduction still has a positive ``schedule_a_total``). The
    signal for "itemized was actually taken" is ``applied_deduction ==
    schedule_a_total`` — ``applied_deduction`` is ``max(standard, sch_a_total)``
    on both the native-spine and workbook federal result dicts. CA Part II is
    computed only when this is true (v1 scope: CA itemizes iff federal does).
    """
    total = federal_results.get("schedule_a_total", 0)
    return total > 0 and federal_results.get("applied_deduction") == total


def compute_part_ii_itemized(sch_a_results: dict) -> dict:
    """Schedule CA (540) Part II — California itemized deductions.

    Start from the federal Schedule A line amounts (``sch_a_results`` — the
    dict returned by ``forms.sch_a.compute``) and apply CA's Part II
    adjustments, scoped to the
    lines this v1 supports (medical + taxes; mortgage/charity conform):

    - **Medical (Part II lines 1–4).** CA conforms to the federal
      7.5%-of-AGI floor AND — per the 2024 Schedule CA (540) form — Part II
      line 2's printed instruction is "Enter amount from federal Form 1040 or
      1040-SR, line 11" (FEDERAL AGI). So lines 1–4 replicate federal
      Schedule A exactly: CA medical is the federal medical deductible,
      passed through unchanged. (Recomputing the floor against CA AGI would
      be wrong — the form uses federal AGI.)
    - **Taxes (Part II lines 5–7).** CA disallows the deduction of state and
      local *income* tax (federal line 5a) and applies NO SALT cap. So CA
      deductible taxes = property + personal-property tax, uncapped, with the
      state-income-tax portion excluded.
    - **Mortgage / charity (lines 8, 11–14).** Conform for the amounts in
      scope — pass the federal values through. NOTE: CA's $1,000,000
      acquisition-debt limit (vs the federal $750,000) is OUT OF SCOPE; the
      pass-through is only valid for conforming amounts (0 here). This is
      documented, not gated.

    The caller computes this ONLY when the federal return itemized (federal
    ``schedule_a_total > 0``); a federal standard-deduction return gets no
    Part II and Form 540 keeps the CA standard deduction. (v1 scope: CA
    itemizes iff the federal return itemized — independent CA itemization on a
    federally-standard return is not modeled.)
    """
    medical = sch_a_results.get("sch_a_line_4_medical_deductible", 0)
    # State/local income tax (line 5a) is disallowed; no CA SALT cap applies.
    ca_taxes = (sch_a_results.get("sch_a_line_5b_property_tax", 0)
                + sch_a_results.get("sch_a_line_5c_personal_property_tax", 0))
    mortgage = sch_a_results.get("sch_a_line_8a_mortgage_interest", 0)
    charity = sch_a_results.get("sch_a_line_14_charity_total", 0)
    total = medical + ca_taxes + mortgage + charity
    return {
        "sch_ca_part_ii_medical": medical,
        "sch_ca_part_ii_taxes": ca_taxes,
        "sch_ca_part_ii_mortgage": mortgage,
        "sch_ca_part_ii_charity": charity,
        "ca_itemized_total": total,
    }


def derive_auto_divergences(
    federal_results: dict, year: int, ca540=None
) -> list[CASchCAAdjustment]:
    """Generate mechanical divergences from the packaged CA divergence catalog.

    Sources the catalog's ``auto:`` rows for ``year`` (via ``load_catalog``) and
    fires each whose keyed value is positive:

    - ``federal_key`` rows (UI, SS, state-tax refund) read
      ``federal_results[federal_key]`` — keys produced by f1040.compute /
      sch_1.compute — and fire with no user input.
    - ``ca540_field`` rows (RRB, PFL) read ``getattr(ca540, ca540_field)``:
      federal compute does not separately surface these (RRB is lumped into
      ``pensions_taxable`` / 1040 line 5b; PFL is reported on 1099-G alongside
      UI without separation), so the taxpayer supplies them on ``CA540Return``.
      These fire only when ``ca540`` is provided AND the field is positive.

    Emitted divergences carry ``source=CATALOG_AUTO`` and ``catalog_id=<row
    id>``; amount / line / direction / description are the migrated catalog
    values (behavior-preserving vs the retired hardcoded tuples).
    """
    divergences: list[CASchCAAdjustment] = []

    for entry in load_catalog(year):
        if entry.auto is None:
            continue
        direction = (
            DivergenceDirection.SUBTRACTION
            if entry.direction is CatalogDirection.SUB
            else DivergenceDirection.ADDITION
        )
        if entry.auto.federal_key is not None:
            amount = federal_results.get(entry.auto.federal_key, 0.0)
        elif ca540 is not None:
            amount = getattr(ca540, entry.auto.ca540_field) or 0.0
        else:
            continue
        if amount > 0:
            divergences.append(CASchCAAdjustment(
                source=DivergenceSource.CATALOG_AUTO,
                sch_ca_line=entry.sch_ca_line,
                direction=direction,
                amount=amount,
                description=entry.description,
                catalog_id=entry.id,
            ))

    return divergences
