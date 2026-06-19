"""Tests for tenforty.pdf_packet — combined per-filing PDF assembly.

Pure file-assembly logic: ordering of emitted form-keys into packets, the
partition invariant (every emitted key is claimed by exactly one packet or
is the standalone 4868 exception), and pypdf concatenation. No tax math.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty import pdf_packet


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
        # Federal corporate
        "1120s", "1120s_k1_0", "1120s_k1_1", "1120s_k1_2",
        # California
        "f540", "sch_ca", "sch_d_540",
        # Standalone
        "4868",
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


if __name__ == "__main__":
    unittest.main()
