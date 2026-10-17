"""PDF field mapping for FTB 3532 (Head of Household Filing Status
Schedule), TY2021-TY2025.

FTB 3532 is a one-page questionnaire with no arithmetic. Every answered line
is a direct presentation of a ``ftb3532_*`` compute key; the keys are fixed by
the FTB 3532 plan's mapping-lane interface.

Field identity rule. Every field path below comes from THAT year's own
template dump (name, /FT, /Rect, /MaxLen, /TU, /AP /N states), not from a
neighbouring year, field numbering or adjacency. Each year gets its own
explicit dict; ``inherit_pdf_fields`` is deliberately not used, because the
field tree changes shape twice across the span (spec
docs/plans/2026-10-16-ftb3532-spec.md section 3.5):

- 2023 -> 2024: every field name gains a ``3532_`` prefix (``1001`` ->
  ``3532_1001``).
- 2024 -> 2025: Part I and Part II stop being independent checkboxes
  (``3532_1003 CB``..``3532_1008 CB`` and ``3532_1013 CB``..``3532_1017 CB``,
  each on ``/Yes``) and become ONE radio group each (``3532_1003 RB`` states
  ``/0``..``/5``, ``3532_1013 RB`` states ``/0``..``/4``).

Every year: lines 3a and 3b are radio groups (``1022 RB`` / ``1023 RB``, with
the year's prefix) whose state ``/0`` widget sits immediately left of the
printed "Yes" and ``/1`` immediately left of "No" (bound by geometry, pinned in
tests/test_pdf_ftb3532_mapping.py ``Ftb3532OptionGeometryTests``). The 2025
Part I / Part II state tables were likewise bound by placing each on-state
widget on its printed ``1a``..``1f`` / ``2a``..``2e`` label row, not by state
order.

Construction:
- ``get_mapping`` - the twelve text cells (header, 1f periods, line 3, lines
  4 and 5).
- ``get_derivations`` - every button cell. 2021-2024 checkboxes: one
  derivation per box, ``/Yes`` for the selected value and ``/Off`` for every
  other box, so no stale default survives. Radios (2025 Part I/II; 3a/3b all
  years): one derivation per group returning the state token. An unknown
  enum value raises ``ValueError`` (``PdfFiller.resolve_fields`` only swallows
  ``KeyError``, so a bad value cannot silently leave a part blank). An absent
  key raises ``KeyError`` and the cell is skipped; 3a/3b return ``None`` when
  their key is absent (the under-19 "go to line 4" branch).
- ``required_pdf_fields(values, year)`` - the branch-aware set of PDF fields
  the resolved payload must contain, for the emit gate's completeness check.
"""

import datetime
from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping

# Answered on every branch: header, line 3, lines 4 and 5.
REQUIRED_TEXT_KEYS: frozenset[str] = frozenset({
    "ftb3532_header_name",
    "ftb3532_header_ssn",
    "ftb3532_qp_first_name",
    "ftb3532_qp_last_name",
    "ftb3532_qp_ssn",
    "ftb3532_qp_dob",
    "ftb3532_line_4_gross_income",
    "ftb3532_line_5_days",
})

_MARITAL_KEY = "ftb3532_marital_status"
_RELATIONSHIP_KEY = "ftb3532_relationship"
_LINE_3A_KEY = "ftb3532_line_3a"
_LINE_3B_KEY = "ftb3532_line_3b"

# Part I enum values (HohMaritalStatus), in printed line order 1a..1f.
_MARITAL_VALUES: tuple[str, ...] = (
    "unmarried",                            # 1a
    "surviving_spouse",                     # 1b
    "marriage_annulled",                    # 1c
    "divorced_or_legally_separated",        # 1d
    "married_lived_apart_all_year",         # 1e
    "married_lived_together_part_of_year",  # 1f
)
# Part II enum values (HohRelationship), in printed line order 2a..2e.
_RELATIONSHIP_VALUES: tuple[str, ...] = (
    "child_or_stepchild",                   # 2a
    "grandchild_sibling_niece_or_nephew",   # 2b
    "eligible_foster_child",                # 2c
    "parent_or_stepparent",                 # 2d
    "other_relative",                       # 2e
)
_LIVED_TOGETHER = "married_lived_together_part_of_year"

