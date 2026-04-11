# Verification + Engine Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speed up the engine from ~18s to ~2-3s per scenario via `unoserver` daemon, add round-trip PDF verification, build max-coverage test fixtures, and create a per-year field coverage table. (Future: in-process UNO API for ~0.03s/scenario.)

**Architecture:** Replace the cold-start `soffice --headless --convert-to` approach with `unoconvert` talking to a persistent `unoserver` daemon (~2-3s per scenario vs ~18s). Uses a separate `UnoEngine` class (rather than adding a param to `SpreadsheetEngine`) for cleaner separation. A round-trip PDF verifier asserts engine results match filled PDF fields. A coverage table tracks which fields have been verified.

**Tech Stack:** Python 3.14, unoserver (run via LibreOffice's Python), openpyxl, pypdf, pytest

**Prerequisites:**
- LibreOffice must be ad-hoc re-signed for macOS: `codesign --force --sign - /path/to/LibreOfficePython` (already done on this machine)
- `unoserver` installed in both LibreOffice's Python and the project venv

---

## Subagent Guidelines

**Every subagent MUST follow these rules:**

1. **Activate the venv before ANY Python command:** `source /Users/juno/Projects/tenforty/.venv/bin/activate`
2. **PEP8 typing only.** `dict[str, str]`, `list[int]`, `X | None`. Never import from `typing`.
3. **All imports at top of file.** No inline imports.
4. **Reduce code duplication.**
5. **TDD: red → green → commit.**
6. **Test commands always include `-v`.**
7. **Test classes inherit from `unittest.TestCase`.** Use `self.assertEqual()`, etc. Never bare `assert`.
8. **Commit after each passing test cycle.**
9. **No personal data.** All dollar amounts in YAML fixtures must be divisible by 50.
10. **Tuples with 3+ items must be dataclasses.**

---

## Pre-Task 0: Rename conftest.py → helpers.py

Before starting any tasks, rename `tests/conftest.py` to `tests/helpers.py` and update all imports across the test suite. `conftest.py` is a pytest special file for fixtures and hooks — we're using it for plain helper functions and constants, which belong in a regular module.

- [ ] Rename `tests/conftest.py` → `tests/helpers.py`
- [ ] Find/replace `from tests.conftest import` → `from tests.helpers import` in all test files (grep to ensure none missed)
- [ ] Create a minimal `tests/conftest.py` with just a docstring: `"""pytest configuration (if needed)."""`
- [ ] Run full test suite to verify nothing broke
- [ ] Commit: `refactor: rename tests/conftest.py to tests/helpers.py`

---

## File Structure

```
tenforty/
├── tenforty/
│   ├── engine.py                    # Already has _resolve_named_range() extracted
│   └── uno_engine.py               # Create: UNO-based engine using unoconvert
├── spreadsheets/
│   └── federal/
│       └── 2025/
│           ├── 1040.xlsx            # Existing
│           └── 1040.ods             # Create: pre-converted ODS (for future use)
├── scripts/
│   ├── convert_to_ods.py           # Create: one-time ODS conversion script
│   └── start_unoserver.sh          # Create: helper to start the UNO daemon
├── tests/
│   ├── helpers.py                  # Shared test helpers (libreoffice_available, constants, etc.)
│   ├── invariants.py               # Modify: add verify_pdf_round_trip
│   ├── test_uno_engine.py          # Create: tests for UNO engine
│   ├── test_engine_parity.py       # Create: verify UNO == cold-start results
│   ├── test_round_trip.py          # Create: PDF round-trip verification tests
│   └── fixtures/
│       ├── max_income.yaml         # Create: exercises every income line
│       └── max_deductions.yaml     # Create: exercises every deduction/credit line
├── docs/
│   └── coverage/
│       └── 2025-field-coverage.md  # Create: per-year field coverage table
```

---

### Task 1: ODS Conversion Script + Pre-converted File

**Files:**
- Create: `scripts/convert_to_ods.py`
- Create: `spreadsheets/federal/2025/1040.ods`

This is a one-time conversion. The ODS is stored for future use but not used by the engine yet.

- [ ] **Step 1: Create the conversion script**

`scripts/convert_to_ods.py`:
```python
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
```

- [ ] **Step 2: Run the conversion**

```bash
source .venv/bin/activate && python scripts/convert_to_ods.py spreadsheets/federal/2025/1040.xlsx
```

Expected: `spreadsheets/federal/2025/1040.ods` created (~3MB).

- [ ] **Step 3: Commit**

```bash
git add scripts/convert_to_ods.py spreadsheets/federal/2025/1040.ods
git commit -m "feat: add ODS conversion script and pre-converted federal 1040"
```

---

### Task 2: UNO Engine Implementation

**Files:**
- Create: `tenforty/uno_engine.py`
- Create: `tests/test_uno_engine.py`
- Create: `scripts/start_unoserver.sh`

The UNO engine connects to a running `unoserver` daemon, opens the XLSX once, and provides set-cells + recalculate + read-cells operations.

- [ ] **Step 1: Create the unoserver startup helper**

`scripts/start_unoserver.sh`:
```bash
#!/bin/sh
# Start the unoserver daemon using LibreOffice's Python.
# LibreOffice's Python has the 'uno' module needed by unoserver.
#
# Prerequisites:
#   1. LibreOffice installed
#   2. unoserver installed in LO's Python:
#      /Applications/LibreOffice.app/Contents/Resources/python -m pip install unoserver
#   3. LO's embedded Python re-signed (macOS only):
#      codesign --force --sign - /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/*/Resources/Python.app/Contents/MacOS/LibreOfficePython

LO_PYTHON="/Applications/LibreOffice.app/Contents/Resources/python"

if [ ! -f "$LO_PYTHON" ]; then
    echo "Error: LibreOffice Python not found at $LO_PYTHON"
    exit 1
fi

echo "Starting unoserver daemon..."
exec "$LO_PYTHON" -m unoserver.server "$@"
```

- [ ] **Step 2: Write failing test for UnoEngine**

`tests/test_uno_engine.py`:
```python
import socket
import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.f1040 import F1040
from tenforty.uno_engine import UnoEngine
from tests.helpers import SPREADSHEETS_DIR


def unoserver_available() -> bool:
    """Check if unoserver daemon is running by attempting a connection."""
    try:
        sock = socket.create_connection(("127.0.0.1", 2002), timeout=2)
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


needs_unoserver = unittest.skipUnless(
    unoserver_available(), "unoserver not available",
)


@needs_unoserver
class TestUnoEngine(unittest.TestCase):
    def test_simple_w2_scenario(self):
        """Same test as the cold-start engine — $100k wages, single filer."""
        xlsx_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not xlsx_path.exists():
            self.skipTest("Federal 1040 spreadsheet not found")

        engine = UnoEngine()

        inputs = {
            "filing_status_single": "X",
            "birthdate_month": 6,
            "birthdate_day": 15,
            "birthdate_year": 1990,
            "w2_wages_1": 100000,
            "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000,
            "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000,
            "w2_medicare_withheld_1": 1450,
        }

        results = engine.compute(
            spreadsheet_path=xlsx_path,
            mapping=F1040,
            year=2025,
            inputs=inputs,
        )

        self.assertEqual(results["wages"], 100000)
        self.assertEqual(results["agi"], 100000)
        self.assertEqual(results["taxable_income"], 84250)
        self.assertEqual(results["federal_withheld"], 15000)
        self.assertGreater(results["total_tax"], 13000)
        self.assertLess(results["total_tax"], 14000)
        self.assertGreater(results["overpaid"], 0)

    def test_two_scenarios_same_engine(self):
        """Running two scenarios on the same engine gives independent results."""
        xlsx_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not xlsx_path.exists():
            self.skipTest("Federal 1040 spreadsheet not found")

        engine = UnoEngine()

        inputs_100k = {
            "filing_status_single": "X",
            "birthdate_month": 6, "birthdate_day": 15, "birthdate_year": 1990,
            "w2_wages_1": 100000, "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000, "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000, "w2_medicare_withheld_1": 1450,
        }

        inputs_200k = {
            "filing_status_single": "X",
            "birthdate_month": 6, "birthdate_day": 15, "birthdate_year": 1990,
            "w2_wages_1": 200000, "w2_fed_withheld_1": 40000,
            "w2_ss_wages_1": 176100, "w2_ss_withheld_1": 10950,
            "w2_medicare_wages_1": 200000, "w2_medicare_withheld_1": 2900,
        }

        results_100k = engine.compute(
            spreadsheet_path=xlsx_path, mapping=F1040, year=2025, inputs=inputs_100k,
        )
        results_200k = engine.compute(
            spreadsheet_path=xlsx_path, mapping=F1040, year=2025, inputs=inputs_200k,
        )

        self.assertEqual(results_100k["wages"], 100000)
        self.assertEqual(results_200k["wages"], 200000)
        self.assertGreater(results_200k["agi"], results_100k["agi"])
```

- [ ] **Step 3: Run test to verify failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_uno_engine.py -v
```

Expected: `ImportError` — `tenforty.uno_engine` does not exist.

- [ ] **Step 4: Implement UnoEngine**

`tenforty/uno_engine.py`:
```python
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
    """Parse a named range definition into (sheet_name, cell_address).

    Duplicated from engine.py — extract to shared module if this becomes
    a maintenance issue.
    """
    dest = defn.value
    sheet_name, cell_addr = dest.split("!")
    sheet_name = sheet_name.strip("'")
    cell_addr = cell_addr.replace("$", "")
    return sheet_name, cell_addr


class UnoEngine:
    """Spreadsheet engine using LibreOffice UNO API for fast recalculation."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2002) -> None:
        self._host = host
        self._port = port
        self._desktop = None
        self._doc = None
        self._current_path: Path | None = None

    def compute(
        self,
        spreadsheet_path: Path,
        mapping: type,
        year: int,
        inputs: dict[str, object],
        work_dir: Path | None = None,
    ) -> dict[str, object]:
        """Compute by writing inputs, recalculating via unoconvert, reading outputs."""
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
        self, workbook_path: Path, input_map: dict[str, str],
        sheet_map: dict[str, str], inputs: dict[str, object],
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

    def _read_outputs(
        self, workbook_path: Path, output_map: dict[str, str],
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

    def _recalculate(self, workbook_path: Path, work_dir: Path) -> Path:
        """Recalculate using unoconvert (talks to running unoserver daemon)."""
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
            raise RuntimeError(
                f"UNO recalculation failed: {result.stderr}"
            )

        return output_path
```

**Note:** `UnoEngine` uses the same openpyxl write/read approach as `SpreadsheetEngine` (both have `_write_inputs` and `_read_outputs` methods with a shared `_resolve_named_range` helper pattern). The only difference is the recalculate step: `UnoEngine` uses `unoconvert` (file-based, ~2-3s) which talks to the running daemon, while `SpreadsheetEngine` cold-starts soffice (~18s). If duplication between the two engines becomes a maintenance issue, extract the shared methods into a base class. Future: in-process UNO API for ~0.03s.

- [ ] **Step 5: Run tests**

First start the unoserver in another terminal:
```bash
scripts/start_unoserver.sh
```

Then run:
```bash
source .venv/bin/activate && python -m pytest tests/test_uno_engine.py -v
```

Expected: Both tests PASS.

- [ ] **Step 6: Make start_unoserver.sh executable and commit**

```bash
chmod +x scripts/start_unoserver.sh
git add tenforty/uno_engine.py tests/test_uno_engine.py scripts/start_unoserver.sh
git commit -m "feat: add UnoEngine using unoserver daemon for faster recalculation"
```

---

### Task 3: Engine Parity Verification

**Files:**
- Create: `tests/test_engine_parity.py`

This is the critical verification step: prove that the UNO engine produces identical results to the cold-start engine for all existing test scenarios.

- [ ] **Step 1: Write parity test**

`tests/test_engine_parity.py`:
```python
"""Verify that UnoEngine produces identical results to SpreadsheetEngine.

This test runs the same scenarios through both engines and asserts
every output value matches exactly. If these tests pass, the UNO
engine is a safe drop-in replacement.
"""

import socket
import tempfile
import unittest
from pathlib import Path

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.scenario import load_scenario
from tenforty.uno_engine import UnoEngine
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR, libreoffice_available


def unoserver_available() -> bool:
    """Check if unoserver daemon is running by attempting a connection."""
    try:
        sock = socket.create_connection(("127.0.0.1", 2002), timeout=2)
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


needs_both = unittest.skipUnless(
    libreoffice_available() and unoserver_available(),
    "Requires both LibreOffice and running unoserver",
)


@needs_both
class TestEngineParity(unittest.TestCase):
    """Run same scenarios through both engines, assert identical results."""

    def _compare_engines(self, fixture_name: str):
        xlsx_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not xlsx_path.exists():
            self.skipTest("Federal 1040 spreadsheet not found")

        scenario = load_scenario(FIXTURES_DIR / fixture_name)
        flat_inputs = flatten_scenario(scenario)

        # Cold-start engine
        cold_engine = SpreadsheetEngine()
        cold_results = cold_engine.compute(
            spreadsheet_path=xlsx_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
            work_dir=Path(tempfile.mkdtemp()),
        )

        # UNO engine
        uno_engine = UnoEngine()
        uno_results = uno_engine.compute(
            spreadsheet_path=xlsx_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
        )

        # Compare every output
        for key in sorted(set(cold_results) | set(uno_results)):
            cold_val = cold_results.get(key)
            uno_val = uno_results.get(key)
            self.assertEqual(
                cold_val, uno_val,
                f"Mismatch on '{key}': cold-start={cold_val}, UNO={uno_val}",
            )

    def test_parity_simple_w2(self):
        self._compare_engines("simple_w2.yaml")

    def test_parity_w2_investments(self):
        self._compare_engines("w2_with_investments.yaml")

    def test_parity_itemized(self):
        self._compare_engines("itemized_deductions.yaml")
```

- [ ] **Step 2: Run parity tests**

With unoserver running:
```bash
source .venv/bin/activate && python -m pytest tests/test_engine_parity.py -v
```

Expected: All 3 PASS — UNO engine matches cold-start engine exactly.

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine_parity.py
git commit -m "test: verify UNO engine produces identical results to cold-start engine"
```

---

### Task 4: Round-Trip PDF Verifier

**Files:**
- Modify: `tests/invariants.py`
- Create: `tests/test_round_trip.py`

- [ ] **Step 1: Write failing test for the verifier**

`tests/test_round_trip.py`:
```python
import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import verify_pdf_round_trip

from tests.helpers import (
    F1040_PDF,
    FIXTURES_DIR,
    SPREADSHEETS_DIR,
    needs_libreoffice,
    needs_pdf,
)


@needs_libreoffice
@needs_pdf
class TestRoundTripSimpleW2(unittest.TestCase):
    def test_all_filled_fields_match(self):
        work_dir = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=work_dir,
        )
        results = orchestrator.compute_federal(scenario)

        verify_pdf_round_trip(
            test=self,
            results=results,
            scenario=scenario,
            translation_spec=F1040_PDF_SPEC,
            pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF,
            year=2025,
            work_dir=work_dir,
        )


@needs_libreoffice
@needs_pdf
class TestRoundTripItemized(unittest.TestCase):
    def test_all_filled_fields_match(self):
        work_dir = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "itemized_deductions.yaml")

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=work_dir,
        )
        results = orchestrator.compute_federal(scenario)

        verify_pdf_round_trip(
            test=self,
            results=results,
            scenario=scenario,
            translation_spec=F1040_PDF_SPEC,
            pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF,
            year=2025,
            work_dir=work_dir,
        )
```

- [ ] **Step 2: Run to verify failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_round_trip.py -v
```

Expected: `ImportError` — `verify_pdf_round_trip` does not exist in invariants.

- [ ] **Step 3: Implement verify_pdf_round_trip**

Add to `tests/invariants.py`:

```python
def verify_pdf_round_trip(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
    translation_spec: TranslationSpec,
    pdf_mapping_cls: type,
    pdf_template: Path,
    year: int,
    work_dir: Path,
) -> None:
    """Verify that engine results survive the full pipeline to the PDF.

    Runs: translate → fill PDF → read back → compare every field.
    Reports mismatches and coverage gaps.
    """
    # Translate engine results to PDF namespace
    translator = ResultTranslator(translation_spec)
    translated = translator.translate(results, scenario)

    # Fill the PDF
    filler = PdfFiller()
    output_pdf = work_dir / "round_trip_verify.pdf"
    mapping = pdf_mapping_cls.get_mapping(year)
    filler.fill(pdf_template, output_pdf, mapping, translated)

    # Read back
    reader = PdfReader(output_pdf)
    pdf_fields = reader.get_fields()

    # Verify every field that was filled
    mismatches: list[str] = []
    gaps: list[str] = []
    verified_count = 0

    # Check: do filled fields match?
    for our_key, pdf_field_name in mapping.items():
        translated_value = translated.get(our_key)
        if translated_value is None:
            continue

        expected_str = str(translated_value)
        actual_str = pdf_fields.get(pdf_field_name, {}).get("/V", "")

        if actual_str != expected_str:
            mismatches.append(
                f"  {our_key}: expected '{expected_str}', "
                f"got '{actual_str}' (PDF field: {pdf_field_name})"
            )
        else:
            verified_count += 1

    # Check: are there translated keys with no PDF mapping? (coverage gaps)
    mapped_keys = set(mapping.keys())
    for key, value in translated.items():
        if value is not None and key not in mapped_keys:
            gaps.append(f"  {key}={value} (no PDF mapping)")

    errors: list[str] = []
    if mismatches:
        errors.append(
            f"{len(mismatches)} field(s) did not round-trip correctly:\n"
            + "\n".join(mismatches)
        )
    if gaps:
        errors.append(
            f"{len(gaps)} translated key(s) have no PDF mapping (coverage gaps):\n"
            + "\n".join(gaps)
        )
    if errors:
        test.fail("\n\n".join(errors))
```

Add these imports at the top of `tests/invariants.py`:
```python
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.result_translator import ResultTranslator, TranslationSpec
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_round_trip.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/invariants.py tests/test_round_trip.py
git commit -m "feat: add round-trip PDF verifier and tests for simple W-2 + itemized scenarios"
```

---

### Task 5: Max-Coverage Test Fixtures

**Files:**
- Create: `tests/fixtures/max_income.yaml`
- Create: `tests/fixtures/max_deductions.yaml`
- Create: `tests/test_round_trip_max_coverage.py`

- [ ] **Step 1: Create max-income fixture**

`tests/fixtures/max_income.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1985-04-20"
  state: CA

w2s:
  - employer: "Tech Corp"
    wages: 150000.00
    federal_tax_withheld: 30000.00
    ss_wages: 150000.00
    ss_tax_withheld: 9300.00
    medicare_wages: 150000.00
    medicare_tax_withheld: 2200.00
    state_wages: 150000.00
    state_tax_withheld: 10000.00

form1099_int:
  - payer: "National Bank"
    interest: 2000.00

form1099_div:
  - payer: "Investment Brokerage"
    ordinary_dividends: 3000.00
    qualified_dividends: 2500.00
    capital_gain_distributions: 5000.00
```

- [ ] **Step 2: Create max-deductions fixture**

`tests/fixtures/max_deductions.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1975-11-30"
  state: CA

w2s:
  - employer: "Acme Corp"
    wages: 250000.00
    federal_tax_withheld: 55000.00
    ss_wages: 176100.00
    ss_tax_withheld: 10950.00
    medicare_wages: 250000.00
    medicare_tax_withheld: 3650.00
    state_wages: 250000.00
    state_tax_withheld: 20000.00

form1098s:
  - lender: "Home Mortgage Co"
    mortgage_interest: 24000.00
    property_tax: 8000.00

form1099_int:
  - payer: "National Bank"
    interest: 1000.00

form1099_div:
  - payer: "Investment Brokerage"
    ordinary_dividends: 2000.00
    qualified_dividends: 1500.00
```

- [ ] **Step 3: Create round-trip tests for max-coverage fixtures**

`tests/test_round_trip_max_coverage.py`:
```python
import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import (
    assert_agi_consistent,
    assert_all_income_accounted_for,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
    verify_pdf_round_trip,
)

from tests.helpers import (
    F1040_PDF,
    FIXTURES_DIR,
    SPREADSHEETS_DIR,
    needs_libreoffice,
    needs_pdf,
)


@needs_libreoffice
class TestMaxIncomeCoverage(unittest.TestCase):
    """Max-income scenario: W-2 + interest + dividends + cap gain distributions."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "max_income.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.work_dir,
        )

    def test_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)
        assert_agi_consistent(self, results, self.scenario)
        assert_all_income_accounted_for(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

    def test_interest_in_agi(self):
        results = self.orchestrator.compute_federal(self.scenario)
        self.assertGreater(float(results["agi"]), 150000)

    def test_capital_gain_distributions_in_agi(self):
        results = self.orchestrator.compute_federal(self.scenario)
        # AGI should include $5000 cap gain distributions
        self.assertGreater(float(results["agi"]), 155000)

    @needs_pdf
    def test_round_trip(self):
        results = self.orchestrator.compute_federal(self.scenario)
        verify_pdf_round_trip(
            test=self, results=results, scenario=self.scenario,
            translation_spec=F1040_PDF_SPEC, pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF, year=2025, work_dir=self.work_dir,
        )


@needs_libreoffice
class TestMaxDeductions(unittest.TestCase):
    """Max-deductions scenario: high income + mortgage + property tax (itemized)."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "max_deductions.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.work_dir,
        )

    def test_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)
        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

    def test_itemizes(self):
        results = self.orchestrator.compute_federal(self.scenario)
        deductions = float(results.get("total_deductions", 0))
        self.assertGreater(deductions, 15750, "Should itemize with $24k mortgage + $8k SALT")

    @needs_pdf
    def test_round_trip(self):
        results = self.orchestrator.compute_federal(self.scenario)
        verify_pdf_round_trip(
            test=self, results=results, scenario=self.scenario,
            translation_spec=F1040_PDF_SPEC, pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF, year=2025, work_dir=self.work_dir,
        )
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_round_trip_max_coverage.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/max_income.yaml tests/fixtures/max_deductions.yaml tests/test_round_trip_max_coverage.py
git commit -m "test: add max-coverage fixtures and round-trip tests for income + deductions"
```

---

### Task 6: Field Coverage Table

**Files:**
- Create: `docs/coverage/2025-field-coverage.md`

- [ ] **Step 1: Build the coverage table**

This is built by inventorying every key in `Pdf1040.get_mapping(2025)` and checking which ones are exercised by our round-trip tests.

`docs/coverage/2025-field-coverage.md`:

```markdown
# 2025 Field Coverage

Fields verified through round-trip PDF tests: engine → translate → fill PDF → read back.

## f1040 (Form 1040)

### Page 1 — Header

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| first_name | 1040 header | — |
| last_name | 1040 header | — |
| ssn | 1040 header | — |
| spouse_first_name | 1040 header | — |
| spouse_last_name | 1040 header | — |
| spouse_ssn | 1040 header | — |
| address | 1040 header | — |
| apt_no | 1040 header | — |
| city | 1040 header | — |
| state | 1040 header | — |
| zip_code | 1040 header | — |

### Page 1 — Income

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| wages | 1040 L1a | simple_w2, max_income, max_deductions |
| household_employee_income | 1040 L1b | — |
| tip_income | 1040 L1c | — |
| medicaid_waiver | 1040 L1d | — |
| dependent_care_benefits | 1040 L1e | — |
| adoption_benefits | 1040 L1f | — |
| form_8919_wages | 1040 L1g | — |
| strike_benefits | 1040 L1h | — |
| stock_option_income | 1040 L1i | — |
| total_w2_income | 1040 L1z | — |
| tax_exempt_interest | 1040 L2a | — |
| taxable_interest | 1040 L2b | simple_w2, max_income |
| qualified_dividends | 1040 L3a | max_income |
| ordinary_dividends | 1040 L3b | max_income |
| ira_distributions | 1040 L4a | — |
| ira_taxable | 1040 L4b | — |
| pensions | 1040 L5a | — |
| pensions_taxable | 1040 L5b | — |
| social_security | 1040 L6a | — |
| social_security_taxable | 1040 L6b | — |
| lump_sum_election | 1040 L6c | — |
| capital_gain_loss | 1040 L7 | — |
| other_income | 1040 L8 | — |
| total_income | 1040 L9 | simple_w2, max_income, max_deductions |
| adjustments | 1040 L10 | — |
| agi | 1040 L11 | simple_w2, max_income, max_deductions |

### Page 2 — Tax and Credits

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| agi_page2 | 1040 L11b | simple_w2, max_income, max_deductions |
| standard_deduction | 1040 L12e | simple_w2, max_income |
| qbi_deduction | 1040 L13a | — |
| additional_deductions | 1040 L13b | — |
| total_deductions | 1040 L14 | simple_w2, max_income, max_deductions |
| taxable_income | 1040 L15 | simple_w2, max_income, max_deductions |
| total_tax | 1040 L16 | simple_w2, max_income, max_deductions |
| schedule2_tax | 1040 L17 | — |
| tax_plus_schedule2 | 1040 L18 | — |
| child_tax_credit | 1040 L19 | — |
| schedule3_credits | 1040 L20 | — |
| total_credits | 1040 L21 | — |
| tax_after_credits | 1040 L22 | — |
| other_taxes | 1040 L23 | — |
| total_tax_liability | 1040 L24 | — |

### Page 2 — Payments

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| federal_withheld_w2 | 1040 L25a | simple_w2, max_income, max_deductions |
| federal_withheld_1099 | 1040 L25b | — |
| federal_withheld_other | 1040 L25c | — |
| federal_withheld | 1040 L25d | simple_w2, max_income, max_deductions |
| estimated_payments | 1040 L26 | — |
| eic | 1040 L27a | — |
| additional_child_tax_credit | 1040 L28 | — |
| american_opportunity_credit | 1040 L29 | — |
| adoption_credit_8839 | 1040 L30 | — |
| schedule3_payments | 1040 L31 | — |
| total_other_payments | 1040 L32 | — |
| total_payments | 1040 L33 | simple_w2, max_income, max_deductions |

### Page 2 — Refund / Amount Owed

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| overpaid | 1040 L34 | simple_w2, max_income, max_deductions |
| refund | 1040 L35a | — |
| applied_to_next_year | 1040 L36 | — |
| amount_owed | 1040 L37 | — |
| estimated_tax_penalty | 1040 L38 | — |

## Schedule A (Itemized Deductions)

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| mortgage_interest | Sch A L8a | max_deductions, itemized |
| property_tax | Sch A L5b | max_deductions, itemized |

*Note: Schedule A PDF mapping not yet created. These fields are written to the XLS
and verified via engine output (`total_deductions`), but not yet round-trip verified
through a Schedule A PDF.*

## Schedule D (Capital Gains)

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| schd_line16 | Sch D L16 | max_income (via cap gain distributions) |

*Note: Schedule D PDF mapping not yet created.*
```

- [ ] **Step 2: Commit**

```bash
git add docs/coverage/2025-field-coverage.md
git commit -m "docs: add 2025 field coverage table for f1040 PDF"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | ODS conversion script + pre-converted file | — |
| 2 | UnoEngine implementation | 2 tests |
| 3 | Engine parity verification (UNO == cold-start) | 3 tests |
| 4 | Round-trip PDF verifier | 2 tests |
| 5 | Max-coverage fixtures + round-trip tests | 6 tests |
| 6 | Field coverage table | — |

**What this plan builds:** A faster UNO-based engine (~2-3s/scenario via unoconvert daemon, down from ~18s cold-start), round-trip PDF verification proving engine→PDF correctness, max-coverage test fixtures, and a per-year field coverage table showing what's verified. (Future: in-process UNO for ~0.03s/scenario.)

**What comes next:**
- In-process UNO engine (set cells directly via LO's Python, no file I/O at all)
- Schedule PDF mappings (Schedule A, D, E)
- 1099-B and K-1 flattener implementations (turn RED tests green)
- Fuzz-generated scenarios
- `formulas` library as alternative engine

---

## Appendix: In-Process UNO Engine (Option A)

If the `unoconvert` approach (Option B, ~2-3s/scenario) is too slow — particularly
for fuzzing or rapid iteration on mapping verification — an in-process UNO approach
achieves ~0.1s/scenario. This appendix documents everything needed to implement it.

### What was proved

On 2026-04-09, we benchmarked in-process UNO and confirmed:

- **Open ODS via UNO:** 7.2s (one-time, vs 15.9s for XLSX)
- **Clear all input cells:** 0.03s
- **Write inputs + calculateAll():** 0.03s
- **4 scenarios total:** 0.44s (0.109s average per scenario)
- **Clearing between scenarios works:** `cell.setString("")` zeros the cell, `calculateAll()` produces correct results with no bleedthrough from prior scenarios

### Architecture

```
[Our Python 3.14 (venv)]  ←JSON over stdin/stdout→  [LO Python 3.12 + uno]
     pytest, tenforty                                    calc_server.py
     orchestrator                                        opens ODS once
     flattener                                           set cells, calculateAll
     PDF filler                                          read cells
```

A small `calc_server.py` script runs under LibreOffice's Python (`/Applications/LibreOffice.app/Contents/Resources/python`). It:

1. Connects to the running `unoserver` daemon
2. Opens the spreadsheet once (ODS preferred for 2x faster open: 7.2s vs 15.9s)
3. Listens for JSON commands on stdin:
   - `{"clear": true}` — clear all mapped input cells
   - `{"set": {"w2_wages_1": 100000, "filing_status_single": "X", ...}}` — set input values
   - `{"calculate": true}` — call `doc.calculateAll()`
   - `{"read": ["agi", "taxable_income", ...]}` — read output values
   - `{"close": true}` — close document and exit
4. Responds with JSON on stdout

Our venv Python launches `calc_server.py` as a subprocess and communicates via JSON lines.

### Prerequisites on macOS

LibreOffice's bundled Python must be ad-hoc re-signed to bypass Launch Constraints:

```bash
codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/LibreOfficePython"
codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.12/Resources/Python.app"
codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework"
codesign --force --deep --sign - "/Applications/LibreOffice.app"
```

Without this, macOS Sequoia (26.x) kills LibreOfficePython with `SIGKILL (Code Signature Invalid) / Launch Constraint Violation`.

### unoserver must be installed in LO's Python

```bash
/Applications/LibreOffice.app/Contents/Resources/python -m pip install unoserver
```

### Key UNO API calls (verified working)

```python
import uno

# Connect to running unoserver
localContext = uno.getComponentContext()
resolver = localContext.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", localContext)
ctx = resolver.resolve(
    "uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

# Open spreadsheet (ODS is 2x faster than XLSX)
doc = desktop.loadComponentFromURL("file:///path/to/1040.ods", "_blank", 0, ())

# Access sheets
sheets = doc.getSheets()
w2_sheet = sheets.getByName("W-2s")

# Set a cell value (col, row are 0-indexed)
w2_sheet.getCellByPosition(2, 2).setValue(100000)  # C3

# Set a string (for checkboxes like filing status)
f1040_sheet.getCellByPosition(5, 19).setString("X")  # F20

# Clear a cell
cell.setString("")

# Recalculate all formulas
doc.calculateAll()

# Read a cell value
agi = f1040_sheet.getCellByPosition(37, 78).getValue()  # AL79

# Resolve named ranges
nrs = doc.NamedRanges  # (property, not method)
if nrs.hasByName("Adj_Gross_Inc"):
    content = nrs.getByName("Adj_Gross_Inc").getContent()
    # content is like "$'1040'.$AL$79"

# Close
doc.close(True)
```

### Converting cell references

The F1040 mapping uses cell refs like "C3" and "AL79". To use UNO's `getCellByPosition(col, row)`:

```python
def col_to_num(col_str: str) -> int:
    """Convert 'A' -> 0, 'B' -> 1, ..., 'AL' -> 37."""
    return sum((ord(c) - 64) * 26**i for i, c in enumerate(reversed(col_str))) - 1

# "C3" -> getCellByPosition(2, 2)  (0-indexed)
# "AL79" -> getCellByPosition(37, 78)
```

### Our tenforty code works under LO's Python 3.12

Verified: `sys.path.insert(0, "/path/to/tenforty")` then `from tenforty.mappings.f1040 import F1040` works. Our code is pure Python with no 3.13+ features.

### What didn't work

- **`pip install uno` from PyPI:** That's an unrelated, broken package. The real `uno` is only available bundled with LibreOffice.
- **Symlinking `pyuno.so` into our venv:** ABI mismatch (3.12 vs 3.14), crashes.
- **`formulas` library:** Couldn't parse the XLS's formulas (timed out during model loading). Too complex for it.
- **Running UNO directly without `unoserver`:** Segfaults. You need the `soffice` process running.
- **`loadComponentFromURL` on a stale/locked file:** Returns None silently. Always use a fresh copy.
- **`--deep` code signing without re-signing nested frameworks first:** The nested `LibreOfficePython` binary keeps its original signature. Must re-sign bottom-up.

### Estimated implementation effort

~2 tasks:
1. `calc_server.py` script (~100 lines) + `InProcessUnoEngine` class that launches it as subprocess
2. Parity test: verify InProcessUnoEngine matches SpreadsheetEngine and UnoEngine on all fixtures
