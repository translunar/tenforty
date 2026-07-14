"""Form 8962 (Premium Tax Credit) NATIVE oracle cross-check battery.

This is a hand-coded cross-check that diffs the production ``compute`` against
an independent hand-coded oracle (``reference_f8962``), plus spec invariants and
mutation checks that prove the battery can actually fail. It is NOT the
soffice/XLSX oracle path, so it is deliberately NOT marked with the ``oracle``
pytest marker.

Run FOREGROUND only:
    .venv/bin/python -m pytest tests/test_f8962_oracle_battery.py -q

The author sees only the two signatures + the reconciliation map (see the
battery-author brief); the bodies of ``tenforty/forms/f8962.py`` and
``tests/oracles/f8962_reference.py`` are intentionally not read here. We import
and CALL both and compare their outputs.
"""
import copy
import dataclasses
import unittest

from tenforty.forms.f8962 import compute
from tenforty.models import Form1095A, Form1095AMonth
from tenforty.params.f8962 import load
from tests.oracles.f8962_reference import reference_f8962

YEARS = (2021, 2022, 2023, 2024, 2025)

# Reconciliation map: (compute key, oracle key). Only these overlapping keys are
# diffed. f8962_line_1 / 2a / 3 and f8962_ui_box_checked have no oracle analog.
SCALAR_RECON = (
    ("f8962_line_4", "line4_poverty_line"),
    ("f8962_line_5", "line5_pct"),
    ("f8962_line_7", "line7_applicable_figure"),
    ("f8962_line_8a", "line8a_annual_contribution"),
    ("f8962_line_8b", "line8b_monthly_contribution"),
    ("f8962_line_24", "line24_total_ptc"),
    ("f8962_line_25", "line25_total_aptc"),
    ("f8962_line_26_net_ptc", "line26_net_ptc"),
    ("f8962_line_27", "line27_excess_aptc"),
    ("f8962_line_28", "line28_repayment_limitation"),
    ("f8962_line_29_repayment", "line29_excess_aptc_repayment"),
)

# Monthly cell letter -> oracle dict key.
MONTH_CELLS = (
    ("a", "col_a_premium"),
    ("b", "col_b_slcsp"),
    ("c", "col_c_contribution"),
    ("d", "col_d_max_assistance"),
    ("e", "col_e_ptc"),
    ("f", "col_f_aptc"),
)


def month(premium=0.0, slcsp=0.0, aptc=0.0):
    return Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc)


def block(months, *, ui=False, tax_exempt_interest=0.0):
    assert len(months) == 12
    return Form1095A(
        months=tuple(months),
        received_unemployment_2021=ui,
        tax_exempt_interest=tax_exempt_interest,
    )


def uniform_block(premium, slcsp, aptc, *, ui=False):
    return block([month(premium, slcsp, aptc) for _ in range(12)], ui=ui)


def magi_for_pct(pct, year):
    """MAGI (whole dollars) targeting ``pct`` percent of the single FPL."""
    return round(pct / 100 * load(year).fpl_single_48)


class _DiffMixin:
    """Shared compute-vs-oracle reconciliation, usable under mutation too."""

    def reconcile(self, blk, magi, year, params=None):
        """Assert every reconciled key is EQUAL between compute and oracle.

        Returns the (compute, oracle) output pair for further invariant checks.
        """
        p = params if params is not None else load(year)
        c = compute(blk, magi, year, p)
        r = reference_f8962(blk, magi, year)

        for ck, rk in SCALAR_RECON:
            self.assertEqual(
                c.get(ck),
                r.get(rk),
                msg=f"year={year} magi={magi} scalar {ck}<->{rk}",
            )

        # Compare a month's cells ONLY when compute emitted that month.
        for n in range(1, 13):
            if f"f8962_month_{n}_a" not in c:
                continue
            om = r["monthly"][n - 1]
            for letter, okey in MONTH_CELLS:
                self.assertEqual(
                    c[f"f8962_month_{n}_{letter}"],
                    om[okey],
                    msg=f"year={year} magi={magi} month {n} col_{letter}<->{okey}",
                )
        return c, r


