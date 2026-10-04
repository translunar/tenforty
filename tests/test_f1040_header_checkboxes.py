"""Form 1040 header block, checkboxes and the digital-assets question.

Before this fix the emitted 1040 printed only money lines: no name, SSN or
address, no filing-status box, no line-7 "Schedule D not required" box, no
digital-assets answer. Native pypdf fills only (no soffice); synthetic data.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f1040_spine
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.models import FilingStatus, Form1099B, TaxReturnConfig
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.fixtures.spine_battery import build_ptc_capped_repayment
from tests.helpers import REPO_ROOT, make_simple_scenario

YEARS = (2021, 2022, 2023, 2024, 2025)

# Probe-verified identity-block leaves per year (marker-probe of each year's
# committed f1040.pdf, rendered and read against the printed labels). A shift
# to a different-but-existing field reddens here.
GOLDEN_HEADER_LEAVES = {
    2021: dict(first_name="f1_02", last_name="f1_03", ssn="f1_04",
               spouse_first_name="f1_05", spouse_last_name="f1_06",
               spouse_ssn="f1_07", address="f1_08", apt_no="f1_09",
               city="f1_10", state="f1_11", zip_code="f1_12"),
    2022: dict(first_name="f1_02", last_name="f1_03", ssn="f1_04",
               spouse_first_name="f1_05", spouse_last_name="f1_06",
               spouse_ssn="f1_07", address="f1_08", apt_no="f1_09",
               city="f1_10", state="f1_11", zip_code="f1_12"),
    2023: dict(first_name="f1_04", last_name="f1_05", ssn="f1_06",
               spouse_first_name="f1_07", spouse_last_name="f1_08",
               spouse_ssn="f1_09", address="f1_10", apt_no="f1_11",
               city="f1_12", state="f1_13", zip_code="f1_14"),
    2024: dict(first_name="f1_04", last_name="f1_05", ssn="f1_06",
               spouse_first_name="f1_07", spouse_last_name="f1_08",
               spouse_ssn="f1_09", address="f1_10", apt_no="f1_11",
               city="f1_12", state="f1_13", zip_code="f1_14"),
    2025: dict(first_name="f1_14", last_name="f1_15", ssn="f1_16",
               spouse_first_name="f1_17", spouse_last_name="f1_18",
               spouse_ssn="f1_19", address="f1_20", apt_no="f1_21",
               city="f1_22", state="f1_23", zip_code="f1_24"),
}

_STATUS_KEYS = {
    FilingStatus.SINGLE: "single",
    FilingStatus.MARRIED_JOINTLY: "mfj",
    FilingStatus.MARRIED_SEPARATELY: "mfs",
    FilingStatus.HEAD_OF_HOUSEHOLD: "hoh",
    FilingStatus.QUALIFYING_WIDOW: "qss",
}


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"


def _fill(year: int, values: dict) -> Path:
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / f"f1040_{year}.pdf"
    PdfFiller().fill(
        _template(year), out, Pdf1040.get_mapping(year), values=values,
        checkbox_states=Pdf1040.get_checkbox_states(year),
    )
    # Keep the directory alive for the caller's read-back.
    _KEEP.append(tmp)
    return out


_KEEP: list = []
_WORK = Path(tempfile.gettempdir()) / "tenforty-1040-header-tests"


def _widget_states(pdf: Path) -> dict[str, str]:
    """Qualified field name -> /AS for every button widget on page 1."""
    out = {}
    for annot in PdfReader(str(pdf)).pages[0].get("/Annots", []):
        annot = annot.get_object()
        parts, node = [], annot
        while node is not None:
            if "/T" in node:
                parts.append(str(node["/T"]))
            node = node.get("/Parent")
            node = node.get_object() if node is not None else None
        name = ".".join(reversed(parts))
        if "/AS" in annot:
            out[name] = str(annot["/AS"])
    return out


def _on_boxes(pdf: Path) -> set[str]:
    return {n for n, s in _widget_states(pdf).items() if s != "/Off"}


def _read_text(pdf: Path) -> dict[str, str]:
    return {n: str(f.get("/V") or "")
            for n, f in (PdfReader(str(pdf)).get_fields() or {}).items()}


class HeaderKeyTests(unittest.TestCase):
    """The spine emits the header block from config."""

    def _config(self, **kw) -> TaxReturnConfig:
        return TaxReturnConfig(
            year=2025, filing_status=FilingStatus.MARRIED_JOINTLY,
            birthdate="1980-01-01", state="TX",
            first_name="Pat", last_name="Example", ssn="000-00-0001",
            spouse_first_name="Sam", spouse_last_name="Example",
            spouse_ssn="000-00-0002", address="1 Test Street",
            address_city="Testville", address_state="TX",
            address_zip="00001", **kw)

    def test_header_values_carry_every_identity_field(self):
        got = f1040_spine.header_values(self._config())
        self.assertEqual(got, {
            "taxpayer_name": "Pat Example", "taxpayer_ssn": "000-00-0001",
            "first_name": "Pat", "last_name": "Example",
            "ssn": "000000001",
            "spouse_first_name": "Sam", "spouse_last_name": "Example",
            "spouse_ssn": "000000002",
            "address": "1 Test Street", "city": "Testville",
            "state": "TX", "zip_code": "00001",
        })

    def test_unset_config_gives_blank_strings_not_missing_keys(self):
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01", state="TX")
        got = f1040_spine.header_values(cfg)
        self.assertEqual(got["taxpayer_name"], "")
        self.assertEqual(got["ssn"], "")
        self.assertEqual(got["zip_code"], "")

    def test_native_compute_result_carries_the_header(self):
        scn = make_simple_scenario()
        scn.config.first_name, scn.config.last_name = "Alex", "Rivera"
        scn.config.ssn = "000-12-3456"
        scn.config.address_city = "Testville"
        results = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=_WORK,
        ).compute_federal(scn)
        self.assertEqual(results["taxpayer_name"], "Alex Rivera")
        self.assertEqual(results["taxpayer_ssn"], "000-12-3456")
        self.assertEqual(results["first_name"], "Alex")
        self.assertEqual(results["ssn"], "000123456")
        self.assertEqual(results["city"], "Testville")


class HeaderMappingTests(unittest.TestCase):
    def test_mapped_header_fields_match_probe_verified_leaves(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            on_template = set(PdfReader(str(_template(year))).get_fields())
            for key, leaf in GOLDEN_HEADER_LEAVES[year].items():
                with self.subTest(year=year, key=key):
                    path = mapping[key]
                    self.assertEqual(
                        path.split(".")[-1].replace("[0]", ""), leaf)
                    self.assertIn(path, on_template)

    def test_every_header_field_prints_its_own_value_every_year(self):
        for year in YEARS:
            values = {k: f"V{k}" for k in GOLDEN_HEADER_LEAVES[year]}
            read = _read_text(_fill(year, values))
            mapping = Pdf1040.get_mapping(year)
            for key in values:
                with self.subTest(year=year, key=key):
                    self.assertEqual(read[mapping[key]], f"V{key}")
            # Distinct fields: no two keys share a PDF field.
            paths = [mapping[k] for k in values]
            self.assertEqual(len(paths), len(set(paths)))


class SsnCellWidthTests(unittest.TestCase):
    """The 1040 SSN cells are MaxLen 9; every other form's are 11."""

    def test_1040_ssn_cells_hold_nine_and_header_feeds_nine_digits(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            reader = PdfReader(str(_template(year)))
            widths = {}
            for annot in reader.pages[0]["/Annots"]:
                annot = annot.get_object()
                node, parts = annot, []
                while node is not None:
                    if "/T" in node:
                        parts.append(str(node["/T"]))
                    node = node.get("/Parent")
                    node = node.get_object() if node is not None else None
                name = ".".join(reversed(parts))
                node = annot
                while node is not None and "/MaxLen" not in node:
                    node = node.get("/Parent")
                    node = node.get_object() if node is not None else None
                widths[name] = int(node["/MaxLen"]) if node is not None else None
            for key in ("ssn", "spouse_ssn"):
                with self.subTest(year=year, key=key):
                    self.assertEqual(widths[mapping[key]], 9)
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01", state="TX", ssn="000-12-3456")
        self.assertEqual(len(f1040_spine.header_values(cfg)["ssn"]), 9)


class FilingStatusCheckboxTests(unittest.TestCase):
    def test_each_status_checks_exactly_its_own_box_every_year(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            for status, suffix in _STATUS_KEYS.items():
                with self.subTest(year=year, status=status.value):
                    values = {
                        f"filing_status_{s}": s == suffix
                        for s in _STATUS_KEYS.values()
                    }
                    on = _on_boxes(_fill(year, values))
                    self.assertEqual(
                        on, {mapping[f"filing_status_{suffix}"]})

    def test_status_boxes_are_five_distinct_fields_every_year(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            paths = {mapping[f"filing_status_{s}"]
                     for s in _STATUS_KEYS.values()}
            self.assertEqual(len(paths), 5, year)

    def test_orchestrator_values_pick_the_configured_status(self):
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=_WORK)
        for status, suffix in _STATUS_KEYS.items():
            with self.subTest(status=status.value):
                scn = make_simple_scenario()
                scn.config.filing_status = status
                got = orch._form_1040_checkbox_values(scn, {})
                self.assertEqual(
                    {k for k, v in got.items()
                     if k.startswith("filing_status_") and v},
                    {f"filing_status_{suffix}"})


class Line7AndDigitalAssetsCheckboxTests(unittest.TestCase):
    def test_line_7_box_lands_on_its_own_field_every_year(self):
        for year in YEARS:
            with self.subTest(year=year):
                on = _on_boxes(_fill(year, {"sch_d_not_required": True}))
                self.assertEqual(
                    on, {Pdf1040.get_mapping(year)["sch_d_not_required"]})
                off = _on_boxes(_fill(year, {"sch_d_not_required": False}))
                self.assertEqual(off, set())

    def test_digital_assets_yes_and_no_every_year(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            for answer in (True, False):
                with self.subTest(year=year, answer=answer):
                    on = _on_boxes(_fill(year, {
                        "digital_assets_yes": answer,
                        "digital_assets_no": not answer}))
                    key = "digital_assets_yes" if answer else "digital_assets_no"
                    self.assertEqual(on, {mapping[key]})

    def test_line_7_box_follows_the_sch_d_gate(self):
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=_WORK)
        scn = make_simple_scenario()
        # Line 7 nonzero, no 1099-B -> no Schedule D -> box checked.
        self.assertTrue(orch._form_1040_checkbox_values(
            scn, {"capital_gain_loss": 120.0})["sch_d_not_required"])
        # Line 7 zero/absent -> not checked (nothing to say "not required"
        # about).
        self.assertFalse(orch._form_1040_checkbox_values(
            scn, {"capital_gain_loss": None})["sch_d_not_required"])
        self.assertFalse(orch._form_1040_checkbox_values(
            scn, {})["sch_d_not_required"])
        # Line 7 nonzero WITH a 1099-B -> Schedule D is attached -> unchecked.
        with_b = dataclasses.replace(scn, form1099_b=[Form1099B(
            broker="Broker", description="XYZ", date_acquired="2020-01-01",
            date_sold="2025-02-01", proceeds=500.0, cost_basis=380.0,
            short_term=False, basis_reported_to_irs=True)])
        self.assertTrue(orch._should_emit_sch_d(with_b))
        self.assertFalse(orch._form_1040_checkbox_values(
            with_b, {"capital_gain_loss": 120.0})["sch_d_not_required"])

    def test_digital_assets_values_follow_the_config(self):
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=_WORK)
        scn = make_simple_scenario()
        for answer in (True, False):
            scn.config.digital_assets = answer
            got = orch._form_1040_checkbox_values(scn, {})
            self.assertIs(got["digital_assets_yes"], answer)
            self.assertIs(got["digital_assets_no"], not answer)
        scn.config.digital_assets = None
        got = orch._form_1040_checkbox_values(scn, {})
        self.assertNotIn("digital_assets_yes", got)
        self.assertNotIn("digital_assets_no", got)


class EmitEndToEndTests(unittest.TestCase):
    """Real entry point: compute_federal -> emit_pdfs, read the printed 1040."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _scenario(self, year: int):
        scn = make_simple_scenario()
        cfg = dataclasses.replace(
            scn.config, year=year, first_name="Alex", last_name="Rivera",
            ssn="000-12-3456", address="1 Test Street",
            address_city="Testville", address_state="TX",
            address_zip="00001", digital_assets=False)
        return dataclasses.replace(scn, config=cfg)

    def test_printed_1040_carries_header_and_boxes_every_year(self):
        for year in YEARS:
            with self.subTest(year=year):
                scn = self._scenario(year)
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                pdf = emitted["1040"]
                mapping = Pdf1040.get_mapping(year)
                read = _read_text(pdf)
                self.assertEqual(read[mapping["first_name"]], "Alex")
                self.assertEqual(read[mapping["last_name"]], "Rivera")
                # Digits only: the 1040's SSN cell is a 9-character comb field, so
                # the hyphenated form would print truncated ("000-12-34").
                self.assertEqual(read[mapping["ssn"]], "000123456")
                self.assertEqual(read[mapping["address"]], "1 Test Street")
                self.assertEqual(read[mapping["city"]], "Testville")
                self.assertEqual(read[mapping["state"]], "TX")
                self.assertEqual(read[mapping["zip_code"]], "00001")
                self.assertEqual(_on_boxes(pdf), {
                    mapping["filing_status_single"],
                    mapping["digital_assets_no"],
                })

    def test_form_8962_prints_the_taxpayer_header(self):
        for year in (2022, 2024):
            with self.subTest(year=year):
                scn = build_ptc_capped_repayment(year)
                scn = dataclasses.replace(scn, config=dataclasses.replace(
                    scn.config, first_name="Alex", last_name="Rivera",
                    ssn="000-12-3456", digital_assets=False))
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                read = _read_text(emitted["8962"])
                mapping = PdfF8962.get_mapping(year)["scalars"]
                self.assertEqual(read[mapping["taxpayer_name"]], "Alex Rivera")
                self.assertEqual(read[mapping["taxpayer_ssn"]], "000-12-3456")


class DigitalAssetsRefusalTests(unittest.TestCase):
    """An unanswered question refuses at EMIT time, never at compute time."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _unanswered(self, year: int):
        scn = make_simple_scenario()
        cfg = dataclasses.replace(scn.config, year=year, digital_assets=None)
        return dataclasses.replace(scn, config=cfg)

    def test_config_default_is_unanswered(self):
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01", state="TX")
        self.assertIsNone(cfg.digital_assets)

    def test_emit_refuses_unanswered_for_2022_onward(self):
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                scn = self._unanswered(year)
                results = self.orch.compute_federal(scn)
                with self.assertRaises(ValueError) as ctx:
                    self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                msg = str(ctx.exception)
                self.assertIn("digital_assets", msg)
                self.assertIn("digital asset", msg)
                self.assertIn(str(year), msg)

    def test_compute_path_does_not_require_it(self):
        for year in YEARS:
            with self.subTest(year=year):
                results = self.orch.compute_federal(self._unanswered(year))
                self.assertIn("agi", results)

    def test_2021_unanswered_emits_with_both_boxes_blank(self):
        scn = self._unanswered(2021)
        results = self.orch.compute_federal(scn)
        emitted = self.orch.emit_pdfs(scn, results, self.tmp / "2021")
        mapping = Pdf1040.get_mapping(2021)
        on = _on_boxes(emitted["1040"])
        self.assertNotIn(mapping["digital_assets_yes"], on)
        self.assertNotIn(mapping["digital_assets_no"], on)

    def test_2021_answered_checks_the_virtual_currency_box(self):
        for answer, key in ((True, "digital_assets_yes"),
                            (False, "digital_assets_no")):
            with self.subTest(answer=answer):
                scn = self._unanswered(2021)
                scn.config.digital_assets = answer
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(
                    scn, results, self.tmp / f"2021-{answer}")
                self.assertIn(
                    Pdf1040.get_mapping(2021)[key], _on_boxes(emitted["1040"]))

    def test_yaml_loader_reads_the_field(self):
        base = REPO_ROOT / "tests" / "fixtures" / "simple_w2.yaml"
        text = base.read_text()
        for literal, expected in (("true", True), ("false", False)):
            with self.subTest(literal=literal):
                path = self.tmp / f"scn_{literal}.yaml"
                path.write_text(text.replace(
                    "config:\n", f"config:\n  digital_assets: {literal}\n", 1))
                self.assertIs(load_scenario(path).config.digital_assets, expected)
        # Absent -> None, and load does not refuse it.
        self.assertIsNone(load_scenario(base).config.digital_assets)


if __name__ == "__main__":
    unittest.main()
