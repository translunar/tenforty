"""Form mappings — maps scenario fields to spreadsheet named ranges."""

from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.registry import FormMapping

__all__ = ["FormMapping", "F1040", "Pdf1040"]