# ---------------------------------------------------------------------------
# Scenario matrix (spec §7) x every year.
# ---------------------------------------------------------------------------
class ScenarioMatrixTests(_DiffMixin, unittest.TestCase):
    def test_full_year_uniform(self):
        for year in YEARS:
            with self.subTest(year=year):
                blk = uniform_block(900.0, 850.0, 500.0)
                self.reconcile(blk, magi_for_pct(250, year), year)

    def test_partial_year_some_months_zero(self):
        # Coverage only Mar..Aug; other months entirely zero.
        for year in YEARS:
            with self.subTest(year=year):
                months = [month() for _ in range(12)]
                for i in range(2, 8):
                    months[i] = month(820.0, 780.0, 460.0)
                self.reconcile(block(months), magi_for_pct(230, year), year)

    def test_partial_year_ragged(self):
        # Non-uniform premiums/aptc across the covered months.
        for year in YEARS:
            with self.subTest(year=year):
                months = [month() for _ in range(12)]
                months[0] = month(700.0, 690.0, 300.0)
                months[3] = month(950.0, 900.0, 700.0)
                months[4] = month(950.0, 900.0, 0.0)
                months[9] = month(600.0, 610.0, 250.0)
                self.reconcile(block(months), magi_for_pct(310, year), year)

    def test_zero_coverage(self):
        for year in YEARS:
            with self.subTest(year=year):
                blk = block([month() for _ in range(12)])
                c, r = self.reconcile(blk, magi_for_pct(220, year), year)
                # An all-zero block -> all outputs zero.
                self.assertEqual(c["f8962_line_24"], 0)
                self.assertEqual(c["f8962_line_25"], 0)
                self.assertEqual(c["f8962_line_26_net_ptc"], 0)
                self.assertEqual(c["f8962_line_27"], 0)
                self.assertEqual(c["f8962_line_29_repayment"], 0)

    def test_net_ptc_case(self):
        # APTC well below the allowed PTC -> taxpayer is owed net PTC (line 26).
        for year in YEARS:
            with self.subTest(year=year):
                blk = uniform_block(900.0, 850.0, 200.0)
                c, r = self.reconcile(blk, magi_for_pct(200, year), year)
                self.assertGreater(c["f8962_line_26_net_ptc"], 0)
                self.assertEqual(c["f8962_line_29_repayment"], 0)

    def test_capped_repayment_case(self):
        # APTC above allowed PTC at a sub-400% band -> excess APTC repayment,
        # subject to the per-band cap (line 28 not None).
        for year in YEARS:
            with self.subTest(year=year):
                blk = uniform_block(700.0, 650.0, 640.0)
                c, r = self.reconcile(blk, magi_for_pct(250, year), year)
                self.assertGreater(c["f8962_line_27"], 0)
                self.assertIsNotNone(c["f8962_line_28"])
                self.assertGreater(c["f8962_line_29_repayment"], 0)

    def test_uncapped_over_400(self):
        # >= 400% FPL -> no repayment cap (line 28 is None).
        for year in YEARS:
            with self.subTest(year=year):
                blk = uniform_block(800.0, 750.0, 400.0)
                c, r = self.reconcile(blk, magi_for_pct(500, year), year)
                self.assertIsNone(c["f8962_line_28"])

    def test_2021_ui_flag_on_and_off(self):
        # 2021 unemployment rule: flat 133% household-income treatment.
        blk_on = uniform_block(900.0, 850.0, 400.0, ui=True)
        blk_off = uniform_block(900.0, 850.0, 400.0, ui=False)
        magi = magi_for_pct(300, 2021)
        c_on, _ = self.reconcile(blk_on, magi, 2021)
        c_off, _ = self.reconcile(blk_off, magi, 2021)
        self.assertTrue(c_on["f8962_ui_box_checked"])
        self.assertFalse(c_off["f8962_ui_box_checked"])
        self.assertEqual(c_on["f8962_line_5"], 133)

    def test_2021_ui_flag_below_133(self):
        # Locks in the corrected flat-133 rule: even at true percentages BELOW
        # 133%, the UI flag pins line 5 to 133 (never lower).
        for pct in (105, 110, 120, 132):
            with self.subTest(pct=pct):
                blk = uniform_block(600.0, 620.0, 250.0, ui=True)
                magi = magi_for_pct(pct, 2021)
                c, _ = self.reconcile(blk, magi, 2021)
                self.assertEqual(c["f8962_line_5"], 133)
                self.assertTrue(c["f8962_ui_box_checked"])

    def test_magi_at_repayment_cap_band_boundaries(self):
        # MAGI at each repayment cap-band boundary +/-1 (bands keyed on line-5
        # FPL%: 200, 300, 400). Use a repayment scenario so the cap actually
        # engages, and diff every reconciled key across the boundary.
        for year in YEARS:
            for boundary in (200, 300, 400):
                for delta in (-1, 0, +1):
                    pct = boundary + delta
                    with self.subTest(year=year, boundary=boundary, delta=delta):
                        blk = uniform_block(700.0, 650.0, 640.0)
                        self.reconcile(blk, magi_for_pct(pct, year), year)

    def test_line5_floor_and_ceiling_edges(self):
        # Applicable-figure table domain edges (floor 150%, ceiling 400%) and
        # +/-1 around each, plus a genuinely-below-floor case (120%) and a
        # well-above-ceiling case (500%). Post-fix these must all reconcile.
        for year in YEARS:
            for pct in (120, 149, 150, 151, 399, 400, 401, 500):
                with self.subTest(year=year, pct=pct):
                    blk = uniform_block(820.0, 780.0, 430.0)
                    self.reconcile(blk, magi_for_pct(pct, year), year)


