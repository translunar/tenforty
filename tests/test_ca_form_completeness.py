"""Template-wide completeness for every CA form we emit.

Standard: every fillable cell on the template is either FILLED in the emitted
PDF or matched by a documented blank-by-design rule below (regex on the
widget's /TU tooltip -> reason). Two meta-assertions keep the lists honest:
no unfilled cell may be unclassified, and no rule may be dead.

"Unfilled" means unfilled in EVERY scenario emitted (refund and amount-owed), so
a cell that fills only on one branch (line 111 owe vs line 115 refund) is not
blank-by-design.
"""

import unittest

from tests._blank_by_design import classify, unfilled
from tests._ca_emit_helpers import (
    CA_YEARS, emit_ca, emit_ca_with_sch_d_adjustment, make_ca_scenario)

SCENARIOS = (dict(), dict(state_tax_withheld=0.0))   # refund, amount owed

# ── Form 540 ────────────────────────────────────────────────────────────────
F540_BLANK_BY_DESIGN = [
    # Identity: no model input for these.
    (r"Suffix", "no name-suffix input in the scenario"),
    # BLIND SPOT: this pattern cannot tell the spouse's cell from the taxpayer's
    # (identical bare tooltip on 2021-2023, and it also matches the taxpayer's
    # "Middle Initial." on 2024-2025), so it would waive a blank TAXPAYER cell
    # too. test_f540_middle_initial_cell_is_filled_from_config_every_year is
    # the load-bearing guard for that cell; do not remove it while this rule stands.
    (r"^Middle Initial\.?$",
     "spouse middle initial on the 2021-2023 templates, whose tooltip is the same bare 'Middle "
     "Initial' as the taxpayer's cell: single-filer scenario. The taxpayer's cell is fed from "
     "config.middle_initial and proven filled by "
     "test_f540_middle_initial_cell_is_filled_from_config_every_year"),
    (r"Spouse.*(SSN|S S N)|spouse.*first name|Spouse's.*Last name|Spouse.*Middle|Spouse.*Suffix",
     "spouse identity: single-filer scenario (fed from config.spouse_* when present; MFJ/MFS cannot "
     "emit through the workbook)"),
    (r"Spouse's.*Date of Birth", "no spouse birthdate input in the scenario"),
    (r"Prior Name|prior name", "no prior-name input"),
    (r"Additional information|Principal Business Activity|PBA|Private Mailbox|Apartment number",
     "no input for additional info / PBA code / PMB / apartment number"),
    (r"Foreign (country|province|postal)", "foreign address: scenario address is domestic"),
    (r"Street address \(number and street\) \(If foreign|"
     r"^City\.$|^State\. Enter two letter|^Zip code\. $|Zip code\. *$",
     "principal-residence address block: blank because the 'same as your principal/physical "
     "residence' box is checked (config.address_is_principal_residence); the separate "
     "physical-residence address is not modeled"),
    (r"AMENDED return", "original return (amended returns use the amended-packet path)"),
    (r"Fiscal year filers", "calendar-year filer"),
    (r"California filing status is different from your federal", "no CA-vs-federal filing-status override input"),
    (r"Line 3\. Enter spouse|Line 5\. Enter year spouse|Line 5\. See instructions",
     "MFS spouse-SSN / QSS death-year lines: not modeled"),
    (r"Line 6\. If someone can claim you", "dependent-of-another box not modeled (would change line 7)"),
    (r"Line 8\. Blind|multiply the number you put in the line 8 box",
     "line 8 blind exemption: not modeled; blank when zero"),
    (r"Line 9\. Senior|multiply the number you put in the line 9 box",
     "line 9 senior exemption: not modeled; blank when zero"),
    (r"Dependent (One|Two|Three)|Line 10\. Dependents|Total dependent exemptions|"
     r"number of total dependent exemptions",
     "line 10: names/SSNs/relationships not in the scenario (dependents are a bare list); count and "
     "amount fill when dependents exist (see test_ca_540_presentation)"),
    # Tax/credits not modeled
    (r"Line 31\. Tax\.? *Check the box if tax is from (FTB 3800|FTB 3803)|Checkbox (C|D)",
     "line 31 FTB 3800/3803 tax sources: not modeled"),
    (r"Line 31\. Tax\.? *(Checkbox B\.)? *Check the box if tax is from Tax Rate Schedule",
     "rate-schedule box: set only above $100,000 taxable income (scenario is below)"),
    (r"Line 34", "line 34 (Sch G-1 / FTB 5870A): not modeled; blank means zero"),
    (r"Line 40\.|Line 43\.|Line 44\.|Line 45\.", "special credits lines 40-45: not modeled"),
    (r"Line 61\.|Line 62\.|Line 63\.", "other taxes lines 61-63: not modeled"),
    (r"Line 73\.|Line 74\.|Line 75\.|Line 76\.|Line 77\.",
     "payment lines 73-77 (592-B/593, Prog 4.0, EITC, YCTC, FYTC): not modeled; blank means zero"),
    (r"^(\[Part II\] )?Line 9[256] ?\. (Payments after )?Individual Shared Responsibility",
     "ISR penalty amount lines 92 / 95 / 96: the penalty (FTB 3853) is not modeled; blank means "
     "zero, which holds because the full-year coverage box on line 92 is checked (a coverage gap "
     "refuses instead of printing a blank penalty)"),
    (r"Line 98\.", "line 98 carryover to next-year estimated tax: not modeled"),
    (r"Code \d+\.|Contributions\. Code", "voluntary-contribution fund lines: only the line-110 total is modeled"),
    (r"Line 113\. Underpayment of estimated tax\. Check the box",
     "FTB 5805 / 5805F attachment boxes: no Form 5805 modeled (documented limitation in "
     "pdf_f540; line 113 itself is a stated amount and prints)"),
    (r"Line 116|Line 117|direct deposit|remaining amount of my refund|Account type",
     "direct deposit: no bank-account input (deliberately never in the scenario)"),
    (r"Voter information|Organ Donor|Health Care Coverage Information|Spouse / R D P \(if joint|"
     r"Primary taxpayer", "elections / opt-in boxes: filer's personal choice, never defaulted"),
    (r"Your email address|Preferred phone number", "no email/phone input in the scenario"),
    (r"Date\. Enter date signed", "signature date: written by hand at signing"),
    (r"paid preparer|Firm|Preparer Tax Identification|Federal Employer Identification",
     "paid-preparer block: self-prepared scenario"),
    (r"Third Party Designee.s Name|Third party designee.s telephone",
     "designee name/phone: designee is 'No'"),
    (r"Line (Two|Three|Four|Five)[:.]|Line (2|3|4|5)\. (Married|Head|Qualifying)",
     "filing-status boxes for the statuses NOT selected (scenario files Single)"),
    (r"Line 6: If someone can claim you", "dependent-of-another box not modeled (would change line 7)"),
    (r"Line 64\. Excess Advance Premium Assistance",
     "2021 line 64 excess APAS repayment: out of v1 scope (documented at _total_tax_2021)"),
    (r"Checkbox B\. Check the box if FTB 5805F|Checkbox A\. Check the box if FTB 5805",
     "FTB 5805 / 5805F attachment boxes: no Form 5805 modeled"),
    (r"voter registration", "elections / opt-in boxes: filer's personal choice, never defaulted"),
    (r"^(Last name|City|State)\.?$|^Zip code\.|^State\. +Enter two letter",
     "spouse last name / principal-residence city-state-zip: same-address filer, no spouse"),
    (r"Spouse's or Registered Domestic Partner's Social Security",
     "spouse SSN: single-filer scenario"),
]


