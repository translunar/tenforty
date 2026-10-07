"""Render the 'Form 1120-S, Line 19 — Other Deductions Statement' page.

Form 1120-S line 19 reads "Other deductions (attach statement)"; the IRS
provides no form for the statement, so tenforty synthesizes a one-page
itemization from the scenario's ``other_deductions_components``. The
description/amount rows foot to the line 19 total by construction (see
``other_deductions_footing_problem``)."""
from pathlib import Path
from typing import Sequence

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from tenforty.models import OtherDeductionComponent
from tenforty.rounding import irs_round

_ROWS_PER_PAGE_LIMIT = 30  # single-page statement; refuse rather than overflow


def _money(x: float) -> str:
    return f"{irs_round(x):,}"


def components_total(components: Sequence[OtherDeductionComponent]) -> int:
    """Sum of per-item ``irs_round`` amounts — the convention f1120s uses for
    every printed line, so the statement total is a sum of printed figures."""
    return sum(irs_round(c.amount) for c in components)


def other_deductions_footing_problem(
        components: Sequence[OtherDeductionComponent],
        other_deductions: float) -> str | None:
    """Return a refusal message if non-empty ``components`` do not foot to the
    rounded ``other_deductions`` total, else None. Empty components never
    mismatch here (their absence is an emit-time concern)."""
    if not components:
        return None
    stmt, line = components_total(components), irs_round(other_deductions)
    if stmt != line:
        return (
            "s_corp_return.deductions.other_deductions_components sum to "
            f"{stmt} (after per-item rounding) but other_deductions rounds "
            f"to {line}; the line 19 statement must foot to the form.")
    return None


def render_other_deductions_statement(
    entity_name: str, ein: str, year: int,
    components: Sequence[OtherDeductionComponent], output_path: Path,
    *, title: str = "Form 1120-S, Line 19 — Other Deductions Statement",
    subtitle: str | None = None,
    total_label: str = "Total other deductions (Form 1120-S, line 19)",
) -> Path:
    """Render the statement to ``output_path``. Deterministic (invariant=1,
    fixed creator/producer), like ``render_199a_statement_a``."""
    if not components:
        raise ValueError("other-deductions statement needs at least one row")
    if len(components) > _ROWS_PER_PAGE_LIMIT:
        raise ValueError(
            f"other-deductions statement supports at most "
            f"{_ROWS_PER_PAGE_LIMIT} rows on one page; got {len(components)}")
    c = canvas.Canvas(str(output_path), pagesize=letter, invariant=1)
    c.setTitle(f"{title} {year}")
    c.setCreator("tenforty")
    c.setProducer("tenforty")

    left, right = 1 * inch, 7.5 * inch
    y = 10.2 * inch
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, title)
    y -= 0.26 * inch
    c.setFont("Helvetica", 10)
    c.drawString(left, y, subtitle or f"(Other deductions — Tax Year {year})")
    y -= 0.45 * inch

    for label, value in [("Corporation's name", entity_name),
                         ("Corporation's EIN", ein),
                         ("Tax year", str(year))]:
        c.drawString(left, y, f"{label}:")
        c.drawString(left + 2.2 * inch, y, str(value))
        y -= 0.24 * inch

    y -= 0.2 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Description")
    c.drawRightString(right, y, "Amount")
    y -= 0.08 * inch
    c.line(left, y, right, y)
    y -= 0.26 * inch

    c.setFont("Helvetica", 10)
    for comp in components:
        c.drawString(left + 0.15 * inch, y, comp.description)
        c.drawRightString(right, y, _money(comp.amount))
        y -= 0.26 * inch

    y -= 0.05 * inch
    c.line(left, y, right, y)
    y -= 0.26 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 0.15 * inch, y, total_label)
    c.drawRightString(right, y, f"{components_total(components):,}")
    c.showPage()
    c.save()
    return output_path


def render_ca_100s_other_deductions_statement(
    entity_name: str, ein: str, year: int,
    components: Sequence[OtherDeductionComponent], output_path: Path,
) -> Path:
    """The same itemization titled for California Form 100S Schedule F line 20
    (a pass-through of the federal line 19 figure)."""
    return render_other_deductions_statement(
        entity_name, ein, year, components, output_path,
        title="Form 100S, Schedule F, Line 20 — Other Deductions Statement",
        subtitle=f"(Other deductions — California — Tax Year {year})",
        total_label="Total other deductions (Form 100S, Schedule F, line 20)")
