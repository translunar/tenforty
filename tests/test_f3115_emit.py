"""Form 3115 emission: the filled form, the Schedule E asset statement, the
filing manifest, packet placement, and the amendment-packet refusal.

PDF assertions pin LITERAL widget paths read off the Rev. December 2022
template (pdfs/federal/revision_keyed/f3115.pdf), never paths looked up
through the mapping under test.
"""
import contextlib
import dataclasses
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from pypdf import PdfReader

from tenforty import pdf_packet, years
from tenforty.__main__ import main as cli_main
from tenforty.forms import f3115 as form_f3115
from tenforty.mappings.pdf_f3115 import PdfF3115, get_mapping
from tenforty.models import AmendmentCase
from tests import _f3115_fixtures as fx
from tests.helpers import REPO_ROOT

_REVISION = "rev-2022-12"
_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "revision_keyed" / "f3115.pdf"

_P1 = "topmostSubform[0].Page1[0]."
_P2 = "topmostSubform[0].Page2[0]."
_P3 = "topmostSubform[0].Page3[0]."
_P4 = "topmostSubform[0].Page4[0]."
_P8 = "topmostSubform[0].Page8[0]."

# EVERY widget the base fixture fills, and nothing else. Line references are
# the printed lines the widget sits on (rect vs. label position, enumerated
# from the template).
_EXPECTED_BASE = {
    _P1 + "f1_1[0]": "Marlow Q Testcase",        # Name of filer
    _P1 + "f1_2[0]": "410 Fixture Lane",         # Number, street
    _P1 + "f1_3[0]": "Sampleton, CA 90000",      # City, state, ZIP
    _P1 + "f1_4[0]": "000-00-0000",              # Identification number
    _P1 + "f1_5[0]": "531110",                   # Principal business activity code
    _P1 + "f1_6[0]": "01/01/2025",               # Tax year of change begins
    _P1 + "f1_7[0]": "12/31/2025",               # Tax year of change ends
    _P1 + "f1_8[0]": "Marlow Q Testcase",        # Name of contact person
    _P1 + "f1_10[0]": "555-0100",                # Contact person's telephone
    _P1 + "c1_1[1]": "/No",                      # Correspondence by fax/email: No
    _P1 + "TypeOfApplicant[0].c1_4[0]": "/1",    # Individual
    _P1 + "c1_5[0]": "/1",                       # Depreciation or Amortization
    _P1 + "f1_18[0]": "7",                       # Line 1a (1) DCN
    _P1 + "c1_7[1]": "/No",                      # Line 2: No
    _P1 + "c1_8[0]": "/Yes",                     # Line 3: Yes
    _P1 + "c1_9[1]": "/No",                      # Line 4: No
    _P1 + "c1_10[1]": "/No",                     # Line 5: No
    _P1 + "f1_31[0]": "Marlow Q Testcase",       # Name and title (print or type)
    _P2 + "c2_1[1]": "/No",                      # Line 6a: No
    _P2 + "c2_4[0]": "/Yes",                     # Line 7a: Yes
    _P2 + "c2_5[0]": "/1",                       # Line 7b: Not under exam
    _P2 + "c2_6[1]": "/No",                      # Line 8a: No
    _P2 + "c2_12[1]": "/No",                     # Line 11a: No
    _P2 + "c2_13[1]": "/No",                     # Line 12: No
    _P2 + "c2_14[1]": "/No",                     # Line 13: No
    _P3 + "c3_1[0]": "/Yes",                     # Line 17: Yes
    _P3 + "c3_2[1]": "/No",                      # Line 18: No
    _P4 + "c4_0[1]": "/No",                      # Line 25: No
    _P4 + "f4_1[0]": "+31,250",                  # Line 26 adjustment
    _P4 + "c4_1[1]": "/No",                      # Line 27: No
    _P4 + "c4_2[1]": "/No",                      # Line 28: No
    _P4 + "c4_4[1]": "/No",                      # Line 29: No
    _P8 + "c8_1[1]": "/No",                      # Schedule E line 1: No
    _P8 + "c8_2[1]": "/No",                      # Schedule E line 2: No
    _P8 + "c8_3[1]": "/No",                      # Schedule E line 3: No
    _P8 + "c8_4[1]": "/No",                      # Schedule E line 4b: No
    _P8 + "c8_5[1]": "/No",                      # Schedule E line 4c: No
}


