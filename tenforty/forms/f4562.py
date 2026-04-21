"""Form 4562 — Depreciation and Amortization.

v1 scope: Part III Section B (line 19a..19j) current-year GDS MACRS
plus the line 22 grand total. Sections 179 (Part I), special/bonus
(Part II), listed property (Part V), and amortization (Part VI) are
out of scope. Prior-year MACRS (line 17) and ADS (Section C, line 20)
are also out of scope in v1 — add tables A-8/A-9 and wire line 17
when a scenario needs them.

Form 4562 Part III Section B is **row-per-recovery-class**, not
row-per-asset. Multiple assets sharing a recovery class aggregate
into the same row (their bases and deductions sum). Row labels:

  19a: 3-year  | 19b: 5-year  | 19c: 7-year  | 19d: 10-year
  19e: 15-year | 19f: 20-year | 19g: 25-year | 19h: 50-year
  19i: residential rental (27.5-year)
  19j: nonresidential real (39-year)

v1 emits only rows whose class has at least one asset — zero-asset
rows are omitted (no phantom zeros). 19i and 19j each have two
placement sub-rows on the PDF; v1 fills the first sub-row and raises
if a second real-property asset of the same class exists (forces
explicit sub-row support rather than silently dropping).
"""

from collections import defaultdict

from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.models import Scenario

# Recovery class → Form 4562 Section B row label (lowercase letter).
_CLASS_TO_ROW: dict[str, str] = {
    "3-year": "a",
    "5-year": "b",
    "7-year": "c",
    "10-year": "d",
    "15-year": "e",
    "20-year": "f",
    "25-year": "g",
    "50-year": "h",
    "27.5-year": "i",
    "39-year": "j",
}

_PROPERTY_METHOD = {
    "half-year": "200DB",
    "mid-quarter": "200DB",
    "mid-month": "S/L",
}


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    tax_year = scenario.config.year
    result: dict = {
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }
    assets_by_class: dict[str, list] = defaultdict(list)
    for asset in scenario.depreciable_assets:
        assets_by_class[asset.recovery_class].append(asset)

    rows: list[dict] = []
    total = 0
    for recovery_class, assets in assets_by_class.items():
        row_label = _CLASS_TO_ROW.get(recovery_class)
        if row_label is None:
            raise NotImplementedError(
                f"No Form 4562 Section B row for recovery_class="
                f"{recovery_class!r}. v1 supports "
                f"{sorted(_CLASS_TO_ROW)}."
            )
        conventions = {a.convention for a in assets}
        if len(conventions) > 1:
            raise NotImplementedError(
                f"Mixed conventions {sorted(conventions)!r} within a single "
                f"recovery class {recovery_class!r} require separate "
                f"Section B sub-rows; v1 assumes one convention per class."
            )
        convention = conventions.pop()
        earliest = min(a.date_placed_in_service for a in assets)
        class_total_basis = sum(a.basis for a in assets)
        class_total_deduction = sum(
            macrs_deduction(a, tax_year) for a in assets
        )
        total += class_total_deduction
        row = {
            "row_label": row_label,
            "recovery_class": recovery_class,
            "date_placed_in_service": earliest,
            "basis": class_total_basis,
            "convention": convention,
            "method": _PROPERTY_METHOD[convention],
            "deduction": class_total_deduction,
        }
        rows.append(row)
        # Scalar field keys per row for the PDF mapping.
        prefix = f"f4562_line_19{row_label}"
        result[f"{prefix}_date_placed_in_service"] = (
            f"{earliest.month:02d}/{earliest.year:04d}"
        )
        result[f"{prefix}_basis"] = int(round(class_total_basis))
        result[f"{prefix}_recovery_period"] = _recovery_period_text(recovery_class)
        result[f"{prefix}_convention"] = _convention_text(convention)
        result[f"{prefix}_method"] = _PROPERTY_METHOD[convention]
        result[f"{prefix}_deduction"] = class_total_deduction

    result["f4562_part_iii_section_b_rows"] = rows
    result["f4562_line_22_total_depreciation"] = total
    return result


def _recovery_period_text(recovery_class: str) -> str:
    # "5-year" → "5 yrs."; "27.5-year" → "27.5 yrs.".
    num = recovery_class.removesuffix("-year")
    return f"{num} yrs."


def _convention_text(convention: str) -> str:
    return {
        "half-year": "HY",
        "mid-month": "MM",
        "mid-quarter": "MQ",
    }[convention]


