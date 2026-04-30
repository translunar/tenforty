# tests/test_sch_ca_compute.py
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import sch_1 as form_sch_1
from tenforty.forms.sch_ca import compute as sch_ca_compute
from tenforty.models import CA540Return, CASchCAAdjustment, DivergenceDirection, DivergenceSource
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario

from tests.helpers import FIXTURES_DIR, REPO_ROOT, needs_libreoffice


class SchCaKernelTests(unittest.TestCase):
    def test_empty_divergences_produce_no_adjustments(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={"agi": 100_000.0, "wages": 100_000.0},
        )
        # No subtractions, no additions; CA AGI matches federal
        self.assertEqual(result["sch_ca_total_subtractions"], 0.0)
        self.assertEqual(result["sch_ca_total_additions"], 0.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0)

    def test_single_subtraction_routes_to_correct_line(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §C 13",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=4300.0,
                    description="HSA disallowed",
                ),
            ]),
            federal_results={"agi": 100_000.0},
        )
        # Subtraction reduces CA AGI
        self.assertEqual(result["sch_ca_line_part_i_c_13_subtractions"], 4300.0)
        self.assertEqual(result["sch_ca_total_subtractions"], 4300.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0 - 4300.0)

    def test_multiple_divergences_same_line_sum(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.AUTO_DERIVED,
                    sch_ca_line="Part I §B 8z",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=1500.0,
                    description="CA Lottery",
                ),
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §B 8z",
                    direction=DivergenceDirection.SUBTRACTION,
                    amount=200.0,
                    description="Recycling income",
                ),
            ]),
            federal_results={"agi": 50_000.0},
        )
        self.assertEqual(result["sch_ca_line_part_i_b_8z_subtractions"], 1700.0)

    def test_addition_increases_ca_agi(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                CASchCAAdjustment(
                    source=DivergenceSource.WORKSHEET,
                    sch_ca_line="Part I §A 2",
                    direction=DivergenceDirection.ADDITION,
                    amount=350.0,
                    description="Out-of-state muni",
                ),
            ]),
            federal_results={"agi": 80_000.0},
        )
        self.assertEqual(result["sch_ca_ca_agi"], 80_000.0 + 350.0)
        self.assertEqual(result["sch_ca_line_part_i_a_2_additions"], 350.0)
        self.assertEqual(result["sch_ca_total_additions"], 350.0)


class SchCaIntegratedKernelTests(unittest.TestCase):
    def test_kernel_combines_auto_derived_and_worksheet_divergences(self):
        worksheet_divergences = [
            CASchCAAdjustment(
                source=DivergenceSource.WORKSHEET,
                sch_ca_line="Part I §C 13",
                direction=DivergenceDirection.SUBTRACTION,
                amount=4300.0,
                description="HSA disallowed",
            ),
        ]
        federal_results = {
            "agi": 100_000.0,
            "sch_1_line_7_unemployment": 4500.0,
        }
        ca540 = CA540Return(divergences=worksheet_divergences)
        result = sch_ca_compute(ca540=ca540, federal_results=federal_results)
        self.assertEqual(result["sch_ca_total_subtractions"], 4300.0 + 4500.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0 - (4300.0 + 4500.0))

    def test_kernel_returns_empty_when_ca540_is_none(self):
        result = sch_ca_compute(ca540=None, federal_results={"agi": 50_000.0})
        self.assertEqual(result, {})

    def test_kernel_pulls_auto_derive_with_empty_worksheet(self):
        ca540 = CA540Return(divergences=[])
        federal_results = {
            "agi": 75_000.0,
            "sch_1_line_7_unemployment": 2_000.0,
        }
        result = sch_ca_compute(ca540=ca540, federal_results=federal_results)
        self.assertEqual(result["sch_ca_total_subtractions"], 2_000.0)
        self.assertEqual(result["sch_ca_ca_agi"], 75_000.0 - 2_000.0)


