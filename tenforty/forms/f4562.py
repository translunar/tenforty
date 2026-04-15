"""Form 4562 — Depreciation and Amortization.

v1 scope: Part III MACRS (line 17 + line 19 repeater rows) and the
line 22 grand total. Sections 179, bonus (Part II), listed property
(Part V), and amortization (Part VI) are out of scope.

Per-asset deductions come from ``forms.depreciation.macrs.macrs_deduction``;
this module just iterates the scenario's ``depreciable_assets``, collects
the Part III row dicts, and sums line 22.
"""

from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.models import Scenario


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    tax_year = scenario.config.year
    rows: list[dict] = []
    total = 0
    for asset in scenario.depreciable_assets:
        deduction = macrs_deduction(asset, tax_year)
        rows.append({
            "description": asset.description,
            "date_placed_in_service": asset.date_placed_in_service,
            "basis": asset.basis,
            "recovery_class": asset.recovery_class,
            "convention": asset.convention,
            "deduction": deduction,
        })
        total += deduction
    return {
        "taxpayer_name": _format_taxpayer_name(scenario),
        "taxpayer_ssn": scenario.config.ssn,
        "f4562_part_iii_macrs_assets": rows,
        "f4562_line_22_total_depreciation": total,
    }


def _format_taxpayer_name(scenario: Scenario) -> str:
    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return f"{first} {last}".strip()
