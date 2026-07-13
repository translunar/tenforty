import dataclasses
from pathlib import Path

import yaml

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
from tenforty.forms import sch_ca as form_sch_ca
from tenforty.forms.sch_ca_fods import FodsDivergences, import_fods_divergences
from tenforty.forms import sch_d_540 as form_sch_d_540
from tenforty.forms import f540 as form_f540
from tenforty.filing.pdf import PdfFiller
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
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.mappings.pdf_sch_d_540 import PdfSchD540
from tenforty.models import (
    CA540Return,
    CASchD540Adjustment,
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
# derivations/checkbox_states on the mapping class.
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


def _ca540_to_yaml_dict(ca540: CA540Return) -> dict:
    """Serialize a CA540Return to a plain dict suitable for YAML emission.

    Called only by ``_emit_ca_resolved_snapshot``; not intended for use
    outside the resolved-snapshot writer path.
    """
    return {
        "estimated_payments": ca540.estimated_payments,
        "use_tax": ca540.use_tax,
        "estimated_tax_penalty": ca540.estimated_tax_penalty,
        "ptet_credit": ca540.ptet_credit,
        "rrb_tier_1_2_amount": ca540.rrb_tier_1_2_amount,
        "pfl_amount": ca540.pfl_amount,
        "voluntary_contributions": [
            {"name": v.name, "amount": v.amount}
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
        # Every component here is clamped at 0, so this estimate only ever RISES
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
        )
        num_children = min(len(cfg.dependents), max(ceilings))
        ceiling = ceilings.get(num_children, max(ceilings.values()))
        # Below the ceiling → possibly EIC-eligible → out of spine scope.
        return agi_estimate >= ceiling

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
        if not self._scenario_in_spine_scope(effective_scenario):
            return self._compute_1040_via_workbook(effective_scenario)
        params = load_params(effective_scenario.config.year)
        schedule_results = self._compute_native_schedules(effective_scenario)
        spine_result = f1040_spine.compute_spine(
            effective_scenario, params, schedule_results,
        )
        # Forward f8949 box-total keys into the final result dict so oracle
        # cross-check consumers (e.g. test_f8949_oracle.py) can read them
        # from compute_federal — mirroring the workbook path which exposed
        # these as named-range OUTPUTS.
        f8949_result = schedule_results.get("f8949", {})
        return {**f8949_result, **spine_result}

    def _compute_native_schedules(
        self, effective_scenario: Scenario,
    ) -> dict[str, dict]:
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
        6. AGI pre-compute stub — provides agi/magi/taxable_income_before_qbi
           from parts already computed (uses std deduction as stand-in for sch_a).
        7. F8995 — needs k1_fanout + f1040 stub (taxable_income_before_qbi).
        8. F8582 — needs k1_fanout + sch_e + f1040 stub (magi).
        9. Sch A — needs agi from the f1040 stub.
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
        # sch_e_line_41_total_pte (Part II) from the same "sch_e" slot.
        sch_e_part_i = form_sch_e.compute(effective_scenario, upstream={})
        sch_e_combined = {**sch_e_part_i, **part_ii_fields}

        # --- Step 4: Sch 1 (needs sch_e) ---
        sch_1_results = form_sch_1.compute(
            effective_scenario, upstream={"sch_e": sch_e_combined},
        )

        # --- Step 5: Sch D (needs k1_fanout + f8949) ---
        sch_d_results = form_sch_d.compute(effective_scenario, upstream=upstream)

        # --- Step 6: F8959 (standalone W-2 wages only) ---
        f8959_results = form_8959.compute(effective_scenario, upstream={})

        # --- Step 7: AGI pre-compute stub ---
        # F8995 and F8582 need upstream["f1040"]["magi"] /
        # "taxable_income_before_qbi_deduction". Build a lightweight stub from
        # the SHARED income preamble so the AGI/total-income math has a single
        # source of truth with compute_spine (they cannot drift). Sch A is not
        # yet computed, so the preamble's pre-QBI taxable income uses the
        # standard deduction as a conservative stand-in for the QBI-threshold
        # check in f8995 (over-estimates taxable income slightly if itemized
        # beats std, which is safe: the threshold guard is generous).
        _params = _load_params(effective_scenario.config.year)
        _preamble = f1040_spine.compute_income_preamble(
            effective_scenario,
            _params,
            {"sch_1": sch_1_results, "sch_d": sch_d_results},
        )
        f1040_stub: dict = {
            "agi": _preamble.agi,
            "magi": _preamble.magi,
            "taxable_income_before_qbi_deduction":
                _preamble.taxable_income_before_qbi_std,
            "net_capital_gain": _preamble.net_capital_gain,
        }

        # --- Step 8: F8995 (needs k1_fanout + f1040 stub) ---
        f8995_results = form_f8995.compute(
            effective_scenario,
            upstream={"k1_fanout": k1_fanout, "f1040": f1040_stub},
        )

        # --- Step 9: F8582 (needs k1_fanout + sch_e + f1040 stub) ---
        f8582_results = form_f8582.compute(
            effective_scenario,
            upstream={
                **upstream,
                "sch_e": sch_e_combined,
                "f1040": f1040_stub,
            },
        )

        # --- Step 10: Sch A (needs agi from f1040 stub) ---
        # Build an effective scenario with itemized_deductions populated from
        # form1098s when itemized_deductions is not set directly. This bridges
        # the YAML fixture model (which uses form1098s for mortgage/property-tax)
        # to forms.sch_a.compute, which reads from scenario.itemized_deductions.
        sch_a_scenario = _scenario_with_effective_itemized(effective_scenario)
        sch_a_results = (
            form_sch_a.compute(
                sch_a_scenario,
                upstream={"f1040": f1040_stub},
            )
            if sch_a_scenario.itemized_deductions is not None
            else {}
        )

        return {
            "sch_1": sch_1_results,
            "sch_a": sch_a_results,
            "sch_d": sch_d_results,
            "sch_e": sch_e_combined,
            "f8959": f8959_results,
            "f8995": f8995_results,
            "f8582": f8582_results,
            # f8949 included so _compute_1040_pipeline can forward box totals
            # into the final result for oracle cross-check consumers.
            "f8949": upstream.get("f8949", {}),
        }

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
                checkbox_states=PdfF1120S.get_checkbox_states(year),
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

    def _emit_ca_pdfs_internal(
        self,
        scenario: Scenario,
        ca_results: dict,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Render the three CA-state PDFs (f540, sch_ca, sch_d_540) from
        a CA compute results dict.

        Mechanical helper: consumes ``ca_results`` as-is and writes PDFs.
        Does NOT mutate, merge, or augment ``ca_results`` — callers
        (``run_full_california_return``) are responsible for ensuring
        required PDF compute keys (e.g. ``f540_taxpayer_name``,
        ``sch_ca_taxpayer_ssn``, ``sch_d_540_taxpayer_name``, etc.) are
        present in the dict before invocation.

        Returns a dict with exactly the keys ``{"f540", "sch_ca",
        "sch_d_540"}`` mapping to the filled PDF paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        filler = PdfFiller()

        emitted: dict[str, Path] = {}
        for basename, mapping_cls in _CA_FORMS_BY_BASENAME:
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

    def discover_fods_divergences(
        self, federal_yaml_path: Path, fods_override: Path | None = None,
    ) -> FodsDivergences:
        """Locate and parse the `<basename>.ca.fods` worksheet, if any.

        Discovery rules:
        - If ``fods_override`` is given, parse it (no auto-discovery).
        - Otherwise look for ``<basename>.ca.fods`` next to the federal YAML.
        - Return empty FodsDivergences if no .fods is found and no override given.
        """
        if fods_override is not None:
            return import_fods_divergences(fods_override)
        candidate = federal_yaml_path.with_suffix(".ca.fods")
        if candidate.exists():
            return import_fods_divergences(candidate)
        return FodsDivergences()

    def run_full_california_return(
        self,
        scenario: Scenario,
        ca_yaml_path: Path,
        output_dir: Path,
        federal_yaml_path: Path | None = None,
        fods_path: Path | None = None,
        disable_fods: bool = False,
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
        # 1. Load CA YAML (envelope: top-level ca540: required, federal_context: optional).
        with open(ca_yaml_path) as f:
            ca_yaml = yaml.safe_load(f) or {}

        # 2. Freshness check — v1 no-op stub.
        self._verify_ca_yaml_freshness(scenario, ca_yaml_path, ca_yaml)

        # 3. Build effective CA540Return — ca_yaml is authoritative, but conflict-detect.
        effective_ca540 = self._build_effective_ca540(scenario.ca540, ca_yaml)

        # 3b. Discover and merge .fods worksheet divergences, if any.
        fods_div = (
            FodsDivergences()
            if disable_fods or federal_yaml_path is None
            else self.discover_fods_divergences(
                federal_yaml_path=federal_yaml_path,
                fods_override=fods_path,
            )
        )
        if fods_div.sch_ca:
            effective_ca540 = effective_ca540.with_extra_divergences(fods_div.sch_ca)
        # 4. Re-derive federal results. compute_federal exposes sch_1_line_*
        #    keys directly (per #80), so downstream CA computes consume the
        #    federal results dict without an interim bridge.
        federal_results = self.compute_federal(scenario)

        # 5. CA computes — Sch CA → Sch D 540 → Form 540 main.
        sch_ca_results = form_sch_ca.compute(
            effective_ca540, federal_results,
        )
        sch_d_540_results = form_sch_d_540.compute(
            federal_results,
            worksheet_adjustments=fods_div.sch_d_540,
        )
        # Schedule CA Part II — CA itemized deductions. Computed only when the
        # federal return itemized (schedule_a_total > 0); a federally-standard
        # return gets no Part II and f540.compute keeps the CA standard
        # deduction (it selects max(std, ca_itemized)). v1 scope: CA itemizes
        # iff the federal return itemized.
        # CA Part II is computed only when the federal return actually APPLIED
        # itemized deductions (not merely produced a nonzero raw Schedule A
        # total) — see sch_ca.federal_itemization_applied.
        ca_part_ii = {}
        if form_sch_ca.federal_itemization_applied(federal_results):
            # compute_federal surfaces only schedule_a_total + line 5e, so
            # recompute the full federal Schedule A line breakdown (medical,
            # property, mortgage, charity) for Part II to read. Uses the same
            # effective-itemized scenario the federal Sch A used, so the
            # breakdown is consistent with schedule_a_total. NOTE: this inherits
            # forms.sch_a.compute's scope gates — for a CA resident only the
            # 2025 SALT-phaseout gate can fire (MAGI above threshold), the same
            # limitation the federal Sch A emit path already carries.
            sch_a_full = form_sch_a.compute(
                _scenario_with_effective_itemized(scenario),
                {"f1040": federal_results},
            )
            ca_part_ii = form_sch_ca.compute_part_ii_itemized(sch_a_full)
        f540_results = form_f540.compute(
            year=scenario.config.year,
            filing_status=scenario.config.filing_status,
            federal_agi=federal_results["agi"],
            ca_agi=sch_ca_results["sch_ca_ca_agi"],
            ca540=effective_ca540,
            num_dependents=len(scenario.config.dependents),
            ca_itemized=ca_part_ii.get("ca_itemized_total"),
            # v1 default (tracked follow-up):
            # - renter_credit_eligible: False (no CA540Return field yet)
        )
        # Note: f540.compute raises NotImplementedError when federal_agi
        # exceeds the year's CA AGI phaseout threshold; we let it propagate
        # without wrapping. Load-time scope-out attestations are the gate;
        # if a scenario reaches this method, it has already passed
        # _validate_scenario_config.

        # 7. Header merge — happens here; _emit_ca_pdfs_internal stays
        #    PDF-only and trusts the dict as-is.
        header_keys = {
            "f540_taxpayer_name": scenario.config.full_name,
            "f540_taxpayer_ssn": scenario.config.ssn,
            "sch_ca_taxpayer_name": scenario.config.full_name,
            "sch_ca_taxpayer_ssn": scenario.config.ssn,
            "sch_d_540_taxpayer_name": scenario.config.full_name,
            "sch_d_540_taxpayer_ssn": scenario.config.ssn,
        }
        ca_results = {
            **sch_ca_results,
            **ca_part_ii,
            **sch_d_540_results,
            **f540_results,
            **header_keys,
        }

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
                sch_d_540_adjustments=fods_div.sch_d_540,
            )

        return ca_results, ca_pdfs

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
        sch_d_540_adjustments: list[CASchD540Adjustment],
    ) -> None:
        """Write a debug ``<basename>.ca-resolved.yaml`` capturing the merged
        in-memory CA view (federal context + ca540 with all divergences
        flattened + Sch D 540 worksheet entries). User-facing review artifact;
        never read back by tenforty."""
        basename = federal_yaml_path.stem
        snapshot_path = output_dir / f"{basename}.ca-resolved.yaml"
        payload = {
            "federal_context": {
                "year": federal_results.get("year"),
                "agi": federal_results.get("agi"),
                "filing_status": federal_results.get("filing_status"),
            },
            "ca540": _ca540_to_yaml_dict(effective_ca540),
            "sch_d_540_divergences": [
                {
                    "source": d.source.name,
                    "direction": d.direction.name,
                    "amount": d.amount,
                    "description": d.description,
                    "pub1001_ref": d.pub1001_ref,
                }
                for d in sch_d_540_adjustments
            ],
        }
        snapshot_path.write_text(yaml.safe_dump(payload, sort_keys=False))

    def _build_effective_ca540(
        self,
        in_memory_ca540: CA540Return | None,
        ca_yaml: dict,
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
        # Reuse the existing _load_ca540 from tenforty.scenario.
        from tenforty.scenario import _load_ca540
        return _load_ca540(ca540_block)

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
