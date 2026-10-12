"""Compute one Form 4562 copy the way the orchestrator does: one activity's
form, handed the RETURN's 40% answer.

Test-side only. The form itself never works out that answer
(`f4562.compute_for` takes it as a required keyword); a test that wants one
copy's values gets them through here so the answer always comes from the
whole scenario, never from the activity alone.
"""
from tenforty.forms import f4562
from tenforty.forms.depreciation.resolver import mid_quarter_applies


def compute_copy(scenario, section: str = "rental_properties",
                 index: int = 0) -> dict:
    """The values of the Form 4562 copy for ``scenario.<section>[index]``."""
    activity = getattr(scenario, section)[index]
    return f4562.compute_for(
        activity, scenario.config.year, scenario.config.pdf_header(),
        mid_quarter=mid_quarter_applies(scenario))
