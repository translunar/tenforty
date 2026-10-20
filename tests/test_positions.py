"""The contested-law positions registry (spec §13): every entry is
well-formed, and the first entry carries its citation trail as ledgered."""
import ast
import dataclasses
import datetime
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import MappingProxyType

import yaml

from tenforty import positions
from tenforty.models import FilingStatus, ScheduleCBusiness, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tenforty.models import SCorp199AInfo
from tests._scorp_fixtures import _make_v1_scenario
from tests.fixtures.spine_battery import build_wages_only
from tests.helpers import REPO_ROOT

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
QBI_SEHI = "qbi-sehi-shareholder-reduction"
_K1_ACKS = ("acknowledges_qbi_below_threshold", "acknowledges_unlimited_at_risk",
            "basis_tracked_externally",
            "acknowledges_no_partnership_se_earnings",
            "acknowledges_no_section_1231_gain",
            "acknowledges_no_more_than_four_k1s", "acknowledges_no_k1_credits",
            "acknowledges_no_section_179", "acknowledges_no_estate_trust_k1")


def _wages_only(**elections):
    base = build_wages_only(2024, FilingStatus.SINGLE)
    return dataclasses.replace(base, positions=dict(elections))


def _k1(entity_type, qbi, n=1):
    return ScheduleK1(
        entity_name=f"Example Entity {n}", entity_ein="00-0000000",
        entity_type=entity_type, material_participation=True,
        ordinary_business_income=qbi, qbi_amount=qbi)


def _reaching(sehi=3_000.0, qbi=10_000.0, extra_k1s=(), businesses=(),
              **elections):
    """Wages, a self-employed health insurance deduction and an S
    corporation K-1 carrying QBI: the shape the QBI/SEHI position reaches
    (``extra_k1s`` / ``businesses`` vary it). All synthetic."""
    base = build_wages_only(2024, FilingStatus.SINGLE)
    cfg = dataclasses.replace(
        base.config, self_employed_health_insurance_deduction=sehi,
        **{k: True for k in _K1_ACKS})
    return dataclasses.replace(
        base, config=cfg, positions=dict(elections),
        schedule_k1s=[_k1("s_corp", qbi), *extra_k1s],
        schedule_c_businesses=[ScheduleCBusiness(description=d)
                               for d in businesses])


class Wired:
    """Mixin: run with every registered position wired (phase 2's state),
    so an election can be accepted at all. Phase 1 wires none."""

    def setUp(self):
        super().setUp()
        wired = MappingProxyType({
            slug: dataclasses.replace(pos, wired=True)
            for slug, pos in positions.POSITIONS.items()})
        patcher = unittest.mock.patch.object(positions, "POSITIONS", wired)
        patcher.start()
        self.addCleanup(patcher.stop)


class RegistryWellFormedTests(unittest.TestCase):

    def test_registry_is_keyed_by_each_entry_slug(self):
        self.assertTrue(positions.POSITIONS)
        for slug, pos in positions.POSITIONS.items():
            with self.subTest(slug=slug):
                self.assertEqual(slug, pos.slug)
                self.assertRegex(slug, SLUG)

    def test_every_entry_is_well_formed(self):
        for slug, pos in positions.POSITIONS.items():
            with self.subTest(slug=slug):
                self.assertTrue(pos.question.strip())
                self.assertIsInstance(pos.recorded, datetime.date)
                self.assertGreaterEqual(len(pos.choices), 2)
                names = [c.slug for c in pos.choices]
                self.assertEqual(len(names), len(set(names)))
                for choice in pos.choices:
                    self.assertRegex(choice.slug, SLUG)
                    self.assertTrue(choice.position.strip())
                    self.assertTrue(choice.consequence.strip())
                    self.assertTrue(choice.sources, choice.slug)

    def test_every_source_is_labeled(self):
        for slug, pos in positions.POSITIONS.items():
            sources = [s for c in pos.choices for s in c.sources]
            sources += list(pos.shared_sources)
            for src in sources:
                with self.subTest(slug=slug, citation=src.citation):
                    self.assertIn(src.kind, positions.SOURCE_KINDS)
                    self.assertIn(src.fidelity, positions.FIDELITIES)
                    self.assertTrue(src.citation.strip())
                    self.assertTrue(src.text.strip())

    def test_every_entry_has_a_reachability_predicate(self):
        for slug, pos in positions.POSITIONS.items():
            with self.subTest(slug=slug):
                self.assertTrue(callable(pos.reached_when))
                self.assertTrue(callable(pos.may_reach))

    def test_the_label_vocabularies(self):
        self.assertEqual(positions.SOURCE_KINDS,
                         frozenset({"authority", "commentary"}))
        self.assertEqual(positions.FIDELITIES,
                         frozenset({"verbatim", "paraphrased", "secondhand"}))


