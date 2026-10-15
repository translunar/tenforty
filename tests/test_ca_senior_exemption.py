"""California Form 540 line 9 (senior exemption), every year 2021-2025.

Count: a person born strictly before the year's ``senior_born_before`` is a
senior; the spouse is counted on a joint return only. Credit: line 9 =
count x ``senior_exemption_credit``, and it rides lines 11 and 32 with the
personal and dependent exemptions. Placement: the line 9 count and amount
keys land on each year's own "Line 9. Senior" widgets (sentinel fill +
read-back, and the widget's own tooltip), never a neighbour year's numbers.

Every expected dollar figure and every birthdate is derived from the year's
loaded params; tests of the pending (None) behaviour run on synthetic params
only. Synthetic data only.
"""
import dataclasses
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f540 as form_f540
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.models import CA540Return, FilingStatus
from tenforty.orchestrator import ReturnOrchestrator, form_1040_age_box_values
from tenforty.params import california as ca_params
from tenforty.params import federal as federal_params
from tests._ca_emit_helpers import CA_YEARS, REPO_ROOT, make_ca_scenario

DAY = datetime.timedelta(days=1)

# Obviously synthetic: no real tax year's cutoff looks like this.
SENTINEL_CUTOFF = datetime.date(1111, 11, 11)

COUNT_KEY = "f540_line9_count"
AMOUNT_KEY = "f540_line9_amount"


def _aged(year: int) -> str:
    """Born the day before the year's cutoff: a senior."""
    return (ca_params.load(year).senior_born_before - DAY).isoformat()


def _not_aged(year: int) -> str:
    """Born on the year's cutoff: not a senior (strictly-before test)."""
    return ca_params.load(year).senior_born_before.isoformat()


def _config(year: int, fs: FilingStatus = FilingStatus.SINGLE, *,
            birthdate: str, spouse_birthdate: str = ""):
    return dataclasses.replace(
        make_ca_scenario(year, fs).config,
        birthdate=birthdate, spouse_birthdate=spouse_birthdate)


def _compute(year: int, fs: FilingStatus, *, num_seniors: int,
             num_dependents: int = 0):
    return form_f540.compute(
        year=year, filing_status=fs, federal_agi=80_000, ca_agi=80_000,
        ca540=CA540Return(), num_dependents=num_dependents,
        num_seniors=num_seniors)


class CaSeniorCountTests(unittest.TestCase):
    """``ca_senior_count``: strict born-before on each year's cutoff; the
    spouse counts on a joint return only."""

    def test_boundary_pair_every_year(self):
        for year in CA_YEARS:
            params = ca_params.load(year)
            with self.subTest(year=year):
                self.assertEqual(form_f540.ca_senior_count(
                    _config(year, birthdate=_aged(year)), params), 1)
                self.assertEqual(form_f540.ca_senior_count(
                    _config(year, birthdate=_not_aged(year)), params), 0)

    def test_joint_return_counts_each_spouse(self):
        mfj = FilingStatus.MARRIED_FILING_JOINTLY
        for year in CA_YEARS:
            params = ca_params.load(year)
            a, n = _aged(year), _not_aged(year)
            for tp, sp, want in ((a, a, 2), (n, a, 1), (a, n, 1), (n, n, 0)):
                with self.subTest(year=year, taxpayer=tp, spouse=sp):
                    cfg = _config(year, mfj, birthdate=tp, spouse_birthdate=sp)
                    self.assertEqual(
                        form_f540.ca_senior_count(cfg, params), want)

    def test_spouse_is_not_counted_off_a_joint_return(self):
        # MFS accepts a spouse birthdate; it must not add a senior.
        for year in CA_YEARS:
            params = ca_params.load(year)
            with self.subTest(year=year):
                cfg = _config(year, FilingStatus.MARRIED_FILING_SEPARATELY,
                              birthdate=_not_aged(year),
                              spouse_birthdate=_aged(year))
                self.assertEqual(form_f540.ca_senior_count(cfg, params), 0)
                cfg = dataclasses.replace(cfg, birthdate=_aged(year))
                self.assertEqual(form_f540.ca_senior_count(cfg, params), 1)

    def test_single_and_hoh_count_the_taxpayer_only(self):
        for year in CA_YEARS:
            params = ca_params.load(year)
            for fs in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD):
                with self.subTest(year=year, fs=fs.value):
                    self.assertEqual(form_f540.ca_senior_count(
                        _config(year, fs, birthdate=_aged(year)), params), 1)
                    self.assertEqual(form_f540.ca_senior_count(
                        _config(year, fs, birthdate=_not_aged(year)), params), 0)

    def test_joint_return_without_spouse_birthdate_refuses(self):
        cfg = _config(2025, FilingStatus.MARRIED_FILING_JOINTLY,
                      birthdate=_not_aged(2025))
        with self.assertRaises(ValueError):
            form_f540.ca_senior_count(cfg, ca_params.load(2025))

    def test_pending_cutoff_refuses_by_name(self):
        # Synthetic params: the real cutoffs are live and stay live.
        params = dataclasses.replace(
            ca_params.load(2025), senior_born_before=None)
        cfg = _config(2025, birthdate=(SENTINEL_CUTOFF - DAY).isoformat())
        with self.assertRaises(form_f540.CaSeniorParamsPendingError) as cm:
            form_f540.ca_senior_count(cfg, params)
        self.assertIn("senior_born_before", str(cm.exception))

    def test_sentinel_cutoff_is_honoured(self):
        # State-independent: the count reads the params it is handed.
        params = dataclasses.replace(
            ca_params.load(2025), senior_born_before=SENTINEL_CUTOFF)
        self.assertEqual(form_f540.ca_senior_count(
            _config(2025, birthdate=(SENTINEL_CUTOFF - DAY).isoformat()),
            params), 1)
        self.assertEqual(form_f540.ca_senior_count(
            _config(2025, birthdate=SENTINEL_CUTOFF.isoformat()), params), 0)


