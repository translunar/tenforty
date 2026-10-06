"""California Form 100S PDF field mapping.

Flat 1:1 compute-key -> FTB AcroForm field. The LINE/NUMBER correspondence
(which compute key belongs to which FTB field number) is identical for every
supported year and is certified by the marker-probe committed at
pdfs/california/<year>/f100s.probe.pdf (each entry's trailing comment records
Side/Line + printed label).

What is NOT identical across years is the AcroForm field-NAME NAMESPACE: the
2021-2023 templates name each widget with the bare number ("1031"), while the
2024-2025 templates prefix it ("100S Form 1031"). Same line, two name forms.
So `_MAPPING_BARE` (2021-2023) and `_MAPPING_PREFIXED` (2024-2025) are built
from one shared `_SUFFIX` dict; only the namespace differs. Each year's paths
are verified present on that year's own template.

The eleven f100s_entity_* keys carry the corporation's identity (and, on Side 3, Schedule Q Questions F and K) onto the form; their
VALUES are injected at emit time from the scenario (see the CA S-corp emit
wiring), not produced by f100s.compute. The diagnostic compute outputs
f100s_measured_tax and f100s_minimum_tax_applies have no Form 100S line and are
intentionally unmapped. The line-21 rate box (field 2013, key f100s_tax_rate)
IS mapped; its value is injected at emit from the attested
params.franchise_tax_rate, formatted as the form prints the percentage, so a
filed 100S reads "1.5% x line 20" complete.
"""
from tenforty.mappings.registry import PdfFormMapping

# compute-key -> FTB field-NUMBER suffix (identical line correspondence for
# every supported year; marker-probe certified). The AcroForm field-NAME
# NAMESPACE differs by year: 2021-2023 name the widget with the bare number
# ("1031"); 2024-2025 prefix it ("100S Form 1031"). Same line, two name forms.
_SUFFIX: dict[str, str] = {
    "f100s_federal_ordinary_income":        "1031",  # Side 1 L1 Ordinary income; label cites fed 1120-S "line 21" (2021-22) / "line 22" (2023-25) — same field & semantic
    "f100s_state_tax_addback":              "1032",  # Side 1 L2 CA franchise/income tax deducted
    "f100s_depreciation_adjustment":        "1035",  # Side 1 L5 Depreciation & amort adjustments
    "f100s_net_income_for_tax":             "2012",  # Side 2 L20 Net income for tax purposes
    "f100s_franchise_tax":                  "2014",  # Side 2 L21 Tax amount
    "f100s_tax_rate":                       "2013",  # Side 2 L21 Tax RATE %-box (emit-injected: params.franchise_tax_rate formatted as printed %)
    "f100s_total_tax":                      "2023",  # Side 2 L26 Balance (v1: =L21)
    "f100s_total_tax_after_other_taxes":    "2027",  # Side 2 L30 Total tax (v1: =L26)
    "f100s_prior_year_overpayment_applied": "2028",  # Side 2 L31 Overpayment from prior year credit
    "f100s_estimated_tax_payments":         "2029",  # Side 2 L32 Estimated tax/QSub payments
    "f100s_total_payments":                 "2033",  # Side 2 L36 Total payments
    "f100s_payments_balance":               "2035",  # Side 2 L38 Payments balance (v1: =L36)
    "f100s_amount_owed":                    "2037",  # Side 2 L40 Franchise or income tax due
    "f100s_overpayment":                    "2038",  # Side 2 L41 Overpayment
    "f100s_entity_name":                    "1003",  # Side 1 Corporation name (emit-injected)
    "f100s_entity_ca_corp_number":          "1004",  # Side 1 California corporation number
    "f100s_entity_fein":                    "1005",  # Side 1 FEIN
    "f100s_entity_street":                  "1008",  # Side 1 Street address
    "f100s_entity_city":                    "1010",  # Side 1 City
    "f100s_entity_state":                   "1011",  # Side 1 State (between City 1010 and ZIP 1012; marker-probe certified 2021-2025)
    "f100s_entity_zip":                     "1012",  # Side 1 ZIP code
    "f100s_entity_s_election_date":         "3012",  # Side 3 Sch Q Question K (J on 2021-2022 forms) Effective date of federal S election (emit-injected)
    "f100s_entity_state_incorporated":      "3007",  # Side 3 Sch Q Question F "Where incorporated: State" (stated; emit-injected)
    "f100s_entity_country_incorporated":    "3008",  # Side 3 Sch Q Question F "Where incorporated: Country" (stated; emit-injected)
    "f100s_entity_date_incorporated":       "3006",  # Side 3 Sch Q Question F Date incorporated (emit-injected; same number every year 2022-2025)
}
_MAPPING_BARE: dict[str, str] = dict(_SUFFIX)                              # 2021-2023
_MAPPING_PREFIXED: dict[str, str] = {k: f"100S Form {n}" for k, n in _SUFFIX.items()}  # 2024-2025


