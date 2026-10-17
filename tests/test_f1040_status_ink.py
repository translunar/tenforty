"""Form 1040 filing-status marks print, and spouse identity follows status.

Field state is not pixels: the filing-status box can be "checked" in the
field tree while its appearance stream draws nothing. These tests RENDER the
filled 1040 page (poppler, via ``tests/_pdf_pixels.py``) and count ink inside
the selected widget, every year and every status, modelled on
``tests/test_ca_button_ink.py::FilingStatusMarkPrintsTests``.

``SpouseIdentityDisciplineTests`` pins the spouse block to the filing status:
spouse fields on a Single or Head-of-Household scenario refuse at load; a
joint return with a blank spouse name or SSN refuses at emit (never printed
half-blank); the 1040 and 540 header keys carry the spouse only for a joint
return (and, as before, for married filing separately). The 540 spouse date
of birth prints on a joint return only. Synthetic data only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f1040_spine
from tenforty.forms import f540 as form_f540
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.models import FilingStatus, TaxReturnConfig
from tenforty import orchestrator as orchestrator_mod
from tenforty import scenario as scenario_mod
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._ca_emit_helpers import CA_YEARS, make_ca_scenario
from tests._pdf_pixels import checked_widgets, dark_pixels_in_rect, widget_rect
from tests.helpers import REPO_ROOT, hoh_facts, make_simple_scenario

YEARS = (2021, 2022, 2023, 2024, 2025)

# A drawn check glyph inside a ~8pt box at 150 dpi puts well over this many
# dark pixels in the (inset) rect; an empty box puts ~0 there.
MIN_INK = 15

_STATUS_KEYS = {
    FilingStatus.SINGLE: "filing_status_single",
    FilingStatus.MARRIED_FILING_JOINTLY: "filing_status_mfj",
    FilingStatus.MARRIED_FILING_SEPARATELY: "filing_status_mfs",
    FilingStatus.HEAD_OF_HOUSEHOLD: "filing_status_hoh",
    FilingStatus.QUALIFYING_WIDOW: "filing_status_qss",
}

_SPOUSE_1040_KEYS = ("spouse_first_name", "spouse_last_name", "spouse_ssn")
_SPOUSE_540_KEYS = (
    "f540_spouse_first_name", "f540_spouse_last_name", "f540_spouse_ssn")
_SPOUSE_CONFIG_FIELDS = (
    "spouse_first_name", "spouse_middle_initial", "spouse_last_name",
    "spouse_ssn")


def _fill_1040_status(year: int, fs: FilingStatus, out: Path) -> Path:
    """Fill the real 1040 template straight from the mapping with only the
    filing-status keys, so every status is testable without a compute."""
    values = {key: status is fs for status, key in _STATUS_KEYS.items()}
    PdfFiller().fill(
        template_path=REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf",
        output_path=out,
        field_mapping=Pdf1040.get_mapping(year), values=values,
        checkbox_states=Pdf1040.get_checkbox_states(year),
    )
    return out


class F1040FilingStatusInkTests(unittest.TestCase):
    """The 1040 filing-status mark has ink in its box — every year, every
    status (MFJ and HoH are the newly exercised states)."""

    def test_mfj_and_hoh_marks_have_ink_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            states = Pdf1040.get_checkbox_states(year)
            for fs, key in _STATUS_KEYS.items():
                with self.subTest(year=year, fs=fs.value):
                    pdf = _fill_1040_status(
                        year, fs, tmp / f"f1040_{year}_{fs.value}.pdf")
                    page, rect = widget_rect(pdf, mapping[key], states[key])
                    ink = dark_pixels_in_rect(pdf, page, rect)
                    self.assertGreaterEqual(
                        ink, MIN_INK,
                        f"{year} {fs.value}: filing-status widget "
                        f"{mapping[key]!r} renders blank ({ink} dark px)")

    def test_exactly_one_status_widget_checked_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            status_fields = {mapping[k] for k in _STATUS_KEYS.values()}
            for fs, key in _STATUS_KEYS.items():
                with self.subTest(year=year, fs=fs.value):
                    pdf = _fill_1040_status(
                        year, fs, tmp / f"one_{year}_{fs.value}.pdf")
                    checked = [n for pi, n, r, s in checked_widgets(pdf)
                               if n in status_fields]
                    self.assertEqual(checked, [mapping[key]])


def _config(fs: FilingStatus, **kw) -> TaxReturnConfig:
    base = dict(
        year=2025, filing_status=fs, birthdate="1980-01-01", state="CA",
        first_name="Filer", last_name="Example", ssn="000-00-0001",
        spouse_first_name="Spouse", spouse_last_name="Example",
        spouse_ssn="000-00-0002")
    base.update(kw)
    return TaxReturnConfig(**base)


class SpouseIdentityDisciplineTests(unittest.TestCase):
    """Spouse fields follow the filing status on load, compute and emit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    # -- load time -----------------------------------------------------------

    def _yaml(self, status: str, extra: str) -> Path:
        base = REPO_ROOT / "tests" / "fixtures" / "simple_w2.yaml"
        text = base.read_text()
        self.assertIn("  filing_status: single\n", text)
        text = text.replace(
            "  filing_status: single\n",
            f"  filing_status: {status}\n{extra}", 1)
        path = self.tmp / f"scn_{status}_{abs(hash(extra))}.yaml"
        path.write_text(text)
        return path

    # Head of household requires its qualifying-person block (FTB 3532);
    # synthetic values, for the 2025 fixture year.
    _HOH_BLOCK = (
        "  head_of_household:\n"
        "    marital_status: unmarried\n"
        "    qualifying_person:\n"
        "      first_name: Example\n"
        "      last_name: Child\n"
        "      ssn: '000-00-0005'\n"
        "      birthdate: '2015-03-07'\n"
        "      relationship: child_or_stepchild\n"
        "      gross_income: 0\n"
        "      days_lived_with_you: 365\n")

    def test_hoh_with_spouse_name_is_refused_at_load(self):
        # Control: the same Head-of-Household scenario without spouse fields
        # loads, so the refusal below is the spouse field's doing.
        cfg = load_scenario(self._yaml("head_of_household",
                                       self._HOH_BLOCK)).config
        self.assertIs(cfg.filing_status, FilingStatus.HEAD_OF_HOUSEHOLD)
        with self.assertRaises(ValueError) as ctx:
            load_scenario(self._yaml(
                "head_of_household",
                self._HOH_BLOCK + "  spouse_first_name: Spouse\n"))
        msg = str(ctx.exception)
        self.assertIn("spouse_first_name", msg)
        self.assertIn("head_of_household", msg)

    def test_every_spouse_field_is_refused_on_single_and_hoh(self):
        for fs in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD):
            for field in _SPOUSE_CONFIG_FIELDS:
                with self.subTest(fs=fs.value, field=field):
                    blanks = dict.fromkeys(
                        ("spouse_first_name", "spouse_last_name",
                         "spouse_ssn"), "")
                    cfg = _config(fs, **{**blanks, field: "Z"})
                    with self.assertRaises(ValueError) as ctx:
                        scenario_mod.refuse_spouse_fields_without_spouse(cfg)
                    self.assertIn(field, str(ctx.exception))
                    self.assertIn(fs.value, str(ctx.exception))

    def test_blank_spouse_fields_pass_on_single_and_hoh(self):
        for fs in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD):
            with self.subTest(fs=fs.value):
                scenario_mod.refuse_spouse_fields_without_spouse(_config(
                    fs, spouse_first_name="", spouse_last_name="",
                    spouse_ssn=""))

    def test_married_statuses_may_carry_spouse_fields_at_load(self):
        for fs in (FilingStatus.MARRIED_FILING_JOINTLY,
                   FilingStatus.MARRIED_FILING_SEPARATELY):
            with self.subTest(fs=fs.value):
                scenario_mod.refuse_spouse_fields_without_spouse(
                    _config(fs, spouse_middle_initial="Z"))

    # -- emit time -----------------------------------------------------------

    def test_mfj_blank_spouse_identity_pure_decision_names_the_field(self):
        for field in _SPOUSE_1040_KEYS:
            for blank in ("", "   "):
                with self.subTest(field=field, blank=blank):
                    cfg = _config(FilingStatus.MARRIED_FILING_JOINTLY,
                                  **{field: blank})
                    with self.assertRaises(ValueError) as ctx:
                        orchestrator_mod.refuse_blank_mfj_spouse_identity(cfg, "Form 1040")
                    self.assertIn(field, str(ctx.exception))
                    self.assertIn("Form 1040", str(ctx.exception))
        # Control: a complete joint identity passes; non-joint statuses are
        # not this refusal's business.
        orchestrator_mod.refuse_blank_mfj_spouse_identity(
            _config(FilingStatus.MARRIED_FILING_JOINTLY), "Form 1040")
        for fs in (FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD,
                   FilingStatus.MARRIED_FILING_SEPARATELY):
            orchestrator_mod.refuse_blank_mfj_spouse_identity(_config(
                fs, spouse_first_name="", spouse_last_name="",
                spouse_ssn=""), "Form 1040")

    def test_mfj_blank_spouse_ssn_is_refused_at_federal_emit(self):
        for field in _SPOUSE_1040_KEYS:
            with self.subTest(field=field):
                scn = make_simple_scenario()
                spouse = {"spouse_first_name": "Spouse",
                          "spouse_last_name": "Example",
                          "spouse_ssn": "000-00-0002"}
                scn = dataclasses.replace(scn, config=dataclasses.replace(
                    scn.config, filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
                    first_name="Filer", last_name="Example",
                    ssn="000-00-0001", **{**spouse, field: ""}))
                out = self.tmp / f"fed_{field}"
                with self.assertRaises(ValueError) as ctx:
                    self.orch.emit_pdfs(scn, {}, out)
                self.assertIn(field, str(ctx.exception))
                self.assertEqual(list(out.glob("*.pdf")), [])

    def test_mfj_blank_spouse_ssn_is_refused_at_ca_emit(self):
        for field in _SPOUSE_1040_KEYS:
            with self.subTest(field=field):
                scn = make_ca_scenario(2025, FilingStatus.MARRIED_FILING_JOINTLY)
                spouse = {"spouse_first_name": "Spouse",
                          "spouse_last_name": "Example",
                          "spouse_ssn": "000-00-0002"}
                scn = dataclasses.replace(scn, config=dataclasses.replace(
                    scn.config, **{**spouse, field: ""}))
                out = self.tmp / f"ca_{field}"
                with self.assertRaises(ValueError) as ctx:
                    self.orch._emit_ca_pdfs_internal(scn, {}, out)
                self.assertIn(field, str(ctx.exception))
                self.assertIn("540", str(ctx.exception))

    # -- header keys ---------------------------------------------------------

    def test_hoh_emits_no_spouse_keys_on_either_form(self):
        # Built directly (bypassing the loader's refusal) with spouse values
        # present, so a name-presence gate would leak them.
        for fs in (FilingStatus.HEAD_OF_HOUSEHOLD, FilingStatus.SINGLE):
            block = (hoh_facts(2025)
                     if fs is FilingStatus.HEAD_OF_HOUSEHOLD else None)
            cfg = _config(fs, spouse_birthdate="1979-03-07",
                          head_of_household=block)
            with self.subTest(fs=fs.value, form="1040"):
                got = f1040_spine.header_values(cfg)
                self.assertEqual(
                    [k for k in got if k.startswith("spouse_")], [])
                self.assertEqual(got["first_name"], "Filer")  # header present
            for year in CA_YEARS:
                with self.subTest(fs=fs.value, form="540", year=year):
                    keys = form_f540.presentation_keys(
                        dataclasses.replace(cfg, year=year), [], year)
                    self.assertEqual(
                        [k for k in keys if k.startswith("f540_spouse_")], [])
                    self.assertEqual(keys["f540_taxpayer_first_name"], "Filer")

    def test_mfj_emits_all_three_spouse_keys_on_both_forms(self):
        # A joint return states the spouse's birthdate (540 line 9 refuses
        # without it); not aged, and distinct from the taxpayer's 1980-01-01
        # so a key that copied the taxpayer's date would fail.
        cfg = _config(FilingStatus.MARRIED_FILING_JOINTLY,
                      spouse_birthdate="1979-03-07")
        got = f1040_spine.header_values(cfg)
        self.assertEqual(
            {k: got[k] for k in _SPOUSE_1040_KEYS},
            {"spouse_first_name": "Spouse", "spouse_last_name": "Example",
             "spouse_ssn": "000000002"})
        for year in CA_YEARS:
            with self.subTest(year=year):
                keys = form_f540.presentation_keys(
                    dataclasses.replace(cfg, year=year), [], year)
                self.assertEqual(
                    {k: keys[k] for k in _SPOUSE_540_KEYS},
                    {"f540_spouse_first_name": "Spouse",
                     "f540_spouse_last_name": "Example",
                     "f540_spouse_ssn": "000-00-0002"})
                self.assertEqual(keys["f540_spouse_dob"], "03/07/1979")
                self.assertEqual(keys["f540_taxpayer_dob"], "01/01/1980")

    def test_mfs_keeps_todays_spouse_behaviour(self):
        mfs = FilingStatus.MARRIED_FILING_SEPARATELY
        got = f1040_spine.header_values(_config(mfs))
        self.assertEqual(got["spouse_first_name"], "Spouse")
        self.assertEqual(got["spouse_ssn"], "000000002")
        # Unset spouse on MFS: blank strings, keys still present (as before).
        blank = f1040_spine.header_values(_config(
            mfs, spouse_first_name="", spouse_last_name="", spouse_ssn=""))
        self.assertEqual({k: blank[k] for k in _SPOUSE_1040_KEYS},
                         dict.fromkeys(_SPOUSE_1040_KEYS, ""))
        # 540 on MFS: spouse printed when named, omitted when not (as before).
        named = form_f540.presentation_keys(
            _config(mfs, spouse_birthdate="1979-03-07"), [], 2025)
        self.assertEqual(named["f540_spouse_first_name"], "Spouse")
        self.assertNotIn("f540_spouse_dob", named)   # joint return only
        unnamed = form_f540.presentation_keys(_config(
            mfs, spouse_first_name="", spouse_last_name="", spouse_ssn=""),
            [], 2025)
        self.assertNotIn("f540_spouse_first_name", unnamed)


