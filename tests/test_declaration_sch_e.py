"""The Schedule E declaration validates against each year's own inventory
(emit-verification protocol step 4; adjudications
/private/tmp/pilot-packet-sch_e/ADJUDICATION.md and
/private/tmp/pilot-packet-sch_e-supp/ADJUDICATION.md).

The module ships inert: graduation (registration in
tenforty.declarations.forms with the pending removal) is a later, separate
step, so this test reads the module directly, not the registry.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.declarations import inventory, propose, registry, sch_e
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.declarations.validate import validate
from tenforty.mappings.pdf_sch_e import PdfSchE
from tenforty.verification import anchors as anchor_eval
from tenforty.verification import crosscheck as crosscheck_mod
from tenforty.verification import emit_manifest
from tenforty.verification import undeclared as undeclared_mod
from tenforty.verification.batteries import BATTERIES
from tenforty.verification.checks import check_placement
from tenforty.verification.coverage import coverage_cells
from tenforty.verification.fill import fill_spec_for
from tenforty.verification.options import option_widgets
from tenforty.verification.pending import PENDING_DECLARATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
FORM = ("federal", "sch_e")


class SchEDeclarationValidatesTests(unittest.TestCase):
    def test_each_year_declared(self):
        self.assertEqual(sorted(sch_e.DECLARATIONS), list(YEARS))
        for year in YEARS:
            decl = sch_e.DECLARATIONS[year]
            with self.subTest(year=year):
                self.assertIsInstance(decl, FormDeclaration)
                self.assertEqual(decl.form, FORM)
                self.assertEqual(decl.key, year)

    def test_each_year_validates_clean(self):
        for year in YEARS:
            with self.subTest(year=year):
                findings = validate(sch_e.DECLARATIONS[year],
                                    siblings=sch_e.DECLARATIONS.values())
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_the_documented_witness_discrepancies_are_the_raw_findings(self):
        # The wired in-force pin: every documented entry is a real raw
        # stylesheet cross-check finding, and every raw finding documented.
        for year in YEARS:
            decl = sch_e.DECLARATIONS[year]
            by_line = {ln.line: ln.line_id for ln in expand(decl, {})}
            raw = crosscheck_mod.crosscheck(
                decl, propose.stylesheet_lines("sch_e", year))
            in_force = crosscheck_mod.discrepancies_in_force(sch_e, year)
            with self.subTest(year=year):
                self.assertEqual(set(in_force),
                                 {by_line[f.line] for f in raw})
                self.assertEqual(crosscheck_mod.crosscheck(
                    decl, propose.stylesheet_lines("sch_e", year),
                    discrepancies=in_force), [])

    def test_explicit_phrases_print_exactly_once(self):
        # The anchor evaluator matches whole printed tokens; a phrase that
        # ends mid-token prints zero times. Each explicit phrase prints on
        # its page once (Part I on page 1, Parts II-V on page 2).
        for year in YEARS:
            template = str(REPO_ROOT / "pdfs" / "federal" / str(year)
                           / "f1040se.pdf")
            for ln in sch_e.DECLARATIONS[year].lines:
                if not isinstance(ln.anchor, NearLabel):
                    continue
                page = 0 if ln.section == "Part I" else 1
                words = anchor_eval._page_words(template, page)
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(len(anchor_eval._phrase_boxes(
                        words, ln.anchor.phrase)), 1, ln.anchor.phrase)

    def test_inventory_backed_descriptions_are_the_inventory_text(self):
        # Description-refresh ruling: every line the inventory prints is
        # described by the inventory's text verbatim (line 2 included: its
        # row text, the full caption kept in a comment).
        for year in YEARS:
            text = {(l.section, l.label): l.text
                    for l in inventory.load("sch_e", year).lines}
            for ln in sch_e.DECLARATIONS[year].lines:
                if ln.inventory_exemption is not None:
                    continue
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(ln.description, text[ln.line_id])

    def test_line_41_is_the_one_value_only_line(self):
        for year in YEARS:
            lines = sch_e.DECLARATIONS[year].lines
            with self.subTest(year=year):
                self.assertEqual([ln.line for ln in lines
                                  if ln.single_state == "value"], ["41"])

    def test_ships_inert(self):
        self.assertIn(FORM, PENDING_DECLARATIONS)
        self.assertNotIn(FORM, {f for f, _ in registry.declared_forms()})


def _sch_e_records():
    """(row id, RecordedForm) for every Schedule E the registered batteries
    emit natively (states observed, no expected values)."""
    manifest = emit_manifest.load_manifest()
    records = []
    for battery in BATTERIES:
        for name, year, build in battery.scenarios():
            rid = emit_manifest.row_id(battery.name, name, year)
            row = manifest.get(rid)
            if not row or row["routing"] != "native" or row["refusal"]:
                continue
            if "federal/sch_e" not in (row["forms"] or ()):
                continue
            out = Path(tempfile.mkdtemp()) / "out"
            records += [(rid, rec) for rec in emit_manifest.emit(
                battery, build(), out).record if rec.form == FORM]
    return records


class SchECoverageTests(unittest.TestCase):
    """Every declared state is exercised, every year, over the registered
    batteries (the Schedule E battery carries columns B/C, lines 5-19, 22,
    25, the line A/B answers and Part II rows a-d)."""

    @classmethod
    def setUpClass(cls):
        cls.records = _sch_e_records()

    def test_every_year_has_records(self):
        self.assertEqual(sorted({rec.key for _, rec in self.records}),
                         list(YEARS))

    def test_no_cell_is_uncovered(self):
        report = coverage_cells(self.records,
                                [sch_e.DECLARATIONS[y] for y in YEARS])
        self.assertEqual(list(report.uncovered), [], "\n".join(
            map(str, report.uncovered)))

    def test_every_filled_key_is_bound_or_not_printed(self):
        # The undeclared-key check (spec §2.3) on the module itself: every
        # key a battery Schedule E is filled from matches a declared line's
        # key or a not_printed entry of that year's declaration.
        undeclared = sorted({
            (rid, key) for rid, rec in self.records
            for key in rec.values
            if not any(p.fullmatch(key) for p in undeclared_mod._key_patterns(
                [sch_e.DECLARATIONS[rec.key]]))})
        self.assertEqual(undeclared, [], "\n".join(map(str, undeclared)))


class SchEStaticCellPlacementTests(unittest.TestCase):
    """Lines the orchestrator writes conditionally (line 27, line 28
    column (e)) are placed on the STATIC mapping: the field path lives in
    the mapping whatever a scenario writes, so placement never depends on
    the values (Q2 ruling: a spec-absent cell would be indistinguishable
    from an unmapped one)."""

    def test_line_27_and_basis_boxes_place_on_the_static_mapping(self):
        for year in YEARS:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
            decl = sch_e.DECLARATIONS[year]
            wanted = {ln.line for ln in decl.lines
                      if ln.key == "sch_e_line_27_no"
                      or ln.key.endswith("_basis_computation_box")}
            findings = [f for f in check_placement(
                template, decl, fill_spec_for(PdfSchE, year))
                if f.line in wanted]
            with self.subTest(year=year):
                self.assertEqual(
                    sorted(wanted), ["27"] if year == 2021 else
                    ["27", "28A(e)", "28B(e)", "28C(e)", "28D(e)"])
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))


class SchELine29bAnchorTests(unittest.TestCase):
    """29b's row prints only a bare "b" and the repeated "Totals", so it
    anchors on line 30's print-once caption one row below it
    (ROW_ABOVE_LABEL, team-lead ruling 2026-10-19)."""

    _P2 = "topmostSubform[0].Page2[0]."
    # The 29a-row box in 29b's column (2021: a shaded widget) and the next
    # column on the 29b row.
    _NEIGHBOURS = {2021: ("R1", "R4"),
                   **{y: ("f2_35", "f2_41") for y in YEARS if y != 2021}}

    def _line(self, year):
        return next(ln for ln in sch_e.DECLARATIONS[year].lines
                    if ln.line == "29b")

    def test_29b_anchors_above_line_30s_caption(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(self._line(year).anchor, NearLabel(
                    "Add columns (h) and (k)", LabelRelation.ROW_ABOVE_LABEL))

    def test_29b_is_placed(self):
        for year in YEARS:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
            findings = [f for f in check_placement(
                template, sch_e.DECLARATIONS[year],
                fill_spec_for(PdfSchE, year)) if f.line == "29b"]
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))

    def test_29b_anchor_refuses_the_29a_row_and_the_next_column(self):
        for year in YEARS:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
            for leaf in self._NEIGHBOURS[year]:
                with self.subTest(year=year, box=leaf):
                    self.assertIsNotNone(anchor_eval.evaluate(
                        self._line(year).anchor, f"{self._P2}{leaf}[0]",
                        template))


class SchEAnswerLinePlacementTests(unittest.TestCase):
    """Lines A/B: each Yes box anchors ON_ROW its own question's print-once
    phrase (row-specific; it cannot tell its own row's No box apart), and
    each No box anchors SAME_ROW_RIGHT_OF the Yes line's resolved box
    (column order). The pair together refuses every constructed mis-map
    (team-lead ruling 2026-10-20)."""

    _PHRASE = {"A": "Did you make any payments",
               "B": "did you or will you file required"}

    def test_yes_lines_anchor_on_their_question(self):
        for year in YEARS[1:]:
            lines = {ln.line: ln for ln in sch_e.DECLARATIONS[year].lines}
            for line, phrase in self._PHRASE.items():
                with self.subTest(year=year, line=line):
                    self.assertEqual(lines[line].anchor, NearLabel(
                        phrase, LabelRelation.ON_ROW))

    def test_answer_lines_are_placed(self):
        for year in YEARS[1:]:
            template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
            findings = [f for f in check_placement(
                template, sch_e.DECLARATIONS[year],
                fill_spec_for(PdfSchE, year))
                if f.line in ("A", "A(No)", "B", "B(No)")]
            with self.subTest(year=year):
                self.assertEqual(findings, [], "\n".join(
                    f.message for f in findings))


class SchEAnswerLineResolutionTests(unittest.TestCase):
    """Lines A/B are option lines (selects "/1" Yes, "/2" No): the gate and
    the check-suite resolve each through the CANONICAL spec's translation
    derivations to exactly one widget (option-line ruling 2026-10-17; step-4
    ruling 2026-10-20). Widgets: line A c1_1, line B c1_2; Yes [0] /1, No
    [1] /2 (2022-2025; 2021 unserved)."""

    _P1 = "topmostSubform[0].Page1[0]."
    _GROUP = {"A": "c1_1", "B": "c1_2"}

    def test_each_answer_line_resolves_to_its_own_widget(self):
        for year in YEARS[1:]:
            spec = fill_spec_for(PdfSchE, year)
            for ln in sch_e.DECLARATIONS[year].lines:
                if ln.selects is None:
                    continue
                index = 0 if ln.selects == "/1" else 1
                widget = f"{self._P1}{self._GROUP[ln.group]}[{index}]"
                with self.subTest(year=year, line=ln.line):
                    self.assertEqual(option_widgets(spec, ln.key, ln.selects),
                                     [(widget, ln.selects)])

    def test_an_out_of_domain_answer_fails_loud(self):
        # A bool (or any value but "/1"/"/2") is a producer bug: every A/B
        # widget's derivation refuses it rather than printing nothing.
        derivations = fill_spec_for(PdfSchE, 2025).derivations
        for path, derive in derivations.items():
            key = ("sch_e_payments_requiring_1099s" if ".c1_1[" in path
                   else "sch_e_filed_required_1099s")
            for bad in (True, "Yes", "/Off"):
                with self.subTest(widget=path, value=bad):
                    with self.assertRaises(ValueError):
                        derive({key: bad})

    def test_2021_answer_lines_stay_unserved(self):
        self.assertEqual(
            [ln.line for ln in sch_e.DECLARATIONS[2021].lines
             if ln.selects is not None], [])
        self.assertEqual(dict(fill_spec_for(PdfSchE, 2021).derivations), {})


def _emit_row(battery_name, scenario_name, year):
    for battery in BATTERIES:
        if battery.name != battery_name:
            continue
        for name, y, build in battery.scenarios():
            if (name, y) == (scenario_name, year):
                out = Path(tempfile.mkdtemp()) / "out"
                return [rec for rec in emit_manifest.emit(
                    battery, build(), out).record if rec.form == FORM]
    raise LookupError((battery_name, scenario_name, year))


class SchEEmitSpecIsCanonicalTests(unittest.TestCase):
    """The orchestrator fills Schedule E from the CANONICAL spec (flattened:
    the chokepoint takes the A/B derivations only on a flat fill) and writes
    only values: no per-scenario field paths (FillSpec.extend) for the A/B
    answers, line 27 or line 28 column (e) (Q1/Q2 rulings). Red the moment
    an extend() for Schedule E returns."""

    def test_emitted_spec_equals_fill_spec_for(self):
        rows = (("rental-losses-b-and-c", 2024),   # A Yes, B No
                ("rental-loss-a", 2023),           # A No, B blank
                ("three-rentals-every-expense", 2022),  # A Yes, B Yes
                ("k1-rows-rotation-3", 2025))      # line 27 No + 28A(e) box
        for name, year in rows:
            records = _emit_row("emit_battery_sch_e", name, year)
            with self.subTest(row=name, year=year):
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0].spec,
                                 fill_spec_for(PdfSchE, year).flattened())


if __name__ == "__main__":
    unittest.main()