# The form's line 3: "If your qualifying person is age 19 or older in
# <year>, go to line 3a. If not, go to line 4."
_LINE_3A_AGE = 19


def _member(values: Mapping[str, object], key: str, members: tuple[str, ...]) -> str:
    value = values[key]  # KeyError when absent -> resolve_fields skips the cell
    text = getattr(value, "value", value)
    if text not in members:
        raise ValueError(
            f"FTB 3532: {key}={value!r} is not one of {', '.join(members)}; "
            "the form has no box for it, so tenforty will not print this part "
            "blank. Correct the head_of_household block.")
    return text


def _checkbox(key: str, members: tuple[str, ...], selected: str):
    def derive(values: Mapping[str, object]) -> str:
        return "/Yes" if _member(values, key, members) == selected else "/Off"
    return derive


def _radio(key: str, members: tuple[str, ...], states: Mapping[str, str]):
    def derive(values: Mapping[str, object]) -> str:
        return states[_member(values, key, members)]
    return derive


def _yes_no(key: str, yes_state: str, no_state: str):
    def derive(values: Mapping[str, object]) -> str | None:
        if values.get(key) is None:
            return None  # under 19: the form says "go to line 4"
        answer = values[key]
        if not isinstance(answer, bool):
            raise ValueError(
                f"FTB 3532: {key} must be True or False, got {answer!r}.")
        return yes_state if answer else no_state
    return derive


# ---------------------------------------------------------------------------
# TY2021 - pdfs/california/2021/ftb3532.pdf (form code 8481213).
# Unprefixed names; Part I/II independent checkboxes on /Yes. Header and
# line 3 SSN MaxLen 9; line 5 MaxLen 4. Line 1b reads "Widow/widower".
# ---------------------------------------------------------------------------
_MAPPING_2021: dict[str, str] = {
    "ftb3532_header_name": "1001",          # /TU "Name or names as shown on tax return"
    "ftb3532_header_ssn": "1002",           # /TU "Social Security Number or ITIN..."
    "ftb3532_period_1_from": "1009",        # /TU "List the beginning FROM date..."
    "ftb3532_period_1_to": "1010",          # /TU "List the ending TO date..."
    "ftb3532_period_2_from": "1011",        # /TU "Second beginning date..."
    "ftb3532_period_2_to": "1012",          # /TU "Second ending date..."
    "ftb3532_qp_first_name": "1018",        # /TU "Line 3. First Name"
    "ftb3532_qp_last_name": "1019",         # /TU "Line 3  Last Name"
    "ftb3532_qp_ssn": "1020",               # /TU "Line 3   Social Security Number"
    "ftb3532_qp_dob": "1021",               # /TU "Line 3  Date of birth..."
    "ftb3532_line_4_gross_income": "1024",  # /TU "Line 4   ...gross income..."
    "ftb3532_line_5_days": "1025",          # /TU "Line 5  Number of days..."
}
_DERIVATIONS_2021: dict[str, Callable[[Mapping[str, object]], object]] = {
    "1003 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "unmarried"),
    "1004 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "surviving_spouse"),
    "1005 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "marriage_annulled"),
    "1006 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "divorced_or_legally_separated"),
    "1007 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_apart_all_year"),
    "1008 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_together_part_of_year"),
    "1013 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "child_or_stepchild"),
    "1014 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "grandchild_sibling_niece_or_nephew"),
    "1015 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "eligible_foster_child"),
    "1016 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "parent_or_stepparent"),
    "1017 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "other_relative"),
    "1022 RB": _yes_no(_LINE_3A_KEY, "/0", "/1"),
    "1023 RB": _yes_no(_LINE_3B_KEY, "/0", "/1"),
}
_PART_I_2021 = ("1003 CB", "1004 CB", "1005 CB", "1006 CB", "1007 CB", "1008 CB")
_PART_II_2021 = ("1013 CB", "1014 CB", "1015 CB", "1016 CB", "1017 CB")
_LINE_3A_3B_2021 = ("1022 RB", "1023 RB")


