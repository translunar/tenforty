"""Recalculates a workbook through LibreOffice and harvests its answers.

Optional answer cache (off unless TENFORTY_ORACLE_CACHE is exactly "1"; evidentiary
runs leave it unset). A compute whose workbook-side inputs are unchanged reuses the
stored answer instead of launching LibreOffice. Entries live in
$TENFORTY_ORACLE_CACHE_DIR, else ~/.cache/tenforty-oracle/, at user level so they
outlive worktree teardown.

THE KEY IS THE CONTRACT: a dependency missing from it silently serves stale answers.
An entry's name is the sha256 of a canonical serialization of ALL of:
  - the template file's bytes (the bytes, not its path);
  - the `inputs` dict, sorted by key, each value by repr (so 1 and 1.0 differ);
  - `input_map`, `output_map` and `sheet_map`, each as sorted items;
  - the bytes of this file (any engine change invalidates everything);
  - the `soffice --version` string, probed at most once per process and only while
    caching is on. If the probe fails, nothing is cached in that process.

`year` and the mapping class are deliberately absent: they act only through the
three maps. Anything else compute() reads must be added to _cache_key.

Failure policy: open to recomputation, closed to wrong answers. Any cache-layer
exception, unusable entry, or answer JSON would not reproduce exactly means the real
compute runs; errors from the real compute still propagate and are never stored.
"""

import datetime
import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest.mock
from pathlib import Path

import openpyxl


# Belt-and-suspenders on top of per-invocation UserInstallation (see #23).
# Serializes every soffice invocation so concurrent callers can't race on
# any soffice-internal shared resource (sockets, registry caches) that
# profile isolation doesn't cover.
_SOFFICE_LOCK = threading.Lock()

_CACHE_ENV = "TENFORTY_ORACLE_CACHE"
_CACHE_DIR_ENV = "TENFORTY_ORACLE_CACHE_DIR"
_cache_counts = {"hits": 0, "misses": 0}
_cache_counts_lock = threading.Lock()


def cache_stats() -> dict[str, int]:
    """Process-level answer-cache counters: a snapshot of hits and misses."""
    with _cache_counts_lock:
        return dict(_cache_counts)


def _count_cache(outcome: str) -> None:
    with _cache_counts_lock:
        _cache_counts[outcome] += 1


def _cache_enabled() -> bool:
    return os.environ.get(_CACHE_ENV) == "1"


def _cache_dir() -> Path:
    override = os.environ.get(_CACHE_DIR_ENV)
    return Path(override) if override else Path.home() / ".cache" / "tenforty-oracle"


