import unittest

from tenforty.filing.pdf import PdfFiller


class TestPdfFiller(unittest.TestCase):
    def test_instantiation(self):
        filler = PdfFiller()
        self.assertIsNotNone(filler)

    def test_fill_method_exists(self):
        """PDF filler takes computed results + a field mapping."""
        filler = PdfFiller()
        self.assertTrue(callable(getattr(filler, "fill", None)))


class RenderNumericTests(unittest.TestCase):
    def test_emits_Yes_for_True(self):
        self.assertEqual(PdfFiller._render_numeric(True), "Yes")

    def test_emits_Off_for_False(self):
        self.assertEqual(PdfFiller._render_numeric(False), "Off")

    def test_irs_rounds_floats(self):
        # 1234.5 rounds to 1235 (IRS half-up); regression guard for the
        # existing rounding branch.
        self.assertEqual(PdfFiller._render_numeric(1234.5), "1235")

    def test_passes_strings_through(self):
        self.assertEqual(PdfFiller._render_numeric("541990"), "541990")