# ---------------------------------------------------------------------------
# TY2022 - pdfs/california/2022/ftb3532.pdf (form code 8481223).
# Unprefixed names; checkboxes on /Yes. SSN MaxLen 10; line 5 MaxLen 3.
# ---------------------------------------------------------------------------
_MAPPING_2022: dict[str, str] = {
    "ftb3532_header_name": "1001",          # /TU "Name or names as shown on tax return."
    "ftb3532_header_ssn": "1002",           # /TU "Social Security Number or ITIN..."
    "ftb3532_period_1_from": "1009",        # /TU "List the beginning FROM date..."
    "ftb3532_period_1_to": "1010",          # /TU "List the ending TO date..."
    "ftb3532_period_2_from": "1011",        # /TU "Second beginning date..."
    "ftb3532_period_2_to": "1012",          # /TU "Second ending date..."
    "ftb3532_qp_first_name": "1018",        # /TU "Line 3 . First Name."
    "ftb3532_qp_last_name": "1019",         # /TU "Line 3 .  Last Name."
    "ftb3532_qp_ssn": "1020",               # /TU "Line 3 . Social Security Number."
    "ftb3532_qp_dob": "1021",               # /TU "Line 3 . Date of birth..."
    "ftb3532_line_4_gross_income": "1024",  # /TU "Line 4 . ...gross income..."
    "ftb3532_line_5_days": "1025",          # /TU "Line 5 . Number of days..."
}
_DERIVATIONS_2022: dict[str, Callable[[Mapping[str, object]], object]] = {
    "1003 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "unmarried"),
    "1004 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "surviving_spouse"),
    "1005 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "marriage_annulled"),
    "1006 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "divorced_or_legally_separated"),
    "1007 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_apart_all_year"),
    "1008 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_together_part_of_year"),
    "1013 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "child_or_stepchild"),
    "1014 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "grandchild_sibling_niece_or_nephew"),
    "1015 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "eligible_foster_child"),
    "1016 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "parent_or_stepparent"),
    "1017 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "other_relative"),
    "1022 RB": _yes_no(_LINE_3A_KEY, "/0", "/1"),
    "1023 RB": _yes_no(_LINE_3B_KEY, "/0", "/1"),
}
_PART_I_2022 = ("1003 CB", "1004 CB", "1005 CB", "1006 CB", "1007 CB", "1008 CB")
_PART_II_2022 = ("1013 CB", "1014 CB", "1015 CB", "1016 CB", "1017 CB")
_LINE_3A_3B_2022 = ("1022 RB", "1023 RB")