class QbiSehiEntryTests(unittest.TestCase):
    """The first entry, against the 2026-10-18 ledger record."""

    def setUp(self):
        self.pos = positions.POSITIONS[QBI_SEHI]

    def _source(self, fragment):
        found = [s for c in self.pos.choices for s in c.sources
                 if fragment in s.citation]
        found += [s for s in self.pos.shared_sources if fragment in s.citation]
        self.assertEqual(len(found), 1, fragment)
        return found[0]

    def test_the_two_choices(self):
        self.assertEqual([c.slug for c in self.pos.choices],
                         ["irs-faq", "no-reduction"])
        self.assertEqual(self.pos.recorded, datetime.date(2026, 10, 18))

    def test_faq_a39_is_informal_and_historical(self):
        src = self._source("FAQ A39")
        self.assertEqual(src.kind, "commentary")
        self.assertEqual(src.fidelity, "verbatim")
        self.assertIn("This may result in QBI being reduced at both the "
                      "entity and the shareholder level.", src.text)
        for needle in ("Formerly Q33", "historical", "2026-05-12"):
            self.assertIn(needle, src.note)

    def test_the_regulation_is_quoted_verbatim(self):
        src = self._source("1.199A-3(b)(1)(vi)")
        self.assertEqual((src.kind, src.fidelity), ("authority", "verbatim"))
        self.assertIn("on a proportionate basis to the gross income received "
                      "from the trade or business", src.text)

    def test_the_status_keeps_the_aicpa_and_the_text_apart(self):
        self.assertIn("the AICPA (known secondhand) argues no; the "
                      "regulation's attribution clause and the statute's "
                      "wage exclusion support that reading", self.pos.status)

    def test_the_regulation_text_is_the_clause_with_a_bracketed_subject(self):
        src = self._source("1.199A-3(b)(1)(vi)")
        self.assertTrue(src.text.startswith("["))
        self.assertIn("bracketed subject is ours", src.note)

    def test_aicpa_is_secondhand_commentary(self):
        src = self._source("AICPA")
        self.assertEqual((src.kind, src.fidelity),
                         ("commentary", "secondhand"))

    def test_section_199a_c_4_is_marked_paraphrased(self):
        src = self._source("199A(c)(4)")
        self.assertEqual((src.kind, src.fidelity),
                         ("authority", "paraphrased"))

    def test_the_shared_chain(self):
        for fragment in ("162(l)", "1372", "Notice 2008-1"):
            with self.subTest(source=fragment):
                src = self._source(fragment)
                self.assertIn(src, self.pos.shared_sources)
                self.assertEqual(src.kind, "authority")



def _shapes():
    """(name, scenario) over the gate's shapes, reaching or not."""
    return (
        ("s-corp k1", _reaching()),
        ("two s-corp k1s", _reaching(extra_k1s=[_k1("s_corp", 5_000.0, 2)])),
        ("s-corp k1 + zero-qbi partnership k1",
         _reaching(extra_k1s=[_k1("partnership", 0.0, 2)])),
        ("s-corp k1 + partnership k1 with qbi",
         _reaching(extra_k1s=[_k1("partnership", 5_000.0, 2)])),
        ("partnership k1 only", dataclasses.replace(
            _reaching(), schedule_k1s=[_k1("partnership", 10_000.0)])),
        ("s-corp k1 + schedule c",
         _reaching(businesses=["Example Bindery"])),
        ("schedule c only", dataclasses.replace(
            _reaching(businesses=["Example Bindery"]), schedule_k1s=[])),
        ("no qbi", _reaching(qbi=0.0)),
        ("no sehi", _reaching(sehi=0.0)),
        ("wages", _wages_only()),
    )


