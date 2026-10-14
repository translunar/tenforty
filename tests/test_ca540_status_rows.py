"""Form 540 per-status rows (MFJ, HoH) for TY2025.

Real-params rows read ``ca_params.load(2025)`` through the status accessor
where the column exists, and expect UnsupportedStatusError where it doesn't
yet (``agi_phaseout_threshold`` MFJ/HoH: dual-transcription pending — those
rows flip when the columns land). Sentinel rows patch the params object so a
per-status column differs from single's, proving the 540 code reads the
requested status's column rather than single's. The status-mismatch rows
cover run_full_california_return's conform-to-federal refusal.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.forms import f540
from tenforty.models import CA540Return, FilingStatus
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params import california as ca_params
from tenforty.params.status_view import UnsupportedStatusError
from tenforty.rounding import irs_round
from tests._ca_fixtures import _make_ca_v1_smoke_scenario, _write_ca_yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent

_YEAR = 2025
_S = FilingStatus.SINGLE
_MFJ = FilingStatus.MARRIED_FILING_JOINTLY
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD
_ROW_STATUSES = (_MFJ, _HOH)
# Personal exemptions claimed on Form 540 line 7: MFJ claims two, HoH one.
_PERSONAL_COUNT = {_MFJ: 2, _HOH: 1}


class StatusRowParamsTests(unittest.TestCase):
    """MFJ/HoH rows against the real TY2025 params, via the accessor."""

    def setUp(self):
        self.params = ca_params.load(_YEAR)
        self.single = self.params.for_status(_S)

    def test_standard_deduction_reads_status_column(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                self.assertEqual(
                    f540.compute_standard_deduction(_YEAR, status),
                    self.params.for_status(status).standard_deduction)

    def test_exemption_credit_personal_count(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                self.assertEqual(
                    f540.compute_exemption_credit(_YEAR, status),
                    _PERSONAL_COUNT[status] * self.single.exemption_credit)

    def test_rate_schedule_reads_status_column(self):
        income = 250_000  # rate-schedule branch (> $100,000)
        for status in _ROW_STATUSES:
            schedule = self.params.for_status(status).rate_schedule
            with self.subTest(status=status):
                self.assertNotEqual(schedule, self.single.rate_schedule)
                self.assertEqual(
                    f540.compute_ca_tax(_YEAR, status, income),
                    irs_round(f540._walk_rate_schedule(schedule, income)))
                self.assertNotEqual(
                    f540.compute_ca_tax(_YEAR, status, income),
                    f540.compute_ca_tax(_YEAR, _S, income))

    def test_renters_credit_threshold_reads_status_column(self):
        for status in _ROW_STATUSES:
            view = self.params.for_status(status)
            threshold = view.renter_credit_agi_threshold
            with self.subTest(status=status):
                # Between single's threshold and this status's: only the
                # status column grants the credit.
                self.assertGreater(threshold,
                                   self.single.renter_credit_agi_threshold)
                self.assertEqual(
                    f540._compute_renters_credit(_YEAR, status, threshold),
                    view.renter_credit_amount)
                self.assertEqual(
                    f540._compute_renters_credit(_YEAR, status, threshold + 1),
                    0)

    def test_phaseout_threshold_column_absent_refuses(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                with self.assertRaises(UnsupportedStatusError) as ctx:
                    self.params.for_status(status).agi_phaseout_threshold
                self.assertEqual(ctx.exception.field, "agi_phaseout_threshold")
                self.assertIs(ctx.exception.status, status)

    def test_phaseout_column_absent_refuses_compute_never_uses_single(self):
        # Federal AGI far below single's threshold: falling back to single's
        # column would compute; the status column's absence must refuse.
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                with self.assertRaises(UnsupportedStatusError) as ctx:
                    f540.compute(year=_YEAR, filing_status=status,
                                 federal_agi=50_000, ca_agi=50_000,
                                 ca540=CA540Return())
                self.assertEqual(ctx.exception.field, "agi_phaseout_threshold")


class SentinelColumnReadTests(unittest.TestCase):
    """A patched params object whose status columns differ from single's:
    the 540 code must return the requested status's sentinel."""

    def _patched(self, **fields):
        params = dataclasses.replace(ca_params.load(_YEAR), **fields)
        return mock.patch.object(ca_params, "load", return_value=params)

    def test_phaseout_gate_reads_status_column(self):
        single_threshold, status_threshold = 100_000, 300_000
        column = {_S.value: single_threshold}
        column.update({s.value: status_threshold for s in _ROW_STATUSES})
        self.assertNotEqual(single_threshold, status_threshold)
        between = single_threshold + 1
        with self._patched(agi_phaseout_threshold=column):
            with self.assertRaises(NotImplementedError):
                f540.compute(year=_YEAR, filing_status=_S,
                             federal_agi=between, ca_agi=50_000,
                             ca540=CA540Return())
            for status in _ROW_STATUSES:
                with self.subTest(status=status):
                    result = f540.compute(
                        year=_YEAR, filing_status=status,
                        federal_agi=between, ca_agi=50_000,
                        ca540=CA540Return())
                    self.assertIsInstance(result, dict)
                    with self.assertRaises(NotImplementedError) as ctx:
                        f540.compute(year=_YEAR, filing_status=status,
                                     federal_agi=status_threshold + 1,
                                     ca_agi=50_000, ca540=CA540Return())
                    self.assertNotIsInstance(ctx.exception,
                                             UnsupportedStatusError)
                    self.assertIn(f"{status_threshold}", str(ctx.exception))

    def test_standard_deduction_reads_status_column(self):
        column = {_S.value: 1_000}
        column.update({s.value: 7_000 for s in _ROW_STATUSES})
        self.assertNotEqual(column[_S.value], column[_MFJ.value])
        with self._patched(standard_deduction=column):
            for status in _ROW_STATUSES:
                with self.subTest(status=status):
                    self.assertEqual(
                        f540.compute_standard_deduction(_YEAR, status), 7_000)

    def test_exemption_credit_reads_status_column(self):
        column = {_S.value: 10}
        column.update({s.value: 70 for s in _ROW_STATUSES})
        self.assertNotEqual(column[_S.value], column[_MFJ.value])
        with self._patched(exemption_credit=column):
            for status in _ROW_STATUSES:
                with self.subTest(status=status):
                    self.assertEqual(
                        f540.compute_exemption_credit(_YEAR, status), 70)

    def test_rate_schedule_reads_status_column(self):
        column = {_S.value: ((0, 0.01),)}
        column.update({s.value: ((0, 0.05),) for s in _ROW_STATUSES})
        self.assertNotEqual(column[_S.value], column[_MFJ.value])
        with self._patched(rate_schedule=column):
            for status in _ROW_STATUSES:
                with self.subTest(status=status):
                    self.assertEqual(
                        f540.compute_ca_tax(_YEAR, status, 200_000), 10_000)

    def test_renters_credit_reads_status_columns(self):
        threshold = {_S.value: 1_000}
        threshold.update({s.value: 9_000 for s in _ROW_STATUSES})
        amount = {_S.value: 1}
        amount.update({s.value: 9 for s in _ROW_STATUSES})
        self.assertNotEqual(threshold[_S.value], threshold[_MFJ.value])
        self.assertNotEqual(amount[_S.value], amount[_MFJ.value])
        with self._patched(renter_credit_agi_threshold=threshold,
                           renter_credit_amount=amount):
            for status in _ROW_STATUSES:
                with self.subTest(status=status):
                    self.assertEqual(
                        f540._compute_renters_credit(_YEAR, status, 5_000), 9)


