"""End-to-end test: emit a 2023 federal PDF packet + rendered-value spot checks.

Verifies that the 2023 PDF field mappings and workbook wiring produce a filled
1040 packet for a canonical 2023 wage+investment+rental scenario, and — the
point of this test — that the values land on the correct LINES on the two forms
whose 2023 field trees were renumbered vs 2024:

  * Schedule 1 line 7 (unemployment compensation): 2023 flattens this cell to
    f1_10 (2024 nested it in Line8a_ReadOrder); line 10 (total additional
    income) is f1_36 (2024: f1_37).
  * Form 1040 money lines (wages, total income, AGI).

The scenario adds a 1099-G so Schedule 1 line 7 is actually exercised (the
canonical battery scenario has rental income → line 10 but no unemployment).
Reading the filled field VALUE back from the emitted PDF and comparing it to the
computed result confirms value→field→line end-to-end — a path-existence check
alone cannot (the IRS reuses field numbers across lines between years).
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.models import Form1099G
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental
from tests.helpers import REPO_ROOT, needs_libreoffice

_UNEMPLOYMENT = 8_000.0


def _int_value(fields: dict, path: str) -> int:
    """Return the emitted field's value as a whole-dollar int.

    The filler writes whole-dollar strings (IRS half-up rounding); strip any
    thousands separators / currency formatting before parsing.
    """
    raw = fields[path].get("/V")
    if raw is None:
        raise AssertionError(f"field {path!r} is blank in the emitted PDF")
    text = str(raw).replace(",", "").replace("$", "").strip()
    return int(round(float(text)))


@needs_libreoffice
class Emit2023Tests(unittest.TestCase):
    def test_emits_2023_packet_with_values_on_the_right_lines(self):
        scenario = build_canonical_wage_investment_rental(2023)
        # Exercise Schedule 1 line 7 (unemployment) — a 2023-renumbered cell.
        scenario.form1099_g = [
            Form1099G(payer="Synthetic State", unemployment_compensation=_UNEMPLOYMENT)
        ]

        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results, emitted = orch.run_full_return(scenario, Path(tmp))

            # Packet emitted.
            self.assertIn("1040", emitted)
            self.assertTrue(emitted["1040"].exists())
            self.assertIn("sch_1", emitted)
            self.assertTrue(emitted["sch_1"].exists())

            f1040_map = Pdf1040.get_mapping(2023)
            sch1_map = PdfSch1.get_mapping(2023)["scalars"]
            f1040_fields = PdfReader(emitted["1040"]).get_fields() or {}
            sch1_fields = PdfReader(emitted["sch_1"]).get_fields() or {}

            # --- Schedule 1 renumbered cells (the point of this test) ---
            # Line 7 unemployment (2023: flat f1_10) must carry exactly the
            # 1099-G amount.
            self.assertEqual(
                _int_value(sch1_fields, sch1_map["sch_1_line_7_unemployment"]),
                int(_UNEMPLOYMENT),
                "unemployment did not land on Schedule 1 line 7 (f1_10) in 2023",
            )
            # Line 10 total additional income (2023: f1_36) = rental net (Sch E
            # → Sch 1 line 5) + unemployment. The canonical scenario's rental
            # nets $4,000 (rents 18,000 − mortgage 7,000 − taxes 2,500 −
            # depreciation 4,500); plus $8,000 unemployment = $12,000. That it
            # strictly exceeds the unemployment alone proves lines 7 and 10 were
            # not swapped by the renumber.
            _RENTAL_NET = 4_000
            expected_line10 = _RENTAL_NET + int(_UNEMPLOYMENT)
            self.assertEqual(
                _int_value(
                    sch1_fields, sch1_map["sch_1_line_10_total_additional_income"]
                ),
                expected_line10,
                "Schedule 1 line 10 (f1_36) total additional income mismatch",
            )

            # --- Form 1040 money lines (spine results onto the right lines) ---
            self.assertEqual(
                _int_value(f1040_fields, f1040_map["wages"]),
                int(round(results["wages"])),
                "wages did not land on Form 1040 line 1a",
            )
            self.assertEqual(
                _int_value(f1040_fields, f1040_map["total_income"]),
                int(round(results["total_income"])),
                "total income did not land on Form 1040 line 9",
            )
            self.assertEqual(
                _int_value(f1040_fields, f1040_map["agi"]),
                int(round(results["agi"])),
                "AGI did not land on Form 1040 line 11",
            )

            # --- Footing: the emitted 1040 must be arithmetically consistent ---
            # Form 1040 line 8 ("additional income from Schedule 1, line 10")
            # must equal the attached Schedule 1's line 10 total — otherwise the
            # printed return is internally inconsistent (an IRS-visible
            # arithmetic error). And line 9 total income must foot: it equals the
            # sum of the income lines including line 8. With a 1099-G present,
            # line 10 = rental 4,000 + unemployment 8,000 = 12,000, so line 8
            # must read 12,000 (not the rental-only $4,000 the `other_income`
            # key carried before this cell was repointed to `sch_1_line_10`).
            line8 = _int_value(
                f1040_fields, "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_52[0]"
            )
            sch1_line10 = _int_value(
                sch1_fields, sch1_map["sch_1_line_10_total_additional_income"]
            )
            self.assertEqual(
                line8, sch1_line10,
                "Form 1040 line 8 must equal Schedule 1 line 10 (footing)",
            )
            income_lines = sum(
                _int_value(f1040_fields, f1040_map[k])
                for k in ("wages", "taxable_interest", "ordinary_dividends",
                          "capital_gain_loss")
            )
            self.assertEqual(
                _int_value(f1040_fields, f1040_map["total_income"]),
                income_lines + line8,
                "Form 1040 line 9 total income must foot (sum of income lines + line 8)",
            )


if __name__ == "__main__":
    unittest.main()