class QbiSehiReachabilityPredicateTests(unittest.TestCase):
    """The ruled shape gate (S corporation only): a nonzero SEHI deduction
    sourced from the S corporation, read by shape as no Schedule C
    business, at least one S corporation K-1 with QBI, and no other K-1
    with QBI."""

    def setUp(self):
        self.reached = positions.POSITIONS[QBI_SEHI].reached_when

    def test_sehi_and_s_corp_k1_qbi_reach_it(self):
        self.assertTrue(self.reached(_reaching()))

    def test_either_alone_does_not(self):
        self.assertFalse(self.reached(_reaching(sehi=0.0)))
        self.assertFalse(self.reached(_reaching(qbi=0.0)))
        self.assertFalse(self.reached(_wages_only()))

    def test_the_shapes(self):
        reaching = {"s-corp k1", "two s-corp k1s",
                    "s-corp k1 + zero-qbi partnership k1"}
        for name, s in _shapes():
            with self.subTest(shape=name):
                self.assertIs(self.reached(s), name in reaching)


def _s_corp(sehi=3_000.0, section_199a=None, **elections):
    """A shareholder return with an S corporation return block: its K-1
    (and that K-1's QBI) is synthesized at compute time. All synthetic."""
    base = _make_v1_scenario(section_199a=section_199a)
    cfg = dataclasses.replace(
        base.config, self_employed_health_insurance_deduction=sehi)
    return dataclasses.replace(base, config=cfg, positions=dict(elections))


class QbiSehiLoadTimeViewTests(unittest.TestCase):
    """may_reach: false only when the loaded return definitely never
    reaches the position; reached_when must imply it."""

    def setUp(self):
        self.pos = positions.POSITIONS[QBI_SEHI]

    def test_an_s_corp_return_may_reach_it_before_its_k1_exists(self):
        s = _s_corp()
        self.assertEqual(s.schedule_k1s, [])
        self.assertFalse(self.pos.reached_when(s))
        self.assertTrue(self.pos.may_reach(s))

    def test_zero_sehi_never_reaches_it(self):
        self.assertFalse(self.pos.may_reach(_s_corp(sehi=0.0)))
        self.assertFalse(self.pos.may_reach(_wages_only()))

    def test_reaching_implies_may_reach(self):
        for name, s in (*_shapes(), ("s-corp", _s_corp())):
            with self.subTest(scenario=name):
                if self.pos.reached_when(s):
                    self.assertTrue(self.pos.may_reach(s))

    def test_a_schedule_c_or_partnership_return_definitely_never_reaches_it(
            self):
        # The loaded view is exact for what the S corporation pipeline
        # cannot change: it only appends S corporation K-1s.
        for name, s in (
                ("schedule c", dataclasses.replace(
                    _s_corp(), schedule_c_businesses=[
                        ScheduleCBusiness(description="Example Bindery")])),
                ("partnership k1 with qbi", dataclasses.replace(
                    _s_corp(),
                    schedule_k1s=[_k1("partnership", 5_000.0)]))):
            with self.subTest(scenario=name):
                self.assertFalse(self.pos.may_reach(s))