class CaSpousePlacementTests(unittest.TestCase):
    """The 540 spouse cells are placed, not merely present: each key lands
    on its own field (sentinel fill + read-back), and that field sits in the
    spouse row directly below the matching taxpayer cell, every CA year.
    Deleting every year's spouse mappings reddened no other test, hence
    this class."""

    _PAIRS = (("f540_taxpayer_first_name", "f540_spouse_first_name"),
              ("f540_taxpayer_last_name", "f540_spouse_last_name"),
              ("f540_taxpayer_ssn", "f540_spouse_ssn"))

    def _template(self, year: int) -> Path:
        return REPO_ROOT / "pdfs" / "california" / str(year) / "f540.pdf"

    def test_each_spouse_key_prints_its_own_sentinel_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        keys = [k for pair in self._PAIRS for k in pair]
        for year in CA_YEARS:
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                values = {k: f"S{i}" for i, k in enumerate(keys)}
                out = tmp / f"f540_{year}.pdf"
                PdfFiller().fill(
                    template_path=self._template(year), output_path=out,
                    field_mapping=mapping, values=values)
                read = {n: str(f.get("/V") or "")
                        for n, f in PdfReader(str(out)).get_fields().items()}
                for k, v in values.items():
                    self.assertEqual(read[mapping[k]], v, k)
                paths = [mapping[k] for k in keys]
                self.assertEqual(len(paths), len(set(paths)))

    def test_spouse_row_sits_directly_below_the_taxpayer_row(self):
        for year in CA_YEARS:
            mapping = PdfF540.get_mapping(year)
            template = self._template(year)
            spouse_rows = set()
            for tp_key, sp_key in self._PAIRS:
                with self.subTest(year=year, key=sp_key):
                    tp_page, tp = widget_rect(template, mapping[tp_key])
                    sp_page, sp = widget_rect(template, mapping[sp_key])
                    self.assertEqual((tp_page, sp_page), (0, 0))
                    self.assertLess(abs(tp[0] - sp[0]), 5)   # same column
                    self.assertLess(sp[3], tp[1] + 1)        # below taxpayer
                    self.assertLess(tp[1] - sp[3], 20)       # the next row
                    spouse_rows.add(round(sp[1]))
            with self.subTest(year=year, check="one spouse row"):
                self.assertEqual(len(spouse_rows), 1, spouse_rows)


