"""MFS capital-loss cap ($1,500) must reach the EMITTED 1040 line 7a.

WHAT THIS TEST DOES AND DOES NOT COVER — read before trusting a green run.

IRC §1211(b) caps the net capital loss deductible against ordinary income at
$3,000, but only $1,500 for married filing separately — exactly half. This
test drives a married-filing-separately filer with a loss well over that cap
through the REAL production entry points (``ReturnOrchestrator.compute_federal``
→ ``emit_pdfs``) and reads 1040 line 7a back out of the filled PDF.

ROUTING — THIS IS NOT THE NATIVE SPINE. tenforty's native 1040 spine is
single-filers-only: ``ReturnOrchestrator._scenario_in_spine_scope`` returns
False for any filing status other than ``FilingStatus.SINGLE``, and
``f1040_spine.compute_spine`` raises NotImplementedError if reached anyway. An
MFS scenario therefore routes to the XLSX WORKBOOK oracle path
(``_compute_1040_via_workbook``). For an MFS filer, the workbook *is*
production — there is no other path. That is why this test is oracle-marked
and needs LibreOffice.

CONSEQUENTLY, WHAT IS PINNED HERE IS:
  (a) the VENDOR WORKBOOK's own §1211(b) MFS cap (its Schedule D line 21 cell
      halves the cap off the ``File_Marr_Sep`` filing-status input), and
  (b) tenforty's OWN EMIT PLUMBING — the named-range → compute-key →
      PDF-field-path chain that has to carry that halved figure onto the form.
Part (b) is genuinely ours and was genuinely untested for this filer class.

WHAT IS **NOT** PINNED HERE: the NATIVE cap logic in ``sch_d.compute`` /
``f1040_spine.compute_income_preamble``. That code is UNREACHABLE for MFS BY
DESIGN — no MFS scenario can reach it while the spine is single-only. A green
run here says nothing whatsoever about a native MFS path, because no such path
exists. ``MFSCapTests`` in ``tests/test_capital_loss_cap_regression.py`` covers
the native cap arithmetic by calling the shared preamble function directly.
REVISIT THIS FILE when the native spine grows filing statuses: at that point
the scenario below starts routing native, ``test_mfs_scenario_routes_to_the_
workbook_not_the_native_spine`` fails as its designed signal, and this test
should be re-pointed at (or duplicated for) the native path.

WHY THE HARVEST IS NARROWED TO THE INCOME SECTION — DO NOT WIDEN IT.
There is a known PRE-EXISTING defect on the workbook path for every MFJ/MFS
return: tenforty has no spouse-birthdate concept, so the workbook's
``Birthday_Needed`` flag ('1040'!BI136) is unconditionally TRUE for those
statuses (BI143 = ``OR(SpouseBirthMonth="", ...)``, always true for us). The
workbook then REFUSES to compute the deduction-and-below section:
  * '1040'!AL91 (line 12, the deduction) short-circuits to 0 on Birthday_Needed;
  * the ``Deduction`` named range ('1040'!AU91) holds the literal diagnostic
    string "Birthdate(s) needed." instead of a label;
  * ``Tax_SubTotal`` ('1040'!AL96) evaluates to "" (blank) on Birthday_Needed,
    which the engine reads as None.
So ``total_deductions``, ``taxable_income`` and ``total_tax`` are all corrupt or
blank for an MFS return. Asserting on them would produce a confusing ERROR or a
meaningless wrong number that reads as harness breakage rather than a real
finding — and it is a DIFFERENT bug from the one this file is about.

Line 7a and ``total_income`` sit ABOVE that refusal point and are structurally
unaffected: '1040'!AL74 (line 7a / ``CapitalGains``) and '1040'!AL77
(``Total_Income``) contain no Birthday_Needed guard, and neither does the wages
chain feeding them (AL51/AL60). Verified by reading the 2025 workbook formulas.

THEREFORE: this file deliberately does NOT reuse ``PARITY_KEYS`` from
``tests/test_f1040_spine_oracle.py``. That constant contains ``taxable_income``,
``total_deductions`` and ``total_tax`` — every one of them at or below the
refusal line. Pointing this test at the shared constant would reawaken exactly
the trap described above. Keep the narrow, local key set.

STANDALONE BY NECESSITY: this scenario is deliberately NOT added to the spine
parity battery. ``tests/test_f1040_spine_oracle.py``'s routing guard asserts
that EVERY battery scenario routes to the native spine, on the grounds that a
fallback comparison would be workbook-vs-workbook and prove nothing. An MFS
scenario violates that guard by construction.

All identities and dollar figures are synthetic. The statutory $1,500 cap is
public law and is read from ``params.capital_loss_limit`` rather than hardcoded
as a test input.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf
import pytest

from tenforty.models import Form1099B, Scenario, TaxReturnConfig, W2
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params

from tests.helpers import REPO_ROOT, needs_libreoffice, scope_out_attestation_defaults

YEAR = 2025

# Synthetic scenario figures. WAGES clears nothing in particular (the EIC gate
# is moot — MFS is out of spine scope on filing status alone), and the LOSS is
# deliberately many multiples of the $1,500 cap so a capped result is
# unmistakably distinct from an uncapped one.
WAGES = 60_000.0
LOT_PROCEEDS = 50_000.0
LOT_LOSS = 8_000.0          # cost basis 58,000 → net long-term loss of 8,000
LOT_COST_BASIS = LOT_PROCEEDS + LOT_LOSS

# 2025 Form 1040 PDF field for line 7a (capital gain or loss). Hardcoded as a
# LITERAL rather than read back out of Pdf1040.get_mapping() on purpose: reading
# it from the mapping would make the assertion tautological (it would follow the
# mapping wherever the mapping went, including onto the wrong box). Verified
# against tenforty/mappings/pdf_1040.py's 2025 block, whose field numbering runs
# monotonically down the income section — f1_68 = line 6a (social_security),
# f1_69 = line 6b (social_security_taxable), f1_70 = line 7a (capital_gain_loss),
# f1_71 = line 7b (child_capital_gain). The positional sequence, not the comment,
# is the evidence.
_LINE_7A_FIELD = "topmostSubform[0].Page1[0].f1_70[0]"


def _mfs_cap() -> int:
    """The MFS §1211(b) cap, read from params — never hardcoded as an INPUT."""
    return load_federal_params(YEAR).capital_loss_limit["married_separately"]


def _mfs_scenario() -> Scenario:
    """MFS filer: one W-2 plus one long-term 1099-B lot sold at a loss.

    ``basis_reported_to_irs=True`` routes the lot straight onto Schedule D
    (box D) with no Form 8949 statement required — the same input shape the
    single-filer scenarios in tests/test_capital_loss_cap_regression.py and
    tests/fixtures/spine_battery.py use, so the only variable versus those is
    the filing status.
    """
    kwargs = scope_out_attestation_defaults()
    kwargs["prior_year_itemized"] = False
    config = TaxReturnConfig(
        year=YEAR,
        filing_status="married_separately",
        birthdate="1985-04-20",
        state="CA",
        first_name="Taxpayer",
        last_name="Sample",
        ssn="000-00-0000",
        **kwargs,
    )
    return Scenario(
        config=config,
        w2s=[W2(
            employer="Synthetic Employer",
            wages=WAGES,
            federal_tax_withheld=9_000.0,
            ss_wages=WAGES,
            ss_tax_withheld=3_720.0,
            medicare_wages=WAGES,
            medicare_tax_withheld=870.0,
        )],
        form1099_b=[Form1099B(
            broker="Synthetic Broker",
            description="Synthetic Lot",
            date_acquired=f"{YEAR - 3}-04-01",
            date_sold=f"{YEAR}-07-01",
            proceeds=LOT_PROCEEDS,
            cost_basis=LOT_COST_BASIS,
            short_term=False,
            basis_reported_to_irs=True,
        )],
    )


@needs_libreoffice
class MFSCapReachesEmittedPdfTests(unittest.TestCase):
    """The workbook path, end to end, for an MFS filer with an over-cap loss.

    Derivation. Cap (MFS, 2025) = $1,500. One long-term lot at an $8,000 loss,
    so Schedule D line 16 = -8,000 (the TRUE, uncapped net loss) and Schedule D
    line 21 = -MIN(8,000, 1,500) = -1,500 (the allowed loss, which is what
    Form 1040 line 7a carries per the line-21 instruction "If line 16 is a loss,
    enter here and on Form 1040 ... line 7a, the smaller of ..."). Total income
    = wages + allowed loss = 60,000 + (-1,500) = 58,500.

    -1,500 is the ONLY figure that proves both halves of the claim at once: that
    the filing status reached the cap logic at all, and that the emit plumbing
    carried the MFS-specific value. An assertion that merely checked "the loss
    is capped" or "line 7a > -8,000" would pass identically against a return
    that wrongly applied the single-filer $3,000 cap — which is precisely the
    defect this test exists to catch.
    """

    def _compute_and_emit(self):
        """Run the real production path and return (results, line-7a raw str).

        Uses ``compute_federal`` + ``emit_pdfs`` — the actual production entry
        points — rather than reaching into ``_compute_1040_via_workbook``
        directly, so the routing decision itself is exercised rather than
        assumed.
        """
        scenario = _mfs_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=tmp / "work",
            )
            results = orch.compute_federal(scenario)
            emitted = orch.emit_pdfs(scenario, results, tmp / "out")
            reader = pypdf.PdfReader(str(emitted["1040"]))
            fields = reader.get_fields() or {}
            raw = fields.get(_LINE_7A_FIELD, {}).get("/V")
        return results, raw

    @pytest.mark.oracle
    def test_mfs_capital_loss_limit_is_half_the_single_cap(self):
        """§1211(b): $3,000 generally, $1,500 married filing separately.

        Stated as its own assertion so this file DECLARES the halving rather
        than merely relying on it — every other assertion here reads the cap
        from params, so without this one nothing would pin what that value
        actually is. Fails if a params edit set the MFS entry to the
        single-filer $3,000 (or to anything else).

        Oracle-marked (like every test in this class) purely so the whole file
        stays in the LibreOffice-gated tier and the fast suite's pass count is
        untouched; this particular assertion needs no workbook.
        """
        params = load_federal_params(YEAR)
        self.assertEqual(params.capital_loss_limit["married_separately"], 1_500)
        self.assertEqual(
            params.capital_loss_limit["married_separately"] * 2,
            params.capital_loss_limit["single"],
            "MFS cap must be exactly half the single-filer cap",
        )

    @pytest.mark.oracle
    def test_mfs_scenario_routes_to_the_workbook_not_the_native_spine(self):
        """Premise check, and a tripwire for the day the spine grows statuses.

        The whole scope disclosure in this module's docstring depends on MFS
        being out of native-spine scope. Assert it rather than assume it. WHEN
        THIS FAILS: the native spine has been extended past single filers —
        that is the designed signal, not a regression. Re-point this file (or
        add a native sibling) at the now-reachable native cap path, and revisit
        the harvest narrowing below, which exists only because the WORKBOOK
        refuses MFS returns.
        """
        scenario = _mfs_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp) / "work",
            )
            effective, _ = orch._build_effective_scenario(scenario)
            self.assertFalse(
                orch._scenario_in_spine_scope(effective),
                "MFS scenario now routes to the NATIVE spine. If the spine "
                "was deliberately extended to more filing statuses, this is "
                "the designed signal: this file's scope disclosure and its "
                "income-section-only harvest are both stale and must be "
                "revisited.",
            )

    @pytest.mark.oracle
    def test_emitted_1040_line_7a_is_the_halved_mfs_cap(self):
        """THE CENTRAL ASSERTION: 1040 line 7a on the filled PDF == -1,500.

        Reads the ACTUAL filled PDF field, so it exercises the full
        compute-key → PDF-field-path transformation, not just the compute dict.
        Compared numerically (via int()) rather than against a rendered string,
        because the workbook path yields floats where the native path yields
        ints; PdfFiller._render_scalar irs_round()s both, but the assertion
        should be about the VALUE, not about which numeric type happened to
        arrive.
        """
        cap = _mfs_cap()
        _results, raw = self._compute_and_emit()
        self.assertIsNotNone(
            raw,
            f"1040 line 7a field {_LINE_7A_FIELD} was not filled at all — an "
            f"MFS return with a capital loss must render a line 7a.",
        )
        self.assertEqual(
            int(raw), -cap,
            f"1040 line 7a rendered {raw!r}; expected {-cap} — the §1211(b) "
            f"MFS cap. -3000 here would mean the single-filer cap was applied "
            f"(the filing status never reached the cap logic); "
            f"-{int(LOT_LOSS)} would mean no cap was applied at all and the "
            f"raw Schedule D line 16 total reached line 7a.",
        )

    @pytest.mark.oracle
    def test_compute_capital_gain_loss_is_the_halved_mfs_cap(self):
        """Same quantity one layer earlier, to localise a failure.

        If this passes while the PDF assertion above fails, the defect is in
        the EMIT plumbing (compute key → PDF field). If both fail, the capped
        figure never made it out of the compute path in the first place. Kept
        as a separate test method (not a second assert in the PDF test) so the
        two report independently.
        """
        cap = _mfs_cap()
        results, _raw = self._compute_and_emit()
        self.assertEqual(results["capital_gain_loss"], -cap)

    @pytest.mark.oracle
    def test_total_income_is_wages_minus_the_halved_cap(self):
        """Total income (1040 line 9) = wages + the ALLOWED loss, not the full
        loss and not the single-filer-capped loss.

        58,500 is distinct from both figures a wrong branch would produce: the
        single/MFJ $3,000 cap gives 57,000, and an uncapped full loss gives
        52,000. Total income is the last line ABOVE the workbook's MFS
        birthdate refusal, so it is safe to assert; everything below it
        (deductions, taxable income, total tax) is not — see the module
        docstring.
        """
        cap = _mfs_cap()
        results, _raw = self._compute_and_emit()
        self.assertEqual(results["total_income"], WAGES - cap)  # 58,500

    @pytest.mark.oracle
    def test_schedule_d_line_16_stays_the_true_uncapped_loss(self):
        """Schedule D line 16 is the TRUE net loss (-8,000) even though line 7a
        carries the capped figure. The two lines hold DIFFERENT numbers, and
        that is correct: line 16 is the year's actual net capital result, line
        21/7a is the portion §1211(b) lets you deduct this year. A "tidy-up"
        that aligned them — in either direction — would be introducing a bug.

        This mirrors ``Line16UncappedTests`` in
        ``tests/test_capital_loss_cap_regression.py``, which pins the same
        invariant on the native single-filer path.
        """
        cap = _mfs_cap()
        results, _raw = self._compute_and_emit()
        self.assertEqual(results["schd_line16"], -LOT_LOSS)      # -8,000, true
        self.assertEqual(results["capital_gain_loss"], -cap)     # -1,500, capped


if __name__ == "__main__":
    unittest.main()
