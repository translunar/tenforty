"""Unit tests for the opt-in on-disk cache of SpreadsheetEngine answers.

The cache wraps compute()'s contract (args in -> dict out), so every test stubs
the recalculation phases and the subprocess module; no real soffice can launch.
The template is a small synthetic workbook, read only for its defined names.
"""

import datetime
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
from openpyxl.workbook.defined_name import DefinedName

from tenforty.mappings.f1040 import F1040
from tenforty.oracle import engine as engine_mod
from tenforty.oracle.engine import SpreadsheetEngine
from tests.helpers import SPREADSHEETS_DIR

_VERSION = "LibreOffice 99.9.9 synthetic"
_REAL_RECALCULATE = SpreadsheetEngine._recalculate


def _write_template(path: Path, stamp: str = "", wages_cell: str = "$A$1") -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet"
    workbook.create_sheet("Other")
    sheet["Z1"] = stamp
    for name, target in (
        ("Wages", f"Sheet!{wages_cell}"),
        ("WagesAlias", "'Sheet'!$A$1"),
        ("AGI", "Sheet!$A$2"),
    ):
        workbook.defined_names[name] = DefinedName(name, attr_text=target)
    workbook.save(path)


def _mapping(inputs=None, outputs=None, sheets=None) -> type:
    class _Mapping:
        INPUTS = {2025: inputs or {"wages": "Wages", "other": "B2"}}
        OUTPUTS = {2025: outputs or {"agi": "AGI", "tax": "C3"}}
        SHEET_MAP = {2025: sheets or {"other": "Sheet", "tax": "Sheet"}}

        @classmethod
        def get_inputs(cls, year):
            return cls.INPUTS[year]

        @classmethod
        def get_outputs(cls, year):
            return cls.OUTPUTS[year]

    return _Mapping


class _CacheHarness(unittest.TestCase):
    """Caching enabled, recalculation phases stubbed, subprocess faked."""

    env = {"TENFORTY_ORACLE_CACHE": "1"}

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.cache_dir = self.tmp / "cache"
        self.template = self.tmp / "templates" / "1040.xlsx"
        self.template.parent.mkdir()
        _write_template(self.template)
        self.mapping = _mapping()
        self.inputs = {"wages": 100, "other": 2.5}

        env = patch.dict(
            os.environ,
            {**self.env, "TENFORTY_ORACLE_CACHE_DIR": str(self.cache_dir)},
        )
        env.start()
        self.addCleanup(env.stop)
        if "TENFORTY_ORACLE_CACHE" not in self.env:
            os.environ.pop("TENFORTY_ORACLE_CACHE", None)

        self.answer = {"agi": 100, "tax": 12.5}
        for name, kwargs in (
            ("_write_inputs", {}),
            ("_recalculate", {"return_value": self.tmp / "recalculated.xlsx"}),
            ("_read_outputs", {"side_effect": self._fake_read}),
        ):
            patcher = patch.object(SpreadsheetEngine, name, **kwargs)
            setattr(self, name.lstrip("_"), patcher.start())
            self.addCleanup(patcher.stop)

        self.run_mock = MagicMock(side_effect=self._fake_run)
        run_patch = patch("tenforty.oracle.engine.subprocess.run", self.run_mock)
        run_patch.start()
        self.addCleanup(run_patch.stop)
        self.version = _VERSION

        engine_mod._soffice_version.cache_clear()
        self.addCleanup(engine_mod._soffice_version.cache_clear)

    def _fake_read(self, _path, output_map, _sheet_map):
        return {key: self.answer.get(key) for key in output_map}

    def _fake_run(self, cmd, *_a, **_kw):
        self.assertEqual(cmd, ["soffice", "--version"])
        return MagicMock(returncode=0, stdout=self.version, stderr="")

    def compute(self, mapping=None, inputs=None, template=None, work_dir=None):
        return SpreadsheetEngine().compute(
            spreadsheet_path=template or self.template,
            mapping=mapping or self.mapping,
            year=2025,
            inputs=self.inputs if inputs is None else inputs,
            work_dir=work_dir or self.tmp / "work",
        )

    def entries(self) -> list[Path]:
        return sorted(self.cache_dir.glob("*")) if self.cache_dir.exists() else []


