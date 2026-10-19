"""The single fill chokepoint (spec §7).

Every PDF form fill in tenforty goes through ``fill``. It runs the runtime
gate hook, calls ``PdfFiller``, and records exactly what it filled in the
emit's ``EmitRecorder``. ``SingleChokepointTests`` fails on any
``PdfFiller.fill`` / ``fill_with_repeaters`` call anywhere else.

A ``FillSpec`` is one assembly of fill arguments. ``fill_spec_for`` builds a
mapping class's CANONICAL spec: its mapping exactly as ``get_mapping``
returns it, and every fill getter it defines, verbatim. A site then derives
the spec it actually fills with from that, through two named transforms:

- ``FillSpec.extend(**parts)``: additive, scenario-specific cells (1120-S
  items G/H, accounting method, amended/final marks, Schedule E's 1099
  questions, ...), merged exactly as the site's dict-merges did. For a
  repeater spec, ``mapping=`` merges into the mapping's scalars.
- ``FillSpec.flattened()``: a ``{scalars, repeaters}`` mapping filled as one
  flat mapping. It covers the two shapes in use: empty repeaters (8959,
  8962, 8995, 8582: the scalars) and groups of pre-baked row dicts (8949:
  scalars, then each group's rows, in order). It refuses a key collision
  between the merged parts, and any other repeater shape.

The recorded spec is the FINAL spec ``fill`` received.
"""
import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from tenforty.filing.pdf import PdfFiller
from tenforty.verification import gate
from tenforty.verification.record import EmitRecorder, RecordedForm

# FillSpec part -> the mapping-class getter that supplies it.
FILL_GETTERS: dict[str, str] = {
    "mapping": "get_mapping",
    "aggregations": "get_aggregations",
    "derivations": "get_derivations",
    "checkbox_states": "get_checkbox_states",
    "field_formats": "get_field_formats",
    "blank_when_zero": "get_blank_when_zero",
}

# Mapping-class getters that are NOT fill arguments: each supplies cells a
# site adds through FillSpec.extend for one scenario's answers, or names
# what is deliberately unprinted. fill_spec_for recognises and skips them;
# any getter in neither table raises.
KNOWN_NON_FILL_GETTERS: dict[str, str] = {
    "get_suppressed": "compute keys deliberately not printed; not a fill argument",
    "get_presentation_mapping": "1040-X / Schedule X presentation cells the site merges into the mapping via extend",
    "get_entity_header_fields": "1120-S page-1 identity cells the site merges from the SCorpReturn via extend",
    "get_amended_mark": "amended-return box added via extend only when the return is flagged amended",
    "get_final_mark": "final K-1 box added via extend only for a shareholder flagged final",
    "get_item_g_cells": "1120-S item G Yes/No cells: the chosen box only, via extend",
    "get_item_h_cells": "1120-S item H check-if boxes: only True items, via extend",
    "get_discuss_cells": "preparer-discussion Yes/No cells: the chosen box only, via extend",
    "get_schedule_q_cells": "100S Schedule Q answer cells: the chosen box per stated answer, via extend",
    "get_accounting_method_cells": "100S question L accounting-method cells: the stated method's box, via extend",
    "get_entity_type_cells": "100S K-1 entity-type radio: the stated type's state, via extend",
    "get_resident_cells": "100S K-1 resident radio: the stated answer's state, via extend",
    "get_1099_question_cells": "Schedule E lines A/B: the stated answer's box per question, via extend",
    "get_line_27_cells": "Schedule E line 27 'No' box when Part II is used, via extend",
    "get_basis_computation_cells": "Schedule E line 28(e) basis box for flagged rows, via extend",
}

_EXTENDABLE = frozenset(FILL_GETTERS)