# ---------------------------------------------------------------------------
# TY2023 - pdfs/california/2023/ftb3532.pdf (form code 8481233).
# Unprefixed names; checkboxes on /Yes. SSN fields carry no MaxLen; line 5
# MaxLen 4.
# ---------------------------------------------------------------------------
_MAPPING_2023: dict[str, str] = {
    "ftb3532_header_name": "1001",          # /TU "Name or names as shown on tax return."
    "ftb3532_header_ssn": "1002",           # /TU "Social Security Number or ITIN..."
    "ftb3532_period_1_from": "1009",        # /TU "List the beginning FROM date..."
    "ftb3532_period_1_to": "1010",          # /TU "List the ending TO date..."
    "ftb3532_period_2_from": "1011",        # /TU "Second beginning date..."
    "ftb3532_period_2_to": "1012",          # /TU "Second ending date..."
    "ftb3532_qp_first_name": "1018",        # /TU "Part Three. Line 3. First Name."
    "ftb3532_qp_last_name": "1019",         # /TU "Line 3 .  Last Name."
    "ftb3532_qp_ssn": "1020",               # /TU "Line 3 . Social Security Number."
    "ftb3532_qp_dob": "1021",               # /TU "Line 3 . Date of birth..."
    "ftb3532_line_4_gross_income": "1024",  # /TU "Line 4 . ...gross income..."
    "ftb3532_line_5_days": "1025",          # /TU "Line 5 . Number of days..."
}
_DERIVATIONS_2023: dict[str, Callable[[Mapping[str, object]], object]] = {
    "1003 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "unmarried"),
    "1004 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "surviving_spouse"),
    "1005 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "marriage_annulled"),
    "1006 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "divorced_or_legally_separated"),
    "1007 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_apart_all_year"),
    "1008 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_together_part_of_year"),
    "1013 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "child_or_stepchild"),
    "1014 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "grandchild_sibling_niece_or_nephew"),
    "1015 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "eligible_foster_child"),
    "1016 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "parent_or_stepparent"),
    "1017 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "other_relative"),
    "1022 RB": _yes_no(_LINE_3A_KEY, "/0", "/1"),
    "1023 RB": _yes_no(_LINE_3B_KEY, "/0", "/1"),
}
_PART_I_2023 = ("1003 CB", "1004 CB", "1005 CB", "1006 CB", "1007 CB", "1008 CB")
_PART_II_2023 = ("1013 CB", "1014 CB", "1015 CB", "1016 CB", "1017 CB")
_LINE_3A_3B_2023 = ("1022 RB", "1023 RB")


# ---------------------------------------------------------------------------
# TY2024 - pdfs/california/2024/ftb3532.pdf (form code 8481243).
# Names gain the "3532_" prefix; checkboxes still on /Yes. SSN MaxLen 10;
# line 5 MaxLen 3.
# ---------------------------------------------------------------------------
_MAPPING_2024: dict[str, str] = {
    "ftb3532_header_name": "3532_1001",          # /TU "Name or names as shown on tax return."
    "ftb3532_header_ssn": "3532_1002",           # /TU "Social Security Number or ITIN..."
    "ftb3532_period_1_from": "3532_1009",        # /TU "List the beginning FROM date..."
    "ftb3532_period_1_to": "3532_1010",          # /TU "List the ending TO date..."
    "ftb3532_period_2_from": "3532_1011",        # /TU "Second beginning date..."
    "ftb3532_period_2_to": "3532_1012",          # /TU "Second ending date..."
    "ftb3532_qp_first_name": "3532_1018",        # /TU "Part three. Line 3 . First Name."
    "ftb3532_qp_last_name": "3532_1019",         # /TU "Line 3 .  Last Name."
    "ftb3532_qp_ssn": "3532_1020",               # /TU "Line 3 . Social Security Number. Enter 9 digits."
    "ftb3532_qp_dob": "3532_1021",               # /TU "Line 3 . Date of birth..."
    "ftb3532_line_4_gross_income": "3532_1024",  # /TU "Line 4 . ...gross income..."
    "ftb3532_line_5_days": "3532_1025",          # /TU "Line 5 . Number of days..."
}
_DERIVATIONS_2024: dict[str, Callable[[Mapping[str, object]], object]] = {
    "3532_1003 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "unmarried"),
    "3532_1004 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "surviving_spouse"),
    "3532_1005 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "marriage_annulled"),
    "3532_1006 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "divorced_or_legally_separated"),
    "3532_1007 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_apart_all_year"),
    "3532_1008 CB": _checkbox(_MARITAL_KEY, _MARITAL_VALUES, "married_lived_together_part_of_year"),
    "3532_1013 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "child_or_stepchild"),
    "3532_1014 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "grandchild_sibling_niece_or_nephew"),
    "3532_1015 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "eligible_foster_child"),
    "3532_1016 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "parent_or_stepparent"),
    "3532_1017 CB": _checkbox(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, "other_relative"),
    "3532_1022 RB": _yes_no(_LINE_3A_KEY, "/0", "/1"),
    "3532_1023 RB": _yes_no(_LINE_3B_KEY, "/0", "/1"),
}
_PART_I_2024 = ("3532_1003 CB", "3532_1004 CB", "3532_1005 CB",
                "3532_1006 CB", "3532_1007 CB", "3532_1008 CB")
