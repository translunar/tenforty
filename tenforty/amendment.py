from dataclasses import MISSING, fields
from pathlib import Path

import yaml

from tenforty.models import AmendmentCase


class MissingFiledValueError(ValueError):
    """A required filed-return value is absent from the filed-values file.

    The amendment assembler needs Column A (the as-filed figures) for every
    line it touches. A missing key must fail loudly rather than default to
    0.0: a silently-substituted filed value would produce a wrong Column B
    (C - A) and a fileable-looking-but-incorrect 1040-X. Never substitute.
    """


class OutOfScopeAmendmentError(ValueError):
    """The filed return carries an amount on a 1040-X line tenforty cannot source.

    tenforty's spine does not compute every amount-bearing 1040-X line (EIC,
    Schedule 1-A tips/overtime deductions, nonrefundable credits, other taxes,
    estimated payments). For a simple return those lines are absent/zero and
    the assembler proceeds. But if the FILED return actually carried a nonzero
    value on such a line, emitting a blank/zero Column A would silently drop it
    and produce a wrong Column B — so we refuse loudly instead, naming the line.
    """


# Every AmendmentCase field name; the loader is fail-closed like
# scenario.load_scenario — any key outside this set raises rather than being
# silently dropped (a dropped `explanation:` is how a bad packet ships).
_KNOWN_CASE_KEYS: frozenset[str] = frozenset(f.name for f in fields(AmendmentCase))

# Required = every field with no default (i.e. every field except the sole
# optional `prior_amendment_note`).
_REQUIRED_CASE_KEYS: frozenset[str] = frozenset(
    f.name for f in fields(AmendmentCase) if f.default is MISSING)


def load_amendment_case(path: Path) -> AmendmentCase:
    """Load an amendment case from a YAML file, fail-closed.

    Mirrors ``scenario.load_scenario``: YAML safe-load, top-level mapping
    check, unknown-key diff naming the offending key(s), and a required-key
    check naming any absent field. ``prior_amendment_note`` is the only
    optional field.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Amendment case file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Amendment case YAML must be a mapping at the top level, got "
            f"{type(data).__name__}")

    unknown = set(data) - _KNOWN_CASE_KEYS
    if unknown:
        raise ValueError(
            f"Unknown key(s) in amendment case YAML: {sorted(unknown)}. "
            f"Known keys: {sorted(_KNOWN_CASE_KEYS)}")

    missing = [k for k in sorted(_REQUIRED_CASE_KEYS) if k not in data]
    if missing:
        raise ValueError(
            f"Amendment case missing required key(s): {missing}")

    return AmendmentCase(
        year=int(data["year"]),
        explanation=data["explanation"],
        original_refund_received=float(data["original_refund_received"]),
        original_refund_applied=float(data["original_refund_applied"]),
        prior_amendment_note=data.get("prior_amendment_note"),
        # CA Schedule X analogues: OPTIONAL at load (a federal-only case omits
        # them) — left None when absent, never coerced to 0.0. schedule_x
        # .assemble_ca fails closed if a CA amendment needs them while None.
        ca_original_refund_received=_optional_float(
            data.get("ca_original_refund_received")),
        ca_original_refund_applied=_optional_float(
            data.get("ca_original_refund_applied")),
    )


def _optional_float(value: object) -> float | None:
    """Coerce a present value to float; preserve absence (None) as None."""
    return None if value is None else float(value)


def load_filed_values(
    path: Path, required_keys: tuple[str, ...]
) -> dict[str, float]:
    """Read the flat filed-values YAML dict (as-filed Column A figures).

    Verifies EVERY member of ``required_keys`` is present and raises
    ``MissingFiledValueError`` listing ALL missing keys at once. NEVER
    substitutes or invents a value for a missing key — a defaulted filed
    value would corrupt Column B (C - A).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Filed-values file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Filed-values YAML must be a mapping at the top level, got "
            f"{type(data).__name__}")

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise MissingFiledValueError(
            f"Filed-values file is missing required key(s): {sorted(missing)}. "
            f"Refusing to substitute a default — supply the as-filed figure "
            f"for each in {path}.")

    return {k: float(v) for k, v in data.items()}
