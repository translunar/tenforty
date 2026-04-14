"""UNO-based spreadsheet engine using a persistent unoserver daemon.

Requires unoserver running (start with scripts/start_unoserver.sh).
Uses unoconvert to recalculate via the running daemon (~2-3s vs ~18s cold-start).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl


def _resolve_named_range(defn: object) -> tuple[str, str]:
    """Parse a named range definition into (sheet_name, cell_address)."""
    dest = defn.value
    sheet_name, cell_addr = dest.split("!")
    sheet_name = sheet_name.strip("'")
    cell_addr = cell_addr.replace("$", "")
    return sheet_name, cell_addr


class UnoEngine:
    """Spreadsheet engine using unoconvert for faster recalculation."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2002) -> None:
        self._host = host
        self._port = port

    def compute(
        self,
        spreadsheet_path: Path,
        mapping: type,
        year: int,
        inputs: dict[str, object],
        work_dir: Path | None = None,
    ) -> dict[str, object]:
        input_map = mapping.get_inputs(year)
        output_map = mapping.get_outputs(year)
        sheet_map = getattr(mapping, "SHEET_MAP", {}).get(year, {})

        work_dir = work_dir or Path(tempfile.mkdtemp())
        work_dir.mkdir(parents=True, exist_ok=True)

        working_copy = work_dir / spreadsheet_path.name
        shutil.copy2(spreadsheet_path, working_copy)

        self._write_inputs(working_copy, input_map, sheet_map, inputs)
        recalculated = self._recalculate(working_copy, work_dir)
        return self._read_outputs(recalculated, output_map)

    def _write_inputs(
        self,
        workbook_path: Path,
        input_map: dict[str, str],
        sheet_map: dict[str, str],
        inputs: dict[str, object],
    ) -> None:
        wb = openpyxl.load_workbook(workbook_path)
        named_ranges = {n.name: n for n in wb.defined_names.values()}

        for input_key, value in inputs.items():
            if input_key not in input_map:
                continue

            cell_ref = input_map[input_key]

            if cell_ref in named_ranges:
                sheet_name, cell_addr = _resolve_named_range(named_ranges[cell_ref])
                wb[sheet_name][cell_addr] = value
            elif input_key in sheet_map:
                wb[sheet_map[input_key]][cell_ref] = value
            else:
                raise ValueError(
                    f"Input '{input_key}' maps to '{cell_ref}' but has no named range "
                    f"and no sheet in SHEET_MAP"
                )

        wb.save(workbook_path)

    def _recalculate(self, workbook_path: Path, work_dir: Path) -> Path:
        output_path = work_dir / "recalculated" / workbook_path.name
        output_path.parent.mkdir(exist_ok=True)

        result = subprocess.run(
            [
                "unoconvert",
                "--convert-to", "xlsx",
                str(workbook_path),
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"UNO recalculation failed: {result.stderr}")

        return output_path

    def _read_outputs(
        self,
        workbook_path: Path,
        output_map: dict[str, str],
    ) -> dict[str, object]:
        wb = openpyxl.load_workbook(workbook_path, data_only=True)
        named_ranges = {n.name: n for n in wb.defined_names.values()}
        results: dict[str, object] = {}

        for output_key, named_range in output_map.items():
            if named_range not in named_ranges:
                results[output_key] = None
                continue

            sheet_name, cell_addr = _resolve_named_range(named_ranges[named_range])
            results[output_key] = wb[sheet_name][cell_addr].value

        return results
