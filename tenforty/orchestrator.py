import dataclasses
from pathlib import Path

from tenforty.attestations import enforce_compute_time
from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.forms import f1040 as form_1040
from tenforty.forms import f4868 as form_4868
from tenforty.forms import f8949 as form_f8949
from tenforty.forms import sch_1 as form_sch_1
from tenforty.forms import sch_a as form_sch_a
from tenforty.forms import sch_b as form_sch_b
from tenforty.forms import sch_d as form_sch_d
from tenforty.forms import sch_e as form_sch_e
from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.forms import f4562 as form_4562
from tenforty.forms import f8959 as form_8959
from tenforty.forms import f8995 as form_f8995
from tenforty.forms import f8582 as form_f8582
from tenforty.forms import f1120s as form_f1120s
from tenforty.filing.pdf import PdfFiller
from tenforty.constants import y2025
from tenforty.oracle.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_4868 import Pdf4868
from tenforty.mappings.pdf_sch_b import PdfSchB
from tenforty.mappings.pdf_sch_d import PdfSchD
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_a import PdfSchA
from tenforty.mappings.pdf_sch_e import PdfSchE
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.mappings.pdf_8959 import Pdf8959
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.mappings.pdf_f8949 import BoxLetter, PdfF8949
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.models import (
    EntityType,
    FilingStatus,
    K1Allocation,
    K1AllocationEntity,
    K1AllocationShareholder,
    K1FanoutData,
    Scenario,
    ScheduleK1,
)
from tenforty.types import UpstreamState