@functools.cache
def _soffice_version() -> str | None:
    """The soffice version string, or None if it cannot be determined.

    Returns None instead of raising because functools.cache does not cache
    exceptions: a raising probe would launch again on every compute.
    """
    try:
        with _SOFFICE_LOCK:
            result = subprocess.run(
                ["soffice", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
    except (OSError, subprocess.SubprocessError):
        return None
    version = result.stdout.strip()
    return version if result.returncode == 0 and version else None


def _cache_key(
    spreadsheet_path: Path,
    input_map: dict[str, str],
    output_map: dict[str, str],
    sheet_map: dict[str, str],
    inputs: dict[str, object],
    soffice_version: str,
) -> str:
    """Hash every workbook-side dependency; see the module docstring."""
    canonical = json.dumps({
        "template": hashlib.sha256(spreadsheet_path.read_bytes()).hexdigest(),
        "inputs": [[key, repr(inputs[key])] for key in sorted(inputs)],
        "input_map": sorted(input_map.items()),
        "output_map": sorted(output_map.items()),
        "sheet_map": sorted(sheet_map.items()),
        "engine": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "soffice": soffice_version,
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _cache_entry(
    spreadsheet_path: Path,
    input_map: dict[str, str],
    output_map: dict[str, str],
    sheet_map: dict[str, str],
    inputs: dict[str, object],
) -> Path | None:
    """The entry path for this compute, or None if it must not be cached."""
    try:
        version = _soffice_version()
        if version is None:
            return None
        key = _cache_key(
            spreadsheet_path, input_map, output_map, sheet_map, inputs, version,
        )
        return _cache_dir() / f"{key}.json"
    except Exception:
        return None


def _cache_read(entry: Path, output_map: dict[str, str]) -> dict[str, object] | None:
    """The stored answer, freshly parsed so callers may mutate it, or None."""
    try:
        outputs = json.loads(entry.read_bytes())["outputs"]
        # _read_outputs yields exactly the output_map keys, so any other shape
        # is a damaged entry rather than an answer.
        if isinstance(outputs, dict) and outputs.keys() == output_map.keys():
            return outputs
    except Exception:
        pass
    return None


def _cache_write(
    entry: Path, outputs: dict[str, object], year: int, template_name: str,
) -> None:
    """Store atomically; an answer JSON would not reproduce is left unstored."""
    try:
        payload = json.dumps({
            "outputs": outputs,
            "meta": {
                "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "year": year,
                "template": template_name,
                "soffice": _soffice_version(),
            },
        }, allow_nan=False)
        if json.loads(payload)["outputs"] != outputs:
            return
        # Private: answers computed from a real return are that filer's figures.
        entry.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp_name = tempfile.mkstemp(
            dir=entry.parent, prefix=entry.stem, suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as temp_file:
                temp_file.write(payload)
            os.replace(temp_name, entry)
        except BaseException:
            os.unlink(temp_name)
            raise
    except Exception:
        return


def _resolve_named_range(defn: object) -> tuple[str, str]:
    """Parse a named range definition into (sheet_name, cell_address)."""
    dest = defn.value
    sheet_name, cell_addr = dest.split("!")
    sheet_name = sheet_name.strip("'")
    cell_addr = cell_addr.replace("$", "")
    return sheet_name, cell_addr


def _assert_oracle_sanctioned() -> None:
    """Fail loudly if soffice/LibreOffice is reached from a non-oracle-marked test.

    Inert in production: PYTEST_CURRENT_TEST is unset outside pytest, so this never
    fires and soffice runs normally. Under pytest, an oracle-marked test has its
    sanction set by the conftest hookwrapper (see tests/conftest.py); an unmarked
    test that routes here has no sanction -> RuntimeError. Guards the LAUNCH, so it
    catches ANY route to soffice, orchestrator or otherwise.
    """
    current = os.environ.get("PYTEST_CURRENT_TEST")
    if not current:
        return  # production: PYTEST_CURRENT_TEST unset -> soffice runs normally
    if os.environ.get("TENFORTY_ORACLE_SANCTIONED") == "1":
        return  # oracle-marked test: sanctioned by the conftest hookwrapper
    if isinstance(subprocess.run, unittest.mock.NonCallableMock):
        # subprocess.run has been replaced by a mock (e.g. tests/test_oracle_engine.py,
        # which A3's AST entry-point guard already allowlists for the same reason): no
        # REAL soffice can launch, so there is nothing to guard. NOTE: a Mock whose
        # side_effect delegates to the real subprocess.run could evade this exemption;
        # that is OUT of the threat model -- the tripwire targets ACCIDENTAL leaks, not
        # deliberate circumvention (the whole-branch review and A3's AST guard cover
        # that). Do NOT tighten this into something that re-breaks the engine's
        # mock-based unit tests.
        return
    raise RuntimeError(
        f"soffice/LibreOffice was reached from a non-oracle-marked test "
        f"({current}); decorate that test @needs_libreoffice (oracle-tier). "
        f"See the tiering-leak remediation."
    )


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

        entry = None
        if _cache_enabled():
            entry = _cache_entry(
                spreadsheet_path, input_map, output_map, sheet_map, inputs,
            )
            cached = _cache_read(entry, output_map) if entry else None
            if cached is not None:
                # DELIBERATE: A CACHE HIT SKIPS _assert_oracle_sanctioned. The
                # sanction guards LibreOffice LAUNCHES, not answer reuse, and a
                # hit launches no recalculation. The guard stays at the top of
                # _recalculate, so every miss still passes through it.
                _count_cache("hits")
                return cached
            _count_cache("misses")

        work_dir = work_dir or Path("/tmp/tenforty_work")
        work_dir.mkdir(parents=True, exist_ok=True)

        working_copy = work_dir / spreadsheet_path.name
        shutil.copy2(spreadsheet_path, working_copy)

        self._write_inputs(working_copy, input_map, sheet_map, inputs)
        recalculated = self._recalculate(working_copy, work_dir)
        outputs = self._read_outputs(recalculated, output_map, sheet_map)
        if entry is not None:
            _cache_write(entry, outputs, year, spreadsheet_path.name)
        return outputs

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
        _assert_oracle_sanctioned()
        output_dir = work_dir / "recalculated"
        output_dir.mkdir(exist_ok=True)
        expected_output = output_dir / workbook_path.name

        # Per-invocation UserInstallation sidesteps the profile lock at
        # ~/.config/libreoffice/4/.~lock.registrymodifications.xcu# so
        # concurrent soffice frontends can't silently exit 0 without
        # producing output.
        with _SOFFICE_LOCK, tempfile.TemporaryDirectory(prefix="soffice_profile_") as profile_dir:
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
        sheet_map: dict[str, str],
    ) -> dict[str, object]:
        wb = openpyxl.load_workbook(workbook_path, data_only=True)
        named_ranges = {n.name: n for n in wb.defined_names.values()}
        results: dict[str, object] = {}

        for output_key, cell_ref in output_map.items():
            if cell_ref in named_ranges:
                defn = named_ranges[cell_ref]
                sheet_name, cell_addr = _resolve_named_range(defn)
                results[output_key] = wb[sheet_name][cell_addr].value
            elif output_key in sheet_map:
                sheet_name = sheet_map[output_key]
                results[output_key] = wb[sheet_name][cell_ref].value
            else:
                results[output_key] = None

        return results
