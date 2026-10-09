import dataclasses
import math
from collections.abc import Mapping
from pathlib import Path

import yaml

from tenforty.attestations import enforce_compute_time
from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.forms import f1040 as form_1040
from tenforty.forms import f4868 as form_4868
from tenforty.forms import f8949 as form_f8949
from tenforty.forms import sch_1 as form_sch_1
from tenforty.forms import sch_2 as form_sch_2
from tenforty.forms import sch_a as form_sch_a
from tenforty.forms import sch_b as form_sch_b
from tenforty.forms import sch_c as form_sch_c
from tenforty.forms import sch_d as form_sch_d
from tenforty.forms import sch_e as form_sch_e
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.forms import sch_se as form_sch_se
from tenforty.forms import f4562 as form_4562
from tenforty.forms import f8959 as form_8959
from tenforty.forms import f8962 as form_f8962
from tenforty.forms import f8995 as form_f8995
from tenforty.forms import f8582 as form_f8582
from tenforty.params import f8962 as params_f8962
from tenforty.forms import f1120s as form_f1120s
from tenforty.forms import f100s as form_f100s
from tenforty.forms import f100s_k1 as form_f100s_k1
from tenforty.forms import sch_ca as form_sch_ca
from tenforty.ca_divergences import (
    check_unaddressed_divergences,
    entry_citation,
    resolve_divergence_id,
)
from tenforty.models import (
    DivergenceSource, validate_sche_1099_answers, validate_tax_year_dates,
    validate_third_party_designee,
    validate_unclaimed_property)
from tenforty.forms import sch_d_540 as form_sch_d_540
from tenforty.forms import f540 as form_f540
from tenforty.filing.pdf import PdfFiller
from tenforty.params import ca_scorp
from tenforty.oracle.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_4868 import Pdf4868
from tenforty.mappings.pdf_sch_b import PdfSchB
from tenforty.mappings.pdf_sch_d import PdfSchD
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_2 import PdfSch2
from tenforty.mappings.pdf_sch_a import PdfSchA
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.mappings.pdf_sch_se import PdfSchSe
from tenforty.mappings.pdf_sch_e import PdfSchE
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.mappings.pdf_8959 import Pdf8959
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.mappings.pdf_f8949 import BoxLetter, PdfF8949
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.filing.statement_199a import render_199a_statement_a
from tenforty.filing.statement_other_deductions import (
    render_ca_100s_other_deductions_statement,
    render_other_deductions_statement,
)
from tenforty.mappings.pdf_f100s import PdfF100S
from tenforty.mappings.pdf_f100s_k1 import PdfF100SK1
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.mappings.pdf_f540 import interest_and_penalties_must_be_stated
from tenforty.mappings.pdf_f540 import AMENDED_RETURN_KEY, AMENDED_RETURN_ON
from tenforty.mappings.pdf_f1040x import PdfF1040X
from tenforty.mappings.pdf_schedule_x import PdfScheduleX
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
from tenforty.models import (
    AmendmentCase,
    CA540Return,
    EntityType,
    FilingStatus,
    ItemizedDeductions,
    K1Allocation,
    K1AllocationEntity,
    K1AllocationShareholder,
    K1FanoutData,
    RentalProperty,
    Scenario,
    ScheduleK1,
)
from tenforty.types import UpstreamState

_PDFS_ROOT = Path(__file__).parent.parent / "pdfs"


# CA-state PDF emit table: (basename, mapping_class). Drives the
# uniform fill loop in `_emit_ca_pdfs_internal` — each entry produces
# `<basename>_<year>.pdf` from the year-keyed mapping/aggregations/
# derivations/checkbox_states on the mapping class. `sch_d_540` is
# conditional: it is skipped unless `form_sch_d_540.is_required`.
_CA_FORMS_BY_BASENAME: tuple[tuple[str, type], ...] = (
    ("f540", PdfF540),
    ("sch_ca", PdfSchCa),
    ("sch_d_540", PdfSchD540),
)


def _flatten_sch_b_rows(sch_b_values: dict) -> dict:
    """Convert sch_b.compute's payer-lists into the flat row slots that the
    Sch B PDF mapping expects (interest_payer_{i}, interest_amount_{i}, and
    the matching dividend_* keys). All scalar keys pass through unchanged."""
    flat = {
        k: v for k, v in sch_b_values.items()
        if k not in ("interest_payers", "dividend_payers")
    }
    for i, row in enumerate(sch_b_values.get("interest_payers", []), start=1):
        flat[f"interest_payer_{i}"] = row["payer"]
        flat[f"interest_amount_{i}"] = row["amount"]
    for i, row in enumerate(sch_b_values.get("dividend_payers", []), start=1):
        flat[f"dividend_payer_{i}"] = row["payer"]
        flat[f"dividend_amount_{i}"] = row["amount"]
    return flat


def _make_k1_from_1120s_allocation(alloc: K1Allocation) -> ScheduleK1:
    """Build a ScheduleK1 instance from a 1120-S computed allocation.

    The 1120-S pipeline produces typed `K1Allocation` dataclasses; the
    1040 pipeline's Sch E Part II compute consumes `ScheduleK1` dataclass
    instances. This is the bridge.

    Carries box 1 (ordinary business income) and box 17 code V (QBI). All
    other ScheduleK1 fields are zero because K1Allocation has no source
    for them — the v1 Schedule K compute is line-1-only — not because the
    bridge drops them.
    """
    return ScheduleK1(
        entity_name=alloc.entity.name,
        entity_ein=alloc.entity.ein,
        entity_type=EntityType.S_CORP,
        material_participation=True,  # v1 default; caller-configurable later
        ordinary_business_income=alloc.box_1_ordinary_business_income,
        # Box 17 code V. Without this the emitted K-1 and its §199A
        # Statement A report QBI of $X while the shareholder's Form 8995
        # sees $0 — the same filing contradicting itself. `box_17v_qbi` is
        # an int (irs_round); qbi_amount is typed float, so convert
        # explicitly rather than letting an int land in a float field.
        qbi_amount=float(alloc.box_17v_qbi),
    )


def _flatten_k1_party(
    prefix: str,
    party: K1AllocationEntity | K1AllocationShareholder,
) -> dict:
    """Flatten a typed K-1-allocation party (entity or shareholder) into
    the prefixed flat keys the K-1 PDF mapping expects.

    The IRS Schedule K-1 PDF combines name, street, city, state, and ZIP
    into a single multi-line text area per party (Part I field B for the
    corporation, Part II field F1 for the shareholder). This helper
    pre-assembles the combined string here so the PDF mapping can stay a
    flat 1:1 dict (one compute key, one PDF cell) instead of needing a
    multi-key string-aggregation pattern in the mapping registry.

    Disambiguation between entity and shareholder uses `isinstance`
    (not `hasattr`): if a future shareholder gains an EIN field — some
    shareholders are entities themselves (trusts, ESOPs) — `hasattr`
    would emit both keys silently. `isinstance` dispatch on the typed
    discriminator surfaces design changes as type errors.

    Render note: the assembled string is

        Name
        Street
        City, ST ZIP

    (newline-separated). After the first end-to-end PDF emit
    succeeds, eyeball the rendered K-1 against the IRS form to confirm
    the cell wraps this format cleanly. If the cell is single-line or
    the form expects a different separator, change the joiner here —
    the mapping shape stays the same.
    """
    name_and_address = (
        f"{party.name}\n"
        f"{party.address.street}\n"
        f"{party.address.city}, {party.address.state} {party.address.zip_code}"
    )
    flat: dict = {
        f"{prefix}_name_and_address": name_and_address,
    }
    if isinstance(party, K1AllocationEntity):
        flat[f"{prefix}_ein"] = party.ein
    elif isinstance(party, K1AllocationShareholder):
        flat[f"{prefix}_ssn_or_ein"] = party.ssn_or_ein
    else:
        raise TypeError(
            f"_flatten_k1_party received unexpected party type: "
            f"{type(party).__name__}"
        )
    return flat


def _format_mmddyyyy(d) -> str:
    """A date as the IRS printed-form convention MM/DD/YYYY (2020-01-01 ->
    "01/01/2020"), for the 1120-S header items A and E."""
    return d.strftime("%m/%d/%Y")


def _entity_header_values(r) -> dict:
    """Entity identity values for the Form 1120-S page-1 header block, keyed by
    the ``f1120s_entity_*`` names ``PdfF1120S.get_entity_header_fields`` maps.

    Injected at emit from the SCorpReturn (like the CA 100S identity block),
    not produced by ``f1120s.compute``. A superset is returned: the 2021-2024
    forms print one combined "City, ST ZIP" cell while 2025 splits city / state
    / ZIP, and each year's mapping consumes only the keys it has a cell for."""
    a = r.address
    return {
        "f1120s_entity_name": r.name,
        "f1120s_entity_street": a.street,
        "f1120s_entity_city_state_zip": f"{a.city}, {a.state} {a.zip_code}",
        "f1120s_entity_city": a.city,
        "f1120s_entity_state": a.state,
        "f1120s_entity_zip": a.zip_code,
        "f1120s_entity_ein": r.ein,
        "f1120s_entity_s_election_date":
            _format_mmddyyyy(r.s_election_effective_date),
        "f1120s_entity_date_incorporated": _format_mmddyyyy(r.date_incorporated),
        "f1120s_entity_total_assets": r.total_assets,
        "f1120s_entity_shareholder_count": len(r.shareholders),
        "f1120s_officer_title": r.officer_title,
        **_tax_year_header_values(r),
    }


def _unclaimed_property_values(ca) -> dict:
    """Item U(2) date and U(3) dollars / cents, only after a stated "Yes"
    (``validate_unclaimed_property`` has already enforced the dependency)."""
    if ca.filed_unclaimed_property_report is not True:
        return {}
    total_cents = round(ca.unclaimed_property_amount_remitted * 100)
    return {
        "f100s_entity_unclaimed_date": ca.unclaimed_property_report_date,
        "f100s_entity_unclaimed_dollars": total_cents // 100,
        "f100s_entity_unclaimed_cents": f"{total_cents % 100:02d}",
    }


def _k1_tax_year_header_values(r) -> dict:
    """Schedule K-1 (1120-S) header month / day / four-digit-year boxes."""
    b, e = r.tax_year_beginning, r.tax_year_ending
    if b is None or e is None:
        return {}
    return {
        "k1_tax_year_begin_month": b.strftime("%m"),
        "k1_tax_year_begin_day": b.strftime("%d"),
        "k1_tax_year_end_month": e.strftime("%m"),
        "k1_tax_year_end_day": e.strftime("%d"),
        "k1_tax_year_end_year": e.strftime("%Y"),
    }


def _tax_year_header_values(r) -> dict:
    """Short-year header date values for the 1120-S page 1 header cells
    (month/day strings plus the two-digit ending year); {} for a calendar year."""
    b, e = r.tax_year_beginning, r.tax_year_ending
    if b is None or e is None:
        return {}
    return {
        "f1120s_tax_year_begin_md": b.strftime("%m/%d"),
        "f1120s_tax_year_end_md": e.strftime("%m/%d"),
        "f1120s_tax_year_end_yy": e.strftime("%y"),
    }


def _format_rate_percent(rate: float) -> str:
    """Franchise-tax rate as the Form 100S line-21 percentage box prints it:
    0.015 -> "1.5"."""
    return f"{rate * 100:g}"


def _split_ownership_percent(fraction: float) -> tuple[str, str]:
    """Schedule K-1 (100S) Item A renders the allocation % as two boxes,
    "<whole>.<frac>%". Split an ownership fraction (0-1) into the integer part
    and a two-digit fractional part: 1.0 -> ("100", "00"); 0.6 -> ("60", "00");
    0.29 -> ("29", "00"). Uses integer arithmetic on hundredths-of-a-percent
    (rather than float truncation) so the fractional box is structurally
    always two digits in 00-99, never "100"."""
    hundredths = round(fraction * 10000)  # total hundredths of a percent
    whole, frac = divmod(hundredths, 100)
    return str(whole), f"{frac:02d}"


def _ca540_to_yaml_dict(ca540: CA540Return) -> dict:
    """Serialize a CA540Return to a plain dict suitable for YAML emission.

    Called only by ``_emit_ca_resolved_snapshot``; not intended for use
    outside the resolved-snapshot writer path.
    """
    return {
        "estimated_payments": ca540.estimated_payments,
        "use_tax": ca540.use_tax,
        "estimated_tax_penalty": ca540.estimated_tax_penalty,
        "interest_and_penalties": ca540.interest_and_penalties,
        "ptet_credit": ca540.ptet_credit,
        "rrb_tier_1_2_amount": ca540.rrb_tier_1_2_amount,
        "pfl_amount": ca540.pfl_amount,
        "voluntary_contributions": [
            # Same keys the CA YAML loader reads, so the snapshot's list can
            # be pasted back into a `ca540:` block.
            {"fund_code": v.fund_code, "amount": v.amount}
            for v in ca540.voluntary_contributions
        ],
        "divergences": [
            {
                "source": d.source.name,
                "sch_ca_line": d.sch_ca_line,
                "direction": d.direction.name,
                "amount": d.amount,
                "description": d.description,
                "federal_source": d.federal_source,
                "pub1001_ref": d.pub1001_ref,
                "catalog_id": d.catalog_id,
                "note": d.note,
            }
            for d in ca540.divergences
        ],
    }


def _scenario_with_effective_itemized(scenario: Scenario) -> Scenario:
    """Return a Scenario whose itemized_deductions field is populated.

    YAML fixtures use ``form1098s`` (a list of Form1098 objects) to carry
    mortgage interest and property tax.  ``forms.sch_a.compute`` reads from
    ``scenario.itemized_deductions`` (an ItemizedDeductions dataclass).  This
    helper bridges the two representations so the native sch_a compute path
    works for both fixture styles without mutating the caller's scenario.

    Merging rules:
    - If ``scenario.itemized_deductions`` is already set, return the scenario
      unchanged (direct itemized_deductions takes precedence; callers that set
      both are already signalling their intent).
    - If ``scenario.form1098s`` is non-empty, synthesize an ItemizedDeductions
      from the summed mortgage_interest and property_tax across all 1098s.
      Other ItemizedDeductions fields (medical, state income tax, charity) are
      left at 0.0 — they are not carried on Form 1098.
    - If neither is set, return the scenario unchanged (no itemized deductions).
    """
    if scenario.itemized_deductions is not None:
        return scenario
    if not scenario.form1098s:
        return scenario
    total_mortgage = sum(f.mortgage_interest for f in scenario.form1098s)
    total_property_tax = sum(f.property_tax for f in scenario.form1098s)
    effective_itemized = ItemizedDeductions(
        mortgage_interest=total_mortgage,
        property_tax=total_property_tax,
    )
    return dataclasses.replace(scenario, itemized_deductions=effective_itemized)


def _k1_positive_income(k1: ScheduleK1) -> float:
    """Sum of a K-1's income boxes, each clamped at 0 — a loss in one box never
    lowers the estimate. Used only by the cheap EIC-ceiling gate, where an
    overestimate is safe (see _scenario_in_spine_scope)."""
    return sum(max(0.0, v) for v in (
        k1.ordinary_business_income,
        k1.net_rental_real_estate,
        k1.other_net_rental,
        k1.interest_income,
        k1.ordinary_dividends,
        k1.royalties,
        k1.net_short_term_capital_gain,
        k1.net_long_term_capital_gain,
        k1.other_income,
    ))


def _rental_net_income(r: RentalProperty) -> float:
    """Net rental income (rents received − all deductible Schedule E expenses)."""
    return r.rents_received - (
        r.advertising + r.auto_and_travel + r.cleaning_and_maintenance
        + r.commissions + r.insurance + r.legal_and_professional_fees
        + r.management_fees + r.mortgage_interest + r.other_interest
        + r.repairs + r.supplies + r.taxes + r.utilities
        + r.depreciation + r.other_expenses
    )


# The K-1 boxes that carry business income or loss onto Schedule E Part II.
_K1_BUSINESS_BOXES = (
    "ordinary_business_income", "net_rental_real_estate", "other_net_rental",
    "royalties", "other_income",
)


def aggregate_business_losses(scenario: Scenario) -> int:
    """Sum of every LOSS-positioned business item on the return, as a
    positive whole-dollar number, with NO netting of business income against
    it: each Schedule C business's net loss, each K-1 business box that is
    negative, and each Schedule E rental property's net loss.

    This is the quantity the IRC §461(l) guard compares to the threshold. It
    is a deliberate SUPERSET of the true excess-business-loss base (which
    nets business income and gains against the deductions): leaving the
    income out can only make the sum larger, so the guard can over-refuse
    but can never pass a return whose loss the limitation would cut. Inputs
    are read before the passive-loss and at-risk rules for the same reason.

    WHOLE DOLLARS, never below what the forms print. The forms round entry
    lines one by one, so a printed loss can exceed the raw arithmetic by a
    dollar or more; summing raw floats would let a return through whose
    printed loss is over the threshold. So: a Schedule C business contributes
    its PRINTED line 31, a rental property its PRINTED Schedule E line 21,
    and each K-1 loss box is rounded UP (the K-1 row prints its boxes netted
    and its two rental boxes combined, so no per-box rounding matches the
    page; the ceiling is never less than what any of those prints)."""
    sch_c = sum(max(0, -form_sch_c.printed_net_profit(biz))
                for biz in scenario.schedule_c_businesses)
    k1 = sum(math.ceil(max(0.0, -getattr(k, box)))
             for k in scenario.schedule_k1s for box in _K1_BUSINESS_BOXES)
    rental = sum(max(0, -form_sch_e.printed_rental_net(r))
                 for r in scenario.rental_properties)
    return sch_c + k1 + rental


