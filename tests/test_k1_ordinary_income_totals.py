"""1040 lines 2b / 3b totals = 1099 + K-1 (IRC 1366(b) conduit treatment).

A K-1's ``interest_income`` and ``ordinary_dividends`` reach the EMITTED
Schedule B (via the Schedule E Part II fanout) but have never reached the
native spine's 1040 total-income / AGI math. These tests pin the two
authoritative totals the preamble now computes — ``taxable_interest_total``
(line 2b) and ``ordinary_divs_total`` (line 3b) — alongside the unchanged
1099-only components, mirroring the existing ``qualified_divs`` /
``qualified_divs_total`` precedent in the same module.

NOTE: this task is purely ADDITIVE. Nothing consumes the new fields yet, so
these tests assert on the ``IncomePreamble`` directly; the wiring into
total_income / AGI is a separate task.

FIXTURE NOTE: every K-1 here is HAND-AUTHORED with non-zero
``interest_income`` and ``ordinary_dividends``. K-1s produced by the 1120-S
form (``tenforty/forms/f1120s.py``) carry structurally-zero interest and
dividends (``_SCH_K_V1_ZERO_PLACEHOLDERS``), so a fixture built from an
S-corp-GENERATED K-1 would exercise none of this code and would pass
whether or not the totals are computed correctly.

All figures are GENERIC/synthetic.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f1040_spine
from tenforty.forms import sch_b as form_sch_b
from tenforty.forms import sch_ca as form_sch_ca
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import (
    CA540Return,
    Form1099DIV,
    Form1099INT,
    K1FanoutData,
    PayerAmount,
    ScheduleK1,
)
from tenforty.orchestrator import ReturnOrchestrator, _k1_positive_income
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_k1_scenario, make_simple_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fanout(interest_items=(), dividend_items=()) -> K1FanoutData:
    """A K1FanoutData carrying only the two Schedule B addition tuples.

    ``interest_items`` / ``dividend_items`` are (payer, amount) pairs.
    """
    return K1FanoutData(
        sch_b_interest_additions=tuple(
            PayerAmount(payer=p, amount=a) for p, a in interest_items
        ),
        sch_b_dividend_additions=tuple(
            PayerAmount(payer=p, amount=a) for p, a in dividend_items
        ),
        sch_d_short_term_additions=(),
        sch_d_long_term_additions=(),
        qbi_aggregate=0.0,
        qualified_dividends_aggregate=0.0,
        passive_activities=(),
    )


class K1OrdinaryIncomeTotalsPreambleTests(unittest.TestCase):
    """Direct unit coverage of the four new ``IncomePreamble`` fields."""

    def setUp(self) -> None:
        self.params = load_federal_params(2025)

    def _scenario_with_1099s(self):
        s = make_simple_scenario()
        s.form1099_int = [Form1099INT(payer="Generic Bank", interest=1_200.0)]
        s.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=7_000.0,
        )]
        return s

    def test_totals_are_1099_plus_k1(self) -> None:
        """Both totals = 1099 component + K-1 component.

        Interest: 1099-INT 1,200 + K-1s (300 + 450) = 1,950.
        Ordinary dividends: 1099-DIV 9,000 + K-1s (4,000 + 1,000) = 14,000.
        """
        pre = f1040_spine.compute_income_preamble(
            self._scenario_with_1099s(),
            self.params,
            {},
            k1_fanout=_fanout(
                interest_items=(
                    ("Generic S-Corp Inc", 300.0),
                    ("Generic Holdings Inc", 450.0),
                ),
                dividend_items=(
                    ("Generic S-Corp Inc", 4_000.0),
                    ("Generic Holdings Inc", 1_000.0),
                ),
            ),
        )

        # The pre-existing fields KEEP their 1099-only meaning.
        self.assertEqual(pre.taxable_interest, 1_200)
        self.assertEqual(pre.ordinary_divs, 9_000)
        # New K-1 components.
        self.assertEqual(pre.taxable_interest_k1, 750)
        self.assertEqual(pre.ordinary_divs_k1, 5_000)
        # New authoritative 1040 line 2b / 3b totals.
        self.assertEqual(pre.taxable_interest_total, 1_950)
        self.assertEqual(pre.ordinary_divs_total, 14_000)

    def test_totals_equal_1099_only_when_fanout_is_empty(self) -> None:
        """No K-1s at all: the totals collapse onto the 1099 components."""
        s = self._scenario_with_1099s()

        # Both the omitted-argument path and the explicit empty fanout must
        # behave identically (``compute_income_preamble`` substitutes
        # ``K1FanoutData.empty()`` when the argument is None).
        for label, kwargs in (
            ("omitted", {}),
            ("explicit-empty", {"k1_fanout": K1FanoutData.empty()}),
        ):
            with self.subTest(fanout=label):
                pre = f1040_spine.compute_income_preamble(
                    s, self.params, {}, **kwargs,
                )
                self.assertEqual(pre.taxable_interest_k1, 0)
                self.assertEqual(pre.ordinary_divs_k1, 0)
                self.assertEqual(pre.taxable_interest_total, 1_200)
                self.assertEqual(pre.ordinary_divs_total, 9_000)

    def test_totals_equal_k1_only_when_there_are_no_1099s(self) -> None:
        """No 1099-INT / 1099-DIV: the totals are the K-1 components alone.

        This is the case the pre-fix spine got most visibly wrong — line 2b
        and line 3b would both have been 0 despite real conduit income.
        """
        s = make_simple_scenario()
        s.form1099_int = []
        s.form1099_div = []

        pre = f1040_spine.compute_income_preamble(
            s,
            self.params,
            {},
            k1_fanout=_fanout(
                interest_items=(("Generic S-Corp Inc", 300.0),),
                dividend_items=(("Generic S-Corp Inc", 4_000.0),),
            ),
        )

        self.assertEqual(pre.taxable_interest, 0)
        self.assertEqual(pre.ordinary_divs, 0)
        self.assertEqual(pre.taxable_interest_total, 300)
        self.assertEqual(pre.ordinary_divs_total, 4_000)

    def test_interest_and_dividend_channels_do_not_cross(self) -> None:
        """A K-1 interest addition must not leak into the dividend total, and
        vice versa — the two fanout tuples are distinct channels.

        Deliberately asymmetric amounts (interest-only 700 on one side,
        dividend-only 2,500 on the other) so a copy-paste swap of the two
        fanout tuples in the implementation cannot pass.
        """
        s = make_simple_scenario()
        s.form1099_int = []
        s.form1099_div = []

        pre = f1040_spine.compute_income_preamble(
            s,
            self.params,
            {},
            k1_fanout=_fanout(
                interest_items=(("Generic S-Corp Inc", 700.0),),
                dividend_items=(("Generic S-Corp Inc", 2_500.0),),
            ),
        )

        self.assertEqual(pre.taxable_interest_total, 700)
        self.assertEqual(pre.ordinary_divs_total, 2_500)


class K1OrdinaryIncomeTotalsFromRealFanoutTests(unittest.TestCase):
    """Same totals, but with the fanout produced by the REAL Schedule E Part
    II compute from hand-authored ``ScheduleK1`` objects, rather than a
    hand-built ``K1FanoutData``.

    This closes the gap a hand-built fanout leaves open: that
    ``sch_e_part_ii`` actually routes ``ScheduleK1.interest_income`` and
    ``.ordinary_dividends`` into the two tuples the preamble reads.

    Scenario (all synthetic): TWO hand-authored S-corp K-1s —
      Generic S-Corp Inc:  interest 300,  ordinary dividends 4,000
      Generic Holdings Inc: interest 450, ordinary dividends 1,000
    plus one 1099-INT (1,200) and one 1099-DIV (9,000 ordinary).
    """

    def setUp(self) -> None:
        self.params = load_federal_params(2025)
        self.scenario = make_k1_scenario()
        self.scenario.form1099_int = [
            Form1099INT(payer="Generic Bank", interest=1_200.0),
        ]
        self.scenario.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=7_000.0,
        )]
        self.scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Generic S-Corp Inc",
                entity_ein="00-0000000",
                entity_type="s_corp",
                material_participation=True,
                ordinary_business_income=50_000.0,
                qbi_amount=50_000.0,
                interest_income=300.0,
                ordinary_dividends=4_000.0,
                qualified_dividends=3_000.0,
            ),
            ScheduleK1(
                entity_name="Generic Holdings Inc",
                entity_ein="00-0000000",
                entity_type="s_corp",
                material_participation=True,
                ordinary_business_income=10_000.0,
                qbi_amount=10_000.0,
                interest_income=450.0,
                ordinary_dividends=1_000.0,
                qualified_dividends=500.0,
            ),
        ]

    def test_preamble_totals_from_real_sch_e_fanout(self) -> None:
        _fields, fanout = form_sch_e_part_ii.compute(self.scenario, upstream={})

        # Guard the fixture itself: if these tuples were empty (as they would
        # be for an 1120-S-GENERATED K-1, whose Schedule K interest/dividend
        # boxes are structurally zero) the assertions below would pass
        # vacuously.
        self.assertEqual(len(fanout.sch_b_interest_additions), 2)
        self.assertEqual(len(fanout.sch_b_dividend_additions), 2)

        pre = f1040_spine.compute_income_preamble(
            self.scenario, self.params, {}, k1_fanout=fanout,
        )

        self.assertEqual(pre.taxable_interest, 1_200)
        self.assertEqual(pre.taxable_interest_k1, 750)
        self.assertEqual(pre.taxable_interest_total, 1_950)
        self.assertEqual(pre.ordinary_divs, 9_000)
        self.assertEqual(pre.ordinary_divs_k1, 5_000)
        self.assertEqual(pre.ordinary_divs_total, 14_000)

    def test_preamble_totals_agree_with_schedule_b(self) -> None:
        """The preamble's authoritative line 2b / 3b totals must equal what
        Schedule B — the form that itemizes the very same payers — reports.

        The 1040 and its own Schedule B disagreeing on the same return is
        precisely the defect this unit exists to close, so the agreement is
        asserted directly rather than inferred.
        """
        _fields, fanout = form_sch_e_part_ii.compute(self.scenario, upstream={})
        sch_b = form_sch_b.compute(self.scenario, upstream={"k1_fanout": fanout})
        pre = f1040_spine.compute_income_preamble(
            self.scenario, self.params, {}, k1_fanout=fanout,
        )

        self.assertEqual(pre.taxable_interest_total, sch_b["taxable_interest"])
        self.assertEqual(
            pre.ordinary_divs_total, sch_b["total_ordinary_dividends"],
        )
        # Pin the shared values too, so a change that breaks BOTH sides
        # identically cannot pass this test by agreeing on a wrong number.
        self.assertEqual(pre.taxable_interest_total, 1_950)
        self.assertEqual(pre.ordinary_divs_total, 14_000)


class K1OrdinaryIncomeRoundingMatchesScheduleBTests(unittest.TestCase):
    """The K-1 components must use Schedule B's summation semantics.

    ``sch_b.compute`` rounds EACH payer's amount to whole dollars and then
    sums the rounded figures (``tenforty/forms/sch_b.py``: each fanout
    addition is appended as ``irs_round(pa.amount)``, then ``total_interest
    = sum(p["amount"] ...)``). Summing raw amounts first and rounding once
    at the end is a DIFFERENT function whenever amounts carry cents, and
    would put the 1040 and its own Schedule B a dollar apart — the exact
    class of disagreement this unit exists to eliminate.

    Fixture: two K-1s at 100.50 interest and two at 250.50 dividends.
      per-payer rounding then sum: 101 + 101 = 202;  251 + 251 = 502
      sum then round once:         irs_round(201.0) = 201; irs_round(501.0) = 501
    The 1099 side is held at whole dollars so this isolates the K-1
    component (the 1099 components have their own long-standing
    round-once-at-the-end behavior, which this task does not change).
    """

    def setUp(self) -> None:
        self.params = load_federal_params(2025)
        self.scenario = make_k1_scenario()
        self.scenario.form1099_int = []
        self.scenario.form1099_div = []
        self.scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Generic S-Corp Inc",
                entity_ein="00-0000000",
                entity_type="s_corp",
                material_participation=True,
                ordinary_business_income=50_000.0,
                qbi_amount=50_000.0,
                interest_income=100.50,
                ordinary_dividends=250.50,
            ),
            ScheduleK1(
                entity_name="Generic Holdings Inc",
                entity_ein="00-0000000",
                entity_type="s_corp",
                material_participation=True,
                ordinary_business_income=10_000.0,
                qbi_amount=10_000.0,
                interest_income=100.50,
                ordinary_dividends=250.50,
            ),
        ]

    def test_k1_components_round_per_payer_like_schedule_b(self) -> None:
        _fields, fanout = form_sch_e_part_ii.compute(self.scenario, upstream={})
        sch_b = form_sch_b.compute(self.scenario, upstream={"k1_fanout": fanout})
        pre = f1040_spine.compute_income_preamble(
            self.scenario, self.params, {}, k1_fanout=fanout,
        )

        # 202 / 502, NOT the 201 / 501 that a single round-at-the-end yields.
        self.assertEqual(pre.taxable_interest_k1, 202)
        self.assertEqual(pre.ordinary_divs_k1, 502)
        self.assertEqual(pre.taxable_interest_total, 202)
        self.assertEqual(pre.ordinary_divs_total, 502)

        # ...and that is exactly what Schedule B itself reports.
        self.assertEqual(sch_b["taxable_interest"], 202)
        self.assertEqual(sch_b["total_ordinary_dividends"], 502)
        self.assertEqual(pre.taxable_interest_total, sch_b["taxable_interest"])
        self.assertEqual(
            pre.ordinary_divs_total, sch_b["total_ordinary_dividends"],
        )


# ---------------------------------------------------------------------------
# Task 4 — cross-path and end-to-end regression coverage.
#
# Everything above this line exercises ``compute_income_preamble`` (and the
# Schedule E Part II fanout that feeds it) directly. Everything below drives
# the REAL orchestrator end to end, because the defect this unit closed was
# not in the preamble's arithmetic — it was in what the 1040 spine did with
# the preamble's answer. A test that stops at the preamble cannot see that.
#
# ⚠️ SCOPE NOTE FOR EVERY CLASS BELOW — NATIVE-SPINE PATH ONLY.
# Every scenario here is a SINGLE filer, and that is load-bearing rather than
# incidental. ``_compute_1040_pipeline`` routes out-of-spine-scope scenarios
# (non-single filers, and any EIC-possible filer) to the XLSX workbook, which
# never calls ``compute_income_preamble`` at all: its line 2b/3b named ranges
# are 1099-only and the flattener's K-1 interest/dividend keys are dropped
# because ``F1040.INPUTS`` has no slot for them. So for THAT filer class a
# K-1's interest and ordinary dividends are still outside AGI, and the
# Schedule B gate still reads a 1099-only figure.
#
# That is PRE-EXISTING and out of this unit's scope — reaching it means
# teaching the workbook path about K-1 conduit income. It is chartered as
# follow-up unit (r). Nothing below asserts anything about the workbook path,
# deliberately: asserting the current behavior would bless it. Read every
# "must" below as "must, on the native spine".
# ---------------------------------------------------------------------------


def _hand_authored_k1(
    *,
    entity_name: str = "Generic S-Corp Inc",
    **income,
) -> ScheduleK1:
    """A hand-authored S-corp ``ScheduleK1`` with every income box at 0
    except the ones named in ``income``.

    FIXTURE RULE (see the module docstring): K-1s produced by tenforty's own
    1120-S pipeline carry STRUCTURALLY ZERO interest and dividends, so a
    fixture routed through that pipeline would exercise none of this code and
    would pass whether or not the totals are computed correctly. Every K-1 in
    this module is therefore constructed directly.
    """
    return ScheduleK1(
        entity_name=entity_name,
        entity_ein="00-0000000",
        entity_type="s_corp",
        material_participation=True,
        **income,
    )


class _OrchestratorTestCase(unittest.TestCase):
    """Base class supplying a real ``ReturnOrchestrator`` on a temp work dir."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name),
        )