_PDFS_ROOT = Path(__file__).parent.parent / "pdfs"


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
    """
    return ScheduleK1(
        entity_name=alloc.entity.name,
        entity_ein=alloc.entity.ein,
        entity_type=EntityType.S_CORP,
        material_participation=True,  # v1 default; caller-configurable later
        ordinary_business_income=alloc.box_1_ordinary_business_income,
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

    def _compute_1040_pipeline(
        self, effective_scenario: Scenario,
    ) -> dict[str, object]:
        """Run the 1040 pipeline (spreadsheet evaluation + f1040.compute).

        Accepts the already-resolved effective scenario (with any synthesized
        K-1s already appended). Returns the 1040 results dict only — corp keys
        are merged by the caller. This is the single source of truth for the
        spreadsheet evaluation step, the 1099-G withholding supplement, and
        the form_1040.compute step.
        """
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

        return form_1040.compute(raw_1040=raw, upstream={})

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
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        filler = PdfFiller()

        # Hoist sch_e_part_ii.compute to run at most once per call to this method.
        # All downstream consumers (sch_b, sch_d, sch_e, f8995, f8582) share
        # a single fanout result rather than each recomputing from scratch —
        # keeping the K-1 fanout computation deterministic and avoiding
        # redundant spreadsheet evaluation.
        if self._should_emit_sch_e_part_ii(scenario):
            part_ii_fields, k1_fanout = form_sch_e_part_ii.compute(scenario, upstream={})
        else:
            part_ii_fields = {}
            k1_fanout = K1FanoutData.empty()

        upstream: UpstreamState = {"f1040": results, "k1_fanout": k1_fanout}

        if self._should_compute_8949(scenario):
            upstream["f8949"] = form_f8949.compute(scenario, upstream)

        f1040_template = _PDFS_ROOT / "federal" / str(year) / "f1040.pdf"
        # results is already PDF-ready (forms.f1040.compute produced it,
        # including the 25d sum). No translator, no patch needed.
        out_1040 = output_dir / f"f1040_{year}.pdf"
        filler.fill(
            template_path=f1040_template,
            output_path=out_1040,
            field_mapping=Pdf1040.get_mapping(year),
            values=results,
        )

        f4868_template = _PDFS_ROOT / "federal" / str(year) / "f4868.pdf"
        out_4868 = output_dir / f"f4868_{year}.pdf"
        f4868_values = form_4868.compute(scenario, upstream=upstream)
        filler.fill(
            template_path=f4868_template,
            output_path=out_4868,
            field_mapping=Pdf4868.get_mapping(year),
            values=f4868_values,
        )

        emitted: dict[str, Path] = {"1040": out_1040, "4868": out_4868}

        if self._should_emit_sch_b(scenario, results):
            sch_b_template = _PDFS_ROOT / "federal" / str(year) / "f1040sb.pdf"
            out_sch_b = output_dir / f"f1040sb_{year}.pdf"
            sch_b_values = form_sch_b.compute(scenario, upstream=upstream)
            flat_values = _flatten_sch_b_rows(sch_b_values)
            filler.fill(
                template_path=sch_b_template,
                output_path=out_sch_b,
                field_mapping=PdfSchB.get_mapping(year),
                values=flat_values,
            )
            emitted["sch_b"] = out_sch_b

        if self._should_emit_sch_d(scenario):
            sch_d_template = _PDFS_ROOT / "federal" / str(year) / "f1040sd.pdf"
            out_sch_d = output_dir / f"f1040sd_{year}.pdf"
            sch_d_values = form_sch_d.compute(scenario, upstream=upstream)
            filler.fill_with_repeaters(
                template_path=sch_d_template,
                output_path=out_sch_d,
                mapping=PdfSchD.get_mapping(year),
                values=sch_d_values,
            )
            emitted["sch_d"] = out_sch_d

        if self._should_emit_8949_pdf(scenario, upstream):
            f8949_template = _PDFS_ROOT / "federal" / str(year) / "f8949.pdf"
            out_8949 = output_dir / f"f8949_{year}.pdf"
            # PdfF8949 keeps per-box repeater groups (box_a_rows, box_b_rows, …)
            # rather than the single-repeater {template, rows} shape that
            # fill_with_repeaters expects, because boxes A/B share page-1 PDF
            # fields and D/E share page-2 fields — a single repeater can't
            # disambiguate them. Each row dict already bakes its row index
            # and PDF field path into its keys, so a flat merge onto one
            # field_mapping resolves all per-box keys correctly for filler.fill.
            f8949_full_mapping = PdfF8949.get_mapping(year)
            f8949_flat: dict[str, str] = dict(f8949_full_mapping["scalars"])
            for row_dicts in f8949_full_mapping["repeaters"].values():
                for row_dict in row_dicts:
                    f8949_flat.update(row_dict)
            filler.fill(
                template_path=f8949_template,
                output_path=out_8949,
                field_mapping=f8949_flat,
                values=upstream["f8949"],
            )
            emitted["f8949"] = out_8949

        sch_e_values: dict = {}
        if self._should_emit_sch_e(scenario):
            sch_e_template = _PDFS_ROOT / "federal" / str(year) / "f1040se.pdf"
            out_sch_e = output_dir / f"f1040se_{year}.pdf"
            part_i = form_sch_e.compute(scenario, upstream=upstream)
            # Merge: Part I scalars win for shared keys (e.g. taxpayer_name).
            merged = {
                **part_i,
                **part_ii_fields,
            }
            # Derive page-2 header fields for the mapping layer without
            # polluting compute outputs with PDF-template structure.
            merged["taxpayer_name_page2"] = merged.get("taxpayer_name")
            merged["taxpayer_ssn_page2"] = merged.get("taxpayer_ssn")
            sch_e_values = merged
            filler.fill_with_repeaters(
                template_path=sch_e_template,
                output_path=out_sch_e,
                mapping=PdfSchE.get_mapping(year),
                values=sch_e_values,
            )
            emitted["sch_e"] = out_sch_e

        if self._should_emit_sch_a(scenario, {"f1040": results}):
            sch_a_template = _PDFS_ROOT / "federal" / str(year) / "f1040sa.pdf"
            out_sch_a = output_dir / f"f1040sa_{year}.pdf"
            sch_a_values = form_sch_a.compute(scenario, upstream=upstream)
            filler.fill_with_repeaters(
                template_path=sch_a_template,
                output_path=out_sch_a,
                mapping=PdfSchA.get_mapping(year),
                values=sch_a_values,
            )
            emitted["sch_a"] = out_sch_a

        if self._should_emit_sch_1(scenario, {"f1040": results}):
            sch_1_template = _PDFS_ROOT / "federal" / str(year) / "f1040s1.pdf"
            out_sch_1 = output_dir / f"f1040s1_{year}.pdf"
            sch_1_values = form_sch_1.compute(
                scenario, upstream={**upstream, "sch_e": sch_e_values},
            )
            filler.fill_with_repeaters(
                template_path=sch_1_template,
                output_path=out_sch_1,
                mapping=PdfSch1.get_mapping(year),
                values=sch_1_values,
            )
            emitted["sch_1"] = out_sch_1

        if self._should_emit_4562(scenario, {"f1040": results}):
            f4562_template = _PDFS_ROOT / "federal" / str(year) / "f4562.pdf"
            out_4562 = output_dir / f"f4562_{year}.pdf"
            f4562_values = form_4562.compute(scenario, upstream=upstream)
            filler.fill_with_repeaters(
                template_path=f4562_template,
                output_path=out_4562,
                mapping=Pdf4562.get_mapping(year),
                values=f4562_values,
            )
            emitted["f4562"] = out_4562

        if self._should_emit_8959(scenario, {"f1040": results}):
            f8959_template = _PDFS_ROOT / "federal" / str(year) / "f8959.pdf"
            out_8959 = output_dir / f"f8959_{year}.pdf"
            f8959_values = form_8959.compute(scenario, upstream=upstream)
            filler.fill(
                template_path=f8959_template,
                output_path=out_8959,
                field_mapping=Pdf8959.get_mapping(year)["scalars"],
                values=f8959_values,
            )
            emitted["8959"] = out_8959

        if self._should_emit_8995(scenario):
            f8995_template = _PDFS_ROOT / "federal" / str(year) / "f8995.pdf"
            out_8995 = output_dir / f"f8995_{year}.pdf"
            f8995_values = form_f8995.compute(scenario, upstream=upstream)
            filler.fill(
                template_path=f8995_template,
                output_path=out_8995,
                field_mapping=PdfF8995.get_mapping(year)["scalars"],
                values=f8995_values,
            )
            emitted["f8995"] = out_8995

        if self._should_emit_8582(scenario, upstream):
            f8582_template = _PDFS_ROOT / "federal" / str(year) / "f8582.pdf"
            out_8582 = output_dir / f"f8582_{year}.pdf"
            # Reuse sch_e_values if already computed above; otherwise compute
            # Part I now so 8582 has rental loss context even when Sch E
            # wasn't emitted (e.g. only passive K-1 activity, no rental property).
            if not sch_e_values:
                sch_e_values = form_sch_e.compute(scenario, upstream=upstream)
            f8582_values = form_f8582.compute(scenario, upstream={
                **upstream,
                "sch_e": sch_e_values,
            })
            filler.fill(
                template_path=f8582_template,
                output_path=out_8582,
                field_mapping=PdfF8582.get_mapping(year)["scalars"],
                values=f8582_values,
            )
            emitted["f8582"] = out_8582

        # 1120-S emit (only when scenario.s_corp_return is populated).
        if scenario.s_corp_return is not None:
            # Main 1120-S + Sch B + Sch K.
            main_template = _PDFS_ROOT / "federal" / str(year) / "f1120s.pdf"
            main_output = output_dir / f"f1120s_{year}.pdf"
            # Pass the full results dict — aggregation and derivation lambdas
            # reference keys that are NOT in _MAPPING_<year>, so filtering to
            # mapping keys alone would silently drop those inputs.
            filler.fill(
                template_path=main_template,
                output_path=main_output,
                values=results,
                field_mapping=PdfF1120S.get_mapping(year),
                aggregations=PdfF1120S.get_aggregations(year),
                derivations=PdfF1120S.get_derivations(year),
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
            for i, alloc in enumerate(
                results.get("f1120s_sch_k1_allocations", []),
                start=1,
            ):
                flat_values = {
                    **_flatten_k1_party("entity", alloc.entity),
                    **_flatten_k1_party("shareholder", alloc.shareholder),
                    "ownership_percentage": alloc.ownership_percentage,
                    "box_1_ordinary_business_income":
                        alloc.box_1_ordinary_business_income,
                }
                k1_output = output_dir / f"f1120s_k1_{i}_{year}.pdf"
                filler.fill(
                    template_path=k1_template,
                    output_path=k1_output,
                    values=flat_values,
                    field_mapping=PdfF1120SK1.get_mapping(year),
                )
                emitted[f"1120s_k1_{i}"] = k1_output

        return emitted

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
        effective_scenario, corp_results = self._build_effective_scenario(scenario)
        results_1040 = self._compute_1040_pipeline(effective_scenario)
        results = {**corp_results, **results_1040}
        emitted = self._emit_pdfs_internal(effective_scenario, results, output_dir)
        return results, emitted

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
        std = y2025.STANDARD_DEDUCTION[scenario.config.filing_status]
        return total > std

    def _should_emit_sch_b(self, scenario: Scenario, results: dict) -> bool:
        """Emit Sch B when either total interest or total dividends >= $1,500
        (the IRS Part I / Part II filing threshold)."""
        total_interest = sum(i.interest for i in scenario.form1099_int)
        total_dividends = sum(d.ordinary_dividends for d in scenario.form1099_div)
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

    def _should_emit_8995(self, scenario: Scenario) -> bool:
        """Emit Form 8995 whenever any K-1 carries QBI."""
        return any(k1.qbi_amount for k1 in scenario.schedule_k1s)

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
