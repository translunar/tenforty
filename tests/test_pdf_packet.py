"""Tests for tenforty.pdf_packet — combined per-filing PDF assembly.

Pure file-assembly logic: ordering of emitted form-keys into packets, the
partition invariant (every emitted key is claimed by exactly one packet or
is the standalone 4868 exception), and pypdf concatenation. No tax math.
"""

import ast
import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty import pdf_packet
from tenforty.models import SourceDocument
from tests.helpers import REPO_ROOT


def _make_pdf(path: Path, num_pages: int) -> Path:
    """Write a minimal valid PDF with `num_pages` blank pages."""
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)
    writer.close()
    return path


class OrderedMembersTests(unittest.TestCase):
    def test_federal_individual_sorts_into_attachment_order(self):
        # Deliberately scrambled insertion order.
        emitted = {
            "8959": Path("/x/8959.pdf"),
            "sch_e": Path("/x/sch_e.pdf"),
            "1040": Path("/x/1040.pdf"),
            "sch_d": Path("/x/sch_d.pdf"),
            "f8949": Path("/x/f8949.pdf"),
            "sch_1": Path("/x/sch_1.pdf"),
            "4868": Path("/x/4868.pdf"),  # standalone — must not appear
        }
        paths = pdf_packet.ordered_members(emitted, pdf_packet.FEDERAL_INDIVIDUAL)
        names = [p.name for p in paths]
        # 1040 first, then sch_1(01), sch_d(12), f8949(12A), sch_e(13), 8959(71).
        self.assertEqual(
            names,
            ["1040.pdf", "sch_1.pdf", "sch_d.pdf", "f8949.pdf", "sch_e.pdf", "8959.pdf"],
        )
        self.assertNotIn("4868.pdf", names)

    def test_8949_sorts_between_sch_d_and_sch_e(self):
        emitted = {
            "sch_e": Path("/x/sch_e.pdf"),
            "f8949": Path("/x/f8949.pdf"),
            "sch_d": Path("/x/sch_d.pdf"),
        }
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, ["sch_d.pdf", "f8949.pdf", "sch_e.pdf"])

    def test_absent_members_are_skipped(self):
        emitted = {"1040": Path("/x/1040.pdf"), "sch_e": Path("/x/sch_e.pdf")}
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, ["1040.pdf", "sch_e.pdf"])


class K1FamilyTests(unittest.TestCase):
    def test_k1s_sort_numerically_not_lexically(self):
        emitted = {
            "1120s_k1_10": Path("/x/k1_10.pdf"),
            "1120s": Path("/x/1120s.pdf"),
            "1120s_k1_2": Path("/x/k1_2.pdf"),
            "1120s_k1_0": Path("/x/k1_0.pdf"),
        }
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_CORPORATE)]
        # 1120s main first, then K-1s in numeric (not lexical) order.
        self.assertEqual(
            names,
            ["1120s.pdf", "k1_0.pdf", "k1_2.pdf", "k1_10.pdf"],
        )

    def test_arbitrary_k1_count_handled(self):
        emitted = {"1120s": Path("/x/1120s.pdf")}
        emitted.update(
            {f"1120s_k1_{i}": Path(f"/x/k1_{i}.pdf") for i in range(7)}
        )
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_CORPORATE)]
        self.assertEqual(len(names), 8)
        self.assertEqual(names[0], "1120s.pdf")
        self.assertEqual(names[-1], "k1_6.pdf")