def _mixed_source_scenario():
    """The canonical mixed-source scenario shared by Task 4's Steps 1, 3 and 4b.

    All figures synthetic/generic. 2025 single filer, standard deduction:

      W-2 wages                                        100,000
      1099-INT  "Generic Bank"          interest         2,000
      1099-DIV  "Generic Brokerage"     ord. dividends    5,000
                                        qual. dividends       0
      K-1       "Generic S-Corp Inc"    interest_income   3,000
                                        ordinary_dividends 6,000

    The K-1 carries NO ordinary_business_income and NO qbi_amount, so
    Schedule E Part II line 41 is 0, Schedule 1 line 10 is 0, and no Form
    8995 is emitted. There is no 1099-B and no K-1 capital gain, so
    Schedule D line 16 (and therefore line 21) is 0. That isolates the two
    lines under test: every dollar of total income above wages arrives on
    line 2b or line 3b.

    DERIVED FROM THE FORM, not read out of the code (IRC 1366(b) conduit
    treatment — an S corporation's interest and dividend items keep their
    character in the shareholder's hands, so they land on the shareholder's
    own lines 2b/3b exactly as a 1099 would):

      line 2b (taxable interest)   = 2,000 + 3,000 =  5,000
      line 3b (ordinary dividends) = 5,000 + 6,000 = 11,000
      line 3a (qualified dividends)                =      0
      line 9  (total income) = 100,000 + 5,000 + 11,000 = 116,000
      line 11 (AGI)          = 116,000 - 0 adjustments  = 116,000

    The K-1's contribution to AGI is 3,000 + 6,000 = 9,000; a 1099-only AGI
    (the pre-fix figure) would be 107,000.
    """
    s = make_k1_scenario()
    s.form1099_int = [Form1099INT(payer="Generic Bank", interest=2_000.0)]
    s.form1099_div = [Form1099DIV(
        payer="Generic Brokerage",
        ordinary_dividends=5_000.0,
        qualified_dividends=0.0,
    )]
    s.schedule_k1s = [_hand_authored_k1(
        interest_income=3_000.0,
        ordinary_dividends=6_000.0,
    )]
    return s


