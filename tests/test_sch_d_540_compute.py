import unittest

from tenforty.forms.sch_d_540 import compute as sch_d_540_compute


class SchD540ComputeTests(unittest.TestCase):
    def test_federal_pass_through_when_no_divergence(self):
        federal_results = {"schd_line16": 4_000.0}
        scenario_config = {"acknowledges_no_ca_sch_d_federal_state_divergence": True}
        result = sch_d_540_compute(
            federal_results=federal_results,
            config=scenario_config,
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 4_000.0)

    def test_attestation_false_raises(self):
        federal_results = {"schd_line16": 4_000.0}
        scenario_config = {"acknowledges_no_ca_sch_d_federal_state_divergence": False}
        with self.assertRaises(NotImplementedError) as ctx:
            sch_d_540_compute(
                federal_results=federal_results,
                config=scenario_config,
            )
        self.assertIn("federal_state_divergence", str(ctx.exception))

    def test_federal_loss_passes_through(self):
        federal_results = {"schd_line16": -3_000.0}
        scenario_config = {"acknowledges_no_ca_sch_d_federal_state_divergence": True}
        result = sch_d_540_compute(
            federal_results=federal_results,
            config=scenario_config,
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], -3_000.0)

    def test_missing_schd_line16_defaults_to_zero(self):
        federal_results = {}
        scenario_config = {"acknowledges_no_ca_sch_d_federal_state_divergence": True}
        result = sch_d_540_compute(
            federal_results=federal_results,
            config=scenario_config,
        )
        self.assertEqual(result["sch_d_540_net_capital_gain"], 0)
