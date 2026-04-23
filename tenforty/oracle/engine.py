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


class SpreadsheetEngine:
    """Writes inputs into a spreadsheet, recalculates via LibreOffice, reads outputs."""

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

        work_dir = work_dir or Path("/tmp/tenforty_work")
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
                defn = named_ranges[cell_ref]
                sheet_name, cell_addr = _resolve_named_range(defn)
                wb[sheet_name][cell_addr] = value
            elif input_key in sheet_map:
                sheet_name = sheet_map[input_key]
                wb[sheet_name][cell_ref] = value
            else:
                raise ValueError(
                    f"Input '{input_key}' maps to '{cell_ref}' but has no named range "
                    f"and no sheet in SHEET_MAP"
                )

        wb.save(workbook_path)

    def _recalculate(self, workbook_path: Path, work_dir: Path) -> Path:
        output_dir = work_dir / "recalculated"
        output_dir.mkdir(exist_ok=True)
        expected_output = output_dir / workbook_path.name

        # Per-invocation UserInstallation sidesteps the profile lock at
        # ~/.config/libreoffice/4/.~lock.registrymodifications.xcu# so
        # concurrent soffice frontends can't silently exit 0 without
        # producing output.
        with tempfile.TemporaryDirectory(prefix="soffice_profile_") as profile_dir:
            try:
                result = subprocess.run(
                    [
                        "soffice",
                        f"-env:UserInstallation=file://{profile_dir}",
                        "--headless", "--calc",
                        "--convert-to", "xlsx",
                        "--outdir", str(output_dir),
                        str(workbook_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            # TimeoutExpired is NOT CalledProcessError — would leak past the
            # returncode check. Re-raise as RuntimeError so downstream callers
            # see a uniform error surface.
            except subprocess.TimeoutExpired as e:
                raise RuntimeError(
                    f"soffice timeout after {e.timeout}s for "
                    f"{expected_output}; stdout={e.stdout!r} stderr={e.stderr!r}"
                ) from e

        if result.returncode != 0:
            raise RuntimeError(
                f"soffice recalculation failed (exit={result.returncode}): "
                f"stderr={result.stderr!r} stdout={result.stdout!r}"
            )
        # soffice can exit 0 without creating output when the profile lock at
        # ~/.config/libreoffice/4/.~lock.registrymodifications.xcu# is held by
        # a concurrent invocation. The per-invocation UserInstallation above
        # sidesteps that lock; this check is residual defense.
        if not expected_output.exists():
            raise RuntimeError(
                f"soffice exited 0 but did not create {expected_output}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        # Zero-byte or truncated output passes .exists() but fails downstream
        # in openpyxl.load_workbook with a confusing BadZipFile error. Catch
        # the empty case here; openpyxl handles truncation-but-nonempty.
        if expected_output.stat().st_size == 0:
            raise RuntimeError(
                f"soffice exited 0 and created {expected_output} but it is empty. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        return expected_output

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

            defn = named_ranges[named_range]
            sheet_name, cell_addr = _resolve_named_range(defn)
            results[output_key] = wb[sheet_name][cell_addr].value

        return results