def _filled(path: Path) -> dict[str, str]:
    """Every field on ``path`` that carries a value (text or an on-state)."""
    out = {}
    for name, field in (PdfReader(path).get_fields() or {}).items():
        value = str(field.get("/V") or "")
        if value not in ("", "/Off"):
            out[name] = value
    return out


def _emit(tc: unittest.TestCase, block=None, **config_overrides):
    tmp = tempfile.TemporaryDirectory()
    tc.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    scenario = fx.load(root, fx.scenario_dict(block=block, **config_overrides))
    out = root / "out"
    _results, emitted = fx.orchestrator(root).run_full_return(scenario, out)
    return scenario, emitted, out


class FilledFormTests(unittest.TestCase):
    def test_base_fixture_fills_exactly_the_expected_widgets(self):
        _scenario, emitted, out = _emit(self)
        self.assertEqual(emitted["f3115"], out / "f3115_2025.pdf")
        self.assertEqual(_filled(emitted["f3115"]), _EXPECTED_BASE)

    def test_emitted_form_keeps_all_eight_pages(self):
        _scenario, emitted, _out = _emit(self)
        self.assertEqual(len(PdfReader(emitted["f3115"]).pages), 8)

    def test_one_year_election_checks_line_28_and_the_de_minimis_box(self):
        _s, emitted, _o = _emit(
            self, block=fx.base_block(elect_one_year_spread=True))
        fields = _filled(emitted["f3115"])
        expected = dict(_EXPECTED_BASE)
        del expected[_P4 + "c4_2[1]"]
        expected[_P4 + "c4_2[0]"] = "/Yes"   # Line 28: Yes
        expected[_P4 + "c4_3[0]"] = "/90"    # $50,000 de minimis election
        self.assertEqual(fields, expected)
        # The neighbouring elective provision stays unchecked.
        self.assertNotIn(_P4 + "c4_3[1]", fields)

    def test_no_election_leaves_both_elective_boxes_off(self):
        _s, emitted, _o = _emit(self)
        fields = _filled(emitted["f3115"])
        self.assertEqual(fields[_P4 + "c4_2[1]"], "/No")
        for box in ("c4_2[0]", "c4_3[0]", "c4_3[1]"):
            with self.subTest(box=box):
                self.assertNotIn(_P4 + box, fields)

    def test_line_26_carries_the_sign_and_the_stated_cents(self):
        cases = {
            31250.0: "+31,250", -31250.0: "-31,250", 0.0: "0",
            49999.99: "+49,999.99", -1234.5: "-1,234.50", 725000.0: "+725,000",
        }
        for adjustment, printed in cases.items():
            with self.subTest(adjustment=adjustment):
                _s, emitted, _o = _emit(self, block=fx.base_block(
                    section_481a_adjustment=adjustment))
                self.assertEqual(
                    _filled(emitted["f3115"])[_P4 + "f4_1[0]"], printed)

    def test_yes_no_answers_that_print_either_way(self):
        """Lines 17, 18 and Schedule E 4b accept both answers; each checks
        its own box of the pair and not the other."""
        pairs = {
            "proposed_method_used_for_books": (_P3 + "c3_1[0]", _P3 + "c3_1[1]"),
            "requests_conference_if_adverse": (_P3 + "c3_2[0]", _P3 + "c3_2[1]"),
            "lived_in_residential_rental_before_renting": (
                _P8 + "c8_4[0]", _P8 + "c8_4[1]"),
        }
        for key, (yes_box, no_box) in pairs.items():
            for answer in (True, False):
                with self.subTest(key=key, answer=answer):
                    _s, emitted, _o = _emit(
                        self, block=fx.base_block(**{key: answer}))
                    fields = _filled(emitted["f3115"])
                    on, off = (yes_box, no_box) if answer else (no_box, yes_box)
                    self.assertEqual(
                        fields[on], "/Yes" if answer else "/No")
                    self.assertNotIn(off, fields)

    def test_line_4b_not_applicable_leaves_both_boxes_blank(self):
        _s, emitted, _o = _emit(self, block=fx.base_block(
            lived_in_residential_rental_before_renting=None))
        fields = _filled(emitted["f3115"])
        self.assertNotIn(_P8 + "c8_4[0]", fields)
        self.assertNotIn(_P8 + "c8_4[1]", fields)
        # Its neighbour, line 4c, is still answered.
        self.assertEqual(fields[_P8 + "c8_5[1]"], "/No")

    def test_absent_business_activity_code_leaves_the_cell_blank(self):
        _s, emitted, _o = _emit(self, block=fx.base_block(
            principal_business_activity_code=None))
        fields = _filled(emitted["f3115"])
        self.assertNotIn(_P1 + "f1_5[0]", fields)
        self.assertEqual(fields[_P1 + "f1_4[0]"], "000-00-0000")

    def test_return_without_the_block_emits_no_form_3115(self):
        data = fx.scenario_dict()
        del data["form_3115"]
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(Path(tmp), data)
            out = Path(tmp) / "out"
            _r, emitted = fx.orchestrator(tmp).run_full_return(scenario, out)
            self.assertNotIn("f3115", emitted)
            self.assertNotIn("f3115_asset_stmt", emitted)
            self.assertNotIn("f3115_duplicate_copy", emitted)
            self.assertEqual(sorted(p.name for p in out.glob("f3115*")), [])


