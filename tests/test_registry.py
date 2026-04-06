import unittest

from tenforty.mappings.registry import FormMapping


class FakeMapping(FormMapping):
    INPUTS = {
        2025: {
            "wages": "W2_Wages_You",
            "filing_single": "File_Single",
        },
    }
    OUTPUTS = {
        2025: {
            "agi": "Adj_Gross_Inc",
            "tax": "Tax",
        },
    }


class TestFormMappingGetInputs(unittest.TestCase):
    def test_returns_inputs_for_valid_year(self):
        result = FakeMapping.get_inputs(2025)
        self.assertEqual(result, {"wages": "W2_Wages_You", "filing_single": "File_Single"})

    def test_raises_for_missing_year(self):
        with self.assertRaises(ValueError) as ctx:
            FakeMapping.get_inputs(2020)
        self.assertIn("No input mapping for year 2020", str(ctx.exception))


class TestFormMappingGetOutputs(unittest.TestCase):
    def test_returns_outputs_for_valid_year(self):
        result = FakeMapping.get_outputs(2025)
        self.assertEqual(result, {"agi": "Adj_Gross_Inc", "tax": "Tax"})

    def test_raises_for_missing_year(self):
        with self.assertRaises(ValueError) as ctx:
            FakeMapping.get_outputs(2020)
        self.assertIn("No output mapping for year 2020", str(ctx.exception))


class TestFormMappingInherit(unittest.TestCase):
    def test_inherit_inputs_with_override(self):
        result = FakeMapping.inherit(2025, {"wages": "W2_Wages_NEW"}, source="inputs")
        self.assertEqual(result["wages"], "W2_Wages_NEW")
        self.assertEqual(result["filing_single"], "File_Single")

    def test_inherit_outputs_with_addition(self):
        result = FakeMapping.inherit(2025, {"refund": "Overpaid"}, source="outputs")
        self.assertEqual(result["agi"], "Adj_Gross_Inc")
        self.assertEqual(result["refund"], "Overpaid")

    def test_inherit_does_not_mutate_original(self):
        FakeMapping.inherit(2025, {"wages": "CHANGED"}, source="inputs")
        self.assertEqual(FakeMapping.INPUTS[2025]["wages"], "W2_Wages_You")
