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
from tests._ca_emit_helpers import CA_YEARS, emit_ca, make_ca_scenario

SCENARIOS = (dict(), dict(state_tax_withheld=0.0))   # refund, amount owed

# ── Form 540 ────────────────────────────────────────────────────────────────
F540_BLANK_BY_DESIGN = [
    # Identity: no model input for these.
    (r"Middle Initial|Suffix", "no middle-initial / suffix input in the scenario"),
    (r"Spouse.*(SSN|S S N)|spouse.*first name|Spouse's.*Last name|Spouse.*Middle|Spouse.*Suffix",
     "spouse identity: single-filer scenario (fed from config.spouse_* when present; MFJ/MFS cannot "
     "emit through the workbook)"),
    (r"Spouse's.*Date of Birth", "no spouse birthdate input in the scenario"),
    (r"Prior Name|prior name", "no prior-name input"),
    (r"Additional information|Principal Business Activity|PBA|Private Mailbox|Apartment number",
     "no input for additional info / PBA code / PMB / apartment number"),
    (r"Foreign (country|province|postal)", "foreign address: scenario address is domestic"),
    (r"Principal Residence\. Enter your county",
     "NEEDS INPUT: the scenario has no county field (reported; not invented)"),
    (r"same as your principal/physical residence|Street address \(number and street\) \(If foreign|"
     r"^City\.$|^State\. Enter two letter|^Zip code\. $|Zip code\. *$",
     "principal-residence address block: only required when it differs from the mailing address"),
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
    (r"Line 92\.|Individual Shared Responsibility", "ISR penalty / full-year coverage box: not modeled"),
    (r"Line 98\.", "line 98 carryover to next-year estimated tax: not modeled"),
    (r"Code \d+\.|Contributions\. Code", "voluntary-contribution fund lines: only the line-110 total is modeled"),
    (r"Line 112\.|Interest and Penalties", "line 112 interest/penalties: not modeled"),
    (r"Line 113\. Underpayment of estimated tax\. Check the box",
     "FTB 5805 / 5805F attachment boxes: no Form 5805 modeled"),
    (r"Line 114\.", "KNOWN GAP (reported): line 114 total amount due has no compute key; line 111 "
     "already carries the balance due, so summing 111+112+113 here would need a semantics decision"),
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


class CAFormCompletenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.emits = {}
        for year in CA_YEARS:
            cls.emits[year] = [emit_ca(make_ca_scenario(year, **kw))[1] for kw in SCENARIOS]

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


if __name__ == "__main__":
    unittest.main()
