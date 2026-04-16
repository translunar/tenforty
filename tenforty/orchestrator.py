from pathlib import Path

from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.forms import f1040 as form_1040
from tenforty.forms import f4868 as form_4868
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
from tenforty.models import FilingStatus, Scenario

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


class ReturnOrchestrator:
    """Coordinates computation across forms in dependency order."""

    def __init__(self, spreadsheets_dir: Path, work_dir: Path) -> None:
        self.spreadsheets_dir = spreadsheets_dir
        self.work_dir = work_dir
        self.engine = SpreadsheetEngine()

    def compute_federal(self, scenario: Scenario) -> dict[str, object]:
        """Compute the federal return (1040 + all schedules)."""
        year = scenario.config.year
        spreadsheet = self.spreadsheets_dir / "federal" / str(year) / "1040.xlsx"

        if not spreadsheet.exists():
            raise FileNotFoundError(
                f"Federal spreadsheet not found: {spreadsheet}"
            )

        flat_inputs = flatten_scenario(scenario)

        raw = self.engine.compute(
            spreadsheet_path=spreadsheet,
            mapping=F1040,
            year=year,
            inputs=flat_inputs,
            work_dir=self.work_dir / "federal",
        )
        return form_1040.compute(raw_1040=raw, upstream={})

    def emit_pdfs(
        self,
        scenario: Scenario,
        results: dict[str, object],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Fill both 1040 and 4868 PDFs and write them to output_dir.

        Returns a dict mapping form name ('1040', '4868') to the filled PDF path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        year = scenario.config.year
        filler = PdfFiller()

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
        f4868_values = form_4868.compute(scenario, upstream={"f1040": results})
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
            sch_b_values = form_sch_b.compute(
                scenario, upstream={"f1040": results},
            )
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
            sch_d_values = form_sch_d.compute(
                scenario, upstream={"f1040": results},
            )
            filler.fill_with_repeaters(
                template_path=sch_d_template,
                output_path=out_sch_d,
                mapping=PdfSchD.get_mapping(year),
                values=sch_d_values,
            )
            emitted["sch_d"] = out_sch_d

        sch_e_values: dict = {}
        if self._should_emit_sch_e(scenario):
            sch_e_template = _PDFS_ROOT / "federal" / str(year) / "f1040se.pdf"
            out_sch_e = output_dir / f"f1040se_{year}.pdf"
            part_i = form_sch_e.compute(scenario, upstream={"f1040": results})
            part_ii: dict = {}
            if self._should_emit_sch_e_part_ii(scenario):
                part_ii = form_sch_e_part_ii.compute(scenario, upstream={})
            # Merge: Part I scalars win for shared keys (e.g. taxpayer_name);
            # strip _-prefixed sidecar keys (e.g. _k1_fanout) from Part II.
            merged = {
                **part_i,
                **{k: v for k, v in part_ii.items() if not k.startswith("_")},
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
            sch_a_values = form_sch_a.compute(
                scenario, upstream={"f1040": results},
            )
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
                scenario, upstream={"sch_e": sch_e_values, "f1040": results},
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
            f4562_values = form_4562.compute(scenario, upstream={})
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
            f8959_values = form_8959.compute(
                scenario, upstream={"f1040": results},
            )
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
            part_ii = form_sch_e_part_ii.compute(scenario, upstream={})
            f8995_values = form_f8995.compute(scenario, upstream={
                "f1040": results,
                "_k1_fanout": part_ii["_k1_fanout"],
            })
            filler.fill(
                template_path=f8995_template,
                output_path=out_8995,
                field_mapping=PdfF8995.get_mapping(year)["scalars"],
                values=f8995_values,
            )
            emitted["f8995"] = out_8995

        if self._should_emit_8582(scenario):
            f8582_template = _PDFS_ROOT / "federal" / str(year) / "f8582.pdf"
            out_8582 = output_dir / f"f8582_{year}.pdf"
            # Reuse sch_e_values if already computed above; otherwise compute now.
            if not sch_e_values:
                sch_e_values = form_sch_e.compute(scenario, upstream={"f1040": results})
            part_ii_8582 = form_sch_e_part_ii.compute(scenario, upstream={})
            f8582_values = form_f8582.compute(scenario, upstream={
                "f1040": results,
                "sch_e": sch_e_values,
                "_k1_fanout": part_ii_8582["_k1_fanout"],
            })
            filler.fill(
                template_path=f8582_template,
                output_path=out_8582,
                field_mapping=PdfF8582.get_mapping(year)["scalars"],
                values=f8582_values,
            )
            emitted["f8582"] = out_8582

        return emitted

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
        from tenforty.constants import y2025
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

    def _should_emit_8582(self, scenario: Scenario) -> bool:
        """Emit 8582 whenever any passive loss is present or carried forward."""
        has_passive_k1_loss = any(
            k1.net_rental_real_estate < 0 or k1.other_net_rental < 0 or
            k1.ordinary_business_income < 0 or k1.prior_year_passive_loss_carryforward
            for k1 in scenario.schedule_k1s if not k1.material_participation
        )
        return has_passive_k1_loss or form_sch_e.has_any_net_loss(scenario)

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