_PART_II_2024 = ("3532_1013 CB", "3532_1014 CB", "3532_1015 CB",
                 "3532_1016 CB", "3532_1017 CB")
_LINE_3A_3B_2024 = ("3532_1022 RB", "3532_1023 RB")


# ---------------------------------------------------------------------------
# TY2025 - pdfs/california/2025/ftb3532.pdf (form code 8481253).
# Prefixed names; Part I and Part II are each ONE radio group. SSN MaxLen 9;
# line 5 MaxLen 3. Radio state -> printed line, by widget /Rect against the
# printed label rows: Part I /0../5 = 1a..1f, Part II /0../4 = 2a..2e.
# ---------------------------------------------------------------------------
_MAPPING_2025: dict[str, str] = {
    "ftb3532_header_name": "3532_1001",          # /TU "Name or names as shown on tax return."
    "ftb3532_header_ssn": "3532_1002",           # /TU "Social Security Number or ITIN..."
    "ftb3532_period_1_from": "3532_1009",        # /TU "List the beginning FROM date..."
    "ftb3532_period_1_to": "3532_1010",          # /TU "List the ending TO date..."
    "ftb3532_period_2_from": "3532_1011",        # /TU "Second beginning date..."
    "ftb3532_period_2_to": "3532_1012",          # /TU "Second ending date..."
    "ftb3532_qp_first_name": "3532_1018",        # /TU "Part three. ... Line 3 . First Name."
    "ftb3532_qp_last_name": "3532_1019",         # /TU "Line 3 .  Last Name."
    "ftb3532_qp_ssn": "3532_1020",               # /TU "Line 3 . Social Security Number. Enter 9 digits."
    "ftb3532_qp_dob": "3532_1021",               # /TU "Line 3 . Date of birth..."
    "ftb3532_line_4_gross_income": "3532_1024",  # /TU "Line 4 . ...gross income..."
    "ftb3532_line_5_days": "3532_1025",          # /TU "Line 5 . Number of days..."
}
_MARITAL_RB_STATES_2025: dict[str, str] = {
    "unmarried": "/0",                            # 1a  widget y 631-645
    "surviving_spouse": "/1",                     # 1b  y 613-627
    "marriage_annulled": "/2",                    # 1c  y 595-609
    "divorced_or_legally_separated": "/3",        # 1d  y 577-591
    "married_lived_apart_all_year": "/4",         # 1e  y 559-573
    "married_lived_together_part_of_year": "/5",  # 1f  y 530-544
}
_RELATIONSHIP_RB_STATES_2025: dict[str, str] = {
    "child_or_stepchild": "/0",                   # 2a  y 431-445
    "grandchild_sibling_niece_or_nephew": "/1",   # 2b  y 410-424
    "eligible_foster_child": "/2",                # 2c  y 389-403
    "parent_or_stepparent": "/3",                 # 2d  y 368-382
    "other_relative": "/4",                       # 2e  y 336-351
}
_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {
    "3532_1003 RB": _radio(_MARITAL_KEY, _MARITAL_VALUES, _MARITAL_RB_STATES_2025),
    "3532_1013 RB": _radio(_RELATIONSHIP_KEY, _RELATIONSHIP_VALUES, _RELATIONSHIP_RB_STATES_2025),
    "3532_1022 RB": _yes_no(_LINE_3A_KEY, "/0", "/1"),
    "3532_1023 RB": _yes_no(_LINE_3B_KEY, "/0", "/1"),
}
_PART_I_2025 = ("3532_1003 RB",)
_PART_II_2025 = ("3532_1013 RB",)
_LINE_3A_3B_2025 = ("3532_1022 RB", "3532_1023 RB")


