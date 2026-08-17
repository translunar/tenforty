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

import unittest

from tenforty.forms import f1040_spine
from tenforty.forms import sch_b as form_sch_b
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import (
    Form1099DIV,
    Form1099INT,
    K1FanoutData,
    PayerAmount,
    ScheduleK1,
)
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_k1_scenario, make_simple_scenario


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


if __name__ == "__main__":
    unittest.main()
