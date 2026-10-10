"""Render the Form 3115 Schedule E statement for lines 4a and 7.

Schedule E has no per-asset grid: lines 4a and 7 say "attach a statement"
describing the property subject to the change and, for the present and
proposed methods, the Code section, asset class, method, recovery period,
convention, special depreciation allowance and asset account. The IRS
provides no form for it, so tenforty writes one block per item of property
from the scenario's `form_3115.assets` rows.

Every value is printed AS STATED; nothing is computed. There is no row limit:
blocks flow onto as many pages as they need, each page carrying the header.
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from tenforty.forms.f3115 import money
from tenforty.models import FORM_3115_ASSET_ACCOUNTS, Form3115, Form3115Asset

TITLE = "Form 3115, Schedule E — Statement for lines 4a and 7"

_LEFT, _RIGHT = 1 * inch, 7.5 * inch
_TOP, _BOTTOM = 10.2 * inch, 0.9 * inch
_FONT, _SIZE, _LEADING = "Helvetica", 9, 0.17 * inch
_INDENT = 0.2 * inch


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def asset_lines(asset: Form3115Asset) -> list[str]:
    """The printed "Label: value" lines of one asset block, in form order
    (line 4a, then line 7a-h)."""
    return [
        f"Type of property: {asset.property_type}",
        f"Placed in service: {asset.date_placed_in_service:%m/%d/%Y}",
        f"Use: {asset.use_in_activity}",
        f"Tax credits or grants: {asset.tax_credits_or_grants}",
        f"Unadjusted basis: {money(asset.unadjusted_basis)}",
        "Depreciation claimed under present method: "
        f"{money(asset.depreciation_claimed_present_method)}",
        f"Code section: {asset.code_section}",
        f"Asset class (Rev. Proc. 87-56): {asset.asset_class}",
        f"Present method: {asset.present_method}",
        f"Present recovery period: {asset.present_recovery_period}",
        f"Present convention: {asset.present_convention}",
        f"Proposed method: {asset.proposed_method}",
        f"Proposed recovery period: {asset.proposed_recovery_period}",
        f"Proposed convention: {asset.proposed_convention}",
        "Special depreciation allowance claimed: "
        f"{_yes_no(asset.special_depreciation_allowance_claimed)}",
        f"Asset account: {FORM_3115_ASSET_ACCOUNTS[asset.asset_account]}",
    ]


def render_f3115_asset_statement(
        form: Form3115, applicant_name: str, identification_number: str,
        output_path: Path) -> Path:
    """Render the statement to ``output_path``. Deterministic (invariant=1,
    fixed creator/producer), like the other synthesized statements."""
    if not form.assets:
        raise ValueError("Form 3115 asset statement needs at least one asset")
    c = canvas.Canvas(str(output_path), pagesize=letter, invariant=1)
    c.setTitle(f"{TITLE} {form.year_of_change}")
    c.setCreator("tenforty")
    c.setProducer("tenforty")
    width = _RIGHT - _LEFT

    def header() -> float:
        y = _TOP
        c.setFont("Helvetica-Bold", 12)
        c.drawString(_LEFT, y, TITLE)
        y -= 0.24 * inch
        c.setFont(_FONT, _SIZE)
        c.drawString(
            _LEFT, y,
            f"Applicant: {applicant_name}    Identification number: "
            f"{identification_number}    Year of change: {form.year_of_change}")
        y -= 0.1 * inch
        c.line(_LEFT, y, _RIGHT, y)
        return y - 0.26 * inch

    y = header()
    for number, asset in enumerate(form.assets, start=1):
        wrapped: list[tuple[str, float]] = []
        for text in asset_lines(asset):
            parts = simpleSplit(text, _FONT, _SIZE, width - _INDENT)
            wrapped += [(parts[0], _INDENT)]
            wrapped += [(part, 2 * _INDENT) for part in parts[1:]]
        title = simpleSplit(
            f"{number}. {asset.description}", "Helvetica-Bold", 10, width)
        needed = (len(title) + len(wrapped) + 1) * _LEADING
        if y - needed < _BOTTOM and y < _TOP - 0.7 * inch:
            c.showPage()
            y = header()
        c.setFont("Helvetica-Bold", 10)
        for part in title:
            c.drawString(_LEFT, y, part)
            y -= _LEADING
        c.setFont(_FONT, _SIZE)
        for text, indent in wrapped:
            if y < _BOTTOM:
                c.showPage()
                y = header()
                c.setFont(_FONT, _SIZE)
            c.drawString(_LEFT + indent, y, text)
            y -= _LEADING
        y -= _LEADING
    c.showPage()
    c.save()
    return output_path
