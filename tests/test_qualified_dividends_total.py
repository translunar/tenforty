"""Total qualified dividends = 1099-DIV + K-1 (IRC 1366(b) conduit treatment).

All figures are GENERIC/synthetic.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f1040_spine
from tenforty.forms import f8995 as form_f8995
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import FilingStatus, Form1099DIV, K1FanoutData, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_k1_scenario, make_simple_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]


class QualifiedDividendsTotalPreambleTests(unittest.TestCase):
    def _fanout(self, k1_qual):
        return K1FanoutData(
            sch_b_interest_additions=(),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(),
            sch_d_long_term_additions=(),
            qbi_aggregate=0.0,
            qualified_dividends_aggregate=k1_qual,
            passive_activities=(),
        )

    def test_total_is_1099div_plus_k1(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        # Give the scenario a 1099-DIV carrying qualified dividends.
        s.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=8_000.0,
        )]
        pre = f1040_spine.compute_income_preamble(
            s, params, {}, k1_fanout=self._fanout(3_000.0),
        )
        self.assertEqual(pre.qualified_divs, 8_000)        # 1099-DIV component
        self.assertEqual(pre.qualified_divs_k1, 3_000)     # K-1 component
        self.assertEqual(pre.qualified_divs_total, 11_000) # the authoritative total

    def test_total_equals_1099div_when_no_k1(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        s.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=8_000.0,
        )]
        pre = f1040_spine.compute_income_preamble(s, params, {})
        self.assertEqual(pre.qualified_divs_k1, 0)
        self.assertEqual(pre.qualified_divs_total, 8_000)

    def test_total_equals_k1_when_no_1099div(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        s.form1099_div = []
        pre = f1040_spine.compute_income_preamble(
            s, params, {}, k1_fanout=self._fanout(3_000.0),
        )
        self.assertEqual(pre.qualified_divs, 0)
        self.assertEqual(pre.qualified_divs_total, 3_000)


class QualifiedDividendsMixedSourceEndToEndTests(unittest.TestCase):
    """End-to-end regression coverage for the blind spot that let both line-3a
    defects (Form 8995 line 12, and the QDCGT preferential-rate base) survive
    a fully green suite: NO test anywhere else in the repo puts qualified
    dividends on a 1099-DIV *and* a K-1 in the same scenario. Form-level unit
    tests that hand-build the upstream stub dict cannot catch a defect in
    what the orchestrator itself feeds a form, so these tests run the real
    ``ReturnOrchestrator`` end to end (mirroring
    ``tests/test_orchestrator_predicates.py``'s construction pattern) rather
    than hand-building a stub.

    Scenario (all figures synthetic/generic): 2025 single filer, standard
    deduction, W-2 wages 100,000 (from ``make_k1_scenario``'s base). ONE
    1099-DIV: ordinary_dividends 10,000, qualified_dividends 8,000. ONE
    S-corp K-1: ordinary_business_income 50,000 (this — NOT qbi_amount —
    is what flows into AGI via Schedule 1/Schedule E; qbi_amount is a
    separate QBI-only channel that does not itself add to AGI),
    qbi_amount 50,000, ordinary_dividends 4,000, qualified_dividends 3,000.
    No 1099-B / Schedule D activity, so net_capital_gain is 0.

    Every expected figure below was independently derived from the Form
    8995 formula (line 6 = 20% x QBI; line 13 = line 11 - line 12;
    line 14 = 20% x line 13; line 15 = min(line 6, line 14)), from the
    2025 IRS single rate schedule, and from the QDCGT worksheet, then
    confirmed to match what the current code actually produces before being
    hardcoded here. Docstrings on individual tests record the corresponding
    PRE-FIX (defective) values so a future reader can see the shape of each
    defect this unit closed.

    THE INTERIM WINDOW IS NOW CLOSED. An earlier revision of this docstring
    warned that the figures here understated tax, because a companion
    defect was still live: on the native spine a K-1's `ordinary_dividends`
    never reached 1040 line 3b / AGI, even though that same K-1's
    `qualified_dividends` (a subset of it, per IRC 1366(b)) WAS already
    given preferential treatment. That produced the arithmetically
    impossible relationship line 3a > line 3b and taxed a slice of ordinary
    income at preferential rates. **That companion unit has landed**: a
    K-1's ordinary dividends and interest now reach 1040 lines 3b/2b and
    AGI. The warning no longer applies and has been removed; the figures
    below are the authoritative post-fix ones.

    What changed when it landed, for THIS scenario:
      AGI 160,000 -> 164,000 (the K-1's 4,000 of ordinary dividends now
      reaches line 3b), and total_tax 24,077 -> 25,037. The 960 delta is
      exactly 4,000 taxed at this scenario's 24% marginal ordinary rate —
      and 25,037 is precisely what routing the identical dollars through a
      1099-DIV instead has always produced, which is the cross-check that
      identified the defect in the first place.

    Full post-fix derivation for this scenario (all from the IRS schedules,
    not read out of the code):
      AGI = wages 100,000 + 1099-DIV ordinary dividends 10,000 + K-1
      ordinary dividends 4,000 + K-1 ordinary_business_income 50,000
      = 164,000.
      f8995 line 11 = 164,000 - standard deduction 15,750 = 148,250.
      line 6 = 20% x qbi 50,000 = 10,000.
      line 12 = qualified_divs_total (8,000 + 3,000) + max(0, ncg 0)
      = 11,000. line 13 = 148,250 - 11,000 = 137,250. line 14 = 20% x
      137,250 = 27,450. line 15 = min(10,000, 27,450) = 10,000 — LINE 6
      binds here, NOT the income limit, so the QBI deduction does not move
      when line 12 moves (that case is covered by
      QualifiedDividendsIncomeLimitBindingEndToEndTests instead).
      Final taxable income = 148,250 - 10,000 = 138,250.
      Preferential base = 11,000; ordinary portion = 138,250 - 11,000
      = 127,250. That is at/above the 100,000 Tax Table ceiling, so the
      rate schedule applies: 11,925 x 10% = 1,192.50, plus 36,550 x 12%
      = 4,386, plus 54,875 x 22% = 12,072.50, plus 23,900 x 24% = 5,736
      => 23,387. The ordinary floor 127,250 already exceeds the 48,350
      0%-band breakpoint, so all 11,000 of preferential income falls in
      the 15% band: 11,000 x 15% = 1,650. total_tax = 23,387 + 1,650
      = 25,037.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work_dir = Path(tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.work_dir,
        )
        self.scenario = make_k1_scenario()
        self.scenario.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=10_000.0,
            qualified_dividends=8_000.0,
        )]
        self.scenario.schedule_k1s = [ScheduleK1(
            entity_name="Generic S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
            qbi_amount=50_000.0,
            ordinary_dividends=4_000.0,
            qualified_dividends=3_000.0,
        )]

    def test_f8995_line_12_is_the_1099div_plus_k1_total(self) -> None:
        """Form 8995 line 12 must be qualified_divs (1099-DIV) +
        qualified_divs_k1 (K-1) + max(0, net_capital_gain) =
        8,000 + 3,000 + 0 = 11,000.

        PRE-FIX (defect A): f8995.py read
        ``fanout.qualified_dividends_aggregate`` directly — the K-1-ONLY
        component — so line 12 came out to 3,000, dropping the 1099-DIV's
        8,000 entirely and overstating the line-14 income limit (and
        therefore, in scenarios where line 14 binds, the QBI deduction).
        """
        sched, _ = self.orchestrator._compute_native_schedules(self.scenario)
        f8995 = sched["f8995"]

        self.assertEqual(f8995["f8995_line_12_net_capital_gain"], 11_000)

        # line 11 (taxable income before QBI) is independent of this defect;
        # read it straight from the form's own output to derive lines 13/14.
        line_11 = f8995["f8995_line_11_taxable_income"]
        expected_line_13 = line_11 - 11_000
        self.assertEqual(f8995["f8995_line_13_subtract"], expected_line_13)
        self.assertEqual(
            f8995["f8995_line_14_income_limit"], round(0.20 * expected_line_13),
        )

    def test_pipeline_tax_uses_full_qualified_dividend_total(self) -> None:
        """Form 1040 line 16 tax (QDCGT worksheet) must be computed against
        the FULL qualified-dividend total (1099-DIV 8,000 + K-1 3,000 =
        11,000) in the preferential-rate base, not the 1099-DIV component
        alone.

        The hardcoded ``25_037`` below is the real independent derivation —
        computed from the IRS ordinary-rate schedule/table and the QDCGT
        breakpoints by hand, not read back out of the code under test (see
        the class docstring for the step-by-step arithmetic). The
        direct ``qdcgt_tax`` call that follows is NOT an independent
        derivation: it re-invokes the exact same ``qdcgt_tax`` function with
        the same arguments the pipeline itself uses, so it cannot detect a
        defect inside ``qdcgt_tax``. What it DOES prove is wiring: that the
        pipeline actually passes the full combined total through to
        ``qdcgt_tax`` rather than silently substituting a partial figure —
        and it demonstrably fails (defect B, below) when that wiring
        regresses.

        PRE-FIX (defect B): f1040_spine.py fed qdcgt_tax
        ``preamble.qualified_divs`` — the 1099-DIV-only component (8,000)
        — so the K-1's 3,000 of qualified dividends was taxed as ORDINARY
        income instead of at the QDCGT preferential rate, overstating tax
        by (25,307 - 25,037 =) 270. That 270 is 3,000 x (24% ordinary
        marginal rate - 15% preferential rate); it is unchanged by the
        K-1-ordinary-dividends unit, which moved both figures up by the
        same 960 without changing the marginal rate either sits at.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(results["total_tax"], 25_037)

        params = load_federal_params(2025)
        independently_computed_tax = qdcgt_tax(
            taxable_income=results["taxable_income"],
            qualified_dividends=11_000,
            net_capital_gain=0,
            params=params,
            filing_status=FilingStatus.SINGLE,
        )
        self.assertEqual(independently_computed_tax, results["total_tax"])

    def test_f8995_and_qdcgt_consumers_agree_on_the_same_total(self) -> None:
        """The two consumers that each used to read only HALF of line 3a —
        Form 8995 line 12 and the QDCGT preferential base fed by the spine
        — must now agree, both landing on the same independently-stated
        total: 8,000 (1099-DIV) + 3,000 (K-1) = 11,000.
        """
        combined_total = 11_000

        sched, _ = self.orchestrator._compute_native_schedules(self.scenario)
        f8995_figure = sched["f8995"]["f8995_line_12_net_capital_gain"]
        self.assertEqual(f8995_figure, combined_total)

        params = load_federal_params(2025)
        results = self.orchestrator._compute_1040_pipeline(self.scenario)
        tax_with_combined_total = qdcgt_tax(
            taxable_income=results["taxable_income"],
            qualified_dividends=combined_total,
            net_capital_gain=0,
            params=params,
            filing_status=FilingStatus.SINGLE,
        )
        # The spine's actual total_tax must match what qdcgt_tax produces
        # when fed the SAME combined_total that f8995 used for line 12 —
        # proving both consumers were fed the one authoritative figure.
        self.assertEqual(results["total_tax"], tax_with_combined_total)


class QualifiedDividendsIncomeLimitBindingEndToEndTests(unittest.TestCase):
    """Pins the actual taxpayer-visible harm of defect A, which the tests in
    ``QualifiedDividendsMixedSourceEndToEndTests`` do NOT: in that class's
    scenario, Form 8995 line 15 = min(line 6 = 10,000, line 14 = 27,450) is
    bound by line 6, so reverting defect A moves lines 12-14 but leaves the
    QBI deduction (and therefore total_tax) completely unchanged — no dollar
    the taxpayer sees is affected. This class uses a scenario where the
    line-14 INCOME LIMIT binds instead, so the QBI deduction itself moves.

    (That 27,450 is the POST-fix figure and must stay in step with the
    derivation in ``QualifiedDividendsMixedSourceEndToEndTests``'s own
    docstring, which is its source: line 13 = 148,250 - 11,000 = 137,250,
    line 14 = 20% x 137,250 = 27,450. It read 26,650 — the pre-fix value
    from the AGI-160,000 world — until 2026-08-17, when the two docstrings
    were caught giving different line-14 figures for the same scenario. The
    point being made here is true either way, since line 6's 10,000 binds
    against both; only the cited number was stale. Any figure quoted from
    another class is a cross-reference, and cross-references rot.)

    Scenario (all figures synthetic/generic): 2025 single filer, standard
    deduction, acknowledges_qbi_below_threshold=True, NO W-2 wages. ONE
    1099-DIV: ordinary_dividends 100,000, qualified_dividends 100,000. ONE
    S-corp K-1: ordinary_business_income 50,000, qbi_amount 50,000,
    ordinary_dividends 4,000, qualified_dividends 3,000. No 1099-B /
    Schedule D activity, so net_capital_gain is 0.

    Derivation (independently worked by hand from the Form 8995 formula,
    the 2025 IRS Tax Table/rate schedule, and the QDCGT worksheet, then
    cross-checked against the code):
      AGI = wages 0 + 1099-DIV ordinary_dividends 100,000 + K-1
      ordinary_dividends 4,000 + K-1 ordinary_business_income 50,000
      = 154,000. (The K-1's own 4,000 of ordinary dividends reaches line 3b
      and AGI as of the K-1-ordinary-dividends unit; before that unit landed
      it did not, and AGI here was 150,000.)
      Taxable income before QBI (f8995 line 11) = AGI - standard deduction
      15,750 = 138,250.

      qbi_total = 50,000 (K-1 qbi_amount); f8995 line 6 = 20% x 50,000 =
      10,000.

      line 12 = qualified_divs_total (100,000 + 3,000) +
      max(0, net_capital_gain) = 103,000 — unchanged by the
      K-1-ordinary-dividends unit, since only the K-1's ORDINARY dividends
      moved; its 3,000 of qualified dividends was already included.
      line 13 = 138,250 - 103,000 = 35,250. line 14 = 20% x 35,250 =
      7,050. line 15 (QBI deduction) = min(7,050, 10,000) = 7,050 — the
      INCOME LIMIT (line 14) still binds, not line 6.

      Final taxable income = 138,250 - 7,050 = 131,200. Preferential base
      (qualified dividends total) = 103,000; ordinary portion = 131,200 -
      103,000 = 28,200, which is below the 100,000 Tax Table ceiling, so
      the 2025 Tax Table applies: the 28,200-28,250 single row carries
      3,149 (the bin midpoint 28,225 gives 1,192.50 + 12% x 16,300 =
      3,148.50, IRS-rounded to 3,149).
      The 103,000 preferential amount stacks on top of the 28,200 ordinary
      floor: 20,150 of it falls in the 0% band (28,200 to the 48,350
      breakpoint) and the remaining 82,850 falls in the 15% band, taxed at
      82,850 x 15% = 12,427.50, IRS-rounded to 12,428. total_tax = 3,149 +
      12,428 = 15,577.

      UNDER DEFECT A (f8995.py reading ``fanout.qualified_dividends_aggregate``
      — the K-1-only 3,000 — instead of the preamble total): line 12 =
      3,000; line 13 = 135,250; line 14 = 27,050; line 15 = min(27,050,
      10,000) = 10,000 — now line 6 binds instead, and the QBI deduction
      is OVERSTATED by 10,000 - 7,050 = 2,950. Final taxable income drops
      to 128,250, whose ordinary portion 25,250 draws 2,795 from the Tax
      Table while 23,100 lands in the 0% band and 79,900 x 15% = 11,985
      in the 15% band, so total_tax comes out to 14,780 — UNDERSTATING the
      taxpayer's tax liability by 15,577 - 14,780 = 797.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work_dir = Path(tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.work_dir,
        )
        self.scenario = make_k1_scenario()
        self.scenario.w2s = []
        self.scenario.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=100_000.0,
            qualified_dividends=100_000.0,
        )]
        self.scenario.schedule_k1s = [ScheduleK1(
            entity_name="Generic S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
            qbi_amount=50_000.0,
            ordinary_dividends=4_000.0,
            qualified_dividends=3_000.0,
        )]

    def test_qbi_deduction_moves_when_income_limit_binds(self) -> None:
        """The QBI deduction itself (f8995 line 15) must reflect the FULL
        qualified-dividend total in the line-12/13/14 chain, because here
        the income limit (line 14), not line 6, is the binding constraint.

        Correct: line 15 = 7,050; total_tax = 15,577.
        Under defect A: line 15 = 10,000 (overstated by 2,950);
        total_tax = 14,780 (understated by 797) — a real dollar amount
        the taxpayer would see on their return.
        """
        sched, _ = self.orchestrator._compute_native_schedules(self.scenario)
        f8995 = sched["f8995"]

        # line 12 is unchanged by the K-1-ordinary-dividends unit (only the
        # K-1's ORDINARY dividends moved); lines 13-15 move because line 11
        # rose with AGI. See the class docstring for the full derivation.
        self.assertEqual(f8995["f8995_line_12_net_capital_gain"], 103_000)
        self.assertEqual(f8995["f8995_line_13_subtract"], 35_250)
        self.assertEqual(f8995["f8995_line_14_income_limit"], 7_050)
        self.assertEqual(f8995["f8995_line_15_qbi_deduction"], 7_050)

        results = self.orchestrator._compute_1040_pipeline(self.scenario)
        self.assertEqual(results["taxable_income"], 131_200)
        self.assertEqual(results["total_tax"], 15_577)