class MappingTests(unittest.TestCase):
    def test_every_mapped_path_is_a_template_field(self):
        template_fields = set(PdfReader(_TEMPLATE).get_fields())
        for key, path in get_mapping(_REVISION).items():
            with self.subTest(key=key):
                self.assertIn(path, template_fields)

    def test_no_two_keys_share_a_widget(self):
        paths = list(get_mapping(_REVISION).values())
        self.assertEqual(len(paths), len(set(paths)))

    def test_checkbox_on_states_are_the_template_widgets_own(self):
        reader = PdfReader(_TEMPLATE)
        on_states = {}
        for page in reader.pages:
            for annot in page.get("/Annots", []):
                widget = annot.get_object()
                if "/AP" not in widget or "/T" not in widget:
                    continue
                parts, node = [], widget
                while node is not None:
                    if "/T" in node:
                        parts.append(node["/T"])
                    parent = node.get("/Parent")
                    node = parent.get_object() if parent is not None else None
                name = ".".join(reversed(parts))
                states = [s for s in widget["/AP"]["/N"].keys() if s != "/Off"]
                if len(states) == 1:
                    on_states[name] = states[0]
        mapping = get_mapping(_REVISION)
        checkbox_states = PdfF3115.get_checkbox_states(_REVISION)
        self.assertTrue(checkbox_states)
        for key, state in checkbox_states.items():
            with self.subTest(key=key):
                self.assertEqual(on_states[mapping[key]], state)

    def test_every_presentation_key_is_mapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(Path(tmp), fx.scenario_dict())
        values = form_f3115.presentation_values(scenario)
        self.assertEqual(set(values) - set(get_mapping(_REVISION)), set())

    def test_unknown_revision_refuses(self):
        with self.assertRaisesRegex(ValueError, "rev-1999-01"):
            get_mapping("rev-1999-01")

    def test_revision_is_recorded_in_the_years_manifest(self):
        self.assertEqual(
            years.REVISION_KEYED_FORM_REVISIONS["f3115"], _REVISION)
        self.assertTrue(_TEMPLATE.exists())
        self.assertTrue(_TEMPLATE.with_name("f3115.probe.pdf").exists())
        # The revision printed on the template itself.
        self.assertIn(
            "(Rev. December 2022)", PdfReader(_TEMPLATE).pages[0].extract_text())