class HitMissContract(_CacheHarness):

    def test_miss_invokes_recalc_and_stores_then_hit_reuses_it(self) -> None:
        first = self.compute()
        self.assertEqual(self.recalculate.call_count, 1)
        self.assertEqual(len(self.entries()), 1)

        second = self.compute()
        self.assertEqual(self.recalculate.call_count, 1)
        self.write_inputs.assert_called_once()
        self.read_outputs.assert_called_once()
        self.assertEqual(first, {"agi": 100, "tax": 12.5})
        self.assertEqual(second, first)

    def test_harvested_value_types_survive_the_round_trip(self) -> None:
        self.answer = {"agi": 7, "tax": 7.0, "note": "#REF!", "flag": True, "gone": None}
        mapping = _mapping(outputs={key: "AGI" for key in self.answer})
        self.compute(mapping=mapping)
        hit = self.compute(mapping=mapping)
        self.assertEqual(self.recalculate.call_count, 1)
        self.assertEqual(
            {key: type(value) for key, value in hit.items()},
            {key: type(value) for key, value in self.answer.items()},
        )
        self.assertEqual(hit, self.answer)

    def test_entry_is_key_named_json_with_outputs_and_meta(self) -> None:
        self.compute()
        entry = self.entries()[0]
        self.assertEqual(entry.suffix, ".json")
        self.assertRegex(entry.stem, r"^[0-9a-f]{64}$")
        payload = json.loads(entry.read_text())
        self.assertEqual(set(payload), {"outputs", "meta"})
        self.assertEqual(payload["outputs"], {"agi": 100, "tax": 12.5})
        meta = payload["meta"]
        self.assertEqual(set(meta), {"created", "year", "template", "soffice"})
        self.assertEqual(meta["year"], 2025)
        self.assertEqual(meta["template"], "1040.xlsx")
        self.assertEqual(meta["soffice"], _VERSION)
        datetime.datetime.fromisoformat(meta["created"])

    def test_mutating_a_returned_dict_does_not_poison_the_cache(self) -> None:
        self.compute()["agi"] = "poison from the miss return"
        self.compute()["agi"] = "poison from the hit return"
        self.assertEqual(self.compute()["agi"], 100)
        self.assertEqual(self.recalculate.call_count, 1)

    def test_counters_count_hits_and_misses(self) -> None:
        before = engine_mod.cache_stats()
        self.compute()
        self.compute()
        self.compute()
        after = engine_mod.cache_stats()
        self.assertEqual(after["misses"] - before["misses"], 1)
        self.assertEqual(after["hits"] - before["hits"], 2)

    def test_counters_are_a_snapshot(self) -> None:
        before = engine_mod.cache_stats()
        engine_mod.cache_stats()["hits"] = before["hits"] + 1000
        self.assertEqual(engine_mod.cache_stats(), before)


