from pathlib import Path

from tenforty.engine import SpreadsheetEngine
from tenforty.filing.balance_due import compute_balance_due
from tenforty.filing.pdf import PdfFiller
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_4868 import Pdf4868
from tenforty.models import Scenario
from tenforty.result_translator import ResultTranslator
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tenforty.translations.f4868_pdf import F4868_PDF_SPEC

_PDFS_ROOT = Path(__file__).parent.parent / "pdfs"


class ReturnOrchestrator:
    """Coordinates computation across forms in dependency order."""

    def __init__(self, spreadsheets_dir: Path, work_dir: Path) -> None:
        self.spreadsheets_dir = spreadsheets_dir
        self.work_dir = work_dir
        self.engine = SpreadsheetEngine()

    def compute_federal(self, scenario: Scenario) -> dict[str, object]:
        """Compute the federal return (1040 + all schedules)."""
        year = scenario.config.year
        spreadsheet = self.spreadsheets_dir / "federal" / str(year) / "1040.xlsx"

        if not spreadsheet.exists():
            raise FileNotFoundError(
                f"Federal spreadsheet not found: {spreadsheet}"
            )

        flat_inputs = flatten_scenario(scenario)

        return self.engine.compute(
            spreadsheet_path=spreadsheet,
            mapping=F1040,
            year=year,
            inputs=flat_inputs,
            work_dir=self.work_dir / "federal",
        )

    def emit_pdfs(
        self,
        scenario: Scenario,
        results: dict[str, object],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Fill both 1040 and 4868 PDFs and write them to output_dir.

        Returns a dict mapping form name ('1040', '4868') to the filled PDF path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        filler = PdfFiller()

        f1040_template = _PDFS_ROOT / "federal" / str(year) / "f1040.pdf"
        translated_1040 = ResultTranslator(F1040_PDF_SPEC).translate(results, scenario)
        out_1040 = output_dir / f"f1040_{year}.pdf"
        filler.fill(
            template_path=f1040_template,
            output_path=out_1040,
            field_mapping=Pdf1040.get_mapping(year),
            values=translated_1040,
        )

        f4868_template = _PDFS_ROOT / "federal" / str(year) / "f4868.pdf"
        translated_4868 = ResultTranslator(F4868_PDF_SPEC).translate(results, scenario)
        balance_due = compute_balance_due(
            results.get("total_tax", 0),
            results.get("total_payments", 0),
        )
        translated_4868["balance_due"] = balance_due
        translated_4868["amount_paying_with_extension"] = 0
        translated_4868["voucher_amount"] = balance_due

        out_4868 = output_dir / f"f4868_{year}.pdf"
        filler.fill(
            template_path=f4868_template,
            output_path=out_4868,
            field_mapping=Pdf4868.get_mapping(year),
            values=translated_4868,
        )

        return {"1040": out_1040, "4868": out_4868}