class AssetStatementTests(unittest.TestCase):
    def _text(self, emitted) -> str:
        reader = PdfReader(emitted["f3115_asset_stmt"])
        return "\n".join(page.extract_text() for page in reader.pages)

    def test_statement_is_emitted_and_identifies_the_applicant(self):
        _s, emitted, out = _emit(self)
        self.assertEqual(
            emitted["f3115_asset_stmt"], out / "f3115_asset_statement_2025.pdf")
        text = self._text(emitted)
        self.assertIn("Form 3115, Schedule E", text)
        self.assertIn("lines 4a and 7", text)
        self.assertIn("Marlow Q Testcase", text)
        self.assertIn("000-00-0000", text)
        self.assertIn("2025", text)

    def test_every_column_of_every_asset_prints(self):
        _s, emitted, _o = _emit(self)
        text = self._text(emitted)
        expected = {
            "Synthetic rental building": [
                "Residential rental property", "03/01/2019",
                "Held for rental (Schedule E)", "240,000", "41,538",
                "39 years", "27.5 years", "Straight line, section 168(b)(3)",
                "None assigned (residential rental property)",
            ],
            "Synthetic appliance set": [
                "Tangible personal property", "07/15/2020", "6,200", "795",
                "200% declining balance, section 168(b)(1)", "5 years",
                "Half-year", "57.0",
            ],
        }
        for asset, fragments in expected.items():
            for fragment in [asset, *fragments]:
                with self.subTest(asset=asset, fragment=fragment):
                    self.assertIn(fragment, text)
        # Stated once per asset: the yes/no and account columns.
        self.assertEqual(text.count("Special depreciation allowance claimed: No"), 2)
        self.assertEqual(text.count("Asset account: Single asset account"), 2)
        self.assertEqual(text.count("Code section: 168"), 2)
        self.assertEqual(text.count("Tax credits or grants: None"), 2)

    def test_special_allowance_and_account_columns_follow_the_row(self):
        block = fx.base_block()
        block["assets"][1]["special_depreciation_allowance_claimed"] = True
        block["assets"][1]["asset_account"] = "general"
        _s, emitted, _o = _emit(self, block=block)
        text = self._text(emitted)
        self.assertEqual(text.count("Special depreciation allowance claimed: Yes"), 1)
        self.assertEqual(text.count("Special depreciation allowance claimed: No"), 1)
        self.assertEqual(text.count("Asset account: General asset account"), 1)
        self.assertEqual(text.count("Asset account: Single asset account"), 1)

    def test_no_row_capacity_limit(self):
        block = fx.base_block()
        block["assets"] = [
            {**fx.ASSET_APPLIANCE, "description": f"Synthetic asset {i:03d}"}
            for i in range(1, 41)]
        _s, emitted, _o = _emit(self, block=block)
        reader = PdfReader(emitted["f3115_asset_stmt"])
        self.assertGreater(len(reader.pages), 1)
        text = self._text(emitted)
        for i in range(1, 41):
            with self.subTest(asset=i):
                self.assertEqual(text.count(f"Synthetic asset {i:03d}"), 1)

    def test_one_block_longer_than_a_page_continues_on_the_next(self):
        words = [f"clause{i:04d}" for i in range(1, 1201)]
        block = fx.base_block()
        block["assets"] = [
            {**fx.ASSET_BUILDING, "use_in_activity": " ".join(words)}]
        _s, emitted, _o = _emit(self, block=block)
        reader = PdfReader(emitted["f3115_asset_stmt"])
        self.assertGreater(len(reader.pages), 1)
        text = self._text(emitted)
        for word in (words[0], words[599], words[-1]):
            with self.subTest(word=word):
                self.assertEqual(text.count(word), 1)
        # The columns after the long one still print, once.
        self.assertEqual(text.count("Asset account: Single asset account"), 1)
        # Nothing is drawn below the bottom margin of any page.
        for number, page in enumerate(reader.pages, start=1):
            lowest = []
            page.extract_text(visitor_text=lambda t, cm, tm, fd, fs: (
                lowest.append(tm[5]) if t.strip() else None))
            with self.subTest(page=number):
                self.assertGreaterEqual(min(lowest), 0.75 * 72)

    def test_statement_is_deterministic(self):
        _s, first, _o = _emit(self)
        _s, second, _o = _emit(self)
        self.assertEqual(first["f3115_asset_stmt"].read_bytes(),
                         second["f3115_asset_stmt"].read_bytes())


