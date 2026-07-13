"""California Schedule K-1 (100S) PDF field mapping.

One PDF per shareholder (mirrors PdfF1120SK1). Certified by the marker-probe
committed at pdfs/california/<year>/f100s_k1.probe.pdf, with each field PATH
taken from the template's own get_fields() listing (never inferred from a
marker/format). TWO form revisions:
  - 2021-2023: bare field names ("1029"); Line 1 income cols 1029/1031/1032.
  - 2024-2025: "Sch K-1 (100s) "-prefixed; Line 1 income cols "1030 A"/1032/1033
    (col (b) is "1030 A" WITH a trailing space+A — a DIFFERENT field from the
    bare "1030", which is Side-1 Item H "total shares").
Identity + allocation-% field numbers are stable across all years; only the
namespace and the Line-1 income numbers differ between revisions.

VALUES: forms/f100s_k1 supplies per-shareholder federal_ordinary_income +
ca_ordinary_income + ownership_fraction; the identity fields and the split
allocation-% (Item A renders as "<whole>.<frac>%", two AcroForm fields) are
assembled at emit time from the scenario. v1 maps Line 1 (ordinary business
income) only, mirroring the federal K-1's box-1 scope; other pro-rata lines
and granular address fields are a follow-up.
"""
from tenforty.mappings.registry import PdfFormMapping

# Identity/alloc suffixes: stable across all years.
_IDENTITY_SUFFIX: dict[str, str] = {
    "k1_shareholder_name":     "1003",   # Side 1 "Shareholder's name"
    "k1_shareholder_id":       "1004",   # Side 1 "Shareholder's identifying number"
    "k1_corp_fein":            "1009",   # Side 1 "Corporation's FEIN"
    "k1_corp_ca_number":       "1010",   # Side 1 "California corporation number"
    "k1_corp_name":            "1011",   # Side 1 "Corporation's name"
    "k1_ownership_pct_whole":  "1016a",  # Item A % box, integer part (left of decimal)
    "k1_ownership_pct_frac":   "1016b",  # Item A % box, fractional part (right of decimal)
}
# Line 1 (Ordinary business income) income columns — differ by revision.
_LINE1_BARE: dict[str, str] = {          # 2021-2023
    "k1_federal_ordinary_income":   "1029",  # Line 1 col (b) federal amount
    "k1_ca_ordinary_income_total":  "1031",  # Line 1 col (d) CA total
    "k1_ca_ordinary_income_source": "1032",  # Line 1 col (e) CA source
}
_LINE1_PREFIXED: dict[str, str] = {      # 2024-2025 (numbers moved)
    "k1_federal_ordinary_income":   "1030 A",  # Line 1 col (b) federal amount (space+A!)
    "k1_ca_ordinary_income_total":  "1032",    # Line 1 col (d) CA total
    "k1_ca_ordinary_income_source": "1033",    # Line 1 col (e) CA source
}


def _bare(suffixes: dict[str, str]) -> dict[str, str]:
    return dict(suffixes)


def _prefixed(suffixes: dict[str, str]) -> dict[str, str]:
    return {k: f"Sch K-1 (100s) {n}" for k, n in suffixes.items()}


_MAPPING_2021_2023 = {**_bare(_IDENTITY_SUFFIX), **_bare(_LINE1_BARE)}
_MAPPING_2024_2025 = {**_prefixed(_IDENTITY_SUFFIX), **_prefixed(_LINE1_PREFIXED)}


class PdfF100SK1(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for California Schedule K-1 (100S). One PDF per
    shareholder. Bare names + Line-1 1029/1031/1032 for 2021-2023;
    "Sch K-1 (100s) "-prefixed + Line-1 "1030 A"/1032/1033 for 2024-2025."""

    _FORM_NAME = "Schedule K-1 (100S)"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2021: _MAPPING_2021_2023, 2022: _MAPPING_2021_2023,
        2023: _MAPPING_2021_2023,
        2024: _MAPPING_2024_2025, 2025: _MAPPING_2024_2025,
    }
