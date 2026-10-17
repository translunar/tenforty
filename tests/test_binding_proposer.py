"""Binding proposals (emit-verification harness spec §4.2).

The proposer turns the official artifacts (line inventories, IRS
stylesheets) and the computation's output key NAMES into machine
proposals: a naming-convention key is auto-confirmed only when the
artifacts and the key's own words agree; everything else goes to agents as
an exception; the description ranking never binds.
"""
import dataclasses
import unittest
import unittest.mock

from tenforty.declarations import inventory, propose, stylesheet
from tenforty.declarations.propose import Binding, Exception_
from tests.fixtures.sch_c_battery import LINE_KEYS

# STAND-IN candidate pool: the only compute-key names this lane may use
# today are the ones the plan and spec quote. The real per-form names-only
# lists arrive at the pilot via scripts/harness_output_keys.py (from the
# real emit path's EmitRecord); RankingTests gets its realistic pool then.
STAND_IN_POOL = (
    "agi",
    "taxable_income",
    "f8995_line_15_qbi_deduction",
    "f8995_line_3_component",
    "f8995_line_6_total_before_limit",
    "sch_se_line_12_se_tax",
)
F8995_KEYS = (
    "f8995_line_15_qbi_deduction",
    "f8995_line_3_component",
    "f8995_line_6_total_before_limit",
)


def _exceptions(proposals, line, reason=None):
    return [e for e in proposals.exceptions
            if e.line == line and (reason is None or e.reason == reason)]


class NamingPassTests(unittest.TestCase):
    def test_f8995_2025_line_15_auto_confirms_with_its_stylesheet_element(self):
        (sheet_15,) = [l for l in stylesheet.load("f8995", 2025)
                       if l.label == "15"]
        proposals = propose.propose("f8995", 2025, F8995_KEYS)
        self.assertIn(
            Binding("", "15", "f8995_line_15_qbi_deduction",
                    f"naming+stylesheet:{sheet_15.elements[0]}"),
            proposals.auto_confirmed)

    def test_naming_pass_needs_the_forms_prefix(self):
        # The 1040's keys carry no line-number convention (KEY_PREFIX has
        # no entry): nothing auto-confirms.
        self.assertNotIn("1040", propose.KEY_PREFIX)
        self.assertEqual(
            propose.propose("1040", 2025, STAND_IN_POOL).auto_confirmed, ())


class SeamTests(unittest.TestCase):
    """A key whose number names a line its words do not describe is a seam:
    never auto-confirmed. The known seams are LINE_KEYS's (tests may cite
    it as the expected answer; they are not authors)."""

    def test_f8995_line_3_component_is_a_seam_with_printed_5_first(self):
        self.assertEqual(LINE_KEYS["f8995"]["5"], "f8995_line_3_component")
        proposals = propose.propose("f8995", 2025, F8995_KEYS)
        self.assertNotIn("f8995_line_3_component",
                         [b.key for b in proposals.auto_confirmed])
        (seam,) = _exceptions(proposals, "3", "seam")
        self.assertEqual(seam.candidates[0], "5")
        self.assertIn("f8995_line_3_component", seam.candidates)

    def test_f8995_line_6_total_before_limit_is_a_seam_naming_printed_10(self):
        self.assertEqual(LINE_KEYS["f8995"]["10"],
                         "f8995_line_6_total_before_limit")
        proposals = propose.propose("f8995", 2025, F8995_KEYS)
        (seam,) = _exceptions(proposals, "6", "seam")
        self.assertIn("10", seam.candidates)

    def test_a_key_with_no_words_left_fails_closed_to_a_seam(self):
        # "f8995_line_10" says nothing beyond its number, so nothing can
        # agree with it: a seam for agent review, never auto.
        proposals = propose.propose("f8995", 2025, ("f8995_line_10",))
        self.assertEqual(proposals.auto_confirmed, ())
        self.assertEqual([e.reason for e in _exceptions(proposals, "10")],
                         ["seam"])


class AcronymTests(unittest.TestCase):
    def test_three_letter_acronyms_match_consecutive_initials(self):
        self.assertEqual(propose.containment(
            ["agi"], propose.words("This is your adjusted gross income")), 1.0)
        self.assertEqual(propose.containment(
            ["qbi"], propose.words("Qualified business income deduction")),
            1.0)

    def test_two_letter_words_never_match_as_initials(self):
        # Floor: an acronym match needs a key word of 3+ characters.
        self.assertEqual(propose.containment(
            ["se"], propose.words("self employment tax")), 0.0)