class DuplicateCopyTests(unittest.TestCase):
    """The copy that is signed and filed separately: the form and its
    statement in one standalone file, kept out of the return's packet."""

    def test_duplicate_copy_is_the_form_followed_by_the_statement(self):
        _s, emitted, out = _emit(self)
        path = emitted["f3115_duplicate_copy"]
        self.assertEqual(path, out / "f3115_2025_duplicate_copy_to_sign.pdf")
        reader = PdfReader(path)
        statement_pages = len(PdfReader(emitted["f3115_asset_stmt"]).pages)
        self.assertEqual(len(reader.pages), 8 + statement_pages)
        self.assertIn("Application for Change in Accounting Method",
                      reader.pages[0].extract_text())
        self.assertIn("Form 3115, Schedule E", reader.pages[8].extract_text())
        self.assertEqual(_filled(path), _EXPECTED_BASE)

    def test_duplicate_copy_is_standalone_not_a_packet_member(self):
        self.assertEqual(
            pdf_packet.classify_key("f3115_duplicate_copy"), "standalone")
        _s, emitted, _o = _emit(self)
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertNotIn("f3115_2025_duplicate_copy_to_sign.pdf", names)
        self.assertIn("f3115_2025.pdf", names)


class ManifestTests(unittest.TestCase):
    def _manifest(self, **kwargs) -> str:
        _s, _emitted, out = _emit(self, **kwargs)
        return (out / "f3115_filing_manifest_2025.txt").read_text()

    def test_manifest_lists_what_was_emitted(self):
        text = self._manifest()
        self.assertIn("f3115_2025.pdf", text)
        self.assertIn("f3115_asset_statement_2025.pdf", text)
        self.assertIn("Schedule E, lines 4a and 7", text)
        self.assertIn("f3115_2025_duplicate_copy_to_sign.pdf", text)

    def test_manifest_states_the_signed_duplicate_copy_requirement(self):
        text = self._manifest()
        # Transcribed from the Form 3115 instructions (Rev. December 2022),
        # "When and Where To File" and its Address Chart.
        for fragment in (
                "signed", "duplicate copy",
                "Internal Revenue Service", "Ogden, UT 84201", "M/S 6111",
                "1973 N. Rulon White Blvd.", "844-249-8134",
                "no earlier than the first day of the year of change",
                "no later than the date the original is filed",
                "Rev. December 2022"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_manifest_prints_both_delivery_addresses_whole(self):
        """The mail and private-delivery addresses share a city line, so
        each is pinned as its own consecutive block."""
        lines = [line.strip() for line in self._manifest().splitlines()]
        mail = lines.index("By mail:              Internal Revenue Service")
        self.assertEqual(
            lines[mail + 1:mail + 3], ["Ogden, UT 84201", "M/S 6111"])
        private = lines.index(
            "By private delivery:  Internal Revenue Service")
        self.assertEqual(lines[private + 1:private + 4], [
            "1973 N. Rulon White Blvd.", "Ogden, UT 84201", "Attn: M/S 6111"])
        self.assertEqual(lines.count("Ogden, UT 84201"), 2)
        self.assertIn("By fax:               844-249-8134", lines)

    def test_manifest_lists_required_applicant_supplied_attachments(self):
        text = self._manifest()
        self.assertIn("REQUIRED, NOT EMITTED", text)
        for line in ("Line 14", "Line 15a", "Lines 16a-b", "Line 26",
                     "Schedule E, line 5", "Schedule E, line 7c",
                     "Schedule E, line 7g"):
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_line_17_no_adds_its_explanation_to_the_required_list(self):
        self.assertNotIn("Line 17", self._manifest())
        self.assertIn("Line 17", self._manifest(
            block=fx.base_block(proposed_method_used_for_books=False)))

    def test_manifest_says_the_adjustment_is_stated_not_computed(self):
        text = self._manifest()
        self.assertIn("section 481(a) adjustment", text)
        self.assertIn("STATED", text)
        self.assertIn("not carried", text)

    def test_spread_period_line_follows_the_adjustment(self):
        cases = [
            (dict(), "4 tax years"),
            (dict(elect_one_year_spread=True), "1 tax year (the $50,000 de minimis election)"),
            (dict(section_481a_adjustment=-31250.0), "1 tax year (negative adjustment)"),
        ]
        for overrides, fragment in cases:
            with self.subTest(overrides=overrides):
                self.assertIn(
                    fragment, self._manifest(block=fx.base_block(**overrides)))


class PacketTests(unittest.TestCase):
    def test_form_and_statement_are_claimed_by_the_federal_packet(self):
        for key in ("f3115", "f3115_asset_stmt"):
            with self.subTest(key=key):
                self.assertEqual(
                    pdf_packet.classify_key(key), "federal_individual")

    def test_form_3115_follows_form_4562_then_its_statement(self):
        _s, emitted, _o = _emit(self)
        emitted = dict(emitted)
        emitted["f4562"] = Path("/x/f4562.pdf")
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names[-3:], [
            "f4562.pdf", "f3115_2025.pdf", "f3115_asset_statement_2025.pdf"])
        self.assertEqual(names[0], "f1040_2025.pdf")

    def test_assembled_packet_contains_the_form_and_statement_pages(self):
        _s, emitted, out = _emit(self)
        combined = pdf_packet.assemble_all(emitted, out, 2025)
        packet = PdfReader(combined["federal_individual"])
        loose = sum(
            len(PdfReader(p).pages) for key, p in emitted.items()
            if pdf_packet.classify_key(key) == "federal_individual")
        self.assertEqual(
            pdf_packet.classify_key("f3115_duplicate_copy"), "standalone")
        self.assertEqual(len(packet.pages), loose)
        tail = packet.pages[-1].extract_text()
        self.assertIn("Form 3115, Schedule E", tail)