# Derived in _mixed_source_scenario's docstring. Named so a reader can see at
# a glance which figure each assertion is pinning.
MIXED_LINE_2B = 5_000
MIXED_LINE_3B = 11_000
MIXED_TOTAL_INCOME = 116_000
MIXED_AGI = 116_000
MIXED_AGI_WITHOUT_K1 = 107_000


class K1IncomeReachesLines2b3bAndAgiTests(_OrchestratorTestCase):
    """Task 4 Step 1 — the end-to-end test.

    On the native spine (see the SCOPE NOTE above this class — a non-single
    filer routes to the workbook, where this is still broken, follow-up unit
    (r)), a K-1's interest and ordinary dividends must reach 1040 lines 2b
    and 3b and be INSIDE adjusted gross income. Before this unit landed they
    reached the emitted Schedule B (via the Schedule E Part II fanout) but
    were silently dropped by the native spine, so the 1040 and its own
    Schedule B reported different totals on the same return and tax was
    understated.

    See ``_mixed_source_scenario`` for the scenario and the full derivation.
    """

    def setUp(self) -> None:
        super().setUp()
        self.scenario = _mixed_source_scenario()

    def test_fanout_actually_carries_the_k1_items(self) -> None:
        """Fixture guard, not a behavioral claim.

        If the Schedule E Part II fanout carried no interest/dividend
        additions for this K-1 — the situation for an 1120-S-GENERATED K-1,
        whose Schedule K interest and dividend boxes are structurally zero —
        every assertion in this class would still pass, vacuously, because
        the totals would collapse onto the 1099 components. This pins that
        the negative space is genuinely occupied.
        """
        _fields, fanout = form_sch_e_part_ii.compute(self.scenario, upstream={})
        self.assertEqual(len(fanout.sch_b_interest_additions), 1)
        self.assertEqual(len(fanout.sch_b_dividend_additions), 1)
        self.assertEqual(fanout.sch_b_interest_additions[0].amount, 3_000.0)
        self.assertEqual(fanout.sch_b_dividend_additions[0].amount, 6_000.0)

    def test_lines_2b_and_3b_are_the_1099_plus_k1_totals(self) -> None:
        """1040 line 2b = 5,000 and line 3b = 11,000, per the derivation.

        Both spellings of each line are asserted: ``interest_income`` /
        ``dividend_income`` are the spine's oracle-facing keys and
        ``taxable_interest`` / ``ordinary_dividends`` are the PDF-facing
        aliases. They are separate entries in the spine's output dict, and
        the CA Schedule CA kernel reads the PDF-facing pair while the CLI
        summary reads the other — so a regression that fixed only one
        spelling would leave the two halves of the packet disagreeing.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(results["taxable_interest"], MIXED_LINE_2B)
        self.assertEqual(results["interest_income"], MIXED_LINE_2B)
        self.assertEqual(results["ordinary_dividends"], MIXED_LINE_3B)
        self.assertEqual(results["dividend_income"], MIXED_LINE_3B)

    def test_agi_includes_the_k1_interest_and_dividends(self) -> None:
        """1040 line 9 = 116,000 and line 11 = 116,000, per the derivation.

        The K-1's 9,000 is the whole point: the pre-fix spine published the
        corrected totals on lines 2b/3b but summed the 1099-ONLY components
        into total income, so AGI came out at 107,000 while the printed
        lines 2b/3b said otherwise — an internally inconsistent 1040.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(results["total_income"], MIXED_TOTAL_INCOME)
        self.assertEqual(results["agi"], MIXED_AGI)
        self.assertEqual(
            results["agi"] - MIXED_AGI_WITHOUT_K1, 9_000,
            "AGI does not include the K-1's 3,000 of interest and 6,000 of "
            "ordinary dividends. Under IRC 1366(b) those items keep their "
            "character in the shareholder's hands and belong on 1040 lines "
            "2b/3b, inside total income. An AGI of "
            f"{MIXED_AGI_WITHOUT_K1} means total_income is summing the "
            "1099-only components (preamble.taxable_interest / "
            ".ordinary_divs) instead of the authoritative totals "
            "(.taxable_interest_total / .ordinary_divs_total).",
        )

    def test_compute_path_preamble_agrees_with_the_pipeline(self) -> None:
        """The orchestrator's own compute-time preamble — the one that feeds
        the Form 8995 / Form 8582 pre-pass stub — must land on the same
        totals and the same AGI as the finished spine results.

        These are two different producers of the same figures (the pre-pass
        builds a stub dict from ``compute_income_preamble``; the spine builds
        its output dict from a second call to the same helper with the full
        schedule results), and a return whose 8995 was computed against one
        AGI and whose 1040 printed another would be internally inconsistent.
        """
        schedules, fanout = self.orchestrator._compute_native_schedules(
            self.scenario,
        )
        preamble = f1040_spine.compute_income_preamble(
            self.scenario,
            load_federal_params(2025),
            schedules,
            k1_fanout=fanout,
        )
        results = self.orchestrator._compute_1040_pipeline(self.scenario)

        self.assertEqual(preamble.taxable_interest_total, MIXED_LINE_2B)
        self.assertEqual(preamble.ordinary_divs_total, MIXED_LINE_3B)
        self.assertEqual(preamble.agi, MIXED_AGI)
        self.assertEqual(preamble.agi, results["agi"])


