# tests/test_year_completeness_gate.py
"""Layer-5 completeness gate: for every year the manifest declares, every
pack piece exists — and for years it does NOT declare, everything raises.
This is the test that turns 'we support 2024' from an assertion into a
checked property. KNOWN_GAPS entries are work owed, not permission."""
import importlib
import unittest

from tenforty import years as year_manifest
from tenforty.attestations import _CA_ATTESTATIONS
from tenforty.mappings.catalog import AMENDMENT_KNOWN_GAPS, CATALOG, KNOWN_GAPS
from tenforty.params import california as ca_params
from tenforty.params import ca_scorp
from tenforty.params.federal import load as load_federal
from tenforty.tax_table import load_table
from tests.fixtures.spine_battery import battery_for
from tests.helpers import REPO_ROOT

_PDFS = REPO_ROOT / "pdfs"
_PROBE_UNSUPPORTED_YEAR = 1999


class FederalCompletenessTests(unittest.TestCase):
    def test_every_federal_year_has_a_complete_pack(self):
        for year in year_manifest.FEDERAL_YEARS:
            with self.subTest(year=year, piece="params"):
                self.assertEqual(load_federal(year).year, year)
            with self.subTest(year=year, piece="attestation"):
                importlib.import_module(
                    f"tests.params_attestations.federal_y{year}")
            with self.subTest(year=year, piece="tax_table"):
                self.assertGreater(len(load_table("federal", year)), 1_000)
            with self.subTest(year=year, piece="battery"):
                self.assertGreater(len(battery_for(year)), 0)
            for (juris, form), entry in sorted(CATALOG.items()):
                if (juris != "federal"
                        or form in year_manifest.SCORP_FORMS
                        or (juris, form, year) in KNOWN_GAPS):
                    continue
                with self.subTest(year=year, form=form, piece="template"):
                    template = (_PDFS / juris / str(year)
                                / f"{entry.template_stem}.pdf")
                    self.assertTrue(template.exists(), f"missing {template}")
                    self.assertGreater(template.stat().st_size, 50_000)
                with self.subTest(year=year, form=form, piece="mapping"):
                    entry.mapping_cls.get_mapping(year)  # raises if absent

    def test_workbook_years_have_workbooks(self):
        # Layer-6 penny-parity (vs a third-party XLSX workbook) is a FEDERAL
        # 1040 acceptance layer only; it is deliberately NOT part of the
        # S-corp family's pack. No third-party workbook exists for Form
        # 1120-S or CA Form 100S (SCORP_FEDERAL_YEARS / CA_SCORP_YEARS), so
        # WORKBOOK_YEARS excludes them by design. The named substitute
        # acceptance oracle for the S-corp family is the hand-coded,
        # air-gapped tests/oracles/f100s_reference.py, exercised by
        # tests/test_f100s_oracle_battery.py (spec §7 layer 6).
        for year in year_manifest.WORKBOOK_YEARS:
            with self.subTest(year=year):
                workbook = (REPO_ROOT / "spreadsheets" / "federal"
                            / str(year) / "1040.xlsx")
                self.assertTrue(workbook.exists(), f"missing {workbook}")


class FederalComputeOnlyCompletenessTests(unittest.TestCase):
    """Compute-only federal years carry an INPUT pack (air-gapped attested
    params + Layer-2 tax table) but NO PDF pack — no templates, no mappings,
    no workbook required. The gate demands exactly what the tier promises:
    the native compute inputs, not the emit surface. (Execution of the compute
    itself is machine-checked by the spine-battery compute parameterization.)"""

    def test_every_compute_only_year_has_its_input_pack(self):
        for year in year_manifest.FEDERAL_COMPUTE_ONLY_YEARS:
            with self.subTest(year=year, piece="params"):
                self.assertEqual(load_federal(year).year, year)
            with self.subTest(year=year, piece="attestation"):
                importlib.import_module(
                    f"tests.params_attestations.federal_y{year}")
            with self.subTest(year=year, piece="tax_table"):
                self.assertGreater(len(load_table("federal", year)), 1_000)

