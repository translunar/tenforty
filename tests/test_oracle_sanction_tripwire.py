"""Unit tests for the runtime soffice-sanction tripwire (tiering-leak step 3).

Covers `tenforty.oracle.engine._assert_oracle_sanctioned` (the guard placed at the
top of `_recalculate`, before any soffice launch) and
`tests.helpers.set_oracle_sanction` (the conftest hookwrapper's setter, which
sets/clears the sanction env from a test item's `oracle` marker).
"""

import os
import unittest
from unittest.mock import patch

from tenforty.oracle.engine import _assert_oracle_sanctioned
from tests.helpers import set_oracle_sanction


class _StubItem:
    """Minimal stand-in for a pytest Item, exposing only get_closest_marker."""

    def __init__(self, oracle: bool) -> None:
        self._oracle = oracle

    def get_closest_marker(self, name):
        return object() if self._oracle else None


class OracleSanctionTripwireTests(unittest.TestCase):
    def test_guard_raises_under_pytest_without_sanction(self) -> None:
        with patch.dict(
            os.environ, {"PYTEST_CURRENT_TEST": "pkg::test_x"}, clear=False,
        ):
            os.environ.pop("TENFORTY_ORACLE_SANCTIONED", None)
            with self.assertRaises(RuntimeError) as ctx:
                _assert_oracle_sanctioned()
            self.assertIn("pkg::test_x", str(ctx.exception))

    def test_guard_allows_with_sanction(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PYTEST_CURRENT_TEST": "pkg::test_x",
                "TENFORTY_ORACLE_SANCTIONED": "1",
            },
            clear=False,
        ):
            self.assertIsNone(_assert_oracle_sanctioned())

    def test_guard_inert_without_pytest_current_test(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ.pop("TENFORTY_ORACLE_SANCTIONED", None)
            self.assertIsNone(_assert_oracle_sanctioned())

    def test_setter_sets_for_oracle_item(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TENFORTY_ORACLE_SANCTIONED", None)
            set_oracle_sanction(_StubItem(oracle=True))
            self.assertEqual(os.environ.get("TENFORTY_ORACLE_SANCTIONED"), "1")

    def test_setter_clears_for_unmarked_after_oracle(self) -> None:
        with patch.dict(os.environ, {"TENFORTY_ORACLE_SANCTIONED": "1"}, clear=False):
            set_oracle_sanction(_StubItem(oracle=False))
            self.assertNotIn("TENFORTY_ORACLE_SANCTIONED", os.environ)


if __name__ == "__main__":
    unittest.main()
