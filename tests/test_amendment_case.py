import tempfile
import unittest
from pathlib import Path

from tenforty.amendment import (
    MissingFiledValueError, load_amendment_case, load_filed_values)


def _write(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


class AmendmentCaseLoaderTests(unittest.TestCase):
    GOOD = """\
year: 2024
explanation: |
  Correcting omitted capital gain distributions.
original_refund_received: 100.0
original_refund_applied: 0.0
"""

    def test_loads_happy_path(self):
        case = load_amendment_case(_write(self.GOOD))
        self.assertEqual(case.year, 2024)
        self.assertIn("capital gain", case.explanation)
        self.assertIsNone(case.prior_amendment_note)

    def test_unknown_key_fails_closed(self):
        with self.assertRaises(ValueError) as ctx:
            load_amendment_case(_write(self.GOOD + "typo_key: 1\n"))
        self.assertIn("typo_key", str(ctx.exception))

    def test_missing_required_key_raises_valueerror(self):
        with self.assertRaises(ValueError):
            load_amendment_case(_write("year: 2024\n"))

    def test_ca_original_payment_fields_default_to_none(self):
        # A federal-only amendment case omits the CA analogues entirely;
        # they load as None (fail-closed at USE in assemble_ca, never
        # inferred to 0.0 here).
        case = load_amendment_case(_write(self.GOOD))
        self.assertIsNone(case.ca_original_refund_received)
        self.assertIsNone(case.ca_original_refund_applied)

    def test_loads_ca_original_payment_fields(self):
        case = load_amendment_case(_write(
            self.GOOD
            + "ca_original_refund_received: 250.0\n"
            + "ca_original_refund_applied: 0.0\n"))
        self.assertEqual(case.ca_original_refund_received, 250.0)
        self.assertEqual(case.ca_original_refund_applied, 0.0)

    def test_unknown_key_still_fails_closed_with_ca_fields(self):
        with self.assertRaises(ValueError) as ctx:
            load_amendment_case(_write(
                self.GOOD
                + "ca_original_refund_received: 1.0\n"
                + "ca_typo: 2\n"))
        self.assertIn("ca_typo", str(ctx.exception))


class FiledValuesReaderTests(unittest.TestCase):
    def test_reads_required_keys(self):
        p = _write("total_tax: 100.0\nagi: 5000.0\n")
        vals = load_filed_values(p, required_keys=("total_tax", "agi"))
        self.assertEqual(vals["total_tax"], 100.0)

    def test_missing_required_key_refuses_and_names_it(self):
        p = _write("total_tax: 100.0\n")
        with self.assertRaises(MissingFiledValueError) as ctx:
            load_filed_values(p, required_keys=("total_tax", "agi"))
        self.assertIn("agi", str(ctx.exception))

    def test_never_substitutes_defaults(self):
        p = _write("total_tax: 100.0\nextra: 1.0\n")
        vals = load_filed_values(p, required_keys=("total_tax",))
        self.assertNotIn("agi", vals)  # nothing invented