class SCorpElectionTests(Wired, unittest.TestCase):
    """Two-stage check: accepted at load while the S corporation K-1 does
    not exist yet, then re-checked exactly on the effective scenario."""

    def setUp(self):
        super().setUp()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()))

    def test_accepted_at_load(self):
        self.assertEqual(_s_corp(**{QBI_SEHI: "irs-faq"}).positions,
                         {QBI_SEHI: "irs-faq"})

    def test_zero_sehi_refuses_at_load(self):
        with self.assertRaisesRegex(ValueError, "never reaches"):
            _s_corp(sehi=0.0, **{QBI_SEHI: "irs-faq"})

    def test_kept_when_the_synthesized_k1_carries_qbi(self):
        effective, _ = self.orch._build_effective_scenario(
            _s_corp(**{QBI_SEHI: "irs-faq"}))
        self.assertTrue(any(k.qbi_amount for k in effective.schedule_k1s))
        self.assertEqual(effective.positions, {QBI_SEHI: "irs-faq"})

    def test_refused_at_compute_when_the_synthesized_k1_has_no_qbi(self):
        scenario = _s_corp(section_199a=SCorp199AInfo(qbi_override=0.0),
                           **{QBI_SEHI: "irs-faq"})
        with self.assertRaisesRegex(ValueError, "never reaches"):
            self.orch._build_effective_scenario(scenario)


