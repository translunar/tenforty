"""ORACLE-ONLY EIC-answer adapter (childless-EITC spec §10.1; never imported
by tenforty/orchestrator.py).

Production never writes the workbook's EIC eligibility answers, so a
workbook-routed return runs on the sheet's defaults. For parity evidence
this adapter writes EVERY answer explicitly from the scenario's
`eic_eligibility` facts, through the real engine, by:
  * extending the flattened inputs with one key per answer cell, and
  * swapping the engine's mapping for one that maps those keys (and the
    sheet's own diagnostic cells, as extra outputs).

Each question on the EIC sheet has exactly ONE input cell; its other
answer is a formula (pinned per year by tests/test_eic_workbook_health.py),
so "every answer explicitly" means each INPUT cell set to "X" or cleared,
never the derived side.
"""
import contextlib
from unittest import mock

from tenforty.mappings.f1040 import F1040
from tenforty.models import FilingStatus, Scenario, parse_filing_status

# Per year: the EIC sheet, its hardcoded constants (health check), each
# answer's INPUT cell, the formula cells that derive the other answers, and
# the status cells a row's evidence is read from. Read 2026-10-22 from
# spreadsheets/federal/<year>/1040.xlsx by formula consumers (plan doc).
EIC_WORKBOOK_CELLS: dict[int, dict] = {
    2025: {
        "sheet": "Line 27a (EIC)",
        "constants": {
            ("Line 27a (EIC)", "N58"): "eic_investment_income_limit",
            ("Line 27a (EIC)", "N176"): "eic_min_age",
            ("Line 27a (EIC)", "N177"): "eic_max_age",
            ("EIC Table", "N3"): ("eic_max_credit", None),
            ("EIC Table", "R3"): ("eic_max_credit", None),
            ("EIC Table", "N5"): ("eic_phaseout_threshold", "single"),
            ("EIC Table", "R5"): ("eic_phaseout_threshold",
                                  "married_filing_jointly"),
            ("EIC Table", "N6"): ("eic_completed_phaseout", "single"),
            ("EIC Table", "R6"): ("eic_completed_phaseout",
                                  "married_filing_jointly"),
        },
        # answer key -> (sheet, input cell)
        "inputs": {
            # K112 is the labelled input ("Enter number of qualifying
            # children here"); B112 derives from it, else the Dependents count.
            "eic_answer_qualifying_children": ("Line 27a (EIC)", "K112"),
            "eic_answer_ssn_not_valid": ("Line 27a (EIC)", "H28"),
            "eic_answer_nonresident_alien": ("Line 27a (EIC)", "B39"),
            "eic_answer_main_home_not_us": ("Line 27a (EIC)", "H199"),
            "eic_answer_qc_of_another": ("Line 27a (EIC)", "B216"),
            "eic_answer_dependent_you": ("1040", "O84"),
            "eic_answer_dependent_spouse": ("1040", "X84"),
            "eic_answer_clergy": ("Line 27a (EIC)", "B235"),
        },
        # The derived side of each question: must stay a formula.
        "derived": ("B28", "H39", "B112", "B199", "H216", "B226", "H226",
                    "H235"),
        # answer-status cells read back after recalculation
        "diagnostics": {
            "eic_diag_no_credit": ("Line 27a (EIC)", "A1"),
            "eic_diag_summary": ("Line 27a (EIC)", "C1"),
            "eic_diag_prompt_an": ("Line 27a (EIC)", "AN1"),
            "eic_diag_prompt_ao": ("Line 27a (EIC)", "AO1"),
            "eic_diag_prompt_ap": ("Line 27a (EIC)", "AP1"),
        },
    },
}

_X = "X"


def answers(scenario: Scenario) -> dict[str, object]:
    """Every answer cell's value for this scenario: "X" where the stated
    fact is the cell's answer, None (cleared) otherwise. Zero qualifying
    children (the childless credit's premise) is written as 0."""
    block = scenario.eic_eligibility
    if block is None:
        raise ValueError("the EIC-answer adapter needs the scenario's "
                         "eic_eligibility block")
    joint = parse_filing_status(scenario.config.filing_status) is (
        FilingStatus.MARRIED_FILING_JOINTLY)
    people = [block.taxpayer] + ([block.spouse] if joint else [])

    def x(flag: bool):
        return _X if flag else None
    return {
        "eic_answer_qualifying_children": 0,
        "eic_answer_ssn_not_valid": x(
            not all(p.ssn_valid_for_employment for p in people)),
        "eic_answer_nonresident_alien": x(
            any(p.nonresident_alien_any_part_of_year for p in people)),
        "eic_answer_main_home_not_us": x(
            not all(p.main_home_in_us_more_than_half_year for p in people)),
        "eic_answer_qc_of_another": x(
            block.taxpayer.could_be_qualifying_child_of_another),
        "eic_answer_dependent_you": x(block.taxpayer.can_be_claimed_as_dependent),
        "eic_answer_dependent_spouse": x(
            joint and block.spouse.can_be_claimed_as_dependent),
        # No scenario input can state clergy/church-employee income (its
        # unreachability is pinned): always answered "No" (input cleared).
        "eic_answer_clergy": None,
    }


def answering_mapping(year: int) -> type:
    """F1040 extended with the year's answer inputs and diagnostic outputs."""
    cells = EIC_WORKBOOK_CELLS[year]
    extra_in = {k: cell for k, (_, cell) in cells["inputs"].items()}
    extra_out = {k: cell for k, (_, cell) in cells["diagnostics"].items()}
    extra_sheets = {k: sheet for k, (sheet, _) in
                    {**cells["inputs"], **cells["diagnostics"]}.items()}

    class _Answering:
        SHEET_MAP = {year: {**F1040.SHEET_MAP[year], **extra_sheets}}

        @staticmethod
        def get_inputs(y):
            return {**F1040.get_inputs(y), **extra_in}

        @staticmethod
        def get_outputs(y):
            return {**F1040.get_outputs(y), **extra_out}
    return _Answering


@contextlib.contextmanager
def eic_answers_adapter(orchestrator):
    """Within this context, the orchestrator's workbook path writes every EIC
    answer from the scenario's facts and reads the sheet's diagnostics back.
    Marks the orchestrator so the production guard lets the facts through."""
    from tenforty import orchestrator as orchestrator_module
    real_flatten = orchestrator_module.flatten_scenario
    real_compute = orchestrator.engine.compute

    def flatten(scenario):
        return {**real_flatten(scenario), **answers(scenario)}

    def compute(spreadsheet_path, mapping, year, inputs, work_dir=None):
        if mapping is F1040:
            mapping = answering_mapping(year)
        return real_compute(spreadsheet_path=spreadsheet_path,
                            mapping=mapping, year=year, inputs=inputs,
                            work_dir=work_dir)
    with mock.patch.object(orchestrator_module, "flatten_scenario", flatten), \
            mock.patch.object(orchestrator.engine, "compute", compute), \
            mock.patch.object(orchestrator, "_eic_answers_adapter", True,
                              create=True):
        yield
