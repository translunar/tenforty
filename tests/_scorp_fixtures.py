"""Shared fixtures for Sub-plan 2 / 1120-S tests.

Non-test helper module. The leading underscore prevents pytest from
collecting it as a test file. Tests across Tasks 1-19 import from here
instead of from each other to avoid test-to-test import dependencies.
"""

from tenforty.models import Address


def _example_address() -> Address:
    return Address(
        street="1 Example Ave",
        city="Example City",
        state="EX",
        zip_code="00000",
    )
