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