class ScorpCompletenessTests(unittest.TestCase):
    def test_every_scorp_federal_year_has_a_complete_pack(self):
        for (juris, form), entry in sorted(CATALOG.items()):
            if juris != "federal" or form not in year_manifest.SCORP_FORMS:
                continue
            for year in year_manifest.SCORP_FEDERAL_YEARS:
                if (juris, form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(year=year, form=form, piece="template"):
                    template = (_PDFS / juris / str(year)
                                / f"{entry.template_stem}.pdf")
                    self.assertTrue(template.exists(), f"missing {template}")
                    self.assertGreater(template.stat().st_size, 50_000)
                with self.subTest(year=year, form=form, piece="mapping"):
                    entry.mapping_cls.get_mapping(year)


class CAScorpCompletenessTests(unittest.TestCase):
    """Manifest-driven, tier-aware completeness for the CA S-corp family.

    Unlike the CATALOG-driven federal/California checks above, this gate is
    driven straight off the manifest (CA_SCORP_FORMS x CA_SCORP_YEARS) so a
    declared CA-S-corp cell CANNOT be silently packless: if the form is not
    yet catalogued or computed, the cell reddens here rather than being
    invisible (years.py: 'no silent half-support in either direction').
    CA_SCORP is a full compute+emit tier, so each cell owes its year-agnostic
    compute module and attested per-year params (compute), plus a
    marker-probe-certified PDF mapping + template (emit). Cells mid-build are
    listed in KNOWN_GAPS with the plan task that fills them, retired as the
    full compute+emit pack for each cell lands."""

    def test_every_ca_scorp_cell_has_a_complete_pack(self):
        for form in year_manifest.CA_SCORP_FORMS:
            for year in year_manifest.CA_SCORP_YEARS:
                if ("california", form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(year=year, form=form, piece="compute"):
                    importlib.import_module(f"tenforty.forms.{form}")
                    self.assertEqual(ca_scorp.load(year).year, year)
                with self.subTest(year=year, form=form, piece="attestation"):
                    importlib.import_module(
                        f"tests.params_attestations.ca_scorp_y{year}")
                with self.subTest(year=year, form=form, piece="emit"):
                    entry = CATALOG[("california", form)]
                    template = (_PDFS / "california" / str(year)
                                / f"{entry.template_stem}.pdf")
                    self.assertTrue(template.exists(), f"missing {template}")
                    entry.mapping_cls.get_mapping(year)


class CaliforniaCompletenessTests(unittest.TestCase):
    def test_every_california_year_has_a_complete_pack(self):
        for year in year_manifest.CALIFORNIA_YEARS:
            with self.subTest(year=year, piece="params"):
                self.assertEqual(ca_params.load(year).year, year)
            with self.subTest(year=year, piece="attestation"):
                importlib.import_module(
                    f"tests.params_attestations.california_y{year}")
            with self.subTest(year=year, piece="tax_table"):
                self.assertGreater(len(load_table("california", year)), 500)
            with self.subTest(year=year, piece="divergence_catalog"):
                # The CA divergence catalog is authored per year as
                # sch_ca_divergences-<year>.catalog.yaml (the populated,
                # hand-authored artifact consumed by
                # scripts/build_sch_ca_fods.py). Adding a new CA year to the
                # manifest reddens this gate until that year's catalog ships.
                catalog = (REPO_ROOT / "spreadsheets" / "california" / str(year)
                           / f"sch_ca_divergences-{year}.catalog.yaml")
                self.assertTrue(catalog.exists(), f"missing {catalog}")
                self.assertGreater(catalog.stat().st_size, 0,
                                   f"{catalog} is empty")
            for (juris, form), entry in sorted(CATALOG.items()):
                if juris != "california" or (juris, form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(year=year, form=form, piece="template"):
                    template = (_PDFS / juris / str(year)
                                / f"{entry.template_stem}.pdf")
                    self.assertTrue(template.exists(), f"missing {template}")
                    self.assertGreater(template.stat().st_size, 50_000)
                with self.subTest(year=year, form=form, piece="mapping"):
                    entry.mapping_cls.get_mapping(year)

    def test_compute_only_years_load_params(self):
        for year in year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS:
            with self.subTest(year=year):
                self.assertEqual(ca_params.load(year).year, year)


class AttestationYearBoundCoverageTests(unittest.TestCase):
    def test_every_supported_ca_year_covered_by_each_attestation_window(self):
        # applies_in_years encodes LAW scope and stays explicit; this check
        # forces a deliberate per-attestation review when a year is added,
        # instead of silent inheritance.
        supported = (set(year_manifest.CALIFORNIA_YEARS)
                     | set(year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS))
        for attestation in _CA_ATTESTATIONS:
            if attestation.applies_in_years is None:
                continue
            with self.subTest(attestation=attestation.field):
                uncovered = supported - attestation.applies_in_years
                self.assertEqual(
                    uncovered, set(),
                    f"{attestation.field}: supported years "
                    f"{sorted(uncovered)} outside its law window — review "
                    f"whether the statute still applies and extend or "
                    f"re-scope deliberately")


class AmendmentCompletenessTests(unittest.TestCase):
    """MIXED-keyed amendment tier. f1040x is REVISION-keyed (one pack for the
    current 1040-X revision serves every amendable federal year); schedule_x is
    YEAR-keyed (the FTB publishes a per-year Schedule X, so one pack per
    amendable California year). Each cell owes template + probe + mapping.
    AMENDMENT_KNOWN_GAPS allowlists cells mid-build — keyed (form, revision) for
    f1040x and (form, year) for schedule_x — retired as packs land."""

    def test_f1040x_revision_pack(self):
        rev = year_manifest.AMENDMENT_TEMPLATE_REVISIONS["f1040x"]
        if ("f1040x", rev) in AMENDMENT_KNOWN_GAPS:
            self.skipTest(f"f1040x @ {rev} allowlisted in AMENDMENT_KNOWN_GAPS")
        base = REPO_ROOT / "pdfs" / "federal" / "amendments"
        with self.subTest(piece="template"):
            self.assertTrue((base / "f1040x.pdf").exists())
        with self.subTest(piece="probe"):
            self.assertTrue((base / "f1040x.probe.pdf").exists())
        with self.subTest(piece="mapping"):
            mod = importlib.import_module("tenforty.mappings.pdf_f1040x")
            self.assertTrue(mod.get_mapping(rev))

    def test_schedule_x_year_packs(self):
        base = REPO_ROOT / "pdfs" / "california" / "amendments"
        for year in year_manifest.amendable_california_years():
            if ("schedule_x", year) in AMENDMENT_KNOWN_GAPS:
                continue
            with self.subTest(year=year, piece="template"):
                self.assertTrue((base / f"schedule_x_{year}.pdf").exists())
            with self.subTest(year=year, piece="probe"):
                self.assertTrue((base / f"schedule_x_{year}.probe.pdf").exists())
            with self.subTest(year=year, piece="mapping"):
                mod = importlib.import_module("tenforty.mappings.pdf_schedule_x")
                self.assertTrue(mod.get_mapping(year))


class UnsupportedYearRaisesEverywhereTests(unittest.TestCase):
    def test_probe_year_raises_in_every_component(self):
        with self.assertRaises(ValueError):
            load_federal(_PROBE_UNSUPPORTED_YEAR)
        with self.assertRaises(NotImplementedError):
            ca_params.load(_PROBE_UNSUPPORTED_YEAR)
        with self.assertRaises(FileNotFoundError):
            load_table("federal", _PROBE_UNSUPPORTED_YEAR)
        for (juris, form), entry in sorted(CATALOG.items()):
            with self.subTest(form=form):
                with self.assertRaises(ValueError):
                    entry.mapping_cls.get_mapping(_PROBE_UNSUPPORTED_YEAR)
