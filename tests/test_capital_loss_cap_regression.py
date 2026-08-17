"""Regression coverage for the IRC §1211(b) capital-loss cap fix (51c6570).

Pre-fix, ``tenforty/forms/f1040_spine.py`` fed the TRUE, uncapped Schedule D
line 16 total straight into 1040 total_income. IRC §1211(b) caps the net
capital LOSS deductible against ordinary income at $3,000 ($1,500 married
filing separately); the excess carries forward under §1212(b). A filer with
a $50,000 loss therefore had total_income UNDERSTATED by $47,000 relative to
the correct, capped figure — a severe understatement of tax, not a rounding
error.

``tests/test_sch_d_capital_loss_limit.py`` already pins the cap arithmetic
INSIDE Schedule D (``sch_d.compute``'s ``sch_d_line_21_allowed_loss``) in
isolation. What no test anywhere else in the repo exercised is the WIRING
from that allowed figure into 1040 total_income (``f1040_spine.py``'s
``total_income = wages + ... + schd_line21_allowed + ...``) and onward into
the emitted 1040 PDF — which is exactly where the pre-fix defect lived. Every
class below drives that wiring through the real production entry points
(``ReturnOrchestrator._compute_1040_pipeline`` / ``compute_income_preamble``
/ the PDF emit path), never by re-deriving the answer from the code under
test.

All identities and dollar amounts are synthetic/generic. Statutory cap
figures ($3,000 / $1,500) are public law, read from
``params.capital_loss_limit`` rather than hardcoded as test inputs.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.forms import f1040_spine, sch_d
from tenforty.models import Form1099B, K1FanoutData, Scenario, TaxReturnConfig, W2
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params

from tests.fixtures.spine_battery import build_capital_loss_over_cap
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

YEAR = 2025

# 2025 Form 1040 field for line 7a (capital gain/loss) — see
# tenforty/mappings/pdf_1040.py's 2025 block and
# tests/test_pdf_1040_fill.py, which pins this same field to the same
# translation key ("capital_gain_loss").
_LINE_7A_FIELD = "topmostSubform[0].Page1[0].f1_70[0]"


def _cap(filing_status: str = "single") -> int:
    # Read the cap from params — never hardcode 3000/1500 as a test INPUT.
    return load_federal_params(YEAR).capital_loss_limit[filing_status]


def _config(filing_status: str = "single", **overrides) -> TaxReturnConfig:
    kw = scope_out_attestation_defaults()
    kw["prior_year_itemized"] = False
    kw.update(overrides)
    return TaxReturnConfig(
        year=YEAR, filing_status=filing_status,
        birthdate="1985-04-20", state="CA",
        first_name="Taxpayer", last_name="Regress", ssn="000-00-0000",
        **kw,
    )


def _lt_lot_scenario(wages: float, loss_or_gain: float,
                      filing_status: str = "single") -> Scenario:
    """Single W-2 + a single long-term 1099-B lot whose net proceeds minus
    basis equals ``loss_or_gain`` exactly (negative = loss, positive =
    gain). ``basis_reported_to_irs=True`` routes it straight onto Schedule D
    (no Form 8949 statement required), matching
    ``tests/fixtures/spine_battery.py``'s ``build_capital_loss_over_cap``
    pattern. Wages alone (>= the 2025 0-dependent EIC ceiling of $26,214)
    are enough to clear ``_scenario_in_spine_scope``'s EIC gate and route to
    the native spine, regardless of the lot's sign.
    """
    proceeds = 50_000.0
    cost_basis = proceeds - loss_or_gain
    return Scenario(
        config=_config(filing_status),
        w2s=[W2(
            employer="Synthetic Employer", wages=wages,
            federal_tax_withheld=wages * 0.15,
            ss_wages=wages, ss_tax_withheld=wages * 0.062,
            medicare_wages=wages, medicare_tax_withheld=wages * 0.0145,
        )],
        form1099_b=[Form1099B(
            broker="Synthetic Broker", description="Synthetic Lot",
            date_acquired=f"{YEAR - 3}-04-01", date_sold=f"{YEAR}-07-01",
            proceeds=proceeds, cost_basis=cost_basis,
            short_term=False, basis_reported_to_irs=True,
        )],
    )


def _pipeline_results(scenario: Scenario) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp) / "work",
        )
        return orch._compute_1040_pipeline(scenario)


class EndToEndCappedLossTests(unittest.TestCase):
    """The full pipeline, on the exact scenario the team-lead's oracle-parity
    gate flagged as diverging in all five supported years: wages $130,000,
    ONE long-term 1099-B lot sold at a $50,000 loss (proceeds $20,000
    against a $70,000 basis), single filer, 2025
    (``build_capital_loss_over_cap``).

    Derivation: cap (single, 2025) = $3,000. total_income = wages +
    max(loss, -cap) = 130,000 + (-3,000) = 127,000. PRE-FIX, total_income
    used the uncapped line 16 directly: 130,000 + (-50,000) = 80,000 — a
    $47,000 understatement of income (and therefore tax). schd_line16 is
    the TRUE Schedule D total: -50,000 (see Line16UncappedTests — that
    figure stays uncapped by design). net_capital_gain =
    max(0, min(line 15, line 16)) = max(0, min(-50000, -50000)) = 0 (an
    all-loss year has no preferential-rate capital gain).
    """

    def test_total_income_is_wages_minus_the_cap_not_wages_minus_the_loss(self):
        scenario = build_capital_loss_over_cap(YEAR)
        cap = _cap("single")
        wages = 130_000
        results = _pipeline_results(scenario)
        self.assertEqual(results["total_income"], wages - cap)  # 127,000
        # The pre-fix value, stated explicitly so a reader sees the defect's
        # shape: wages - the FULL loss = 130,000 - 50,000 = 80,000.
        self.assertNotEqual(results["total_income"], wages - 50_000)

    def test_capital_gain_loss_line_7a_is_the_capped_allowed_loss(self):
        scenario = build_capital_loss_over_cap(YEAR)
        cap = _cap("single")
        results = _pipeline_results(scenario)
        self.assertEqual(results["capital_gain_loss"], -cap)  # -3,000

    def test_net_capital_gain_is_zero_for_an_all_loss_year(self):
        scenario = build_capital_loss_over_cap(YEAR)
        results = _pipeline_results(scenario)
        self.assertEqual(results["net_capital_gain"], 0)


class BoundaryPairTests(unittest.TestCase):
    """The single most important assertion class in this file: a loss just
    UNDER the cap must be FULLY allowed, one just AT the cap must also be
    fully allowed, and one just OVER must be capped. A single large-loss
    test (EndToEndCappedLossTests) cannot distinguish a correct
    ``max(line_16, -cap)`` from an INVERTED comparison — both produce the
    same answer once the loss is many multiples of the cap. Only a
    boundary pair one dollar on either side of the cap forces the sign
    convention to be exercised correctly: inverting it would flip which
    side of the pair gets capped.

    Wages $50,000 (>= the $26,214 0-dependent EIC ceiling, so all three
    scenarios route to the native spine), single filer 2025, cap = $3,000.
    total_income = wages + allowed_loss for each case, derived below.
    """

    def test_loss_one_dollar_under_cap_fully_allowed(self):
        cap = _cap("single")
        wages = 50_000
        scenario = _lt_lot_scenario(wages, -(cap - 1))  # -2,999
        results = _pipeline_results(scenario)
        self.assertEqual(results["capital_gain_loss"], -(cap - 1))
        self.assertEqual(results["total_income"], wages - (cap - 1))  # 47,001

    def test_loss_exactly_at_cap_fully_allowed(self):
        cap = _cap("single")
        wages = 50_000
        scenario = _lt_lot_scenario(wages, -cap)  # -3,000
        results = _pipeline_results(scenario)
        self.assertEqual(results["capital_gain_loss"], -cap)
        self.assertEqual(results["total_income"], wages - cap)  # 47,000

    def test_loss_one_dollar_over_cap_is_capped(self):
        cap = _cap("single")
        wages = 50_000
        scenario = _lt_lot_scenario(wages, -(cap + 1))  # -3,001
        results = _pipeline_results(scenario)
        # Smaller-in-MAGNITUDE of 3,001 and 3,000 is 3,000: capped, NOT the
        # full -3,001. An inverted comparison would instead let -3,001
        # through untouched (matching the under-cap case's total_income)
        # while wrongly capping the under-cap case above — this pair
        # catches either direction of the inversion.
        self.assertEqual(results["capital_gain_loss"], -cap)
        self.assertEqual(results["total_income"], wages - cap)  # 47,000
        # And it must differ from the just-under-cap case by exactly $1 of
        # allowed loss (2,999 vs 3,000 capped), i.e. total_income must NOT
        # equal wages - 3,001.
        self.assertNotEqual(results["total_income"], wages - (cap + 1))


class MFSCapTests(unittest.TestCase):
    """Married-filing-separately caps at $1,500, half the single/MFJ figure
    — pins the filing-status branch through the real production wiring
    (``sch_d.compute`` -> ``f1040_spine.compute_income_preamble``), not only
    ``TestLine21Cap.test_mfs_filing_status_branch`` in
    ``test_sch_d_capital_loss_limit.py``, which exercises ``sch_d.compute``
    alone.

    NOTE: ``ReturnOrchestrator._compute_1040_pipeline`` routes non-single
    filers to the XLSX oracle path (``_scenario_in_spine_scope`` requires
    ``FilingStatus.SINGLE``; ``compute_spine`` itself raises
    NotImplementedError for any other status), and that oracle path
    requires LibreOffice, which this unit may not invoke. So this test
    calls the actual shared preamble function the native spine's
    ``compute_spine`` delegates to (``compute_income_preamble`` — see its
    docstring: "Called from both the orchestrator's f8995/f8582 pre-pass
    ... and compute_spine") directly, feeding it a REAL ``sch_d.compute``
    result for an MFS scenario. This is the maximal "real pipeline" reach
    available for a non-single filing status in the current codebase.

    Derivation: cap (MFS, 2025) = $1,500. Wages $60,000, one long-term lot
    at an $8,000 loss (proceeds $50,000, basis $58,000). schd_line16 =
    -8,000; schd_line21_allowed = max(-8,000, -1,500) = -1,500.
    total_income = 60,000 + (-1,500) = 58,500.
    """

    def test_mfs_total_income_capped_at_1500_not_3000_or_the_full_loss(self):
        cap = _cap("married_separately")
        self.assertEqual(cap, 1_500)
        wages = 60_000.0
        scenario = Scenario(
            config=_config("married_separately"),
            w2s=[W2(
                employer="Synthetic Employer", wages=wages,
                federal_tax_withheld=9_000.0,
                ss_wages=wages, ss_tax_withheld=3_720.0,
                medicare_wages=wages, medicare_tax_withheld=870.0,
            )],
        )
        fanout = K1FanoutData(
            sch_b_interest_additions=(), sch_b_dividend_additions=(),
            sch_d_short_term_additions=(), sch_d_long_term_additions=(-8_000.0,),
            qbi_aggregate=0.0, qualified_dividends_aggregate=0.0,
            passive_activities=(),
        )
        sch_d_results = sch_d.compute(scenario, upstream={"k1_fanout": fanout})
        self.assertEqual(sch_d_results["sch_d_line_16_total"], -8_000)
        self.assertEqual(sch_d_results["sch_d_line_21_allowed_loss"], -1_500)

        params = load_federal_params(YEAR)
        preamble = f1040_spine.compute_income_preamble(
            scenario, params, {"sch_d": sch_d_results}, k1_fanout=fanout,
        )
        self.assertEqual(preamble.total_income, 58_500)
        # Not the single/MFJ $3,000 cap's figure (57,000), and not the
        # uncapped full loss (52,000).
        self.assertNotEqual(preamble.total_income, wages - 3_000)
        self.assertNotEqual(preamble.total_income, wages - 8_000)


class Line16UncappedTests(unittest.TestCase):
    """Schedule D line 16 must stay the TRUE, uncapped net loss even while
    1040 line 7a carries the capped figure — this is a deliberate,
    team-lead-confirmed ruling ("schd_line16 stays UNCAPPED... That IS
    Schedule D line 16 on the form"). A future "tidy-up" that made line 16
    match line 7a (or vice versa) would be introducing a bug; this test
    exists to catch exactly that.
    """

    def test_schd_line16_uncapped_while_capital_gain_loss_is_capped(self):
        scenario = build_capital_loss_over_cap(YEAR)
        cap = _cap("single")
        results = _pipeline_results(scenario)
        self.assertEqual(results["schd_line16"], -50_000)   # TRUE, uncapped
        self.assertEqual(results["capital_gain_loss"], -cap)  # -3,000, capped
        self.assertNotEqual(results["schd_line16"], results["capital_gain_loss"])


class CrossPathEmitTests(unittest.TestCase):
    """A prior unit in this program shipped a regression because its tests
    drove only the COMPUTE path and never the EMIT path (standing program
    policy: always add a cross-path assertion). This class builds the
    upstream exactly the way ``_federal_individual_emit_specs`` does
    (``results = orch._compute_1040_pipeline(s)``, then the emit-path
    construction) and reads the ACTUAL FILLED 1040 PDF field back with
    pypdf — a real additional transformation layer (compute-result key name
    -> PDF field path) that a spec-inspection assertion alone would not
    exercise. No LibreOffice is required: PDF form-filling uses pypdf
    directly (see ``tests/test_f1040_line12_emit.py``'s identical,
    non-oracle idiom); only the XLSX workbook oracle path needs it, and
    this scenario (single filer, wages clear the EIC gate) never reaches
    that path.

    Expected field value: str(irs_round(-3,000)) == "-3000" (PdfFiller
    str()-coerces the value it writes; see ``tenforty/filing/pdf.py``).
    """

    def test_emitted_1040_line_7a_equals_the_capped_allowed_loss(self):
        scenario = build_capital_loss_over_cap(YEAR)
        cap = _cap("single")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=tmp / "work",
            )
            results = orch._compute_1040_pipeline(scenario)
            self.assertEqual(results["capital_gain_loss"], -cap)
            emitted = orch.emit_pdfs(scenario, results, tmp / "out")
            reader = pypdf.PdfReader(str(emitted["1040"]))
            fields = reader.get_fields() or {}
            raw = fields.get(_LINE_7A_FIELD, {}).get("/V")
            self.assertEqual(raw, str(-cap))  # "-3000"


class GainYearUnaffectedTests(unittest.TestCase):
    """A net capital GAIN year must be entirely unaffected by the cap — it
    only ever limits a LOSS. This catches an over-eager implementation that
    also clamps gains (e.g. a naive ``min`` instead of ``max``, or a cap
    applied without a loss guard).

    Wages $100,000, one long-term lot at a $10,000 GAIN (proceeds $60,000,
    basis $50,000), single filer 2025. Schedule D line 16 = +10,000 (a
    gain, not a loss — §1211(b) never applies): schd_line21_allowed equals
    schd_line16 unchanged (see ``TestLine21Cap.test_net_gain_passes_
    through_untouched`` in test_sch_d_capital_loss_limit.py — the gain
    branch is untouched by the cap). total_income = 100,000 + 10,000 =
    110,000. net_capital_gain = max(0, min(line 15, line 16)) =
    max(0, min(10000, 10000)) = 10,000.
    """

    def test_gain_year_total_income_and_capital_gain_loss_unaffected(self):
        wages = 100_000
        scenario = _lt_lot_scenario(wages, 10_000.0)
        results = _pipeline_results(scenario)
        self.assertEqual(results["schd_line16"], 10_000)
        self.assertEqual(results["capital_gain_loss"], 10_000)
        self.assertEqual(results["total_income"], 110_000)
        self.assertEqual(results["net_capital_gain"], 10_000)


if __name__ == "__main__":
    unittest.main()
