# tests/test_emit_declarations.py
"""Generated per-scenario emit checks (emit-verification harness spec §3.2,
§3.4, §2.3; plan Track B generated-tests; rulings 2026-10-17: the committed
manifest, two-trades as refusing rows).

One class per (battery, scenario, year), ``Scn_<battery>__<scenario>__<year>``,
generated at import from the committed emit manifest
(``tests/fixtures/harness_emit_manifest.json``). ``setUpClass`` emits once
through the battery's real entry point and FIRST asserts reality equals the
manifest row in both directions; then one method per (form, check):

- a DECLARED form: ``test_<form>_<year>_<check>`` for value, placement, ink,
  option_group and repeater_rows (every copy of the form inside one method);
- a PENDING form: one ``test_<form>_<year>_pending`` that skips with its
  pending reason (D3);
- a REFUSING scenario: exactly one ``test_refusal`` asserting the refusal
  type and message fragment, and no form methods (it covers nothing).

Workbook-routed scenarios are excluded (the harness is native-only) and
listed in ``EXCLUDED_WORKBOOK_ROUTED``. Real methods carry the axes, so node
ids are stable and subtests never fold into the counts (spec §3.2).
"""
import re
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import registry
from tenforty.verification import checks, emit_manifest, pending, zero_lines
from tenforty.verification.batteries import BATTERIES
from tenforty.verification.coverage import WORKBOOK_LABEL, coverage_cells
from tenforty.verification.undeclared import undeclared_keys

CHECKS = ("value", "placement", "ink", "option_group", "repeater_rows")
MANIFEST = emit_manifest.load_manifest()
_BATTERY = {b.name: b for b in BATTERIES}
_EMITS: dict[str, object] = {}
_TMP = tempfile.TemporaryDirectory()

EXCLUDED_WORKBOOK_ROUTED: dict[str, str] = {
    rid: ("routed to the workbook (out of native-spine scope): the harness "
          "checks only the native pipeline")
    for rid, row in sorted(MANIFEST.items()) if row["routing"] == "workbook"
}