class ElectionFieldTests(Wired, unittest.TestCase):
    """Scenario.positions: {slug: choice}, validated at construction."""

    def test_no_elections_by_default(self):
        self.assertEqual(build_wages_only(2024, FilingStatus.SINGLE).positions,
                         {})

    def test_a_valid_election_on_a_reaching_return_is_kept(self):
        self.assertEqual(_reaching(**{QBI_SEHI: "no-reduction"}).positions,
                         {QBI_SEHI: "no-reduction"})

    def test_an_unknown_position_refuses(self):
        with self.assertRaisesRegex(ValueError, "no-such-position") as cm:
            _reaching(**{"no-such-position": "irs-faq"})
        self.assertIn(QBI_SEHI, str(cm.exception))

    def test_an_unknown_choice_refuses_listing_the_valid_ones(self):
        with self.assertRaisesRegex(ValueError, "maybe") as cm:
            _reaching(**{QBI_SEHI: "maybe"})
        for choice in ("irs-faq", "no-reduction"):
            self.assertIn(choice, str(cm.exception))

    def test_an_election_the_return_never_reaches_refuses(self):
        with self.assertRaisesRegex(ValueError, "never reaches") as cm:
            _wages_only(**{QBI_SEHI: "irs-faq"})
        self.assertIn(QBI_SEHI, str(cm.exception))

    def test_a_malformed_block_refuses(self):
        for bad in (["irs-faq"], {QBI_SEHI: 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                dataclasses.replace(_reaching(), positions=bad)


class ElectionYamlTests(Wired, unittest.TestCase):
    """The top-level `positions:` key reaches the Scenario."""

    def _load(self, positions_block, sehi):
        data = yaml.safe_load(
            (REPO_ROOT / "tests" / "fixtures" / "k1_scorp_basic.yaml")
            .read_text())
        data["config"]["self_employed_health_insurance_deduction"] = sehi
        data["positions"] = positions_block
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.yaml"
            path.write_text(yaml.safe_dump(data))
            return load_scenario(path)

    def test_loads_an_election(self):
        self.assertEqual(
            self._load({QBI_SEHI: "irs-faq"}, 2_000.0).positions,
            {QBI_SEHI: "irs-faq"})

    def test_refuses_an_unreached_election(self):
        with self.assertRaisesRegex(ValueError, "never reaches"):
            self._load({QBI_SEHI: "irs-faq"}, 0.0)

    def test_an_empty_block_means_no_elections(self):
        self.assertEqual(self._load(None, 2_000.0).positions, {})

    def test_a_falsy_non_mapping_refuses(self):
        for bad in ([], False, 0, ""):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "must map a position slug"):
                self._load(bad, 2_000.0)


class ElectionHelperTests(Wired, unittest.TestCase):

    def test_returns_the_election_and_records_the_consult(self):
        with positions.recording() as record:
            self.assertEqual(positions.election(
                _reaching(**{QBI_SEHI: "irs-faq"}), QBI_SEHI), "irs-faq")
        self.assertEqual(record, [
            {"slug": QBI_SEHI, "choice": "irs-faq", "reached": True}])

    def test_every_entry_is_reached(self):
        # Ruling Q-R: entries exist only for reached positions, so reached
        # is True on every one.
        with positions.recording() as record:
            positions.election(_reaching(**{QBI_SEHI: "no-reduction"}),
                               QBI_SEHI)
        self.assertTrue(record)
        for entry in record:
            self.assertIs(entry["reached"], True)

    def test_a_repeated_consult_records_once(self):
        scenario = _reaching(**{QBI_SEHI: "irs-faq"})
        with positions.recording() as record:
            positions.election(scenario, QBI_SEHI)
            positions.election(scenario, QBI_SEHI)
        self.assertEqual(len(record), 1)

    def test_runs_do_not_share_a_record(self):
        with positions.recording() as first:
            positions.election(_reaching(**{QBI_SEHI: "irs-faq"}), QBI_SEHI)
        with positions.recording() as second:
            pass
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_outside_a_run_nothing_is_recorded(self):
        # The emit path recomputes Form 8995 outside any run; its consult
        # returns the election and records nowhere, not even in the run
        # that just ended.
        with positions.recording() as finished:
            pass
        self.assertEqual(positions.election(
            _reaching(**{QBI_SEHI: "irs-faq"}), QBI_SEHI), "irs-faq")
        self.assertEqual(finished, [])

    def test_a_missing_election_refuses_naming_the_controversy(self):
        with positions.recording() as record:
            with self.assertRaises(NotImplementedError) as cm:
                positions.election(_reaching(), QBI_SEHI)
        self.assertEqual(str(cm.exception), positions.refusal_message(QBI_SEHI))
        self.assertEqual(record, [])

    def test_a_consult_on_a_return_that_never_reaches_it_is_a_programming_error(
            self):
        with positions.recording() as record:
            with self.assertRaisesRegex(RuntimeError, "never reaches"):
                positions.election(_wages_only(), QBI_SEHI)
        self.assertEqual(record, [])

    def test_the_refusal_message(self):
        pos = positions.POSITIONS[QBI_SEHI]
        msg = positions.refusal_message(QBI_SEHI)
        for needle in (QBI_SEHI, pos.question, "positions:"):
            self.assertIn(needle, msg)
        for choice in pos.choices:
            self.assertIn(choice.slug, msg)
            self.assertIn(choice.consequence, msg)

    def test_a_choice_mutated_after_construction_refuses(self):
        scenario = _reaching(**{QBI_SEHI: "irs-faq"})
        scenario.positions[QBI_SEHI] = "maybe"
        with self.assertRaisesRegex(ValueError, "maybe"):
            positions.election(scenario, QBI_SEHI)

    def test_an_unregistered_slug_is_a_programming_error(self):
        with self.assertRaises(LookupError):
            positions.election(_reaching(), "no-such-position")


class ResultsRecordTests(Wired, unittest.TestCase):
    """Ruling 5: each run's consults ride its results dict; a run that
    reaches no position carries no record at all (silence = never
    reached)."""

    def setUp(self):
        super().setUp()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()))

    def _pipeline(self, scenario, consult):
        def core(effective):
            if consult:
                positions.election(effective, QBI_SEHI)
            return {}
        with unittest.mock.patch.object(
                ReturnOrchestrator, "_compute_1040_pipeline_core",
                side_effect=core):
            return self.orch._compute_1040_pipeline(scenario)

    def test_a_consult_rides_the_results(self):
        results = self._pipeline(_reaching(**{QBI_SEHI: "no-reduction"}),
                                 consult=True)
        self.assertEqual(results[positions.RESULTS_KEY], [
            {"slug": QBI_SEHI, "choice": "no-reduction", "reached": True}])

    def test_no_consult_leaves_no_record(self):
        results = self._pipeline(_reaching(**{QBI_SEHI: "no-reduction"}),
                                 consult=False)
        self.assertNotIn(positions.RESULTS_KEY, results)

    def test_a_non_reaching_return_carries_no_record(self):
        with unittest.mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook path reached")):
            results = self.orch.compute_federal(_wages_only())
        self.assertIn("agi", results)
        self.assertNotIn(positions.RESULTS_KEY, results)