class KeyComposition(_CacheHarness):
    """Each component of the key must split the entry; the rest must not."""

    def _change_template(self) -> None:
        _write_template(self.template, stamp="revised")

    def _change_engine_source(self) -> None:
        copy = self.tmp / "engine_copy.py"
        copy.write_bytes(Path(engine_mod.__file__).read_bytes() + b"\n# edited\n")
        patcher = patch.object(engine_mod, "__file__", str(copy))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _change_soffice_version(self) -> None:
        self.version = "LibreOffice 99.9.10 synthetic"
        engine_mod._soffice_version.cache_clear()

    def _assert_splits(self, change, **compute_kwargs) -> None:
        self.compute()
        self.assertEqual(self.recalculate.call_count, 1)
        if change is not None:
            change()
        self.compute(**compute_kwargs)
        self.assertEqual(self.recalculate.call_count, 2)
        self.assertEqual(len(self.entries()), 2)

    def test_template_bytes(self) -> None:
        self._assert_splits(self._change_template)

    def test_engine_source(self) -> None:
        self._assert_splits(self._change_engine_source)

    def test_soffice_version(self) -> None:
        self._assert_splits(self._change_soffice_version)

    def test_openpyxl_version(self) -> None:
        def change() -> None:
            patcher = patch.object(engine_mod.openpyxl, "__version__", "99.9.9")
            patcher.start()
            self.addCleanup(patcher.stop)
        self._assert_splits(change)

    def test_one_input_value(self) -> None:
        self._assert_splits(None, inputs={"wages": 101, "other": 2.5})

    def test_an_added_input(self) -> None:
        self._assert_splits(None, inputs={"wages": 100, "other": 2.5, "extra": 0})

    def test_a_removed_input(self) -> None:
        self._assert_splits(None, inputs={"wages": 100})

    def test_int_and_float_inputs_are_distinct(self) -> None:
        self._assert_splits(None, inputs={"wages": 100.0, "other": 2.5})

    def test_string_and_number_inputs_are_distinct(self) -> None:
        self._assert_splits(None, inputs={"wages": "100", "other": 2.5})

    def test_float_inputs_use_full_precision(self) -> None:
        self._assert_splits(None, inputs={"wages": 100, "other": 2.5000000000000004})

    def test_input_map(self) -> None:
        self._assert_splits(
            None, mapping=_mapping(inputs={"wages": "Wages", "other": "B3"}))

    def test_output_map(self) -> None:
        self._assert_splits(None, mapping=_mapping(outputs={"agi": "AGI", "tax": "C4"}))

    def test_sheet_map(self) -> None:
        self._assert_splits(
            None, mapping=_mapping(sheets={"other": "Sheet", "tax": "Elsewhere"}))

    def test_components_cannot_alias_across_map_boundaries(self) -> None:
        """The same pairs filed under a different component are a different key."""
        same = {"k": "V"}
        self.compute(mapping=_mapping(inputs=same, outputs={"o": "O"}, sheets={"s": "S"}))
        self.compute(mapping=_mapping(inputs={"o": "O"}, outputs={"s": "S"}, sheets=same))
        self.assertEqual(self.recalculate.call_count, 2)

    def test_template_path_is_not_a_component(self) -> None:
        """Gate worktrees are rebuilt constantly; the bytes are what matter."""
        self.compute()
        moved = self.tmp / "another_worktree" / "1040.xlsx"
        moved.parent.mkdir()
        shutil.copy2(self.template, moved)
        self.compute(template=moved)
        self.assertEqual(self.recalculate.call_count, 1)

    def test_work_dir_is_not_a_component(self) -> None:
        self.compute()
        self.compute(work_dir=self.tmp / "elsewhere")
        self.assertEqual(self.recalculate.call_count, 1)

    def test_input_insertion_order_is_not_a_component(self) -> None:
        self.compute(inputs={"wages": 100, "other": 2.5})
        self.compute(inputs={"other": 2.5, "wages": 100})
        self.assertEqual(self.recalculate.call_count, 1)


