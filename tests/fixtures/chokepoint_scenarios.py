# tests/fixtures/chokepoint_scenarios.py
"""Synthetic emit cases for the fill-chokepoint lane (emit-verification
harness plan, Track B).

Each case runs one public emit entry point on one synthetic scenario into an
output directory. Together they reach all nine PdfFiller call sites in
``orchestrator.py`` (3115; the federal flat and repeater specs; 1120-S and its
K-1; the CA 540 loop incl. FTB 3532; 100S and its K-1; 1040-X / Schedule X).

``snapshot(output_dir)`` reduces every emitted PDF to its sha256 plus its
``(name, /V, /AS)`` field triples. ``tests/fixtures/chokepoint_before/`` holds
the snapshots captured from the tree BEFORE the chokepoint reroute; the
byte-identical test compares a fresh run against them. Never PDFs, never
real data: every identity here is synthetic.

Every case runs native: the workbook path is patched to raise, so no case
can reach LibreOffice.
"""
import dataclasses
import hashlib
import json
import tempfile
import unittest.mock
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.forms import f1040x as form_f1040x
from tenforty.models import (
    AmendmentCase,
    Form1099B,
    CA540Return,
    FilingStatus,
    Form1099INT,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    SCorpCAInputs,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests import _audit_workbook_fixtures as audit_fx
from tests import _f3115_fixtures as f3115_fx
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.fixtures import sch_c_battery
from tests.fixtures.spine_battery import (
    build_addl_medicare_boundary,
    build_canonical_wage_investment_rental,
    build_ptc_net_credit,
    build_qbi_k1_deduction,
    build_wages_only,
)
from tests.helpers import CA_SCOPE_OUT_FIELDS, REPO_ROOT

BEFORE_DIR = REPO_ROOT / "tests" / "fixtures" / "chokepoint_before"


def native_orchestrator(work_dir: Path) -> ReturnOrchestrator:
    return ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                              work_dir=work_dir)


def no_workbook():
    """Patch the workbook path to raise: these cases are native-only."""
    return unittest.mock.patch.object(
        ReturnOrchestrator, "_compute_1040_via_workbook",
        side_effect=AssertionError("workbook path reached in a native case"))


def _with_ca(scenario):
    cfg = dataclasses.replace(
        scenario.config, full_year_health_care_coverage=True,
        **{k: True for k in CA_SCOPE_OUT_FIELDS})
    return dataclasses.replace(
        scenario, config=cfg, ca540=CA540Return(interest_and_penalties=0.0))


def _ca_yaml(tmp: Path) -> Path:
    path = tmp / "scenario.ca.yaml"
    path.write_text(yaml.safe_dump({"ca540": {"interest_and_penalties": 0.0}}))
    return path


# --- the cases: name -> (entry point, runner(orch, out) -> return value) ---

def _emit_pdfs_canonical(orch, out):
    scenario = build_canonical_wage_investment_rental(2024)
    return orch.emit_pdfs(scenario, orch.compute_federal(scenario), out)


def _run_full_return_sch_c(orch, out):
    return orch.run_full_return(sch_c_battery.build("qbi-interplay", 2025), out)


def _run_full_return_ptc(orch, out):
    return orch.run_full_return(build_ptc_net_credit(2024), out)


def _run_full_return_qbi_k1(orch, out):
    return orch.run_full_return(build_qbi_k1_deduction(2024), out)


def _run_full_return_f3115(orch, out):
    src = out.parent / "f3115_src"
    src.mkdir(parents=True, exist_ok=True)
    scenario = f3115_fx.load(src, f3115_fx.scenario_dict())
    return orch.run_full_return(scenario, out)


def _run_full_return_f8949(orch, out):
    """The canonical return plus one lot whose basis was not reported to the
    IRS (box B), so Form 8949 prints."""
    base = build_canonical_wage_investment_rental(2024)
    lot = Form1099B(broker="Synthetic Broker", description="10 sh EXAMPLE",
                    date_acquired="2024-02-01", date_sold="2024-09-15",
                    proceeds=4_000.0, cost_basis=3_100.0, short_term=True,
                    basis_reported_to_irs=False)
    scenario = dataclasses.replace(
        base, form1099_b=[*base.form1099_b, lot])
    return orch.run_full_return(scenario, out)


def _run_full_return_f8959(orch, out):
    return orch.run_full_return(build_addl_medicare_boundary(2024), out)


def _run_full_return_f4562(orch, out):
    return orch.run_full_return(audit_fx.scenario(), out)


def _hoh_ca_scenario(year: int):
    base = build_wages_only(year, FilingStatus.HEAD_OF_HOUSEHOLD)
    qp = HohQualifyingPerson(
        first_name="Example", last_name="Child", ssn="000000005",
        birthdate=f"{year - 10}-03-07",
        relationship=HohRelationship.CHILD_OR_STEPCHILD,
        full_time_student=None, permanently_disabled=None,
        gross_income=0.0, days_lived_with_you=365,
        claimed_as_dependent=False)
    facts = HeadOfHouseholdFacts(marital_status=HohMaritalStatus.UNMARRIED,
                                 qualifying_person=qp)
    scenario = _with_ca(dataclasses.replace(
        base, config=dataclasses.replace(base.config,
                                         head_of_household=facts)))
    return dataclasses.replace(scenario, ca540=None)


