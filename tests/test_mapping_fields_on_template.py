# tests/test_mapping_fields_on_template.py
"""Layer-4 static gate: every PDF field path a mapping references must
exist on that year's blank template. No path exists for a guessed field
name to survive: probe-discovered names are on the template by
construction, and anything else fails here."""
import unittest

from pypdf import PdfReader

from tenforty import years as year_manifest
from tenforty.mappings.catalog import CATALOG, KNOWN_GAPS, field_paths
from tests.helpers import REPO_ROOT

_PDFS = REPO_ROOT / "pdfs"


def _years_for(jurisdiction: str, form: str) -> tuple[int, ...]:
    if form in year_manifest.SCORP_FORMS:
        return year_manifest.SCORP_FEDERAL_YEARS
    if form in year_manifest.CA_SCORP_FORMS:
        return year_manifest.CA_SCORP_YEARS
    return (year_manifest.FEDERAL_YEARS if jurisdiction == "federal"
            else year_manifest.CALIFORNIA_YEARS)


class CatalogShapeTests(unittest.TestCase):
    def test_catalog_covers_manifest_form_sets_exactly(self):
        federal = {form for (juris, form) in CATALOG if juris == "federal"}
        california = {form for (juris, form) in CATALOG if juris == "california"}
        self.assertEqual(federal,
                         set(year_manifest.FEDERAL_FORMS)
                         | set(year_manifest.SCORP_FORMS))
        self.assertEqual(california,
                         set(year_manifest.CALIFORNIA_FORMS)
                         | set(year_manifest.CA_SCORP_FORMS))


class FieldsExistOnTemplateTests(unittest.TestCase):
    def test_every_mapped_field_exists_on_blank_template(self):
        for (jurisdiction, form), entry in sorted(CATALOG.items()):
            for year in _years_for(jurisdiction, form):
                if (jurisdiction, form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(jurisdiction=jurisdiction, form=form,
                                  year=year):
                    template = (_PDFS / jurisdiction / str(year)
                                / f"{entry.template_stem}.pdf")
                    self.assertTrue(template.exists(),
                                    f"missing template {template}")
                    on_template = set((PdfReader(template).get_fields()
                                       or {}).keys())
                    referenced = field_paths(entry, year)
                    self.assertGreater(len(referenced), 0)
                    missing = referenced - on_template
                    self.assertEqual(
                        missing, set(),
                        f"{form} {year}: mapping references fields absent "
                        f"from the blank template")


class CheckboxStatesAreMappedTests(unittest.TestCase):
    """Every checkbox state's semantic key must itself be a mapped field, so
    its PDF field path is verified by the fields-on-template gate (which
    checks get_mapping's leaves). This makes checkbox coverage a STANDING
    property: a future checkbox state whose field was never mapped — and
    whose PDF path would otherwise be verified nowhere — reddens here instead
    of silently escaping."""
    def test_checkbox_states_are_a_subset_of_the_mapping(self):
        for (jurisdiction, form), entry in sorted(CATALOG.items()):
            cls = entry.mapping_cls
            if not hasattr(cls, "get_checkbox_states"):
                continue
            for year in _years_for(jurisdiction, form):
                if (jurisdiction, form, year) in KNOWN_GAPS:
                    continue
                with self.subTest(jurisdiction=jurisdiction, form=form,
                                  year=year):
                    checkbox_keys = set(cls.get_checkbox_states(year))
                    mapped_keys = set(cls.get_mapping(year))
                    self.assertLessEqual(
                        checkbox_keys, mapped_keys,
                        f"{form} {year}: checkbox-state fields not in the "
                        f"mapping — their PDF paths are verified nowhere")
