"""FilingStatus MARRIED_* → MARRIED_FILING_* rename (v0.2.0 input schema).

The retired strings must fail LOUDLY at every input boundary (scenario
YAML, direct TaxReturnConfig construction, CA YAML federal_context) with a
message naming the replacement — never a silent alias, never a bare
"'married_jointly' is not a valid FilingStatus". The workbook flattener must
refuse a status it has no checkbox key for rather than silently feed the
oracle a status-less return.
"""
import dataclasses
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.models import (
    RETIRED_FILING_STATUS_STRINGS,
    W2,
    FilingStatus,
    Scenario,
    TaxReturnConfig,
    parse_filing_status,
)
from tenforty.oracle.flattener import flatten_scenario
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._ca_fixtures import _make_ca_v1_smoke_scenario, _write_ca_yaml
from tests.helpers import scope_out_attestation_defaults

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_yaml(directory: Path, *, filing_status: str) -> Path:
    """Minimal synthetic scenario YAML whose only variable is the status."""
    data = {
        "config": {
            "year": 2025,
            "filing_status": filing_status,
            "birthdate": "1985-03-01",
            "state": "CA",
            "first_name": "Example",
            "last_name": "Filer",
            "ssn": "000-00-0001",
            "digital_assets": False,
            **scope_out_attestation_defaults(),
        },
    }
    path = directory / "scenario.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _config(status) -> TaxReturnConfig:
    return TaxReturnConfig(
        year=2025,
        filing_status=status,
        birthdate="1985-03-01",
        state="CA",
        digital_assets=False,
        **scope_out_attestation_defaults(),
    )


def _scenario_from(cfg: TaxReturnConfig, *, state_refund: bool = False) -> Scenario:
    from tenforty.models import Form1099G
    form1099_g = (
        [Form1099G(payer="Example State", state_tax_refund=100.0)]
        if state_refund else [])
    return Scenario(
        config=cfg,
        w2s=[W2(employer="Example Employer", wages=50_000.0,
                federal_tax_withheld=5_000.0, ss_wages=50_000.0,
                ss_tax_withheld=3_100.0, medicare_wages=50_000.0,
                medicare_tax_withheld=725.0)],
        form1099_g=form1099_g,
    )


def _scenario(status: FilingStatus, *, state_refund: bool = False) -> Scenario:
    return _scenario_from(_config(status), state_refund=state_refund)


class FilingStatusNamesTests(unittest.TestCase):
    def test_members_and_values(self):
        self.assertEqual(
            {s.name: s.value for s in FilingStatus},
            {"SINGLE": "single",
             "MARRIED_FILING_JOINTLY": "married_filing_jointly",
             "MARRIED_FILING_SEPARATELY": "married_filing_separately",
             "HEAD_OF_HOUSEHOLD": "head_of_household",
             "QUALIFYING_WIDOW": "qualifying_widow"})

    def test_retired_table_maps_old_strings_to_new_members(self):
        self.assertEqual(
            RETIRED_FILING_STATUS_STRINGS,
            {"married_jointly": FilingStatus.MARRIED_FILING_JOINTLY,
             "married_separately": FilingStatus.MARRIED_FILING_SEPARATELY})


class RetiredStatusStringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_yaml_with_new_mfj_string_loads(self):
        # Positive control: the fixture is otherwise loadable, so the
        # refusals below are caused by the status string alone.
        scenario = load_scenario(
            _write_yaml(self.tmp, filing_status="married_filing_jointly"))
        self.assertIs(scenario.config.filing_status,
                      FilingStatus.MARRIED_FILING_JOINTLY)

    def test_yaml_with_retired_mfj_string_is_refused_with_replacement(self):
        with self.assertRaisesRegex(
                ValueError,
                r"married_filing_jointly.*v0\.2\.0|v0\.2\.0.*married_filing_jointly"):
            load_scenario(_write_yaml(self.tmp, filing_status="married_jointly"))

    def test_yaml_with_retired_mfs_string_is_refused_with_replacement(self):
        with self.assertRaisesRegex(
                ValueError,
                r"married_filing_separately.*v0\.2\.0|v0\.2\.0.*married_filing_separately"):
            load_scenario(_write_yaml(self.tmp, filing_status="married_separately"))

    def test_typo_gets_did_you_mean(self):
        with self.assertRaisesRegex(ValueError, r"did you mean 'married_filing_jointly'"):
            parse_filing_status("married_filing_jointy")

    def test_unknown_string_without_close_match_has_no_suggestion(self):
        with self.assertRaises(ValueError) as ctx:
            parse_filing_status("zzzz")
        self.assertNotIn("did you mean", str(ctx.exception))
        self.assertIn("zzzz", str(ctx.exception))

    def test_direct_config_construction_also_refuses(self):
        with self.assertRaisesRegex(ValueError, "married_filing_jointly"):
            TaxReturnConfig(year=2025, filing_status="married_jointly",
                            birthdate="1985-03-01", state="CA")

    def test_enum_member_passes_through(self):
        self.assertIs(parse_filing_status(FilingStatus.HEAD_OF_HOUSEHOLD),
                      FilingStatus.HEAD_OF_HOUSEHOLD)

    def test_valid_string_parses_to_member(self):
        self.assertIs(parse_filing_status("married_filing_separately"),
                      FilingStatus.MARRIED_FILING_SEPARATELY)


class CaSnapshotRetiredStatusTests(unittest.TestCase):
    def test_ca_yaml_federal_context_retired_string_is_refused(self):
        scenario = _make_ca_v1_smoke_scenario()
        scenario.ca540 = None
        ca_yaml_path = _write_ca_yaml({
            "ca540": {"estimated_payments": 0.0, "use_tax": 0.0},
            "federal_context": {"filing_status": "married_jointly"},
        })
        output_dir = Path(tempfile.mkdtemp())
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=_REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work")
        with self.assertRaisesRegex(ValueError, "married_filing_jointly"):
            orchestrator.run_full_california_return(
                scenario=scenario, ca_yaml_path=ca_yaml_path,
                output_dir=output_dir)


class FlattenerStatusKeyTests(unittest.TestCase):
    def test_every_status_has_a_workbook_checkbox_key(self):
        for status in FilingStatus:
            with self.subTest(status=status):
                flat = flatten_scenario(_scenario(status))
                self.assertEqual(
                    sum(1 for k in flat if k.startswith("filing_status_")), 1)

    def test_every_status_has_a_salt_worksheet_key(self):
        for status in FilingStatus:
            with self.subTest(status=status):
                flat = flatten_scenario(_scenario(status, state_refund=True))
                self.assertEqual(
                    sum(1 for k in flat if k.startswith("salt_filing_status_")), 1)

    def test_unknown_status_value_raises_not_silently_omits(self):
        cfg = _config(FilingStatus.SINGLE)
        object.__setattr__(cfg, "filing_status", "bogus")
        with self.assertRaises(KeyError):
            flatten_scenario(_scenario_from(cfg))


class RetiredLiteralSweepTests(unittest.TestCase):
    ALLOW = {"tenforty/models.py", "tests/test_filing_status_rename.py"}
    # Lowercase alternatives are unanchored so embedded forms
    # (`filing_status_married_jointly`) match; `married_filing_*` cannot.
    # Uppercase stays anchored so MARRIED_FILING_* cannot false-positive.
    PATTERN = re.compile(
        r"\bMARRIED_(JOINTLY|SEPARATELY)\b|married_(jointly|separately)")

    def test_no_retired_literal_outside_the_refusal_table(self):
        hits = []
        for top in ("tenforty", "tests", "scripts"):
            for path in sorted((_REPO_ROOT / top).rglob("*")):
                if path.suffix not in (".py", ".yaml"):
                    continue
                if "__pycache__" in path.parts:
                    continue
                rel = path.relative_to(_REPO_ROOT).as_posix()
                if rel in self.ALLOW:
                    continue
                if self.PATTERN.search(path.read_text(errors="replace")):
                    hits.append(rel)
        self.assertEqual(hits, [])
