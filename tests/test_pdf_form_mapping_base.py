"""Behavior tests for the PdfFormMapping base class."""

import unittest

from tenforty.mappings.registry import PdfFormMapping


class _FlatTestMapping(PdfFormMapping[dict[str, str]]):
    _FORM_NAME = "Test Flat"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2024: {"a": "x"},
        2025: {"a": "y"},
    }


class _RichTestMapping(PdfFormMapping[dict]):
    _FORM_NAME = "Test Rich"
    _MAPPINGS: dict[int, dict] = {
        2025: {"scalars": {"k": "v"}, "repeaters": {}},
    }


class PdfFormMappingTests(unittest.TestCase):
    def test_get_mapping_returns_payload_for_known_year(self):
        self.assertEqual(_FlatTestMapping.get_mapping(2024), {"a": "x"})
        self.assertEqual(_FlatTestMapping.get_mapping(2025), {"a": "y"})

    def test_get_mapping_unknown_year_raises_with_form_name(self):
        with self.assertRaisesRegex(
            ValueError, "No Test Flat PDF mapping for year 1999"
        ):
            _FlatTestMapping.get_mapping(1999)

    def test_get_mapping_supports_arbitrary_value_shape(self):
        result = _RichTestMapping.get_mapping(2025)
        self.assertIn("scalars", result)
        self.assertIn("repeaters", result)
        self.assertEqual(result["scalars"], {"k": "v"})

    def test_get_mapping_unknown_year_includes_year_in_message(self):
        with self.assertRaisesRegex(
            ValueError, "year 9999"
        ):
            _RichTestMapping.get_mapping(9999)


if __name__ == "__main__":
    unittest.main()