class InputsSharingACellBypassTheCache(_CacheHarness):
    """_write_inputs is last-write-wins and the key sorts inputs, so inputs that
    share a cell could give two answers under one key. Those computes never cache.
    """

    def _assert_bypassed(self, mapping, inputs) -> None:
        before = engine_mod.cache_stats()
        self.compute(mapping=mapping, inputs=inputs)
        self.compute(mapping=mapping, inputs=dict(reversed(list(inputs.items()))))
        after = engine_mod.cache_stats()
        self.assertEqual(self.recalculate.call_count, 2)
        self.assertEqual(self.entries(), [])
        self.assertEqual(after["bypasses"] - before["bypasses"], 2)
        self.assertEqual(after["hits"], before["hits"])
        self.assertEqual(after["misses"], before["misses"])
        self.run_mock.assert_not_called()

    def test_same_sheet_and_cell_ref(self) -> None:
        self._assert_bypassed(
            _mapping(inputs={"a": "C3", "b": "C3"},
                     sheets={"a": "Sheet", "b": "Sheet", "tax": "Sheet"}),
            {"a": 1, "b": 2})

    def test_same_cell_in_a_different_spelling(self) -> None:
        self._assert_bypassed(
            _mapping(inputs={"a": "C3", "b": "$c$3"},
                     sheets={"a": "Sheet", "b": "Sheet", "tax": "Sheet"}),
            {"a": 1, "b": 2})

    def test_two_defined_names_for_one_cell(self) -> None:
        self._assert_bypassed(
            _mapping(inputs={"a": "Wages", "b": "WagesAlias"}), {"a": 1, "b": 2})

    def test_defined_name_and_direct_ref_for_one_cell(self) -> None:
        self._assert_bypassed(
            _mapping(inputs={"a": "Wages", "b": "A1"},
                     sheets={"b": "Sheet", "tax": "Sheet"}),
            {"a": 1, "b": 2})

    def test_equal_values_still_bypass(self) -> None:
        self._assert_bypassed(
            _mapping(inputs={"a": "Wages", "b": "WagesAlias"}), {"a": 1, "b": 1})

    def test_unreadable_template_bypasses(self) -> None:
        self.template.write_bytes(b"not a workbook")
        self._assert_bypassed(self.mapping, {"wages": 1})

    def test_input_with_no_route_reaches_the_real_writer(self) -> None:
        """_write_inputs owns this refusal (stubbed here), so it must be reached."""
        mapping = _mapping(inputs={"a": "C3"})
        self.compute(mapping=mapping, inputs={"a": 1})
        self.write_inputs.assert_called_once()
        self.assertEqual(self.entries(), [])

    def _assert_cached(self, mapping, inputs) -> None:
        before = engine_mod.cache_stats()
        self.compute(mapping=mapping, inputs=inputs)
        self.compute(mapping=mapping, inputs=inputs)
        self.assertEqual(self.recalculate.call_count, 1)
        self.assertEqual(
            engine_mod.cache_stats()["bypasses"], before["bypasses"])

    def test_sharing_in_the_map_only_does_not_bypass(self) -> None:
        self._assert_cached(
            _mapping(inputs={"a": "Wages", "b": "WagesAlias"}), {"a": 1})

    def test_unmapped_inputs_cannot_share_a_cell(self) -> None:
        self._assert_cached(
            _mapping(inputs={"a": "Wages"}), {"a": 1, "unmapped": 2, "also": 3})

    def test_same_ref_on_different_sheets_does_not_bypass(self) -> None:
        self._assert_cached(
            _mapping(inputs={"a": "C3", "b": "C3"},
                     sheets={"a": "Sheet", "b": "Other", "tax": "Sheet"}),
            {"a": 1, "b": 2})

    def test_defined_names_are_read_once_per_template_content(self) -> None:
        real_load = openpyxl.load_workbook
        with patch.object(engine_mod.openpyxl, "load_workbook",
                          side_effect=real_load) as load:
            self.compute()
            self.compute(inputs={"wages": 1})
        self.assertLessEqual(load.call_count, 1)

    def test_revised_template_is_resolved_afresh(self) -> None:
        """Same path, new bytes: the name no longer lands on the other input's cell."""
        mapping = _mapping(inputs={"a": "Wages", "b": "A1"},
                           sheets={"b": "Sheet", "tax": "Sheet"})
        inputs = {"a": 1, "b": 2}
        self.compute(mapping=mapping, inputs=inputs)
        self.assertEqual(self.entries(), [])
        _write_template(self.template, wages_cell="$B$9")
        self.compute(mapping=mapping, inputs=inputs)
        self.assertEqual(len(self.entries()), 1)

    def test_real_k1_entity_type_keys(self) -> None:
        """The flattener supplies one entity-type key per K-1, so real computes
        cache; a caller supplying both reaches the shared cell and bypasses."""
        template = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        before = engine_mod.cache_stats()
        self.compute(mapping=F1040, template=template,
                     inputs={"k1_a_entity_type_s_corp": "X"})
        self.assertEqual(engine_mod.cache_stats()["bypasses"], before["bypasses"])
        self.assertEqual(len(self.entries()), 1)
        self.compute(mapping=F1040, template=template,
                     inputs={"k1_a_entity_type_s_corp": "X",
                             "k1_a_entity_type_partnership": "X"})
        self.assertEqual(
            engine_mod.cache_stats()["bypasses"], before["bypasses"] + 1)
        self.assertEqual(len(self.entries()), 1)


class Disabled(_CacheHarness):
    """Unset, or anything other than exactly "1", means today's behavior."""

    env = {}

    def _assert_uncached(self) -> None:
        before = engine_mod.cache_stats()
        self.compute()
        self.compute()
        self.assertEqual(self.recalculate.call_count, 2)
        self.assertFalse(self.cache_dir.exists())
        self.run_mock.assert_not_called()
        self.assertEqual(engine_mod.cache_stats(), before)

    def test_unset(self) -> None:
        self.assertNotIn("TENFORTY_ORACLE_CACHE", os.environ)
        with patch.object(engine_mod.openpyxl, "load_workbook") as load:
            self._assert_uncached()
        load.assert_not_called()

    def test_other_values(self) -> None:
        for value in ("0", "", "true", "yes", "11", " 1"):
            with self.subTest(value=value):
                self.recalculate.reset_mock()
                with patch.dict(os.environ, {"TENFORTY_ORACLE_CACHE": value}):
                    self._assert_uncached()

    def test_existing_entry_is_not_read(self) -> None:
        with patch.dict(os.environ, {"TENFORTY_ORACLE_CACHE": "1"}):
            self.compute()
        self.run_mock.reset_mock()
        entry = self.entries()[0]
        stored = entry.read_bytes()
        self.answer = {"agi": 555, "tax": 5.5}
        self.assertEqual(self.compute()["agi"], 555)
        self.assertEqual(self.recalculate.call_count, 2)
        self.assertEqual(entry.read_bytes(), stored)
        self.run_mock.assert_not_called()


