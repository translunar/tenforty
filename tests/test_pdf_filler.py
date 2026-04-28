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


class RenderScalarTests(unittest.TestCase):
    def test_irs_rounds_floats(self):
        # 1234.5 rounds to 1235 (IRS half-up); regression guard for the
        # existing rounding branch.
        self.assertEqual(PdfFiller._render_scalar(1234.5), "1235")

    def test_passes_strings_through(self):
        self.assertEqual(PdfFiller._render_scalar("541990"), "541990")

    def test_rejects_bool_true(self):
        # Bools are no longer accepted — they must be routed through
        # checkbox_states in fill(). This guards the footgun where a
        # bool-valued field gets forgotten and silently renders "Yes"/"Off".
        with self.assertRaises(ValueError) as cm:
            PdfFiller._render_scalar(True)
        self.assertIn("checkbox_states", str(cm.exception))

    def test_rejects_bool_false(self):
        with self.assertRaises(ValueError) as cm:
            PdfFiller._render_scalar(False)
        self.assertIn("checkbox_states", str(cm.exception))