def _ident(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", text)


def _scenarios():
    """(battery, name, year, builder) for every battery scenario, in the
    battery's own order."""
    for battery in BATTERIES:
        for name, year, build in battery.scenarios():
            yield battery, name, year, build


def emitted(battery, name, year, build):
    """The EmitResult of one native, non-refusing row, emitted at most once
    per test session (scenario classes and the coverage test share it)."""
    rid = emit_manifest.row_id(battery.name, name, year)
    if rid not in _EMITS:
        out = Path(_TMP.name) / _ident(rid)
        _EMITS[rid] = emit_manifest.emit(battery, build(), out)
    return _EMITS[rid]


def _forms(labels):
    """{(jurisdiction, form): [labels...]} from a manifest row's form set."""
    grouped: dict = {}
    for label in labels:
        form = tuple(label.split("#")[0].split("/"))
        grouped.setdefault(form, []).append(label)
    return grouped


def _check_method(form, year, check):
    def test(self):
        decl = registry.for_form(form, year)
        recs = [r for r in self.result.record if r.form == form]
        findings = []
        for rec in recs:
            if check == "value":
                findings += checks.check_value(rec, decl)
            elif check == "placement":
                from tenforty.mappings.catalog import CATALOG
                from tenforty.orchestrator import _PDFS_ROOT
                template = (_PDFS_ROOT / form[0] / str(year)
                            / f"{CATALOG[form].template_stem}.pdf")
                findings += checks.check_placement(template, decl, rec.spec)
            elif check == "ink":
                findings += checks.check_ink(rec, decl)
            elif check == "option_group":
                findings += checks.check_option_groups(rec, decl)
            else:
                findings += checks.check_repeater_rows(rec.spec, decl)
        self.assertEqual(findings, [], "\n" + "\n".join(
            f.message for f in findings))
    return test


def _pending_method(reason):
    def test(self):
        self.skipTest(reason)
    return test


def _refusal_method(row, battery, build):
    def test(self):
        with self.assertRaises(Exception) as cm:
            emit_manifest.emit(battery, build(),
                               Path(tempfile.mkdtemp()) / "refused")
        self.assertEqual(type(cm.exception).__name__, row["refusal"]["type"])
        self.assertIn(row["refusal"]["fragment"], str(cm.exception))
    return test


def _setup_class(rid, row, battery, name, year, build):
    @classmethod
    def setUpClass(cls):
        cls.result = emitted(battery, name, year, build)
        actual = sorted(emit_manifest.form_label(r) for r in cls.result.record)
        if actual != row["forms"]:
            raise AssertionError(
                f"{rid}: manifest stale. It records forms {row['forms']}, "
                f"the real emit filled {actual}. Regenerate with "
                f"`{emit_manifest.REGENERATE}` and explain every changed "
                "row.")
    return setUpClass


def _generate():
    classes = {}
    seen_live = set()
    for battery, name, year, build in _scenarios():
        rid = emit_manifest.row_id(battery.name, name, year)
        seen_live.add(rid)
        row = MANIFEST.get(rid)
        if row is None or row["routing"] == "workbook":
            continue  # a missing row fails ManifestCoverageTests
        attrs = {"__doc__": f"Generated: {rid} via {battery.entry_point}."}
        if row["refusal"] is not None:
            attrs["test_refusal"] = _refusal_method(row, battery, build)
        else:
            attrs["setUpClass"] = _setup_class(rid, row, battery, name, year,
                                               build)
            for form, _labels in sorted(_forms(row["forms"]).items()):
                stem = _ident(form[1])
                if form in pending.PENDING_DECLARATIONS:
                    attrs[f"test_{stem}_{year}_pending"] = _pending_method(
                        pending.PENDING_DECLARATIONS[form])
                    continue
                for check in CHECKS:
                    attrs[f"test_{stem}_{year}_{check}"] = _check_method(
                        form, year, check)
        cls_name = f"Scn_{_ident(battery.name)}__{_ident(name)}__{year}"
        classes[cls_name] = type(cls_name, (unittest.TestCase,), attrs)
    return classes, seen_live


_CLASSES, _LIVE_ROWS = _generate()
globals().update(_CLASSES)


class ManifestCoverageTests(unittest.TestCase):
    """The manifest names exactly the batteries' live scenarios, and every
    live scenario's routing still matches its row (routing is cheap to
    recompute; form sets and refusals are checked by each class)."""

    def test_manifest_rows_are_exactly_the_live_scenarios(self):
        self.assertEqual(set(MANIFEST), _LIVE_ROWS,
                         f"regenerate with `{emit_manifest.REGENERATE}`")

    def test_routing_matches_the_manifest(self):
        for battery, name, year, build in _scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            with self.subTest(row=rid):
                self.assertEqual(emit_manifest.routing(build()),
                                 MANIFEST[rid]["routing"])


class RefusingScenarioTests(unittest.TestCase):
    """Review Focus 5: a refusing scenario is one refusal-asserting method
    and contributes nothing else."""

    def test_refusing_rows_get_exactly_one_refusal_method(self):
        refusing = [rid for rid, row in MANIFEST.items()
                    if row["routing"] == "native" and row["refusal"]]
        self.assertGreater(len(refusing), 0)
        for rid in refusing:
            battery, name, year = rid.split("/")
            cls = _CLASSES[f"Scn_{_ident(battery)}__{_ident(name)}__{year}"]
            tests = [m for m in vars(cls) if m.startswith("test_")]
            with self.subTest(row=rid):
                self.assertEqual(tests, ["test_refusal"])


class CoverageTests(unittest.TestCase):

    def test_every_declared_line_state_is_exercised(self):
        records = []
        for battery, name, year, build in _scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = MANIFEST.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            records += [(rid, r) for r in emitted(battery, name, year,
                                                  build).record]
        report = coverage_cells(records)
        path = Path(_TMP.name) / "coverage.txt"
        path.write_text(report.render())
        print(f"\ncoverage report: {path}")
        for cell in report.workbook_scoped:
            print(f"{WORKBOOK_LABEL}: {cell}")
        self.assertEqual(list(report.uncovered), [],
                         f"uncovered cells; see {path}")


class AlwaysZeroLineTests(unittest.TestCase):
    """[R-ZL-1] option 2: a declared value-only line that computes 0 in
    every native battery record is a finding unless ATTESTED_ZERO or
    PENDING accounts for it (tenforty/verification/zero_lines.py)."""

    def test_every_always_zero_line_is_accounted_for(self):
        records = []
        for battery, name, year, build in _scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = MANIFEST.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            records += [(rid, r) for r in emitted(battery, name, year,
                                                  build).record]
        found = zero_lines.findings(records)
        self.assertEqual(found, [], "\n".join(found))


class UndeclaredKeyTests(unittest.TestCase):

    def test_no_scenario_packet_has_an_undeclared_key(self):
        findings = []
        for battery, name, year, build in _scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = MANIFEST.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            findings += undeclared_keys(
                emitted(battery, name, year, build).record, scenario=rid)
        self.assertEqual(findings, [], "\n".join(
            f"{f.scenario}: {f.message}" for f in findings))


class DeclarationRegistryTests(unittest.TestCase):
    """D2 and D3 at the harness's own entrance (the live censuses, read)."""

    def test_work_in_progress_is_empty(self):
        self.assertEqual(dict(registry.WORK_IN_PROGRESS), {})

    def test_no_form_is_both_declared_and_pending(self):
        declared = {form for form, _key in registry.declared_forms()}
        self.assertEqual(declared & set(pending.PENDING_DECLARATIONS), set())


class ManifestStaleControlTests(unittest.TestCase):
    """The reality check fails a stale row in BOTH directions: a form the
    manifest lists but the emit did not fill, and a filled form the
    manifest does not list."""

    def _setup(self, forms):
        rid, row = next((r, x) for r, x in sorted(MANIFEST.items())
                        if x["routing"] == "native" and not x["refusal"])
        battery, name, year = rid.split("/")
        for b, n, y, build in _scenarios():
            if (b.name, n, str(y)) == (battery, name, year):
                stale = dict(row, forms=forms(row["forms"]))
                return _setup_class(rid, stale, b, n, y, build)
        raise LookupError(rid)

    def test_a_listed_form_the_emit_did_not_fill_fails(self):
        setup = self._setup(lambda f: sorted(f + ["federal/f8949"]))
        with self.assertRaises(AssertionError) as cm:
            setup.__func__(type("Probe", (), {}))
        self.assertIn("harness_manifest.py", str(cm.exception))

    def test_a_filled_form_the_manifest_omits_fails(self):
        setup = self._setup(lambda f: f[1:])
        with self.assertRaises(AssertionError):
            setup.__func__(type("Probe", (), {}))


if __name__ == "__main__":
    unittest.main()
