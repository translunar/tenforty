"""California Schedule X ("Explanation of Amended Return Changes") PDF field
mapping — YEAR-KEYED across the five per-year FTB templates (TY2021-2025).

Consumes the ``forms/schedule_x`` assembler's YEAR-AGNOSTIC output keys
(``schedule_x_line1``..``schedule_x_line11`` incl. 8a/8b/8c/10, the balance
lines, ``schedule_x_explanation`` and ``schedule_x_taxable_year``) and maps
each to its field PATH on THAT YEAR's own template. Every path is that year's
OWN ``get_fields()`` key, marker-probe certified against
``pdfs/california/amendments/schedule_x_<year>.pdf`` (see
``docs/plans/amended-returns-probe-tables.md``, "CA Schedule X"). NO path is
inferred, inherited, or format-carried across a year boundary.

THREE DISTINCT FIELD-NAMESPACE/NUMBERING SHAPES
-----------------------------------------------
The single-page form has identical LAYOUT (Part I lines 1-11, Part II reasons +
explanation) across all five years, but the AcroForm namespace AND numbering
diverge — the exact contamination trap that burned prior work twice. Three
groups, each re-certified from its own template's get_fields:

  * **Group A — 2021 & 2022** (bare numeric names, TY WRITE-IN field):
    a fillable TAXABLE-YEAR box at ``1001``; name/SSN at ``1002``/``1003``;
    money lines 1-11 at ``1004``-``1016`` (offset +1 by the year write-in);
    Part II explanation at ``1030``.
  * **Group B — 2023** (bare numeric names, TY PREPRINTED): NO year field, so
    name/SSN shift to ``1001``/``1002`` and money lines 1-11 land at
    ``1003``-``1015`` (−1 vs Group A); explanation at ``1028``.
  * **Group C — 2024 & 2025** (``"Sch X Form "``-PREFIXED names, TY
    PREPRINTED): SAME line-to-suffix numbering as Group B, but every path is
    prefixed. Explanation at ``Sch X Form 1028``.

So Groups B and C share ONE suffix dict (``_MONEY_SUFFIX_BC``); Group C only
differs by the ``"Sch X Form "`` prefix (mirroring the bare/prefixed split in
pdf_f100s_k1). Group A has its OWN numbering AND the extra taxable-year field,
so it is an explicit dict. Each year's paths are verified present on that year's
own template by the mapping test.

PER-YEAR DIFFERENCE — TAXABLE YEAR
----------------------------------
``schedule_x_taxable_year`` is mapped ONLY for 2021/2022 (the fillable write-in
box). 2023/2024/2025 print the year on the template — there is NO fillable year
field, so ``schedule_x_taxable_year`` is INTENTIONALLY UNMAPPED for those three
years (the coverage test allows this per-year difference).

INTENTIONALLY UNMAPPED DIAGNOSTIC ALIASES (all years)
-----------------------------------------------------
The assembler emits two DUPLICATE aliases carrying the same value as their bare
line key:
  * ``schedule_x_line7_amount_owed`` duplicates ``schedule_x_line7``
  * ``schedule_x_line11_refund``     duplicates ``schedule_x_line11``
Only the BARE line keys are mapped. Mapping an alias too would double-write a
single field (identical value written twice to one widget), so both aliases are
DELIBERATELY absent from every year's mapping. The coverage test asserts their
absence.

The Part II reason CHECKBOXES (13 boxes for 2021/2022, 12 for 2023-2025) and
the name/SSN identity fields are out of this mapping's scope — the assembler
emits neither; identity is injected at emit and the reason boxes are a
follow-up. Only the fillable Part I money lines + the Part II explanation (+ the
Group-A year write-in) are mapped here.
"""
from tenforty.mappings.registry import PdfFormMapping

