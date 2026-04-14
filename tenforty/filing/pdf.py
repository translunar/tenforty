from pathlib import Path

from pypdf import PdfReader, PdfWriter

from tenforty.rounding import irs_round


class PdfFiller:
    """Fills PDF form fields with computed tax values."""

    def fill(
        self,
        template_path: Path,
        output_path: Path,
        field_mapping: dict[str, str],
        values: dict[str, object],
    ) -> Path:
        """Fill a PDF form template with values.

        Numeric values are coerced to whole dollars using IRS half-up
        rounding before being rendered — the 1040 and its schedules
        display whole-dollar amounts.

        Args:
            template_path: Path to the fillable PDF template.
            output_path: Path to write the filled PDF.
            field_mapping: Maps our result keys to PDF field names.
            values: Computed results from the engine.

        Returns:
            Path to the filled PDF.
        """
        reader = PdfReader(template_path)
        writer = PdfWriter(clone_from=reader)

        pdf_fields: dict[str, str] = {}
        for result_key, pdf_field_name in field_mapping.items():
            if result_key in values and values[result_key] is not None:
                value = values[result_key]
                if isinstance(value, bool):
                    rendered = str(value)
                elif isinstance(value, (int, float)):
                    rendered = str(irs_round(value))
                else:
                    rendered = str(value)
                pdf_fields[pdf_field_name] = rendered

        for page in writer.pages:
            writer.update_page_form_field_values(page, pdf_fields)

        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path