class PartitionInvariantTests(unittest.TestCase):
    REAL_KEYS = {
        # Federal individual
        "1040", "sch_1", "sch_a", "sch_b", "sch_d", "f8949", "sch_e",
        "f8995", "8959", "f8582", "f4562",
        "sch_2", "sch_se", "sch_c_1", "sch_c_2", "8962",
        # Federal corporate
        "1120s", "1120s_k1_0", "1120s_k1_1", "1120s_k1_2",
        "1120s_k1_qbi_stmt_1",
        # California
        "f540", "sch_ca", "sch_d_540",
        # Standalone
        "4868", "depreciation_audit",
    }

    def test_every_real_emitted_key_is_claimed_exactly_once(self):
        for key in self.REAL_KEYS:
            with self.subTest(key=key):
                self.assertIsNotNone(
                    pdf_packet.classify_key(key),
                    f"emitted key {key!r} is claimed by no packet and is not "
                    f"the standalone exception — partition gap",
                )

    def test_4868_is_standalone(self):
        self.assertEqual(pdf_packet.classify_key("4868"), "standalone")

    def test_depreciation_audit_is_standalone(self):
        # Review matter beside the forms: an xlsx, never a packet member.
        self.assertEqual(
            pdf_packet.classify_key("depreciation_audit"), "standalone")
        for packet in pdf_packet.PACKETS:
            with self.subTest(packet=packet.name):
                self.assertNotIn(
                    "depreciation_audit", [m.key for m in packet.members])

    def test_unknown_key_is_unclaimed(self):
        self.assertIsNone(pdf_packet.classify_key("f9999_new_form"))

    def test_k1_family_keys_claimed_by_corporate(self):
        self.assertEqual(
            pdf_packet.classify_key("1120s_k1_5"), "federal_corporate")
        self.assertEqual(pdf_packet.classify_key("1120s"), "federal_corporate")


class AssemblePacketTests(unittest.TestCase):
    def test_page_count_is_sum_of_inputs_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = _make_pdf(d / "a.pdf", 2)
            b = _make_pdf(d / "b.pdf", 3)
            c = _make_pdf(d / "c.pdf", 1)
            out = pdf_packet.assemble_packet([a, b, c], d / "out.pdf")
            self.assertTrue(out.exists())
            reader = pypdf.PdfReader(str(out))
            self.assertEqual(len(reader.pages), 6)


