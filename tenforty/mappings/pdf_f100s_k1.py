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
from tenforty.mappings.registry import PdfFormMapping, trim_decimal

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
# Face items certified per template by printed caption; the field NUMBERS are
# stable 2021-2025 (only the namespace differs): shareholder / corporation
# address block, Line B shares (beginning, ending), Line C loans from
# shareholder (beginning, ending).
_FACE_SUFFIX: dict[str, str] = {
    "k1_shareholder_street":   "1005",
    "k1_shareholder_city":     "1006",
    "k1_shareholder_state":    "1007",
    "k1_shareholder_zip":      "1008",
    "k1_corp_street":          "1012",
    "k1_corp_city":            "1013",
    "k1_corp_state":           "1014",
    "k1_corp_zip":             "1015",
    "k1_shares_beginning":     "1017",
    "k1_shares_end":           "1018",
    "k1_loans_beginning":      "1019",
    "k1_loans_end":            "1020",
}
# Line H "Corporation's total number of shares" (beginning, ending) exists on
# the 2024-2025 forms ONLY. On 2021-2023 the bare numbers 1029 / 1030 are the
# Line 1 income columns, so these must never be added to the bare mapping.
_LINE_H_SUFFIX: dict[str, str] = {
    "k1_corp_total_shares_beginning": "1029",
    "k1_corp_total_shares_end":       "1030",
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


_MAPPING_2021_2023 = {
    **_bare(_IDENTITY_SUFFIX), **_bare(_FACE_SUFFIX), **_bare(_LINE1_BARE)}
_MAPPING_2024_2025 = {
    **_prefixed(_IDENTITY_SUFFIX), **_prefixed(_FACE_SUFFIX),
    **_prefixed(_LINE_H_SUFFIX), **_prefixed(_LINE1_PREFIXED)}

# Shares may be fractional; loans stay whole-dollar.
_FIELD_FORMATS = {
    "k1_shares_beginning": trim_decimal, "k1_shares_end": trim_decimal,
    "k1_corp_total_shares_beginning": trim_decimal,
    "k1_corp_total_shares_end": trim_decimal,
}


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

    @classmethod
    def get_field_formats(cls, year: int) -> dict:
        """Compute key -> render override (see ``PdfFiller.resolve_fields``)."""
        if year not in cls._MAPPINGS:
            raise ValueError(f"No {cls._FORM_NAME} field formats for year {year}")
        return _FIELD_FORMATS

    @classmethod
    def get_final_mark(cls, year: int) -> tuple[str, str]:
        """(field_path, ON-state) for the line E "final Schedule K-1" mark.

        Additive like ``get_amended_mark``. Through 2023 Final and Amended are
        two independent checkboxes (1022 cb / 1023 cb); from 2024 they are TWO
        STATES OF ONE RADIO (1023 RB), so a K-1 cannot carry both
        (``final_and_amended_share_one_field``). Tokens per year, read from the
        template: 2024 '/1. A final Schedule K-1'; 2025 '/0' (the radio's /Opt
        lists final first, amended second, and the widgets sit left / right).
        """
        if year not in _FINAL_MARK_BY_YEAR:
            raise ValueError(
                f"No Schedule K-1 (100S) final mark for year {year}")
        return _FINAL_MARK_BY_YEAR[year]

    @classmethod
    def final_and_amended_share_one_field(cls, year: int) -> bool:
        """True when Final and Amended are states of one radio, so a single
        K-1 cannot be both."""
        return cls.get_final_mark(year)[0] == cls.get_amended_mark(year)[0]

    @classmethod
    def get_amended_mark(cls, year: int) -> tuple[str, str]:
        """(field_path, ON-state) for the line E "amended Schedule K-1" mark
        (§4a). ADDITIVE: independent of the ``_MAPPINGS`` value registry above.

        PER-YEAR — this is why on-states are never copied across years. Both
        the field PATH and the ON-state diverge (bare vs prefixed namespace,
        checkbox vs radio), each read off that year's own get_fields()/_States_
        (probe-tables §(d)):
          - 2021-23: '1023 cb', ON '/Yes'  (simple checkbox ['/Yes','/Off'])
          - 2024:    'Sch K-1 (100s) 1023 RB', ON '/(2) An amended Schedule K-1.'
                     (radio ['/1. A final Schedule K-1',
                             '/(2) An amended Schedule K-1.'])
          - 2025:    'Sch K-1 (100s) 1023 RB', ON '/1'  (radio ['/0','/1'])
        The orchestrator writes the ON token only when flagged amended; unset
        otherwise (radio /V then reads back as NOT the amended token).
        """
        if year not in _AMENDED_MARK_BY_YEAR:
            raise ValueError(
                f"No Schedule K-1 (100S) amended mark for year {year}")
        return _AMENDED_MARK_BY_YEAR[year]


_AMENDED_MARK_BY_YEAR: dict[int, tuple[str, str]] = {
    2021: ("1023 cb", "/Yes"),
    2022: ("1023 cb", "/Yes"),
    2023: ("1023 cb", "/Yes"),
    2024: ("Sch K-1 (100s) 1023 RB", "/(2) An amended Schedule K-1."),
    2025: ("Sch K-1 (100s) 1023 RB", "/1"),
}

_FINAL_MARK_BY_YEAR: dict[int, tuple[str, str]] = {
    2021: ("1022 cb", "/Yes"),
    2022: ("1022 cb", "/Yes"),
    2023: ("1022 cb", "/Yes"),
    2024: ("Sch K-1 (100s) 1023 RB", "/1. A final Schedule K-1"),
    2025: ("Sch K-1 (100s) 1023 RB", "/0"),
}
