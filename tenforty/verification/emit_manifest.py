"""The committed emit manifest (ruled 2026-10-17, option c).

The generated harness tests need, at IMPORT, what each battery scenario does
on the real emit path: its routing (native, or workbook and so excluded),
whether it refuses (type and message fragment), and otherwise the exact set
of forms it fills. Computing that at import would cost every collection the
whole battery, so it is committed: ``tests/fixtures/harness_emit_manifest.
json``, written by ``scripts/harness_manifest.py``.

The manifest is never trusted blindly. Every generated class first emits
for real and asserts reality equals its row in BOTH directions (exact form
set; refusal type and fragment), failing with the regeneration command.
A manifest diff IS a behaviour change: every regeneration carries an
enumerated per-row explanation (ledgered discipline).
"""
import json
import tempfile
import unittest.mock
from pathlib import Path

from tenforty.verification.batteries import BATTERIES, BatteryRef

MANIFEST_PATH = (Path(__file__).resolve().parents[2] / "tests" / "fixtures"
                 / "harness_emit_manifest.json")
REGENERATE = "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/harness_manifest.py"
FRAGMENT_CHARS = 60


def row_id(battery: str, scenario: str, year: int) -> str:
    return f"{battery}/{scenario}/{year}"


def form_label(rec) -> str:
    """One filled form in a manifest row: ``jurisdiction/form``, plus
    ``#copy`` for one of several copies."""
    label = "/".join(rec.form)
    return f"{label}#{rec.copy_id}" if rec.copy_id is not None else label


def refusal_fragment(exc: BaseException) -> str:
    return str(exc).strip().splitlines()[0][:FRAGMENT_CHARS]


def _orchestrator(work: Path):
    from tenforty.orchestrator import ReturnOrchestrator
    return ReturnOrchestrator(
        spreadsheets_dir=Path(__file__).resolve().parents[2] / "spreadsheets",
        work_dir=work)


def _no_workbook():
    from tenforty.orchestrator import ReturnOrchestrator
    return unittest.mock.patch.object(
        ReturnOrchestrator, "_compute_1040_via_workbook",
        side_effect=AssertionError("workbook path reached in a native row"))


def routing(scenario) -> str:
    """``native`` or ``workbook`` (cheap: no compute)."""
    orch = _orchestrator(Path(tempfile.mkdtemp()))
    return "native" if orch._scenario_in_spine_scope(scenario) else "workbook"


def emit(battery: BatteryRef, scenario, out: Path):
    """Run one native scenario through the battery's entry point. Returns
    the EmitResult (or raises the refusal)."""
    orch = _orchestrator(out.parent / (out.name + "_work"))
    with _no_workbook():
        ret = getattr(orch, battery.entry_point)(scenario, out)
    return ret[1] if isinstance(ret, tuple) else ret


def observe(battery: BatteryRef, scenario, out: Path) -> dict:
    """What one scenario does on the real path, as a manifest row."""
    route = routing(scenario)
    if route == "workbook":
        return {"routing": "workbook", "refusal": None, "forms": None}
    try:
        result = emit(battery, scenario, out)
    except (NotImplementedError, ValueError) as exc:
        return {"routing": "native",
                "refusal": {"type": type(exc).__name__,
                            "fragment": refusal_fragment(exc)},
                "forms": None}
    return {"routing": "native", "refusal": None,
            "forms": sorted(form_label(r) for r in result.record)}


def build_manifest() -> dict:
    rows = {}
    with tempfile.TemporaryDirectory() as td:
        for battery in BATTERIES:
            for i, (name, year, build) in enumerate(battery.scenarios()):
                rid = row_id(battery.name, name, year)
                if rid in rows:
                    raise ValueError(f"duplicate manifest row {rid}")
                rows[rid] = observe(battery, build(),
                                    Path(td) / f"{battery.name}_{i}")
    return rows


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def write_manifest(rows: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")


def diff(old: dict, new: dict) -> list[str]:
    """Per-row differences, for the regeneration explanation."""
    out = []
    for rid in sorted(set(old) | set(new)):
        if old.get(rid) != new.get(rid):
            out.append(f"{rid}: {old.get(rid)} -> {new.get(rid)}")
    return out