_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2021: _DERIVATIONS_2021,
    2022: _DERIVATIONS_2022,
    2023: _DERIVATIONS_2023,
    2024: _DERIVATIONS_2024,
    2025: _DERIVATIONS_2025,
}
# (Part I cells, Part II cells, 3a/3b cells) per year.
_BUTTON_GROUPS_BY_YEAR: dict[int, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    2021: (_PART_I_2021, _PART_II_2021, _LINE_3A_3B_2021),
    2022: (_PART_I_2022, _PART_II_2022, _LINE_3A_3B_2022),
    2023: (_PART_I_2023, _PART_II_2023, _LINE_3A_3B_2023),
    2024: (_PART_I_2024, _PART_II_2024, _LINE_3A_3B_2024),
    2025: (_PART_I_2025, _PART_II_2025, _LINE_3A_3B_2025),
}


def _birth_year(dob: object) -> int | None:
    """Year from an mm/dd/yyyy DOB string, or None when absent or unparseable
    (a missing DOB is then reported through its own required field)."""
    if not isinstance(dob, str):
        return None
    try:
        return datetime.datetime.strptime(dob, "%m/%d/%Y").year
    except ValueError:
        return None


class PdfFtb3532(PdfFormMapping[dict[str, str]]):
    """FTB 3532 mapping: per-year text cells, button derivations, and the
    branch-aware required-field set (see module docstring)."""

    _FORM_NAME = "FTB 3532"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2021: _MAPPING_2021,
        2022: _MAPPING_2022,
        2023: _MAPPING_2023,
        2024: _MAPPING_2024,
        2025: _MAPPING_2025,
    }

    @classmethod
    def get_derivations(
        cls, year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in _DERIVATIONS_BY_YEAR:
            raise ValueError(f"No FTB 3532 derivations for year {year}")
        return _DERIVATIONS_BY_YEAR[year]

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        # No FTB 3532 cell sums compute keys (the form has no arithmetic).
        if year not in cls._MAPPINGS:
            raise ValueError(f"No FTB 3532 aggregations for year {year}")
        return {}

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        # Every button cell is a derivation returning its state token
        # directly; no bool-valued compute key is mapped 1:1.
        if year not in cls._MAPPINGS:
            raise ValueError(f"No FTB 3532 checkbox states for year {year}")
        return {}

    @classmethod
    def required_pdf_fields(cls, values: Mapping[str, object], year: int) -> set[str]:
        """PDF field paths the resolved payload must contain for this
        scenario's branch of the form.

        Always: the eight always-answered text cells (REQUIRED_TEXT_KEYS) and
        every Part I and Part II button cell (each checkbox is written
        explicitly, /Yes or /Off). Line 1f: the first From/To pair, plus the
        second pair when either of its keys is present. Qualifying person 19
        or older in the tax year, read from the payload's DOB as
        ``year - birth_year >= 19`` (the schema's age reading): both 3a and
        3b. The age branch comes from the DOB, not from whether 3a/3b keys
        are present, so a 19+ payload that dropped both answers is caught
        instead of passing as the under-19 branch.
        """
        mapping = cls.get_mapping(year)
        part_i, part_ii, line_3a_3b = _BUTTON_GROUPS_BY_YEAR[year]
        required = {mapping[k] for k in REQUIRED_TEXT_KEYS}
        required.update(part_i)
        required.update(part_ii)
        marital = values.get(_MARITAL_KEY)
        if getattr(marital, "value", marital) == _LIVED_TOGETHER:
            required.add(mapping["ftb3532_period_1_from"])
            required.add(mapping["ftb3532_period_1_to"])
            if ("ftb3532_period_2_from" in values
                    or "ftb3532_period_2_to" in values):
                required.add(mapping["ftb3532_period_2_from"])
                required.add(mapping["ftb3532_period_2_to"])
        birth_year = _birth_year(values.get("ftb3532_qp_dob"))
        if birth_year is not None and year - birth_year >= _LINE_3A_AGE:
            required.update(line_3a_3b)
        return required
