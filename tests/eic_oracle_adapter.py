"""ORACLE-ONLY EIC-answer adapter (childless-EITC spec §10.1; never imported
by tenforty/orchestrator.py).

Production never writes the workbook's EIC eligibility answers, so a
workbook-routed return runs on the sheet's defaults. For parity evidence
this adapter writes EVERY answer explicitly from the scenario's
`eic_eligibility` facts, through the real engine, by:
  * extending the flattened inputs with one key per answer cell, and
  * swapping the engine's mapping for one that maps those keys (and the
    sheet's own diagnostic cells, as extra outputs).

Each eligibility question on the EIC sheet has exactly ONE input cell; its
other answer is a formula (pinned per year by
tests/test_eic_workbook_health.py), so "every answer explicitly" means each
INPUT cell set to "X" or cleared, never the derived side. The ONE exception
is Step 2 question 3 (Form 4797), whose "Yes" and "No" are both plain input
cells: production answers it (ruling R-S7-6a,
mappings.f1040.EIC_FORM_4797_QUESTION), and this adapter writes production's
identical formula and clears "Yes".
"""
import contextlib
from unittest import mock

from tenforty.mappings.f1040 import (
    EIC_FORM_4797_NO_KEY, F1040, eic_form_4797_no_answer)
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
            # Step 2 Q3 (Form 4797): both answers are inputs (R-S7-6a).
            "eic_answer_form_4797_yes": ("Line 27a (EIC)", "B65"),
            EIC_FORM_4797_NO_KEY: ("Line 27a (EIC)", "H65"),
        },
        # The derived side of each question, formula text pinned EXACTLY
        # (ruling R-S7-2): with every input blank these yield the
        # all-favorable answers, the premise the workbook-path guard rests on.
        # A relayout or flipped default must fail here, loudly.
        "derived": {
            "B28": '=IF(A28,"X","")',
            "H39": '=IF(AND(B39="",NOT(EIC_Check)),"X","")',
            "B112": '=IF(K112<>"",ROUND(K112,0),N6)',
            "B199": '=IF(A199,"X","")',
            "H216": '=IF(G216,"X","")',
            "B226": '=IF(A226,"X","")',
            "H226": '=IF(G226,"X","")',
            "H235": '=IF(G235,"X","")',
        },
        # answer-status cells read back after recalculation
        "diagnostics": {
            "eic_diag_no_credit": ("Line 27a (EIC)", "A1"),
            "eic_diag_summary": ("Line 27a (EIC)", "C1"),
            "eic_diag_prompt_an": ("Line 27a (EIC)", "AN1"),
            "eic_diag_prompt_ao": ("Line 27a (EIC)", "AO1"),
            "eic_diag_prompt_ap": ("Line 27a (EIC)", "AP1"),
        },
        # Ruling R-S7-9a: each STOP a denied row must positively reach,
        # read back after recalculation -> its formula, pinned EXACTLY.
        "stops": {
            "eic_stop_agi_limit": ("G21", '=H21="X"'),           # Step 1 Q1
            "eic_stop_ssn": ("G28", '=OR(NOT(A28),H28<>"")'),    # Step 1 Q2
            "eic_stop_age": ("G185", "=AND(K164,G172,NOT(A185))"),  # Step 4 Q2
            "eic_stop_main_home": ("G199", '=H199<>""'),         # Step 4 Q3
            "eic_stop_qc_of_another": ("A216", '=AND(G206,B216<>"")'),  # Q5
            "eic_stop_dependent": ("A226",
                                   '=AND(G216,DependentYOU<>"")'),  # Q6
            "eic_stop_credit_zero": ("A321", "=AND(A310,L316=0)"),  # Wks A
        },
    },
    # 2024: read by formula consumers in the 2024 template (step 8; no
    # carry-over from 2025 — Steps 3-6 sit on different rows, the children
    # answer is the N5 override, and the EIC Table holds literal values, so
    # it is pinned whole against the ingested CSV instead of by constants).
    2024: {
        "sheet": "Line 27 (EIC)",
        "literal_table": True,
        "constants": {
            ("Line 27 (EIC)", "N58"): "eic_investment_income_limit",
            ("Line 27 (EIC)", "N168"): "eic_min_age",
            ("Line 27 (EIC)", "N169"): "eic_max_age",
        },
        "inputs": {
            # N5 is the "Override" for the qualifying-children count:
            # B109 '=IF(N5<>"",ROUND(N5,0),Dependents!AQ38)'.
            "eic_answer_qualifying_children": ("Line 27 (EIC)", "N5"),
            "eic_answer_ssn_not_valid": ("Line 27 (EIC)", "H28"),
            "eic_answer_nonresident_alien": ("Line 27 (EIC)", "B39"),
            "eic_answer_main_home_not_us": ("Line 27 (EIC)", "H186"),
            "eic_answer_qc_of_another": ("Line 27 (EIC)", "B203"),
            "eic_answer_dependent_you": ("1040", "J32"),
            "eic_answer_dependent_spouse": ("1040", "P32"),
            "eic_answer_clergy": ("Line 27 (EIC)", "B222"),
            "eic_answer_form_4797_yes": ("Line 27 (EIC)", "B65"),
            EIC_FORM_4797_NO_KEY: ("Line 27 (EIC)", "H65"),
        },
        "derived": {
            "B28": '=IF(A28,"X","")',
            "H39": '=IF(AND(B39="",NOT(EIC_Check)),"X","")',
            "B109": '=IF(N5<>"",ROUND(N5,0),Dependents!AQ38)',
            "B186": '=IF(A186,"X","")',
            "H203": '=IF(G203,"X","")',
            "B213": '=IF(A213,"X","")',
            "H213": '=IF(G213,"X","")',
            "H222": '=IF(G222,"X","")',
        },
        "diagnostics": {
            "eic_diag_no_credit": ("Line 27 (EIC)", "A1"),
            "eic_diag_summary": ("Line 27 (EIC)", "C1"),
            "eic_diag_prompt_an": ("Line 27 (EIC)", "AN1"),
            "eic_diag_prompt_ao": ("Line 27 (EIC)", "AO1"),
            "eic_diag_prompt_ap": ("Line 27 (EIC)", "AP1"),
        },
        # The SSN row's stop awaits adjudication: 2024 G28
        # '=AND(EIC_trigger,NOT(A28))' is structurally always FALSE.
        "stops": {
            "eic_stop_agi_limit": ("G21", '=H21="X"'),           # Step 1 Q1
            "eic_stop_age": ("G177", "=AND(K159,G164,NOT(A177))"),  # Step 4 Q2
            "eic_stop_main_home": ("G186", '=H186<>""'),         # Step 4 Q3
            "eic_stop_qc_of_another": ("A203", '=AND(G193,B203<>"")'),  # Q5
            "eic_stop_dependent": ("A213",
                                   '=AND(G203,DependentYOU<>"")'),  # Q6
            "eic_stop_credit_zero": ("A307", "=AND(A297,L303=0)"),  # Wks A
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
        # Form 4797 is unreachable too: production's own answer (R-S7-6a).
        "eic_answer_form_4797_yes": None,
        EIC_FORM_4797_NO_KEY: eic_form_4797_no_answer(scenario.config.year),
    }


def answering_mapping(year: int) -> type:
    """F1040 extended with the year's answer inputs and diagnostic outputs."""
    if year not in EIC_WORKBOOK_CELLS:
        raise ValueError(
            f"the EIC answer cells for {year} are not located yet (spec "
            f"§10.2 gate): add the year to EIC_WORKBOOK_CELLS, read by "
            f"formula consumers, before any {year} parity row")
    cells = EIC_WORKBOOK_CELLS[year]
    extra_in = {k: cell for k, (_, cell) in cells["inputs"].items()}
    extra_out = {k: cell for k, (_, cell) in cells["diagnostics"].items()}
    extra_out.update({k: cell for k, (cell, _) in cells["stops"].items()})
    # The Q3 "No" cell is read back too: the investment row's stop.
    extra_out["eic_stop_form_4797_no"] = cells["inputs"][EIC_FORM_4797_NO_KEY][1]
    extra_sheets = {k: sheet for k, (sheet, _) in
                    {**cells["inputs"], **cells["diagnostics"]}.items()}
    extra_sheets.update({k: cells["sheet"] for k in
                         [*cells["stops"], "eic_stop_form_4797_no"]})

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