class K1VersusForm1099ChannelEquivalenceTests(_OrchestratorTestCase):
    """Task 4 Step 2 — the channel-equivalence test.

    IDENTICAL dollars of interest and ordinary dividends must produce an
    IDENTICAL return whether they arrive on a K-1 or on 1099s. That is the
    defect's economics stated directly: under IRC 1366(b) an S corporation's
    interest and dividend items pass through with their character intact, so
    the shareholder's 1040 cannot care which piece of paper reported them.
    Pre-fix the two channels diverged, because only the 1099 channel reached
    total income.

    ⚠️ TWO LIMITS ON THAT "cannot care" — it is what SHOULD hold, and this
    class pins it only where it actually does.

    1. Native spine only — see the SCOPE NOTE above this class. On the XLSX
       workbook path (non-single or EIC-possible filers) the two channels
       STILL diverge, because that path never consults the income preamble;
       that is follow-up unit (r).
    2. WHOLE-DOLLAR AMOUNTS ONLY, even on the native spine. The K-1 leg
       rounds per payer and the 1099 leg rounds once over the raw sum, so
       cent-bearing amounts can still diverge BY CHANNEL. Measured, single
       filer, native path, two payers @ 750.50 each:

           K-1 channel   line 2b = 1502   total income = 101,502   AGI = 101,502
           1099 channel  line 2b = 1501   total income = 101,501   AGI = 101,501

       Same root cause as the cross-path gap documented on
       ``K1ScheduleBEmitPathAgreesWith1040Tests`` (which carries the exact
       condition), and chartered to the same follow-up unit (n). Both
       fixtures below are whole-dollar, which is why the equality holds
       here; unlike the cross-path class this one has no guard asserting
       that, so a future editor adding cents gets a bare inequality. Worth
       adding a guard if this class ever grows fractional fixtures.

    Both scenarios (all figures synthetic/generic) are 2025 single filers on
    the standard deduction with the SAME ``TaxReturnConfig`` — including the
    same K-1 attestations — so the ONLY difference between them is which
    channel carries the money:

      W-2 wages                    100,000   (both)
      interest                       6,000   (K-1 box 4  |  1099-INT)
      ordinary dividends            14,000   (K-1 box 5a |  1099-DIV box 1a)
      qualified dividends                0   (both — keeps all of it ordinary)

    DERIVED FROM THE FORMS AND THE 2025 IRS SINGLE RATE SCHEDULE, not read
    out of the code:

      line 9 / line 11 (AGI) = 100,000 + 6,000 + 14,000 = 120,000
      line 15 (taxable income) = 120,000 - standard deduction 15,750
                               = 104,250
      No qualified dividends and no net capital gain, so the QDCGT
      worksheet has an empty preferential base and the entire 104,250 is
      taxed at ordinary rates. 104,250 is at/above the 100,000 Tax Table
      ceiling, so the rate schedule applies:
          11,925 x 10%  =  1,192.50
          36,550 x 12%  =  4,386.00   (11,925 -> 48,475)
          54,875 x 22%  = 12,072.50   (48,475 -> 103,350)
             900 x 24%  =    216.00   (103,350 -> 104,250)
                          ----------
                            17,867.00
      No SE income and wages below the 200,000 Additional Medicare
      threshold, so line 16 is the whole of total tax: 17,867.
    """

    INTEREST = 6_000.0
    ORDINARY_DIVIDENDS = 14_000.0
    EXPECTED_AGI = 120_000
    EXPECTED_TAXABLE_INCOME = 104_250
    EXPECTED_TOTAL_TAX = 17_867

    def setUp(self) -> None:
        super().setUp()

        self.k1_channel = make_k1_scenario()
        self.k1_channel.form1099_int = []
        self.k1_channel.form1099_div = []
        self.k1_channel.schedule_k1s = [_hand_authored_k1(
            interest_income=self.INTEREST,
            ordinary_dividends=self.ORDINARY_DIVIDENDS,
        )]

        # Same base builder, so the two configs are identical field for field.
        self.form1099_channel = make_k1_scenario()
        self.form1099_channel.form1099_int = [
            Form1099INT(payer="Generic Bank", interest=self.INTEREST),
        ]
        self.form1099_channel.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=self.ORDINARY_DIVIDENDS,
            qualified_dividends=0.0,
        )]
        self.form1099_channel.schedule_k1s = []

    def test_the_two_channels_produce_the_same_return(self) -> None:
        """Same dollars, same AGI, same taxable income, same tax.

        The equality assertions are the durable invariant — they hold under
        any future retune of rates or the standard deduction, because both
        sides move together. The literal figures alongside them stop a
        regression that breaks BOTH channels identically from passing by
        agreeing on a wrong number.
        """
        k1_results = self.orchestrator._compute_1040_pipeline(self.k1_channel)
        f1099_results = self.orchestrator._compute_1040_pipeline(
            self.form1099_channel,
        )

        for key in ("total_income", "agi", "taxable_income", "total_tax"):
            with self.subTest(key=key):
                self.assertEqual(
                    k1_results[key], f1099_results[key],
                    f"1040 {key} differs by channel: routing the SAME "
                    f"{self.INTEREST:,.0f} of interest and "
                    f"{self.ORDINARY_DIVIDENDS:,.0f} of ordinary dividends "
                    f"through a K-1 gives {k1_results[key]}, through 1099s "
                    f"gives {f1099_results[key]}. Under IRC 1366(b) these "
                    "items pass through with their character intact, so the "
                    "two must be identical; a difference means the K-1 "
                    "channel is being dropped somewhere between the "
                    "Schedule E Part II fanout and 1040 line 9.",
                )

        # Independently derived (see the class docstring), asserted on BOTH
        # sides so neither channel can drift while matching the other.
        for label, results in (
            ("k1", k1_results), ("form1099", f1099_results),
        ):
            with self.subTest(channel=label):
                self.assertEqual(results["agi"], self.EXPECTED_AGI)
                self.assertEqual(
                    results["taxable_income"], self.EXPECTED_TAXABLE_INCOME,
                )
                self.assertEqual(
                    results["total_tax"], self.EXPECTED_TOTAL_TAX,
                )


