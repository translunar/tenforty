"""The per-status params accessor: ``params.for_status(status)``.

A present column reads straight from params; a missing column raises
UnsupportedStatusError (fail-closed, never KeyError, never another status's
column); non-per-status fields pass through. NoRawStatusSubscriptTests keeps
form code on the accessor so the completeness gate has one chokepoint.
"""
import ast
import dataclasses
import unittest
from pathlib import Path

from tenforty import years
from tenforty.models import FilingStatus
from tenforty.params import california as ca_params
from tenforty.params.california import PER_STATUS_CALIFORNIA_FIELDS
from tenforty.params.federal import PER_STATUS_FEDERAL_FIELDS
from tenforty.params.federal import load as load_federal
from tenforty.params.status_view import StatusView, UnsupportedStatusError

REPO_ROOT = Path(__file__).resolve().parent.parent

_FEDERAL_YEARS = years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS
_CALIFORNIA_YEARS = years.CALIFORNIA_YEARS + years.CALIFORNIA_COMPUTE_ONLY_YEARS


class StatusViewTests(unittest.TestCase):
    def test_present_federal_column_returns_params_value(self):
        for year in _FEDERAL_YEARS:
            params = load_federal(year)
            for status in FilingStatus:
                view = params.for_status(status)
                for name in PER_STATUS_FEDERAL_FIELDS:
                    column = getattr(params, name)
                    if status.value not in column:
                        continue
                    with self.subTest(year=year, status=status, field=name):
                        self.assertEqual(getattr(view, name),
                                         column[status.value])

    def test_present_california_column_returns_params_value(self):
        for year in _CALIFORNIA_YEARS:
            params = ca_params.load(year)
            for status in FilingStatus:
                view = params.for_status(status)
                for name in PER_STATUS_CALIFORNIA_FIELDS:
                    column = getattr(params, name)
                    if status.value not in column:
                        continue
                    with self.subTest(year=year, status=status, field=name):
                        self.assertEqual(getattr(view, name),
                                         column[status.value])

    def test_missing_column_raises_unsupported_status_error(self):
        params = load_federal(2025)
        trimmed = dataclasses.replace(params, standard_deduction={
            k: v for k, v in params.standard_deduction.items()
            if k != FilingStatus.HEAD_OF_HOUSEHOLD.value})
        # The other statuses still read (the drop is the only change).
        self.assertEqual(
            trimmed.for_status(FilingStatus.SINGLE).standard_deduction,
            params.standard_deduction["single"])
        view = trimmed.for_status(FilingStatus.HEAD_OF_HOUSEHOLD)
        with self.assertRaises(UnsupportedStatusError) as ctx:
            view.standard_deduction
        err = ctx.exception
        self.assertNotIsInstance(err, KeyError)
        self.assertIsInstance(err, NotImplementedError)
        self.assertEqual(err.field, "standard_deduction")
        self.assertEqual(err.year, 2025)
        self.assertIs(err.status, FilingStatus.HEAD_OF_HOUSEHOLD)
        message = str(err)
        self.assertIn("standard_deduction", message)
        self.assertIn("2025", message)
        self.assertIn("head_of_household", message)

    def test_missing_california_column_raises_unsupported_status_error(self):
        params = ca_params.load(2025)
        trimmed = dataclasses.replace(params, rate_schedule={
            k: v for k, v in params.rate_schedule.items()
            if k != FilingStatus.MARRIED_FILING_JOINTLY.value})
        with self.assertRaises(UnsupportedStatusError) as ctx:
            trimmed.for_status(FilingStatus.MARRIED_FILING_JOINTLY).rate_schedule
        self.assertEqual(ctx.exception.field, "rate_schedule")

    def test_non_per_status_fields_pass_through(self):
        params = load_federal(2025)
        view = params.for_status(FilingStatus.MARRIED_FILING_JOINTLY)
        self.assertEqual(view.year, params.year)
        self.assertEqual(view.ss_wage_base, params.ss_wage_base)
        self.assertEqual(view.eic_income_ceiling, params.eic_income_ceiling)
        ca = ca_params.load(2025)
        self.assertEqual(
            ca.for_status(FilingStatus.SINGLE).dependent_exemption_amount,
            ca.dependent_exemption_amount)

    def test_view_exposes_status_and_year(self):
        view = load_federal(2024).for_status(FilingStatus.SINGLE)
        self.assertIsInstance(view, StatusView)
        self.assertIs(view.status, FilingStatus.SINGLE)
        self.assertEqual(view.year, 2024)

    def test_unknown_attribute_raises_attribute_error(self):
        view = load_federal(2025).for_status(FilingStatus.SINGLE)
        with self.assertRaises(AttributeError):
            view.no_such_field

    def test_view_is_read_only(self):
        view = load_federal(2025).for_status(FilingStatus.SINGLE)
        with self.assertRaises(AttributeError):
            view.standard_deduction = 0


def _status_like(node: ast.expr) -> bool:
    """A Name/Attribute whose final identifier ends with ``status``."""
    if isinstance(node, ast.Name):
        return node.id.endswith("status")
    if isinstance(node, ast.Attribute):
        return node.attr.endswith("status")
    return False


def _scanned_files() -> list[Path]:
    allowed = {"tax_table.py", "status_view.py"}
    files = sorted((REPO_ROOT / "tenforty" / "forms").glob("*.py"))
    files.append(REPO_ROOT / "tenforty" / "orchestrator.py")
    return [p for p in files if p.name not in allowed]


class NoRawStatusSubscriptTests(unittest.TestCase):
    def test_no_subscript_by_status_value(self):
        """``x[<...>status.value]`` in form code bypasses the accessor."""
        hits = []
        for path in _scanned_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.slice, ast.Attribute)
                        and node.slice.attr == "value"
                        and _status_like(node.slice.value)):
                    hits.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
        self.assertEqual(hits, [])

    def test_no_direct_subscript_of_a_per_status_params_field(self):
        """``params.<per-status field>[...]`` in form code bypasses the
        accessor even when the key is a pre-extracted string. Catches the
        sites the ``.value`` rule cannot see (``status = ....value`` then
        ``params.salt_cap_starting[status]``)."""
        per_status = (set(PER_STATUS_FEDERAL_FIELDS)
                      | set(PER_STATUS_CALIFORNIA_FIELDS))
        hits = []
        for path in _scanned_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.value, ast.Attribute)
                        and node.value.attr in per_status):
                    hits.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} "
                        f"{node.value.attr}")
        self.assertEqual(hits, [])