# ---------------------------------------------------------------------------
# Per-year 400%-boundary triplet (team-lead mandated).
# ---------------------------------------------------------------------------
class Boundary400Tests(_DiffMixin, unittest.TestCase):
    def test_400pct_triplet_expected_from_oracle(self):
        # For each year: MAGI = 4*fpl exactly, 4*fpl+1, 4*fpl-1. Assert
        # compute == oracle at each. The exact-4*fpl line-5 DIFFERS by year
        # (2021 -> 401 inclusive; 2022-2025 -> 400 strict) -- do NOT hardcode:
        # take the expected from the ORACLE side and assert compute equals it.
        for year in YEARS:
            fpl = load(year).fpl_single_48
            for magi in (4 * fpl - 1, 4 * fpl, 4 * fpl + 1):
                with self.subTest(year=year, magi=magi):
                    blk = uniform_block(800.0, 750.0, 400.0)
                    c = compute(blk, magi, year, load(year))
                    r = reference_f8962(blk, magi, year)
                    expected_line5 = r["line5_pct"]
                    self.assertEqual(c["f8962_line_5"], expected_line5)
                    # And the full reconciliation holds at each boundary point.
                    self.reconcile(blk, magi, year)

    def test_exact_4fpl_line5_is_year_correct(self):
        # Cross-check the oracle's own exact-4*fpl expectation matches the
        # documented per-year rule (inclusive 2021 -> 401, strict -> 400).
        for year in YEARS:
            fpl = load(year).fpl_single_48
            r = reference_f8962(uniform_block(800.0, 750.0, 400.0), 4 * fpl, year)
            expected = 401 if year == 2021 else 400
            with self.subTest(year=year):
                self.assertEqual(r["line5_pct"], expected)