class CacheDirectory(_CacheHarness):

    def test_created_lazily_on_first_store(self) -> None:
        self.assertFalse(self.cache_dir.exists())
        self.compute()
        self.assertTrue(self.cache_dir.is_dir())

    def test_nested_cache_dir_is_created(self) -> None:
        nested = self.tmp / "a" / "b" / "c"
        with patch.dict(os.environ, {"TENFORTY_ORACLE_CACHE_DIR": str(nested)}):
            self.compute()
        self.assertEqual(len(list(nested.glob("*.json"))), 1)

    def test_default_is_user_level(self) -> None:
        home = self.tmp / "home"
        home.mkdir()
        with patch.dict(os.environ, {"HOME": str(home)}):
            del os.environ["TENFORTY_ORACLE_CACHE_DIR"]
            self.compute()
        self.assertEqual(
            len(list((home / ".cache" / "tenforty-oracle").glob("*.json"))), 1)

    def test_entries_are_private_to_the_user(self) -> None:
        """Answers computed from a real return are that filer's figures."""
        self.compute()
        self.assertEqual(self.cache_dir.stat().st_mode & 0o077, 0)
        self.assertEqual(self.entries()[0].stat().st_mode & 0o077, 0)


class CorruptEntries(_CacheHarness):
    """Unusable entry = miss, then overwritten by the recomputed answer."""

    def _assert_recomputed_and_rewritten(self, damaged: bytes) -> None:
        self.compute()
        entry = self.entries()[0]
        entry.write_bytes(damaged)
        self.answer = {"agi": 200, "tax": 25.0}
        self.assertEqual(self.compute(), {"agi": 200, "tax": 25.0})
        self.assertEqual(self.recalculate.call_count, 2)
        self.assertEqual(json.loads(entry.read_text())["outputs"]["agi"], 200)
        self.assertEqual(self.compute()["agi"], 200)
        self.assertEqual(self.recalculate.call_count, 2)

    def test_truncated_json(self) -> None:
        self._assert_recomputed_and_rewritten(b'{"outputs": {"agi": 1')

    def test_not_utf8(self) -> None:
        self._assert_recomputed_and_rewritten(b"\xff\xfe\x00garbage")

    def test_json_not_an_object(self) -> None:
        self._assert_recomputed_and_rewritten(b"[1, 2, 3]")

    def test_missing_outputs(self) -> None:
        self._assert_recomputed_and_rewritten(b'{"meta": {}}')

    def test_outputs_not_an_object(self) -> None:
        self._assert_recomputed_and_rewritten(b'{"outputs": [1, 2], "meta": {}}')

    def test_outputs_missing_a_harvested_key(self) -> None:
        self._assert_recomputed_and_rewritten(b'{"outputs": {"agi": 1}, "meta": {}}')

    def test_outputs_with_an_unmapped_key(self) -> None:
        self._assert_recomputed_and_rewritten(
            b'{"outputs": {"agi": 1, "tax": 2, "junk": 3}, "meta": {}}')

    def test_entry_is_a_directory(self) -> None:
        self.compute()
        entry = self.entries()[0]
        entry.unlink()
        entry.mkdir()
        self.assertEqual(self.compute(), {"agi": 100, "tax": 12.5})
        self.assertEqual(self.recalculate.call_count, 2)


