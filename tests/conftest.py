"""pytest configuration."""
import os

import pytest

from tests.helpers import set_oracle_sanction


# Oracle-collection env gate. Two same-week incidents had implementers reach the
# soffice/LibreOffice oracle path via a bare `pytest tests/`. Oracle-marked tests
# now REFUSE to run unless TENFORTY_ORACLE_OK=1 — the merge-gate runner (team-lead)
# sets it deliberately. We fail LOUD at collection (UsageError, nonzero exit)
# rather than skip, so a gate run can never silently lose its oracle coverage.
#
# trylast=True runs this AFTER pytest's builtin -m marker deselection: a routine
# `-m "not oracle"` invocation DESELECTS but still COLLECTS oracle items, so by
# the time this hook sees `items` those deselected oracle tests are already gone
# and the gate correctly stays quiet.
@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    if os.environ.get("TENFORTY_ORACLE_OK") == "1":
        return
    if any(item.get_closest_marker("oracle") is not None for item in items):
        raise pytest.UsageError(
            "Oracle-marked tests are selected but TENFORTY_ORACLE_OK is not set. "
            "Oracle tests invoke LibreOffice and must be run deliberately by the "
            'merge-gate runner. Set TENFORTY_ORACLE_OK=1 to run them, or deselect '
            'them with -m "not oracle".'
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    # Set/clear the soffice sanction BEFORE the internal pytest_runtest_setup fires
    # (that internal hook triggers fixture setup incl. unittest setUpClass, which may
    # launch soffice). hookwrapper pre-yield runs before all non-wrapper hookimpls, so
    # the sanction is in place before any class-level launch can reach the guard.
    set_oracle_sanction(item)
    yield