# ── Schedule CA (540) ───────────────────────────────────────────────────────
SCH_CA_BLANK_BY_DESIGN = [
    # Part Two prints on an itemizing return (see tests/test_ca_sch_ca_part_ii_print.py,
    # which asserts every placed cell by value). What stays blank even then:
    (r"^\[Part II\] (?:[^.]*\. )?Line\s+(?:19|20|21|22|23|24|25|27)\s*\.",
     "Part Two lines 19-25 (job expenses / 2% miscellaneous deductions) and 27 (other "
     "adjustments): no scenario input; lines 26 and 28 carry line 18 down unchanged"),
    (r"^\[Part II\] (?:[^.]*\. )?Line\s+(?:5 ?c|6|8 ?[bcd]|9|12|13|15|16)\s*\.",
     "Part Two lines whose federal Schedule A line is zero on every return forms.sch_a.compute "
     "produces (5c, 6, 8b-8d, 9, 12, 13, 15, 16): blank, as on the federal Schedule A; a "
     "nonzero line 6 / 15 / 16 refuses in compute_part_ii_itemized instead of printing unadjusted"),
    (r"^\[Part II\] (?:[^.]*\. )?Line\s+(?:4|8 ?a|8 ?e|10|11|14)\s*\.\s*Column [BC]\.",
     "Part Two Col B / Col C on the medical, interest and charity lines: those sections "
     "conform in v1 (Col A passes through), so there is no adjustment to print; the only "
     "modeled adjustment is state income tax on lines 5a / 5e, carried to 7 and 17"),
    (r"Column A\. Federal Amounts|Column A\.? *$|Federal Amounts\.",
     "Col A for a line with no federal source in the compute (federal 1b-1i, 2a alimony, 8a-8v, "
     "12/14/16/18/19a/23/24x, 25): blank, as the federal 1040 is blank there"),
    (r"Column [BC]\. (Subtractions|Additions)",
     "Col B / Col C for a line no catalog row posts to (every catalog-reachable cell is placed and "
     "proven by test_ca_sch_ca_completeness)"),
    (r"Check the box if you did NOT itemize for federal but will itemize",
     "elective CA-only itemization box: v1 itemizes for CA iff the federal return itemized (not modeled)"),
    (r"Enter type of|List type|Specify|Date of original divorce|Recipient|Reserved for future use|"
     r"Enter date",
     "free-text write-ins / dates / recipient identity: no scenario input"),
]


