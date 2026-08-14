"""Total qualified dividends = 1099-DIV + K-1 (IRC 1366(b) conduit treatment).

All figures are GENERIC/synthetic.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f1040_spine
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
    line 14 = 20% x line 13; line 15 = min(line 6, line 14)) and from the
    QDCGT worksheet, then confirmed to match what the current (post-fix)
    code actually produces before being hardcoded here — see task-3-report
    for the confirmation run. Docstrings on individual tests record the
    corresponding PRE-FIX (defective) values so a future reader can see the
    shape of each defect this unit closed.

    NOTE for future readers: the asserted AGI (160,000) and total_tax
    (24,077) here bake in a SEPARATE, still-live defect (already scheduled
    as its own fix unit): on the native spine, a K-1's `ordinary_dividends`
    never reaches 1040 line 3b / AGI, even though that same K-1's
    `qualified_dividends` (a subset of it, per IRC 1366(b)) IS correctly
    given preferential treatment by the fix in THIS unit. In this scenario
    that means the K-1's 4,000 of ordinary dividends is excluded from AGI.
    When that separate defect is fixed, AGI here will legitimately become
    164,000 and the tax figures in this class WILL change. Such a change
    is NOT a regression in this unit's fix — do not treat it as one.
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

        The hardcoded ``24_077`` below is the real independent derivation —
        computed from the IRS ordinary-rate schedule/table and the QDCGT
        breakpoints by hand, not read back out of the code under test. The
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
        by (24,347 - 24,077 =) 270.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(results["total_tax"], 24_077)

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
    scenario, Form 8995 line 15 = min(line 6 = 10,000, line 14 = 26,650) is
    bound by line 6, so reverting defect A moves lines 12-14 but leaves the
    QBI deduction (and therefore total_tax) completely unchanged — no dollar
    the taxpayer sees is affected. This class uses a scenario where the
    line-14 INCOME LIMIT binds instead, so the QBI deduction itself moves.

    Scenario (all figures synthetic/generic): 2025 single filer, standard
    deduction, acknowledges_qbi_below_threshold=True, NO W-2 wages. ONE
    1099-DIV: ordinary_dividends 100,000, qualified_dividends 100,000. ONE
    S-corp K-1: ordinary_business_income 50,000, qbi_amount 50,000,
    ordinary_dividends 4,000, qualified_dividends 3,000. No 1099-B /
    Schedule D activity, so net_capital_gain is 0.

    Derivation (independently worked by hand from the Form 8995 formula,
    the 2025 IRS Tax Table/rate schedule, and the QDCGT worksheet — see the
    fix-wave report for the full arithmetic — then cross-checked against
    the code):
      AGI = wages 0 + 1099-DIV ordinary_dividends 100,000 + K-1
      ordinary_business_income 50,000 = 150,000. (The K-1's own 4,000 of
      ordinary_dividends does NOT reach AGI here — see the NOTE on
      ``QualifiedDividendsMixedSourceEndToEndTests`` above; that is a
      separate, still-live defect, not something this test is about.)
      Taxable income before QBI (f8995 line 11) = AGI - standard deduction
      15,750 = 134,250.

      qbi_total = 50,000 (K-1 qbi_amount); f8995 line 6 = 20% x 50,000 =
      10,000.

      POST-FIX line 12 = qualified_divs_total (100,000 + 3,000) +
      max(0, net_capital_gain) = 103,000. line 13 = 134,250 - 103,000 =
      31,250. line 14 = 20% x 31,250 = 6,250. line 15 (QBI deduction) =
      min(6,250, 10,000) = 6,250 — the INCOME LIMIT (line 14) binds, not
      line 6.

      Final taxable income = 134,250 - 6,250 = 128,000. Preferential base
      (qualified dividends total) = 103,000; ordinary portion = 128,000 -
      103,000 = 25,000, taxed via the 2025 Tax Table at 25,000 = 2,765.
      The 103,000 preferential amount stacks on top of the 25,000 ordinary
      floor: 23,350 of it falls in the 0% band (25,000 to the 48,350
      breakpoint) and the remaining 79,650 falls in the 15% band, taxed at
      79,650 x 15% = 11,947.50, IRS-rounded to 11,948. total_tax = 2,765 +
      11,948 = 14,713.

      UNDER DEFECT A (f8995.py reading ``fanout.qualified_dividends_aggregate``
      — the K-1-only 3,000 — instead of the preamble total): line 12 =
      3,000; line 13 = 131,250; line 14 = 26,250; line 15 = min(26,250,
      10,000) = 10,000 — now line 6 binds instead, and the QBI deduction
      is OVERSTATED by 10,000 - 6,250 = 3,750. Final taxable income drops
      to 124,250 and total_tax comes out to 13,700 — UNDERSTATING the
      taxpayer's tax liability by 14,713 - 13,700 = 1,013.
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

        Correct (post-fix): line 15 = 6,250; total_tax = 14,713.
        Under defect A: line 15 = 10,000 (overstated by 3,750);
        total_tax = 13,700 (understated by 1,013) — a real dollar amount
        the taxpayer would see on their return.
        """
        sched, _ = self.orchestrator._compute_native_schedules(self.scenario)
        f8995 = sched["f8995"]

        self.assertEqual(f8995["f8995_line_12_net_capital_gain"], 103_000)
        self.assertEqual(f8995["f8995_line_13_subtract"], 31_250)
        self.assertEqual(f8995["f8995_line_14_income_limit"], 6_250)
        self.assertEqual(f8995["f8995_line_15_qbi_deduction"], 6_250)

        results = self.orchestrator._compute_1040_pipeline(self.scenario)
        self.assertEqual(results["taxable_income"], 128_000)
        self.assertEqual(results["total_tax"], 14_713)
