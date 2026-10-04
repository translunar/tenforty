from collections.abc import Callable, Mapping
from pathlib import Path

import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    TextStringObject,
)

from tenforty.rounding import irs_round

# Operators that put ink on the page. A button on-state appearance stream
# containing none of these (and no non-empty text-show) draws nothing.
_PAINT_OPS = re.compile(rb"(?<![A-Za-z0-9_])(S|s|f|F|f\*|B|b|B\*|b\*|Do|sh|BI)(?![A-Za-z0-9_*])")
_NONEMPTY_TEXT_SHOW = re.compile(rb"\(\s*[^)\s][^)]*\)\s*(Tj|'|\")|\[[^\]]*\(\s*[^)\s][^\]]*\]\s*TJ")


def _stream_paints(data: bytes) -> bool:
    """True iff an appearance-stream content string would put ink on the page."""
    return bool(_PAINT_OPS.search(data) or _NONEMPTY_TEXT_SHOW.search(data))


def _field_type(widget) -> str | None:
    node = widget
    while node is not None:
        if "/FT" in node:
            return node["/FT"]
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def _x_mark_stream(writer: PdfWriter, rect) -> DecodedStreamObject:
    """A Form XObject drawing an X across a widget-sized box (widget space)."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    w, h = abs(x1 - x0), abs(y1 - y0)
    m = max(1.5, min(w, h) * 0.2)
    content = (
        f"q 0 0 0 RG {max(1.0, min(w, h) * 0.1):.2f} w "
        f"{m:.2f} {m:.2f} m {w - m:.2f} {h - m:.2f} l S "
        f"{m:.2f} {h - m:.2f} m {w - m:.2f} {m:.2f} l S Q"
    ).encode()
    stream = DecodedStreamObject()
    stream.set_data(content)
    stream.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([FloatObject(0), FloatObject(0),
                                          FloatObject(w), FloatObject(h)]),
    })
    return stream


def ensure_button_marks_visible(writer: PdfWriter) -> None:
    """Make every checked checkbox / radio widget render, in every viewer.

    Two independent defects leave a checked box blank on paper:

    1. pypdf writes a radio group's parent ``/V`` as a TEXT string
       (``(/1 . Single.)``) instead of the NAME the spec requires
       (``/1#20.#20Single.``); poppler then draws no mark although each kid's
       ``/AS`` is right. Coerced to a name here.
    2. A template whose on-state appearance stream paints nothing (empty
       content, or a text-show of an empty string) or is absent draws nothing
       even when ``/AS`` selects it. An X is drawn into the widget rect so
       the mark survives printing. Streams that already paint (the IRS
       templates, the FTB check glyph) are left untouched.
    """
    for page in writer.pages:
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget" or _field_type(w) != "/Btn":
                continue
            for holder in (w, w["/Parent"].get_object() if "/Parent" in w else None):
                if holder is not None and isinstance(holder.get("/V"), TextStringObject):
                    text = str(holder["/V"])
                    if text.startswith("/"):
                        holder[NameObject("/V")] = NameObject(text)
            state = w.get("/AS")
            if state is None or state == "/Off":
                continue
            ap = w.get("/AP")
            normal = ap.get("/N") if ap is not None else None
            existing = normal.get(state) if normal is not None else None
            if existing is not None and _stream_paints(existing.get_object().get_data()):
                continue
            mark = writer._add_object(_x_mark_stream(writer, w["/Rect"]))
            if ap is None:
                w[NameObject("/AP")] = ap = DictionaryObject()
            if normal is None:
                ap[NameObject("/N")] = normal = DictionaryObject()
            normal[NameObject(str(state))] = mark


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

    @staticmethod
    def resolve_fields(
        field_mapping: dict[str, str],
        values: dict[str, object],
        aggregations: Mapping[str, tuple[str, ...]] | None = None,
        derivations: Mapping[str, Callable[[Mapping[str, object]], object]] | None = None,
        checkbox_states: Mapping[str, str] | None = None,
        field_formats: Mapping[str, str | Callable[[float], str]] | None = None,
    ) -> dict[str, str]:
        """Resolve a flat ``field_mapping`` (+ optional aggregations, derivations,
        checkbox_states) into the ``{pdf_field_path: rendered_str}`` dict that
        ``fill`` writes to the template.

        Extracted from ``fill`` so callers can obtain a form's EMIT PAYLOAD
        (the exact field→value dict that would be rendered) WITHOUT touching a
        PDF — the changed-forms selector compares these payloads across the
        as-filed and corrected runs. ``fill`` delegates to this method, so the
        payload is by construction identical to what would be rendered.

        ``field_formats`` maps a COMPUTE KEY (in ``field_mapping``) to a Python
        format spec (e.g. ``".4f"``) — or a ``float -> str`` callable such as
        ``mappings.registry.trim_decimal`` — that replaces the whole-dollar default for
        that one numeric field — for rates such as Form 8962 line 7 (0.0850)
        that would otherwise round to "0". Applies only to the 1:1 pass, only
        to non-bool numerics; every field not named keeps the whole-dollar
        default.
        """
        pdf_fields: dict[str, str] = {}

        for result_key, pdf_field_name in field_mapping.items():
            if result_key in values and values[result_key] is not None:
                v = values[result_key]
                if checkbox_states and result_key in checkbox_states and isinstance(v, bool):
                    pdf_fields[pdf_field_name] = checkbox_states[result_key] if v else "/Off"
                elif (
                    field_formats and result_key in field_formats
                    and isinstance(v, (int, float)) and not isinstance(v, bool)
                ):
                    fmt = field_formats[result_key]
                    pdf_fields[pdf_field_name] = (
                        fmt(v) if callable(fmt) else format(v, fmt)
                    )
                else:
                    pdf_fields[pdf_field_name] = PdfFiller._render_scalar(v)

        if aggregations:
            for pdf_field, compute_keys in aggregations.items():
                present_keys = [k for k in compute_keys if k in values and values[k] is not None]
                # Skip when every input is missing — nothing to write.
                if not present_keys:
                    continue
                total = sum(values[k] for k in compute_keys if k in values and values[k] is not None)
                pdf_fields[pdf_field] = PdfFiller._render_scalar(total)

        if derivations:
            for pdf_field, lambda_fn in derivations.items():
                try:
                    result = lambda_fn(values)
                except KeyError:
                    # A required input key is absent from values; skip this cell
                    # rather than writing a broken or partial value.
                    continue
                if result is not None:
                    pdf_fields[pdf_field] = PdfFiller._render_scalar(result)

        return pdf_fields

    def fill(
        self,
        template_path: Path,
        output_path: Path,
        field_mapping: dict[str, str],
        values: dict[str, object],
        aggregations: Mapping[str, tuple[str, ...]] | None = None,
        derivations: Mapping[str, Callable[[Mapping[str, object]], object]] | None = None,
        checkbox_states: Mapping[str, str] | None = None,
        field_formats: Mapping[str, str | Callable[[float], str]] | None = None,
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

            field_formats: Maps compute key → Python format spec overriding the
                whole-dollar default for that numeric field (see
                ``resolve_fields``).

        Returns:
            Path to the filled PDF.
        """
        reader = PdfReader(template_path)
        writer = PdfWriter(clone_from=reader)

        pdf_fields = self.resolve_fields(
            field_mapping, values,
            aggregations=aggregations,
            derivations=derivations,
            checkbox_states=checkbox_states,
            field_formats=field_formats,
        )

        for page in writer.pages:
            writer.update_page_form_field_values(page, pdf_fields)
        ensure_button_marks_visible(writer)

        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path

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
                flat[pdf_field] = PdfFiller._render_scalar(v)

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
                        flat[field] = PdfFiller._render_scalar(v)
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
        ensure_button_marks_visible(writer)
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path