class QbiSehiReachabilityPinTests(unittest.TestCase):
    """Spec §13: every registered position is reachable, i.e. some code
    path consults it. KNOWN GAP until positions phase 2 wires the Form 8995
    consult: nothing consults qbi-sehi-shareholder-reduction yet. Phase 2
    flips this pin to "consulted"."""

    def test_nothing_consults_it_yet(self):
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=Path(tempfile.mkdtemp()))
        # Before the f8995 lane merges the return computes; after, the
        # interim Form 8995 refusal (naming this slug) fires. Either is fine
        # here. No election: an unwired position refuses one at load.
        with unittest.mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook path reached")), \
                unittest.mock.patch.object(
                    positions, "election", wraps=positions.election) as spy:
            try:
                orch.compute_federal(_reaching())
            except NotImplementedError as exc:
                self.assertIn(QBI_SEHI, str(exc))
        self.assertEqual(
            spy.call_count, 0,
            "KNOWN GAP (positions phase 2): the Form 8995 path now consults "
            "the registry; flip this pin to assert the position is consulted")



class WiredGateTests(unittest.TestCase):
    """KNOWN GAP (positions phase 2): no position is wired yet, so an
    election is refused at load: the computation would refuse the return
    whatever is elected. Phase 2 sets wired=True and these flip."""

    def test_nothing_is_wired_yet(self):
        self.assertFalse(positions.POSITIONS[QBI_SEHI].wired,
                         "KNOWN GAP flipped: positions phase 2 wired it")

    def test_an_election_for_an_unwired_position_refuses(self):
        with self.assertRaisesRegex(ValueError, "not yet consulted"):
            _reaching(**{QBI_SEHI: "irs-faq"})

    def test_an_unknown_choice_is_named_before_the_wiring(self):
        with self.assertRaisesRegex(ValueError, "not one of its choices"):
            _reaching(**{QBI_SEHI: "maybe"})

    def test_an_unwired_unreachable_election_names_the_wiring_first(self):
        with self.assertRaisesRegex(ValueError, "not yet consulted"):
            _wages_only(**{QBI_SEHI: "irs-faq"})


def _election_slugs(root: Path) -> set[str]:
    """Every position slug an ``election(...)`` call under ``root`` names
    (a bare ``election`` or any ``x.election``). The slug argument must be
    a string literal or a module-level string constant of that file; any
    other form fails loudly rather than being skipped. So does any way of
    reaching ``election`` other than calling it by that name (an import
    alias, a bound alias, a rebinding), and a constant rebound anywhere in
    its file (a local that shadows it would resolve to the wrong value)."""
    referenced, unresolved, aliased, shadowed = set(), [], [], []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        constants = {
            target.id: node.value.value
            for node in tree.body if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for target in node.targets if isinstance(target, ast.Name)}
        called = {id(node.func) for node in ast.walk(tree)
                  if isinstance(node, ast.Call)}
        bindings: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(
                    node.ctx, ast.Load):
                names = [node.id]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.asname or a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names = [node.name]
            else:
                names = []
            for name in names:
                bindings[name] = bindings.get(name, 0) + 1
            if isinstance(node, ast.ImportFrom) and any(
                    a.name == "election" and a.asname not in (None, "election")
                    for a in node.names):
                aliased.append(f"{path}:{node.lineno}")
            elif (isinstance(node, ast.Name) and node.id == "election"
                  and (not isinstance(node.ctx, ast.Load)
                       or id(node) not in called)):
                aliased.append(f"{path}:{node.lineno}")
            elif (isinstance(node, ast.Attribute) and node.attr == "election"
                  and id(node) not in called):
                aliased.append(f"{path}:{node.lineno}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not ((isinstance(func, ast.Name) and func.id == "election")
                    or (isinstance(func, ast.Attribute)
                        and func.attr == "election")):
                continue
            slug = (node.args[1] if len(node.args) >= 2 else next(
                (k.value for k in node.keywords if k.arg == "slug"), None))
            if isinstance(slug, ast.Constant) and isinstance(slug.value, str):
                referenced.add(slug.value)
            elif isinstance(slug, ast.Name) and slug.id in constants:
                if bindings.get(slug.id, 0) > 1:
                    shadowed.append(f"{path}:{node.lineno}")
                else:
                    referenced.add(constants[slug.id])
            else:
                unresolved.append(f"{path}:{node.lineno}")
    if aliased:
        raise AssertionError(
            "election reached through an alias or rebinding, which the scan "
            f"cannot follow: {aliased}")
    if shadowed:
        raise AssertionError(
            "election() calls whose slug constant is rebound (shadowed) in "
            f"its file, so its value there is not the module's: {shadowed}")
    if unresolved:
        raise AssertionError(
            "election() calls whose slug is neither a string literal nor a "
            f"module-level string constant: {unresolved}")
    return referenced


