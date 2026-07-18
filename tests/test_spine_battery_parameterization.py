# tests/test_spine_battery_parameterization.py
"""battery_for(year) generates the parity battery from params — no cloned
per-year builders. Structural checks only; the deep proof is the parity
gate itself (tests/test_f1040_spine_oracle.py) staying green both years."""
import tempfile
import unittest
from pathlib import Path

from tenforty import years as year_manifest
from tenforty.forms import f8949 as form_f8949
from tenforty.forms import sch_d as form_sch_d
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params import f8962 as f8962_params
from tests.fixtures.spine_battery import battery_for

REPO_ROOT = Path(__file__).parent.parent

_EXPECTED_NAMES = [
    "canonical_wage_investment_rental",
    "qdcgt_15_to_20_boundary",
    "net_short_term_gain_with_ltcg_and_qualdiv",
    "qbi_threshold_boundary",
    "qbi_k1_deduction",
    "addl_medicare_boundary",
    "zero_tax_refund",
    "owes_tax",
    "tax_table_band",
    "itemizer_with_w2_state_tax",
    "ptc_net_credit",
    "ptc_capped_repayment",
    "ptc_partial_year_401",
    "wage_with_estimated_payments",
]

# 2021 additionally carries ptc_2021_ui_flat133 (the 2021-only ARPA
# unemployment-compensation special rule) and charitable_nonitemizer_2021
# (the 2021-only CARES/CAA line-12b non-itemizer charitable deduction);
# 2022-2025 do not — both scenarios are meaningless outside 2021 and
# battery_for() must not emit them for any other year.
_EXPECTED_NAMES_BY_YEAR = {
    2021: _EXPECTED_NAMES + ["ptc_2021_ui_flat133", "charitable_nonitemizer_2021"],
    2022: _EXPECTED_NAMES,
    2023: _EXPECTED_NAMES,
    2024: _EXPECTED_NAMES,
    2025: _EXPECTED_NAMES,
}