class SchCaColAPassthroughTests(unittest.TestCase):
    """Col A federal-amount passthrough (T14 PDF mapping support).

    The kernel emits `sch_ca_line_<line>_col_a` keys for every entry in
    `_FEDERAL_TO_SCH_CA_COL_A_MAP` whose federal value is present and
    truthy. v1 covers 20 lines: §A 1z/2/3/4/5b/6/7, §B 1/3/4/5/6/7/8z,
    §C 11/13/15/17/20/21. Federal compute output keys are sourced from
    f1040 (semantic-named, e.g. `wages`, `taxable_interest`) for §A and
    sch_1 (line-keyed `sch_1_line_<N>_*`) for §B and §C. PDF mapping for
    these widget targets lives in pdf_sch_ca.
    """

    def test_federal_agi_always_emitted(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={"agi": 60_000.0},
        )
        self.assertEqual(result["sch_ca_federal_agi"], 60_000.0)

    def test_col_a_emitted_for_section_a_keys(self):
        # Section A: federal Form 1040 income lines, semantic-keyed.
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={
                "agi": 200_000.0,
                "wages": 120_000.0,
                "taxable_interest": 1_500.0,
                "ordinary_dividends": 3_200.0,
                "ira_taxable": 8_000.0,
                "pensions_taxable": 25_000.0,
                "social_security_taxable": 18_000.0,
                "capital_gain_loss": 4_500.0,
            },
        )
        self.assertEqual(result["sch_ca_line_part_i_a_1z_col_a"], 120_000.0)
        self.assertEqual(result["sch_ca_line_part_i_a_2_col_a"], 1_500.0)
        self.assertEqual(result["sch_ca_line_part_i_a_3_col_a"], 3_200.0)
        self.assertEqual(result["sch_ca_line_part_i_a_4_col_a"], 8_000.0)
        self.assertEqual(result["sch_ca_line_part_i_a_5b_col_a"], 25_000.0)
        self.assertEqual(result["sch_ca_line_part_i_a_6_col_a"], 18_000.0)
        self.assertEqual(result["sch_ca_line_part_i_a_7_col_a"], 4_500.0)

    def test_col_a_emitted_for_section_b_keys(self):
        # Section B: federal Schedule 1 additional income, line-keyed.
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={
                "agi": 100_000.0,
                "sch_1_line_1_taxable_refunds": 800.0,
                "sch_1_line_3_business_income": 25_000.0,
                "sch_1_line_4_other_gains": 1_000.0,
                "sch_1_line_5_rental_re_royalty": 14_500.0,
                "sch_1_line_6_farm_income": 3_000.0,
                "sch_1_line_7_unemployment": 2_500.0,
                "sch_1_line_8z_other_income": 600.0,
            },
        )
        self.assertEqual(result["sch_ca_line_part_i_b_1_col_a"], 800.0)
        self.assertEqual(result["sch_ca_line_part_i_b_3_col_a"], 25_000.0)
        self.assertEqual(result["sch_ca_line_part_i_b_4_col_a"], 1_000.0)
        self.assertEqual(result["sch_ca_line_part_i_b_5_col_a"], 14_500.0)
        self.assertEqual(result["sch_ca_line_part_i_b_6_col_a"], 3_000.0)
        self.assertEqual(result["sch_ca_line_part_i_b_7_col_a"], 2_500.0)
        self.assertEqual(result["sch_ca_line_part_i_b_8z_col_a"], 600.0)

    def test_col_a_emitted_for_section_c_keys(self):
        # Section C: federal Schedule 1 adjustments to income.
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={
                "agi": 100_000.0,
                "sch_1_line_11_educator": 250.0,
                "sch_1_line_13_hsa": 4_300.0,
                "sch_1_line_15_se_tax": 1_700.0,
                "sch_1_line_17_se_health": 6_200.0,
                "sch_1_line_20_ira": 7_000.0,
                "sch_1_line_21_student_loan_interest": 2_500.0,
            },
        )
        self.assertEqual(result["sch_ca_line_part_i_c_11_col_a"], 250.0)
        self.assertEqual(result["sch_ca_line_part_i_c_13_col_a"], 4_300.0)
        self.assertEqual(result["sch_ca_line_part_i_c_15_col_a"], 1_700.0)
        self.assertEqual(result["sch_ca_line_part_i_c_17_col_a"], 6_200.0)
        self.assertEqual(result["sch_ca_line_part_i_c_20_col_a"], 7_000.0)
        self.assertEqual(result["sch_ca_line_part_i_c_21_col_a"], 2_500.0)

    def test_col_a_not_emitted_when_federal_value_zero_or_absent(self):
        # When federal_results lacks every passthrough key, the kernel
        # emits only the always-emitted totals (federal_agi, totals,
        # ca_agi). Verify no `_col_a` key sneaks out.
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={"agi": 50_000.0},
        )
        col_a_keys = [k for k in result if k.endswith("_col_a")]
        self.assertEqual(
            col_a_keys, [],
            f"Expected no _col_a keys with empty federal income, got {col_a_keys}",
        )

    def test_col_a_passthrough_map_covers_expected_lines(self):
        # Verify the kernel's federal→Sch-CA-line map enumerates exactly
        # the 20 lines the v1 PDF mapping wires (§A 7 + §B 7 + §C 6).
        from tenforty.forms.sch_ca import _FEDERAL_TO_SCH_CA_COL_A_MAP
        expected_lines = frozenset({
            "Part I §A 1z", "Part I §A 2", "Part I §A 3", "Part I §A 4",
            "Part I §A 5b", "Part I §A 6", "Part I §A 7",
            "Part I §B 1", "Part I §B 3", "Part I §B 4",
            "Part I §B 5", "Part I §B 6", "Part I §B 7", "Part I §B 8z",
            "Part I §C 11", "Part I §C 13", "Part I §C 15",
            "Part I §C 17", "Part I §C 20", "Part I §C 21",
        })
        self.assertEqual(
            frozenset(_FEDERAL_TO_SCH_CA_COL_A_MAP.values()),
            expected_lines,
            "Col A passthrough map must cover exactly the 20 v1-wired Sch CA lines.",
        )


