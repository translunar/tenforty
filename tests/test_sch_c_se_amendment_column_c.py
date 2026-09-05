# tests/test_sch_c_se_amendment_column_c.py
# Mirrors tests/test_se_health_amendment_column_c.py (real recompute for the
# carry-through case) + direct-dict unit tests for the reconciliation guard.
import dataclasses, tempfile, unittest
from pathlib import Path
from tenforty.forms import f1040x as form_f1040x
from tenforty.forms.f1040x import OutOfScopeAmendmentError, REQUIRED_FILED_KEYS
from tenforty.models import AmendmentCase, ScheduleCBusiness
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental
from tests.helpers import REPO_ROOT


def _with_business(scenario, receipts, expenses=0.0):
    """Twin carrying one Schedule C business; QBI-ack so a high-income fixture
    doesn't trip the Form 8995 over-threshold gate (QBI is not what this tests)."""
    cfg = dataclasses.replace(scenario.config, acknowledges_qbi_below_threshold=True)
    biz = ScheduleCBusiness(description="reclassified", gross_receipts=receipts,
                            supplies=expenses)
    return dataclasses.replace(scenario, config=cfg, schedule_c_businesses=[biz])


def _case():
    return AmendmentCase(year=2024, explanation="Reclassified K-1 income to Schedule C.",
                         original_refund_received=0.0, original_refund_applied=0.0)


# Minimal filed/corrected dicts for the reconciliation guard (pure dict logic —
# assemble() operates on dicts, so no compute is needed to exercise the guard).
def _min_dict(**over):
    d = {"agi": 100_000, "total_deductions": 14_600, "_qbi_deduction_1040": 0,
         "taxable_income": 85_400, "total_tax": 14_000, "federal_withheld": 10_000,
         "total_payments": 10_000}
    d.update(over)
    return d


class SchCSeAmendmentCarryThroughTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")
    def tearDown(self):
        self._tmp.cleanup()
    def _filed_from(self, scenario):
        results = self.orch.compute_federal(scenario)
        return {k: results[k] for k in REQUIRED_FILED_KEYS}   # excludes component keys

    def test_se_tax_carries_into_column_c_not_column_a(self):
        # Motivating case: as-filed had NO Schedule C (SE tax 0, and the
        # component keys aren't in REQUIRED_FILED_KEYS → Column A = 0); the
        # amended scenario adds a Schedule C → SE tax appears in Column C only.
        base = build_canonical_wage_investment_rental(2024)   # single filer
        filed = self._filed_from(base)                        # no business as filed
        corrected = self.orch.compute_federal(_with_business(base, 80_000.0, 5_000.0))
        self.assertGreater(corrected["sch_se_line_12_se_tax"], 0)
        out = form_f1040x.assemble(filed, corrected, _case())
        self.assertEqual(out["f1040x_line10_a"], 0)
        self.assertEqual(out["f1040x_line10_c"], corrected["other_taxes"])
        self.assertEqual(out["f1040x_line10_b"], corrected["other_taxes"])

    def test_line6_excludes_se_tax(self):
        # 1040-X line 6 is the LINE-16 base (+ Sch 2 Part I); SE tax is line 10,
        # never line 6. Guards the line-16-vs-23 conflation history.
        base = build_canonical_wage_investment_rental(2024)
        filed = self._filed_from(base)
        corrected = self.orch.compute_federal(_with_business(base, 80_000.0, 5_000.0))
        out = form_f1040x.assemble(filed, corrected, _case())
        self.assertEqual(out["f1040x_line6_c"],
                         corrected["total_tax"] + corrected.get("f8962_repayment", 0.0))


class SchCSeAmendmentReconciliationTests(unittest.TestCase):
    def test_reconciliation_refuses_unaccounted_other_taxes(self):
        # Filed declares other_taxes 5,000 but modeled components sum to 1,000
        # (e.g. an unmodeled NIIT of 4,000) → refuse; don't silently adopt.
        filed = _min_dict(other_taxes=5_000, f8959_tax_total=1_000, sch_se_line_12_se_tax=0)
        corrected = _min_dict(f8959_tax_total=1_000, sch_se_line_12_se_tax=0)
        with self.assertRaises(OutOfScopeAmendmentError):
            form_f1040x.assemble(filed, corrected, _case())

    def test_reconciliation_refuses_declared_below_modeled(self):
        # BELOW direction (either-direction guard): filed DECLARES other_taxes 0
        # while its own modeled components sum to 800 → just as unaccountable as
        # the above direction → refuse, message naming both figures. (declared=0
        # is an EXPLICIT key, distinct from the legacy no-key case below.)
        filed = _min_dict(other_taxes=0, f8959_tax_total=800, sch_se_line_12_se_tax=0)
        corrected = _min_dict(f8959_tax_total=800, sch_se_line_12_se_tax=0)
        with self.assertRaises(OutOfScopeAmendmentError):
            form_f1040x.assemble(filed, corrected, _case())

    def test_reconciliation_passes_when_declared_equals_modeled(self):
        # Declared other_taxes 1,000 == modeled f8959 1,000 → proceeds; line 10
        # Column A is the modeled total.
        filed = _min_dict(other_taxes=1_000, f8959_tax_total=1_000, sch_se_line_12_se_tax=0)
        corrected = _min_dict(f8959_tax_total=1_000, sch_se_line_12_se_tax=0)
        out = form_f1040x.assemble(filed, corrected, _case())   # no raise
        self.assertEqual(out["f1040x_line10_a"], 1_000)

    def test_legacy_filed_without_other_taxes_key_unchanged(self):
        # Legacy filed dict: no declared other_taxes → reconciliation skipped;
        # line 10 Column A is the modeled sum (here f8959 only). Backward compatible.
        filed = _min_dict(f8959_tax_total=800)   # no other_taxes / se_tax keys
        corrected = _min_dict(f8959_tax_total=800)
        out = form_f1040x.assemble(filed, corrected, _case())
        self.assertEqual(out["f1040x_line10_a"], 800)
