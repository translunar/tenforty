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


# pytest-xdist (the fast tier runs `-n 4 --dist load`): a worker ships each
# subtest report to the controller through execnet, and execnet serializes
# only exact primitive types. subTest keyword values such as FilingStatus /
# HohMaritalStatus / DivergenceDirection members (str-valued Enums, i.e. str
# SUBCLASSES, which execnet also refuses) or datetime.date raise DumpError
# INSIDE the test, failing it. This wrapper replaces any non-primitive kwarg
# value with its repr at pytest_report_to_serializable, the boundary where a
# report is serialized; a serial run never serializes reports, so it is
# unaffected. Under xdist a failing subtest's label shows the value as a
# quoted repr string. Depends on pytest's subtest report carrying its kwargs
# under "_subtest.context" (pytest 9 built-in subtests).
def _xdist_safe(value):
    # Exact types: a str-valued Enum is a str subclass, and execnet refuses
    # subclasses.
    if value is None or type(value) in (bool, int, float, str, bytes):
        return value
    if type(value) in (list, tuple):
        return type(value)(_xdist_safe(v) for v in value)
    if type(value) is dict:
        return {k: _xdist_safe(v) for k, v in value.items()}
    return repr(value)


@pytest.hookimpl(wrapper=True)
def pytest_report_to_serializable(config, report):
    data = yield
    if isinstance(data, dict) and "_subtest.context" in data:
        context = data["_subtest.context"]
        context["kwargs"] = _xdist_safe(dict(context.get("kwargs") or {}))
    return data
