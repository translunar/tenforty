"""Always-zero declared lines ([R-ZL-1] option 2; Juno's plain-allowlist
ruling, 2026-10-21).

A declared value-only line (``single_state == "value"``: it always prints a
number, zero included) whose computed value is 0 in EVERY native battery
record, across every year, is a finding: either the producer hard-codes 0
(an unimplemented feature that may print a silently wrong 0), or the
batteries never drive the line, so its nonzero path is unverified.

A finding is cleared only by an entry in one of two maps:

- ``ATTESTED_ZERO``: the line is 0 for every return tenforty accepts, and
  the reason says why in one sentence. A plain allowlist by ruling: no
  staleness test, rot risk accepted.
- ``PENDING``: the line is known to be always-zero because of an open
  question or a fail-open defect. It is NOT attested: the reason names the
  blocking tag (a ruling still to come, or the defect lane that fixes it),
  so nothing is quietly attested and each line names its blocker.

Lines are keyed ``("<jurisdiction>/<form>", "<line>")`` across all years.
"""
import numbers
from collections.abc import Iterable, Mapping

from tenforty.declarations import registry
from tenforty.declarations.model import expand
from tenforty.verification.record import RecordedForm

LineId = tuple[str, str]

_ELECTIVE = ("elective benefit, no input modeled; omission can only "
             "overstate tax, never understate [R-ZL-2]")
_BOX_C_F = ("box C/F unrepresentable by construction (f8949 BOX_KEYS maps "
            "every Form 1099-B lot to box A, B, D or E) [R-ZL-4]")

ATTESTED_ZERO: dict[LineId, str] = {
    ("federal/sch_1", "11"): _ELECTIVE,   # educator expenses
    ("federal/sch_1", "20"): _ELECTIVE,   # IRA deduction
    ("federal/sch_1", "21"): _ELECTIVE,   # student loan interest
    ("federal/sch_b", "3"): _ELECTIVE,    # Form 8815 savings-bond exclusion
    ("federal/sch_d", "3"): _BOX_C_F,
    ("federal/sch_d", "3(e)"): _BOX_C_F,
    ("federal/sch_d", "3(h)"): _BOX_C_F,
    ("federal/sch_d", "10"): _BOX_C_F,
    ("federal/sch_d", "10(e)"): _BOX_C_F,
    ("federal/sch_d", "10(h)"): _BOX_C_F,
}

_Q_ZL1 = ("PENDING Q-ZL1 (Juno): mandatory-if-present item with no input; "
          "hard-coded 0 and nothing refuses")
_D1 = ("PENDING D1: K-1 section 1231 gain is dropped under "
       "acknowledges_no_section_1231_gain; hard refusal lane [R-ZL-3]")
_D2 = ("PENDING D2: a flagged lot prints this line but the tax ignores the "
       "28%/25% rates; hard refusal lane, no battery row until fixed "
       "[R-ZL-3]")

PENDING: dict[LineId, str] = {
    ("federal/8959", "2"): _Q_ZL1,    # unreported tips (Form 4137)
    ("federal/8959", "3"): _Q_ZL1,    # Form 8919 wages
    ("federal/8959", "14"): _Q_ZL1,   # RRTA compensation
    ("federal/8959", "16"): _Q_ZL1,   # derived from line 14
    ("federal/8959", "17"): _Q_ZL1,   # derived from line 14
    ("federal/8959", "23"): _Q_ZL1,   # RRTA Additional Medicare withholding
    ("federal/sch_1", "6"): _Q_ZL1,   # farm income
    ("federal/sch_1", "13"): _Q_ZL1,  # HSA (Form 8889 can create tax) [R-ZL-2]
    ("federal/sch_1", "4"): _D1,
    ("federal/sch_d", "18"): _D2,
    ("federal/sch_d", "19"): _D2,
}


def _is_number(v) -> bool:
    return isinstance(v, numbers.Number) and not isinstance(v, bool)


def always_zero_lines(records: Iterable[tuple[str, RecordedForm]]
                      ) -> dict[LineId, int]:
    """Declared value-only lines that are 0 in every record producing them,
    with how many records produced each. A line with any non-numeric value
    is not judged here (not a number line); a line no record produces is not
    always-zero (it has no observations — coverage owns that)."""
    decls = {(f, k): registry.for_form(f, k)
             for f, k in registry.declared_forms()}
    seen: dict[LineId, list] = {}
    for _scenario, rec in records:
        decl = decls.get((rec.form, rec.key))
        if decl is None:
            continue
        for ln in expand(decl, rec.values):
            if (ln.scope == "WORKBOOK" or not ln.key
                    or ln.selects is not None or ln.single_state != "value"):
                continue
            value = rec.values.get(ln.key)
            if value is not None:
                seen.setdefault(("/".join(decl.form), ln.line), []).append(
                    value)
    return {line: len(vals) for line, vals in seen.items()
            if all(_is_number(v) for v in vals)
            and all(v == 0 for v in vals)}


def findings(records: Iterable[tuple[str, RecordedForm]],
             attested: Mapping[LineId, str] = ATTESTED_ZERO,
             pending: Mapping[LineId, str] = PENDING) -> list[str]:
    """One message per always-zero line in neither map."""
    return [
        f"{form} line {line}: computes 0 in all {n} battery records. "
        "Drive it nonzero with a battery row, or add an ATTESTED_ZERO entry "
        "(verified one-sentence reason) or a PENDING entry naming its "
        "blocker."
        for (form, line), n in sorted(always_zero_lines(records).items())
        if (form, line) not in attested and (form, line) not in pending]