# ── Schedule D (540) ────────────────────────────────────────────────────────
SCH_D_540_BLANK_BY_DESIGN = [
    (r".", "KNOWN GAP (reported): Sch D (540) is a pass-through of the federal Schedule D net "
           "(sch_d_540.compute); only the identity header and the net-capital-gain total cells are "
           "placed. The line-by-line federal / CA columns (1a-16, Part II QSBS/QOZ adjustments) have "
           "no compute keys and are not placed."),
]


class CAFormCompletenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_ca_sch_ca_part_ii_print import itemizing_scenario
        cls.emits = {}
        for year in CA_YEARS:
            cls.emits[year] = [emit_ca(make_ca_scenario(year, **kw))[1] for kw in SCENARIOS]
            # An itemizing return, so a Part Two cell counts as blank only if
            # it is blank even when California itemized deductions are taken.
            cls.emits[year].append(emit_ca(itemizing_scenario(year))[1])
        # Schedule D (540) is omitted from the scenarios above (no CA capital-
        # gain adjustment), so its cells are inspected on emits that carry one.
        cls.sch_d_emits = {
            year: [emit_ca_with_sch_d_adjustment(make_ca_scenario(year, **kw))[1]
                   for kw in SCENARIOS]
            for year in CA_YEARS}

    def _blank_cells(self, year: int, basename: str) -> dict[str, dict]:
        per_scenario = [unfilled(pdfs[basename]) for pdfs in self.emits[year]]
        first, rest = per_scenario[0], per_scenario[1:]
        return {n: i for n, i in first.items() if all(n in r for r in rest)}

    def test_f540_every_blank_cell_is_documented(self):
        all_used = set()
        for year in CA_YEARS:
            with self.subTest(year=year):
                bad, used = classify(self._blank_cells(year, "f540"), F540_BLANK_BY_DESIGN)
                all_used |= used
                self.assertEqual(bad, [], f"{year}: unclassified blank 540 cells")
        dead = [F540_BLANK_BY_DESIGN[i][0] for i in range(len(F540_BLANK_BY_DESIGN))
                if i not in all_used]
        self.assertEqual(dead, [], "dead blank-by-design rules (match no blank cell in any year)")

    def test_f540_county_cell_is_filled_from_config_every_year(self):
        # config.county is the input; the emit helper sets "Synthetic County".
        # Read the filled value back off the emitted PDF's county cell.
        from tests._blank_by_design import template_fields
        for year in CA_YEARS:
            with self.subTest(year=year):
                cells = {n: i for n, i in
                         template_fields(self.emits[year][0]["f540"]).items()
                         if "Enter your county" in i["tu"]}
                self.assertEqual(len(cells), 1, cells)
                self.assertEqual(
                    next(iter(cells.values()))["value"], "Synthetic County")

    def test_f540_full_year_coverage_box_is_checked_every_year(self):
        # config.full_year_health_care_coverage is the input; the emit helper
        # sets it True, so the box is marked rather than waived as blank.
        from tenforty.mappings.pdf_f540 import PdfF540
        from tests._blank_by_design import template_fields
        for year in CA_YEARS:
            with self.subTest(year=year):
                cell = PdfF540.get_mapping(year)["f540_full_year_coverage_checkbox"]
                for pdfs in self.emits[year]:
                    info = template_fields(pdfs["f540"])[cell]
                    self.assertIn("had full-year health care coverage, check the box", info["tu"])
                    self.assertEqual(info["value"], "/Yes")

    def test_f540_residence_same_box_is_checked_every_year(self):
        # config.address_is_principal_residence is the input; the emit helper
        # sets it True, so the box is marked rather than waived as blank.
        from tenforty.mappings.pdf_f540 import PdfF540
        from tests._blank_by_design import template_fields
        for year in CA_YEARS:
            with self.subTest(year=year):
                cell = PdfF540.get_mapping(year)["f540_address_is_residence_checkbox"]
                for pdfs in self.emits[year]:
                    info = template_fields(pdfs["f540"])[cell]
                    self.assertIn("same as your principal/physical residence", info["tu"])
                    self.assertEqual(info["value"], "/Yes")

    def test_f540_middle_initial_cell_is_filled_from_config_every_year(self):
        # config.middle_initial is the input; the emit helper sets "Q".
        from tenforty.mappings.pdf_f540 import PdfF540
        from tests._blank_by_design import template_fields
        for year in CA_YEARS:
            with self.subTest(year=year):
                cell = PdfF540.get_mapping(year)["f540_taxpayer_middle_initial"]
                for pdfs in self.emits[year]:
                    self.assertEqual(
                        template_fields(pdfs["f540"])[cell]["value"], "Q")

    def test_sch_d_540_every_blank_cell_is_documented_and_filled_set_is_pinned(self):
        for year in CA_YEARS:
            with self.subTest(year=year):
                self.assertNotIn("sch_d_540", self.emits[year][0])
                per_scenario = [unfilled(pdfs["sch_d_540"]) for pdfs in self.sch_d_emits[year]]
                blank = {n: i for n, i in per_scenario[0].items()
                         if all(n in r for r in per_scenario[1:])}
                bad, used = classify(blank, SCH_D_540_BLANK_BY_DESIGN)
                self.assertEqual(bad, [])
                # the filled cells are exactly the mapped ones (header + totals), nothing stray
                from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
                from tests._blank_by_design import template_fields
                filled = {n for n, i in template_fields(self.sch_d_emits[year][0]["sch_d_540"]).items()
                          if i["value"] is not None}
                mapped = set(PdfSchD540.get_mapping(year).values()) | set(
                    PdfSchD540.get_derivations(year))
                self.assertLessEqual(filled, mapped)
                self.assertGreaterEqual(len(filled), 2)

    def test_sch_ca_every_blank_cell_is_documented(self):
        """Blank = unfilled in the baseline emit AND in the rich all-catalog fill."""
        from tests.test_ca_sch_ca_completeness import FEDERAL, fill_sch_ca, rich_ca540
        import tempfile
        from pathlib import Path
        used_all = set()
        for year in CA_YEARS:
            with self.subTest(year=year):
                ca540, _ = rich_ca540(year)
                rich_pdf = fill_sch_ca(year, ca540, FEDERAL,
                                       Path(tempfile.mkdtemp()) / "rich.pdf")
                rich_blank = unfilled(rich_pdf)
                blank = {n: i for n, i in self._blank_cells(year, "sch_ca").items()
                         if n in rich_blank}
                bad, used = classify(blank, SCH_CA_BLANK_BY_DESIGN)
                used_all |= used
                self.assertEqual(bad, [], f"{year}: unclassified blank Sch CA cells")
        dead = [SCH_CA_BLANK_BY_DESIGN[i][0] for i in range(len(SCH_CA_BLANK_BY_DESIGN))
                if i not in used_all]
        self.assertEqual(dead, [])


if __name__ == "__main__":
    unittest.main()
