"""The contested-law positions registry (spec §13): every entry is
well-formed, and the first entry carries its citation trail as ledgered."""
import datetime
import re
import unittest

from tenforty import positions

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
QBI_SEHI = "qbi-sehi-shareholder-reduction"


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


if __name__ == "__main__":
    unittest.main()