class AmendmentPacketRefusalTests(unittest.TestCase):
    """An amendment packet does not carry a Form 3115: refused, not dropped."""

    def _run(self, original, amended, tmp):
        case = AmendmentCase(
            year=2025, explanation="SYNTHETIC-EXPLANATION",
            original_refund_received=0.0, original_refund_applied=0.0)
        return fx.orchestrator(tmp).run_amendment_packet(
            original, amended, case, Path(tmp) / "filed.yaml", None,
            Path(tmp) / "out")

    def test_amended_scenario_with_the_block_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with_block = fx.load(Path(tmp), fx.scenario_dict())
            without = dataclasses.replace(with_block, form_3115=None)
            for label, original, amended in (
                    ("amended", without, with_block),
                    ("original", with_block, without)):
                with self.subTest(side=label):
                    with self.assertRaisesRegex(
                            NotImplementedError, "amendment packet"):
                        self._run(original, amended, tmp)
                    self.assertFalse((Path(tmp) / "out").exists())

    def test_refusal_names_the_side_carrying_the_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            with_block = fx.load(Path(tmp), fx.scenario_dict())
            without = dataclasses.replace(with_block, form_3115=None)
            for original, amended, named in (
                    (without, with_block, "The amended scenario"),
                    (with_block, without, "The original scenario"),
                    (with_block, with_block,
                     "The original and amended scenario")):
                with self.subTest(named=named):
                    with self.assertRaises(NotImplementedError) as ctx:
                        self._run(original, amended, tmp)
                    self.assertTrue(str(ctx.exception).startswith(named))

    def test_twin_without_the_block_gets_past_the_refusal(self):
        """The same call without a Form 3115 reaches the filed-values read
        (which then fails on the missing file) instead of refusing."""
        with tempfile.TemporaryDirectory() as tmp:
            with_block = fx.load(Path(tmp), fx.scenario_dict())
            without = dataclasses.replace(with_block, form_3115=None)
            with self.assertRaises(Exception) as ctx:
                self._run(without, without, tmp)
            self.assertNotIn("Form 3115", str(ctx.exception))
            self.assertNotIsInstance(ctx.exception, NotImplementedError)