# ---------------------------------------------------------------------------
# Spec §7 invariants asserted on the compute output for every scenario.
# ---------------------------------------------------------------------------
class InvariantTests(_DiffMixin, unittest.TestCase):
    def _emitted_months(self, c):
        return [n for n in range(1, 13) if f"f8962_month_{n}_a" in c]

    def _all_scenarios(self):
        """A spread of scenarios covering each qualitative regime."""
        scen = []
        for year in YEARS:
            scen.append((uniform_block(900.0, 850.0, 500.0), magi_for_pct(250, year), year))
            scen.append((uniform_block(900.0, 850.0, 200.0), magi_for_pct(200, year), year))
            scen.append((uniform_block(700.0, 650.0, 640.0), magi_for_pct(250, year), year))
            scen.append((uniform_block(800.0, 750.0, 400.0), magi_for_pct(500, year), year))
            scen.append((block([month() for _ in range(12)]), magi_for_pct(220, year), year))
            months = [month() for _ in range(12)]
            for i in range(2, 8):
                months[i] = month(820.0, 780.0, 460.0)
            scen.append((block(months), magi_for_pct(230, year), year))
        return scen

    def test_invariants_hold_every_scenario(self):
        for blk, magi, year in self._all_scenarios():
            with self.subTest(year=year, magi=magi):
                c = compute(blk, magi, year, load(year))

                emitted = self._emitted_months(c)
                sum_e = sum(c[f"f8962_month_{n}_e"] for n in emitted)
                sum_a = sum(c[f"f8962_month_{n}_a"] for n in emitted)
                sum_f = sum(c[f"f8962_month_{n}_f"] for n in emitted)

                # PTC <= premium each month, and in aggregate.
                for n in emitted:
                    self.assertLessEqual(
                        c[f"f8962_month_{n}_e"], c[f"f8962_month_{n}_a"],
                        msg=f"month {n} col_e > col_a",
                    )
                self.assertLessEqual(sum_e, sum_a)

                # line 24 == sum col_e; line 25 == sum col_f.
                self.assertEqual(c["f8962_line_24"], sum_e)
                self.assertEqual(c["f8962_line_25"], sum_f)

                # line 26 (net PTC) and line 29 (repayment) never both nonzero.
                self.assertFalse(
                    c["f8962_line_26_net_ptc"] != 0 and c["f8962_line_29_repayment"] != 0,
                    msg="line 26 and line 29 both nonzero",
                )

                # Cap respected: line 29 <= line 28 whenever line 5 < 400.
                if c["f8962_line_5"] < 400 and c["f8962_line_28"] is not None:
                    self.assertLessEqual(
                        c["f8962_line_29_repayment"], c["f8962_line_28"]
                    )

    def test_all_zero_block_all_outputs_zero(self):
        for year in YEARS:
            with self.subTest(year=year):
                c = compute(block([month() for _ in range(12)]),
                            magi_for_pct(250, year), year, load(year))
                # No month emitted, and every dollar output is zero.
                self.assertEqual(self._emitted_months(c), [])
                for key in ("f8962_line_24", "f8962_line_25",
                            "f8962_line_26_net_ptc", "f8962_line_27",
                            "f8962_line_29_repayment"):
                    self.assertEqual(c[key], 0)

    def test_2021_ui_monotonicity(self):
        # Setting received_unemployment_2021=True never DECREASES net PTC vs
        # False, same scenario. (Net PTC = line 26 - line 29 repayment.)
        def net(c):
            return c["f8962_line_26_net_ptc"] - c["f8962_line_29_repayment"]

        for pct in (110, 133, 200, 250, 300, 380):
            with self.subTest(pct=pct):
                magi = magi_for_pct(pct, 2021)
                on = compute(uniform_block(900.0, 850.0, 400.0, ui=True),
                             magi, 2021, load(2021))
                off = compute(uniform_block(900.0, 850.0, 400.0, ui=False),
                              magi, 2021, load(2021))
                self.assertGreaterEqual(net(on), net(off))


# ---------------------------------------------------------------------------
# Applicable-figure band sweep.
# ---------------------------------------------------------------------------
class ApplicableFigureSweepTests(_DiffMixin, unittest.TestCase):
    def test_line7_matches_oracle_across_band_boundaries(self):
        for year in YEARS:
            for boundary in (150, 200, 250, 300, 350, 400):
                for delta in (-1, 0, +1):
                    pct = boundary + delta
                    with self.subTest(year=year, pct=pct):
                        blk = uniform_block(820.0, 780.0, 430.0)
                        magi = magi_for_pct(pct, year)
                        c = compute(blk, magi, year, load(year))
                        r = reference_f8962(blk, magi, year)
                        self.assertEqual(
                            c["f8962_line_7"], r["line7_applicable_figure"],
                            msg=f"year={year} pct={pct} line7 mismatch",
                        )


