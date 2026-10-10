"""Form 4562 — Depreciation and Amortization.

Scope: the header (name, business or activity, identifying number), Part
III line 17 (MACRS on assets placed in service in earlier tax
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

A personal-property row (19a-19f) prints basis, recovery period, convention,
method and deduction. Column (b), month and year placed in service, is
shaded on those rows and is left empty: the form asks for it only on the
residential and nonresidential rows (19i, 19j here).

Every personal-property asset placed in the return year takes the same
convention -- half-year, or mid-quarter when the return's 40% test trips --
so a class row carries exactly one; `_row_convention` refuses rather than
print one of two if that ever fails to hold. Under the mid-quarter
convention same-class assets placed in different quarters still share the
class row: the row prints MQ, their bases summed, and the sum of their
per-asset deductions, each from its own quarter's table. The method comes
from the class, never from the convention.

Only rows whose class has at least one asset placed this year are emitted,
and line 17 only when its amount is nonzero (no phantom zeros). 19i and 19j
each have two placement sub-rows on the PDF; only the first is filled.
"""

from collections import defaultdict

from tenforty.attestations import (
    activities_with_assets, depreciation_activities,
)
from tenforty.forms.depreciation.macrs import asset_convention, method_for
from tenforty.forms.depreciation.resolver import (
    asset_amount, mid_quarter_applies,
)
from tenforty.models import REAL_PROPERTY_CLASSES, RentalProperty, Scenario
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


def _row_convention(recovery_class: str, assets: list, tax_year: int,
                    mid_quarter: bool) -> str:
    """The one convention a class's row prints. Every asset here was placed
    in service in ``tax_year``, so each takes the return year's convention
    and they cannot differ; this refuses if they ever do."""
    conventions = {
        asset_convention(a, return_year=tax_year, mid_quarter=mid_quarter)[0]
        for a in assets}
    if len(conventions) != 1:
        raise NotImplementedError(
            f"Form 4562 line 19 row for recovery_class={recovery_class!r} "
            f"would carry more than one convention ({sorted(conventions)}); "
            f"a row prints exactly one.")
    return conventions.pop()


def _line_19_rows(placed_this_year: list, tax_year: int, *,
                  mid_quarter: bool) -> list[dict]:
    """One Section B row per recovery class, over the assets placed in
    service during ``tax_year``. Every printed column of a row is decided
    here. ``mid_quarter`` is the return's 40% answer."""
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
        # Through the resolver's per-asset figure, not the raw table, so
        # this form cannot disagree with the line the activity prints. Each
        # asset's amount comes from its own quarter's table under the
        # mid-quarter convention; the row prints their sum.
        deduction = sum(
            asset_amount(a, tax_year, mid_quarter=mid_quarter)[0]
            for a in assets)
        rows.append({
            "row_label": row_label,
            "recovery_class": recovery_class,
            "date_placed_in_service": min(
                a.date_placed_in_service for a in assets),
            "basis": sum(a.basis for a in assets),
            "convention": _row_convention(
                recovery_class, assets, tax_year, mid_quarter),
            "method": method_for(recovery_class),
            "deduction": deduction,
        })
    return rows


def _line_19_row_fields(row: dict) -> dict:
    """Scalar field keys for one Section B row, for the PDF mapping."""
    prefix = f"f4562_line_19{row['row_label']}"
    fields: dict = {}
    # Column (b) is shaded on the personal-property rows; only the
    # residential and nonresidential rows state month and year.
    if row["recovery_class"] in REAL_PROPERTY_CLASSES:
        earliest = row["date_placed_in_service"]
        fields[f"{prefix}_date_placed_in_service"] = (
            f"{earliest.month:02d}/{earliest.year:04d}")
    return {
        **fields,
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


ACTIVITY_KEY = "f4562_business_or_activity"


def _business_or_activity(scenario: Scenario) -> str:
    """What the header box "Business or activity to which this form relates"
    prints: the one asset-listing activity, named exactly as its own
    schedule names it -- a rental's address (Schedule E line 1a) or a
    business's description (Schedule C line A). Nothing is added to it.

    Empty when there is nothing to print: the activity has no name, or the
    assets span more than one activity, so the one merged form has no
    single activity to name. The box then stays blank; no placeholder is
    ever printed."""
    listing = activities_with_assets(scenario)
    if len(listing) != 1:
        return ""
    _label, activity = listing[0]
    if isinstance(activity, RentalProperty):
        return activity.address
    return str(activity.description).strip()


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    tax_year = scenario.config.year
    mid_quarter = mid_quarter_applies(scenario)
    result: dict = {**scenario.config.pdf_header()}
    activity = _business_or_activity(scenario)
    if activity:
        result[ACTIVITY_KEY] = activity
    placed_this_year, placed_earlier = [], []
    for asset in scenario_assets(scenario):
        if asset.date_placed_in_service.year == tax_year:
            placed_this_year.append(asset)
        else:
            placed_earlier.append(asset)

    # Line 17: one amount for every asset placed in an earlier tax year, at
    # the resolver's per-asset figure (so the basis ceiling carries through).
    # Each such asset reads the convention it STATES, not this year's.
    line_17 = sum(
        asset_amount(a, tax_year, mid_quarter=mid_quarter)[0]
        for a in placed_earlier)
    if line_17:
        result[LINE_17_KEY] = line_17

    rows = _line_19_rows(placed_this_year, tax_year, mid_quarter=mid_quarter)
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


