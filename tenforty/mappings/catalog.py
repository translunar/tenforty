# tenforty/mappings/catalog.py
"""Catalog of every PDF form: manifest form name -> mapping class +
blank-template stem. The completeness and fields-on-template gates iterate
this; it is deliberately explicit (no auto-discovery) so that adding a
form is a reviewed, one-line change — and a test asserts it stays in
lockstep with the manifest's form sets."""
from dataclasses import dataclass

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.mappings.pdf_4868 import Pdf4868
from tenforty.mappings.pdf_8959 import Pdf8959
from tenforty.mappings.pdf_f100s import PdfF100S
from tenforty.mappings.pdf_f100s_k1 import PdfF100SK1
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.mappings.pdf_f8949 import PdfF8949
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_a import PdfSchA
from tenforty.mappings.pdf_sch_b import PdfSchB
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.mappings.pdf_sch_d import PdfSchD
from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
from tenforty.mappings.pdf_sch_e import PdfSchE


@dataclass(frozen=True)
class FormEntry:
    mapping_cls: type
    template_stem: str


CATALOG: dict[tuple[str, str], FormEntry] = {
    ("federal", "1040"): FormEntry(Pdf1040, "f1040"),
    ("federal", "sch_1"): FormEntry(PdfSch1, "f1040s1"),
    ("federal", "sch_a"): FormEntry(PdfSchA, "f1040sa"),
    ("federal", "sch_b"): FormEntry(PdfSchB, "f1040sb"),
    ("federal", "sch_d"): FormEntry(PdfSchD, "f1040sd"),
    ("federal", "sch_e"): FormEntry(PdfSchE, "f1040se"),
    ("federal", "4562"): FormEntry(Pdf4562, "f4562"),
    ("federal", "4868"): FormEntry(Pdf4868, "f4868"),
    ("federal", "8959"): FormEntry(Pdf8959, "f8959"),
    ("federal", "f8582"): FormEntry(PdfF8582, "f8582"),
    ("federal", "f8949"): FormEntry(PdfF8949, "f8949"),
    ("federal", "f8962"): FormEntry(PdfF8962, "f8962"),
    ("federal", "f8995"): FormEntry(PdfF8995, "f8995"),
    ("federal", "f1120s"): FormEntry(PdfF1120S, "f1120s"),
    ("federal", "f1120s_k1"): FormEntry(PdfF1120SK1, "f1120s_k1"),
    ("california", "f100s"): FormEntry(PdfF100S, "f100s"),
    ("california", "f100s_k1"): FormEntry(PdfF100SK1, "f100s_k1"),
    ("california", "f540"): FormEntry(PdfF540, "f540"),
    ("california", "sch_ca"): FormEntry(PdfSchCa, "sch_ca"),
    ("california", "sch_d_540"): FormEntry(PdfSchD540, "sch_d_540"),
}

# Grid cells known to be incomplete, exempted from the gates so the suite
# stays green while the holes are real. Every entry here is WORK OWED —
# the proof-year plan (Phase A) empties the federal entries. Never add an
# entry without a comment saying what is missing.
#
# The S-corp emit pack and both CA S-corp forms are fully packed across all
# their respective years. f8962 (Form 8962, Premium Tax Credit) joined
# FEDERAL_FORMS with only a skeleton mapping (tenforty/mappings/pdf_f8962.py)
# — the real probe-certified template+mapping pack lands Task 6/7. Until
# then every f8962 cell is allowlisted here, including the 2021 compute-only
# "loud extra" slice (see tests/test_year_completeness_gate.py's dedicated
# f8962-2021 test).
KNOWN_GAPS: frozenset[tuple[str, str, int]] = frozenset({
    ("federal", "f8962", 2021),  # f8962 pack (template+probe+mapping) lands Task 6/7
    ("federal", "f8962", 2022),  # f8962 pack (template+probe+mapping) lands Task 6/7
    ("federal", "f8962", 2023),  # f8962 pack (template+probe+mapping) lands Task 6/7
    ("federal", "f8962", 2024),  # f8962 pack (template+probe+mapping) lands Task 6/7
    ("federal", "f8962", 2025),  # f8962 pack (template+probe+mapping) lands Task 6/7
})

# Amendment-tier gaps — a DISTINCT allowlist from KNOWN_GAPS above. The
# amendment tier is MIXED-keyed, so this frozenset would hold two key SHAPES:
#   - f1040x is REVISION-keyed → ("f1040x", revision)  e.g. ("f1040x", "rev-2025-12")
#   - schedule_x is YEAR-keyed → ("schedule_x", year)  e.g. ("schedule_x", 2024)
# i.e. (str, str) for f1040x and (str, int) for schedule_x. (KNOWN_GAPS above is
# a (juris, form, year) 3-tuple; none of these three shapes collide.)
#
# EMPTY: the amendment tier is now fully live with ZERO allowlisted cells. The
# f1040x revision pack landed in Task 6a; the five per-year CA Schedule X
# mappings (2021-2025, three field-namespace shapes, each probe-certified from
# its own template's get_fields) landed in Task 6b. The completeness gate now
# demands every amendment cell live — template + probe + mapping for the
# f1040x revision and for every years.amendable_california_years() Schedule X.
AMENDMENT_KNOWN_GAPS: frozenset[tuple[str, str] | tuple[str, int]] = frozenset()


def _collect_string_leaves(payload: object, out: set[str]) -> None:
    """Every string leaf in a mapping payload is a PDF field path — the
    payload shapes in this package (flat dicts, scalars+repeaters trees)
    hold nothing else at string-leaf positions."""
    if isinstance(payload, str):
        out.add(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            _collect_string_leaves(value, out)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            _collect_string_leaves(value, out)


def field_paths(entry: FormEntry, year: int) -> set[str]:
    """Every PDF field name the mapping references for a year.

    The genuine PDF-field-name sources are: the string leaves of
    get_mapping (its values), and the KEYS of get_aggregations and
    get_derivations (both keyed by the emitted PDF field). get_suppressed
    and get_checkbox_states are deliberately NOT included: both key by
    SEMANTIC field name, not PDF path. A suppressed field is not emitted at
    all, so no PDF path exists to verify; a checkbox state's field is itself
    a mapped field (guaranteed by CheckboxStatesAreMappedTests), so its PDF
    path is already verified via the mapping leaves. Including their semantic
    keys here would compare them against the template's PDF names and always
    fail — a category error, not a real gap."""
    paths: set[str] = set()
    _collect_string_leaves(entry.mapping_cls.get_mapping(year), paths)
    cls = entry.mapping_cls
    if hasattr(cls, "get_aggregations"):
        paths.update(cls.get_aggregations(year).keys())
    if hasattr(cls, "get_derivations"):
        paths.update(cls.get_derivations(year).keys())
    return paths