# ---------------------------------------------------------------------------
# Mutation checks -- each PROVEN to bite. Perturb the COMPUTE side only, assert
# the reconciliation now FAILS, then restore and assert it passes again. Three
# DIFFERENT targets: params scalar, applicable-figure table, monthly input.
# ---------------------------------------------------------------------------
class MutationBiteTests(_DiffMixin, unittest.TestCase):
    # A passing baseline scenario shared by the mutation checks.
    YEAR = 2023
    PCT = 250

    def _baseline(self):
        blk = uniform_block(900.0, 850.0, 500.0)
        magi = magi_for_pct(self.PCT, self.YEAR)
        return blk, magi

    def _mutated_params(self, base, **overrides):
        # F8962Params is a frozen dataclass; build a perturbed copy.
        return dataclasses.replace(base, **overrides)

    def test_mutation_bites_on_params_fpl(self):
        # TARGET 1: params scalar -- bump fpl_single_48 by +1 on the compute
        # side only. This shifts line 4 (poverty line) so the diff must fail.
        blk, magi = self._baseline()
        base = load(self.YEAR)

        # Baseline reconciles.
        self.reconcile(blk, magi, self.YEAR, params=base)

        mutated = self._mutated_params(base, fpl_single_48=base.fpl_single_48 + 1)
        with self.assertRaises(AssertionError):
            self.reconcile(blk, magi, self.YEAR, params=mutated)

        # Restore: original params reconcile again.
        self.reconcile(blk, magi, self.YEAR, params=base)

    def test_mutation_bites_on_applicable_figure_table(self):
        # TARGET 2: applicable-figure table -- perturb one table entry by a
        # tiny amount on the compute side only. line 7 (and everything it
        # feeds) must then diverge from the oracle.
        blk, magi = self._baseline()
        base = load(self.YEAR)
        c = compute(blk, magi, self.YEAR, base)
        pct = c["f8962_line_5"]  # the row actually looked up
        self.assertIn(pct, base.applicable_figures)

        # Baseline reconciles.
        self.reconcile(blk, magi, self.YEAR, params=base)

        perturbed_table = dict(base.applicable_figures)
        perturbed_table[pct] = perturbed_table[pct] + 0.0004  # one table step
        mutated = self._mutated_params(base, applicable_figures=perturbed_table)
        with self.assertRaises(AssertionError):
            self.reconcile(blk, magi, self.YEAR, params=mutated)

        # Restore.
        self.reconcile(blk, magi, self.YEAR, params=base)

    def test_mutation_bites_on_monthly_input(self):
        # TARGET 3: monthly input -- feed the compute a block whose one covered
        # month's aptc is +1 while the oracle keeps the ORIGINAL block. line 25
        # (total APTC) and the repayment lines must then diverge.
        blk, magi = self._baseline()
        year = self.YEAR
        params = load(year)

        # Baseline: same block to both sides reconciles.
        self.reconcile(blk, magi, year, params=params)

        # Perturb only the block handed to compute.
        months = list(copy.deepcopy(blk.months))
        m0 = months[0]
        months[0] = Form1095AMonth(premium=m0.premium, slcsp=m0.slcsp,
                                   aptc=m0.aptc + 1.0)
        mutated_block = Form1095A(
            months=tuple(months),
            received_unemployment_2021=blk.received_unemployment_2021,
            tax_exempt_interest=blk.tax_exempt_interest,
        )

        c = compute(mutated_block, magi, year, params)
        r = reference_f8962(blk, magi, year)  # oracle keeps the original block
        with self.assertRaises(AssertionError):
            for ck, rk in SCALAR_RECON:
                self.assertEqual(c.get(ck), r.get(rk), msg=f"{ck}<->{rk}")

        # Restore: unperturbed block reconciles again.
        self.reconcile(blk, magi, year, params=params)


if __name__ == "__main__":
    unittest.main()
