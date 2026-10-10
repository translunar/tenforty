"""Form 3115 (Application for Change in Accounting Method), Rev. December 2022.

Presentation only. tenforty prints ONE answer pattern in v1 -- an individual's
automatic change number 7 (depreciation or amortization, impermissible to
permissible) -- from the scenario's `form_3115:` block, and refuses every
other (`attestations._FORM_3115_REFUSALS`). Nothing here is computed tax:

* The section 481(a) adjustment on line 26 is STATED by the applicant. The
  applicant's workpapers compute it; tenforty neither derives nor checks it,
  and does not carry it onto the return's income.
* Name, identification number and address come from `config`, as on every
  other form.
* The one derived cell is line 7b "Not under exam", which the instructions
  define as (A) the applicant is not under exam and (B) audit protection
  applies -- exactly the line 6a "No" and line 7a "Yes" the block attests.

The one-year election (line 28) is made ON the form: line 28 "Yes" plus the
"$50,000 de minimis election" box. No separate election statement exists.

Left blank by design: line 1b, lines 6b-6d, 8b-8d, 9, 10 (asked only of a
partnership or S corporation), 19, Part III, Schedules A-D, the fourth name
line (applicant different from filer), the consolidated-group and Form 2848
boxes, and the preparer block.
"""
from tenforty.models import Form3115, Scenario

# (compute-key stem, Form3115 field) for each Yes/No pair the block answers.
_YES_NO_ANSWERS: tuple[tuple[str, str], ...] = (
    ("f3115_correspondence", "wants_correspondence_by_fax_or_email"),
    ("f3115_line2", "eligibility_rules_restrict_automatic_change"),
    ("f3115_line3", "all_required_information_provided"),
    ("f3115_line4", "ceases_trade_or_terminates_in_year_of_change"),
    ("f3115_line5", "changing_to_section_381_principal_method"),
    ("f3115_line6a", "under_examination"),
    ("f3115_line7a", "audit_protection_applies"),
    ("f3115_line8a", "before_appeals_or_federal_court"),
    ("f3115_line11a", "prior_method_change_within_five_years"),
    ("f3115_line12", "pending_ruling_or_method_change_request"),
    ("f3115_line13", "changing_overall_method"),
    ("f3115_line17", "proposed_method_used_for_books"),
    ("f3115_line18", "requests_conference_if_adverse"),
    ("f3115_line25", "cut_off_basis"),
    ("f3115_line27", "prior_section_481a_adjustment_remaining"),
    ("f3115_line28", "elect_one_year_spread"),
    ("f3115_line29", "adjustment_from_related_party_transactions"),
    ("f3115_sch_e_line1", "depreciation_under_cladr"),
    ("f3115_sch_e_line2", "depreciation_capitalized_under_another_section"),
    ("f3115_sch_e_line3", "depreciation_election_made"),
    ("f3115_sch_e_line4b", "lived_in_residential_rental_before_renting"),
    ("f3115_sch_e_line4c", "public_utility_property"),
)


def money(amount: float) -> str:
    """A stated amount as written: thousands separators, and cents only when
    the applicant stated cents. Never rounded -- a stated 49,999.99 that
    printed as 50,000 would contradict the de minimis election beside it."""
    cents = round(abs(amount) * 100)
    whole, frac = divmod(cents, 100)
    return f"{whole:,}.{frac:02d}" if frac else f"{whole:,}"


def signed_adjustment(amount: float) -> str:
    """Line 26: "Indicate whether the adjustment is an increase (+) or a
    decrease (-) in income." """
    if round(abs(amount) * 100) == 0:
        return "0"
    return f"{'+' if amount > 0 else '-'}{money(amount)}"


def _mdy(d) -> str:
    return d.strftime("%m/%d/%Y")


def presentation_values(scenario: Scenario) -> dict[str, object]:
    """The Form 3115 emit payload: compute key -> text, or bool for a box.

    Each Yes/No answer becomes a `<stem>_yes` / `<stem>_no` pair; an answer
    stated None (Schedule E line 4b, not residential rental property) checks
    neither box."""
    form: Form3115 = scenario.form_3115
    config = scenario.config
    header = config.pdf_header()
    values: dict[str, object] = {
        "f3115_filer_name": header["taxpayer_name"],
        "f3115_street": config.address,
        "f3115_city_state_zip": (
            f"{config.address_city}, {config.address_state} "
            f"{config.address_zip}"),
        "f3115_identification_number": header["taxpayer_ssn"],
        "f3115_business_activity_code": form.principal_business_activity_code,
        "f3115_tax_year_begins": _mdy(form.tax_year_begins),
        "f3115_tax_year_ends": _mdy(form.tax_year_ends),
        "f3115_contact_person": form.contact_person,
        "f3115_contact_phone": form.contact_phone,
        "f3115_applicant_individual": form.applicant_type == "individual",
        "f3115_change_depreciation": (
            form.type_of_change == "depreciation_or_amortization"),
        "f3115_dcn_1": str(form.designated_change_number),
        "f3115_line7b_not_under_exam": (
            form.under_examination is False
            and form.audit_protection_applies is True),
        "f3115_line26_adjustment": signed_adjustment(
            form.section_481a_adjustment),
        "f3115_line28_de_minimis": form.elect_one_year_spread is True,
        "f3115_signer_name": header["taxpayer_name"],
    }
    for stem, field in _YES_NO_ANSWERS:
        answer = getattr(form, field)
        values[f"{stem}_yes"] = answer is True
        values[f"{stem}_no"] = answer is False
    return values