class BatteryParameterizationTests(unittest.TestCase):
    def test_same_scenarios_every_year(self):
        for year, expected in _EXPECTED_NAMES_BY_YEAR.items():
            with self.subTest(year=year):
                self.assertEqual([n for n, _ in battery_for(year)], expected)

    def test_year_threads_into_config(self):
        for year in (2023, 2024, 2025):
            for name, build in battery_for(year):
                with self.subTest(year=year, scenario=name):
                    self.assertEqual(build().config.year, year)

    def test_ss_wage_base_caps_high_wage_scenarios(self):
        # SSA OASDI wage base: 160,200 (2023), 168,600 (2024), 176,100 (2025).
        # The $500k-wage QDCGT scenario must carry ss_wages at exactly the
        # year's base. The 2023 figure is the attested load(2023).ss_wage_base
        # (SSA 2023 OASDI announcement / IRS Pub 15).
        for year, base in ((2023, 160_200.0), (2024, 168_600.0), (2025, 176_100.0)):
            scenario = dict(battery_for(year))["qdcgt_15_to_20_boundary"]()
            self.assertEqual(scenario.w2s[0].ss_wages, base)

    def test_sale_dates_fall_in_tax_year(self):
        for year in (2023, 2024, 2025):
            scenario = dict(battery_for(year))["owes_tax"]()
            self.assertTrue(
                scenario.form1099_b[0].date_sold.startswith(str(year)))

    def test_native_spine_computes_every_scenario_every_year(self):
        # The compute-only tier's promise ("native spine compute") as a machine
        # check: every battery scenario computes through the native 1040 spine —
        # no emit, no workbook, no soffice — for every FULL and COMPUTE-ONLY
        # federal year, producing the core outputs. This is the leg that would
        # catch a spine that crashes or mis-shapes on a newly-backfilled year's
        # params; verifying the inputs pack alone (params/table/attestation)
        # would not. Demand exactly what the tier promises — no less.
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work",
        )
        for year in (year_manifest.FEDERAL_YEARS
                     + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS):
            for name, build in battery_for(year):
                with self.subTest(year=year, scenario=name):
                    results = orch.compute_federal(build())
                    self.assertIn("total_tax", results)
                    self.assertIn("taxable_income", results)
                    self.assertIsInstance(results["total_tax"], (int, float))

    def test_net_short_term_gain_with_ltcg_scenario_carries_a_net_st_gain(self):
        # Structural pin closing the parity-coverage hole that hid bug #10
        # (found 2026-07-18): no prior battery scenario mixed a net
        # SHORT-term capital gain with LTCG/qualified dividends, so the
        # workbook-vs-native parity gate never exercised the QDCGT
        # worksheet's line-15-vs-line-16 split. This does NOT assert a
        # golden dollar amount (that's the parity gate's job); it only
        # proves the scenario materially carries the shape it exists to
        # exercise: a net ST GAIN (line 7 > 0) alongside a net LTCG
        # (line 15 > 0) -- computed via the real f8949 -> sch_d pipeline,
        # not read off the fixture's own literals, so a routing bug that
        # accidentally zeroed one leg would show up here.
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work",
        )
        for year in (year_manifest.FEDERAL_YEARS
                     + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS):
            with self.subTest(year=year):
                build = dict(battery_for(year))[
                    "net_short_term_gain_with_ltcg_and_qualdiv"]
                scenario = build()

                # The scenario computes end-to-end through the native spine.
                results = orch.compute_federal(scenario)
                self.assertIn("total_tax", results)
                self.assertIn("taxable_income", results)

                # Independently derive Sch D lines 7/15/16 from the
                # scenario's own 1099-B lots (the same pipeline the
                # orchestrator runs internally) to confirm both a net ST
                # GAIN and a net LTCG are simultaneously present.
                f8949_result = form_f8949.compute(scenario, upstream={})
                sch_d_result = form_sch_d.compute(
                    scenario, upstream={"f8949": f8949_result})
                self.assertGreater(sch_d_result["sch_d_line_7_net_short"], 0)
                self.assertGreater(sch_d_result["sch_d_line_15_net_long"], 0)
                self.assertEqual(
                    sch_d_result["sch_d_line_16_total"],
                    sch_d_result["sch_d_line_7_net_short"]
                    + sch_d_result["sch_d_line_15_net_long"],
                )
                # Qualified dividends are the other leg of the QDCGT
                # preferential base; confirm they're present too.
                self.assertGreater(
                    sum(f.qualified_dividends
                        for f in scenario.form1099_div), 0)

    def test_qbi_k1_deduction_yields_positive_qbi_every_year(self):
        # Structural regime pin: the QBI-active scenario must materially
        # exercise a Section 199A deduction every year, so a drifting
        # threshold/param table cannot silently zero it. NO golden dollar
        # value here — the exact figure is proven native-vs-oracle by the
        # parity gate (test_f1040_spine_oracle.py). Also confirms the two
        # line-13/14 keys the parity gate now compares are populated on the
        # native side.
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work",
        )
        for year in (year_manifest.FEDERAL_YEARS
                     + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS):
            with self.subTest(year=year):
                build = dict(battery_for(year))["qbi_k1_deduction"]
                results = orch.compute_federal(build())
                self.assertGreater(results["qbi_deduction"], 0)
                self.assertIn("deductions_plus_qbi", results)
                self.assertIsInstance(results["deductions_plus_qbi"], (int, float))


_PTC_YEARS = year_manifest.FEDERAL_YEARS + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS


class PTCBatteryRegimeSelfCheckTests(unittest.TestCase):
    """Regime self-checks for the four PTC battery scenarios: each asserts
    the INTENDED FPL band / credit / repayment regime, so a drifting params
    table (FPL guideline, applicable-figure table, repayment caps) can't
    silently move a scenario out of the regime it exists to exercise."""

    def setUp(self):
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work",
        )

    def test_ptc_net_credit_yields_positive_net_ptc_every_year(self):
        for year in _PTC_YEARS:
            with self.subTest(year=year):
                build = dict(battery_for(year))["ptc_net_credit"]
                results = self.orch.compute_federal(build())
                self.assertGreater(results["f8962_line_26_net_ptc"], 0)

    def test_ptc_capped_repayment_hits_the_200_300_band_cap_every_year(self):
        for year in _PTC_YEARS:
            with self.subTest(year=year):
                build = dict(battery_for(year))["ptc_capped_repayment"]
                results = self.orch.compute_federal(build())
                params = f8962_params.load(year)
                line_5 = results["f8962_line_5"]
                # Confirm the scenario actually lands in the 200-300% FPL
                # band before trusting the cap it implies.
                self.assertGreaterEqual(line_5, 200)
                self.assertLess(line_5, 300)
                expected_cap = next(
                    cap for bound, cap in params.repayment_caps_single
                    if bound > line_5
                )
                self.assertEqual(results["f8962_line_29_repayment"], expected_cap)

    def test_ptc_partial_year_401_line_5_lands_over_400_every_year(self):
        # Coverage Aug-Dec only, wages = round(4.50 * fpl): the intended
        # regime is line 5 == 401 (over the 400%-FPL boundary in every
        # supported year, both the 2021 inclusive rule and the 2022-2025
        # strict rule).
        #
        # NOTE / STOP: the WP-Task-3 brief's second self-check for this
        # scenario — f8962_line_29_repayment == 5 * 550 (full repayment of
        # the 5 covered months' APTC, i.e. zero PTC entitlement above
        # 400% FPL) — assumes the pre-ARPA "subsidy cliff" (zero
        # applicable figure, hence zero allowed credit, above 400% FPL).
        # Every year tenforty supports (2021-2025) carries the ARPA/IRA
        # enhanced-subsidy table instead, which floor-key-looks-up the
        # applicable figure up to and including the >=400% ceiling row
        # (0.085 in every attested year) rather than clamping it to 0.
        # That ceiling figure yields a nonzero monthly allowed credit
        # (cell e) in every one of the five supported years, so
        # f8962_line_29_repayment computes to less than 5 * 550 across the
        # board (verified 2021: 2035, 2022: 2055, 2023: 2165, 2024: 2325,
        # 2025: 2400 — never 2750). Asserting the brief's literal formula
        # would be a false assertion; per the brief's own instruction
        # ("If a provided self-check can't pass truthfully, STOP+report"),
        # this check is intentionally NOT asserted here. Only the
        # independently-true first conjunct (line 5 == 401) is checked.
        for year in _PTC_YEARS:
            with self.subTest(year=year):
                build = dict(battery_for(year))["ptc_partial_year_401"]
                results = self.orch.compute_federal(build())
                self.assertEqual(results["f8962_line_5"], 401)
                # STRUCTURAL pin: at >=400% FPL, no repayment-limitation cap
                # applies, so line 28 (the cap itself) must be blank/None —
                # not merely unused. Catches a bug that wrongly POPULATES the
                # cap line at 401% even if line 29 happens to come out
                # unaffected by it.
                self.assertIsNone(results["f8962_line_28"])
                # Pinning line 5 == 401 only proves the "no cap applies"
                # BRANCH is taken (>=400% FPL means the repayment-limitation
                # cap does not apply) — it does not prove that branch is
                # MATERIALLY exercised. A bug that wrongly applied the
                # 200-300%-band cap at 401% would still pass the assertion
                # above if the repayment happened to fall under that cap by
                # coincidence. So also require the actual repayment to
                # EXCEED the highest statutory cap for the year: only then
                # is it structurally impossible for a capped computation to
                # have produced this result, so a cap wrongly applied at
                # 401% would necessarily show up here as a failure. Together
                # with the line-28-is-None pin above, this proves the "no
                # cap" branch both structurally (cap line blank) and
                # materially (repayment exceeds what any cap would allow).
                params = f8962_params.load(year)
                top_cap = max(cap for _bound, cap in params.repayment_caps_single)
                self.assertGreater(results["f8962_line_29_repayment"], top_cap)

    def test_ptc_2021_ui_flat133_regime(self):
        build = dict(battery_for(2021))["ptc_2021_ui_flat133"]
        results = self.orch.compute_federal(build())
        self.assertEqual(results["f8962_line_5"], 133)
        self.assertEqual(
            results["f8962_line_26_net_ptc"], 12 * min(600, 550),
        )