def _run_full_california_return_hoh(orch, out):
    out.mkdir(parents=True, exist_ok=True)
    return orch.run_full_california_return(
        scenario=_hoh_ca_scenario(2025), ca_yaml_path=_ca_yaml(out.parent),
        output_dir=out)


def _run_amendment_packet(orch, out):
    year = 2024
    original = _with_ca(build_canonical_wage_investment_rental(year))
    amended = dataclasses.replace(original, form1099_int=[
        Form1099INT(payer="Synthetic Bank", interest=3_000.0)])
    work = out.parent / "amend_src"
    work.mkdir(parents=True, exist_ok=True)
    orig_fed = orch.compute_federal(original)
    filed = work / "federal_filed.yaml"
    filed.write_text(yaml.safe_dump(
        {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
    orig_ca = orch._compute_ca_results(original, original.ca540, orig_fed)
    ca_filed = work / "ca_filed.yaml"
    ca_filed.write_text(yaml.safe_dump(
        {"f540_total_liability": orig_ca["f540_total_liability"]}))
    case = AmendmentCase(
        year=year, explanation="Corrected taxable interest income.",
        original_refund_received=0.0, original_refund_applied=0.0,
        original_tax_paid=0.0,
        ca_original_refund_received=max(0.0, -orig_ca["f540_total_liability"]),
        ca_original_refund_applied=0.0)
    return orch.run_amendment_packet(original, amended, case, filed, ca_filed,
                                     out)


def _scorp_scenario(year: int):
    s = _make_v1_scenario()
    set_tax_year(s, year)
    r = s.s_corp_return
    r.amended_return = True
    r.discuss_with_preparer = True
    r.electing_s_this_year = False
    r.name_change = True
    r.address_change = True
    r.shareholders[0].final_k1 = True
    return s


def _run_full_federal_scorp_return(orch, out):
    return orch.run_full_federal_scorp_return(_scorp_scenario(2025), out)


def _run_full_california_scorp_return(orch, out):
    s = _scorp_scenario(2025)
    # The 100S K-1 holds "final" and "amended" as two states of one radio
    # (the emit refuses both at once): this case is final, not amended, and
    # states the K-1's entity-type and resident answers.
    s.s_corp_return.amended_return = False
    s.s_corp_return.shareholders[0].ca_resident = True
    s.s_corp_return.shareholders[0].ca_entity_type = "individual"
    s.s_corp_return.ca = SCorpCAInputs(
        first_year=False, estimated_tax_payments=0.0,
        prior_year_overpayment_applied=0.0,
        state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
        apportionment_ca_only=True, discuss_with_preparer=True)
    return orch.run_full_california_scorp_return(s, out)


CASES = {
    "emit_pdfs_canonical_2024": ("emit_pdfs", _emit_pdfs_canonical),
    "run_full_return_sch_c_2025": ("run_full_return", _run_full_return_sch_c),
    "run_full_return_ptc_2024": ("run_full_return", _run_full_return_ptc),
    "run_full_return_qbi_k1_2024": ("run_full_return", _run_full_return_qbi_k1),
    "run_full_return_f3115_2025": ("run_full_return", _run_full_return_f3115),
    "run_full_return_f8949_2024": ("run_full_return", _run_full_return_f8949),
    "run_full_return_f8959_2024": ("run_full_return", _run_full_return_f8959),
    "run_full_return_f4562_2025": ("run_full_return", _run_full_return_f4562),
    "run_full_california_return_hoh_2025": (
        "run_full_california_return", _run_full_california_return_hoh),
    "run_amendment_packet_2024": ("run_amendment_packet",
                                  _run_amendment_packet),
    "run_full_federal_scorp_return_2025": (
        "run_full_federal_scorp_return", _run_full_federal_scorp_return),
    "run_full_california_scorp_return_2025": (
        "run_full_california_scorp_return", _run_full_california_scorp_return),
}


def run_case(name: str, root: Path):
    """Run one case under ``root``; returns (return value, output dir)."""
    _entry, runner = CASES[name]
    out = root / name / "out"
    out.parent.mkdir(parents=True, exist_ok=True)
    orch = native_orchestrator(root / name / "work")
    with no_workbook():
        ret = runner(orch, out)
    return ret, out


def _field_triples(pdf: Path) -> list[list[str]]:
    fields = PdfReader(str(pdf)).get_fields() or {}
    return sorted([name, str(f.get("/V")) if f.get("/V") is not None else "",
                   str(f.get("/AS")) if f.get("/AS") is not None else ""]
                  for name, f in fields.items())


def snapshot(out: Path) -> dict:
    """{pdf file name: {sha256, fields}} for every PDF in ``out``."""
    return {
        pdf.name: {
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "fields": _field_triples(pdf),
        }
        for pdf in sorted(out.glob("*.pdf"))
    }


def capture_before() -> list[Path]:
    """Write one before-snapshot JSON per case (run on the untouched tree)."""
    BEFORE_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory() as td:
        for name in CASES:
            _ret, out = run_case(name, Path(td))
            path = BEFORE_DIR / f"{name}.json"
            path.write_text(json.dumps(snapshot(out), indent=1, sort_keys=True)
                            + "\n")
            written.append(path)
    return written


def load_before(name: str) -> dict:
    return json.loads((BEFORE_DIR / f"{name}.json").read_text())
