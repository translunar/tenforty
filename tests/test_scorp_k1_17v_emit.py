"""End-to-end emit test: Schedule K-1 (1120-S) box 17 code V / STMT.

Verifies that the per-shareholder K-1 emit loop in
`ReturnOrchestrator._emit_federal_scorp_pdfs_internal` (or equivalent) writes
the literal "V" into the box-17 code cell and the literal "STMT" into the
box-17 amount cell, since the actual §199A dollar figures are furnished on
an attached statement rather than inline on the K-1 itself.

Mirrors the concrete emit+`_read_v` harness already established in
tests/test_scorp_packet_emit.py and tests/test_pdf_2024_scorp_emit.py.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario


def _read_v(pdf_path: Path, field_path: str) -> str:
    """Read one AcroForm field's /V by its full path, normalizing the
    thousands-comma and dollar formatting the filler applies to numerics.
    Harmless for the plain-text "V"/"STMT" values asserted here."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


class K1Box17EmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_box_17_code_v_and_stmt_present(self):
        scenario = _make_v1_scenario(
            gross_receipts=100000.0, compensation_of_officers=30000.0)
        out_dir = Path(self._tmp.name) / "out"
        _results, emitted = self.orch.run_full_return(scenario, out_dir)

        k1_path = emitted["1120s_k1_1"]
        self.assertTrue(k1_path.exists())

        base = "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0]"
        self.assertEqual(
            _read_v(k1_path, f"{base}.f1_90[0]"), "V")       # 2025-era code cell
        self.assertEqual(
            _read_v(k1_path, f"{base}.f1_91[0]"), "STMT")    # 2025-era amount cell


if __name__ == "__main__":
    unittest.main()