class _ReachedFreshnessCheck(Exception):
    """Raised by the patched freshness step: the status check let it through."""


class FederalContextStatusMismatchTests(unittest.TestCase):
    """run_full_california_return refuses a CA YAML whose
    federal_context.filing_status differs from the scenario's."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=_REPO_ROOT / "spreadsheets",
            work_dir=self.out / "work")
        self.scenario = _make_ca_v1_smoke_scenario()
        self.scenario.ca540 = None
        self.assertIs(self.scenario.config.filing_status, _S)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, ca_yaml: dict):
        path = _write_ca_yaml(ca_yaml, self.out)
        with mock.patch.object(ReturnOrchestrator, "_verify_ca_yaml_freshness",
                               side_effect=_ReachedFreshnessCheck):
            self.orch.run_full_california_return(
                scenario=self.scenario, ca_yaml_path=path,
                output_dir=self.out)

    def _ca540(self):
        return {"estimated_payments": 0.0, "use_tax": 0.0}

    def test_matching_status_proceeds(self):
        with self.assertRaises(_ReachedFreshnessCheck):
            self._run({"ca540": self._ca540(),
                       "federal_context": {"filing_status": _S.value}})

    def test_absent_context_proceeds(self):
        with self.assertRaises(_ReachedFreshnessCheck):
            self._run({"ca540": self._ca540()})

    def test_absent_status_in_context_proceeds(self):
        with self.assertRaises(_ReachedFreshnessCheck):
            self._run({"ca540": self._ca540(), "federal_context": {}})

    def test_mismatched_status_refuses(self):
        for status in _ROW_STATUSES:
            with self.subTest(status=status):
                with self.assertRaises(ValueError) as ctx:
                    self._run({"ca540": self._ca540(),
                               "federal_context": {"filing_status": status.value}})
                message = str(ctx.exception)
                self.assertIn(status.value, message)
                self.assertIn(_S.value, message)
                self.assertIn("federal", message.lower())
