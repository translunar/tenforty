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

    @staticmethod
    def _render(value) -> str:
        """Stringify a scalar value for PDF field writing (mirrors existing fill logic)."""
        if isinstance(value, bool):
            return "Yes" if value else "Off"
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)

    @staticmethod
    def _expand_repeaters(mapping: dict, values: dict) -> dict[str, str]:
        """Flatten a {scalars, repeaters} mapping + values into a flat field dict.

        Scalar fields are copied straight across (skipping None values). Each
        repeater section iterates `values[section]`, substituting `{i}`
        (1-indexed) into the PDF field names from the template. When
        `len(list) > max_slots` and `overflow == "raise"`, raises
        OverflowError; other overflow policies are reserved for future use.
        """
        flat: dict[str, str] = {}
        for result_key, pdf_field in mapping.get("scalars", {}).items():
            v = values.get(result_key)
            if v is not None:
                flat[pdf_field] = PdfFiller._render(v)

        for section_name, section in mapping.get("repeaters", {}).items():
            rows = values.get(section_name) or []
            max_slots = section["max_slots"]
            policy = section.get("overflow", "raise")
            if len(rows) > max_slots:
                if policy == "raise":
                    raise OverflowError(
                        f"Repeater '{section_name}' has {len(rows)} rows; "
                        f"PDF supports {max_slots} per page. "
                        "Multi-page emission is deferred (see #11 non-goals)."
                    )
                raise NotImplementedError(
                    f"Repeater overflow policy {policy!r} not yet implemented; "
                    "only 'raise' is supported in v1."
                )
            for i, row in enumerate(rows, start=1):
                for inner_key, template in section["template"].items():
                    v = row.get(inner_key)
                    if v is not None:
                        field = template.replace("{i}", str(i))
                        flat[field] = PdfFiller._render(v)
        return flat

    def fill_with_repeaters(
        self,
        template_path,
        output_path,
        mapping: dict,
        values: dict,
    ):
        """Fill a PDF with a {scalars, repeaters} mapping shape."""
        reader = PdfReader(str(template_path))
        writer = PdfWriter(clone_from=reader)
        pdf_fields = self._expand_repeaters(mapping, values)
        for page in writer.pages:
            writer.update_page_form_field_values(page, pdf_fields)
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path
