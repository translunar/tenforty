"""Amendment-case + filed-values loading, fail-closed.

FILED-VALUES FILE CONVENTION (RULING 2 + 3)
-------------------------------------------
A filed-values file is the amendment's Column A — the return AS ORIGINALLY
FILED (or as last adjusted). For the 1040-X assembler to reproduce Column A
faithfully it must be able to see EVERY amount the filed return carried, so the
file MUST DECOMPOSE its figures against tenforty's model rather than roll them
into one line:

  * ``total_tax`` is the MODELED income tax ONLY — the amount tenforty's spine
    computes (tax on taxable income, incl. QDCGT + Additional Medicare). It is
    NOT a catch-all "total tax from the 1040". Any tax component tenforty does
    not model must NOT be folded into ``total_tax``; it goes under its own
    guard key below.

  * MODELED Schedule 2 components ride their OWN filed keys, NOT a guard key:

        f8962_repayment   — Sch 2 Part I,  line 2 (excess-APTC repayment)
                             -> 1040-X line 6  ("Tax")
        f8959_tax_total   — Sch 2 Part II, line 11 (Additional Medicare Tax)
                             -> 1040-X line 10 ("Other taxes")

    Both are OPTIONAL filed-file keys (``.get(..., 0.0)`` in the assembler,
    never REQUIRED_FILED_KEYS members) — omit them (or write 0) when the
    filed return carried nothing on that component.

  * Any STILL-UNMODELED filed component goes under its matching out-of-scope
    GUARD KEY. tenforty does not source these 1040-X lines, so each has a
    reserved filed-file key (see ``forms.f1040x._OUT_OF_SCOPE_FILED_KEYS``):

        schedule_1a_deduction   — line 4b (Schedule 1-A tips/overtime/car-loan/seniors, TY2025)
        nonrefundable_credits   — line 7  (nonrefundable credits)
        other_taxes             — line 10 (other taxes NOT already covered by
                                   f8959_tax_total, e.g. NIIT, SE tax)
        earned_income_credit    — line 14 (earned income credit)

    ONLY still-unmodeled components belong under a guard key — a modeled
    component (f8962_repayment, f8959_tax_total) must ride its own key above,
    never be folded into ``other_taxes`` or another guard.

  * ``estimated_tax_payments`` is now SOURCED, not guarded: the federal spine
    emits it verbatim (1040 line 26), so a filer who paid estimated tax
    supplies this key in the filed-values file for 1040-X line 13 (estimated
    tax payments). OPTIONAL — ``.get(..., 0.0)`` in the assembler, never a
    REQUIRED_FILED_KEYS member; absent means the filed return paid no
    estimated tax.

WHY THIS IS LOAD-BEARING: an unmodeled component hidden in a COMMENT (or
silently merged into ``total_tax``) neither fires the assembler's out-of-scope
guard NOR reaches Column A/C — so it would silently vanish from the amendment
and ship a fileable-looking-but-wrong 1040-X. Keyed under its guard name, a
nonzero unmodeled component instead makes ``forms.f1040x.assemble`` REFUSE
cleanly (OutOfScopeAmendmentError naming the line), which is the correct
outcome: tenforty cannot amend a return whose filed figures it cannot
reconstruct. Assert 0 (or omit) a guard key only when the filed return truly
carried nothing on that line.
"""
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