class K1ScheduleBEmitPathAgreesWith1040Tests(_OrchestratorTestCase):
    """Task 4 Step 3 — the CROSS-PATH test (standing policy).

    The emitted Schedule B and the emitted 1040 travel in the SAME packet.
    Schedule B is the itemization the IRS reads against 1040 lines 2b/3b.
    Nothing in this repo compared them across the two paths before, and that
    gap is what let the previous unit's regression ship: the compute path and
    the PDF-emit path build DIFFERENT upstream dicts from different
    producers, so a value can be right on one and wrong on the other while
    every unit test stays green.

    The emit side here is built the way
    ``ReturnOrchestrator._federal_individual_emit_specs`` builds it — the
    finished 1040 results dict plus a hoisted Schedule E Part II fanout —
    rather than by hand, so it exercises the real seam.

    ⚠️ SCOPE OF THE INVARIANT — READ BEFORE STRENGTHENING THIS TEST.
    "Schedule B agrees with lines 2b/3b to the dollar" is NOT true in
    general today. Whole-dollar payer amounts are a SUFFICIENT condition for
    it, and that is the condition this class relies on — every fixture here
    is whole-dollar by construction, pinned by
    ``test_fixture_is_whole_dollar_by_construction``.

    Whole dollars are sufficient but NOT necessary, and the guard asserts
    that simple sufficient condition rather than the exact one, because "no
    fractional amounts" is what a fixture author can actually keep true.

    EXACT CONDITION — stated because this boundary has now been mis-stated
    three times (twice by the controller, once by me), each time by guessing
    at it from a couple of examples. Derived, then brute-force verified in
    exact rational arithmetic over 1,210,000 cases — all 2-payer and all
    3-payer cent combinations exhaustively, plus 200,000 random returns of
    1-20 payers — with ZERO mismatches:

        Let e_i = irs_round(a_i) - a_i be a payer's rounding error, which
        lies in (-0.50, +0.50]. The two conventions AGREE exactly when
        sum(e_i) also lies in (-0.50, +0.50]. Otherwise they diverge, by
        however many whole dollars sum(e_i) escapes that window by.

    Three consequences, each measured, and each contradicting a plausible
    guess someone has already made about this:

      * TWO OR MORE fractional payers is NECESSARY. One fractional payer
        among whole-dollar ones can never diverge (verified over every cent
        fraction). But it is NOT SUFFICIENT:
            two @ 100.10  ->  200 vs 200, agree   (errors -0.10 each)
            two @ 100.25  ->  201 vs 200, differ  (errors -0.25 each)
      * The magnitude is NOT capped at one dollar; it grows with the number
        of payers:  ten @ 0.49 -> 5 vs 0 (five dollars);
                    a hundred @ 0.49 -> 49 vs 0.
      * The DIRECTION is not fixed either. Schedule B can be higher OR lower
        than 1040 line 2b:  ten @ 0.51 -> Sch B five dollars HIGHER;
                            ten @ 0.49 -> Sch B five dollars LOWER.

    The reason is a rounding-convention split. ``sch_b.compute`` rounds EACH
    payer's amount and sums the rounded figures. This unit matched that on
    the K-1 leg (see ``K1OrdinaryIncomeRoundingMatchesScheduleBTests``), but
    the 1099 leg of ``compute_income_preamble`` still rounds ONCE over the
    raw sum — ``irs_round(sum(f.interest for f in scenario.form1099_int))``.
    Those are different functions the moment cents are involved. Measured on
    the native path:

        two 1099-INTs @ 100.50, two 1099-DIVs @ 250.50, no K-1
            1040 line 2b = 201   Schedule B line 4 = 202
            1040 line 3b = 501   Schedule B line 6 = 502
        the same, plus a K-1 @ 100.50 interest / 250.50 dividends
            1040 line 2b = 302   Schedule B line 4 = 303
        ONE 1099-INT @ 2,000.50, no K-1  (both conventions coincide)
            1040 line 2b = 2001  Schedule B line 4 = 2001

    Note the K-1 leg adds the SAME 101 / 251 to both sides — the entire $1
    divergence is the 1099 leg, the leg this unit deliberately did not
    touch. Correcting it moves ``total_income`` and therefore a real
    taxpayer's tax, which needs its own oracle-checked unit. **That is
    chartered as follow-up unit (n).**

    (Careful about what a fractional fixture would actually break here.
    Giving THIS fixture's single 1099-INT cents does NOT break the
    cross-path equality — one fractional payer per line agrees, per the
    exact condition above — it breaks the pinned literals MIXED_LINE_2B /
    MIXED_LINE_3B instead. Reaching a genuine cross-path divergence takes a
    SECOND fractional payer on the same line. Both failures are worth
    avoiding, which is why the guard asks for whole dollars outright rather
    than trying to encode the exact condition.)

    Per team-lead's ruling this is left as a NAMED GAP rather than an xfail:
    a documented boundary plus a ledgered unit beats an expected-failure
    marker that nobody owns. Do not widen the fixture to fractional amounts
    to "prove" the gap — that converts a ledgered follow-up into red CI.

    See ``_mixed_source_scenario`` for the scenario and the derivation:
    line 2b = 5,000, line 3b = 11,000.
    """

    def setUp(self) -> None:
        super().setUp()
        self.scenario = _mixed_source_scenario()

    def _emit_path_sch_b(self, results: dict) -> dict:
        _part_ii_fields, fanout = form_sch_e_part_ii.compute(
            self.scenario, upstream={},
        )
        return form_sch_b.compute(
            self.scenario,
            upstream={"f1040": results, "k1_fanout": fanout},
        )

    def test_fixture_is_whole_dollar_by_construction(self) -> None:
        """Pin the precondition the equality test depends on.

        The cross-path equality below holds only for whole-dollar payer
        amounts (see the class docstring, and follow-up unit (n)). Without
        this guard, a future editor who changes a fixture amount to, say,
        2,000.50 would get a bare off-by-one failure and no way to tell a
        real regression from the known 1099-leg rounding split. With it,
        they get told which is which.
        """
        amounts = (
            [("1099-INT", f.payer, f.interest)
             for f in self.scenario.form1099_int]
            + [("1099-DIV", f.payer, f.ordinary_dividends)
               for f in self.scenario.form1099_div]
            + [("K-1 interest", k.entity_name, k.interest_income)
               for k in self.scenario.schedule_k1s]
            + [("K-1 dividends", k.entity_name, k.ordinary_dividends)
               for k in self.scenario.schedule_k1s]
        )
        for source, payer, amount in amounts:
            with self.subTest(source=source, payer=payer):
                self.assertEqual(
                    amount, int(amount),
                    f"{source} payer {payer!r} carries a fractional amount "
                    f"({amount}). This class's assertions are guaranteed "
                    "only for whole-dollar amounts. Two things can break: "
                    "the pinned literals MIXED_LINE_2B / MIXED_LINE_3B move "
                    "as soon as ANY amount gains cents, and the cross-path "
                    "equality can break once TWO OR MORE payers on the SAME "
                    "line carry cents — the 1099 leg of "
                    "compute_income_preamble rounds once over the raw sum "
                    "while Schedule B rounds per payer. Two or more "
                    "fractional payers is necessary but not sufficient for "
                    "that second failure, and when it does occur the gap is "
                    "not capped at one dollar and can fall in either "
                    "direction; see this class's docstring for the exact "
                    "condition. That divergence is REAL and PRE-EXISTING, "
                    "chartered as follow-up unit (n) — it is not something "
                    "this test should be made to demonstrate.",
                )

    def test_whole_dollar_schedule_b_totals_equal_1040_lines_2b_and_3b(
        self,
    ) -> None:
        """On a whole-dollar return, the emitted Schedule B's totals equal
        the emitted 1040's lines 2b/3b.

        Scoped to whole dollars deliberately — see the class docstring for
        why the general claim is false today and where it is chartered.
        """
        results = self.orchestrator._compute_1040_pipeline(self.scenario)
        sch_b = self._emit_path_sch_b(results)

        for label, sch_b_key, f1040_key in (
            ("interest (Sch B line 4 / 1040 line 2b)",
             "total_interest", "taxable_interest"),
            ("interest (Sch B taxable-interest alias)",
             "taxable_interest", "taxable_interest"),
            ("ordinary dividends (Sch B line 6 / 1040 line 3b)",
             "total_ordinary_dividends", "ordinary_dividends"),
        ):
            with self.subTest(line=label):
                self.assertEqual(
                    sch_b[sch_b_key], results[f1040_key],
                    f"the emitted Schedule B and the emitted 1040 disagree on "
                    f"{label}: Schedule B says {sch_b[sch_b_key]}, the 1040 "
                    f"says {results[f1040_key]}. They would ship in the same "
                    "packet, with Schedule B itemizing the very payers the "
                    "1040 line totals. This fixture is whole-dollar, so the "
                    "known 1099-leg rounding split (follow-up unit (n)) "
                    "cannot explain a difference here — treat it as a real "
                    "regression in which total the 1040 publishes.",
                )

        # Pin the shared figures against the independent derivation, so a
        # change that breaks both sides identically cannot pass by agreeing.
        self.assertEqual(sch_b["total_interest"], MIXED_LINE_2B)
        self.assertEqual(sch_b["total_ordinary_dividends"], MIXED_LINE_3B)