class RankingTests(unittest.TestCase):
    """The description ranking for a line no key names. Vehicle: the 1040
    (2025) AGI lines (stylesheet element AdjustedGrossIncomeAmt). No 1040
    2025 line's text BEGINS "Adjusted gross income" (only Form 1040-X
    rev-2025-12 line 1 does), so the vehicle is the line by its element,
    not by that phrase."""

    def test_agi_ranks_in_the_top_three_for_the_agi_lines(self):
        proposals = propose.propose("1040", 2025, STAND_IN_POOL)
        for line in ("11b", "11a"):
            with self.subTest(line=line):
                (exc,) = _exceptions(proposals, line, "no-proposal")
                self.assertIn("agi", exc.candidates[:3])

    def test_the_vehicle_lines_carry_the_agi_element(self):
        styles = propose.stylesheet_lines("1040", 2025)
        for line in ("11b", "11a"):
            with self.subTest(line=line):
                self.assertIn("AdjustedGrossIncomeAmt",
                              styles[("", line)].elements)


class NeverAutoBindsRankingTests(unittest.TestCase):
    def test_only_naming_proposals_ever_auto_confirm(self):
        for form, key, pool in (("f8995", 2025, F8995_KEYS + STAND_IN_POOL),
                                ("1040", 2025, STAND_IN_POOL)):
            with self.subTest(form=form):
                for binding in propose.propose(form, key, pool).auto_confirmed:
                    self.assertTrue(binding.evidence.startswith("naming+"),
                                    binding)
                    self.assertTrue(binding.key.startswith(
                        propose.KEY_PREFIX[form] + "_line"), binding)


class StylesheetGateTests(unittest.TestCase):
    def test_a_line_whose_stylesheet_text_disagrees_is_not_auto_confirmed(self):
        # Reachable negative space for the federal gate: the same f8995
        # line 15 proposal, with the stylesheet's text for line 15 swapped
        # for an unrelated line's, becomes a "disagree" exception.
        real = propose.stylesheet_lines("f8995", 2025)
        perturbed = dict(real)
        perturbed[("", "15")] = dataclasses.replace(
            real[("", "15")], text=real[("", "3")].text)
        with unittest.mock.patch.object(
                propose, "stylesheet_lines", lambda form, year: perturbed):
            proposals = propose.propose("f8995", 2025, F8995_KEYS)
        self.assertNotIn("f8995_line_15_qbi_deduction",
                         [b.key for b in proposals.auto_confirmed])
        self.assertEqual([e.reason for e in _exceptions(proposals, "15")],
                         ["disagree"])


class ProposeScriptTests(unittest.TestCase):
    def test_writes_one_json_per_form_year_and_summarizes(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path

        from scripts import harness_propose
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "keys.txt"
            keys.write_text("\n".join(F8995_KEYS) + "\n")
            out = io.StringIO()
            with redirect_stdout(out):
                harness_propose.main(["--form", "f8995", "--keys", "2025",
                                      "--output-keys", str(keys),
                                      "--out", tmp])
            data = json.loads(
                (Path(tmp) / "proposals" / "f8995_2025.json").read_text())
        self.assertEqual([b["key"] for b in data["auto_confirmed"]],
                         ["f8995_line_15_qbi_deduction"])
        self.assertIn("1 auto-confirmed", out.getvalue())
        self.assertIn("seam=2", out.getvalue())


class ConsumerCaveatTests(unittest.TestCase):
    """The extraction lanes' recorded caveats (harness ledger)."""

    def test_stray_1040_2025_labels_cannot_auto_confirm(self):
        # 1040 (2025) page 1 carries two checkbox-option digits as stray
        # labels "2" and "3" (texts "Line 3b" and ""): no stylesheet text
        # agrees with them, so no naming key could auto-confirm onto them.
        styles = propose.stylesheet_lines("1040", 2025)
        strays = [l for l in inventory.load("1040", 2025).lines
                  if l.page == 1 and l.label in ("2", "3")]
        self.assertEqual(sorted(l.label for l in strays), ["2", "3"])
        for stray in strays:
            with self.subTest(label=stray.label):
                self.assertLess(propose.stylesheet_agreement(styles, stray),
                                propose.STYLESHEET_AGREEMENT)

    def test_stylesheet_sub_letters_carry_the_last_number(self):
        styles = propose.stylesheet_lines("sch_se", 2024)
        for label in ("1b", "4b", "4c", "8d"):
            self.assertIn(("Part I", label), styles)

    def test_sch_ca_split_rows_are_not_lines_to_bind(self):
        # Schedule CA (2025): the printed row "19" reads "a Alimony paid."
        # beside the tooltip's own "19a"; it is the same line, split.
        lines = inventory.load("sch_ca", 2025).lines
        section_c = "Part I Section C"
        (row_19,) = [l for l in lines
                     if l.label == "19" and l.section == section_c]
        self.assertTrue(row_19.text.startswith("a "))
        self.assertTrue(propose.is_split_row(row_19, lines))
        (line_19a,) = [l for l in lines if l.label == "19a"]
        self.assertFalse(propose.is_split_row(line_19a, lines))
        # Part II's own line 19 is a real line, not a split row.
        (part_ii_19,) = [l for l in lines
                         if l.label == "19" and l.section == "Part II"]
        self.assertFalse(propose.is_split_row(part_ii_19, lines))


if __name__ == "__main__":
    unittest.main()
