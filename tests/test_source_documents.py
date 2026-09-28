"""Tests for W-2 source-document declaration, validation, and routing.

Covers the load layer only: `W2.pdf` -> normalized `SourceDocument` records
with packet routing derived from the W-2's own declared data. Packet
splicing is tested in test_pdf_packet.py; the emit gate in
test_source_document_gate.py.
"""

import tempfile
import textwrap
import unittest
from pathlib import Path

import pypdf

from tenforty.models import SourceDocument, W2
from tenforty.scenario import _load_source_documents, load_scenario

# Minimal config block that satisfies _validate_scenario_config for a CA
# return, borrowed from tests/test_scenario_ca540.py::_YAML_WITHOUT_CA540
# (year bumped to 2024; SSN/name are the same repo-standard synthetic
# placeholders used there). This test's subject is source_documents, not
# config validation -- see task-1-brief.md Step 1 contingency note.
_MINIMAL_CA_CONFIG = textwrap.dedent("""\
    config:
      year: 2024
      filing_status: single
      birthdate: "01-01-1980"
      state: CA
      first_name: "Taxpayer"
      last_name: "A"
      ssn: "000-00-0000"
      has_foreign_accounts: false
      prior_year_itemized: false
      acknowledges_sch_a_sales_tax_unsupported: false
      acknowledges_qbi_below_threshold: false
      acknowledges_unlimited_at_risk: false
      basis_tracked_externally: false
      acknowledges_no_partnership_se_earnings: false
      acknowledges_no_section_1231_gain: false
      acknowledges_no_more_than_four_k1s: false
      acknowledges_no_k1_credits: false
      acknowledges_no_section_179: false
      acknowledges_no_estate_trust_k1: false
      acknowledges_no_wash_sale_adjustments: false
      acknowledges_no_other_basis_adjustments: false
      acknowledges_no_28_rate_gain: false
      acknowledges_no_unrecaptured_section_1250: false
      acknowledges_no_1120s_schedule_l_needed: false
      acknowledges_no_1120s_schedule_m_needed: false
      acknowledges_constant_shareholder_ownership: false
      acknowledges_no_section_1375_tax: false
      acknowledges_no_section_1374_tax: false
      acknowledges_cogs_aggregate_only: false
      acknowledges_officer_comp_aggregate_only: false
      acknowledges_no_elective_payment_election: false
      acknowledges_no_540nr_filing: false
      acknowledges_no_ca_amt_preferences: false
      acknowledges_no_ca_nol_carryover: false
      acknowledges_no_ca_depreciation_divergence: false
      acknowledges_no_ca_ira_basis_divergence: false
      acknowledges_no_ca_rdp_status: false
      acknowledges_no_excess_business_loss_carryover: false
      acknowledges_no_1031_personal_property_divergence: false
      acknowledges_no_ic_worker_reclassification: false
      acknowledges_no_other_state_tax_credit: false
      acknowledges_no_railroad_retirement_benefits: false
      acknowledges_no_paid_family_leave_benefits: false
      acknowledges_no_capital_loss_carryforward: true
      acknowledges_no_federal_amt: true
""")


def _make_pdf(path: Path, num_pages: int = 1) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)
    writer.close()
    return path


def _w2(**overrides) -> W2:
    base = dict(
        employer="Acme Corp", wages=50000.0, federal_tax_withheld=6000.0,
        ss_wages=50000.0, ss_tax_withheld=3100.0, medicare_wages=50000.0,
        medicare_tax_withheld=725.0,
    )
    base.update(overrides)
    return W2(**base)


class LoadSourceDocumentsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_w2_without_pdf_contributes_no_record(self):
        docs = _load_source_documents([_w2()], self.base)
        self.assertEqual(docs, [])

    def test_w2_pdf_resolves_relative_to_base_dir(self):
        _make_pdf(self.base / "w2.pdf")
        docs = _load_source_documents([_w2(pdf="w2.pdf")], self.base)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].path, (self.base / "w2.pdf").resolve())
        self.assertEqual(docs[0].kind, "w2")

    def test_routing_federal_only_without_ca_withholding(self):
        _make_pdf(self.base / "w2.pdf")
        docs = _load_source_documents([_w2(pdf="w2.pdf")], self.base)
        self.assertEqual(docs[0].packets, ("federal_individual",))

    def test_routing_includes_california_with_ca_withholding(self):
        _make_pdf(self.base / "w2.pdf")
        w2 = _w2(pdf="w2.pdf", state="CA",
                 state_wages=50000.0, state_tax_withheld=2500.0)
        docs = _load_source_documents([w2], self.base)
        self.assertEqual(docs[0].packets, ("federal_individual", "california"))

    def test_ca_state_with_zero_withholding_routes_federal_only(self):
        _make_pdf(self.base / "w2.pdf")
        w2 = _w2(pdf="w2.pdf", state="CA",
                 state_wages=50000.0, state_tax_withheld=0.0)
        docs = _load_source_documents([w2], self.base)
        self.assertEqual(docs[0].packets, ("federal_individual",))

    def test_non_ca_state_withholding_routes_federal_only(self):
        _make_pdf(self.base / "w2.pdf")
        w2 = _w2(pdf="w2.pdf", state="NY",
                 state_wages=50000.0, state_tax_withheld=2500.0)
        docs = _load_source_documents([w2], self.base)
        self.assertEqual(docs[0].packets, ("federal_individual",))

    def test_declaration_order_preserved(self):
        _make_pdf(self.base / "a.pdf")
        _make_pdf(self.base / "b.pdf")
        docs = _load_source_documents(
            [_w2(employer="A", pdf="a.pdf"), _w2(employer="B", pdf="b.pdf")],
            self.base)
        self.assertEqual([d.path.name for d in docs], ["a.pdf", "b.pdf"])

    def test_missing_file_refused_naming_employer(self):
        with self.assertRaises(ValueError) as ctx:
            _load_source_documents([_w2(pdf="nope.pdf")], self.base)
        self.assertIn("Acme Corp", str(ctx.exception))
        self.assertIn("nope.pdf", str(ctx.exception))

    def test_non_pdf_file_refused_naming_employer(self):
        (self.base / "junk.pdf").write_text("not a pdf")
        with self.assertRaises(ValueError) as ctx:
            _load_source_documents([_w2(pdf="junk.pdf")], self.base)
        self.assertIn("Acme Corp", str(ctx.exception))

    def test_zero_page_pdf_refused(self):
        writer = pypdf.PdfWriter()
        with open(self.base / "empty.pdf", "wb") as f:
            writer.write(f)
        writer.close()
        with self.assertRaises(ValueError) as ctx:
            _load_source_documents([_w2(pdf="empty.pdf")], self.base)
        self.assertIn("Acme Corp", str(ctx.exception))


class LoadScenarioIntegrationTests(unittest.TestCase):
    """End-to-end through load_scenario: YAML in, Scenario.source_documents out."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def _write_scenario(self, w2_extra: str = "") -> Path:
        yaml_path = self.base / "scenario.yaml"
        yaml_path.write_text(_MINIMAL_CA_CONFIG + textwrap.dedent(f"""\
            w2s:
              - employer: "Acme Corp"
                wages: 50000
                federal_tax_withheld: 6000
                ss_wages: 50000
                ss_tax_withheld: 3100
                medicare_wages: 50000
                medicare_tax_withheld: 725
            {w2_extra}"""))
        return yaml_path

    def test_scenario_without_pdfs_loads_with_empty_source_documents(self):
        scenario = load_scenario(self._write_scenario())
        self.assertEqual(scenario.source_documents, [])

    def test_scenario_with_pdf_populates_source_documents(self):
        _make_pdf(self.base / "w2 acme.pdf")
        yaml_path = self.base / "scenario.yaml"
        yaml_path.write_text(_MINIMAL_CA_CONFIG + textwrap.dedent("""\
            w2s:
              - employer: "Acme Corp"
                wages: 50000
                federal_tax_withheld: 6000
                ss_wages: 50000
                ss_tax_withheld: 3100
                medicare_wages: 50000
                medicare_tax_withheld: 725
                state: CA
                state_wages: 50000
                state_tax_withheld: 2500
                pdf: "w2 acme.pdf"
        """))
        scenario = load_scenario(yaml_path)
        self.assertEqual(len(scenario.source_documents), 1)
        doc = scenario.source_documents[0]
        self.assertIsInstance(doc, SourceDocument)
        self.assertEqual(doc.kind, "w2")
        self.assertEqual(doc.packets, ("federal_individual", "california"))
        self.assertTrue(doc.path.is_absolute())


if __name__ == "__main__":
    unittest.main()
