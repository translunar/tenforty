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
# their respective years. f8962 (Form 8962, Premium Tax Credit) is now fully
# packed too — the probe-certified year-keyed mapping
# (tenforty/mappings/pdf_f8962.py) landed in Task 7, so its five formerly
# allowlisted cells (2021-2025, including the 2021 compute-only "loud extra"
# slice) are retired: the completeness + fields-on-template gates now demand
# and verify the real pack.
#
# 2021 individual-return emit packs: 2021 moved from FEDERAL_COMPUTE_ONLY_YEARS
# into FEDERAL_YEARS (federal-2021-emit Task 1), so the completeness gate now
# demands a template + mapping for every 2021 individual form. f8962's 2021 pack
# already landed (Task 7), so it is NOT gapped here; the remaining twelve forms
# owe their 2021 emit packs, built in federal-2021-emit Tasks 2-3.
#
# sch_d_540 2021 retired: fresh air-gapped probe (controller-verified, "Text
# Field N" namespace — a fourth distinct FTB naming scheme, disjoint from
# 2023's bare numbers and 2024/2025's prefixed schemes) landed in
# tenforty/mappings/pdf_sch_d_540.py; fields-on-template + emit gates now
# cover 2021.
KNOWN_GAPS: frozenset[tuple[str, str, int]] = frozenset({
    # f1040 2021 retired: fresh air-gapped probe + render-verify (controller +
    # team-lead-verified 57/57 keys, income block nests in Lines1-11_ReadOrder[0],
    # single line-1 wages box f1_28 per team-lead ruling; 8 wage sub-line keys
    # deliberately unmapped — compute-dead AND the 2021 form lacks 1a-1z) landed
    # in tenforty/mappings/pdf_1040.py; completeness + fields-on-template + emit
    # gates now cover 2021 — the LAST 2021 individual form, gate fully green.
    # sch_1 2021 retired: fresh air-gapped probe (controller-verified 16/16 keys,
    # form1[0] namespace, line-10 total → f1_31 vs 2022's f1_36 which is absent on
    # 2021 — the 8a-8z sub-lines that shifted it were added after 2021) landed in
    # tenforty/mappings/pdf_sch_1.py; fields-on-template + emit gates now cover 2021.
    # 4562 2021 retired: fresh-probe mapping (controller-verified 42/42 keys,
    # compute-letter 19i/19j → residential/nonresidential rows Line19h_1/Line19i_1,
    # no 50-year 19h row on the 2021 form) landed in tenforty/mappings/pdf_4562.py;
    # fields-on-template + emit gates now cover 2021.
    # Retired by federal-2021-emit Task 3 (INHERIT batch): sch_a, 4868, 8959,
    # f8582, f8949, f8995 — 2021 field tree diff_pdf_fields-IDENTICAL to 2022,
    # mapping inherits the 2022 payload; fields-on-template + emit gates now cover 2021.
    # sch_b 2021 retired: fresh-probe mapping (controller-verified 66/66 keys)
    # landed in tenforty/mappings/pdf_sch_b.py; fields-on-template + emit gates
    # now cover 2021.
    # sch_d 2021 retired: fresh-probe mapping (controller-verified 38/38 keys,
    # lines 18/19 content-corrected vs the merged-2022-2025 swap bug) landed in
    # tenforty/mappings/pdf_sch_d.py; fields-on-template + emit gates now cover 2021.
    # sch_e 2021 retired: fresh-probe render-verified mapping (60 mapped incl.
    # corrected name/ein cols a/d; 12 deliberately-unmapped — 8 entity-type P/S
    # → compute-side follow-up, 4 line-29 dead cross keys) landed in
    # tenforty/mappings/pdf_sch_e.py; fields-on-template + emit gates now cover 2021.
    #
    # CA 2021/2022 individual-return emit packs: 2021 and 2022 moved from
    # CALIFORNIA_COMPUTE_ONLY_YEARS into CALIFORNIA_YEARS (ca-2021-2022-emit
    # Task 1), so the completeness gate now demands a template + mapping for
    # every 2021/2022 California form. The f540/sch_ca/sch_d_540 templates
    # already exist, but their probe-certified year mappings are owed —
    # built in ca-2021-2022-emit Tasks 2-3. Six cells:
    # f540 2021 retired: direct-map-only fresh air-gapped probe (controller-
    # reconciled 25/25 cells against the 2021 template; CA namespace differs
    # from 2023) landed in tenforty/mappings/pdf_f540.py; fields-on-template +
    # emit gates now cover 2021.
    # sch_ca 2021 retired: direct-map-only fresh air-gapped probe (controller-
    # reconciled 57/57 cells against the 2021 template; bare-numeric CA
    # namespace that does NOT align field-for-field with 2022/2023, hence a
    # fresh map not an inherit) landed in tenforty/mappings/pdf_sch_ca.py.
    # Zero-derivation (allowlisted in ZERO_DERIVATION_FORMS); completeness +
    # fields-on-template + emit gates now cover sch_ca/2021.
    # f540 2022 retired: direct-map probe (25/25 controller-reconciled, CA
    # bare-numeric namespace matching 2023 except sign-block email/phone 5019/5020)
    # + 22-cell get_derivations surface ported from 2023 (line 64 total-tax
    # composition, NO 2021-style line-65/APAS insertion) landed in
    # tenforty/mappings/pdf_f540.py; completeness + derivations-surface +
    # fields-on-template gates now cover f540/2022.
    # sch_ca + sch_d_540 2022 retired (INHERIT batch): 2022 field tree
    # diff_pdf_fields-IDENTICAL to 2023, mapping inherits the 2023 payload;
    # fields-on-template + emit gates now cover 2022.
})

# Forms that legitimately carry NO get_derivations in ANY year — Schedule CA's
# adjustments are all direct-mapped; a form here is exempt from the
# derivations-surface completeness check (test_derivations_surface_complete).
# The check otherwise requires that a form carrying derivations in ANY supported
# non-gapped year carries them in EVERY such year; a genuinely derivation-free
# form has no anchor year and would pass trivially, but is listed explicitly so
# the intent is reviewed — and the gate re-guards each entry, reddening if a
# listed form ever grows a derivation.
ZERO_DERIVATION_FORMS: frozenset[tuple[str, str]] = frozenset({
    ("california", "sch_ca"),
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