@dataclasses.dataclass(frozen=True)
class FillSpec:
    kind: Literal["flat", "repeater"]
    mapping: Mapping
    aggregations: Mapping = dataclasses.field(default_factory=dict)
    derivations: Mapping = dataclasses.field(default_factory=dict)
    checkbox_states: Mapping = dataclasses.field(default_factory=dict)
    field_formats: Mapping = dataclasses.field(default_factory=dict)
    blank_when_zero: frozenset = frozenset()

    def extend(self, **parts: Mapping) -> "FillSpec":
        """Additive site cells, merged as ``{**existing, **added}`` per part;
        ``mapping=`` merges into the scalars of a repeater spec."""
        unknown = set(parts) - _EXTENDABLE
        if unknown:
            raise TypeError(f"FillSpec.extend: unknown part(s) {sorted(unknown)}")
        changes: dict = {}
        for part, added in parts.items():
            current = getattr(self, part)
            if part == "blank_when_zero":
                changes[part] = frozenset(current) | frozenset(added)
            elif part == "mapping" and self.kind == "repeater":
                changes[part] = {**current,
                                 "scalars": {**current["scalars"], **added}}
            else:
                changes[part] = {**current, **added}
        return dataclasses.replace(self, **changes)

    def flattened(self) -> "FillSpec":
        """This repeater spec as one flat mapping (module docstring)."""
        if self.kind != "repeater":
            raise ValueError("FillSpec.flattened: only a repeater spec flattens.")
        flat: dict = {}

        def merge(part: Mapping, where: str) -> None:
            for key, path in part.items():
                if key in flat:
                    raise ValueError(
                        f"FillSpec.flattened: key {key!r} appears twice "
                        f"(again in {where}); refusing to overwrite.")
                flat[key] = path

        merge(self.mapping.get("scalars", {}), "scalars")
        for group, rows in self.mapping.get("repeaters", {}).items():
            if not isinstance(rows, list) or not all(
                    isinstance(r, Mapping) for r in rows):
                raise ValueError(
                    f"FillSpec.flattened: repeater {group!r} is a template "
                    "repeater, not pre-baked rows; fill it as a repeater.")
            for row in rows:
                merge(row, f"repeater {group!r}")
        return dataclasses.replace(self, kind="flat", mapping=flat)


def fill_spec_for(mapping_cls: type, key: int | str) -> FillSpec:
    """The class's canonical spec for one year or revision."""
    getters = {n for n in dir(mapping_cls) if n.startswith("get_")}
    unknown = getters - set(FILL_GETTERS.values()) - set(KNOWN_NON_FILL_GETTERS)
    if unknown:
        raise ValueError(
            f"fill_spec_for({mapping_cls.__name__}): unrecognised getter(s) "
            f"{sorted(unknown)}; classify each in FILL_GETTERS or "
            "KNOWN_NON_FILL_GETTERS (tenforty/verification/fill.py).")
    parts = {part: getattr(mapping_cls, getter)(key)
             for part, getter in FILL_GETTERS.items() if getter in getters}
    mapping = parts.pop("mapping")
    kind = ("repeater" if isinstance(mapping, Mapping) and "scalars" in mapping
            else "flat")
    if "blank_when_zero" in parts:
        parts["blank_when_zero"] = frozenset(parts["blank_when_zero"])
    return FillSpec(kind=kind, mapping=mapping, **parts)


def fill(form: tuple[str, str], key: int | str, spec: FillSpec,
         template: Path, out: Path, values: Mapping,
         recorder: EmitRecorder, *, copy_id: str | None = None,
         filler: PdfFiller | None = None) -> Path:
    """Fill ``template`` into ``out`` from ``values`` under ``spec``: the
    gate hook first, then PdfFiller, then the record (the exact ``values``
    object and the final ``spec``)."""
    gate.check(form, key, spec, values)
    filler = filler or PdfFiller()
    if spec.kind == "flat":
        filler.fill(
            template_path=template, output_path=out,
            field_mapping=spec.mapping, values=values,
            aggregations=spec.aggregations or None,
            derivations=spec.derivations or None,
            checkbox_states=spec.checkbox_states or None,
            field_formats=spec.field_formats or None,
            blank_when_zero=spec.blank_when_zero or None,
        )
    else:
        extras = [p for p in ("aggregations", "derivations", "checkbox_states",
                              "field_formats", "blank_when_zero")
                  if getattr(spec, p)]
        if extras:
            raise ValueError(
                f"fill({form}, {key}): a repeater fill takes no {extras}; "
                "flatten the spec or drop them.")
        filler.fill_with_repeaters(
            template_path=template, output_path=out,
            mapping=spec.mapping, values=values)
    recorder.add(RecordedForm(form=form, key=key, copy_id=copy_id,
                              values=values, spec=spec, pdf_path=Path(out),
                              template=Path(template)))
    return Path(out)