class ScheduleBGateCountsK1IncomeTests(_OrchestratorTestCase):
    """Task 4 Step 4 — the Schedule B emission gate (P-3).

    ON THE NATIVE-SPINE PATH the IRS Part I / Part II filing threshold is
    applied to the 1040 line 2b / 3b TOTAL, not to the 1099 slice.
    Historically the gate summed only the 1099s, so a return with 1,400 on a
    1099-INT and 1,400 on a K-1 had a true 2,800 Schedule B total, failed the
    gate, and was emitted with NO Schedule B at all -- the taxpayer's own
    itemization of the income missing from the packet.

    ⚠️ SCOPE -- "native-spine path" above is load-bearing, not a hedge. Every
    scenario in this class is a SINGLE filer, which is what keeps it on the
    native spine. A non-single or EIC-possible filer routes to the XLSX
    workbook, whose line 2b/3b named ranges are 1099-only, so for that filer
    class the 1,400 + 1,400 case below is STILL BROKEN and this class does not
    say otherwise. See the scope note on
    ``ReturnOrchestrator._should_emit_sch_b``; chartered as follow-up unit
    (r). There is deliberately no workbook-path test here: asserting the
    current workbook behavior would bless it.

    The three scenarios below share one shape (2025 single filer, W-2 wages
    100,000, no dividends anywhere) and differ ONLY in the two interest
    amounts, so the boundary pair is a genuine pair.

    ⚠️ DELIBERATELY OFF THE 1,500 BOUNDARY. Whether the gate should fire at
    exactly 1,500 or only ABOVE it is an open question on this program,
    ledgered separately and NOT settled by this unit. Every figure here is
    comfortably clear of 1,500 (totals of 1,200 / 1,600 / 2,800) so these
    assertions are correct under EITHER resolution and pre-judge neither.
    """

    def _scenario(self, *, form1099_interest: float, k1_interest: float):
        s = make_k1_scenario()
        s.form1099_int = [
            Form1099INT(payer="Generic Bank", interest=form1099_interest),
        ]
        s.form1099_div = []
        s.schedule_k1s = [_hand_authored_k1(interest_income=k1_interest)]
        return s

    def _gate(self, scenario) -> bool:
        """Run the real gate against the real finished 1040 results, exactly
        as ``_federal_individual_emit_specs`` does."""
        results = self.orchestrator._compute_1040_pipeline(scenario)
        return self.orchestrator._should_emit_sch_b(scenario, results)

    def test_boundary_pair_under_and_over_the_threshold(self) -> None:
        """A boundary PAIR, so the negative half is provably reachable.

        Both scenarios carry 600 of 1099 interest and differ only in the
        K-1's interest:

          UNDER: K-1   600 -> line 2b = 1,200 -> no Schedule B
          OVER:  K-1 1,000 -> line 2b = 1,600 -> Schedule B

        The OVER case demonstrates that "Schedule B is emitted" is an
        outcome this scenario shape CAN produce, which is what makes the
        UNDER case a real constraint rather than a decoration. The pair also
        catches an inverted comparison, which a single large-magnitude
        scenario cannot.
        """
        under = self._scenario(form1099_interest=600.0, k1_interest=600.0)
        over = self._scenario(form1099_interest=600.0, k1_interest=1_000.0)

        # Fixture guard: the two really do straddle the threshold on line 2b.
        self.assertEqual(
            self.orchestrator._compute_1040_pipeline(under)["taxable_interest"],
            1_200,
        )
        self.assertEqual(
            self.orchestrator._compute_1040_pipeline(over)["taxable_interest"],
            1_600,
        )

        self.assertFalse(
            self._gate(under),
            "Schedule B was emitted for a return whose TOTAL interest is "
            "1,200 -- comfortably below the 1,500 filing threshold on every "
            "reading of it. The gate is over-emitting.",
        )
        self.assertTrue(
            self._gate(over),
            "Schedule B was NOT emitted for a return whose TOTAL interest is "
            "1,600. Since the otherwise-identical 1,200 scenario correctly "
            "produces no Schedule B, the gate is reading a partial total.",
        )

    def test_split_across_channels_still_clears_the_threshold(self) -> None:
        """The P-3 regression case: 1,400 on a 1099 and 1,400 on a K-1.

        NEITHER channel clears 1,500 alone; the TOTAL, 2,800, clears it
        comfortably. Under the historic 1099-only gate this return was
        emitted with no Schedule B whatsoever. This is the scenario the gate
        fix exists for, and it is the one assertion here that a 1099-only
        gate cannot satisfy.
        """
        s = self._scenario(form1099_interest=1_400.0, k1_interest=1_400.0)
        results = self.orchestrator._compute_1040_pipeline(s)

        self.assertEqual(results["taxable_interest"], 2_800)
        self.assertTrue(
            self.orchestrator._should_emit_sch_b(s, results),
            "Schedule B was NOT emitted for a return with 1,400 of 1099 "
            "interest and 1,400 of K-1 interest. 1040 line 2b is 2,800, well "
            "over the 1,500 threshold; the gate is summing the 1099s alone "
            "instead of reading the published line 2b/3b totals.",
        )