class CaSpouseDobPlacementTests(unittest.TestCase):
    """The 540 Side 1 "Spouse's/RDP's DOB" box, every CA year: the mapped
    field IS the template's spouse date-of-birth widget (its own /TU, not an
    assumed number), a filled value reads back and prints ink, and the box
    sits on the taxpayer DOB's row to its right."""

    def _template(self, year: int) -> Path:
        return REPO_ROOT / "pdfs" / "california" / str(year) / "f540.pdf"

    def test_mapped_field_is_the_templates_spouse_dob_widget(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                fields = PdfReader(str(self._template(year))).get_fields()
                sp = str(fields[mapping["f540_spouse_dob"]].get("/TU", ""))
                tp = str(fields[mapping["f540_taxpayer_dob"]].get("/TU", ""))
                self.assertRegex(sp, r"^Spouse's or R")
                self.assertIn("Date of Birth", sp)
                self.assertIn("Your Date of Birth", tp)

    def test_spouse_dob_reads_back_and_prints_ink_every_year(self):
        tmp = Path(tempfile.mkdtemp())
        for year in CA_YEARS:
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                values = {"f540_taxpayer_dob": "01/01/1980",
                          "f540_spouse_dob": "03/07/1979"}
                out = tmp / f"f540_{year}.pdf"
                PdfFiller().fill(
                    template_path=self._template(year), output_path=out,
                    field_mapping=mapping, values=values)
                read = {n: str(f.get("/V") or "")
                        for n, f in PdfReader(str(out)).get_fields().items()}
                self.assertEqual(read[mapping["f540_spouse_dob"]], "03/07/1979")
                page, rect = widget_rect(out, mapping["f540_spouse_dob"])
                self.assertGreater(
                    dark_pixels_in_rect(out, page, rect, inset=1.0), 8)

    def test_spouse_dob_sits_right_of_the_taxpayer_dob_on_its_row(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                tp_page, tp = widget_rect(self._template(year),
                                          mapping["f540_taxpayer_dob"])
                sp_page, sp = widget_rect(self._template(year),
                                          mapping["f540_spouse_dob"])
                self.assertEqual((tp_page, sp_page), (0, 0))
                self.assertLess(abs(tp[1] - sp[1]), 2)   # same row
                self.assertGreater(sp[0], tp[2])          # to its right


if __name__ == "__main__":
    unittest.main()
