"""Convert XLSX spreadsheets to ODS format for future use.

Usage:
    python scripts/convert_to_ods.py spreadsheets/federal/2025/1040.xlsx
"""

import subprocess
import sys
from pathlib import Path


def convert_to_ods(xlsx_path: Path) -> Path:
    """Convert an XLSX file to ODS in the same directory.

    Raises:
        FileNotFoundError: If the input file does not exist.
        RuntimeError: If the conversion fails.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Input file not found: {xlsx_path}")

    output_dir = xlsx_path.parent
    result = subprocess.run(
        [
            "soffice", "--headless", "--calc",
            "--convert-to", "ods",
            "--outdir", str(output_dir),
            str(xlsx_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Conversion failed: {result.stderr}")

    ods_path = output_dir / xlsx_path.with_suffix(".ods").name
    print(f"Converted: {xlsx_path} -> {ods_path}")
    return ods_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/convert_to_ods.py <path-to-xlsx>")
        sys.exit(1)
    try:
        convert_to_ods(Path(sys.argv[1]))
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