@needs_libreoffice
class SchCaKernelE2EFederalIntegrationTests(unittest.TestCase):
    """Pipe REAL federal compute output into sch_ca.compute and assert
    auto-derived divergences fire on actual produced keys.

    Guards the T14b realignment: the kernel's auto-derive catalog reads
    `sch_1_line_1_taxable_refunds`, `sch_1_line_7_unemployment`, and
    `social_security_taxable` — keys actually emitted by sch_1.compute and
    f1040.compute. A stub-based unit test alone cannot catch a regression
    where these producers rename a key out from under the kernel.

    NOTE — orchestrator wiring gap (tracked as task #80): `compute_federal`
    currently returns only the f1040.compute dict; sch_1.compute is invoked
    separately at PDF-emit time. The manual composition below
    (`{**f1040_results, **sch_1.compute(scenario, upstream={})}`) is a
    TEMPORARY BRIDGE; once #80 lands and `compute_federal` plumbs sch_1
    output through, callers can drop the manual sch_1 invocation and feed
    `compute_federal_results` straight into `sch_ca.compute`.
    """

    def _run_federal(self, fixture_name: str):
        scenario = load_scenario(FIXTURES_DIR / fixture_name)
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040_results = orch.compute_federal(scenario)
        sch_1_results = form_sch_1.compute(scenario, upstream={})
        return scenario, {**f1040_results, **sch_1_results}

    def test_state_refund_auto_derive_fires_on_real_federal_output(self):
        scenario, federal_results = self._run_federal("state_refund_benefit_rule.yaml")
        self.assertIn("sch_1_line_1_taxable_refunds", federal_results,
            "sch_1.compute must emit sch_1_line_1_taxable_refunds for the kernel to consume")
        self.assertGreater(federal_results["sch_1_line_1_taxable_refunds"], 0)

        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results=federal_results,
        )
        self.assertIn("sch_ca_line_part_i_b_1_subtractions", result,
            "Auto-derived state-refund subtraction must route to Part I §B 1")
        self.assertEqual(
            result["sch_ca_line_part_i_b_1_subtractions"],
            federal_results["sch_1_line_1_taxable_refunds"],
        )
        self.assertGreaterEqual(result["sch_ca_total_subtractions"],
            federal_results["sch_1_line_1_taxable_refunds"])
        self.assertLess(result["sch_ca_ca_agi"], result["sch_ca_federal_agi"])

    def test_unemployment_auto_derive_fires_on_real_federal_output(self):
        scenario, federal_results = self._run_federal("unemployment_withholding.yaml")
        self.assertIn("sch_1_line_7_unemployment", federal_results,
            "sch_1.compute must emit sch_1_line_7_unemployment for the kernel to consume")
        self.assertGreater(federal_results["sch_1_line_7_unemployment"], 0)

        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results=federal_results,
        )
        self.assertIn("sch_ca_line_part_i_b_7_subtractions", result,
            "Auto-derived unemployment subtraction must route to Part I §B 7")
        self.assertEqual(
            result["sch_ca_line_part_i_b_7_subtractions"],
            federal_results["sch_1_line_7_unemployment"],
        )

    def test_rrb_named_field_routes_to_sch_ca_5b(self):
        # Federal compute does not separately surface RRB — the taxpayer
        # supplies the RRB-only amount on CA540Return and the kernel routes
        # it as a §A 5b Col B subtraction.
        scenario, federal_results = self._run_federal("simple_w2.yaml")
        result = sch_ca_compute(
            ca540=CA540Return(rrb_tier_1_2_amount=4_200.0),
            federal_results=federal_results,
        )
        self.assertEqual(result.get("sch_ca_line_part_i_a_5b_subtractions"), 4_200.0)
        self.assertGreaterEqual(result["sch_ca_total_subtractions"], 4_200.0)

    def test_pfl_named_field_routes_to_sch_ca_b7(self):
        scenario, federal_results = self._run_federal("simple_w2.yaml")
        result = sch_ca_compute(
            ca540=CA540Return(pfl_amount=1_500.0),
            federal_results=federal_results,
        )
        self.assertEqual(result.get("sch_ca_line_part_i_b_7_subtractions"), 1_500.0)
        self.assertGreaterEqual(result["sch_ca_total_subtractions"], 1_500.0)
