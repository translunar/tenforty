"""Anchor data types (spec §3.3): independent statements of where a printed
line sits on the paper, used to prove the mapped field really is that line.

Data only. Evaluating an anchor against a template is the check-suite's job;
nothing here reads a PDF. A declared line carries an anchor only when the
default anchor (its own tooltip on California forms, its printed label row
on federal forms) cannot locate it.
"""
import enum
from dataclasses import dataclass

# Geometry tolerances in PDF points (spec §3.3).
ROW_PT = 2           # two boxes share a row when their baselines differ by less
COLUMN_PT = 5        # two boxes share a column when their left edges differ by less
NEXT_ROW_PT = 20     # the next row down starts within this distance
LABEL_GAP_PT = 12    # a box sits beside its label within this gap
WRAP_PT = 14         # a wrapped label's continuation row is within this distance


class LabelRelation(enum.Enum):
    """Where a field sits relative to a printed phrase."""
    ON_ROW = "on_row"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    AFTER_WRAPPED = "after_wrapped"   # on the row after a label that wraps


class FieldRelation(enum.Enum):
    """Where a field sits relative to another declared line's field."""
    SAME_ROW_RIGHT_OF = "same_row_right_of"
    SAME_ROW_LEFT_OF = "same_row_left_of"
    NEXT_ROW_BELOW = "next_row_below"


@dataclass(frozen=True)
class Tooltip:
    """The field's own /TU tooltip matches this regular expression."""
    pattern: str


@dataclass(frozen=True)
class RowLabel:
    """The field sits on the row of this printed label token."""
    token: str


@dataclass(frozen=True)
class NearLabel:
    """The field sits in ``relation`` to this printed phrase."""
    phrase: str
    relation: LabelRelation


@dataclass(frozen=True)
class NearField:
    """The field sits in ``relation`` to another declared line's field."""
    other_line: str
    relation: FieldRelation


Anchor = Tooltip | RowLabel | NearLabel | NearField