@dataclasses.dataclass(frozen=True)
class _FederalFormSpec:
    """One federal individual-return form's fully-prepared emit unit, WITHOUT
    rendering. Built by ``_federal_individual_emit_specs`` so both the full-set
    emit (``_emit_pdfs_internal``) and the selective amendment emit
    (``run_amendment_packet``) drive the SAME per-form path — one fills every
    spec, the other fills only the selector-chosen subset.

    ``name`` is the stable form identifier used both as the ``emit`` dict key
    (preserving the historic keys the emit tests assert) AND as the changed-forms
    selector's form name. ``kind`` is ``"flat"`` (PdfFiller.fill / resolve_fields)
    or ``"repeater"`` (fill_with_repeaters / _expand_repeaters); ``mapping`` and
    ``values`` are that form's already-computed emit inputs.
    """

    name: str
    template: Path
    output_name: str
    kind: str  # "flat" | "repeater"
    mapping: dict
    values: dict
    # Optional flat-fill extras (default empty): a form whose emit needs
    # XFA checkbox on-states (bool compute key -> "/N") and/or derived cells
    # (PDF path -> lambda(values)) carries them here so both the render and
    # the changed-forms-selector payload see the same fields. "repeater"
    # specs ignore these.
    checkbox_states: dict = dataclasses.field(default_factory=dict)
    derivations: dict = dataclasses.field(default_factory=dict)
    # compute key -> format spec overriding the whole-dollar render (rates).
    field_formats: dict = dataclasses.field(default_factory=dict)


# Standing caveat (spec §4): the changed-forms selector compares two
# tenforty-computed pictures, so it structurally CANNOT see a form the filed
# return carried that tenforty does not model. Always printed on the manifest.
_ERRONEOUS_INCLUSION_CAVEAT: str = (
    "Selection compares tenforty-computed as-filed vs corrected; a form the "
    "filed return included that tenforty does not model cannot be detected "
    "here — preparer must confirm."
)

# Federal compute-only year (years.FEDERAL_COMPUTE_ONLY_YEARS): the 1040-X
# emits, but no year-keyed individual-form PDFs exist to attach.
_FEDERAL_COMPUTE_ONLY_NOTE: str = (
    "compute-only year: individual-form attachment emit unavailable; "
    "preparer supplies changed forms."
)

# CA compute-only year (years.CALIFORNIA_COMPUTE_ONLY_YEARS): Schedule X emits
# (year packs exist for every amendable CA year), but the COMPLETE amended 540
# — which per spec §3 IS the CA amendment — cannot emit (540 emit needs a
# CALIFORNIA_YEARS pack). A materially bigger hole than the federal note, so it
# gets its own distinct line.
_CA_COMPUTE_ONLY_NOTE: str = (
    "amended Form 540 must be prepared separately; only Schedule X emitted."
)

# §4a: a flagged CA S-corp run marks the corrected 100S + K-1(100S) as amended,
# but the CA S-corp AMENDMENT itself files on Form 100X — which tenforty does
# not emit. This LOUD note is dropped into the output dir so the preparer can
# never mistake the emitted corrected return for the whole filing.
_CA_SCORP_100X_NOTE: str = (
    "CA S-CORP AMENDMENT — READ FIRST\n"
    "================================\n\n"
    "CA S-corp amendment files on Form 100X, which tenforty does not emit; "
    "the amended-marked Form 100S + K-1(100S) emitted here are the complete "
    "corrected return that accompanies a preparer-completed 100X.\n"
)


@dataclasses.dataclass(frozen=True)
class MailedFile:
    """One file in the amendment mailing packet: its filename, a short
    human description, and WHY it is included ("changed" / "new" /
    "amendment form" / "complete amended return")."""

    filename: str
    description: str
    reason: str


@dataclasses.dataclass(frozen=True)
class CADivergenceRow:
    """One rendered Schedule CA divergence line for the packet manifest: the
    catalog id, its description, its source citation, and — when applicable —
    the applied amount and the filer's provenance note."""

    catalog_id: str
    description: str
    citation: str
    amount: float | None = None
    note: str | None = None


@dataclasses.dataclass(frozen=True)
class CADivergenceTrail:
    """The three-bucket audit trail of Schedule CA divergences on a return
    (spec §2.6): what the catalog auto-applied, what the filer supplied, and
    what the filer examined and dismissed as not applicable."""

    auto_applied: tuple[CADivergenceRow, ...] = ()
    user_supplied: tuple[CADivergenceRow, ...] = ()
    reviewed_not_applicable: tuple[CADivergenceRow, ...] = ()

    @classmethod
    def build(
        cls, ca540: CA540Return, federal_results: dict, year: int,
    ) -> "CADivergenceTrail":
        """Materialize the trail from a resolved CA return.

        - Auto-applied: the CATALOG_AUTO divergences that fired
          (``derive_auto_divergences``), each with its amount + catalog citation.
        - User-supplied: the id-keyed USER divergences on ``ca540``, each with
          its amount, citation, and note.
        - Reviewed-not-applicable: ``ca540.reviewed_divergence_ids``, resolved to
          catalog entries for description + citation.
        """
        auto = tuple(
            CADivergenceRow(
                catalog_id=d.catalog_id,
                description=d.description,
                citation=entry_citation(resolve_divergence_id(year, d.catalog_id)),
                amount=d.amount,
            )
            for d in form_sch_ca.derive_auto_divergences(
                federal_results, year, ca540=ca540)
        )
        user = tuple(
            CADivergenceRow(
                catalog_id=d.catalog_id,
                description=d.description,
                citation=(
                    entry_citation(resolve_divergence_id(year, d.catalog_id))
                    if d.catalog_id is not None else (d.pub1001_ref or "")
                ),
                amount=d.amount,
                note=d.note,
            )
            for d in ca540.divergences
            if d.source is DivergenceSource.USER
        )
        reviewed = tuple(
            CADivergenceRow(
                catalog_id=entry.id,
                description=entry.description,
                citation=entry_citation(entry),
            )
            for entry in (
                resolve_divergence_id(year, rid)
                for rid in ca540.reviewed_divergence_ids
            )
        )
        return cls(
            auto_applied=auto,
            user_supplied=user,
            reviewed_not_applicable=reviewed,
        )


@dataclasses.dataclass(frozen=True)
class PacketManifest:
    """The printed contents of an amendment mailing packet (spec §6).

    ``mailed_files`` is every file that mails, each tagged with why. ``dropped``
    is the team-lead-ruled class of forms the FILED return carried that the
    corrected return no longer needs (not attached — noted for the preparer's
    explanation). ``caveats`` always carries the spec §4 erroneous-inclusion
    caveat, plus any compute-only notes and the empty-selection note. ``render``
    produces the human-readable ``packet_manifest.txt`` body.
    """

    year: int
    mailed_files: tuple[MailedFile, ...]
    dropped: tuple[str, ...]
    caveats: tuple[str, ...]
    ca_divergences: CADivergenceTrail = dataclasses.field(
        default_factory=CADivergenceTrail)
    # The assembled amendment-form values the packet was filled from: every
    # ``forms.f1040x.assemble`` key and, when the packet has a CA side, every
    # ``forms.schedule_x.assemble_ca`` key, in one flat dict (the two key sets
    # are disjoint by prefix). For callers that summarize a packet; NOT part of
    # the printed manifest, nor of equality or hashing.
    values: Mapping[str, object] = dataclasses.field(
        default_factory=dict, compare=False, repr=False)

    def render(self) -> str:
        lines: list[str] = [
            f"Amendment packet manifest — tax year {self.year}",
            "=" * 60,
            "",
            "Files to mail:",
        ]
        for mf in self.mailed_files:
            lines.append(f"  - {mf.filename}: {mf.description} [{mf.reason}]")
        lines.append("")
        lines.append("Forms no longer applicable (NOT attached):")
        if self.dropped:
            for form in self.dropped:
                lines.append(
                    f"  - {form}: no longer applies — not attached; preparer "
                    f"notes in explanation."
                )
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append("Caveats:")
        for caveat in self.caveats:
            lines.append(f"  - {caveat}")
        lines.append("")
        lines.extend(self._render_ca_divergences())
        return "\n".join(lines)

    def _render_ca_divergences(self) -> list[str]:
        """The CA Schedule CA divergences section (spec §2.6): three buckets,
        each row carrying its citation. Rendered deterministically; an empty
        bucket prints ``(none)`` so the trail is auditable even when a return
        has no divergence in a given bucket (or no CA side at all)."""
        trail = self.ca_divergences
        lines = ["California Schedule CA divergences:"]

        lines.append("  Auto-applied (catalog-derived):")
        if trail.auto_applied:
            for r in trail.auto_applied:
                lines.append(
                    f"    - {r.catalog_id}: {r.description} "
                    f"— ${r.amount:,.2f} [{r.citation}]"
                )
        else:
            lines.append("    (none)")

        lines.append("  User-supplied:")
        if trail.user_supplied:
            for r in trail.user_supplied:
                note = f" — note: {r.note}" if r.note else ""
                lines.append(
                    f"    - {r.catalog_id}: {r.description} "
                    f"— ${r.amount:,.2f} [{r.citation}]{note}"
                )
        else:
            lines.append("    (none)")

        lines.append("  Reviewed and not applicable:")
        if trail.reviewed_not_applicable:
            for r in trail.reviewed_not_applicable:
                lines.append(
                    f"    - {r.catalog_id}: {r.description} [{r.citation}]"
                )
        else:
            lines.append("    (none)")

        lines.append("")
        return lines


