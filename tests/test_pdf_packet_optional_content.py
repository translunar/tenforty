"""Packet assembly keeps each part's optional-content (layer) state.

Some templates ship layers hidden by default: the 2021 FTB 3532 carries
"CalFile turn on" (a "Keep this form for your records - DO NOT MAIL TO FTB"
banner) and "Guides and Grids" OFF; the 2021 Schedule D (540) carries
"Guides and Grids" OFF. A merged PDF without the catalog's /OCProperties
shows every layer, so the assembled packet must list each source's OFF
groups OFF. poppler honors the default configuration, so pdftotext and the
rendered page show what a viewer or printer would.

Native throughout (the workbook path is patched to fail): no LibreOffice.
All identities are synthetic.
"""
import dataclasses
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import pypdf
import yaml
from pypdf.generic import NameObject

from tenforty import pdf_packet
from tenforty.models import FilingStatus
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_emit_helpers import (
    emit_ca_with_sch_d_adjustment, make_ca_scenario)
from tests._pdf_pixels import render_gray
from tests.fixtures.spine_battery import build_wages_only
from tests.helpers import CA_SCOPE_OUT_FIELDS

REPO_ROOT = Path(__file__).parent.parent
YEAR = 2021
BANNER = "DO NOT MAIL TO FTB"
# The banner's band on the 2021 FTB 3532 page at 150 DPI (pixel rows), where
# the visual pass saw the hidden layer's ink.
BANNER_ROWS = range(24, 60)


def _hoh_ca_scenario(year: int):
    """The battery's HoH wages-only row (it carries the shared valid
    head_of_household block), CA-resident."""
    base = build_wages_only(year, FilingStatus.HEAD_OF_HOUSEHOLD)
    return dataclasses.replace(base, config=dataclasses.replace(
        base.config, full_year_health_care_coverage=True,
        **{k: True for k in CA_SCOPE_OUT_FIELDS}))


def _page_text(pdf: Path, page_index: int) -> str:
    n = str(page_index + 1)
    return subprocess.run(
        ["pdftotext", "-f", n, "-l", n, str(pdf), "-"],
        check=True, capture_output=True, text=True).stdout


def _banner_band_ink(pdf: Path, page_index: int) -> int:
    """Non-white pixels in the banner band."""
    w, _h, buf = render_gray(pdf, page_index, 150)
    return sum(1 for row in BANNER_ROWS
               for px in buf[row * w:(row + 1) * w] if px < 250)


def _off_names(pdf: Path) -> list[str]:
    root = pypdf.PdfReader(str(pdf)).trailer["/Root"]
    if "/OCProperties" not in root:
        return []
    default = root["/OCProperties"].get("/D", {})
    return sorted(ref.get_object()["/Name"] for ref in default.get("/OFF", []))


def _page_layer_states(pdf: Path) -> list[dict[str, tuple[str, bool]]]:
    """Per page: each /Properties resource name -> (group name, ON?) under
    the document's default optional-content configuration."""
    reader = pypdf.PdfReader(str(pdf))
    root = reader.trailer["/Root"]
    ocp = root["/OCProperties"] if "/OCProperties" in root else None
    off = set()
    if ocp is not None:
        default = ocp.get("/D", {})
        on_ids = {ref.idnum for ref in default.get("/ON", [])}
        if default.get("/BaseState") == "/OFF":
            off = {ref.idnum for ref in ocp["/OCGs"]} - on_ids
        else:
            off = {ref.idnum for ref in default.get("/OFF", [])}
    states = []
    for page in reader.pages:
        props = page.get("/Resources", {}).get("/Properties", {})
        page_states = {}
        for key, ref in props.items():
            group = ref.get_object()
            if group.get("/Type") != "/OCG":
                continue
            # No /OCProperties at all: a viewer shows every group.
            visible = ocp is None or ref.idnum not in off
            page_states[key] = (group["/Name"], visible)
        states.append(page_states)
    return states


class _PacketCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        patcher = unittest.mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=AssertionError("workbook path reached"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _emit_hoh_ca(self) -> dict[str, Path]:
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=self.tmp / "work")
        ca_yaml = self.tmp / "ca.yaml"
        ca_yaml.write_text(yaml.safe_dump(
            {"ca540": {"interest_and_penalties": 0.0}}))
        _results, pdfs = orch.run_full_california_return(
            scenario=_hoh_ca_scenario(YEAR), ca_yaml_path=ca_yaml,
            output_dir=self.tmp / "ca")
        return pdfs

    def _assemble(self, pdfs: dict[str, Path]) -> tuple[list[Path], Path]:
        packet = next(p for p in pdf_packet.PACKETS if p.name == "california")
        parts = pdf_packet.ordered_members(pdfs, packet)
        out = self.tmp / "packet.pdf"
        pdf_packet.assemble_packet(parts, out)
        return parts, out

    def _first_page_of(self, parts: list[Path], target: Path) -> int:
        index = 0
        for part in parts:
            if part == target:
                return index
            index += len(pypdf.PdfReader(str(part)).pages)
        self.fail(f"{target} not in the packet")

    def assert_layer_states_survive(self, parts, packet):
        expected = [s for part in parts for s in _page_layer_states(part)]
        self.assertEqual(_page_layer_states(packet), expected)
        self.assertEqual(
            _off_names(packet),
            sorted(n for part in parts for n in _off_names(part)))


class Ftb3532BannerTests(_PacketCase):

    def test_hidden_banner_is_reachable_in_the_standalone_form(self):
        # Reachability: the banner is real ink on a hidden layer. Strip the
        # standalone emit's /OCProperties and it shows.
        pdfs = self._emit_hoh_ca()
        standalone = pdfs["ftb3532"]
        self.assertIn("CalFile turn on", _off_names(standalone))
        writer = pypdf.PdfWriter(clone_from=str(standalone))
        del writer.root_object[NameObject("/OCProperties")]
        stripped = self.tmp / "stripped.pdf"
        with open(stripped, "wb") as f:
            writer.write(f)
        self.assertIn(BANNER, _page_text(stripped, 0))
        self.assertGreater(_banner_band_ink(stripped, 0), 1000)

    def test_standalone_emit_hides_the_banner(self):
        standalone = self._emit_hoh_ca()["ftb3532"]
        self.assertNotIn(BANNER, _page_text(standalone, 0))
        self.assertEqual(_banner_band_ink(standalone, 0), 0)

    def test_assembled_packet_hides_the_banner(self):
        pdfs = self._emit_hoh_ca()
        parts, packet = self._assemble(pdfs)
        page = self._first_page_of(parts, pdfs["ftb3532"])
        self.assertIn("Head of Household", _page_text(packet, page))
        self.assertNotIn(BANNER, _page_text(packet, page))
        self.assertEqual(_banner_band_ink(packet, page), 0)

    def test_every_page_keeps_its_layer_states(self):
        parts, packet = self._assemble(self._emit_hoh_ca())
        self.assert_layer_states_survive(parts, packet)


class ScheduleD540LayerTests(_PacketCase):

    def test_2021_sch_d_540_guides_layer_stays_off_in_the_packet(self):
        _results, pdfs = emit_ca_with_sch_d_adjustment(make_ca_scenario(YEAR))
        self.assertIn("sch_d_540", pdfs)
        self.assertIn("Guides and Grids", _off_names(pdfs["sch_d_540"]))
        parts, packet = self._assemble(pdfs)
        self.assertIn(pdfs["sch_d_540"], parts)
        self.assert_layer_states_survive(parts, packet)