class K1IncomeFlowsThroughToScheduleCaColumnATests(_OrchestratorTestCase):
    """Task 4 Step 4b — the CA flow-through, in exactly ONE assertion.

    California starts from federal AGI, and ``sch_ca.py`` maps the federal
    ``taxable_interest`` / ``ordinary_dividends`` output keys straight into
    Schedule CA (540) Part I Section A lines 2 and 3, column A. Those column-A
    figures moving with the corrected federal totals is the POINT of this
    change, not a side effect -- so it is pinned here rather than left to be
    discovered by someone diffing CA output.

    Scope is deliberately one assertion. Broader CA verification is covered
    by the merge-gate regression against real CA returns.

    See ``_mixed_source_scenario``: line 2b = 5,000, line 3b = 11,000.
    """

    def test_sch_ca_part_i_section_a_lines_2_and_3_column_a(self) -> None:
        scenario = _mixed_source_scenario()
        federal_results = self.orchestrator._compute_1040_pipeline(scenario)
        sch_ca = form_sch_ca.compute(
            CA540Return(divergences=[]), federal_results, 2025,
        )

        self.assertEqual(
            {
                "line 2 col A": sch_ca.get("sch_ca_line_part_i_a_2_col_a"),
                "line 3 col A": sch_ca.get("sch_ca_line_part_i_a_3_col_a"),
            },
            {"line 2 col A": MIXED_LINE_2B, "line 3 col A": MIXED_LINE_3B},
            "Schedule CA (540) Part I Section A column A does not carry the "
            "corrected federal totals. Column A is a pure passthrough of "
            "federal 1040 lines 2b/3b; the 1099-only figures here would be "
            "2,000 and 5,000. CA conforms to the federal treatment of "
            "pass-through interest and dividends, so the CA return must "
            "follow the federal correction.",
        )


#: ``ScheduleK1`` fields that carry identity rather than money. Probing them
#: with a 1.0 would be meaningless, so the discovery below skips them.
_K1_NON_INCOME_FIELDS = frozenset({
    "entity_name", "entity_ein", "entity_type", "material_participation",
})


def _probe_k1_positive_income() -> tuple[tuple[str, ...], dict[str, float]]:
    """Discover, BEHAVIORALLY, which ``ScheduleK1`` fields the routing gate's
    ``_k1_positive_income`` enumerates.

    Probes each non-identity field of ``ScheduleK1`` by setting it (and only
    it) to 1.0 and asking ``_k1_positive_income`` what it returns. No source
    or AST parsing: the discovery survives a refactor of that function and
    automatically picks up any field added to it later.

    Returns ``(counted, anomalous)``:

    - ``counted`` — fields whose probe contributed exactly 1.0. These are the
      fields the gate enumerates once, and they are what the detector below
      iterates.
    - ``anomalous`` — field name -> contribution, for any field whose probe
      returned something OTHER than 0.0 or 1.0.

    ``anomalous`` exists because of a blind spot found in review on
    2026-08-17. The probe originally kept a field only on an exact ``== 1.0``
    match, which meant a field the gate DOUBLE-COUNTED (contribution 2.0, or
    any scaled/clamped variant) silently fell out of the discovered set — and
    the detector then stopped checking that field entirely. The single most
    alarming thing the gate could do to a field was the one thing that made
    the detector look away from it. Surfacing anomalies instead of dropping
    them turns that silence into a named failure (see
    ``test_discovery_probe_finds_the_gate_fields``).

    Deliberately returns data rather than asserting: this runs inside test
    methods, never at import, so a future anomaly is a FAILURE in one test
    and never a collection-time ERROR that takes the rest of the file down
    with it.
    """
    counted: list[str] = []
    anomalous: dict[str, float] = {}
    for f in dataclasses.fields(ScheduleK1):
        if f.name in _K1_NON_INCOME_FIELDS:
            continue
        contribution = _k1_positive_income(_hand_authored_k1(**{f.name: 1.0}))
        if contribution == 1.0:
            counted.append(f.name)
        elif contribution != 0.0:
            anomalous[f.name] = contribution
    return tuple(counted), anomalous