class QualifiedDividendsEmitPathAgreesWithComputePathTests(unittest.TestCase):
    """The COMPUTE path and the PDF-EMIT path must produce the SAME Form 8995.

    Nothing else in this repo compares those two paths, and that gap let a
    real regression ship: ``forms.f8995.compute`` reads
    ``upstream["f1040"]["qualified_dividends"]``, but only ONE of the two
    producers supplied that key. The compute path got it from the
    orchestrator's compute-time stub (built from the shared income
    preamble). The emit path builds a DIFFERENT upstream —
    ``{"f1040": results, "k1_fanout": ...}`` — from the FINISHED 1040
    results dict, and that dict carried ``dividend_income`` and
    ``ordinary_dividends`` but NO ``qualified_dividends``. With the old
    silent ``.get(..., 0)`` default, the emit path therefore computed line
    12 as 0.

    Measured on this exact scenario BEFORE the fix — and note these are
    HISTORICAL measurements, taken while AGI here was still 150,000,
    i.e. before the K-1-ordinary-dividends unit landed. The QBI-deduction
    figures below are therefore the pre-that-unit ones (6,250); today the
    correct deduction is 7,050. The SHAPE of the defect is what this table
    records, not figures to compare against current assertions:

                                  COMPUTE      EMIT
        f8995 line 12             103,000         0
        line 15 (QBI deduction)     6,250    10,000
        emitted 1040 line 13                    6,250

    So the emitted Form 8995 and the emitted 1040 in the SAME packet
    contradicted each other, and the emitted 8995 asserted exactly the
    overstated 10,000 deduction this branch exists to eliminate.

    The fix has ``compute_spine`` publish ``qualified_dividends`` (the
    authoritative 1040 line 3a total) in its output dict, so both paths
    read one value, and makes f8995's read STRICT so any future upstream
    that omits the key fails loudly instead of silently producing 0.

    Scenario (all figures synthetic/generic): 2025 single filer, standard
    deduction, acknowledges_qbi_below_threshold=True, NO W-2 wages. ONE
    1099-DIV: ordinary_dividends 100,000, qualified_dividends 100,000. ONE
    S-corp K-1: ordinary_business_income 50,000, qbi_amount 50,000,
    ordinary_dividends 4,000, qualified_dividends 3,000. This shape is used
    because the Form 8995 line-14 INCOME LIMIT binds here, so the defect
    moved the QBI deduction itself, not merely the intermediate lines.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work_dir = Path(tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.work_dir,
        )
        self.scenario = make_k1_scenario()
        self.scenario.w2s = []
        self.scenario.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=100_000.0,
            qualified_dividends=100_000.0,
        )]
        self.scenario.schedule_k1s = [ScheduleK1(
            entity_name="Generic S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
            qbi_amount=50_000.0,
            ordinary_dividends=4_000.0,
            qualified_dividends=3_000.0,
        )]

    def _emit_path_f8995(self) -> dict:
        """Reproduce what the PDF-emit path does to build Form 8995.

        Mirrors ``ReturnOrchestrator._emit_pdfs_internal``: compute the 1040
        results via the pipeline, hoist the Schedule E Part II fanout, then
        assemble ``upstream = {"f1040": results, "k1_fanout": fanout}`` and
        run the real ``f8995.compute`` against it.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)
        _part_ii_fields, fanout = form_sch_e_part_ii.compute(
            self.scenario, upstream={},
        )
        return form_f8995.compute(
            self.scenario,
            upstream={"f1040": results, "k1_fanout": fanout},
        )

    def test_emit_path_f8995_equals_compute_path_f8995(self) -> None:
        """The emit-path Form 8995 must equal the compute-path Form 8995.

        This is an equality between two INDEPENDENTLY-COMPUTED pipelines,
        not a tautology: each side builds its own ``upstream`` dict from a
        different producer (the orchestrator's compute-time preamble stub
        vs. the finished spine results dict) and runs the same form against
        it. Before the fix these two sides disagreed on lines 12-15 — that
        disagreement IS the bug, and this assertion is what would have
        caught it.
        """
        compute_sched, _ = self.orchestrator._compute_native_schedules(
            self.scenario,
        )
        compute_f8995 = compute_sched["f8995"]
        emit_f8995 = self._emit_path_f8995()

        for line in (
            "f8995_line_12_net_capital_gain",
            "f8995_line_13_subtract",
            "f8995_line_14_income_limit",
            "f8995_line_15_qbi_deduction",
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    emit_f8995[line], compute_f8995[line],
                    f"emit path and compute path disagree on {line}: "
                    f"emit={emit_f8995[line]} compute={compute_f8995[line]}. "
                    "The emitted Form 8995 would contradict the emitted 1040 "
                    "in the same packet.",
                )

        # Pin the shared values against the independent derivation recorded
        # on QualifiedDividendsIncomeLimitBindingEndToEndTests, so a future
        # change that breaks BOTH paths identically cannot pass this test by
        # agreeing on a wrong number.
        self.assertEqual(emit_f8995["f8995_line_12_net_capital_gain"], 103_000)
        self.assertEqual(emit_f8995["f8995_line_15_qbi_deduction"], 7_050)

    def test_1040_line_3a_is_the_authoritative_1099div_plus_k1_total(self) -> None:
        """1040 line 3a (``qualified_dividends`` in the spine's output dict)
        must equal the authoritative total: 1099-DIV qualified dividends
        100,000 + K-1 qualified dividends 3,000 = 103,000.

        The 103,000 literal is derived from the scenario inputs by the line-3a
        formula (1099-DIV box 1b + K-1 box 5b, per IRC 1366(b)), not read back
        out of the code under test.

        BEHAVIOR CHANGE pinned here: ``mappings.pdf_1040`` has always mapped
        the key ``qualified_dividends`` to 1040 line 3a for every year, but
        ``compute_spine`` never emitted that key — so line 3a was BLANK on
        every emitted 1040 to date. That was a pre-existing DISPLAY defect
        (the tax math was already right; the printed form was incomplete).
        Publishing the key both fixes the display and gives the emit path the
        value Form 8995 line 12 needs.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(results["qualified_dividends"], 103_000)

        # Line 3a must be a SUBSET of line 3b on a well-formed 1040:
        # qualified dividends are a subset of ordinary dividends, so line 3a
        # can never exceed line 3b.
        #
        # HISTORY: this assertion used to read assertGreater(3a, 3b) — it
        # deliberately PINNED the known-bad interim state, in which line 3a
        # already included the K-1's 3,000 of qualified dividends while line
        # 3b still excluded the K-1's 4,000 of ordinary dividends entirely
        # (3a 103,000 > 3b 100,000, arithmetically impossible on a real
        # 1040). It served as a failing marker for the companion
        # K-1-ordinary-dividends unit to land against. That unit HAS landed,
        # line 3b is now 104,000, and the assertion flipped to the correct
        # invariant below.
        #
        # This inequality is asserted BEFORE the line-3b equality on
        # purpose: a regression that stops the K-1's ordinary dividends from
        # reaching line 3b breaks both, and running the diagnostic one first
        # is what makes the explanatory message below the thing a failing
        # reader actually sees. (Previously the bare equality ran first and
        # this message never printed.)
        self.assertLessEqual(
            results["qualified_dividends"], results["ordinary_dividends"],
            "1040 line 3a (qualified dividends) exceeds line 3b (ordinary "
            "dividends), which is impossible: line 3a is by definition a "
            "SUBSET of line 3b. This is the signature of a K-1's qualified "
            "dividends reaching line 3a while its ordinary dividends fail "
            "to reach line 3b — the exact defect the K-1-ordinary-dividends "
            "unit fixed. A slice of ordinary income is being granted "
            "preferential capital-gain rates, understating tax.",
        )
        # Line 3b = 1099-DIV 100,000 + K-1 4,000 = 104,000, per IRC 1366(b)
        # conduit treatment; derived from the scenario inputs, not read back
        # out of the code under test.
        self.assertEqual(results["ordinary_dividends"], 104_000)
