"""Mapping-shape / placeholder-sweep tests for Schedule K-1 PDF mapping.

Mapping keys are flat with explicit `entity_` / `shareholder_` prefixes
because the IRS K-1 PDF has both an entity-name field and a
shareholder-name field that must be filled distinctly. The orchestrator
emit step (Task 18) flattens the nested compute output (`alloc["entity"]`,
`alloc["shareholder"]`) into this flat keyspace before invoking the filler.
"""

from pathlib import Path
import unittest

from pypdf import PdfReader

from tenforty.mappings import pdf_f1120s_k1


_EXPECTED_K1_KEYS = frozenset({
    "entity_ein",
    "entity_name_and_address",
    "shareholder_ssn_or_ein",
    "shareholder_name_and_address",
    "ownership_percentage",
    "box_1_ordinary_business_income",
})


class PdfF1120SK1MappingTests(unittest.TestCase):
    def test_2025_every_k1_allocation_key_is_mapped(self):
        mapping = pdf_f1120s_k1.PdfF1120SK1.get_mapping(2025)
        mapped = set(mapping.keys())
        missing = _EXPECTED_K1_KEYS - mapped
        self.assertEqual(missing, set())

    def test_2025_every_value_is_a_real_pdf_field(self):
        # Resolve from the test file's location upward — see the same
        # rationale in `test_pdf_f1120s_mapping.py`.
        project_root = Path(__file__).resolve().parent.parent
        pdf_path = project_root / "pdfs" / "federal" / "2025" / "f1120s_k1.pdf"
        reader = PdfReader(pdf_path)
        real_fields = set(reader.get_fields() or {})
        mapping = pdf_f1120s_k1.PdfF1120SK1.get_mapping(2025)
        bad = {k: v for k, v in mapping.items() if v not in real_fields}
        self.assertEqual(bad, {})

    def test_2025_every_pdf_field_has_at_most_one_compute_key(self):
        """Each PDF cell is filled by exactly one compute key.

        Multiple compute keys mapping to the same PDF field would mean
        `pdf_filler` writes the same cell N times with the last-iterated
        key winning silently. Catch that here."""
        mapping = pdf_f1120s_k1.PdfF1120SK1.get_mapping(2025)
        seen: dict[str, str] = {}
        duplicates: list[tuple[str, str, str]] = []
        for compute_key, pdf_field in mapping.items():
            if pdf_field in seen:
                duplicates.append((pdf_field, seen[pdf_field], compute_key))
            else:
                seen[pdf_field] = compute_key
        self.assertEqual(duplicates, [])
