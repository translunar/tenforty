"""End-to-end emit test: Schedule K-1 (1120-S) box 17 code V / STMT.

Verifies that the per-shareholder K-1 emit loop in
`ReturnOrchestrator._emit_federal_scorp_pdfs_internal` (or equivalent) writes
the literal "V" into the box-17 code cell and the literal "STMT" into the
box-17 amount cell, since the actual §199A dollar figures are furnished on
an attached statement rather than inline on the K-1 itself.

Mirrors the concrete emit+`_read_v` harness already established in
tests/test_scorp_packet_emit.py and tests/test_pdf_2024_scorp_emit.py.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
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

    def test_box_17_code_v_and_stmt_every_scorp_year(self):
        """Emit-and-read-back "V"/"STMT" for EVERY supported S-corp federal
        year, against per-era HARDCODED field paths.

        The expected paths are written out literally here rather than pulled
        from `PdfF1120SK1.get_mapping(year)` on purpose: deriving them from
        the mapping under test would be circular and would pass even if the
        mapping pointed at the wrong cell. The 2024-era f1_90/f1_91 paths DO
        exist on the 2021-2023 templates — they just render on a different
        printed line — so neither the "key resolves to an existing field" nor
        the "no two keys collide" mapping tests can catch an era-B entry
        wrongly inheriting era-A paths. This end-to-end read-back is the only
        check in the suite that does.

        Uses `run_full_federal_scorp_return`, the public corporate-only entry:
        it drives the same per-shareholder K-1 emit loop as `run_full_return`
        but skips the 1040 spine, which S-corp-only years (2021) do not have.
        """
        # base -> (code cell, amount cell), hardcoded per field-tree era.
        base = "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0]"
        expected_cells = {
            2021: ("f1_87[0]", "f1_88[0]"),
            2022: ("f1_87[0]", "f1_88[0]"),
            2023: ("f1_87[0]", "f1_88[0]"),
            2024: ("f1_90[0]", "f1_91[0]"),
            2025: ("f1_90[0]", "f1_91[0]"),
        }
        # Guard: every supported year must have an expectation declared, so a
        # newly added year fails loudly here instead of silently going untested.
        self.assertEqual(
            sorted(expected_cells), sorted(years.SCORP_FEDERAL_YEARS))

        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                code_cell, amount_cell = expected_cells[year]
                scenario = _make_v1_scenario(
                    gross_receipts=100000.0, compensation_of_officers=30000.0)
                scenario = dataclasses.replace(
                    scenario,
                    config=dataclasses.replace(scenario.config, year=year),
                )
                out_dir = Path(self._tmp.name) / f"out_{year}"
                _corp, emitted = self.orch.run_full_federal_scorp_return(
                    scenario, out_dir)

                k1_path = emitted["1120s_k1_1"]
                self.assertTrue(k1_path.exists())
                self.assertEqual(
                    _read_v(k1_path, f"{base}.{code_cell}"), "V")
                self.assertEqual(
                    _read_v(k1_path, f"{base}.{amount_cell}"), "STMT")


if __name__ == "__main__":
    unittest.main()