class K1RoutingGateIncomeAlsoReachesTotalIncomeTests(_OrchestratorTestCase):
    """Task 4 Step 4c — the mechanical partial-total detector.

    THE INVARIANT: every K-1 income field the ROUTING GATE counts must also
    reach 1040 line 9 (total income).

    ``_scenario_in_spine_scope`` builds an ``agi_estimate`` from
    ``_k1_positive_income`` to decide whether a return is high-income enough
    to bypass the EIC-eligibility check and stay on the native spine. That
    estimate is the routing gate's own model of "income this K-1 produces".
    If the gate counts a channel that the real AGI computation drops, the
    codebase is holding two contradictory beliefs about the same dollars --
    and the one that reaches the taxpayer's return is the wrong one. That
    asymmetry is the mechanical signature of the partial-total defect species
    this unit closed, and it is checkable without knowing anything about
    which channel is currently broken.

    THIS IS THE TEST THAT WOULD HAVE CAUGHT THIS UNIT'S DEFECT. Before it
    landed, ``interest_income`` and ``ordinary_dividends`` were counted by
    ``_k1_positive_income`` and dropped by ``total_income`` -- so the
    detector's negative space is not hypothetical, it was occupied by this
    very unit's bug.

    Method: a baseline scenario (2025 single filer, W-2 wages 100,000, one
    hand-authored S-corp K-1 with every income box at zero, no 1099s) has a
    known total income of 100,000. For each discovered field, the SAME
    scenario is rebuilt with that one field at 10,000 and nothing else
    changed. Each of these boxes is gross income under IRC 61 reaching the
    shareholder under the IRC 1366 conduit rules, so adding 10,000 to any one
    of them must raise 1040 line 9 by exactly 10,000. (10,000 is a gain in
    the two capital-gain boxes, so the IRC 1211(b) loss cap never engages and
    the expected delta is unconditional.)

    ALLOWLIST: empty, deliberately. If a field genuinely does not belong in
    total income as a matter of tax law, an entry may be added here WITH that
    justification in writing. An entry added merely to turn the test green
    would convert a live defect into a permanent, documented lie -- if a
    field fails, that is a finding to report, not a chore to silence.
    """

    PROBE_AMOUNT = 10_000
    BASELINE_TOTAL_INCOME = 100_000

    #: field name -> written tax-law justification for exclusion. See the
    #: class docstring before adding anything here.
    LEGITIMATELY_EXCLUDED: dict[str, str] = {}

    def _scenario(self, **k1_income):
        s = make_k1_scenario()
        s.form1099_int = []
        s.form1099_div = []
        s.schedule_k1s = [_hand_authored_k1(**k1_income)]
        return s

    def test_baseline_is_wages_only(self) -> None:
        """Fixture guard: an all-zero K-1 contributes nothing, so every
        per-field delta below is attributable to that field alone."""
        results = self.orchestrator._compute_1040_pipeline(self._scenario())
        self.assertEqual(results["total_income"], self.BASELINE_TOTAL_INCOME)
        self.assertEqual(results["agi"], self.BASELINE_TOTAL_INCOME)

    def test_discovery_probe_finds_the_gate_fields(self) -> None:
        """Fixture guard for the discovery probe itself — TWO ways it can go
        quiet, both of which shrink the detector's coverage silently.

        1. AN EMPTY SET. If ``_probe_k1_positive_income`` returned no counted
           fields -- say because ``_k1_positive_income`` was refactored to
           take a different argument shape -- the detector below would
           iterate nothing and pass vacuously forever.

        2. AN ANOMALOUS CONTRIBUTION. A field whose probe returns anything
           other than 0.0 or 1.0 is not counted, so it drops out of the
           detected set and the detector stops examining it. The most
           important case is a contribution of 2.0: the gate DOUBLE-COUNTS
           that field. That is a defect in its own right -- the routing
           gate's agi_estimate is overstated for every return carrying it --
           and, left unguarded, it would make the detector look away from the
           one field most worth looking at. It fails loudly here instead.

        A field legitimately outside the gate contributes exactly 0.0 and is
        simply absent from ``counted``; that is normal and silent, which is
        why 0.0 is not an anomaly.
        """
        counted, anomalous = _probe_k1_positive_income()

        self.assertEqual(
            anomalous, {},
            "orchestrator._k1_positive_income gave an ANOMALOUS contribution "
            "for one or more ScheduleK1 fields. Each field was probed at "
            "exactly 1.0 in isolation, so a correctly-enumerated field "
            "contributes 1.0 and an unenumerated field contributes 0.0. "
            f"These contributed neither: {anomalous}. A contribution of 2.0 "
            "means the field is summed TWICE in that function, overstating "
            "the routing gate's agi_estimate; any other value means it is "
            "scaled or clamped. Fix _k1_positive_income -- do NOT relax this "
            "guard, because an anomalous field is EXCLUDED from the "
            "partial-total detector below, so leaving it anomalous silently "
            "removes it from that coverage as well.",
        )
        self.assertGreaterEqual(len(counted), 9)
        self.assertIn("interest_income", counted)
        self.assertIn("ordinary_dividends", counted)

    def test_every_routing_gate_income_field_reaches_total_income(self) -> None:
        """Each field the routing gate counts must move 1040 line 9 by the
        full amount placed on it.

        Coverage caveat, stated so it is not over-read: this iterates the
        fields the probe COUNTED. A field the gate handles anomalously (e.g.
        double-counts) is not in that set and is therefore not checked here
        — ``test_discovery_probe_finds_the_gate_fields`` is what makes that
        exclusion loud rather than silent.
        """
        counted, _anomalous = _probe_k1_positive_income()
        for field_name in counted:
            if field_name in self.LEGITIMATELY_EXCLUDED:
                continue
            with self.subTest(k1_field=field_name):
                scenario = self._scenario(
                    **{field_name: float(self.PROBE_AMOUNT)},
                )
                results = self.orchestrator._compute_1040_pipeline(scenario)
                delta = results["total_income"] - self.BASELINE_TOTAL_INCOME
                self.assertEqual(
                    delta, self.PROBE_AMOUNT,
                    f"PARTIAL-TOTAL DEFECT on ScheduleK1.{field_name}: "
                    f"{self.PROBE_AMOUNT:,} placed on that box moved 1040 "
                    f"line 9 (total income) by {delta:,}, not "
                    f"{self.PROBE_AMOUNT:,}.\n"
                    "INVARIANT: every K-1 income field enumerated by "
                    "orchestrator._k1_positive_income -- the routing gate's "
                    "own agi_estimate, which decides whether a return stays "
                    "on the native spine -- must also be reachable in the "
                    "spine's total_income summands. The gate already counts "
                    f"{field_name} as income; a total_income that does not "
                    "is the partial-total signature: two contradictory "
                    "beliefs about the same dollars, with the taxpayer-"
                    "visible one understating income.\n"
                    "FIX THE ROUTE, do not allowlist the field. An entry in "
                    "LEGITIMATELY_EXCLUDED is permitted only where exclusion "
                    "is correct as a matter of tax law, and must carry that "
                    "justification in writing.",
                )


if __name__ == "__main__":
    unittest.main()