class CommandLineTests(unittest.TestCase):
    """`python -m tenforty federal ... --output-dir`: the form rides in the
    combined return packet, the duplicate copy and manifest stay loose."""

    def _run(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        scenario_path = root / "scenario.yaml"
        scenario_path.write_text(
            yaml.safe_dump(fx.scenario_dict(), sort_keys=False))
        out = root / "out"
        stdout = io.StringIO()
        argv = ["tenforty", "federal", str(scenario_path),
                "--output-dir", str(out)]
        with mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(stdout):
            code = cli_main()
        self.assertEqual(code, 0)
        return out, stdout.getvalue()

    def test_files_left_on_disk(self):
        out, _printed = self._run()
        self.assertEqual(sorted(p.name for p in out.iterdir()), [
            "f1040_2025_complete.pdf",
            "f3115_2025_duplicate_copy_to_sign.pdf",
            "f3115_filing_manifest_2025.txt",
            "f4868_2025.pdf",
        ])
        packet = PdfReader(out / "f1040_2025_complete.pdf")
        self.assertEqual(
            {k: v for k, v in _filled(out / "f1040_2025_complete.pdf").items()
             if k in _EXPECTED_BASE and "Page8" in k},
            {k: v for k, v in _EXPECTED_BASE.items() if "Page8" in k})
        self.assertIn(
            "Form 3115, Schedule E", packet.pages[-1].extract_text())

    def test_manifest_and_duplicate_copy_are_announced(self):
        out, printed = self._run()
        self.assertIn("=== Form 3115 ===", printed)
        self.assertIn(
            str(out / "f3115_filing_manifest_2025.txt"), printed)
        self.assertIn(
            str(out / "f3115_2025_duplicate_copy_to_sign.pdf"), printed)

    def test_nothing_is_announced_without_the_block(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        data = fx.scenario_dict()
        del data["form_3115"]
        (root / "scenario.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False))
        stdout = io.StringIO()
        argv = ["tenforty", "federal", str(root / "scenario.yaml"),
                "--output-dir", str(root / "out")]
        with mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(stdout):
            self.assertEqual(cli_main(), 0)
        self.assertNotIn("Form 3115", stdout.getvalue())


class EmitPathIsFailClosedTests(unittest.TestCase):
    def test_emit_refuses_a_block_the_ledger_would_refuse(self):
        """`emit_pdfs` handed a Scenario built in code, with results from
        elsewhere, still refuses before any Form 3115 is written."""
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(Path(tmp), fx.scenario_dict())
            orchestrator = fx.orchestrator(tmp)
            results = orchestrator.compute_federal(scenario)
            scenario.form_3115 = dataclasses.replace(
                scenario.form_3115, designated_change_number=8)
            out = Path(tmp) / "out"
            with self.assertRaisesRegex(
                    NotImplementedError, "designated_change_number 8"):
                orchestrator.emit_pdfs(scenario, results, out)
            self.assertEqual(sorted(p.name for p in out.glob("f3115*")), [])


if __name__ == "__main__":
    unittest.main()
