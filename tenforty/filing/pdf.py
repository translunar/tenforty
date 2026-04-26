from collections.abc import Callable, Mapping
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from tenforty.rounding import irs_round


class PdfFiller:
    """Fills PDF form fields with computed tax values."""

    @staticmethod
    def _render_scalar(value: object) -> str:
        """Render a scalar value to its PDF string form.

        Numerics are IRS half-up rounded to whole dollars; everything else
        is str()-coerced. Bools are explicitly rejected — bool-valued fields
        must be registered in the form's checkbox_states map and routed
        through fill() so the per-field XFA appearance state is written.
        Falling through to "Yes"/"Off" here would silently render the cell
        empty in pypdf for any IRS XFA form whose checkboxes use non-/Yes
        on-states."""
        if isinstance(value, bool):
            raise ValueError(
                "PdfFiller._render_scalar does not accept bool values; "
                "bool-valued fields must be registered in the form's "
                "checkbox_states map and routed through fill()."
            )
        if isinstance(value, (int, float)):
            return str(irs_round(value))
        return str(value)

    def fill(
        self,
        template_path: Path,
        output_path: Path,
        field_mapping: dict[str, str],
        values: dict[str, object],
        aggregations: Mapping[str, tuple[str, ...]] | None = None,
        derivations: Mapping[str, Callable[[Mapping[str, object]], object]] | None = None,
        checkbox_states: Mapping[str, str] | None = None,
    ) -> Path:
        """Fill a PDF form template with values.

        Numeric values are coerced to whole dollars using IRS half-up
        rounding before being rendered — the 1040 and its schedules
        display whole-dollar amounts.

        After the 1:1 mapping pass, aggregation cells are filled by summing
        their constituent compute keys (missing/None inputs count as 0, and
        the cell is skipped only when ALL inputs are absent). Derivation cells
        are filled by calling their lambda with the full values dict.

        Args:
            template_path: Path to the fillable PDF template.
            output_path: Path to write the filled PDF.
            field_mapping: Maps our result keys to PDF field names.
            values: Computed results from the engine.
            aggregations: Maps PDF field path → tuple of compute keys to sum.
            derivations: Maps PDF field path → lambda(values) → value.
            checkbox_states: Maps compute key → PDF "on" state string for
                forms whose checkbox fields use non-standard state names
                (e.g. IRS XFA forms use "/1", "/2", "/3" instead of "/Yes").
                When a bool-valued key is listed here, the on-state from this
                dict is written for True; "/Off" is written for False.

        Returns:
            Path to the filled PDF.
        """
        reader = PdfReader(template_path)
        writer = PdfWriter(clone_from=reader)

        pdf_fields: dict[str, str] = {}

        for result_key, pdf_field_name in field_mapping.items():
            if result_key in values and values[result_key] is not None:
                v = values[result_key]
                if checkbox_states and result_key in checkbox_states and isinstance(v, bool):
                    pdf_fields[pdf_field_name] = checkbox_states[result_key] if v else "/Off"
                else:
                    pdf_fields[pdf_field_name] = self._render_scalar(v)

        if aggregations:
            for pdf_field, compute_keys in aggregations.items():
                present_keys = [k for k in compute_keys if k in values and values[k] is not None]
                # Skip when every input is missing — nothing to write.
                if not present_keys:
                    continue
                total = sum(values[k] for k in compute_keys if k in values and values[k] is not None)
                pdf_fields[pdf_field] = self._render_scalar(total)

        if derivations:
            for pdf_field, lambda_fn in derivations.items():
                try:
                    result = lambda_fn(values)
                except KeyError:
                    # A required input key is absent from values; skip this cell
                    # rather than writing a broken or partial value.
                    continue
                if result is not None:
                    pdf_fields[pdf_field] = self._render_scalar(result)

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