class FailsOpenToRecomputation(_CacheHarness):
    """Cache-layer trouble costs a recompute, never an exception or an answer."""

    ANSWER = {"agi": 100, "tax": 12.5}

    def test_cache_dir_cannot_be_created(self) -> None:
        self.cache_dir.write_text("a file where the directory belongs")
        self.assertEqual(self.compute(), self.ANSWER)
        self.assertEqual(self.compute(), self.ANSWER)
        self.assertEqual(self.recalculate.call_count, 2)

    def test_replace_failure_leaves_no_temp_file(self) -> None:
        with patch.object(engine_mod.os, "replace", side_effect=OSError("disk")):
            self.assertEqual(self.compute(), self.ANSWER)
        self.assertEqual(self.entries(), [])

    def test_key_failure_recomputes(self) -> None:
        with patch.object(engine_mod, "_cache_key", side_effect=ValueError("boom")):
            self.assertEqual(self.compute(), self.ANSWER)
        self.assertEqual(self.recalculate.call_count, 1)
        self.assertEqual(self.entries(), [])

    def test_lookup_failure_recomputes(self) -> None:
        self.compute()
        with patch.object(engine_mod.json, "loads", side_effect=RuntimeError("boom")):
            self.assertEqual(self.compute(), self.ANSWER)
        self.assertEqual(self.recalculate.call_count, 2)

    def test_non_json_output_is_returned_uncoerced_and_not_stored(self) -> None:
        moment = datetime.datetime(2025, 1, 2)
        self.answer = {"agi": moment, "tax": 1}
        self.assertEqual(self.compute(), {"agi": moment, "tax": 1})
        self.assertEqual(self.entries(), [])

    def test_output_json_would_reshape_is_not_stored(self) -> None:
        self.answer = {"agi": (1, 2), "tax": {3: "int key"}}
        self.assertEqual(self.compute(), self.answer)
        self.assertEqual(self.entries(), [])

    def test_values_strict_json_cannot_hold_are_not_stored(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.answer = {"agi": value, "tax": 1}
                self.compute()
                self.assertEqual(self.entries(), [])

    def test_missing_template_raises_exactly_as_uncached(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.compute(template=self.tmp / "absent.xlsx")
        self.assertEqual(self.entries(), [])

    def test_real_compute_errors_propagate_and_are_not_stored(self) -> None:
        self.recalculate.side_effect = RuntimeError("soffice timeout")
        with self.assertRaisesRegex(RuntimeError, "soffice timeout"):
            self.compute()
        self.assertEqual(self.entries(), [])


class VersionProbe(_CacheHarness):

    def test_runs_at_most_once_per_process(self) -> None:
        self.compute()
        self.compute(inputs={"wages": 1})
        self.assertEqual(self.run_mock.call_count, 1)

    def test_failed_probe_runs_at_most_once_and_disables_caching(self) -> None:
        """A key without the version could serve another LibreOffice's answers."""
        for failure in (
            FileNotFoundError("soffice"),
            subprocess.TimeoutExpired(cmd=["soffice"], timeout=30),
            MagicMock(returncode=1, stdout="soffice: broken install", stderr=""),
            MagicMock(returncode=0, stdout="   \n", stderr=""),
        ):
            with self.subTest(failure=failure):
                engine_mod._soffice_version.cache_clear()
                self.recalculate.reset_mock()
                self.run_mock.reset_mock()
                self.run_mock.side_effect = [failure]
                self.assertEqual(self.compute(), {"agi": 100, "tax": 12.5})
                self.assertEqual(self.compute(), {"agi": 100, "tax": 12.5})
                self.assertEqual(self.recalculate.call_count, 2)
                self.assertEqual(self.run_mock.call_count, 1)
                self.assertEqual(self.entries(), [])


class SanctionGuardsLaunchesNotReuse(_CacheHarness):
    """The tripwire stays on the miss path. _recalculate is real here, and the
    guard spy raises before anything below it could launch."""

    def test_miss_is_guarded_and_hit_is_not(self) -> None:
        self.compute()
        self.recalculate.side_effect = (
            lambda workbook, work_dir: _REAL_RECALCULATE(
                SpreadsheetEngine(), workbook, work_dir))
        guard = RuntimeError("non-oracle test reached soffice")
        with patch.object(engine_mod, "_assert_oracle_sanctioned",
                          side_effect=guard) as spy:
            self.assertEqual(self.compute(), {"agi": 100, "tax": 12.5})
            spy.assert_not_called()

            with self.assertRaises(RuntimeError) as ctx:
                self.compute(inputs={"wages": 999})
            self.assertIs(ctx.exception, guard)
            spy.assert_called_once()
        self.run_mock.assert_called_once_with(
            ["soffice", "--version"], capture_output=True, text=True, timeout=30)
        self.assertEqual(len(self.entries()), 1)


if __name__ == "__main__":
    unittest.main()
