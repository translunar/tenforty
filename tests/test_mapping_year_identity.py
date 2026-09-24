# tests/test_mapping_year_identity.py
"""Cloned-year mapping payloads: identity forms share one payload; the two
root-swap forms pin their genuine per-year deltas so the inherit refactor
can't silently change a field."""
import unittest

from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_a import PdfSchA
from tenforty.mappings.pdf_sch_b import PdfSchB
from tenforty.mappings.pdf_sch_e import PdfSchE


class IdenticalYearPayloadTests(unittest.TestCase):
    def test_2024_equals_2025(self):
        for cls in (PdfSchB, PdfSchE, PdfF1120SK1):
            with self.subTest(form=cls._FORM_NAME):
                self.assertEqual(cls.get_mapping(2024), cls.get_mapping(2025))


class RootSwapPayloadTests(unittest.TestCase):
    def test_sch_a_2024_is_root_swapped_2025_with_one_override(self):
        s24 = PdfSchA.get_mapping(2024)["scalars"]
        s25 = PdfSchA.get_mapping(2025)["scalars"]
        self.assertEqual(set(s24), set(s25))
        self.assertEqual(len(s24), 22)
        overrides = {
            "sch_a_line_2_agi": "topmostSubform[0].Page1[0].f1_4[0]",
        }
        for key, value25 in s25.items():
            expected = overrides.get(
                key, value25.replace("form1[0]", "topmostSubform[0]"))
            with self.subTest(key=key):
                self.assertEqual(s24[key], expected)

    def test_sch_1_2024_is_root_swapped_2025_with_two_overrides(self):
        s24 = PdfSch1.get_mapping(2024)["scalars"]
        s25 = PdfSch1.get_mapping(2025)["scalars"]
        self.assertEqual(set(s24), set(s25))
        self.assertEqual(len(s24), 16)
        # 2024 lacks the 2025-only line-7 "amount repaid" sub-field (f1_11 on
        # 2025), so line 7's amount is the flat f1_11 here (2025: f1_12).
        # Lines 25/26 differ from 2025 by one field (2024 line 26 = f2_31;
        # 2025 line 26 = f2_30), so line 26 is overridden.
        overrides = {
            "sch_1_line_7_unemployment":
                "form1[0].Page1[0].f1_11[0]",
            "sch_1_line_26_total_adjustments":
                "form1[0].Page2[0].f2_31[0]",
        }
        for key, value25 in s25.items():
            expected = overrides.get(
                key, value25.replace("topmostSubform[0]", "form1[0]"))
            with self.subTest(key=key):
                self.assertEqual(s24[key], expected)