# Group A (2021 & 2022): bare numeric names, TY WRITE-IN at 1001, money lines
# offset +1 by that write-in. Certified from schedule_x_2021.pdf /
# schedule_x_2022.pdf get_fields (identical field sets, re-verified per year).
_MAPPING_2021_2022: dict[str, str] = {
    "schedule_x_taxable_year": "1001",  # TAXABLE YEAR write-in box (top-left)
    "schedule_x_line1":  "1004",  # L1 amount you owe (amended return)
    "schedule_x_line2":  "1005",  # L2 overpaid tax (original / FTB-adjusted)
    "schedule_x_line3":  "1006",  # L3 = L1 + L2
    "schedule_x_line4":  "1007",  # L4 refund (amended return)
    "schedule_x_line5":  "1008",  # L5 tax paid with original + additional
    "schedule_x_line6":  "1009",  # L6 = L4 + L5
    "schedule_x_line7":  "1010",  # L7 AMOUNT YOU OWE (L3 - L6)
    "schedule_x_line8a": "1011",  # L8a penalties
    "schedule_x_line8b": "1012",  # L8b interest
    "schedule_x_line8c": "1013",  # L8c penalties + interest
    "schedule_x_line9":  "1014",  # L9 refund subtotal (L6 - L3)
    "schedule_x_line10": "1015",  # L10 applied to next-year estimated tax
    "schedule_x_line11": "1016",  # L11 REFUND (L9 - L10)
    "schedule_x_explanation": "1030",  # Part II line 2 explanation box
}

# Groups B & C (2023 / 2024 / 2025): TY PREPRINTED (no year field), name/SSN at
# 1001/1002, money lines shifted −1 vs Group A. ONE suffix dict shared by the
# bare (2023) and prefixed (2024/2025) namespaces. Certified from
# schedule_x_2023.pdf (bare) and schedule_x_2024/2025.pdf (prefixed).
_MONEY_SUFFIX_BC: dict[str, str] = {
    "schedule_x_line1":  "1003",  # L1 amount you owe (amended return)
    "schedule_x_line2":  "1004",  # L2 overpaid tax (original / FTB-adjusted)
    "schedule_x_line3":  "1005",  # L3 = L1 + L2
    "schedule_x_line4":  "1006",  # L4 refund (amended return)
    "schedule_x_line5":  "1007",  # L5 tax paid with original + additional
    "schedule_x_line6":  "1008",  # L6 = L4 + L5
    "schedule_x_line7":  "1009",  # L7 AMOUNT YOU OWE (L3 - L6)
    "schedule_x_line8a": "1010",  # L8a penalties
    "schedule_x_line8b": "1011",  # L8b interest
    "schedule_x_line8c": "1012",  # L8c penalties + interest
    "schedule_x_line9":  "1013",  # L9 refund subtotal (L6 - L3)
    "schedule_x_line10": "1014",  # L10 applied to next-year estimated tax
    "schedule_x_line11": "1015",  # L11 REFUND (L9 - L10)
    "schedule_x_explanation": "1028",  # Part II line 2 explanation box
}
_MAPPING_2023: dict[str, str] = dict(_MONEY_SUFFIX_BC)  # bare
_MAPPING_2024_2025: dict[str, str] = {  # "Sch X Form "-prefixed
    k: f"Sch X Form {n}" for k, n in _MONEY_SUFFIX_BC.items()
}


class PdfScheduleX(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for California Schedule X. YEAR-KEYED across five
    per-year FTB templates in THREE shapes: bare names + year write-in + money
    lines 1004-1016 for 2021/2022; bare names + preprinted year + money lines
    1003-1015 for 2023; "Sch X Form "-prefixed + preprinted year + same
    numbering for 2024/2025. Each year's paths are certified from its own
    template's get_fields; nothing is inherited across the bare/prefixed or
    numbering-shift boundaries."""

    _FORM_NAME = "Schedule X"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2021: _MAPPING_2021_2022, 2022: _MAPPING_2021_2022,
        2023: _MAPPING_2023,
        2024: _MAPPING_2024_2025, 2025: _MAPPING_2024_2025,
    }


def get_mapping(year: int) -> dict[str, str]:
    """Module-level accessor the completeness gate calls."""
    return PdfScheduleX.get_mapping(year)
