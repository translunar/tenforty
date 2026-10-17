"""FTB 3532 (Head of Household Filing Status Schedule) presentation keys.

FTB 3532 has no arithmetic: every answered line presents a fact from the
scenario's ``config.head_of_household`` block (or the filer header). This
module turns those facts into the ``ftb3532_*`` keys that
``tenforty.mappings.pdf_ftb3532`` places on each year's template.

California denies head-of-household status to a return that does not attach
a completed FTB 3532 (every year's instructions, General Information), so the
form is required iff the filing status is head of household. The CA emit gate
(``Orchestrator._emit_ca_pdfs_internal``) enforces that; this module only
presents.
"""
from tenforty.forms.presentation_dates import mm_dd_yyyy
from tenforty.models import FilingStatus, TaxReturnConfig, parse_filing_status
from tenforty.scenario import (
    normalize_ssn_digits,
    qp_is_19_or_older,
    validate_head_of_household,
)


def is_required(config: TaxReturnConfig) -> bool:
    """True iff the return claims head of household: California requires a
    completed FTB 3532 with exactly those returns."""
    return (parse_filing_status(config.filing_status)
            is FilingStatus.HEAD_OF_HOUSEHOLD)


def _ssn(value: str, where: str) -> str:
    try:
        return normalize_ssn_digits(value)
    except ValueError as exc:
        raise ValueError(
            f"FTB 3532 cannot print {where}: {exc} Correct it in the "
            "scenario; the form's SSN boxes take 9 digits.") from exc


def presentation_keys(config: TaxReturnConfig) -> dict[str, object]:
    """The ``ftb3532_*`` keys for this return; ``{}`` unless head of
    household.

    Always (HoH): header name/SSN, the Part I and Part II selections, the
    qualifying person's name/SSN/DOB, line 4 and line 5. Branch-only: the
    line 1f From/To pairs (one per lived-together period given) and the line
    3a/3b answers (only when the qualifying person is 19 or older in the
    year — the form says "If not, go to line 4"). Both SSNs are normalized
    to 9 bare digits here as well as at load, because a directly built
    config bypasses the loader. A head-of-household config with no block
    refuses (the FTB 3532 message from ``validate_head_of_household``).
    """
    if not is_required(config):
        return {}
    facts = config.head_of_household
    if facts is None:
        validate_head_of_household(config)  # raises: HoH needs the block
        raise AssertionError("unreachable: HoH without a block must refuse")
    qp = facts.qualifying_person
    year = config.year
    keys: dict[str, object] = {
        "ftb3532_header_name": config.full_name,
        "ftb3532_header_ssn": _ssn(config.ssn, "the filer's SSN (header)"),
        "ftb3532_marital_status": facts.marital_status.value,
        "ftb3532_relationship": qp.relationship.value,
        "ftb3532_qp_first_name": qp.first_name,
        "ftb3532_qp_last_name": qp.last_name,
        "ftb3532_qp_ssn": _ssn(qp.ssn, "the qualifying person's SSN (line 3)"),
        "ftb3532_qp_dob": mm_dd_yyyy(qp.birthdate),
        "ftb3532_line_4_gross_income": qp.gross_income,
        "ftb3532_line_5_days": qp.days_lived_with_you,
    }
    periods = facts.lived_with_spouse_periods
    if len(periods) > 2:
        raise ValueError(
            f"FTB 3532 line 1f has two From/To slots; this return lists "
            f"{len(periods)} lived-together periods. The form has no "
            "continuation statement, so tenforty cannot print it; file by hand.")
    for n, period in enumerate(periods, start=1):
        keys[f"ftb3532_period_{n}_from"] = mm_dd_yyyy(period.start)
        keys[f"ftb3532_period_{n}_to"] = mm_dd_yyyy(period.end)
    if qp_is_19_or_older(qp, year):
        keys["ftb3532_line_3a"] = qp.full_time_student
        keys["ftb3532_line_3b"] = qp.permanently_disabled
    return keys