# ── Schedule Q stated answers ───────────────────────────────────────────────
# One (field, on-state) cell per ANSWER, per year, certified against each year's
# own template by the printed caption beside each widget Rect (Schedule Q
# renumbers between years, and radio on-state tokens differ per year — path
# existence and numbering cannot be copied across years):
#   audit (Question I on the 2022 form, Question J from 2023): Yes / No.
#     2022 field 3011 radio /0 Yes /1 No; 2023 field 3011a radio /Yes /No
#     (tokens spelled out); 2024-2025 field 3011a radio /0 Yes /1 No.
#   information returns filed (Question O), printed left to right N/A, Yes, No:
#     2022-2023 three SEPARATE checkboxes 3018 / 3019 / 3020 (on /Yes);
#     2024 one radio 3018 RB: N/A /0, Yes /1, No /2;
#     2025 one radio 3018 RB: N/A /0, Yes /2, No /1  (Yes and No swap tokens).
# 2021 has no entry: the feature floor is TY2022, and a stated answer is
# refused at emit rather than dropped.
_Cell = tuple[str, str]

# Field-name namespace: bare through 2023, "100S Form "-prefixed after.
_Q_PREFIX: dict[int, str] = {
    2022: "", 2023: "", 2024: "100S Form ", 2025: "100S Form "}
# Audit question: year -> (field, Yes token, No token).
_Q_AUDIT: dict[int, tuple[str, str, str]] = {
    2022: ("3011 rb", "/0", "/1"),
    2023: ("3011a rb", "/Yes", "/No"),
    2024: ("3011a rb", "/0", "/1"),
    2025: ("3011a rb", "/0", "/1"),
}
# Question O, 2022-2023: three separate checkboxes (N/A, Yes, No), all /Yes.
_Q_INFO_CHECKBOXES: dict[int, tuple[str, str, str]] = {
    2022: ("3018 CB", "3019 CB", "3020 CB"),
    2023: ("3018 CB", "3019 CB", "3020 CB"),
}
# Question O, 2024-2025: one radio; year -> {answer: token}.
_Q_INFO_RADIO: dict[int, dict[str, str]] = {
    2024: {"not_applicable": "/0", "yes": "/1", "no": "/2"},
    2025: {"not_applicable": "/0", "yes": "/2", "no": "/1"},
}


def _schedule_q_cells(year: int) -> dict[str, dict[object, _Cell]]:
    prefix = _Q_PREFIX[year]
    field, yes_on, no_on = _Q_AUDIT[year]
    audit = {True: (prefix + field, yes_on), False: (prefix + field, no_on)}
    if year in _Q_INFO_CHECKBOXES:
        na_f, yes_f, no_f = _Q_INFO_CHECKBOXES[year]
        info = {"not_applicable": (prefix + na_f, "/Yes"),
                "yes": (prefix + yes_f, "/Yes"),
                "no": (prefix + no_f, "/Yes")}
    else:
        info = {a: (prefix + "3018 RB", t)
                for a, t in _Q_INFO_RADIO[year].items()}
    return {"under_irs_audit": audit, "information_returns_filed": info}


_SCHEDULE_Q_BY_YEAR: dict[int, dict[str, dict[object, _Cell]]] = {
    y: _schedule_q_cells(y) for y in _Q_PREFIX
}


class PdfF100S(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for California Form 100S. Flat 1:1. The line/number
    correspondence is identical across all CA_SCORP_YEARS (marker-probe
    certified per year); the field-name namespace is bare for 2021-2023 and
    "100S Form "-prefixed for 2024-2025."""

    _FORM_NAME = "Form 100S"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2021: _MAPPING_BARE, 2022: _MAPPING_BARE, 2023: _MAPPING_BARE,
        2024: _MAPPING_PREFIXED, 2025: _MAPPING_PREFIXED,
    }

    @classmethod
    def get_schedule_q_cells(cls, year: int) -> dict[str, dict[object, _Cell]]:
        """{question: {answer: (field_path, on_state)}} for the Schedule Q
        answers the filer states. ADDITIVE to ``_MAPPINGS``: the orchestrator
        merges only the CHOSEN answer's cell, so the others stay unmarked
        (mutually exclusive by construction). Questions: ``under_irs_audit``
        (answers True/False) and ``information_returns_filed`` ("yes", "no",
        "not_applicable"). Raises for a year with no certified cells."""
        if year not in _SCHEDULE_Q_BY_YEAR:
            raise ValueError(
                f"No Form 100S Schedule Q answer cells for year {year}")
        return _SCHEDULE_Q_BY_YEAR[year]
