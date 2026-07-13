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
# EMPTY: the S-corp emit pack is now complete — no cells owed. The final two
# gaps (federal f1120s / f1120s_k1 for 2021) were retired when the 2021
# federal emit slice landed (2021 inherits the marker-probe-verified 2022
# mappings). Both CA S-corp forms were already fully packed across all
# CA_SCORP_YEARS. The completeness gate now demands every catalog cell live.
KNOWN_GAPS: frozenset[tuple[str, str, int]] = frozenset()

# Amendment-tier gaps — a DISTINCT allowlist from KNOWN_GAPS above. The
# amendment pack is REVISION-keyed, not year-keyed, so these entries are
# (form, revision) 2-tuples (KNOWN_GAPS is a (juris, form, year) 3-tuple; the
# two shapes never mix). Same placeholder revision tags as
# years.AMENDMENT_TEMPLATE_REVISIONS so the keys match at runtime. Each entry
# is WORK OWED and is retired as its pack lands in Tasks 3-6.
AMENDMENT_KNOWN_GAPS: frozenset[tuple[str, str]] = frozenset({
    ("f1040x", "rev-2024-02"),
    ("schedule_x", "rev-2024"),
})  # pack lands in Tasks 3-6


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
