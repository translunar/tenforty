"""Convert XLSX spreadsheets to ODS format for future use.

Usage:
    python scripts/convert_to_ods.py spreadsheets/federal/2025/1040.xlsx
"""

import subprocess
import sys
from pathlib import Path


def convert_to_ods(xlsx_path: Path) -> Path:
    """Convert an XLSX file to ODS in the same directory."""
    if not xlsx_path.exists():
        print(f"Error: {xlsx_path} not found")
        sys.exit(1)

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
        print(f"Conversion failed: {result.stderr}")
        sys.exit(1)

    ods_path = output_dir / xlsx_path.with_suffix(".ods").name
    print(f"Converted: {xlsx_path} -> {ods_path}")
    return ods_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/convert_to_ods.py <path-to-xlsx>")
        sys.exit(1)
    convert_to_ods(Path(sys.argv[1]))
