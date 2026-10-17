"""The one result type every harness check reports (spec §3.1).

A ``Finding`` names where a problem is (scenario, form, year or revision,
printed line), which check found it, and what is wrong. Declaration
validation reports with ``scenario=""`` (no scenario is involved).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    scenario: str
    form: str
    year: int | str
    line: str
    check: str
    message: str
