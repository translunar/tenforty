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

The six f100s_entity_* keys carry the corporation's identity onto Side 1; their
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
    "f100s_prior_year_overpayment_applied": "2028",  # Side 2 L31 Overpayment from prior year credit
    "f100s_estimated_tax_payments":         "2029",  # Side 2 L32 Estimated tax/QSub payments
    "f100s_total_payments":                 "2033",  # Side 2 L36 Total payments
    "f100s_amount_owed":                    "2037",  # Side 2 L40 Franchise or income tax due
    "f100s_overpayment":                    "2038",  # Side 2 L41 Overpayment
    "f100s_entity_name":                    "1003",  # Side 1 Corporation name (emit-injected)
    "f100s_entity_ca_corp_number":          "1004",  # Side 1 California corporation number
    "f100s_entity_fein":                    "1005",  # Side 1 FEIN
    "f100s_entity_street":                  "1008",  # Side 1 Street address
    "f100s_entity_city":                    "1010",  # Side 1 City
    "f100s_entity_zip":                     "1012",  # Side 1 ZIP code
}
_MAPPING_BARE: dict[str, str] = dict(_SUFFIX)                              # 2021-2023
_MAPPING_PREFIXED: dict[str, str] = {k: f"100S Form {n}" for k, n in _SUFFIX.items()}  # 2024-2025


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
