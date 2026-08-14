"""Render the §199A 'Statement A — QBI Pass-through Entity Reporting' page
that accompanies Schedule K-1 (Form 1120-S) box 17 code V.

The IRS furnishes Statement A as a worksheet in the 1120-S instructions, not
as a standalone fillable form. tenforty synthesizes an equivalent one-page
statement per shareholder listing the §199A items the shareholder needs to
compute the QBI deduction (below-threshold: QBI is the operative figure;
W-2 wages and UBIA are informational)."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from tenforty.models import K1Allocation


def _money(x: float) -> str:
    return f"{x:,.0f}"


def render_199a_statement_a(alloc: K1Allocation, year: int, output_path: Path) -> Path:
    """Render one shareholder's Statement A to ``output_path``.

    Deterministic: ``invariant=1`` suppresses reportlab's creation timestamp
    and randomized document ID, and the producer/creator strings are fixed, so
    identical inputs yield identical bytes (pinned by the renderer tests).

    W-2 wages and UBIA of qualified property are informational only: below
    the §199A wage/UBIA threshold (tenforty's only supported QBI scope, the
    Form 8995 simplified path), they do not limit the QBI deduction.
    """
    # invariant=1 -> fixed timestamp + document ID (deterministic output).
    c = canvas.Canvas(str(output_path), pagesize=letter, invariant=1)
    c.setTitle(f"Statement A - QBI Pass-through Entity Reporting {year}")
    c.setCreator("tenforty")
    c.setProducer("tenforty")

    left = 1 * inch
    right = 7.5 * inch
    y = 10.2 * inch

    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, "Statement A — QBI Pass-through Entity Reporting")
    y -= 0.26 * inch
    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"(Schedule K-1, Form 1120-S, Box 17, Code V — Tax Year {year})")
    y -= 0.45 * inch

    # Identity block — corporation, then shareholder and their share.
    c.setFont("Helvetica", 10)
    for label, value in [
        ("Corporation's name", alloc.entity.name),
        ("Corporation's EIN", alloc.entity.ein),
        ("Shareholder's name", alloc.shareholder.name),
        ("Shareholder's identifying number", alloc.shareholder.ssn_or_ein),
        ("Shareholder's allocation percentage", f"{alloc.ownership_percentage:g}%"),
    ]:
        c.drawString(left, y, f"{label}:")
        c.drawString(left + 2.9 * inch, y, str(value))
        y -= 0.24 * inch

    y -= 0.2 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Shareholder's share of:")
    y -= 0.08 * inch
    c.line(left, y, right, y)
    y -= 0.26 * inch

    # The three §199A line items, labeled as the 1120-S instructions'
    # Statement A rows so a preparer recognizes the form on sight.
    c.setFont("Helvetica", 10)
    for label, value in [
        ("Ordinary business income (loss)", alloc.box_17v_qbi),
        ("W-2 wages", alloc.box_17v_w2_wages),
        ("UBIA of qualified property", alloc.box_17v_ubia),
    ]:
        c.drawString(left + 0.15 * inch, y, label)
        c.drawRightString(right, y, _money(value))
        y -= 0.26 * inch

    y -= 0.05 * inch
    c.line(left, y, right, y)
    y -= 0.34 * inch
    c.setFont("Helvetica", 8)
    c.drawString(
        left, y,
        "This statement reports the section 199A items for a single trade or "
        "business. Amounts are the shareholder's pro rata share.",
    )
    c.showPage()
    c.save()
    return output_path