class ElectionScanTests(unittest.TestCase):
    """The scan the position-taking path pins rely on."""

    def _scan(self, source):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text(source)
            return _election_slugs(Path(d))

    def test_literals_constants_and_attribute_calls_resolve(self):
        self.assertEqual(self._scan(
            'SLUG = "b-slug"\n'
            'def f(s):\n'
            '    positions.election(s, "a-slug")\n'
            '    election(s, SLUG)\n'
            '    positions.election(s, slug="c-slug")\n'),
            {"a-slug", "b-slug", "c-slug"})

    def test_an_unresolvable_slug_fails_loudly(self):
        with self.assertRaisesRegex(AssertionError, "neither a string"):
            self._scan("def f(s, x):\n    positions.election(s, x())\n")

    def test_an_aliased_import_fails_loudly(self):
        # N1: a call through an import alias would not match by name.
        with self.assertRaisesRegex(AssertionError, "alias"):
            self._scan(
                "from tenforty.positions import election as consult\n"
                'def f(s):\n    consult(s, "a-slug")\n')

    def test_a_bound_alias_fails_loudly(self):
        # N1: nor would a call through a name bound to election itself.
        for source in ('consult = election\n'
                       'def f(s):\n    consult(s, "a-slug")\n',
                       'consult = positions.election\n'
                       'def f(s):\n    consult(s, "a-slug")\n'):
            with self.subTest(source=source):
                with self.assertRaisesRegex(AssertionError, "alias"):
                    self._scan(source)

    def test_a_shadowed_constant_fails_loudly(self):
        # N2: a local rebinding of a module constant must not resolve to the
        # module's value.
        for source in ('SLUG = "b-slug"\n'
                       'def f(s, SLUG):\n    election(s, SLUG)\n',
                       'SLUG = "b-slug"\n'
                       'def f(s):\n    SLUG = s.pick()\n'
                       '    election(s, SLUG)\n',
                       'SLUG = "b-slug"\n'
                       'def f(s):\n    for SLUG in s.picks:\n'
                       '        election(s, SLUG)\n'):
            with self.subTest(source=source):
                with self.assertRaisesRegex(AssertionError, "shadow"):
                    self._scan(source)


class PositionTakingPathTests(unittest.TestCase):
    """Spec §13: every position-taking code path references a registered
    entry, and an entry is wired exactly when a path consults it."""

    def setUp(self):
        self.referenced = _election_slugs(
            Path(positions.__file__).resolve().parent)

    def test_no_path_consults_a_position_yet(self):
        # KNOWN GAP (positions phase 2): nothing calls election() yet.
        # Phase 2 wires the Form 8995 consult; flip this deliberately.
        self.assertEqual(self.referenced, set(),
                         "KNOWN GAP flipped: a path now calls election()")

    def test_an_entry_is_wired_exactly_when_a_path_consults_it(self):
        wired = {slug for slug, pos in positions.POSITIONS.items()
                 if pos.wired}
        self.assertEqual(wired, self.referenced)
        self.assertLessEqual(self.referenced, set(positions.POSITIONS))

if __name__ == "__main__":
    unittest.main()
