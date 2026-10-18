"""Render the 'Schedule 1 (Form 1040), Line 8z — Other Income Statement'.

Line 8z reads "Other income. List type and amount". With two or more nonzero
Form 1099-G types the write-in says "See statement" and this page lists each
type and amount (Juno's 8z ruling): the rows are the computation's
``sch_1_line_8z_statement_rows`` and foot to line 8z by construction (each
type rounded alone, 8z their sum). Rendered by the shared other-income /
other-deductions statement page with the individual's header labels."""
from pathlib import Path
from typing import Sequence

from tenforty.filing.statement_other_deductions import (
    render_other_deductions_statement,
)
from tenforty.models import OtherDeductionComponent


def render_sch_1_8z_statement(
    name: str, ssn: str, year: int, rows: Sequence[tuple[str, int]],
    output_path: Path,
) -> Path:
    """Render the statement for ``rows`` ((type, amount) pairs) to
    ``output_path``. Deterministic."""
    return render_other_deductions_statement(
        name, ssn, year,
        [OtherDeductionComponent(description=label, amount=amount)
         for label, amount in rows],
        output_path,
        title="Schedule 1 (Form 1040), Line 8z — Other Income Statement",
        subtitle=f"(Other income — Tax Year {year})",
        total_label="Other income total (Schedule 1, line 8z)",
        name_label="Name(s) shown on return",
        id_label="Your social security number")
