"""Guard tests: LibreOffice-dependence structurally implies the oracle tier.

These tests protect the invariant established in tests/helpers.py:
`needs_libreoffice` stamps both `pytest.mark.oracle` and the LibreOffice
skipUnless in one place, so a test can never depend on soffice without also
being deselected by `-m "not oracle"`. See tests/helpers.py::needs_libreoffice
for the rationale.
"""

import ast
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, needs_libreoffice

TESTS_DIR = REPO_ROOT / "tests"

# Files that reference a soffice/engine entry-point but FULLY MOCK it (no real
# soffice), so they are legitimately NOT oracle-gated. Keep this list minimal
# and justified.
_MOCKED_ENGINE_ALLOWLIST = {
    "test_oracle_engine.py",  # patches subprocess.run; no real soffice
    # SE-health workbook-path fail-closed guard (ticket (dd)): the guard raises
    # at the top of _compute_1040_via_workbook, before any engine call. The
    # "fires" test raises there; the "field=0" test mocks orch.engine.compute
    # with a sentinel side_effect, so no real soffice is ever invoked.
    "test_se_health_workbook_guard.py",
    # Schedule C / SE workbook-path fail-closed guard: the guard raises at the
    # top of _compute_1040_via_workbook, before any engine call. The "fires"
    # test raises there; the "no business" test mocks orch.engine.compute with
    # a sentinel side_effect, so no real soffice is ever invoked.
    "test_sch_c_workbook_guard.py",
}


def _has_oracle_mark(obj) -> bool:
    return any(getattr(m, "name", None) == "oracle"
               for m in getattr(obj, "pytestmark", []))


class NeedsLibreofficeStampsOracleMark(unittest.TestCase):
    """The structural coupling: needs_libreoffice implies the oracle marker."""

    def test_class_decorated_gets_oracle_mark(self):
        @needs_libreoffice
        class _Dummy(unittest.TestCase):   # LOCAL class — not collected by pytest
            def test_noop(self):
                pass
        self.assertTrue(_has_oracle_mark(_Dummy))

    def test_function_decorated_gets_oracle_mark(self):
        @needs_libreoffice
        def _dummy():
            pass
        self.assertTrue(_has_oracle_mark(_dummy))


class NoBareLibreofficeSkipOutsideHelpers(unittest.TestCase):
    """AST guard: nobody may hand-roll `skipUnless(libreoffice_available())`
    or even reference `libreoffice_available` by name outside helpers.py.
    The only sanctioned use is inside needs_libreoffice itself."""

    def _iter_test_files(self):
        for path in sorted(TESTS_DIR.glob("*.py")):
            if path.name == "helpers.py":
                continue
            yield path

    @staticmethod
    def _calls_skip_unless_on_libreoffice_available(node: ast.Call) -> bool:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else None
        )
        if name != "skipUnless":
            return False
        for arg in node.args:
            if isinstance(arg, ast.Call):
                inner = arg.func
                inner_name = inner.attr if isinstance(inner, ast.Attribute) else (
                    inner.id if isinstance(inner, ast.Name) else None
                )
                if inner_name == "libreoffice_available":
                    return True
        return False

    def test_no_bare_skip_unless_or_bare_name_reference(self):
        offenders = []
        for path in self._iter_test_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and self._calls_skip_unless_on_libreoffice_available(node):
                    offenders.append(f"{path.name}:{node.lineno}")
                if isinstance(node, ast.Name) and node.id == "libreoffice_available":
                    offenders.append(f"{path.name}:{node.lineno}")
                if isinstance(node, ast.Attribute) and node.attr == "libreoffice_available":
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders, [],
            "Found bare libreoffice_available()/skipUnless usage outside "
            "helpers.py. Use @needs_libreoffice instead so LibreOffice "
            "dependence always carries the oracle marker: " + ", ".join(offenders),
        )


class SoffceEntryPointsAreOracleGated(unittest.TestCase):
    """Residual guard, file granularity: any test file that reaches a real
    soffice entry point (_compute_1040_via_workbook or SpreadsheetEngine)
    must use needs_libreoffice, or be explicitly allowlisted as fully mocked."""

    def test_every_soffice_entry_point_file_is_gated_or_allowlisted(self):
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            if path.name == "helpers.py":
                continue
            text = path.read_text()
            uses_entry_point = (
                "_compute_1040_via_workbook(" in text
                or "SpreadsheetEngine(" in text
            )
            if not uses_entry_point:
                continue
            if "needs_libreoffice" in text:
                continue
            if path.name in _MOCKED_ENGINE_ALLOWLIST:
                continue
            offenders.append(path.name)
        self.assertEqual(
            offenders, [],
            "These test files call a real soffice entry point "
            "(_compute_1040_via_workbook or SpreadsheetEngine) without using "
            "@needs_libreoffice and are not in _MOCKED_ENGINE_ALLOWLIST. "
            "Either add @needs_libreoffice, or if the entry point is fully "
            "mocked (no real soffice invocation), add the file to "
            "_MOCKED_ENGINE_ALLOWLIST with a comment justifying it: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
