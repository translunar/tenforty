# tests/test_fill_chokepoint.py
"""The single fill chokepoint (emit-verification harness spec §7; plan
Track B fill-chokepoint; rulings A6 (six entry points), NON_FILL_EMITTED,
and the 2026-10-17 spec-shape rulings).

Every PDF form fill goes through ``tenforty.verification.fill.fill``, which
records what it filled; every emitting entry point returns that record. This
lane changes plumbing only: every emitted PDF is byte-identical to the one
emitted before the reroute (``tests/fixtures/chokepoint_before/``).
"""
import ast
import inspect
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tenforty import years as year_manifest
from tenforty.declarations import registry
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.catalog import CATALOG, KNOWN_GAPS
from tenforty.mappings.registry import PdfFormMapping
from tenforty.orchestrator import PacketManifest, ReturnOrchestrator
from tenforty.verification import fill as fill_module
from tenforty.verification.fill import (
    FILL_GETTERS,
    KNOWN_NON_FILL_GETTERS,
    FillSpec,
    fill_spec_for,
)
from tenforty.verification.record import EmitRecord, EmitResult, RecordedForm
from tests.fixtures import chokepoint_scenarios as cases
from tests.helpers import REPO_ROOT

ENTRY_POINTS = frozenset({
    "emit_pdfs", "run_full_return", "run_full_california_return",
    "run_amendment_packet", "run_full_federal_scorp_return",
    "run_full_california_scorp_return",
})
# Public emit*/run_* methods that emit nothing, each with its reason. EMPTY:
# every public emit*/run_* method today is an emitting entry point.
NON_EMITTING: dict[str, str] = {}

_RUNS: dict = {}
_TMP: tempfile.TemporaryDirectory | None = None


def setUpModule():
    """Run every case ONCE through call-through recording wrappers on
    PdfFiller, so the record, identity, union and byte-identical tests share
    one real emit per case."""
    global _TMP
    _TMP = tempfile.TemporaryDirectory()
    real_fill, real_rep = PdfFiller.fill, PdfFiller.fill_with_repeaters
    for name in cases.CASES:
        captured: list = []

        def fill(self, *args, _real=real_fill, _cap=captured, **kw):
            _cap.append(kw["values"])
            return _real(self, *args, **kw)

        def fill_rep(self, *args, _real=real_rep, _cap=captured, **kw):
            _cap.append(kw["values"])
            return _real(self, *args, **kw)

        with unittest.mock.patch.object(PdfFiller, "fill", fill), \
                unittest.mock.patch.object(PdfFiller, "fill_with_repeaters",
                                           fill_rep):
            ret, out = cases.run_case(name, Path(_TMP.name))
        _RUNS[name] = (ret, out, captured)


def tearDownModule():
    if _TMP is not None:
        _TMP.cleanup()


def _paths_and_record(entry: str, ret):
    """(emitted name -> path, EmitRecord) from an entry point's DIRECT
    return value (never a copy: dict copies drop .record)."""
    if entry == "run_amendment_packet":
        self_paths = {mf.filename: None for mf in ret.mailed_files}
        return self_paths, ret.record
    emitted = ret if entry == "emit_pdfs" else ret[1]
    return emitted, emitted.record


def _years_for(jurisdiction: str, form: str) -> tuple[int, ...]:
    if form in year_manifest.SCORP_FORMS:
        return year_manifest.SCORP_FEDERAL_YEARS
    if form in year_manifest.CA_SCORP_FORMS:
        return year_manifest.CA_SCORP_YEARS
    if jurisdiction == "federal":
        return tuple(y for y in year_manifest.FEDERAL_YEARS
                     if year_manifest.form_supported_in_year(form, y))
    return year_manifest.CALIFORNIA_YEARS


