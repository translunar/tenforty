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
        from tenforty.models import Form1099DIV
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
        from tenforty.models import Form1099DIV
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

        Independent derivation (not a tautology): rather than reading
        ``total_tax`` back out of the pipeline and comparing it to itself,
        this calls ``qdcgt_tax`` directly — a genuinely different code path
        than the one the pipeline's internal ``compute_spine`` call takes to
        produce ``total_tax`` — using the combined 11,000 total and the
        pipeline's own reported taxable_income (134,250, an input, not the
        value under test) as inputs. If the pipeline's wiring is correct,
        the two computations of "tax on the same taxable income with the
        same preferential base" must agree.

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
