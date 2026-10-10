"""Form 4562 — Depreciation and Amortization.

Scope: Part III line 17 (MACRS on assets placed in service in earlier tax
years), Part III Section B (line 19a..19j, GDS MACRS on assets placed in
service DURING the return year) and the line 22 total. Section 179 (Part I),
special/bonus (Part II), ADS (Section C, line 20), listed property (Part V)
and amortization (Part VI) are out of scope.

Which line an asset prints on is decided by its in-service year alone:

  placed during the return year -> its Section B class row (line 19)
  placed in an earlier year     -> line 17, one amount for all such assets

Section B is headed "Assets Placed in Service During {year} Tax Year", so an
asset from an earlier year never appears in a line 19 row. Line 22 is line
17 plus the line 19 column (g) amounts, which is every asset on the return,
each at the resolver's per-asset figure.

Section B is **row-per-recovery-class**, not row-per-asset. Multiple assets
placed this year in one recovery class aggregate into the same row (their
bases and deductions sum). Row labels:

  19a: 3-year  | 19b: 5-year  | 19c: 7-year  | 19d: 10-year
  19e: 15-year | 19f: 20-year | 19g: 25-year | 19h: 50-year
  19i: residential rental (27.5-year)
  19j: nonresidential real (39-year)

There is no mixed-convention guard, by design: the convention is computed
from the recovery class, so one class cannot carry two conventions.

Only rows whose class has at least one asset placed this year are emitted,
and line 17 only when its amount is nonzero (no phantom zeros). 19i and 19j
each have two placement sub-rows on the PDF; only the first is filled.
"""

from collections import defaultdict

from tenforty.attestations import depreciation_activities
from tenforty.forms.depreciation.macrs import convention_for
from tenforty.forms.depreciation.resolver import asset_amount
from tenforty.models import Scenario
from tenforty.rounding import irs_round

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


def scenario_assets(scenario: Scenario) -> list:
    """Every asset on the return, flattened across activities.

    READ-PATH ADAPTER ONLY: assets now nest under their activity, and this
    form still emits its legacy one-form-per-return shape. The per-activity
    form is a later branch."""
    return [
        asset
        for _section, _index, _label, activity in depreciation_activities(
            scenario)
        for asset in activity.depreciable_assets]


def is_required(scenario: Scenario) -> bool:
    """True when the return must carry Form 4562: some property was placed
    in service during the return year, on any activity.

    Instructions for Form 4562 (2025), "Who Must File" (page 2): file the
    form if claiming "Depreciation for property placed in service during the
    2025 tax year." The other triggers on that list, and what happens to
    each here:
      - a section 179 deduction: no input exists, and an asset with section
        179 history refuses (ledger: `bonus_or_section_179_history`);
      - depreciation on any vehicle or other listed property, "regardless
        of when it was placed in service": REFUSES unless the scenario
        states `acknowledges_no_listed_property: true` (ledger:
        `unacknowledged_listed_property`) -- the asset model cannot see
        whether an asset is listed, so it asks whenever personal property
        is present;
      - amortization beginning this year: no input exists;
      - a corporate return: Form 1120-S is excluded by the instructions'
        own words, and no other corporate return is modeled.
    An ongoing year, with only
    property placed in earlier years, files no Form 4562; the depreciation
    still prints on Schedule E line 18 / Schedule C line 13."""
    year = scenario.config.year
    return any(
        asset.date_placed_in_service.year == year
        for asset in scenario_assets(scenario))


LINE_17_KEY = "f4562_line_17"


def _line_19_rows(placed_this_year: list, tax_year: int) -> list[dict]:
    """One Section B row per recovery class, over the assets placed in
    service during ``tax_year``. Every printed column of a row is decided
    here."""
    assets_by_class: dict[str, list] = defaultdict(list)
    for asset in placed_this_year:
        assets_by_class[asset.recovery_class].append(asset)

    rows: list[dict] = []
    for recovery_class, assets in assets_by_class.items():
        row_label = _CLASS_TO_ROW.get(recovery_class)
        if row_label is None:
            raise NotImplementedError(
                f"No Form 4562 Section B row for recovery_class="
                f"{recovery_class!r}. v1 supports "
                f"{sorted(_CLASS_TO_ROW)}."
            )
        # The convention is computed from the class (the One Door helper),
        # so a class has exactly one.
        convention = convention_for(recovery_class)
        rows.append({
            "row_label": row_label,
            "recovery_class": recovery_class,
            "date_placed_in_service": min(
                a.date_placed_in_service for a in assets),
            "basis": sum(a.basis for a in assets),
            "convention": convention,
            "method": _PROPERTY_METHOD[convention],
            # Through the resolver's per-asset figure, not the raw table, so
            # this form cannot disagree with the line the activity prints.
            "deduction": sum(
                asset_amount(a, tax_year)[0] for a in assets),
        })
    return rows


def _line_19_row_fields(row: dict) -> dict:
    """Scalar field keys for one Section B row, for the PDF mapping."""
    prefix = f"f4562_line_19{row['row_label']}"
    earliest = row["date_placed_in_service"]
    return {
        f"{prefix}_date_placed_in_service": (
            f"{earliest.month:02d}/{earliest.year:04d}"),
        # irs_round rather than built-in round: IRS always rounds .5 up,
        # while Python's round() uses banker's (half-to-even) which diverges
        # at .5 boundaries (e.g. round(200_000.5) == 200_000, not 200_001).
        f"{prefix}_basis": int(irs_round(row["basis"])),
        f"{prefix}_recovery_period": _recovery_period_text(
            row["recovery_class"]),
        f"{prefix}_convention": _convention_text(row["convention"]),
        f"{prefix}_method": row["method"],
        f"{prefix}_deduction": row["deduction"],
    }


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    tax_year = scenario.config.year
    result: dict = {**scenario.config.pdf_header()}
    placed_this_year, placed_earlier = [], []
    for asset in scenario_assets(scenario):
        if asset.date_placed_in_service.year == tax_year:
            placed_this_year.append(asset)
        else:
            placed_earlier.append(asset)

    # Line 17: one amount for every asset placed in an earlier tax year, at
    # the resolver's per-asset figure (so the basis ceiling carries through).
    line_17 = sum(asset_amount(a, tax_year)[0] for a in placed_earlier)
    if line_17:
        result[LINE_17_KEY] = line_17

    rows = _line_19_rows(placed_this_year, tax_year)
    for row in rows:
        result.update(_line_19_row_fields(row))

    result["f4562_part_iii_section_b_rows"] = rows
    result["f4562_line_22_total_depreciation"] = line_17 + sum(
        row["deduction"] for row in rows)
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