class ReturnOrchestrator:
    """Coordinates computation across forms in dependency order."""

    def __init__(self, spreadsheets_dir: Path, work_dir: Path) -> None:
        self.spreadsheets_dir = spreadsheets_dir
        self.work_dir = work_dir
        self.engine = SpreadsheetEngine()

    def _build_effective_scenario(
        self, scenario: Scenario,
    ) -> tuple[Scenario, dict[str, object]]:
        """Build the effective scenario for the 1040 pipeline.

        When `scenario.s_corp_return` is set, runs the corporate pipeline and
        appends the synthesized K-1(s) to a copy of the input scenario. The
        caller's scenario is never mutated. Returns a tuple of
        (effective_scenario, corp_results). For non-S-corp scenarios returns
        (scenario, {}) unchanged.
        """
        if scenario.s_corp_return is None:
            return scenario, {}

        corp_results = self.compute_corporate(scenario)
        extra_k1s = [
            _make_k1_from_1120s_allocation(alloc)
            for alloc in corp_results.get("f1120s_sch_k1_allocations", [])
        ]
        effective_scenario = dataclasses.replace(
            scenario,
            schedule_k1s=list(scenario.schedule_k1s) + extra_k1s,
        )
        # Re-run compute-time gates against the effective scenario.
        # Any K-1-related gate (e.g., the >4 K-1s scope-out from
        # Plan D's Sch E Part II) must see the FULL list including
        # the just-appended computed K-1s, not just the original.
        enforce_compute_time(effective_scenario)
        return effective_scenario, corp_results

    def _scenario_in_spine_scope(self, effective_scenario: Scenario) -> bool:
        """Return True iff the native 1040 spine (v1) can compute this scenario.

        The spine's v1 scope is single filers whose return does NOT involve
        the Earned Income Credit (line 27a). Anything outside that scope is
        routed to the XLSX oracle, which still covers the full 1040 surface.

        The EIC check is a CHEAP published-threshold gate only — it never
        computes the credit. A scenario is treated as *possibly* EIC-eligible
        (and therefore out of scope) when it has positive earned income and an
        AGI estimate below the year's EIC income ceiling for its dependent
        count. The ceiling uses the MFJ (largest) phase-out-end amount, so the
        gate is conservative: it may route a not-actually-eligible low-income
        filer to the workbook, but never lets an eligible one through the spine
        (which performs no EIC math). The workbook then computes any real EIC.
        """
        from tenforty.models import FilingStatus
        from tenforty.params.federal import load as load_params

        if effective_scenario.config.filing_status is not FilingStatus.SINGLE:
            return False

        cfg = effective_scenario.config
        earned_income = sum(w.wages for w in effective_scenario.w2s)
        if earned_income <= 0:
            # No earned income → no EIC possible; nothing else takes the spine
            # out of scope for a single filer.
            return True

        params = load_params(cfg.year)
        ceilings = params.eic_income_ceiling or {}
        if not ceilings:
            # No ceiling data → cannot cheaply rule EIC in or out; be safe.
            return True

        # Cheap AGI estimate for the EIC-ceiling gate — include ALL scenario
        # income components, not wages + interest + ordinary dividends only. A
        # filer whose income is K-1 / rental / capital-gain rather than wages is
        # still high-AGI and EIC-INELIGIBLE, and must stay on the validated
        # native spine; the old wages-only estimate mis-routed such a filer to
        # the workbook (real AGI 133k read as 15k during the 2022 reconcile).
        # Every component here EXCEPT Schedule C (see its own note below) is
        # clamped at 0, so this estimate only ever RISES
        # vs the old wages-only value: it can route MORE scenarios native, never
        # fewer, and leaves a genuinely low-income filer (no other income)
        # unchanged. Overestimating is safe for the gate — it rules EIC OUT
        # (routes native) only when the estimate CLEARS the ceiling; a possibly-
        # eligible low-income filer stays below it and still routes to the
        # workbook, which performs the real EIC math. (Adjustments are ignored,
        # which can only make the estimate higher than true AGI — same safe
        # direction.)
        agi_estimate = (
            earned_income
            + sum(f.interest for f in effective_scenario.form1099_int)
            + sum(f.ordinary_dividends + f.capital_gain_distributions
                  for f in effective_scenario.form1099_div)
            + sum(g.unemployment_compensation + g.state_tax_refund
                  + g.rtaa_payments + g.taxable_grants
                  + g.agriculture_payments + g.market_gain
                  for g in effective_scenario.form1099_g)
            + sum(_k1_positive_income(k)
                  for k in effective_scenario.schedule_k1s)
            + sum(max(0.0, _rental_net_income(r))
                  for r in effective_scenario.rental_properties)
            + max(0.0, sum(b.proceeds - b.cost_basis
                           for b in effective_scenario.form1099_b))
            # Schedule C net profit OR LOSS, netted across businesses and NOT
            # clamped. Every other component above is clamped at 0 (an
            # overestimate), but a Schedule C loss is now a real, allowed
            # reduction of AGI: clamping it would let a filer whose WAGES
            # clear the ceiling but whose wages-less-loss do not route to the
            # native spine, which performs no EIC math. Counting the loss
            # sends that possibly-eligible filer out of spine scope, where
            # the workbook path refuses Schedule C outright (fail-closed).
            # This estimate runs BEFORE sch_c.compute's refusals, so it uses
            # the non-raising estimate.
            + sum(form_sch_c.net_profit_estimate(biz)
                  for biz in effective_scenario.schedule_c_businesses)
        )
        num_children = min(len(cfg.dependents), max(ceilings))
        ceiling = ceilings.get(num_children, max(ceilings.values()))
        # Below the ceiling → possibly EIC-eligible → out of spine scope.
        return agi_estimate >= ceiling

    def _refuse_possible_excess_business_loss(self, scenario: Scenario) -> None:
        """FAIL-CLOSED GUARD -- IRC §461(l) excess business loss (Form 461).

        A noncorporate taxpayer's aggregate business loss is deductible only
        up to a yearly threshold; the excess is disallowed and carried
        forward. tenforty does not model Form 461. Rather than deduct a loss
        the limitation would cut, refuse whenever the un-netted sum of
        business losses (``aggregate_business_losses``) exceeds the year's
        threshold for the filing status. There is no acknowledge-and-proceed:
        above the threshold the correct deduction needs the unmodeled form.
        """
        from tenforty.models import FilingStatus
        from tenforty.params.federal import load as load_params
        thresholds = load_params(
            scenario.config.year).excess_business_loss_threshold
        # FilingStatus(...) accepts the enum or its raw string value.
        status = FilingStatus(scenario.config.filing_status).value
        threshold = thresholds[status]
        losses = aggregate_business_losses(scenario)
        if losses > threshold:
            raise NotImplementedError(
                f"Business losses on this return total {losses:,.0f} (Schedule "
                f"C net losses + K-1 business loss boxes + rental property "
                f"losses, with no business income netted against them), which "
                f"exceeds the IRC §461(l) excess-business-loss threshold of "
                f"{threshold:,} for filing status {status} in tax year "
                f"{scenario.config.year}. Form 461 (Limitation on Business "
                f"Losses) is not modeled in tenforty v1, so the allowed loss "
                f"cannot be determined and this return cannot be produced. "
                f"The comparison is deliberately conservative: it may refuse "
                f"a return whose true excess business loss is zero."
            )

    def _compute_1040_pipeline(
        self, effective_scenario: Scenario,
    ) -> dict[str, object]:
        """Native 1040 spine for in-scope scenarios; XLSX oracle otherwise.

        Runs the native spine (gather native schedule computes → compute_spine)
        only when ``_scenario_in_spine_scope`` holds (single filer, not
        EIC-eligible). Out-of-scope scenarios fall back to
        ``_compute_1040_via_workbook`` so the workbook covers the full 1040
        surface (non-single filers, EIC, etc.) until the spine is extended."""
        from tenforty.params.federal import load as load_params
        from tenforty.forms import f1040_spine
        params = load_params(effective_scenario.config.year)
        # Before the native/workbook split, so BOTH paths are covered.
        self._refuse_possible_excess_business_loss(effective_scenario)
        if not self._scenario_in_spine_scope(effective_scenario):
            if effective_scenario.form_1095a is not None:
                # A 1095-A scenario that is out of native-spine scope
                # (EIC-possible / non-single filer) would route to the XLSX
                # workbook — which has NO Form 8962. A silent workbook fallback
                # would drop the Premium Tax Credit entirely. Refuse loudly
                # until the native spine is extended to this filer class.
                raise NotImplementedError(
                    "Scenario carries a Form 1095-A (Premium Tax Credit) but is "
                    "out of native-1040-spine scope (EIC-possible or non-single "
                    "filer), so it would route to the XLSX workbook path, which "
                    "does not compute Form 8962. Refusing rather than silently "
                    "dropping the PTC. Extend the native spine to cover this "
                    "filer class before enabling 8962 for it."
                )
            workbook_result = self._compute_1040_via_workbook(effective_scenario)
            # The native spine's f8995.compute refuses (NotImplementedError)
            # when QBI > 0 and taxable income before the QBI deduction exceeds
            # the Form 8995 simple-path threshold, because Form 8995-A (the
            # above-threshold form) is not implemented in v1. That guard lives
            # inside f8995.py, which only runs on the spine path — every
            # non-single filer (and any EIC-possible filer) routes here
            # instead, to the XLSX workbook. The 2025 workbook has an `8995`
            # sheet (simple path) and NO `8995A` sheet, so an above-threshold
            # scenario routed here would silently get a workbook-computed
            # result with no refusal — a wrong number, silently, exactly the
            # failure mode the 1095-A guard above exists to prevent for PTC.
            # Mirror it for QBI: validate the already-computed workbook result
            # against the same threshold and refuse after the fact, since
            # taxable income does not exist before the workbook runs. This
            # leaves the below-threshold path (where the workbook's `8995`
            # sheet IS valid) completely untouched.
            qbi_total = sum(
                k1.qbi_amount for k1 in effective_scenario.schedule_k1s
            )
            # HONOR THE ATTESTATION ON BOTH PATHS. f8995.compute's
            # native-spine guard reads
            # `not scenario.config.acknowledges_qbi_below_threshold` as the
            # third conjunct of its refusal condition. If this workbook-path
            # guard omitted it, the same attestation would admit a scenario
            # on the spine path and be ignored here -- so whether the filer
            # can invoke the escape hatch would depend on filer class (which
            # is what picks the route), not on anything the filer attested
            # to. Same refusal condition as f8995.py, deliberately.
            #
            # ONE DELIBERATE DIFFERENCE from f8995.py: there, the strict
            # `qualified_dividends` read sits OUTSIDE the guard and fires
            # unconditionally, because that figure is needed to compute the
            # form no matter what the guard decides. Here the strict
            # `taxable_income_before_qbi_deduction` read sits INSIDE, so a
            # workbook result missing that key goes undetected when QBI <= 0
            # or when the attestation is set. That is acceptable because,
            # unlike f8995's, this figure is used for NOTHING but the
            # threshold comparison below -- on both of those branches no
            # comparison happens, so there is no decision a missing key
            # could corrupt, and the workbook result passes through exactly
            # as it would have. Reading it unconditionally would instead
            # turn a key this call never needed into a hard failure. The key
            # is read strictly on precisely the path whose correctness
            # depends on it. Pinned by WorkbookQbiThresholdGuardUnitTests::
            # test_missing_taxable_income_key_raises_rather_than_defaulting_to_zero.
            if (qbi_total > 0
                    and not effective_scenario.config
                    .acknowledges_qbi_below_threshold):
                threshold = params.qbi_threshold[
                    effective_scenario.config.filing_status.value
                ]
                # Same figure f8995.compute gates on: taxable income BEFORE
                # the QBI deduction (form_1040.compute adds the deduction
                # back onto its own "taxable_income" output under this key).
                #
                # STRICT read (no silent default): a `.get(..., 0)` default
                # here would mean that if the workbook path ever stopped
                # producing this key, `0 > threshold` is False and this
                # guard would silently no-op -- routing an above-threshold,
                # nonzero-QBI scenario straight through to a workbook-
                # computed result with the wrong QBI deduction formula,
                # exactly the silent-wrong-number failure this guard exists
                # to prevent. The sole legitimate producer of this key is
                # `_compute_1040_via_workbook` (the XLSX workbook path,
                # bound to `workbook_result` above); if it is ever missing,
                # that is a bug in the workbook path itself and must surface
                # loudly here, not be papered over with a default of 0.
                if "taxable_income_before_qbi_deduction" not in workbook_result:
                    raise KeyError(
                        "workbook_result is missing "
                        "\"taxable_income_before_qbi_deduction\", which this "
                        "QBI above-threshold guard requires to compare "
                        "against the Form 8995 simple-path threshold. The "
                        "expected producer is "
                        "_compute_1040_via_workbook (the XLSX workbook "
                        "path). Do not default this to 0 -- a silent "
                        "default would make `0 > threshold` false and let "
                        "this guard silently no-op, routing an "
                        "above-threshold, nonzero-QBI scenario through to a "
                        "workbook-computed result that used the wrong QBI "
                        "deduction formula."
                    )
                taxable_income_before_qbi = float(
                    workbook_result["taxable_income_before_qbi_deduction"]
                )
                if taxable_income_before_qbi > threshold:
                    raise NotImplementedError(
                        f"Taxable income before QBI ({taxable_income_before_qbi:.0f}) "
                        f"exceeds the Form 8995 simple-path threshold ({threshold}) "
                        f"for filing status "
                        f"{effective_scenario.config.filing_status.value}, and the "
                        f"scenario has {qbi_total:.0f} of QBI. This scenario is out "
                        "of native-1040-spine scope (EIC-possible or non-single "
                        "filer), so it routes to the XLSX workbook path, which has "
                        "an `8995` (simple-path) sheet but no `8995A` sheet. Form "
                        "8995-A is not implemented in tenforty v1. Refusing rather "
                        "than silently returning a workbook-computed result that "
                        "used the wrong QBI deduction formula. Set "
                        "`acknowledges_qbi_below_threshold: true` ONLY if you "
                        "have confirmed that the simple-path formula is "
                        "correct for your return; otherwise extend the native "
                        "spine to cover this filer class (or implement Form "
                        "8995-A) before enabling this scenario."
                    )
            return workbook_result
        schedule_results, k1_fanout = self._compute_native_schedules(effective_scenario)
        spine_result = f1040_spine.compute_spine(
            effective_scenario, params, schedule_results, k1_fanout=k1_fanout,
        )
        # Forward f8949 box-total keys into the final result dict so oracle
        # cross-check consumers (e.g. test_f8949_oracle.py) can read them
        # from compute_federal — mirroring the workbook path which exposed
        # these as named-range OUTPUTS.
        f8949_result = schedule_results.get("f8949", {})
        return {**f8949_result, **spine_result}

    def _compute_sch_c_and_se(self, scenario: Scenario) -> tuple[dict, dict]:
        """Schedule C (net profit) then Schedule SE (self-employment tax).

        ONE implementation of this wiring, shared by the native compute path
        (_compute_native_schedules) and the PDF emit path
        (_federal_individual_emit_specs), so the two cannot hand their
        consumers different upstream: sch_c is a pure leaf (upstream={}),
        sch_se consumes sch_c's net profit. With no business both are {}.
        """
        sch_c_results = form_sch_c.compute(scenario, upstream={})
        sch_se_results = form_sch_se.compute(
            scenario, upstream={"sch_c": sch_c_results},
        )
        return sch_c_results, sch_se_results

    def _compute_native_schedules(
        self, effective_scenario: Scenario,
    ) -> tuple[dict[str, dict], K1FanoutData]:
        """Run each native schedule compute in dependency order.

        Returns a dict keyed by schedule name, each value being that
        schedule's raw compute dict.  The spine consumes these via
        ``schedule_results[name][key]``.

        Ordering mirrors _emit_pdfs_internal:
        1. Sch E Part II (K-1 fanout) — provides K1FanoutData sidecar used
           by sch_d, f8995, and f8582.
        2. Sch E (Part I rental, merged with Part II fields under "sch_e").
        3. Sch 1 — needs sch_e.
        4. Sch D — needs k1_fanout (via f8949 if applicable).
        5. F8959 — standalone (W-2 Medicare wages only at v1 scope).
        6. Income preamble — provides agi/magi/net_capital_gain from parts
           already computed; seeds a partial f1040 stub (no
           taxable_income_before_qbi_deduction yet).
        7. Sch A — needs only agi from the partial stub (QBI is below-the-line
           on 1040 line 13, so this has no circularity with QBI).
        8. Resolve deductions (std vs. itemized) via the actual Sch A result,
           then finalize the stub's taxable_income_before_qbi_deduction with
           the ACTUAL (itemized-aware) figure.
        9. F8962 — needs agi.
        10. F8995 — needs k1_fanout + f1040 stub (taxable_income_before_qbi,
            now the actual figure).
        11. F8582 — needs k1_fanout + sch_e + f1040 stub (magi).
        """
        from tenforty.forms import f1040_spine
        from tenforty.params.federal import load as _load_params

        # --- Step 1: Sch E Part II (K-1 fanout) ---
        if self._should_emit_sch_e_part_ii(effective_scenario):
            part_ii_fields, k1_fanout = form_sch_e_part_ii.compute(
                effective_scenario, upstream={},
            )
        else:
            part_ii_fields = {}
            k1_fanout = K1FanoutData.empty()

        upstream: UpstreamState = {"k1_fanout": k1_fanout}

        # --- Step 2: F8949 (needed by sch_d) ---
        if self._should_compute_8949(effective_scenario):
            upstream["f8949"] = form_f8949.compute(effective_scenario, upstream)

        # --- Step 3: Sch E Part I (rental), merged with Part II fields ---
        # Merge so the spine can read both sch_e_line_26_total (Part I) and
        # sch_e_line_41_total_pte (Part II) from the same "sch_e" slot; the
        # helper also emits the line-41 grand total for the PDF line-41 box.
        sch_e_part_i = form_sch_e.compute(effective_scenario, upstream={})
        sch_e_combined = form_sch_e_part_ii.merge_with_part_i(
            sch_e_part_i, part_ii_fields)

        # --- Step 3b: Sch C (net profit) then Sch SE (self-employment tax) ---
        # sch_c is a pure leaf (upstream={}); sch_se consumes sch_c net profit.
        # Both feed Schedule 1: line 3 (business income) ← sch_c net profit,
        # line 15 (half-SE-tax deduction) ← sch_se line 13. With no business,
        # both return {} → the Sch 1 reads default 0 → AGI unchanged.
        sch_c_results, sch_se_results = self._compute_sch_c_and_se(
            effective_scenario)

        # --- Step 4: Sch 1 (needs sch_e, sch_c, sch_se) ---
        sch_1_results = form_sch_1.compute(
            effective_scenario,
            upstream={
                "sch_e": sch_e_combined,
                "sch_c": sch_c_results,
                "sch_se": sch_se_results,
            },
        )

        # --- Step 5: Sch D (needs k1_fanout + f8949) ---
        sch_d_results = form_sch_d.compute(effective_scenario, upstream=upstream)

        # --- Step 6: F8959 (W-2 wages + Schedule SE net earnings for Part II) ---
        # Runs after Step 3b (sch_se_results), so Part II line 8 sees the SE
        # base. No business → sch_se_results returns {} → Part II stays 0.
        f8959_results = form_8959.compute(
            effective_scenario, upstream={"sch_se": sch_se_results},
        )

        # --- Step 7: AGI pre-compute stub (shared preamble) ---
        # F8995 and F8582 need upstream["f1040"]. Build from the SHARED income
        # preamble so the AGI/total-income math has a single source of truth
        # with compute_spine (they cannot drift).
        _params = _load_params(effective_scenario.config.year)
        _preamble = f1040_spine.compute_income_preamble(
            effective_scenario,
            _params,
            {"sch_1": sch_1_results, "sch_d": sch_d_results},
            k1_fanout=k1_fanout,
        )
        # Partial stub for Schedule A, which reads only agi/magi. QBI is
        # below-the-line (1040 line 13), so Schedule A (line 12, depends on AGI
        # only) can be computed now — no circularity.
        f1040_stub: dict = {
            "agi": _preamble.agi,
            "magi": _preamble.magi,
            "net_capital_gain": _preamble.net_capital_gain,
            # 1040 line 3a TOTAL (1099-DIV + K-1). Form 8995 line 12 reads this
            # rather than the K-1-only fanout aggregate, so the form sees the
            # whole figure the IRS instructions call for.
            "qualified_dividends": _preamble.qualified_divs_total,
        }

        # --- Step 8: Sch A (needs agi from the stub) ---
        # Build an effective scenario with itemized_deductions populated from
        # form1098s when itemized_deductions is not set directly. This bridges
        # the YAML fixture model (which uses form1098s for mortgage/property-tax)
        # to forms.sch_a.compute, which reads from scenario.itemized_deductions.
        # BC-3: Sch A now runs before the Form 8962 and Form 8995 refusal
        # gates, so for a scenario that would trip more than one gate, Sch
        # A's own NotImplementedError surfaces first. This is not merely a
        # precedence shift among identical refusal types: the deduction-
        # resolution step below calls resolve_deductions, which can itself
        # raise ValueError (the 2021 charitable-nonitemizer line-12b guard)
        # for an itemizer with charitable_cash_nonitemizer set — a scenario
        # that previously hit the Form 8995 threshold gate's
        # NotImplementedError first. So the surfaced exception TYPE can now
        # differ, not just which of two NotImplementedErrors fires first.
        # The ValueError's type and message text are byte-identical to
        # main's in that case — no standing ruling is violated, and it is
        # arguably a better outcome (a more specific, actionable diagnosis
        # that can no longer be masked) — but callers relying on
        # NotImplementedError specifically for that combination will now
        # see ValueError instead. See BC-3 in the plan's behavior-change log.
        sch_a_scenario = _scenario_with_effective_itemized(effective_scenario)
        sch_a_results = (
            form_sch_a.compute(
                sch_a_scenario,
                upstream={"f1040": f1040_stub},
            )
            if sch_a_scenario.itemized_deductions is not None
            else {}
        )

        # --- Step 9: finalize the stub with the ACTUAL deduction ---
        # taxable-income-before-QBI now uses the taxpayer's actual deduction
        # (itemized when itemizing), so Form 8995's line-14 income limit binds
        # correctly and the threshold gate reads the correct figure. Uses the
        # SAME resolve_deductions helper as compute_spine (no drift).
        _ded = f1040_spine.resolve_deductions(
            effective_scenario, _params, _preamble.agi, sch_a_results,
        )
        f1040_stub["taxable_income_before_qbi_deduction"] = (
            _ded.taxable_income_before_qbi
        )
        # Unfloored companion for Form 8995 line 11 only (the floored value
        # above keeps feeding the threshold/income-limit gates).
        f1040_stub["taxable_income_before_qbi_deduction_unfloored"] = (
            _ded.taxable_income_before_qbi_unfloored
        )

        # --- Step 10: Form 8962 (Premium Tax Credit) ---
        # Computed here because it consumes AGI (now known from the shared
        # preamble) and its outputs feed the totals downstream (net PTC →
        # total_payments, excess-APTC repayment → overpaid) — mirroring how
        # f8959 is sequenced ahead of the totals in the spine call chain.
        # MAGI SEAM: Form 8962 MAGI is AGI + tax-exempt interest, NOT the
        # spine's "magi" key (which equals AGI and excludes tax-exempt
        # interest). Only computed when a 1095-A is present; when absent, the
        # "f8962" key is omitted so the detail keys stay absent (mirroring how
        # f8959 detail is only present when computed).
        # SE-HEALTH × PTC GUARD lives at the sch_1_line_17_se_health read in
        # forms/f1040_spine.py: if that (currently hardcoded-0) channel is ever
        # nonzero while a 1095-A is present, the spine raises NotImplementedError
        # (Rev. Proc. 2014-41 iterative reconciliation is unmodeled).
        f8962_results = None
        if effective_scenario.form_1095a is not None:
            # PTC-MAGI single-source guard.
            if any(
                f.tax_exempt_interest for f in effective_scenario.form1099_int
            ):
                raise NotImplementedError(
                    "A Form 1099-INT reports tax-exempt interest while a Form "
                    "1095-A (Premium Tax Credit) is present. Put the "
                    "tax-exempt-interest MAGI addition on "
                    "form_1095a.tax_exempt_interest instead — that is the one "
                    "sanctioned knob for tax-exempt interest in PTC MAGI. "
                    "There is only one knob because additively combining both "
                    "sources would double-count the same interest in PTC MAGI, "
                    "which is exactly as wrong as dropping it. Form 1040 line "
                    "2a (tax-exempt interest) is not modeled in the native "
                    "spine; this is the marked seam to revisit if it ever "
                    "lands."
                )
            f8962_results = form_f8962.compute(
                block=effective_scenario.form_1095a,
                magi=_preamble.agi + effective_scenario.form_1095a.tax_exempt_interest,
                year=effective_scenario.config.year,
                params=params_f8962.load(effective_scenario.config.year),
            )

        # --- Step 11: F8995 (needs k1_fanout + f1040 stub) ---
        f8995_results = form_f8995.compute(
            effective_scenario,
            upstream={
                "k1_fanout": k1_fanout,
                "f1040": f1040_stub,
                "sch_c": sch_c_results,
                "sch_se": sch_se_results,
            },
        )

        # --- Step 12: F8582 (needs k1_fanout + sch_e + f1040 stub) ---
        f8582_results = form_f8582.compute(
            effective_scenario,
            upstream={
                **upstream,
                "sch_e": sch_e_combined,
                "f1040": f1040_stub,
            },
        )

        results: dict[str, dict] = {
            "sch_1": sch_1_results,
            "sch_a": sch_a_results,
            "sch_c": sch_c_results,
            "sch_d": sch_d_results,
            "sch_e": sch_e_combined,
            "sch_se": sch_se_results,
            "f8959": f8959_results,
            "f8995": f8995_results,
            "f8582": f8582_results,
            # f8949 included so _compute_1040_pipeline can forward box totals
            # into the final result for oracle cross-check consumers.
            "f8949": upstream.get("f8949", {}),
        }
        # Only present when a 1095-A was computed — the spine reads it via
        # schedule_results.get("f8962", {}) and defaults every value to 0.
        if f8962_results is not None:
            results["f8962"] = f8962_results
        return results, k1_fanout

    def _compute_1040_via_workbook(
        self, effective_scenario: Scenario,
    ) -> dict[str, object]:
        """Run the 1040 pipeline via the XLSX oracle (spreadsheet evaluation + f1040.compute).

        Accepts the already-resolved effective scenario (with any synthesized
        K-1s already appended). Returns the 1040 results dict only — corp keys
        are merged by the caller. This is the single source of truth for the
        spreadsheet evaluation step, the 1099-G withholding supplement, and
        the form_1040.compute step.

        Remains reachable as a test-only oracle after the cutover task
        repoints _compute_1040_pipeline at the native spine.
        """
        # FAIL-CLOSED GUARD — Schedule C / Schedule SE on the workbook path.
        # The native single-filer spine wires Schedule C (net profit) and
        # Schedule SE (self-employment tax) into the 1040. This XLSX workbook
        # path (taken by non-single / EIC-possible filers) does NOT wire them:
        # a workbook-path return carrying a Schedule C business would silently
        # emit a 1040 WITHOUT the business income and SE tax, understating both
        # income and liability. There is NO acknowledge-and-proceed (that would
        # fail-open into a wrong number — the U-1 anti-pattern): Schedule C / SE
        # are honored ONLY on the native single-filer spine, and the message
        # points the user there. Wiring Schedule C into the workbook path is a
        # deferred follow-on; this task FAILS CLOSED, it does not implement it.
        if effective_scenario.schedule_c_businesses:
            raise NotImplementedError(
                "Schedule C / self-employment income is set on a scenario that "
                "routes to the workbook (XLSX) compute path (non-single filer "
                "or EIC-eligible). tenforty has NOT wired Schedule C / Schedule "
                "SE into the workbook path; they are supported only on the "
                "NATIVE single-filer 1040 spine. There is no acknowledge-and-"
                "proceed — the workbook would silently emit a return WITHOUT "
                "the business income and SE tax. Use a single-filer scenario or "
                "file by hand."
            )

        # FAIL-CLOSED GUARD — deferred ticket (dd) (the SE-health
        # workbook-input-wiring ticket in the tenforty series). The native
        # single-filer spine (Task 1) honors
        # config.self_employed_health_insurance_deduction (Schedule 1 line 17),
        # but this XLSX workbook path has NO INPUTS entry for it (the wiring is
        # deferred under (dd) — a per-year named-range asymmetry makes it unsafe
        # off the critical path; the ledger holds the recon). Without this guard
        # a workbook-path return carrying the deduction would compute line 17 as
        # 0 and silently overstate AGI. Refuse loudly rather than emit a wrong
        # (too-high) number. There is NO acknowledge-and-proceed (that would
        # fail-open into a wrong number — the U-1 anti-pattern): the field is
        # honored ONLY on the native single-filer path, and the message points
        # the user there.
        if effective_scenario.config.self_employed_health_insurance_deduction:
            raise NotImplementedError(
                "The self-employed health-insurance deduction (Schedule 1 "
                "line 17) is not wired into the XLSX workbook compute path, so "
                "a workbook-path return carrying it would silently drop the "
                "deduction and overstate AGI. There is no acknowledge-and-"
                "proceed: this deduction is honored only on the NATIVE "
                "single-filer 1040 spine. A workbook-path scenario (non-single "
                "or EIC-possible filer) with "
                "self_employed_health_insurance_deduction set cannot be "
                "computed until the deferred workbook input wiring (ticket "
                "(dd)) lands. Use the native single-filer path, which supports "
                "the field."
            )

        year = effective_scenario.config.year
        spreadsheet = self.spreadsheets_dir / "federal" / str(year) / "1040.xlsx"
        if not spreadsheet.exists():
            raise FileNotFoundError(
                f"Federal spreadsheet not found: {spreadsheet}"
            )

        flat_inputs = flatten_scenario(effective_scenario)
        raw = self.engine.compute(
            spreadsheet_path=spreadsheet,
            mapping=F1040,
            year=year,
            inputs=flat_inputs,
            work_dir=self.work_dir / "federal",
        )

        # Supplement: the oracle's OUTPUTS only read W-2 withholding
        # (W2_FedTaxWH) into "federal_withheld". 1099-G box 4 withholding
        # flows into the workbook's total_payments but is not exposed as a
        # separate named range. Inject it here so f1040.compute's
        # federal_withheld_1099 slot picks it up for line 25b.
        g_withheld = sum(
            g.federal_tax_withheld for g in effective_scenario.form1099_g
        )
        if g_withheld:
            raw["federal_withheld_1099"] = (
                (raw.get("federal_withheld_1099") or 0) + g_withheld
            )

        # PTC money outputs: blank means zero. The workbook leaves PTC_Net
        # (net PTC) blank when net PTC is 0, and PTC_Excess blank when there
        # is no excess-APTC repayment; the engine reads a blank cell as None.
        # The native spine emits 0 in those cases, so normalize these two keys
        # None -> 0 for parity. Scoped DELIBERATELY to the PTC money keys only:
        # any OTHER output going blank should surface loudly as None rather
        # than be silently zeroed.
        # (Sibling scoped normalizations: f8959_tax_total and schedule2_tax are
        # normalized in forms/f1040.compute — a new scoped normalization should
        # find both sites and choose its location deliberately. See the
        # schedule2_tax block there for the test that separates a coercible
        # definitional blank from a diagnostic refusal that must NOT be zeroed.)
        for _ptc_key in ("f8962_net_ptc", "f8962_repayment"):
            if raw.get(_ptc_key) is None:
                raw[_ptc_key] = 0

        # The workbook knows nothing of the 1040 header block; add it from
        # config so the printed header cannot depend on which pipeline
        # computed the return (the native spine emits the same block).
        from tenforty.forms import f1040_spine
        return {
            **f1040_spine.header_values(effective_scenario.config),
            **form_1040.compute(raw_1040=raw, upstream={}),
        }

    def compute_federal(self, scenario: Scenario) -> dict[str, object]:
        """Compute the federal return (1120-S waterfall + 1040 + schedules).

        When `scenario.s_corp_return` is set, runs the corporate pipeline
        first; the computed K-1s are merged with any user-supplied K-1s
        on a *copy* of the scenario (the caller's input is not mutated).
        The corporate output keys (prefixed `f1120s_`) are merged into the
        returned 1040 output dict.

        Delegates to `_build_effective_scenario` and `_compute_1040_pipeline`
        — see those for waterfall and pipeline contracts.
        """
        effective_scenario, corp_results = self._build_effective_scenario(scenario)
        results_1040 = self._compute_1040_pipeline(effective_scenario)
        return {**corp_results, **results_1040}

    def compute_corporate(self, scenario: Scenario) -> dict[str, object]:
        """Compute the federal corporate return (Form 1120-S pipeline).

        Returns {} when scenario.s_corp_return is None (no corporate work
        needed for a pure personal 1040 scenario).
        """
        if scenario.s_corp_return is None:
            return {}
        return form_f1120s.compute(scenario, upstream={})

    def compute_california_corporate(self, scenario: Scenario) -> dict[str, object]:
        """Compute the California S-corp return (Form 100S + Schedule K-1 (100S)).

        Returns {} unless BOTH ``scenario.s_corp_return`` and
        ``s_corp_return.ca`` are set. Runs the federal 1120-S pipeline first
        and feeds its results in as upstream, so the CA net-income base is
        exactly the federal ordinary business income (spec §3 interlock); the
        CA franchise tax never recomputes federal figures.
        """
        if scenario.s_corp_return is None or scenario.s_corp_return.ca is None:
            return {}
        federal = form_f1120s.compute(scenario, upstream={})
        f100s_results = form_f100s.compute(scenario, {"f1120s": federal})
        k1_results = form_f100s_k1.compute(
            scenario, {"f1120s": federal, "f100s": f100s_results})
        return {**f100s_results, **k1_results}

    def emit_pdfs(
        self,
        scenario: Scenario,
        results: dict[str, object],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Fill PDFs and write them to output_dir.

        Raises ValueError when scenario.s_corp_return is not None — callers
        must use run_full_return() instead, which builds the effective scenario
        internally so the synthesized 1120-S K-1 is visible in Sch E. Calling
        this method directly with an S-corp scenario would silently produce an
        incomplete Sch E (missing the corp-pipeline K-1).

        For non-S-corp scenarios, delegates to _emit_pdfs_internal.
        Returns a dict mapping form name to the filled PDF path.
        """
        if scenario.s_corp_return is not None:
            raise ValueError(
                "Scenario has s_corp_return set — use "
                "ReturnOrchestrator.run_full_return() to produce PDFs that "
                "include the synthesized 1120-S K-1 in Sch E. Calling "
                "emit_pdfs() directly skips the K-1 waterfall and produces "
                "incomplete Sch E output."
            )
        return self._emit_pdfs_internal(scenario, results, output_dir)

    def _emit_pdfs_internal(
        self,
        scenario: Scenario,
        results: dict[str, object],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Fill PDFs and write them to output_dir (unguarded internal API).

        Does not check whether scenario.s_corp_return is set. Callers are
        responsible for passing the effective scenario (with any synthesized
        K-1s already appended) when operating on S-corp returns.
        Returns a dict mapping form name to the filled PDF path.
        """
        validate_third_party_designee(scenario.config)
        output_dir.mkdir(parents=True, exist_ok=True)
        filler = PdfFiller()

        # Build the per-form emit specs (identical gates/order/values to the
        # historic inline body — the specs just defer rendering), then fill
        # EVERY one. run_amendment_packet drives the same specs but fills only
        # the selector-chosen subset.
        emitted: dict[str, Path] = {
            spec.name: self._render_federal_spec(filler, spec, output_dir)
            for spec in self._federal_individual_emit_specs(scenario, results)
        }

        # 1120-S emit (only when scenario.s_corp_return is populated).
        emitted.update(
            self._emit_federal_corporate_pdfs_internal(
                scenario, results, output_dir))

        return emitted

    def _federal_individual_emit_specs(
        self, scenario: Scenario, results: dict,
    ) -> list[_FederalFormSpec]:
        """Prepare each federal individual-return form's emit spec WITHOUT
        rendering — the reusable per-form path shared by ``_emit_pdfs_internal``
        (fill all) and ``run_amendment_packet`` (fill the selector-chosen
        subset). Gates, ordering, upstream wiring, and per-form value prep are
        byte-for-byte the historic inline body; only the ``filler.fill`` calls
        are deferred to the caller. The federal EMIT tests are the regression
        guard for this extraction.
        """
        # Year floor for Schedule C returns. This method is the SHARED
        # chokepoint for both public emit entries (emit_pdfs and
        # run_amendment_packet). Schedule C / Schedule SE / Schedule 2 have
        # templates and mappings for years.SCHEDULE_C_FAMILY_YEARS only
        # (the family's own policy floor, years.SCHEDULE_C_FAMILY_FLOOR_YEAR),
        # so a year outside it refuses here, rather than failing later
        # on a missing mapping. Native compute is not year-restricted. The
        # compute layer's own refusals (unmodeled Schedule C features, a net
        # loss without the at-risk attestation) are the real guards for everything else and fire below, in
        # _compute_sch_c_and_se, before any PDF is rendered.
        from tenforty import years as year_manifest
        if (scenario.schedule_c_businesses
                and scenario.config.year
                not in year_manifest.SCHEDULE_C_FAMILY_YEARS):
            raise NotImplementedError(
                "PDF emission for a return with a Schedule C business is "
                "supported for tax years "
                f"{year_manifest.describe(year_manifest.SCHEDULE_C_FAMILY_YEARS)} "
                f"only; this return is tax year {scenario.config.year}. "
                "tenforty's year-coverage policy floors the Schedule C "
                "family there, so there is no Schedule C, Schedule SE or "
                "Schedule 2 template or mapping for this year. The native "
                "compute path "
                "(compute_federal) still produces the numbers; file the PDF "
                "by hand."
            )

        year = scenario.config.year
        # Digital-assets question (Form 1040, TY2022+). An unanswered question
        # cannot be printed as a blank on a return that gets signed, so emit
        # refuses; the native COMPUTE path never asks (no PDF, no question).
        # 2021's virtual-currency wording is the same field but pre-dates the
        # refusal: answered -> box checked, unanswered -> left blank.
        if year >= 2022 and scenario.config.digital_assets is None:
            raise ValueError(
                "Form 1040 PDF emission needs the digital-assets question "
                f"answered for tax year {year}: set `digital_assets` in the "
                "scenario config to true or false ('At any time during "
                f"{year}, did you: (a) receive (as a reward, award, or payment "
                "for property or services); or (b) sell, exchange, or "
                "otherwise dispose of a digital asset (or a financial "
                "interest in a digital asset)?'). It is left unanswered "
                "(null) in this scenario."
            )
        specs: list[_FederalFormSpec] = []

        def _fed(basename: str) -> Path:
            return _PDFS_ROOT / "federal" / str(year) / basename

        # Hoist sch_e_part_ii.compute to run at most once. All downstream
        # consumers (sch_b, sch_d, sch_e, f8995, f8582) share a single fanout
        # result rather than each recomputing from scratch.
        if self._should_emit_sch_e_part_ii(scenario):
            part_ii_fields, k1_fanout = form_sch_e_part_ii.compute(scenario, upstream={})
        else:
            part_ii_fields = {}
            k1_fanout = K1FanoutData.empty()

        upstream: UpstreamState = {"f1040": results, "k1_fanout": k1_fanout}
        # Schedule C / Schedule SE upstream — the same helper the native
        # compute path uses, so the Schedule 1 (lines 3 and 15), Form 8959
        # (Part II) and Form 8995 (Schedule C QBI component) fill computes
        # below receive exactly what the native computes received.
        sch_c_results, sch_se_results = self._compute_sch_c_and_se(scenario)
        upstream["sch_c"] = sch_c_results
        upstream["sch_se"] = sch_se_results

        if self._should_compute_8949(scenario):
            upstream["f8949"] = form_f8949.compute(scenario, upstream)

        # f1040 — results is already PDF-ready (forms.f1040.compute produced it).
        specs.append(_FederalFormSpec(
            name="1040", template=_fed("f1040.pdf"),
            output_name=f"f1040_{year}.pdf", kind="flat",
            mapping=Pdf1040.get_mapping(year),
            values={**results, **self._form_1040_checkbox_values(
                scenario, results)},
            checkbox_states=Pdf1040.get_checkbox_states(year),
            # 1040 line 24 (total tax) is filled by a derivation rather than a
            # result key: no key fills it on the native path, and the single
            # shared implementation of the arithmetic lives in forms/f4868.py.
            # See Pdf1040.get_derivations for why not a spine output key.
            derivations=Pdf1040.get_derivations(year),
        ))

        specs.append(_FederalFormSpec(
            name="4868", template=_fed("f4868.pdf"),
            output_name=f"f4868_{year}.pdf", kind="flat",
            mapping=Pdf4868.get_mapping(year),
            values=form_4868.compute(scenario, upstream=upstream),
        ))

        if self._should_emit_sch_b(scenario, results):
            sch_b_values = form_sch_b.compute(scenario, upstream=upstream)
            specs.append(_FederalFormSpec(
                name="sch_b", template=_fed("f1040sb.pdf"),
                output_name=f"f1040sb_{year}.pdf", kind="flat",
                mapping=PdfSchB.get_mapping(year),
                values=_flatten_sch_b_rows(sch_b_values),
            ))

        if self._should_emit_sch_d(scenario):
            specs.append(_FederalFormSpec(
                name="sch_d", template=_fed("f1040sd.pdf"),
                output_name=f"f1040sd_{year}.pdf", kind="repeater",
                mapping=PdfSchD.get_mapping(year),
                values=form_sch_d.compute(scenario, upstream=upstream),
            ))

        if self._should_emit_8949_pdf(scenario, upstream):
            # PdfF8949 keeps per-box repeater groups (box_a_rows, box_b_rows, …)
            # rather than the single-repeater {template, rows} shape, because
            # boxes A/B share page-1 PDF fields and D/E share page-2 fields. Each
            # row dict already bakes its row index and PDF field path into its
            # keys, so a flat merge onto one field_mapping resolves all per-box
            # keys correctly for a FLAT fill.
            f8949_full_mapping = PdfF8949.get_mapping(year)
            f8949_flat: dict[str, str] = dict(f8949_full_mapping["scalars"])
            for row_dicts in f8949_full_mapping["repeaters"].values():
                for row_dict in row_dicts:
                    f8949_flat.update(row_dict)
            specs.append(_FederalFormSpec(
                name="f8949", template=_fed("f8949.pdf"),
                output_name=f"f8949_{year}.pdf", kind="flat",
                mapping=f8949_flat, values=upstream["f8949"],
            ))

        sch_e_values: dict = {}
        if self._should_emit_sch_e(scenario):
            part_i = form_sch_e.compute(scenario, upstream=upstream)
            # Merge: Part I scalars win for shared keys (e.g. taxpayer_name);
            # helper also emits sch_e_line_41_total_income (the line-41 grand
            # total = line 26 + line 32) for the PDF line-41 box.
            merged = form_sch_e_part_ii.merge_with_part_i(part_i, part_ii_fields)
            # Derive page-2 header fields for the mapping layer without
            # polluting compute outputs with PDF-template structure.
            merged["taxpayer_name_page2"] = merged.get("taxpayer_name")
            merged["taxpayer_ssn_page2"] = merged.get("taxpayer_ssn")
            sch_e_values = merged
            sch_e_mapping = PdfSchE.get_mapping(year)
            sch_e_spec_values = sch_e_values  # downstream compute inputs stay clean
            # Lines A/B (Form 1099 questions): only the CHOSEN answer's box is
            # written (its export on-state), so each Yes/No pair is mutually
            # exclusive; unstated answers add nothing (boxes stay blank).
            validate_sche_1099_answers(scenario.config)
            q_stated = {
                "payments_requiring_1099s":
                    scenario.config.payments_requiring_1099s,
                "filed_required_1099s": scenario.config.filed_required_1099s,
            }
            if any(a is not None for a in q_stated.values()):
                q_cells = PdfSchE.get_1099_question_cells(year)
                q_scalars = dict(sch_e_mapping["scalars"])
                q_values = dict(sch_e_spec_values)
                for question, answer in q_stated.items():
                    if answer is None:
                        continue
                    q_path, q_on = q_cells[question][answer]
                    q_scalars[f"sch_e_{question}"] = q_path
                    q_values[f"sch_e_{question}"] = q_on
                sch_e_mapping = {**sch_e_mapping, "scalars": q_scalars}
                sch_e_spec_values = q_values
            # Line 28 column (e) (basis computation required): written only
            # for rows the compute flags (an S corporation box 1 loss). A
            # year with no cell mapping refuses rather than emit the loss row
            # without its required box.
            basis_rows = [
                letter for letter in ("a", "b", "c", "d")
                if sch_e_spec_values.get(
                    f"sch_e_part_ii_row_{letter}_basis_computation_required")
            ]
            if basis_rows:
                basis_cells = PdfSchE.get_basis_computation_cells(year)
                b_scalars = dict(sch_e_mapping["scalars"])
                b_values = dict(sch_e_spec_values)
                for letter in basis_rows:
                    b_path, b_on = basis_cells[letter]
                    key = f"sch_e_part_ii_row_{letter}_basis_computation_box"
                    b_scalars[key] = b_path
                    b_values[key] = b_on
                sch_e_mapping = {**sch_e_mapping, "scalars": b_scalars}
                sch_e_spec_values = b_values
            specs.append(_FederalFormSpec(
                name="sch_e", template=_fed("f1040se.pdf"),
                output_name=f"f1040se_{year}.pdf", kind="repeater",
                mapping=sch_e_mapping, values=sch_e_spec_values,
            ))

        if self._should_emit_sch_a(scenario, {"f1040": results}):
            specs.append(_FederalFormSpec(
                name="sch_a", template=_fed("f1040sa.pdf"),
                output_name=f"f1040sa_{year}.pdf", kind="repeater",
                mapping=PdfSchA.get_mapping(year),
                values=form_sch_a.compute(scenario, upstream=upstream),
            ))

        if self._should_emit_sch_1(scenario, {"f1040": results}):
            specs.append(_FederalFormSpec(
                name="sch_1", template=_fed("f1040s1.pdf"),
                output_name=f"f1040s1_{year}.pdf", kind="repeater",
                mapping=PdfSch1.get_mapping(year),
                values=form_sch_1.compute(
                    scenario, upstream={**upstream, "sch_e": sch_e_values},
                ),
            ))

        if self._should_emit_sch_2(scenario, results):
            specs.append(_FederalFormSpec(
                name="sch_2", template=_fed("f1040s2.pdf"),
                output_name=f"f1040s2_{year}.pdf", kind="flat",
                mapping=PdfSch2.get_mapping(year),
                values=form_sch_2.compute(scenario, upstream=upstream),
            ))

        # Schedule C — one PDF per business, ALWAYS indexed (sch_c_1,
        # sch_c_2, ...) so a single-business return needs no special case.
        for number, line_values in enumerate(
            sch_c_results.get("sch_c_businesses", []), start=1,
        ):
            specs.append(_FederalFormSpec(
                name=f"sch_c_{number}", template=_fed("f1040sc.pdf"),
                output_name=f"f1040sc_{number}_{year}.pdf", kind="flat",
                mapping=PdfSchC.get_mapping(year),
                values=form_sch_c.emit_values(
                    scenario, number - 1, line_values),
                derivations=PdfSchC.get_derivations(year),
            ))

        # Schedule SE — one form however many businesses (sch_se.compute
        # aggregates them).
        if self._should_emit_sch_se(sch_se_results):
            specs.append(_FederalFormSpec(
                name="sch_se", template=_fed("f1040sse.pdf"),
                output_name=f"f1040sse_{year}.pdf", kind="flat",
                mapping=PdfSchSe.get_mapping(year),
                values={**scenario.config.pdf_header(), **sch_se_results},
            ))

        if self._should_emit_4562(scenario, {"f1040": results}):
            specs.append(_FederalFormSpec(
                name="f4562", template=_fed("f4562.pdf"),
                output_name=f"f4562_{year}.pdf", kind="repeater",
                mapping=Pdf4562.get_mapping(year),
                values=form_4562.compute(scenario, upstream=upstream),
            ))

        if self._should_emit_8959(scenario, {"f1040": results}):
            specs.append(_FederalFormSpec(
                name="8959", template=_fed("f8959.pdf"),
                output_name=f"f8959_{year}.pdf", kind="flat",
                mapping=Pdf8959.get_mapping(year)["scalars"],
                values=form_8959.compute(scenario, upstream=upstream),
            ))

        if self._should_emit_8962(scenario):
            # values = the f1040 results dict: the spine splats the full
            # f8962 detail-key family (f8962_line_*, f8962_month_*,
            # f8962_ui_box_checked) into it when a 1095-A is computed, so no
            # re-compute is needed. checkbox_states carries the 2021 UI-box
            # on-token; derivations hardwire the always-on 4c poverty-table box.
            specs.append(_FederalFormSpec(
                name="8962", template=_fed("f8962.pdf"),
                output_name=f"f8962_{year}.pdf", kind="flat",
                mapping=PdfF8962.get_mapping(year)["scalars"],
                values=results,
                checkbox_states=PdfF8962.get_checkbox_states(year),
                derivations=PdfF8962.get_derivations(year),
                field_formats=PdfF8962.get_field_formats(year),
            ))

        # Form 8995 is required whenever the QBI deduction is claimed,
        # whatever its source (K-1 or Schedule C). ONE compute feeds both the
        # gate and the fill, so they cannot disagree. The compute is skipped
        # when the return has no QBI source at all: the deduction is then
        # zero by construction, and f8995.compute's strict upstream reads are
        # not exercised for returns that never needed the form.
        has_qbi_source = (
            any(k1.qbi_amount for k1 in scenario.schedule_k1s)
            or bool(scenario.schedule_c_businesses)
        )
        f8995_values = (
            form_f8995.compute(scenario, upstream=upstream)
            if has_qbi_source else {}
        )
        if self._should_emit_8995(f8995_values):
            specs.append(_FederalFormSpec(
                name="f8995", template=_fed("f8995.pdf"),
                output_name=f"f8995_{year}.pdf", kind="flat",
                mapping=PdfF8995.get_mapping(year)["scalars"],
                values=PdfF8995.presentation_values(f8995_values),
            ))

        if self._should_emit_8582(scenario, upstream):
            # Reuse sch_e_values if already computed above; otherwise compute
            # Part I now so 8582 has rental loss context even when Sch E wasn't
            # emitted (e.g. only passive K-1 activity, no rental property).
            if not sch_e_values:
                sch_e_values = form_sch_e.compute(scenario, upstream=upstream)
            specs.append(_FederalFormSpec(
                name="f8582", template=_fed("f8582.pdf"),
                output_name=f"f8582_{year}.pdf", kind="flat",
                mapping=PdfF8582.get_mapping(year)["scalars"],
                values=form_f8582.compute(scenario, upstream={
                    **upstream, "sch_e": sch_e_values,
                }),
            ))

        return specs

    @staticmethod
    def _render_federal_spec(
        filler: PdfFiller, spec: _FederalFormSpec, output_dir: Path,
    ) -> Path:
        """Render one prepared spec to ``output_dir/<output_name>``."""
        out = output_dir / spec.output_name
        if spec.kind == "flat":
            filler.fill(
                template_path=spec.template, output_path=out,
                field_mapping=spec.mapping, values=spec.values,
                checkbox_states=spec.checkbox_states or None,
                derivations=spec.derivations or None,
                field_formats=spec.field_formats or None,
            )
        else:
            filler.fill_with_repeaters(
                template_path=spec.template, output_path=out,
                mapping=spec.mapping, values=spec.values,
            )
        return out

    @staticmethod
    def _federal_spec_payload(spec: _FederalFormSpec) -> dict[str, str]:
        """The exact ``{pdf_field: value}`` dict this form would render — the
        changed-forms selector compares these across the as-filed and corrected
        runs. Built via the same PdfFiller resolution the render uses, so the
        payload cannot drift from what fills."""
        if spec.kind == "flat":
            return PdfFiller.resolve_fields(
                spec.mapping, spec.values,
                checkbox_states=spec.checkbox_states or None,
                derivations=spec.derivations or None,
                field_formats=spec.field_formats or None,
            )
        return PdfFiller._expand_repeaters(spec.mapping, spec.values)

    def _emit_federal_corporate_pdfs_internal(
        self, scenario: Scenario, results: dict, output_dir: Path,
    ) -> dict[str, Path]:
        """Emit the federal Form 1120-S + one Schedule K-1 (1120-S) per
        shareholder from a corporate results dict. Returns {} when
        scenario.s_corp_return is None. Split out of _emit_pdfs_internal so the
        S-corp-only years (e.g. 2021, which has no 1040 spine) can emit the
        corporate set WITHOUT running the individual 1040 pipeline."""
        emitted: dict[str, Path] = {}
        if scenario.s_corp_return is None:
            return emitted
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        validate_tax_year_dates(scenario.s_corp_return, year)
        filler = PdfFiller()
        amended = scenario.s_corp_return.amended_return
        # Schedule B must be fully answered before anything is printed: an
        # unstated question would leave its boxes blank on a return that gets
        # signed. Compute never asks; emit refuses (all gaps listed at once).
        form_f1120s.check_schedule_b_for_emit(scenario)
        form_f1120s.check_other_deductions_statement_for_emit(scenario)

        # Main 1120-S + Sch B + Sch K.
        main_template = _PDFS_ROOT / "federal" / str(year) / "f1120s.pdf"
        main_output = output_dir / f"f1120s_{year}.pdf"
        # §4a: mark box H(4) "Amended return" only when flagged. ADDITIVE —
        # merged onto the mapping/checkbox_states/values passed to fill; when
        # not amended nothing is added, so the box stays /Off.
        main_mapping = PdfF1120S.get_mapping(year)
        main_checkbox = PdfF1120S.get_checkbox_states(year)
        # Page-1 header identity block (name/address, items A/D/E/F/I): injected
        # from the SCorpReturn, additive to the compute results (mirrors the CA
        # 100S entity identity at _emit_ca_scorp_pdfs_internal).
        header_cells = PdfF1120S.get_entity_header_fields(year)
        main_mapping = {**main_mapping, **header_cells}
        main_values: dict = {
            **results, **_entity_header_values(scenario.s_corp_return)}
        if amended:
            m_path, m_on = PdfF1120S.get_amended_mark(year)
            main_mapping = {**main_mapping, "f1120s_amended_return": m_path}
            main_checkbox = {**main_checkbox, "f1120s_amended_return": m_on}
            main_values = {**main_values, "f1120s_amended_return": True}
        # Item G (Yes / No: the chosen box only) and item H check-if boxes
        # (only True marks; False / None leave the box blank). Additive.
        r_ = scenario.s_corp_return
        if r_.electing_s_this_year is not None:
            g_path, g_on = PdfF1120S.get_item_g_cells(year)[
                r_.electing_s_this_year]
            main_mapping = {**main_mapping, "f1120s_item_g": g_path}
            main_checkbox = {**main_checkbox, "f1120s_item_g": g_on}
            main_values = {**main_values, "f1120s_item_g": True}
        if r_.discuss_with_preparer is not None:
            d_path, d_on = PdfF1120S.get_discuss_cells(year)[
                r_.discuss_with_preparer]
            main_mapping = {**main_mapping, "f1120s_discuss": d_path}
            main_checkbox = {**main_checkbox, "f1120s_discuss": d_on}
            main_values = {**main_values, "f1120s_discuss": True}
        for item, (h_path, h_on) in PdfF1120S.get_item_h_cells(year).items():
            if getattr(r_, item) is True:
                key = f"f1120s_item_h_{item}"
                main_mapping = {**main_mapping, key: h_path}
                main_checkbox = {**main_checkbox, key: h_on}
                main_values = {**main_values, key: True}
        # Pass the full results dict — aggregation and derivation lambdas
        # reference keys that are NOT in _MAPPING_<year>, so filtering to
        # mapping keys alone would silently drop those inputs.
        filler.fill(
            template_path=main_template,
            output_path=main_output,
            values=main_values,
            field_mapping=main_mapping,
            aggregations=PdfF1120S.get_aggregations(year),
            derivations=PdfF1120S.get_derivations(year),
            checkbox_states=main_checkbox,
            blank_when_zero=PdfF1120S.get_blank_when_zero(year),
        )
        emitted["1120s"] = main_output

        # Per-shareholder Sch K-1.
        #
        # The compute output's allocation is a typed `K1Allocation`
        # dataclass with nested `entity` / `shareholder` sub-dataclasses
        # and an `Address` for each. The K-1 PDF combines name+address
        # into a single multi-line cell per party (Part I field B for
        # the corporation, Part II field F1 for the shareholder); the
        # mapping uses one flat compute key per party for that combined
        # block. `_flatten_k1_party` is the boundary: typed for
        # programmatic consumers, flat with assembled name+address
        # strings for the form filler.
        k1_template = _PDFS_ROOT / "federal" / str(year) / "f1120s_k1.pdf"
        # §4a: "Amended K-1" checkbox on every K-1 when flagged. ADDITIVE —
        # merged per shareholder onto the fill inputs.
        k1_mapping = PdfF1120SK1.get_mapping(year)
        k1_checkbox: dict[str, str] = {}
        k1_amended_values: dict = {}
        if amended:
            k1_path, k1_on = PdfF1120SK1.get_amended_mark(year)
            k1_mapping = {**k1_mapping, "k1_amended_return": k1_path}
            k1_checkbox = {"k1_amended_return": k1_on}
            k1_amended_values = {"k1_amended_return": True}
        stated_shareholders = scenario.s_corp_return.shareholders
        for i, alloc in enumerate(
            results.get("f1120s_sch_k1_allocations", []),
            start=1,
        ):
            # Allocations are built one per shareholder in scenario order
            # (f1120s._compute_schedule_k1_allocations), so index i-1 is this K-1's shareholder.
            sh = stated_shareholders[i - 1]
            this_mapping, this_checkbox, final_values = k1_mapping, k1_checkbox, {}
            if sh.final_k1:
                f_path, f_on = PdfF1120SK1.get_final_mark(year)
                this_mapping = {**k1_mapping, "k1_final": f_path}
                this_checkbox = {**k1_checkbox, "k1_final": f_on}
                final_values = {"k1_final": True}
            flat_values = {
                **_k1_tax_year_header_values(scenario.s_corp_return),
                "k1_irs_center": scenario.s_corp_return.irs_center,
                "k1_total_shares_beginning":
                    scenario.s_corp_return.total_shares_beginning,
                "k1_total_shares_end": scenario.s_corp_return.total_shares_end,
                "k1_shares_beginning": sh.shares_beginning,
                "k1_shares_end": sh.shares_end,
                "k1_loans_beginning": sh.loans_beginning,
                "k1_loans_end": sh.loans_end,
                **final_values,
                **_flatten_k1_party("entity", alloc.entity),
                **_flatten_k1_party("shareholder", alloc.shareholder),
                "ownership_percentage": alloc.ownership_percentage,
                "box_1_ordinary_business_income":
                    alloc.box_1_ordinary_business_income,
                "box_17_code_v": "V",
                "box_17_code_v_amount": "STMT",
                # Box 16 code D (distributions): only when there is one.
                **({"box_16_code_d": "D",
                    "box_16_code_d_amount": alloc.box_16d_distributions}
                   if alloc.box_16d_distributions else {}),
                **k1_amended_values,
            }
            k1_output = output_dir / f"f1120s_k1_{i}_{year}.pdf"
            filler.fill(
                template_path=k1_template,
                output_path=k1_output,
                values=flat_values,
                field_mapping=this_mapping,
                checkbox_states=this_checkbox or None,
                field_formats=PdfF1120SK1.get_field_formats(year),
            )
            emitted[f"1120s_k1_{i}"] = k1_output

            stmt_output = output_dir / f"f1120s_k1_qbi_stmt_{i}_{year}.pdf"
            render_199a_statement_a(alloc, year, stmt_output)
            emitted[f"1120s_k1_qbi_stmt_{i}"] = stmt_output

        # Line 19 "Other deductions (attach statement)": generated only when
        # itemized (the emit gate above refuses a nonzero line without it).
        comps = scenario.s_corp_return.deductions.other_deductions_components
        if comps:
            od_output = output_dir / f"f1120s_other_deductions_stmt_{year}.pdf"
            render_other_deductions_statement(
                scenario.s_corp_return.name, scenario.s_corp_return.ein,
                year, comps, od_output)
            emitted["1120s_other_deductions_stmt"] = od_output

        return emitted

    def _emit_ca_pdfs_internal(
        self,
        scenario: Scenario,
        ca_results: dict,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Render the CA-state PDFs (f540, sch_ca and, when required,
        sch_d_540) from a CA compute results dict.

        Mechanical helper: consumes ``ca_results`` as-is and writes PDFs.
        Does NOT mutate, merge, or augment ``ca_results`` — callers
        (``run_full_california_return``) are responsible for ensuring
        required PDF compute keys (e.g. ``f540_taxpayer_name``,
        ``sch_ca_taxpayer_ssn``, ``sch_d_540_taxpayer_name``, etc.) are
        present in the dict before invocation.

        Schedule D (540) is rendered only when California capital gains
        differ from federal (``form_sch_d_540.is_required``); its instructions
        say not to complete it otherwise, so it is omitted — no file is
        written and the key is absent from the result.

        Returns a dict mapping ``"f540"`` and ``"sch_ca"`` (always) and
        ``"sch_d_540"`` (only when required) to the filled PDF paths.
        """
        year = scenario.config.year
        # Full-year health-care-coverage attestation (Form 540 line 92). An
        # unstated answer cannot be printed as a blank box on a return that
        # gets signed — it would read as "no coverage" with no penalty — so
        # emit refuses; the CA COMPUTE path never asks. (A stated coverage gap
        # is refused earlier, in forms.f540.presentation_keys.)
        if scenario.config.full_year_health_care_coverage is None:
            raise ValueError(
                "Form 540 PDF emission needs the full-year health care "
                f"coverage question answered for tax year {year}: set "
                "`full_year_health_care_coverage` in the scenario config to "
                "true or false (Form 540 line 92: 'If you and your household "
                "had full-year health care coverage, check the box'). It is "
                "left unanswered (null) in this scenario."
            )
        # Line 112 (interest and penalties). Unstated is fine on a pure refund
        # return, which never reads the line; on any other return it enters
        # the total amount due (line 114) or reduces the refund (line 115), so
        # emit refuses rather than count an unstated amount as zero. The CA
        # COMPUTE path never asks.
        if (ca_results["f540_interest_and_penalties"] is None
                and interest_and_penalties_must_be_stated(
                    year, ca_results)):
            raise ValueError(
                "Form 540 PDF emission needs `interest_and_penalties` stated "
                f"in the CA YAML `ca540:` block for tax year {year}: this "
                "return shows an amount you owe (line 111) or carries a "
                "voluntary contribution (line 110) or an underpayment penalty "
                "(line 113), so line 112 (interest, late return penalties, "
                "and late payment penalties) enters the total amount due on "
                "line 114 or reduces the refund on line 115. Set it to 0 if "
                "the return is filed and paid on time, or to the amount owed. "
                "It is left unstated (null) here."
            )
        validate_third_party_designee(scenario.config)
        output_dir.mkdir(parents=True, exist_ok=True)
        filler = PdfFiller()

        emitted: dict[str, Path] = {}
        for basename, mapping_cls in _CA_FORMS_BY_BASENAME:
            if basename == "sch_d_540" and not form_sch_d_540.is_required(ca_results):
                continue
            template = _PDFS_ROOT / "california" / str(year) / f"{basename}.pdf"
            output_path = output_dir / f"{basename}_{year}.pdf"
            filler.fill(
                template_path=template,
                output_path=output_path,
                field_mapping=mapping_cls.get_mapping(year),
                values=ca_results,
                aggregations=mapping_cls.get_aggregations(year),
                derivations=mapping_cls.get_derivations(year),
                checkbox_states=mapping_cls.get_checkbox_states(year),
            )
            emitted[basename] = output_path

        return emitted

    def _emit_ca_scorp_pdfs_internal(
        self,
        scenario: Scenario,
        ca_corporate_results: dict,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Emit CA Form 100S + one Schedule K-1 (100S) per shareholder.

        Returns {} unless scenario.s_corp_return and its .ca sub-block are both
        set. Mirrors the federal 1120-S emit block. Identity, the line-21 rate,
        and the split ownership-% are INJECTED here from the scenario and the
        attested CA S-corp params (they are not f100s.compute outputs).
        """
        r = scenario.s_corp_return
        if r is None or r.ca is None:
            return {}
        # Sch F line 20 passes the federal line 19 figure through, so the same
        # attached-statement requirement (and footing rule) applies here.
        form_f1120s.check_other_deductions_statement_for_emit(scenario)
        validate_unclaimed_property(r.ca)
        validate_tax_year_dates(r, scenario.config.year)
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        filler = PdfFiller()
        emitted: dict[str, Path] = {}

        rate = _format_rate_percent(ca_scorp.load(year).franchise_tax_rate)
        f100s_values = {
            **ca_corporate_results,
            "f100s_entity_name": r.name,
            "f100s_entity_fein": r.ein,
            "f100s_entity_street": r.address.street,
            "f100s_entity_city": r.address.city,
            "f100s_entity_state": r.address.state,
            "f100s_entity_zip": r.address.zip_code,
            "f100s_tax_rate": rate,
            "f100s_entity_date_incorporated":
                _format_mmddyyyy(r.date_incorporated),
            "f100s_entity_s_election_date":
                _format_mmddyyyy(r.s_election_effective_date),
            "f100s_entity_officer_title": r.officer_title,
            **({"f100s_entity_tax_year_begin":
                    r.tax_year_beginning.strftime("%m/%d/%Y"),
                "f100s_entity_tax_year_end":
                    r.tax_year_ending.strftime("%m/%d/%Y")}
               if r.tax_year_beginning and r.tax_year_ending else {}),
            "f100s_entity_activity_code":
                r.schedule_b_answers.business_activity_code,
            "f100s_entity_business_activity":
                r.schedule_b_answers.business_activity_description,
            "f100s_entity_product_or_service":
                r.schedule_b_answers.product_or_service,
            "f100s_entity_max_shareholders": r.ca.max_shareholders,
            "f100s_entity_date_began_in_ca":
                None if r.ca.date_business_began_in_ca is None
                else _format_mmddyyyy(r.ca.date_business_began_in_ca),
            **_unclaimed_property_values(r.ca),
            "f100s_entity_state_incorporated": r.ca.state_of_incorporation,
            "f100s_entity_country_incorporated": r.ca.country_of_incorporation,
            "f100s_entity_ca_corp_number": r.ca.corporation_number,
        }
        f100s_mapping = PdfF100S.get_mapping(year)
        f100s_checkbox: dict[str, str] = {}
        # Schedule Q stated answers: only the CHOSEN answer's box is merged in
        # (additive, like the amended marks), so a Yes/No/N-A group can never
        # carry two marks. A year with no certified cells refuses a stated
        # answer rather than dropping it.
        stated_q = {
            "under_irs_audit": r.ca.under_irs_audit,
            "information_returns_filed": r.ca.information_returns_filed,
            "water_edge_basis": r.ca.water_edge_basis,
            "includes_qsubs": r.ca.includes_qsubs,
            "included_reportable_transaction":
                r.ca.included_reportable_transaction,
            "filed_federal_schedule_m3": r.ca.filed_federal_schedule_m3,
            "ftb_3544_attached": r.ca.ftb_3544_attached,
            "inactive_business": r.ca.inactive_business,
            "filed_unclaimed_property_report":
                r.ca.filed_unclaimed_property_report,
            "discuss_with_preparer": r.ca.discuss_with_preparer,
        }
        # The preparer-discussion answer (signature block) exists on every
        # year's form incl. 2021, so it is exempt from the Schedule Q floor.
        floored = [k for k, a in stated_q.items()
                   if a is not None and k != "discuss_with_preparer"]
        if floored:
            if year < 2022:
                raise ValueError(
                    f"California Form 100S Schedule Q answers are supported "
                    f"for tax years 2022 and later; tax year {year} cannot "
                    "print them. Remove the stated Schedule Q answers "
                    f"({', '.join(floored)}) from s_corp_return.ca.")
        q_cells = PdfF100S.get_schedule_q_cells(year)
        # Question P is DERIVED: v1 supports only 100% California
        # apportionment (gated at load), so Schedule R is never used -> No.
        chosen_q = {**{k: a for k, a in stated_q.items() if a is not None},
                    "apportioning_with_schedule_r":
                        not r.ca.apportionment_ca_only}
        for question, answer in chosen_q.items():
            if question not in q_cells:
                raise ValueError(
                    f"California Form 100S {year} has no {question!r} "
                    "question; remove it from s_corp_return.ca.")
            q_path, q_on = q_cells[question][answer]
            key = f"f100s_q_{question}"
            f100s_mapping = {**f100s_mapping, key: q_path}
            f100s_checkbox[key] = q_on
            f100s_values[key] = True
        # Question L accounting method (from the federal Schedule B answer).
        l_path, l_on = PdfF100S.get_accounting_method_cells(year)[
            r.schedule_b_answers.accounting_method.value]
        f100s_mapping = {**f100s_mapping, "f100s_q_accounting_method": l_path}
        f100s_checkbox["f100s_q_accounting_method"] = l_on
        f100s_values["f100s_q_accounting_method"] = True
        f100s_template = _PDFS_ROOT / "california" / str(year) / "f100s.pdf"
        f100s_output = output_dir / f"f100s_{year}.pdf"
        filler.fill(template_path=f100s_template, output_path=f100s_output,
                    field_mapping=f100s_mapping, values=f100s_values,
                    checkbox_states=f100s_checkbox or None,
                    blank_when_zero=PdfF100S.get_blank_when_zero(year))
        emitted["f100s"] = f100s_output

        k1_template = _PDFS_ROOT / "california" / str(year) / "f100s_k1.pdf"
        # §4a: line E "amended Schedule K-1" mark when flagged. PER-YEAR path +
        # ON-token (checkbox /Yes 2021-23; radio 2024-25). ADDITIVE — merged
        # onto the fill inputs; unset otherwise.
        k1_mapping = PdfF100SK1.get_mapping(year)
        k1_checkbox: dict[str, str] = {}
        k1_amended_values: dict = {}
        if r.amended_return:
            a_path, a_on = PdfF100SK1.get_amended_mark(year)
            k1_mapping = {**k1_mapping, "k1_amended_return": a_path}
            k1_checkbox = {"k1_amended_return": a_on}
            k1_amended_values = {"k1_amended_return": True}
        for i, alloc in enumerate(
                ca_corporate_results.get("f100s_k1_allocations", []), start=1):
            sh = r.shareholders[alloc["shareholder_index"]]
            this_mapping, this_checkbox, final_values = (
                k1_mapping, k1_checkbox, {})
            if sh.final_k1:
                if r.amended_return and (
                        PdfF100SK1.final_and_amended_share_one_field(year)):
                    raise ValueError(
                        f"Schedule K-1 (100S) {year} line E holds 'final' and "
                        "'amended' as two states of ONE radio, so a K-1 cannot "
                        f"be both. Shareholder {sh.name!r} is flagged final_k1 "
                        "on an amended return: emit them as separate runs or "
                        "unflag one.")
                f_path, f_on = PdfF100SK1.get_final_mark(year)
                this_mapping = {**k1_mapping, "k1_final": f_path}
                this_checkbox = {**k1_checkbox, "k1_final": f_on}
                final_values = {"k1_final": True}
            # Lines F (entity type) and G (CA resident): only the CHOSEN
            # answer's cell is merged, so each group is mutually exclusive.
            for stated, cells, tag in (
                    (sh.ca_entity_type, PdfF100SK1.get_entity_type_cells(year),
                     "k1_entity_type"),
                    (sh.ca_resident, PdfF100SK1.get_resident_cells(year),
                     "k1_ca_resident")):
                if stated is None:
                    continue
                c_path, c_on = cells[stated]
                this_mapping = {**this_mapping, tag: c_path}
                this_checkbox = {**this_checkbox, tag: c_on}
                final_values = {**final_values, tag: True}
            whole, frac = _split_ownership_percent(alloc["ownership_fraction"])
            k1_values = {
                "k1_shareholder_name": sh.name,
                "k1_shareholder_id": sh.ssn_or_ein,
                **({"k1_tax_year_begin":
                        r.tax_year_beginning.strftime("%m/%d/%Y"),
                    "k1_tax_year_end":
                        r.tax_year_ending.strftime("%m/%d/%Y")}
                   if r.tax_year_beginning and r.tax_year_ending else {}),
                "k1_corp_fein": r.ein,
                "k1_corp_name": r.name,
                "k1_shareholder_street": sh.address.street,
                "k1_shareholder_city": sh.address.city,
                "k1_shareholder_state": sh.address.state,
                "k1_shareholder_zip": sh.address.zip_code,
                "k1_corp_street": r.address.street,
                "k1_corp_city": r.address.city,
                "k1_corp_state": r.address.state,
                "k1_corp_zip": r.address.zip_code,
                "k1_shares_beginning": sh.shares_beginning,
                "k1_shares_end": sh.shares_end,
                "k1_loans_beginning": sh.loans_beginning,
                "k1_loans_end": sh.loans_end,
                "k1_corp_total_shares_beginning": r.total_shares_beginning,
                "k1_corp_total_shares_end": r.total_shares_end,
                **final_values,
                "k1_ownership_pct_whole": whole,
                "k1_ownership_pct_frac": frac,
                "k1_federal_ordinary_income": alloc["federal_ordinary_income"],
                "k1_ca_ordinary_income_total": alloc["ca_ordinary_income"],
                "k1_ca_ordinary_income_source": alloc["ca_ordinary_income"],
                "k1_corp_ca_number": r.ca.corporation_number,
                **k1_amended_values,
            }
            k1_output = output_dir / f"f100s_k1_{i}_{year}.pdf"
            filler.fill(template_path=k1_template, output_path=k1_output,
                        field_mapping=this_mapping, values=k1_values,
                        checkbox_states=this_checkbox or None,
                        field_formats=PdfF100SK1.get_field_formats(year))
            emitted[f"f100s_k1_{i}"] = k1_output

        comps = r.deductions.other_deductions_components
        if comps:
            od_output = output_dir / f"f100s_other_deductions_stmt_{year}.pdf"
            render_ca_100s_other_deductions_statement(
                r.name, r.ein, year, comps, od_output)
            emitted["f100s_other_deductions_stmt"] = od_output
        return emitted

    def _refuse_missing_source_documents(self, scenario: Scenario) -> None:
        """Emit-time gate: every W-2 needs its Copy B PDF, or an attestation.

        Fires for EVERY W-2 lacking `pdf` — the IRS attachment rule is not
        withholding-conditional (Copy B attaches for every W-2; the
        withholding condition applies to W-2G/1099-R, unmodeled). Lives here
        rather than the load/compute attestation registry so compute-only
        scenarios are never burdened; see the source-documents spec.

        Checks w2s[*].pdf, while assembly consumes scenario.source_documents;
        the two agree only because load_scenario normalizes one from the
        other (see the Scenario.source_documents field note).
        """
        if scenario.config.acknowledges_no_source_documents:
            return
        missing = [w2.employer for w2 in scenario.w2s if not w2.pdf]
        if missing:
            raise ValueError(
                "Filing-packet emit requires a source document (Copy B PDF) "
                f"for every W-2; missing for: {', '.join(missing)}. Add a "
                "`pdf:` field to each w2s entry, or set "
                "`acknowledges_no_source_documents: true` under config to "
                "emit without them.")

    def run_full_return(
        self,
        scenario: Scenario,
        output_dir: Path,
    ) -> tuple[dict[str, object], dict[str, Path]]:
        """Compute the full federal return and emit PDFs to output_dir.

        The two-call pattern (`compute_federal` then `emit_pdfs`) cannot keep
        both ends consistent for S-corp scenarios, because `compute_federal`'s
        effective scenario (with the synthesized K-1) is not exposed to
        `emit_pdfs`; this method holds both ends so the rendered Sch E PDF
        reflects the same K-1 list the numerical results were computed against.

        This is the canonical entry point for S-corp scenarios: it builds
        the effective scenario (with synthesized K-1s) internally and feeds
        it to the PDF emit step, so the Sch E PDF reflects the corp-pipeline
        K-1. The caller's scenario is never mutated.

        Returns a tuple of (results, emitted) where results is the merged
        1040+corp output dict and emitted maps form names to PDF paths.
        """
        self._refuse_missing_source_documents(scenario)
        effective_scenario, corp_results = self._build_effective_scenario(scenario)
        results_1040 = self._compute_1040_pipeline(effective_scenario)
        results = {**corp_results, **results_1040}
        emitted = self._emit_pdfs_internal(effective_scenario, results, output_dir)
        return results, emitted

    def _reject_legacy_fods(self, federal_yaml_path: Path) -> None:
        """Detect-and-explain guard for the retired ``.ca.fods`` worksheet.

        The FODS worksheet round-trip was retired (docs/specs/2026-07-19-ca-
        divergence-catalog-redesign.md §3): the CA divergence catalog is now
        the single runtime source of truth and user divergences are authored
        directly in the ``.ca.yaml``. For one release we detect a leftover
        ``<basename>.ca.fods`` and RAISE an explanatory error rather than
        silently ignoring it — a silent ignore would drop the user's amounts.
        """
        candidate = federal_yaml_path.with_suffix(".ca.fods")
        if candidate.exists():
            raise ValueError(
                f"Found a legacy CA divergence worksheet at {candidate}. "
                "The `.ca.fods` worksheet round-trip has been RETIRED "
                "(docs/specs/2026-07-19-ca-divergence-catalog-redesign.md §3). "
                "Author your CA divergences directly in the `.ca.yaml` instead, "
                "using the `divergences:` list (id + amount, validated against "
                "the year's CA divergence catalog) and the `reviewed:` list for "
                "triggered entries you examined and zeroed. Then delete the "
                f"`{candidate.name}` file. See the catalog ids in "
                "tenforty/params/california/divergences/y<year>.yaml."
            )

    def run_full_california_return(
        self,
        scenario: Scenario,
        ca_yaml_path: Path,
        output_dir: Path,
        federal_yaml_path: Path | None = None,
    ) -> tuple[dict, dict[str, Path]]:
        """Canonical CA-state entry point. Re-derives federal results, runs
        Sch CA + Sch D 540 + 540 main compute, emits state PDFs.

        The CA YAML at ``ca_yaml_path`` is the v1 source-of-truth for
        CA-specific data (divergences, voluntary contributions, estimated
        payments, etc.). Convention: place it next to the federal YAML as
        ``<basename>.ca.yaml`` (e.g. ``alice_2025.yaml`` +
        ``alice_2025.ca.yaml``); not enforced by this method.

        The CA YAML's envelope:
            ca540:                  # required — CA540Return fields
              divergences: [...]
              estimated_payments: 0.0
              ...
            federal_context:        # optional — reserved for post-v1 freshness
              ...

        v1 gaps (tracked as follow-ups, not addressed in this method):
        - Renter's credit eligibility is hard-coded False (no field on
          CA540Return yet).
        - CA itemized deductions are not supported (CA disallows the federal
          SALT cap, etc. — separate from federal Sch A).
        - Freshness verification of the CA YAML's federal_context block
          against live federal compute outputs is a no-op stub.

        Returns ``(ca_results, ca_pdfs)`` where ``ca_results`` is the merged
        compute dict (with header keys) and ``ca_pdfs`` maps form basename
        to PDF path.
        """
        self._refuse_missing_source_documents(scenario)
        # 1. Load CA YAML (envelope: top-level ca540: required, federal_context: optional).
        with open(ca_yaml_path) as f:
            ca_yaml = yaml.safe_load(f) or {}

        # 2. Freshness check — v1 no-op stub.
        self._verify_ca_yaml_freshness(scenario, ca_yaml_path, ca_yaml)

        # 3. Build effective CA540Return — ca_yaml is authoritative, but conflict-detect.
        effective_ca540 = self._build_effective_ca540(
            scenario.ca540, ca_yaml, scenario.config.year)

        # 3b. Detect-and-explain guard for the retired `.ca.fods` worksheet.
        #     Divergences now live in the `.ca.yaml` (spec §3); a leftover
        #     worksheet raises rather than being silently ignored.
        if federal_yaml_path is not None:
            self._reject_legacy_fods(federal_yaml_path)
        # 4. Re-derive federal results. compute_federal exposes sch_1_line_*
        #    keys directly (per #80), so downstream CA computes consume the
        #    federal results dict without an interim bridge.
        federal_results = self.compute_federal(scenario)

        # 5-7. CA computes (Sch CA → Sch D 540 → Form 540 main) + header merge.
        ca_results = self._compute_ca_results(
            scenario, effective_ca540, federal_results,
        )

        # 8. Emit PDFs.
        ca_pdfs = self._emit_ca_pdfs_internal(scenario, ca_results, output_dir)

        # 9. Emit resolved snapshot (skipped when no federal_yaml_path — older
        #    callers without a federal YAML don't get a snapshot).
        if federal_yaml_path is not None:
            self._emit_ca_resolved_snapshot(
                federal_yaml_path=federal_yaml_path,
                output_dir=output_dir,
                effective_ca540=effective_ca540,
                federal_results=federal_results,
                year=scenario.config.year,
            )

        return ca_results, ca_pdfs

    def _compute_ca_results(
        self,
        scenario: Scenario,
        effective_ca540: CA540Return,
        federal_results: dict,
    ) -> dict:
        """Compute the merged CA-state results dict (Sch CA → Sch D 540 →
        Form 540 main + identity header keys) from an already-resolved
        ``effective_ca540`` and ``federal_results``.

        Extracted from ``run_full_california_return`` (steps 5-7) so the
        amendment packet can reuse the exact CA compute core without
        re-implementing it. ``run_full_california_return`` sources
        ``effective_ca540`` from a CA YAML block; ``run_amendment_packet``
        sources it from ``scenario.ca540``. Both feed the SAME compute here so
        the amended 540 can never drift from a normally-filed 540.

        ``f540.compute`` raises NotImplementedError above the CA AGI phaseout
        threshold; that propagates unwrapped.
        """
        # Acknowledgment gate (spec §2.5): a gated + triggered Schedule CA
        # divergence must be applied or reviewed, or the return REFUSES. Run
        # BEFORE any form compute so a refusal never yields a partial result.
        # (Both the normal and amendment paths route through here; ca540 None ->
        # no gate.)
        check_unaddressed_divergences(
            scenario, effective_ca540, scenario.config.year)
        sch_ca_results = form_sch_ca.compute(
            effective_ca540, federal_results, scenario.config.year)
        sch_d_540_results = form_sch_d_540.compute(federal_results)
        # Schedule CA Part II — CA itemized deductions, computed only when the
        # federal return actually APPLIED itemized deductions (see
        # sch_ca.federal_itemization_applied). Inherits sch_a.compute's scope
        # gates (only the 2025 SALT-phaseout gate can fire for a CA resident).
        ca_part_ii: dict = {}
        if form_sch_ca.federal_itemization_applied(federal_results):
            sch_a_full = form_sch_a.compute(
                _scenario_with_effective_itemized(scenario),
                {"f1040": federal_results},
            )
            ca_part_ii = form_sch_ca.compute_part_ii_itemized(sch_a_full)
        # Attribution guard for CA 540 line 71. There are TWO CA-return entry
        # points and this covers the one __post_init__ CANNOT:
        #   1. scenario.ca540 is not None (combined-YAML / programmatic) —
        #      Scenario.__post_init__ already refuses an unattributed
        #      withholding W-2 at construction time.
        #   2. run_full_california_return's separate-CA-YAML path — the
        #      scenario is loaded from a federal-only YAML, so scenario.ca540
        #      is None and __post_init__'s guard never fires; yet
        #      _compute_ca_results still sources line 71 from scenario.w2s
        #      where state=="CA". For THIS path this guard is the SOLE
        #      attribution enforcement — not redundant. Same refusal
        #      semantics as the __post_init__ guard so both paths agree.
        for w in scenario.w2s:
            if w.state is None and w.state_tax_withheld > 0:
                raise ValueError(
                    f"W-2 from {w.employer!r} has state tax withheld "
                    f"(${w.state_tax_withheld:.2f}) but no state "
                    f"attribution; a California Form 540 return must "
                    f"attribute each withholding W-2 to a state so only "
                    f"CA withholding is claimed on line 71 -- add "
                    f'state="CA" (or the actual 2-letter state code) to '
                    f"that W-2."
                )
        ca_withholding = sum(
            w.state_tax_withheld for w in scenario.w2s if w.state == "CA"
        )
        f540_results = form_f540.compute(
            year=scenario.config.year,
            filing_status=scenario.config.filing_status,
            federal_agi=federal_results["agi"],
            ca_agi=sch_ca_results["sch_ca_ca_agi"],
            ca540=effective_ca540,
            num_dependents=len(scenario.config.dependents),
            ca_itemized=ca_part_ii.get("ca_itemized_total"),
            ca_withholding=int(ca_withholding),
        )
        header_keys = {
            "f540_taxpayer_name": scenario.config.full_name,
            "f540_taxpayer_ssn": scenario.config.ssn,
            "sch_ca_taxpayer_name": scenario.config.full_name,
            "sch_ca_taxpayer_ssn": scenario.config.ssn,
            "sch_d_540_taxpayer_name": scenario.config.full_name,
            "sch_d_540_taxpayer_ssn": scenario.config.ssn,
            **form_f540.presentation_keys(
                scenario.config, scenario.w2s, scenario.config.year),
        }
        return {
            **sch_ca_results,
            **ca_part_ii,
            **sch_d_540_results,
            **f540_results,
            **header_keys,
        }

    def run_amendment_packet(
        self,
        original_scenario: Scenario,
        amended_scenario: Scenario,
        case: AmendmentCase,
        filed_path: Path,
        ca_filed_path: Path,
        output_dir: Path,
    ) -> PacketManifest:
        """Assemble + emit the complete amendment mailing packet, return its
        manifest (spec §3/§4/§6). Public entry mirroring
        ``run_full_california_scorp_return``'s style.

        Emits, into ``output_dir``:
          * ``f1040x_<year>.pdf`` — Form 1040-X (Column A from ``filed_path``,
            Column C from the corrected run; assembler guards propagate).
          * each SELECTED changed federal individual form (machine-derived by
            comparing the as-filed run's per-form emit payloads to the corrected
            run's) — and ONLY those. Full-emit federal years only; a federal
            compute-only year (e.g. 2021) emits the 1040-X alone and the
            manifest notes attachments are unavailable.
          * when the amended scenario has a CA side: ``schedule_x_<year>.pdf``
            (all amendable CA years) and the COMPLETE amended 540
            (``f540_amended_<year>.pdf`` + Sch CA + Sch D-540) — the latter only
            for full-emit CA years; a CA compute-only year emits Schedule X
            alone and the manifest notes the 540 must be prepared separately.
          * ``packet_manifest.txt`` — the rendered :class:`PacketManifest`.

        The assemblers raise OutOfScopeAmendmentError / MissingFiledValueError /
        consistency ValueErrors; those PROPAGATE unwrapped.
        """
        from tenforty import years, selector, amendment
        from tenforty.forms import f1040x as form_f1040x
        from tenforty.forms import schedule_x as form_schedule_x

        output_dir.mkdir(parents=True, exist_ok=True)
        year = amended_scenario.config.year
        filler = PdfFiller()
        mailed: list[MailedFile] = []
        caveats: list[str] = [_ERRONEOUS_INCLUSION_CAVEAT]
        dropped: tuple[str, ...] = ()
        ca_divergences = CADivergenceTrail()
        schedule_x_values: dict = {}

        # --- Federal: corrected run feeds Column C; filed file is Column A. ---
        eff_amended, corp_amended = self._build_effective_scenario(amended_scenario)
        corrected_federal = {
            **corp_amended, **self._compute_1040_pipeline(eff_amended)}

        filed = amendment.load_filed_values(
            filed_path, form_f1040x.REQUIRED_FILED_KEYS)
        f1040x_values = form_f1040x.assemble(filed, corrected_federal, case)
        revision = years.AMENDMENT_TEMPLATE_REVISIONS["f1040x"]
        self._emit_flat(
            filler,
            _PDFS_ROOT / "federal" / "amendments" / "f1040x.pdf",
            output_dir / f"f1040x_{year}.pdf",
            {**PdfF1040X.get_mapping(revision),
             **PdfF1040X.get_presentation_mapping(revision)},
            {**f1040x_values,
             **form_f1040x.presentation_keys(amended_scenario.config)},
            checkbox_states=PdfF1040X.get_checkbox_states(revision),
        )
        mailed.append(MailedFile(
            f"f1040x_{year}.pdf", "Form 1040-X (amended federal return)",
            "amendment form"))

        # --- Federal changed-form attachments (full-emit federal years only) ---
        if year in years.FEDERAL_YEARS:
            eff_original, corp_original = self._build_effective_scenario(
                original_scenario)
            original_federal = {
                **corp_original, **self._compute_1040_pipeline(eff_original)}
            filed_specs = self._federal_individual_emit_specs(
                eff_original, original_federal)
            corrected_specs = {
                s.name: s for s in self._federal_individual_emit_specs(
                    eff_amended, corrected_federal)}
            filed_payloads = {
                s.name: self._federal_spec_payload(s) for s in filed_specs}
            corrected_payloads = {
                name: self._federal_spec_payload(s)
                for name, s in corrected_specs.items()}
            changed = selector.changed_forms(filed_payloads, corrected_payloads)
            dropped = tuple(
                selector.dropped_forms(filed_payloads, corrected_payloads))
            for cf in changed:
                spec = corrected_specs[cf.form]
                self._render_federal_spec(filler, spec, output_dir)
                mailed.append(MailedFile(
                    spec.output_name,
                    f"changed federal form ({cf.form})", cf.reason))
            if not changed:
                caveats.append(
                    "Changed-forms selection is empty; no federal "
                    "individual-form attachments mail.")
        else:
            caveats.append(_FEDERAL_COMPUTE_ONLY_NOTE)

        # --- California side (only when the amended scenario has a CA side) ---
        if amended_scenario.ca540 is not None:
            corrected_ca = self._compute_ca_results(
                amended_scenario, amended_scenario.ca540, corrected_federal)
            # Trail (spec §2.6): the three-bucket audit of Schedule CA
            # divergences on the corrected CA return.
            ca_divergences = CADivergenceTrail.build(
                amended_scenario.ca540, corrected_federal, year)
            ca_filed = amendment.load_filed_values(
                ca_filed_path, form_schedule_x.REQUIRED_CA_FILED_KEYS)
            schedule_x_values = form_schedule_x.assemble_ca(
                ca_filed, corrected_ca, case)
            self._emit_flat(
                filler,
                _PDFS_ROOT / "california" / "amendments" / f"schedule_x_{year}.pdf",
                output_dir / f"schedule_x_{year}.pdf",
                {**PdfScheduleX.get_mapping(year),
                 **PdfScheduleX.get_presentation_mapping(year)},
                {**schedule_x_values,
                 **form_schedule_x.presentation_keys(amended_scenario.config)},
                checkbox_states=PdfScheduleX.get_checkbox_states(year),
            )
            mailed.append(MailedFile(
                f"schedule_x_{year}.pdf",
                "California Schedule X (explanation of amended changes)",
                "amendment form"))

            if year in years.CALIFORNIA_YEARS:
                # The 540 emitted here IS the amended return: check its
                # "AMENDED return" box (an original 540 never carries the key).
                ca_pdfs = self._emit_ca_pdfs_internal(
                    amended_scenario,
                    {**corrected_ca, AMENDED_RETURN_KEY: AMENDED_RETURN_ON},
                    output_dir)
                amended_540 = output_dir / f"f540_amended_{year}.pdf"
                ca_pdfs["f540"].replace(amended_540)
                mailed.append(MailedFile(
                    f"f540_amended_{year}.pdf",
                    "Complete amended California Form 540",
                    "complete amended return"))
                mailed.append(MailedFile(
                    f"sch_ca_{year}.pdf",
                    "California Schedule CA (amended)",
                    "complete amended return"))
                if "sch_d_540" in ca_pdfs:
                    mailed.append(MailedFile(
                        f"sch_d_540_{year}.pdf",
                        "California Schedule D-540 (amended)",
                        "complete amended return"))
            else:
                caveats.append(_CA_COMPUTE_ONLY_NOTE)

        # Required attachments tenforty does not produce (e.g. Form 7203 for
        # an S corporation K-1 loss) are named so the preparer adds them.
        caveats.extend(form_sch_e_part_ii.hand_attachment_notes(eff_amended))
        manifest = PacketManifest(
            year=year, mailed_files=tuple(mailed),
            dropped=dropped, caveats=tuple(caveats),
            ca_divergences=ca_divergences,
            values={**f1040x_values, **schedule_x_values})
        (output_dir / "packet_manifest.txt").write_text(manifest.render())
        return manifest

    @staticmethod
    def _emit_flat(
        filler: PdfFiller, template: Path, output_path: Path,
        field_mapping: dict, values: dict,
        checkbox_states: dict | None = None,
    ) -> Path:
        """Fill a flat-mapping amendment form (1040-X / Schedule X)."""
        return filler.fill(
            template_path=template, output_path=output_path,
            field_mapping=field_mapping, values=values,
            checkbox_states=checkbox_states,
        )

    def run_full_california_scorp_return(
        self, scenario: Scenario, output_dir: Path,
    ) -> tuple[dict, dict[str, Path]]:
        """Compute + emit the CA S-corp packet (Form 100S + K-1 (100S)).

        Returns (ca_corporate_results, emitted_paths). Emits nothing when the
        scenario is not a CA S-corp (no s_corp_return / no .ca)."""
        ca_corporate_results = self.compute_california_corporate(scenario)
        emitted = self._emit_ca_scorp_pdfs_internal(
            scenario, ca_corporate_results, output_dir)
        # §4a: when the CA S-corp run is flagged amended, drop the loud Form
        # 100X note (the amended 100S/K-1 is the corrected return, NOT the
        # amendment vehicle). Only when a CA S-corp was actually emitted.
        if (
            scenario.s_corp_return is not None
            and scenario.s_corp_return.ca is not None
            and scenario.s_corp_return.amended_return
        ):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "scorp_amendment_note.txt").write_text(
                _CA_SCORP_100X_NOTE)
        return ca_corporate_results, emitted

    def run_full_federal_scorp_return(
        self, scenario: Scenario, output_dir: Path,
    ) -> tuple[dict, dict[str, Path]]:
        """Compute + emit the federal S-corp packet (Form 1120-S + Schedule K-1
        (1120-S)). Public entry for S-corp-only federal years (e.g. 2021) that
        have no 1040 spine — emits the corporate set WITHOUT the individual
        pipeline. Returns (corp_results, emitted_paths); ({}, {}) when not an
        S-corp scenario."""
        if scenario.s_corp_return is None:
            return {}, {}
        corp_results = self.compute_corporate(scenario)
        emitted = self._emit_federal_corporate_pdfs_internal(
            scenario, corp_results, output_dir)
        return corp_results, emitted

    def _verify_ca_yaml_freshness(
        self,
        scenario: Scenario,
        ca_yaml_path: Path,
        ca_yaml: dict,
    ) -> None:
        """v1 no-op stub; reserved for post-v1 federal_context freshness
        check (verify CA YAML matches live compute_federal outputs).
        """
        return None

    def _emit_ca_resolved_snapshot(
        self,
        federal_yaml_path: Path,
        output_dir: Path,
        effective_ca540: CA540Return,
        federal_results: dict,
        year: int,
    ) -> None:
        """Write a debug ``<basename>.ca-resolved.yaml`` capturing the merged
        in-memory CA view (federal context + ca540 with all divergences
        flattened). User-facing review artifact; never read back by
        tenforty."""
        basename = federal_yaml_path.stem
        snapshot_path = output_dir / f"{basename}.ca-resolved.yaml"
        # Merge the derived catalog-auto divergences into the SNAPSHOT view only
        # (compute derives them independently; this does not feed compute), so
        # the resolved snapshot records every materialized adjustment's origin —
        # USER rows plus CATALOG_AUTO rows — each with its catalog_id.
        auto_divergences = form_sch_ca.derive_auto_divergences(
            federal_results, year, ca540=effective_ca540
        )
        snapshot_ca540 = effective_ca540.with_extra_divergences(auto_divergences)
        payload = {
            "federal_context": {
                "year": federal_results.get("year"),
                "agi": federal_results.get("agi"),
                "filing_status": federal_results.get("filing_status"),
            },
            "ca540": _ca540_to_yaml_dict(snapshot_ca540),
        }
        snapshot_path.write_text(yaml.safe_dump(payload, sort_keys=False))

    def _build_effective_ca540(
        self,
        in_memory_ca540: CA540Return | None,
        ca_yaml: dict,
        year: int,
    ) -> CA540Return:
        """Build the effective CA540Return from the CA YAML.

        v1 source-of-truth is the file at ``ca_yaml_path`` (the CA YAML).
        If ``in_memory_ca540`` is also populated (from T4's combined-YAML
        loading mode), that's a misuse — caller should choose ONE loading
        mode. Hard-error to surface the confusion.

        Raises:
            ValueError: if ``ca_yaml`` lacks a populated ``ca540:`` block.
            ValueError: if ``in_memory_ca540`` is populated AND a populated
                ``ca_yaml.ca540`` block is supplied (mutually exclusive
                loading modes).
        """
        ca540_block = ca_yaml.get("ca540")
        if not ca540_block:
            raise ValueError(
                f"CA YAML has no `ca540:` block (or block is empty). If you "
                f"meant to pass a federal-only YAML, use "
                f"ReturnOrchestrator.run_full_return() instead of "
                f"run_full_california_return()."
            )
        if in_memory_ca540 is not None:
            raise ValueError(
                "Scenario.ca540 is populated AND a separate ca_yaml_path was "
                "supplied; choose one loading mode (combined-YAML via "
                "load_scenario(), or separate CA YAML via "
                "run_full_california_return)."
            )
        # Reuse the existing _load_ca540 from tenforty.scenario. Divergences are
        # id-keyed against the year's catalog, so thread the tax year through.
        from tenforty.scenario import _load_ca540
        return _load_ca540(ca540_block, year)

    def _should_emit_sch_1(self, scenario: Scenario, results: dict) -> bool:
        """Emit Sch 1 when either Part I total (line 10) or Part II total
        (line 26) is nonzero.

        Reads from the f1040 oracle (Sch. 1 AC56/AL93) when available for
        fidelity, and falls back to recomputing Sch 1 natively from a sch_e
        snapshot when results is empty (keeps unit tests that pass ``results={}``
        deterministic).
        """
        f1040 = results.get("f1040") or {}
        line_10 = f1040.get("sch_1_line_10")
        line_26 = f1040.get("sch_1_line_26")
        if line_10 is not None or line_26 is not None:
            return bool(line_10) or bool(line_26)
        sch_e_snapshot = form_sch_e.compute(scenario, upstream={})
        sch_1_snapshot = form_sch_1.compute(
            scenario, upstream={"sch_e": sch_e_snapshot},
        )
        return bool(
            sch_1_snapshot.get("sch_1_line_10_total_additional_income", 0)
            or sch_1_snapshot.get("sch_1_line_26_total_adjustments", 0)
        )

    def _should_emit_sch_a(self, scenario: Scenario, results: dict) -> bool:
        """Emit Sch A when itemizing beats the standard deduction.

        Runs sch_a.compute to get line 17 total and compares to the
        standard deduction for the filing status. ``results`` must carry
        ``{"f1040": {...}}`` with ``agi`` (and ideally ``magi``) set, so
        the sales-tax gate and phaseout scope-out fire correctly.
        """
        if scenario.itemized_deductions is None:
            return False
        f1040 = results.get("f1040") or {}
        if "agi" not in f1040:
            return False
        sch_a = form_sch_a.compute(scenario, upstream={"f1040": f1040})
        total = sch_a.get("sch_a_line_17_total", 0)
        from tenforty.params.federal import load as _load_federal_params
        _params = _load_federal_params(scenario.config.year)
        std = _params.standard_deduction[scenario.config.filing_status.value]
        return total > std

    def _should_emit_sch_b(self, scenario: Scenario, results: dict) -> bool:
        """Emit Sch B when either total interest or total dividends >= $1,500
        (tenforty's rendering of the IRS Part I / Part II filing threshold;
        on ``>=`` versus the IRS's "over $1,500" wording see unit (p) below).

        In these docstrings a single parenthesised letter names an
        internally-tracked follow-up work item, glossed at its first mention.
        (p) is the ``>=`` $1,500 versus IRS "over $1,500" threshold question.

        "Total" means the 1040 line 2b / 3b TOTAL across every source -- 1099
        plus the K-1 conduit components (IRC 1366(b)) -- not the 1099 slice
        alone. Summing only the 1099s (the historic behavior, which this
        docstring already claimed not to do) meant a return with $1,400 on a
        1099 and $1,400 on a K-1 had a true $2,800 Schedule B total, failed
        the gate, and was emitted with NO Schedule B at all.

        The totals are read BY REFERENCE from the finished 1040 results rather
        than re-derived here. ON THE NATIVE-SPINE PATH that means the gate
        cannot drift from THE LINES IT GATES: whatever convention lines 2b/3b
        use (including how the K-1 additions are rounded), the threshold is
        applied to the very figure the 1040 PUBLISHES on lines 2b/3b.
        Re-summing the scenario here would also have to duplicate
        sch_e_part_ii's per-entity-type classification of which K-1s
        contribute -- a copy that rots the moment that classification changes.

        "The lines it gates" is the whole of the claim, and it is deliberately
        NOT "the figure Schedule B prints". Those CAN be different numbers,
        because the two are rounded by different conventions: Schedule B
        rounds each payer and sums the rounded figures, while the 1099 leg of
        compute_income_preamble rounds once over the raw sum.

        This docstring deliberately states NO rule for when the two agree.
        That condition carries caveats, and it lives in exactly ONE place --
        ``K1ScheduleBEmitPathAgreesWith1040Tests`` in
        tests/test_k1_ordinary_income_totals.py. Read it there; do not
        reconstruct it here from the two rows below. (Every earlier attempt to
        state the rule in two places produced two texts that disagreed.)

        Two measured examples, native path, single filer, two 1099-INTs,
        no K-1:

            2 x 749.60   line 2b = 1499   Sch B line 4 = 1500   gate declines
            2 x 750.25   line 2b = 1501   Sch B line 4 = 1500   gate fires

        The gate follows line 2b, so in the first row it declines while the
        Schedule B that would have printed totals 1,500. Judged against the
        predicate this method actually implements -- ``>= 1500.0`` applied to
        line 2b -- that is the predicate answering correctly: line 2b is
        1,499, which is below 1,500. Note the basis matters here, because
        ``>=`` is inclusive: measured, a return whose line 2b is exactly 1,500
        (two 1099-INTs at 750.00) makes this gate FIRE. So "1,499.20 is not
        over $1,500" would be the wrong justification -- it reasons from the
        IRS's "over $1,500" wording, which is not the predicate below.
        Whether ``>=`` or "over" is correct is a PRE-EXISTING question this
        method's change neither created nor settles; it is chartered as
        follow-up unit (p), which owns it.

        The 1040-vs-Schedule-B rounding split is likewise real and
        pre-existing, chartered as follow-up unit (n) -- the 1099 leg's
        round-once-over-the-raw-sum convention. Whichever convention
        (n) settles on, this gate keeps tracking lines 2b/3b by reference and
        needs no edit -- which is the actual value of reading by reference.

        ⚠️ SCOPE -- the no-drift guarantee above is NATIVE-PATH ONLY. It does
        NOT hold on the XLSX workbook path, which _compute_1040_pipeline uses
        for every out-of-spine-scope scenario (non-single filers, and any
        EIC-possible filer). The workbook's Interest_Inc / Dividend_Inc named
        ranges are 1099-only: oracle.flattener emits k1_<letter>_interest_income
        and ..._ordinary_dividends, but F1040.INPUTS carries no such keys, and
        oracle.engine drops unmapped input keys silently. So for that filer
        class this gate reads a value NAMED like a total that is in fact the
        1099 slice, while the Schedule B emitted in the same packet DOES carry
        the K-1 payers (form_sch_b.compute receives the fanout regardless of
        which 1040 path ran). The $1,400-on-a-1099 + $1,400-on-a-K-1 case is
        therefore still unfixed for an MFJ or EIC-possible filer, and their
        K-1 interest/dividends are still outside AGI.

        That gap is PRE-EXISTING -- this method's change did not create it and
        cannot close it, because closing it means teaching the workbook path
        about K-1 conduit income. It is chartered as follow-up unit (r) --
        the XLSX workbook path's missing K-1 interest/dividend support. Every
        test covering this gate is a single-filer native-path scenario; there
        is deliberately no test asserting the workbook-path behavior, because
        asserting it would bless it.

        Fallback: callers that pass no 1040 results (unit-level callers with an
        empty dict) degrade to the 1099-only sums, i.e. the historic behavior.
        That is a strict LOWER bound on the true totals -- the K-1 components
        only ever add -- so the fallback can under-emit but never over-emit,
        and it is never silently zero.
        """
        interest_1099 = sum(i.interest for i in scenario.form1099_int)
        dividends_1099 = sum(d.ordinary_dividends for d in scenario.form1099_div)
        # HAZARD (documented, deliberately NOT guarded): dict.get's default
        # fires only on a MISSING key, not on a key present with value None.
        # A None here would reach `None >= 1500.0` and TypeError at PDF-emit
        # time rather than falling back to the 1099 sums. This cannot happen
        # today -- Interest_Inc and Dividend_Inc are formula cells in all five
        # year workbooks (2021-2025), so they evaluate numeric, never blank --
        # which is why there is no coercion here and no entry for these two
        # keys in f1040.py's _NUMERIC_SCH_1_KEYS. It would become live if
        # either named range were repointed at a raw input cell, or a new
        # year's workbook left one blank. Flagged for follow-up unit (r),
        # which owns the workbook path; a defensive `or` here would be dead
        # code guarding a state the codebase cannot currently reach.
        total_interest = results.get("taxable_interest", interest_1099)
        total_dividends = results.get("ordinary_dividends", dividends_1099)
        return total_interest >= 1500.0 or total_dividends >= 1500.0

    def _should_compute_8949(self, scenario: Scenario) -> bool:
        """Run f8949.compute whenever any 1099-B lot exists.

        Even pure Box A/D no-adjustment scenarios need the compute step,
        because ``sch_d.compute`` reads ``upstream["f8949"]["f8949_agg_*"]``
        for Sch D line 1a / 8a totals. The compute step is the single
        source of truth that partitions aggregate-path vs 8949-path lots.
        """
        return bool(scenario.form1099_b)

    def _should_emit_8949_pdf(self, scenario: Scenario,
                              upstream: dict) -> bool:
        """Emit f8949.pdf only when at least one lot is on the 8949 path.

        The aggregate path (Box A/D no-adjustment) flows to Sch D 1a/8a
        summaries with no PDF row. Because ``f8949.compute`` already
        partitioned the lots, detect 8949-path lots by the presence of
        any non-zero per-box proceeds total in the upstream result.
        """
        f8949_result = upstream.get("f8949", {})
        return any(
            f8949_result.get(f"f8949_box_{box.value}_total_proceeds", 0)
            for box in BoxLetter
        )

    def _form_1040_checkbox_values(
        self, scenario: Scenario, results: dict,
    ) -> dict[str, bool]:
        """The Form 1040's bool checkbox keys, derived from the scenario.

        Filing status: exactly one box. Line 7 "Schedule D not required":
        checked when line 7 carries an amount but no Schedule D is attached --
        read off the SAME gate (`_should_emit_sch_d`) that decides whether a
        Schedule D is emitted, so the box and the attachment cannot disagree.
        Digital assets: Yes/No from the config; neither box when unanswered
        (reachable only for 2021, see the refusal in
        `_federal_individual_emit_specs`).
        """
        status = scenario.config.filing_status
        keys = {
            FilingStatus.SINGLE: "single",
            FilingStatus.MARRIED_JOINTLY: "mfj",
            FilingStatus.MARRIED_SEPARATELY: "mfs",
            FilingStatus.HEAD_OF_HOUSEHOLD: "hoh",
            FilingStatus.QUALIFYING_WIDOW: "qss",
        }
        values: dict[str, bool] = {
            f"filing_status_{suffix}": status is fs
            for fs, suffix in keys.items()
        }
        values["sch_d_not_required"] = (
            bool(results.get("capital_gain_loss"))
            and not self._should_emit_sch_d(scenario)
        )
        answer = scenario.config.digital_assets
        if answer is not None:
            values["digital_assets_yes"] = answer
            values["digital_assets_no"] = not answer
        # Third party designee: only "No" is ever written (True is refused
        # upstream); unstated leaves the pair blank.
        if scenario.config.third_party_designee is False:
            values["third_party_designee_no"] = True
        return values

    def _should_emit_sch_d(self, scenario: Scenario) -> bool:
        """Emit Sch D whenever any 1099-B transactions exist in the scenario."""
        return bool(scenario.form1099_b)

    def _should_emit_sch_e(self, scenario: Scenario) -> bool:
        """Emit Sch E whenever any rental property (Part I) OR any K-1 (Part II)."""
        return bool(scenario.rental_properties) or bool(scenario.schedule_k1s)

    def _should_emit_sch_e_part_ii(self, scenario: Scenario) -> bool:
        """Emit Sch E Part II whenever the scenario has any K-1."""
        return bool(scenario.schedule_k1s)

    def _should_emit_4562(self, scenario: Scenario, results: dict) -> bool:
        """Emit Form 4562 whenever the scenario has any depreciable asset."""
        return bool(scenario.depreciable_assets)

    def _should_emit_8995(self, f8995_values: dict) -> bool:
        """Emit Form 8995 when the computed form claims a QBI deduction
        (line 15) OR reports a loss carryforward (line 16).

        Takes the SAME values dict the fill renders, so the gate and the
        printed form cannot disagree, and it is source-agnostic: a deduction
        from Schedule C alone attaches the form exactly as a K-1's does. The
        carryforward leg keeps a QBI-loss year filing the form (zero
        deduction, nonzero line 16). An empty dict -- no QBI source -- emits
        nothing.
        """
        return bool(
            f8995_values.get("f8995_line_15_qbi_deduction")
            or f8995_values.get("f8995_line_16_qbi_loss_carryforward")
        )

    def _should_emit_8582(
        self, scenario: Scenario, upstream: UpstreamState,
    ) -> bool:
        """Emit 8582 when any passive activity has a loss or carryforward,
        OR when any Sch E Part I rental runs a net loss. Reads the typed
        K1FanoutData sidecar — no re-classification of per-K-1 fields."""
        fanout = upstream["k1_fanout"]
        if any(
            a.loss or a.prior_carryforward for a in fanout.passive_activities
        ):
            return True
        return form_sch_e.has_any_net_loss(scenario)

    def _should_emit_8959(self, scenario: Scenario, results: dict) -> bool:
        """Emit 8959 only when the oracle says it's required (F8959_Reqd).

        Falls back to a wage-threshold heuristic if the oracle value isn't
        available in results (e.g. tests that pass ``results={}``). 2025
        thresholds: $200k single/HoH/QW, $250k MFJ, $125k MFS.
        """
        f1040 = results.get("f1040") or {}
        required = f1040.get("f8959_required")
        if required is not None:
            return bool(required)
        thresholds = {
            FilingStatus.MARRIED_JOINTLY: 250_000,
            FilingStatus.MARRIED_SEPARATELY: 125_000,
            FilingStatus.SINGLE: 200_000,
            FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
            FilingStatus.QUALIFYING_WIDOW: 200_000,
        }
        threshold = thresholds[scenario.config.filing_status]
        medicare_wages = sum(w.medicare_wages for w in scenario.w2s)
        return medicare_wages > threshold

    def _should_emit_sch_2(self, scenario: Scenario, results: dict) -> bool:
        """Emit Schedule 2 when the year is in the Schedule C family's year
        range, the return was computed on the NATIVE path, AND any modeled
        component is nonzero: the excess-APTC repayment (Part I),
        self-employment tax (line 4), or Additional Medicare Tax (line 11).

        This fires for returns with no Schedule C business too. A 2021-2025
        native-path return whose 1040 line 17 or line 23 is nonzero must
        attach Schedule 2; before this gate existed those packets printed the
        totals with no detail schedule.

        TWO DELIBERATE ABSTENTIONS, both keeping the legacy convention of
        totals on the 1040 with no detail schedule:

        - Years outside years.SCHEDULE_C_FAMILY_YEARS (the family's policy
          floor).
        - WORKBOOK-PATH returns (non-single or EIC-possible filers). The
          workbook's 1040 line 17 can include the alternative minimum tax and
          its line 24 can include the net investment income tax; forms/sch_2
          models neither. A Schedule 2 built from the modeled components
          would total LESS than the 1040 it is attached to -- an internally
          inconsistent packet, which is worse than no detail schedule. The
          discriminator is the workbook-harvested `tax_liability_line24` key,
          which the native spine never publishes (see forms/f4868.py).
          Lifting this needs the native spine to model those taxes, or the
          workbook's Schedule 2 lines to be harvested.
        """
        from tenforty import years as year_manifest
        if scenario.config.year not in year_manifest.SCHEDULE_C_FAMILY_YEARS:
            return False
        if "tax_liability_line24" in results:
            return False
        return any(
            results.get(key)
            for key in ("f8962_repayment", "sch_se_line_12_se_tax",
                        "f8959_tax_total")
        )

    def _should_emit_sch_se(self, sch_se_results: dict) -> bool:
        """Emit Schedule SE only when self-employment tax is actually due —
        the IRS attachment rule. Net earnings under $400 compute a zero line
        12 and attach no form; no business yields {}."""
        return bool(sch_se_results.get("sch_se_line_12_se_tax"))

    def _should_emit_8962(self, scenario: Scenario) -> bool:
        """Emit Form 8962 (PTC) iff the scenario carries a Form 1095-A block
        with at least one month reporting a nonzero premium, SLCSP, or APTC.

        Mirrors forms.f8962.compute's own per-month emit predicate (a month
        with all three zero produces no grid row) — so a 1095-A whose every
        month is empty yields no filled cells and no form. The spine only
        computes f8962 at all when form_1095a is present, so the detail keys
        the spec reads are guaranteed available whenever this returns True."""
        block = scenario.form_1095a
        if block is None:
            return False
        return any(
            m.premium or m.slcsp or m.aptc for m in block.months
        )