class FillSpecForTests(unittest.TestCase):
    """fill_spec_for returns the class's CANONICAL spec: the mapping exactly
    as get_mapping returns it, and every fill getter the class defines,
    verbatim."""

    def test_every_catalog_form_year(self):
        for (juris, form), entry in sorted(CATALOG.items()):
            cls = entry.mapping_cls
            for year in _years_for(juris, form):
                if (juris, form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(form=form, year=year):
                    spec = fill_spec_for(cls, year)
                    mapping = cls.get_mapping(year)
                    self.assertEqual(spec.mapping, mapping)
                    self.assertEqual(
                        spec.kind,
                        "repeater" if "scalars" in mapping else "flat")
                    for part, getter in FILL_GETTERS.items():
                        expected = (getattr(cls, getter)(year)
                                    if hasattr(cls, getter) else None)
                        got = getattr(spec, part)
                        if expected is None:
                            self.assertFalse(got)
                        else:
                            self.assertEqual(got, expected)

    def test_unknown_getter_raises_naming_it(self):
        class Stub(PdfFormMapping):
            _FORM_NAME = "Stub"
            _MAPPINGS = {2025: {"k": "f"}}

            @classmethod
            def get_unknown_thing(cls, year):
                return {}

        with self.assertRaises(ValueError) as cm:
            fill_spec_for(Stub, 2025)
        self.assertIn("get_unknown_thing", str(cm.exception))

    def test_every_getter_on_every_mapping_class_is_classified(self):
        import importlib
        import pkgutil

        import tenforty.mappings as mappings_pkg
        getters = set()
        for mod_info in pkgutil.iter_modules(mappings_pkg.__path__):
            mod = importlib.import_module(f"tenforty.mappings.{mod_info.name}")
            for _n, obj in inspect.getmembers(mod, inspect.isclass):
                if (obj.__module__ == mod.__name__
                        and issubclass(obj, PdfFormMapping)
                        and obj is not PdfFormMapping):
                    getters |= {n for n in dir(obj) if n.startswith("get_")}
        known = set(FILL_GETTERS.values()) | set(KNOWN_NON_FILL_GETTERS)
        self.assertEqual(getters - known, set())
        # The pinned list is the live census, not a superset of stale names.
        self.assertEqual(set(KNOWN_NON_FILL_GETTERS),
                         getters - set(FILL_GETTERS.values()))

    def test_every_known_non_fill_getter_has_a_reason(self):
        for name, reason in KNOWN_NON_FILL_GETTERS.items():
            with self.subTest(getter=name):
                self.assertTrue(name.startswith("get_"))
                self.assertGreater(len(reason.strip()), 15)

    def test_non_fill_getters_are_not_folded_in(self):
        from tenforty.mappings.pdf_f1120s import PdfF1120S
        spec = fill_spec_for(PdfF1120S, 2025)
        header = PdfF1120S.get_entity_header_fields(2025)
        self.assertFalse(set(header) & set(spec.mapping))


class FlattenedTests(unittest.TestCase):

    def test_empty_repeaters_flatten_to_the_scalars(self):
        from tenforty.mappings.pdf_f8962 import PdfF8962
        for year in (2021, 2025):
            with self.subTest(year=year):
                spec = fill_spec_for(PdfF8962, year)
                flat = spec.flattened()
                self.assertEqual(flat.kind, "flat")
                self.assertEqual(flat.mapping,
                                 PdfF8962.get_mapping(year)["scalars"])
                self.assertEqual(flat.derivations, spec.derivations)

    def test_row_groups_merge_in_scalars_then_groups_order(self):
        spec = FillSpec(kind="repeater", mapping={
            "scalars": {"a": "F1"},
            "repeaters": {"box_a_rows": [{"r1": "F2"}, {"r2": "F3"}],
                          "box_d_rows": [{"r3": "F4"}]}})
        self.assertEqual(list(spec.flattened().mapping.items()),
                         [("a", "F1"), ("r1", "F2"), ("r2", "F3"),
                          ("r3", "F4")])

    def test_key_collision_refuses(self):
        spec = FillSpec(kind="repeater", mapping={
            "scalars": {"a": "F1"},
            "repeaters": {"g": [{"a": "F9"}]}})
        with self.assertRaises(ValueError) as cm:
            spec.flattened()
        self.assertIn("'a'", str(cm.exception))

    def test_template_repeater_refuses(self):
        spec = FillSpec(kind="repeater", mapping={
            "scalars": {}, "repeaters": {"rows": {
                "template": {"x": "F{i}"}, "max_slots": 3}}})
        with self.assertRaises(ValueError):
            spec.flattened()

    def test_flat_spec_refuses(self):
        with self.assertRaises(ValueError):
            FillSpec(kind="flat", mapping={"a": "F"}).flattened()

    def test_no_collision_in_any_flattened_class_today(self):
        from tenforty.mappings.pdf_8959 import Pdf8959
        from tenforty.mappings.pdf_f8582 import PdfF8582
        from tenforty.mappings.pdf_f8949 import PdfF8949
        from tenforty.mappings.pdf_f8962 import PdfF8962
        from tenforty.mappings.pdf_f8995 import PdfF8995
        for cls in (Pdf8959, PdfF8582, PdfF8949, PdfF8962, PdfF8995):
            for year in year_manifest.FEDERAL_YEARS:
                if not year_manifest.form_supported_in_year(
                        {"Pdf8959": "8959", "PdfF8582": "f8582",
                         "PdfF8949": "f8949", "PdfF8962": "f8962",
                         "PdfF8995": "f8995"}[cls.__name__], year):
                    continue
                with self.subTest(cls=cls.__name__, year=year):
                    fill_spec_for(cls, year).flattened()


class ExtendTests(unittest.TestCase):

    def test_flat_extend_merges_and_leaves_the_original(self):
        spec = FillSpec(kind="flat", mapping={"a": "F1"},
                        checkbox_states={"a": "/1"})
        out = spec.extend(mapping={"b": "F2"}, checkbox_states={"b": "/Yes"})
        self.assertEqual(out.mapping, {"a": "F1", "b": "F2"})
        self.assertEqual(out.checkbox_states, {"a": "/1", "b": "/Yes"})
        self.assertEqual(spec.mapping, {"a": "F1"})

    def test_repeater_extend_merges_into_the_scalars(self):
        spec = FillSpec(kind="repeater", mapping={
            "scalars": {"a": "F1"}, "repeaters": {"r": {"template": {},
                                                         "max_slots": 1}}})
        out = spec.extend(mapping={"b": "F2"})
        self.assertEqual(out.mapping["scalars"], {"a": "F1", "b": "F2"})
        self.assertEqual(out.mapping["repeaters"], spec.mapping["repeaters"])

    def test_unknown_part_refuses(self):
        with self.assertRaises(TypeError):
            FillSpec(kind="flat", mapping={}).extend(values={"x": 1})


class EmitRecordTests(unittest.TestCase):
    """The record carries exactly the objects the filler was handed."""

    def test_every_case_records_each_fill_with_the_identical_values(self):
        for name, (entry, _r) in sorted(cases.CASES.items()):
            ret, out, captured = _RUNS[name]
            with self.subTest(case=name):
                _paths, record = _paths_and_record(entry, ret)
                self.assertIsInstance(record, EmitRecord)
                self.assertEqual(len(record), len(captured))
                self.assertEqual(sorted(id(v) for v in captured),
                                 sorted(id(r.values) for r in record))
                for rec in record:
                    self.assertIsInstance(rec, RecordedForm)
                    self.assertIsInstance(rec.spec, FillSpec)
                    self.assertTrue(rec.pdf_path.exists(), rec.pdf_path)
                    self.assertIn(rec.form, set(CATALOG) | {
                        ("federal", "f1040x"), ("california", "schedule_x"),
                        ("federal", "f3115")})

    def test_amended_540_record_points_at_the_delivered_file(self):
        ret, out, _c = _RUNS["run_amendment_packet_2024"]
        f540 = [r for r in ret.record if r.form == ("california", "f540")]
        self.assertEqual(len(f540), 1)
        self.assertEqual(f540[0].pdf_path.name, "f540_amended_2024.pdf")


class EveryEntryPointCarriesRecordTests(unittest.TestCase):

    def test_the_six_entry_points_each_carry_a_record(self):
        seen = set()
        for name, (entry, _r) in sorted(cases.CASES.items()):
            ret, out, _c = _RUNS[name]
            seen.add(entry)
            with self.subTest(case=name):
                paths, record = _paths_and_record(entry, ret)
                self.assertIsInstance(record, EmitRecord)
                self.assertGreater(len(record), 0)
                if entry != "run_amendment_packet":
                    self.assertIsInstance(paths, EmitResult)
                    self.assertIsInstance(paths, dict)
                else:
                    self.assertIsInstance(ret, PacketManifest)
        self.assertEqual(seen, ENTRY_POINTS)

    def test_every_public_emit_or_run_method_is_classified(self):
        public = {n for n, _ in inspect.getmembers(
            ReturnOrchestrator, inspect.isfunction)
            if (n.startswith("emit") or n.startswith("run_"))}
        self.assertEqual(public - ENTRY_POINTS - set(NON_EMITTING), set())
        self.assertEqual(ENTRY_POINTS & set(NON_EMITTING), set())

    def test_union_of_recorded_and_non_fill_is_every_emitted_file(self):
        for name, (entry, _r) in sorted(cases.CASES.items()):
            ret, out, _c = _RUNS[name]
            with self.subTest(case=name):
                paths, record = _paths_and_record(entry, ret)
                recorded = {r.pdf_path.name for r in record}
                if entry == "run_amendment_packet":
                    names = {n for n in paths if n.endswith(".pdf")}
                    self.assertLessEqual(names, recorded)
                    continue
                unclassified = [
                    key for key, path in paths.items()
                    if path.name not in recorded
                    and registry.non_fill_reason(key) is None]
                self.assertEqual(unclassified, [])
                # And nothing recorded is missing from the emitted dict.
                self.assertLessEqual(
                    recorded, {p.name for p in paths.values()})

    def test_non_fill_entries_are_exact_or_anchored_with_reasons(self):
        for pattern, reason in registry.NON_FILL_EMITTED.items():
            with self.subTest(pattern=pattern):
                self.assertGreater(len(reason.strip()), 15)
        self.assertIsNotNone(registry.non_fill_reason("1120s_k1_qbi_stmt_3"))
        self.assertIsNone(registry.non_fill_reason("1120s_k1_qbi_stmt_x"))
        self.assertIsNone(registry.non_fill_reason("1120s_k1_3"))
        self.assertIsNone(registry.non_fill_reason("x_f3115_asset_stmt"))
        self.assertIsNone(registry.non_fill_reason("f3115_asset_stmt_extra"))


class ByteIdenticalEmitTests(unittest.TestCase):
    """Plumbing only: every emitted PDF is byte-identical to the one emitted
    before the reroute."""

    def test_every_case_matches_its_before_snapshot(self):
        for name in sorted(cases.CASES):
            _ret, out, _c = _RUNS[name]
            with self.subTest(case=name):
                after = cases.snapshot(out)
                before = cases.load_before(name)
                self.assertEqual(sorted(after), sorted(before))
                for pdf in sorted(before):
                    self.assertEqual(after[pdf]["fields"],
                                     before[pdf]["fields"], pdf)
                    self.assertEqual(after[pdf]["sha256"],
                                     before[pdf]["sha256"], pdf)


class SingleChokepointTests(unittest.TestCase):
    """Review Focus 4: no PdfFiller.fill / fill_with_repeaters call anywhere
    under tenforty/ except inside verification/fill.py, and the pypdf field
    write primitive only inside PdfFiller itself (filing/pdf.py)."""

    @staticmethod
    def _calls(attrs):
        root = REPO_ROOT / "tenforty"
        found = []
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in attrs):
                    found.append(f"{rel}:{node.lineno} .{node.func.attr}(")
        return found

    def test_fill_calls_only_in_the_chokepoint(self):
        offenders = [c for c in self._calls({"fill", "fill_with_repeaters"})
                     if not c.startswith("tenforty/verification/fill.py:")]
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_field_write_primitive_only_in_pdf_filler(self):
        offenders = [c for c in self._calls({"update_page_form_field_values"})
                     if not c.startswith("tenforty/filing/pdf.py:")]
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_the_chokepoint_calls_the_filler(self):
        source = Path(fill_module.__file__).read_text()
        self.assertIn(".fill(", source)
        self.assertIn(".fill_with_repeaters(", source)