class AssembleAllTests(unittest.TestCase):
    def test_scorp_run_produces_two_federal_packets(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            emitted = {
                "1040": _make_pdf(d / "f1040_2025.pdf", 2),
                "sch_e": _make_pdf(d / "f1040se_2025.pdf", 1),
                "4868": _make_pdf(d / "f4868_2025.pdf", 1),
                "1120s": _make_pdf(d / "f1120s_2025.pdf", 5),
                "1120s_k1_0": _make_pdf(d / "f1120s_k1_0_2025.pdf", 1),
                "1120s_k1_1": _make_pdf(d / "f1120s_k1_1_2025.pdf", 1),
            }
            combined = pdf_packet.assemble_all(emitted, d, 2025)
            self.assertEqual(
                set(combined),
                {"federal_individual", "federal_corporate"},
            )
            self.assertEqual(
                combined["federal_individual"].name, "f1040_2025_complete.pdf")
            self.assertEqual(
                combined["federal_corporate"].name, "f1120s_2025_complete.pdf")
            ind = pypdf.PdfReader(str(combined["federal_individual"]))
            self.assertEqual(len(ind.pages), 3)  # 1040(2) + sch_e(1); 4868 excluded
            corp = pypdf.PdfReader(str(combined["federal_corporate"]))
            self.assertEqual(len(corp.pages), 7)  # 1120s(5) + 2 K-1s(1 each)

    def test_packet_with_no_members_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            emitted = {"f540": _make_pdf(d / "f540_2025.pdf", 2)}
            combined = pdf_packet.assemble_all(emitted, d, 2025)
            self.assertEqual(set(combined), {"california"})


class SourceDocumentSplicingTests(unittest.TestCase):
    """Source documents splice in immediately after the main form."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def _emit(self, key: str, pages: int) -> Path:
        return _make_pdf(self.base / f"{key}.pdf", pages)

    def _doc(self, name: str, pages: int, packets: tuple) -> SourceDocument:
        return SourceDocument(
            path=_make_pdf(self.base / name, pages), kind="w2",
            packets=packets)

    def test_docs_splice_after_main_form_before_first_schedule(self):
        emitted = {
            "1040": self._emit("1040", 2),
            "sch_1": self._emit("sch_1", 1),
        }
        doc = self._doc("w2.pdf", 1, ("federal_individual",))
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=[doc])
        # 1040 (2 pages) + w2 (1 page) + sch_1 (1 page) = 4 pages
        reader = pypdf.PdfReader(str(combined["federal_individual"]))
        self.assertEqual(len(reader.pages), 4)

    def test_doc_page_lands_between_main_form_and_schedules(self):
        emitted = {
            "1040": self._emit("1040", 2),
            "sch_1": self._emit("sch_1", 1),
        }
        # Distinctive page size marks the source doc's page.
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        doc_path = self.base / "w2.pdf"
        with open(doc_path, "wb") as f:
            writer.write(f)
        writer.close()
        doc = SourceDocument(
            path=doc_path, kind="w2", packets=("federal_individual",))
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=[doc])
        reader = pypdf.PdfReader(str(combined["federal_individual"]))
        widths = [float(p.mediabox.width) for p in reader.pages]
        self.assertEqual(widths, [72.0, 72.0, 100.0, 72.0])

    def test_california_routing_honored(self):
        emitted = {
            "1040": self._emit("1040", 1),
            "f540": self._emit("f540", 1),
            "sch_ca": self._emit("sch_ca", 1),
        }
        doc = self._doc("w2.pdf", 1, ("federal_individual", "california"))
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=[doc])
        fed = pypdf.PdfReader(str(combined["federal_individual"]))
        ca = pypdf.PdfReader(str(combined["california"]))
        self.assertEqual(len(fed.pages), 2)   # 1040 + w2
        self.assertEqual(len(ca.pages), 3)    # 540 + w2 + sch_ca

    def test_federal_only_doc_stays_out_of_california(self):
        emitted = {
            "1040": self._emit("1040", 1),
            "f540": self._emit("f540", 1),
        }
        doc = self._doc("w2.pdf", 1, ("federal_individual",))
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=[doc])
        self.assertEqual(
            len(pypdf.PdfReader(str(combined["california"])).pages), 1)

    def test_docs_alone_do_not_create_a_packet(self):
        # A california-routed doc with no CA forms emitted is inert.
        emitted = {"1040": self._emit("1040", 1)}
        doc = self._doc("w2.pdf", 1, ("federal_individual", "california"))
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=[doc])
        self.assertNotIn("california", combined)

    def test_multiple_docs_keep_declaration_order(self):
        emitted = {"1040": self._emit("1040", 1)}
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with open(self.base / "first.pdf", "wb") as f:
            writer.write(f)
        writer.close()
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(self.base / "second.pdf", "wb") as f:
            writer.write(f)
        writer.close()
        docs = [
            SourceDocument(path=self.base / "first.pdf", kind="w2",
                           packets=("federal_individual",)),
            SourceDocument(path=self.base / "second.pdf", kind="w2",
                           packets=("federal_individual",)),
        ]
        combined = pdf_packet.assemble_all(
            emitted, self.base, 2024, source_documents=docs)
        reader = pypdf.PdfReader(str(combined["federal_individual"]))
        widths = [float(p.mediabox.width) for p in reader.pages]
        self.assertEqual(widths, [72.0, 100.0, 200.0])

    def test_no_docs_default_is_unchanged_behavior(self):
        emitted = {
            "1040": self._emit("1040", 1),
            "sch_1": self._emit("sch_1", 1),
        }
        combined = pdf_packet.assemble_all(emitted, self.base, 2024)
        reader = pypdf.PdfReader(str(combined["federal_individual"]))
        self.assertEqual(len(reader.pages), 2)


def _federal_emit_spec_names() -> set[str]:
    """Every emit-spec name `_federal_individual_emit_specs` can produce,
    read from the orchestrator's SOURCE: the `name=` argument of each
    `_FederalFormSpec(...)` call. An f-string name (the indexed Schedule C
    family) is sampled with "1" in each placeholder, e.g. "sch_c_1"."""
    source = (REPO_ROOT / "tenforty" / "orchestrator.py").read_text()
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "_FederalFormSpec"):
            continue
        for keyword in node.keywords:
            if keyword.arg != "name":
                continue
            value = keyword.value
            if isinstance(value, ast.Constant):
                names.add(value.value)
            elif isinstance(value, ast.JoinedStr):
                names.add("".join(
                    part.value if isinstance(part, ast.Constant) else "1"
                    for part in value.values))
            else:
                raise AssertionError(
                    "emit-spec name is neither a literal nor an f-string; "
                    "teach _federal_emit_spec_names how to sample it")
    return names


class EmitSpecNamesAreClaimedTests(unittest.TestCase):
    """The partition invariant over the keys the orchestrator REALLY emits,
    not a hand-kept list. Form 8962 was emitted under a key no packet
    claimed and the hand-kept list never noticed."""

    def test_enumeration_sees_the_real_specs(self):
        names = _federal_emit_spec_names()
        for expected in ("1040", "4868", "sch_1", "8959", "8962", "f8995"):
            self.assertIn(expected, names)

    def test_every_federal_emit_spec_name_is_claimed(self):
        for name in sorted(_federal_emit_spec_names()):
            with self.subTest(name=name):
                self.assertIn(
                    pdf_packet.classify_key(name),
                    ("federal_individual", "standalone"),
                    f"emit spec {name!r} is claimed by no packet",
                )

    def test_form_8962_sorts_after_8959_and_lands_in_the_packet(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            emitted = {
                "8962": _make_pdf(d / "f8962_2024.pdf", 2),
                "f8582": _make_pdf(d / "f8582_2024.pdf", 1),
                "1040": _make_pdf(d / "f1040_2024.pdf", 2),
                "8959": _make_pdf(d / "f8959_2024.pdf", 1),
            }
            names = [p.name for p in pdf_packet.ordered_members(
                emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
            self.assertEqual(names, [
                "f1040_2024.pdf", "f8959_2024.pdf", "f8962_2024.pdf",
                "f8582_2024.pdf"])
            combined = pdf_packet.assemble_all(emitted, d, 2024)
            reader = pypdf.PdfReader(str(combined["federal_individual"]))
            self.assertEqual(len(reader.pages), 6)


class ScheduleCFamilyPacketTests(unittest.TestCase):
    def test_new_keys_are_claimed_by_federal_individual(self):
        for key in ("sch_2", "sch_se", "sch_c_1", "sch_c_12"):
            with self.subTest(key=key):
                self.assertEqual(
                    pdf_packet.classify_key(key), "federal_individual")

    def test_bare_sch_c_and_california_sch_ca_are_not_in_the_family(self):
        # Schedule C keys are always indexed; "sch_ca" is California's.
        self.assertIsNone(pdf_packet.classify_key("sch_c"))
        self.assertEqual(pdf_packet.classify_key("sch_ca"), "california")

    def test_attachment_sequence_order(self):
        emitted = {
            "sch_se": Path("/x/sch_se.pdf"),
            "f8995": Path("/x/f8995.pdf"),
            "sch_c_2": Path("/x/sch_c_2.pdf"),
            "sch_d": Path("/x/sch_d.pdf"),
            "sch_2": Path("/x/sch_2.pdf"),
            "sch_e": Path("/x/sch_e.pdf"),
            "sch_c_1": Path("/x/sch_c_1.pdf"),
            "sch_b": Path("/x/sch_b.pdf"),
            "sch_1": Path("/x/sch_1.pdf"),
            "1040": Path("/x/1040.pdf"),
            "sch_a": Path("/x/sch_a.pdf"),
        }
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, [
            "1040.pdf", "sch_1.pdf", "sch_2.pdf", "sch_a.pdf", "sch_b.pdf",
            "sch_c_1.pdf", "sch_c_2.pdf", "sch_d.pdf", "sch_e.pdf",
            "sch_se.pdf", "f8995.pdf",
        ])

    def test_ten_or_more_businesses_sort_numerically(self):
        emitted = {f"sch_c_{i}": Path(f"/x/c{i}.pdf") for i in (10, 2, 1, 11)}
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, ["c1.pdf", "c2.pdf", "c10.pdf", "c11.pdf"])


if __name__ == "__main__":
    unittest.main()