# --- Filing manifest --------------------------------------------------------

# Transcribed from the Instructions for Form 3115 (Rev. December 2022),
# "When and Where To File", automatic change requests, and its Address Chart
# ("An automatic change request (Form 3115 copy)" column).
_DUPLICATE_COPY_LINES: tuple[str, ...] = (
    "Form 3115 under the automatic change procedures is filed IN DUPLICATE:",
    "  1. Attach the original Form 3115 to the filer's timely filed",
    "     (including extensions) federal income tax return for the year of",
    "     change. The original attached to the return does not need to be",
    "     signed.",
    "  2. File a copy of the signed Form 3115 (duplicate copy) with the IRS",
    "     National Office at the address below,",
    "     no earlier than the first day of the year of change and",
    "     no later than the date the original is filed with the federal",
    "     income tax return for the year of change. This signed copy may be",
    "     a photocopy.",
    "       By mail:              Internal Revenue Service",
    "                             Ogden, UT 84201",
    "                             M/S 6111",
    "       By private delivery:  Internal Revenue Service",
    "                             1973 N. Rulon White Blvd.",
    "                             Ogden, UT 84201",
    "                             Attn: M/S 6111",
    "       By fax:               844-249-8134",
    "  The IRS does not send acknowledgements of receipt for automatic",
    "  change requests.",
    "  Source: Instructions for Form 3115 (Rev. December 2022), \"When and",
    "  Where To File\" and the Address Chart. CONFIRM the address against the",
    "  current instructions at www.irs.gov/Form3115 before mailing.",
)

# Statements the form requires that tenforty does not write. Each entry is
# (where on the form, what the form asks for).
_REQUIRED_NOT_EMITTED: tuple[tuple[str, str], ...] = (
    ("Line 14",
     "description of (a) the item being changed, (b) the present method, "
     "(c) the proposed method, (d) the present overall method of accounting; "
     "with 14b, whether any federal tax credit, grant or subsidy was claimed "
     "for the item"),
    ("Line 15a",
     "description of the applicant's trade(s) or business(es)"),
    ("Lines 16a-b",
     "explanation of the legal basis supporting the proposed method and the "
     "supporting authority (required for change number 7 unless already "
     "provided in Schedule E)"),
    ("Line 26",
     "summary of the computation of the section 481(a) adjustment and an "
     "explanation of the methodology used to determine it"),
    ("Schedule E, line 5",
     "how the property is treated under the present method, to the extent "
     "not already in the description of the present method"),
    ("Schedule E, line 7c",
     "the facts supporting the asset class for the proposed method"),
    ("Schedule E, line 7g",
     "for any asset with no special depreciation allowance claimed, why "
     "none was or will be claimed"),
)
_LINE_17_NO: tuple[str, str] = (
    "Line 17",
    "explanation of why the proposed method will not be used for the "
    "applicant's books and records")


def required_attachments(form: Form3115) -> list[tuple[str, str]]:
    out = list(_REQUIRED_NOT_EMITTED)
    if form.proposed_method_used_for_books is False:
        out.insert(3, _LINE_17_NO)
    return out


def adjustment_period(form: Form3115) -> str:
    """The section 481(a) adjustment period, per the Form 3115 instructions
    for line 25 (not under examination) and line 28."""
    adjustment = form.section_481a_adjustment
    if round(abs(adjustment) * 100) == 0:
        return "none (the stated adjustment is zero)"
    if adjustment < 0:
        return "1 tax year (negative adjustment)"
    if form.elect_one_year_spread:
        return "1 tax year (the $50,000 de minimis election)"
    return "4 tax years (year of change and next 3 tax years)"


def filing_manifest(
        scenario: Scenario, *, form_file: str, statement_file: str,
        duplicate_file: str) -> str:
    """The text of `f3115_filing_manifest_<year>.txt`: what was emitted, what
    the applicant must still attach, and where the signed duplicate goes."""
    form: Form3115 = scenario.form_3115
    lines = [
        f"Form 3115 filing manifest — year of change {form.year_of_change}",
        "=" * 64,
        "",
        f"Applicant: {scenario.config.full_name}",
        "Change:    designated automatic accounting method change number "
        f"{form.designated_change_number}",
        "",
        "Emitted by tenforty:",
        f"  - {form_file}: Form 3115 (Rev. December 2022)",
        f"  - {statement_file}: statement for Schedule E, lines 4a and 7 "
        f"({len(form.assets)} item(s) of property)",
        f"  - {duplicate_file}: the form and that statement together, for "
        "signing and filing as the duplicate copy",
        "",
        "REQUIRED, NOT EMITTED — the applicant must prepare and attach to "
        "BOTH copies:",
    ]
    lines += [f"  - {where}: {what}"
              for where, what in required_attachments(form)]
    lines += [
        "",
        "Section 481(a) adjustment:",
        f"  - Line 26 prints {signed_adjustment(form.section_481a_adjustment)}"
        " — the amount STATED in the scenario. tenforty does not compute",
        "    or check the section 481(a) adjustment; the applicant's",
        "    workpapers do (attach the Line 26 summary above).",
        "  - The adjustment is not carried onto the return's income by",
        "    tenforty: the scenario's income figures must already include the",
        "    portion taken into account this year.",
        f"  - Adjustment period: {adjustment_period(form)}.",
        "",
        "Signed duplicate copy:",
        *(f"  {line}" for line in _DUPLICATE_COPY_LINES),
        "",
    ]
    return "\n".join(lines)