class CaSeniorExemptionTests(unittest.TestCase):
    """The line-32 exemption credit includes line 9, from params."""

    def test_credit_is_transcribed_nonzero_every_year(self):
        # Precondition for the arithmetic below meaning anything.
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertTrue(ca_params.load(year).senior_exemption_credit)

    def test_compute_adds_each_senior(self):
        for year in CA_YEARS:
            params = ca_params.load(year)
            senior = params.senior_exemption_credit
            dep = params.dependent_exemption_amount
            for fs, seniors in ((FilingStatus.SINGLE, 1),
                                (FilingStatus.MARRIED_FILING_JOINTLY, 2),
                                (FilingStatus.MARRIED_FILING_JOINTLY, 1)):
                with self.subTest(year=year, fs=fs.value, seniors=seniors):
                    personal = params.for_status(fs).exemption_credit
                    got = _compute(year, fs, num_seniors=seniors,
                                   num_dependents=1)
                    self.assertEqual(got["f540_exemption_credit"],
                                     personal + seniors * senior + dep)

    def test_presentation_line9_and_line11_match_line32(self):
        mfj = FilingStatus.MARRIED_FILING_JOINTLY
        for year in CA_YEARS:
            senior = ca_params.load(year).senior_exemption_credit
            for fs, tp, sp, want in (
                    (FilingStatus.SINGLE, _aged(year), "", 1),
                    (mfj, _aged(year), _aged(year), 2),
                    (mfj, _not_aged(year), _aged(year), 1)):
                with self.subTest(year=year, fs=fs.value, seniors=want):
                    cfg = _config(year, fs, birthdate=tp, spouse_birthdate=sp)
                    keys = form_f540.presentation_keys(cfg, [], year)
                    self.assertEqual(keys[COUNT_KEY], want)
                    self.assertEqual(keys[AMOUNT_KEY], want * senior)
                    self.assertEqual(
                        keys["f540_line11_exemption_amount"],
                        _compute(year, fs, num_seniors=want)[
                            "f540_exemption_credit"])

    def test_no_senior_leaves_line9_blank(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                keys = form_f540.presentation_keys(
                    _config(year, birthdate=_not_aged(year)), [], year)
                self.assertNotIn(COUNT_KEY, keys)
                self.assertNotIn(AMOUNT_KEY, keys)

    def test_orchestrator_wires_the_senior_count(self):
        # The CA compute core (shared by original and amended returns) reads
        # the count from the scenario, so line 32 carries the senior credit.
        for year in CA_YEARS:
            params = ca_params.load(year)
            with self.subTest(year=year):
                young = make_ca_scenario(year)
                scn = dataclasses.replace(young, config=dataclasses.replace(
                    young.config, birthdate=_aged(year)))
                work = Path(tempfile.mkdtemp())
                orch = ReturnOrchestrator(
                    spreadsheets_dir=REPO_ROOT / "spreadsheets",
                    work_dir=work / "work")
                # Federal results from the non-aged twin: an aged federal
                # return refuses from TY2025 (Schedule 1-A, ruling
                # R-senior-1a), and the CA core reads the senior count from
                # `scn`, not from the federal results.
                results = orch._compute_ca_results(
                    scn, CA540Return(), orch.compute_federal(young))
                self.assertEqual(
                    results["f540_exemption_credit"],
                    params.for_status(FilingStatus.SINGLE).exemption_credit
                    + params.senior_exemption_credit)
                self.assertEqual(results[AMOUNT_KEY],
                                 params.senior_exemption_credit)

    def test_pending_credit_refuses_by_name_in_compute(self):
        # Synthetic params: the real credits are live and stay live.
        synthetic = dataclasses.replace(
            ca_params.load(2025), senior_exemption_credit=None)
        with mock.patch.object(ca_params, "load", return_value=synthetic):
            with self.assertRaises(form_f540.CaSeniorParamsPendingError) as cm:
                _compute(2025, FilingStatus.SINGLE, num_seniors=1)
        self.assertIn("senior_exemption_credit", str(cm.exception))

    def test_pending_credit_refuses_by_name_in_presentation(self):
        synthetic = dataclasses.replace(
            ca_params.load(2025), senior_born_before=SENTINEL_CUTOFF,
            senior_exemption_credit=None)
        cfg = _config(2025, birthdate=(SENTINEL_CUTOFF - DAY).isoformat())
        with mock.patch.object(ca_params, "load", return_value=synthetic):
            with self.assertRaises(form_f540.CaSeniorParamsPendingError):
                form_f540.presentation_keys(cfg, [], 2025)


class CaLine9PlacementTests(unittest.TestCase):
    """Each year's line 9 keys fill that year's own "Line 9. Senior" count
    box and its amount cell."""

    def test_mapped_widgets_are_line9_by_their_own_tooltip(self):
        for year in CA_YEARS:
            mapping = PdfF540.get_mapping(year)
            fields = PdfReader(str(
                REPO_ROOT / "pdfs" / "california" / str(year) / "f540.pdf"
            )).get_fields()
            with self.subTest(year=year):
                count_tu = str(fields[mapping[COUNT_KEY]].get("/TU"))
                amount_tu = str(fields[mapping[AMOUNT_KEY]].get("/TU"))
                self.assertTrue(count_tu.startswith("Line 9. Senior"), count_tu)
                self.assertIn("line 9 box", amount_tu)

    def test_sentinel_fill_reads_back_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in CA_YEARS:
            senior = ca_params.load(year).senior_exemption_credit
            mapping = PdfF540.get_mapping(year)
            with self.subTest(year=year):
                out = tmp / f"f540_line9_{year}.pdf"
                PdfFiller().fill(
                    template_path=(REPO_ROOT / "pdfs" / "california"
                                   / str(year) / "f540.pdf"),
                    output_path=out, field_mapping=mapping,
                    values={COUNT_KEY: 2, AMOUNT_KEY: 2 * senior})
                fields = PdfReader(str(out)).get_fields()
                self.assertEqual(
                    str(fields[mapping[COUNT_KEY]].get("/V")), "2")
                self.assertEqual(
                    str(fields[mapping[AMOUNT_KEY]].get("/V")).replace(",", ""),
                    str(2 * senior))


class AgedFederalCaConsistencyTests(unittest.TestCase):
    """An aged filer's 1040 age boxes and 540 line 9 count agree, every year.
    The federal side is the orchestrator's pure age-box helper on the federal
    cutoff; the CA side is ``ca_senior_count`` on the CA cutoff — two
    independent decisions over the same config."""

    def test_aged_single_counts_agree(self):
        for year in CA_YEARS:
            fed_cutoff = federal_params.load(year).aged_born_before
            with self.subTest(year=year):
                cfg = _config(year, birthdate=_aged(year))
                boxes = form_1040_age_box_values(cfg, fed_cutoff)
                ca = form_f540.ca_senior_count(cfg, ca_params.load(year))
                self.assertEqual(ca, 1)
                self.assertEqual(sum(boxes.values()), ca)

    def test_joint_counts_agree(self):
        mfj = FilingStatus.MARRIED_FILING_JOINTLY
        for year in CA_YEARS:
            fed_cutoff = federal_params.load(year).aged_born_before
            a, n = _aged(year), _not_aged(year)
            for tp, sp in ((a, a), (n, a), (a, n), (n, n)):
                with self.subTest(year=year, taxpayer=tp, spouse=sp):
                    cfg = _config(year, mfj, birthdate=tp, spouse_birthdate=sp)
                    self.assertEqual(
                        sum(form_1040_age_box_values(cfg, fed_cutoff).values()),
                        form_f540.ca_senior_count(cfg, ca_params.load(year)))


class AgeCutoffAgreementTests(unittest.TestCase):
    """The federal ``aged_born_before`` and the CA ``senior_born_before`` are
    two independent transcription chains (IRS and FTB sources, separately
    adjudicated). Their agreement is EVIDENCE that both are right, not a
    definition: if they ever diverge, route it to team-lead for a source
    ruling — never "fix" it by copying one side onto the other."""

    def test_federal_and_ca_cutoffs_agree_every_year(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertEqual(federal_params.load(year).aged_born_before,
                                 ca_params.load(year).senior_born_before)
