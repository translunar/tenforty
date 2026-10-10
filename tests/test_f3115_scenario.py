"""Form 3115 scenario block: fail-closed loading and the refusal ledger.

Every registered `form_3115_*` refusal is fired here through the real path
(`load_scenario` on a YAML file), and the unmutated block is the loading
twin of each. `RefusalLedgerCoverageTests` proves the sweep table and the
registry name the same set, so a refusal cannot be registered unfired.
"""
import datetime
import tempfile
import unittest

from tenforty import attestations
from tenforty.models import Form3115, Form3115Asset
from tenforty.orchestrator import ReturnOrchestrator
from tests import _f3115_fixtures as fx


def _block(**overrides):
    return fx.base_block(**overrides)


def _asset_block(index=0, **asset_overrides):
    block = fx.base_block()
    block["assets"][index].update(asset_overrides)
    return block


def _without(key):
    block = fx.base_block()
    del block[key]
    return block


def _asset_without(key):
    block = fx.base_block()
    del block["assets"][1][key]
    return block


# refusal name -> (scenario mapping, exception, text the message must carry).
_PARSE_CASES = {
    "form_3115_not_a_mapping": (
        lambda: fx.scenario_dict(block=["year_of_change"]),
        ValueError, r"form_3115.*must be a mapping"),
    "form_3115_unknown_key": (
        lambda: fx.scenario_dict(block=_block(section_481_adjustment=1.0)),
        ValueError, r"Unknown key.*section_481_adjustment"),
    "form_3115_missing_key": (
        lambda: fx.scenario_dict(block=_without("under_examination")),
        ValueError, r"under_examination"),
}

_LOAD_CASES = {
    "form_3115_year_of_change_mismatch": (
        lambda: fx.scenario_dict(block=_block(year_of_change=fx.YEAR - 1)),
        ValueError, r"year_of_change.*2024.*2025"),
    "form_3115_change_number_unsupported": (
        lambda: fx.scenario_dict(block=_block(designated_change_number=8)),
        NotImplementedError, r"designated_change_number 8"),
    "form_3115_tax_year_dates": (
        lambda: fx.scenario_dict(block=_block(
            tax_year_begins=datetime.date(fx.YEAR - 1, 7, 1))),
        ValueError, r"tax_year_begins"),
    "form_3115_applicant_type_unsupported": (
        lambda: fx.scenario_dict(block=_block(applicant_type="partnership")),
        NotImplementedError, r"applicant_type 'partnership'"),
    "form_3115_type_of_change_unsupported": (
        lambda: fx.scenario_dict(block=_block(type_of_change="other")),
        NotImplementedError, r"type_of_change 'other'"),
    "form_3115_joint_filer_unsupported": (
        lambda: fx.scenario_dict(
            filing_status="married_jointly", spouse_first_name="Wren",
            spouse_last_name="Testcase", spouse_ssn="000-00-0000"),
        NotImplementedError, r"joint"),
    "form_3115_applicant_identity_missing": (
        lambda: fx.scenario_dict(address_zip=""),
        ValueError, r"address_zip"),
    "form_3115_contact_missing": (
        lambda: fx.scenario_dict(block=_block(contact_phone="  ")),
        ValueError, r"contact_phone"),
    "form_3115_business_activity_code_malformed": (
        lambda: fx.scenario_dict(block=_block(
            principal_business_activity_code="5311")),
        ValueError, r"principal_business_activity_code"),
    "form_3115_one_year_election_ineligible": (
        lambda: fx.scenario_dict(block=_block(
            elect_one_year_spread=True, section_481a_adjustment=50000.0)),
        ValueError, r"elect_one_year_spread"),
    "form_3115_no_assets": (
        lambda: fx.scenario_dict(block=_block(assets=[])),
        ValueError, r"assets"),
    "form_3115_asset_field_blank": (
        lambda: fx.scenario_dict(block=_asset_block(1, asset_class=" ")),
        ValueError, r"Synthetic appliance set.*asset_class"),
    "form_3115_asset_account_unknown": (
        lambda: fx.scenario_dict(block=_asset_block(0, asset_account="pool")),
        ValueError, r"asset_account 'pool'"),
    "form_3115_asset_amount_negative": (
        lambda: fx.scenario_dict(block=_asset_block(
            0, unadjusted_basis=-1.0)),
        ValueError, r"unadjusted_basis"),
    # --- One answer each: the answer v1 cannot print refuses by name. ---
    "form_3115_correspondence_by_fax_or_email": (
        lambda: fx.scenario_dict(block=_block(
            wants_correspondence_by_fax_or_email=True)),
        NotImplementedError, r"wants_correspondence_by_fax_or_email"),
    "form_3115_eligibility_rules_restrict": (
        lambda: fx.scenario_dict(block=_block(
            eligibility_rules_restrict_automatic_change=True)),
        NotImplementedError, r"line 2"),
    "form_3115_information_incomplete": (
        lambda: fx.scenario_dict(block=_block(
            all_required_information_provided=False)),
        NotImplementedError, r"line 3"),
    "form_3115_final_year_of_trade_or_business": (
        lambda: fx.scenario_dict(block=_block(
            ceases_trade_or_terminates_in_year_of_change=True)),
        NotImplementedError, r"line 4"),
    "form_3115_section_381_principal_method": (
        lambda: fx.scenario_dict(block=_block(
            changing_to_section_381_principal_method=True)),
        NotImplementedError, r"line 5"),
    "form_3115_under_examination": (
        lambda: fx.scenario_dict(block=_block(under_examination=True)),
        NotImplementedError, r"line 6a.*unsupported in v1"),
    "form_3115_no_audit_protection": (
        lambda: fx.scenario_dict(block=_block(audit_protection_applies=False)),
        NotImplementedError, r"line 7a"),
    "form_3115_before_appeals_or_court": (
        lambda: fx.scenario_dict(block=_block(
            before_appeals_or_federal_court=True)),
        NotImplementedError, r"line 8a.*unsupported in v1"),
    "form_3115_prior_change_within_five_years": (
        lambda: fx.scenario_dict(block=_block(
            prior_method_change_within_five_years=True)),
        NotImplementedError,
        r"prior §446\(e\) change within 5 years — eligibility interaction "
        r"with Rev\. Proc\. 2022-14 §6\.01 not encoded in v1"),
    "form_3115_pending_request": (
        lambda: fx.scenario_dict(block=_block(
            pending_ruling_or_method_change_request=True)),
        NotImplementedError, r"line 12"),
    "form_3115_overall_method_change": (
        lambda: fx.scenario_dict(block=_block(changing_overall_method=True)),
        NotImplementedError, r"line 13"),
    "form_3115_cut_off_basis": (
        lambda: fx.scenario_dict(block=_block(cut_off_basis=True)),
        NotImplementedError, r"line 25"),
    "form_3115_prior_adjustment_remaining": (
        lambda: fx.scenario_dict(block=_block(
            prior_section_481a_adjustment_remaining=True)),
        NotImplementedError, r"line 27"),
    "form_3115_related_party_adjustment": (
        lambda: fx.scenario_dict(block=_block(
            adjustment_from_related_party_transactions=True)),
        NotImplementedError, r"line 29"),
    "form_3115_cladr": (
        lambda: fx.scenario_dict(block=_block(depreciation_under_cladr=True)),
        NotImplementedError, r"Schedule E, line 1"),
    "form_3115_depreciation_capitalized": (
        lambda: fx.scenario_dict(block=_block(
            depreciation_capitalized_under_another_section=True)),
        NotImplementedError, r"Schedule E, line 2"),
    "form_3115_depreciation_election": (
        lambda: fx.scenario_dict(block=_block(
            depreciation_election_made=True)),
        NotImplementedError, r"Schedule E, line 3"),
    "form_3115_public_utility_property": (
        lambda: fx.scenario_dict(block=_block(public_utility_property=True)),
        NotImplementedError, r"Schedule E, line 4c"),
}

# Raised directly at the amendment entry; fired in tests/test_f3115_emit.py.
_FIRED_ELSEWHERE = {"form_3115_in_amendment_packet"}


class LoadingTwinTests(unittest.TestCase):
    """The unmutated block loads: the passing twin of every refusal below."""

    def test_base_block_loads_into_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(tmp, fx.scenario_dict())
        form = scenario.form_3115
        self.assertIsInstance(form, Form3115)
        self.assertEqual(form.year_of_change, 2025)
        self.assertEqual(form.designated_change_number, 7)
        self.assertEqual(form.section_481a_adjustment, 31250.0)
        self.assertIs(form.elect_one_year_spread, False)
        self.assertEqual(form.tax_year_ends, datetime.date(2025, 12, 31))
        self.assertEqual(len(form.assets), 2)
        self.assertIsInstance(form.assets[0], Form3115Asset)
        self.assertEqual(form.assets[1].proposed_recovery_period, "5 years")
        self.assertEqual(
            form.assets[0].date_placed_in_service, datetime.date(2019, 3, 1))

    def test_scenario_without_the_block_has_no_form(self):
        data = fx.scenario_dict()
        del data["form_3115"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(fx.load(tmp, data).form_3115)

    def test_every_block_key_is_required(self):
        """No defaults: dropping ANY key of the block refuses, naming it."""
        for key in fx.BASE_BLOCK:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, key):
                    fx.load(tmp, fx.scenario_dict(block=_without(key)))

    def test_every_asset_column_is_required(self):
        for key in fx.ASSET_BUILDING:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, rf"assets\[1\].*{key}"):
                    fx.load(tmp, fx.scenario_dict(block=_asset_without(key)))

    def test_unknown_asset_key_refuses(self):
        block = _asset_block(0, salvage_value=10.0)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                    ValueError, r"assets\[0\].*salvage_value"):
                fx.load(tmp, fx.scenario_dict(block=block))

    def test_quoted_answer_is_not_coerced(self):
        """A quoted "no" is truthy; a string where a bool belongs refuses."""
        for key in ("under_examination", "elect_one_year_spread",
                    "lived_in_residential_rental_before_renting"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, key):
                    fx.load(tmp, fx.scenario_dict(block=_block(**{key: "no"})))

    def test_non_numeric_adjustment_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "section_481a_adjustment"):
                fx.load(tmp, fx.scenario_dict(
                    block=_block(section_481a_adjustment="31250")))

    def test_line_4b_may_be_stated_not_applicable(self):
        """Schedule E line 4b is asked only of residential rental property:
        an explicit null (key present) states it does not apply."""
        block = _block(lived_in_residential_rental_before_renting=None)
        with tempfile.TemporaryDirectory() as tmp:
            form = fx.load(tmp, fx.scenario_dict(block=block)).form_3115
        self.assertIsNone(form.lived_in_residential_rental_before_renting)

    def test_business_activity_code_may_be_stated_absent(self):
        block = _block(principal_business_activity_code=None)
        with tempfile.TemporaryDirectory() as tmp:
            form = fx.load(tmp, fx.scenario_dict(block=block)).form_3115
        self.assertIsNone(form.principal_business_activity_code)


class RefusalFiringTests(unittest.TestCase):
    """Each refusal fires through `load_scenario` with its own text."""

    def test_parse_and_load_refusals_fire(self):
        for name, (build, exc, pattern) in {
                **_PARSE_CASES, **_LOAD_CASES}.items():
            with self.subTest(refusal=name), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(exc, pattern):
                    fx.load(tmp, build())

    def test_message_is_the_registered_one(self):
        """The text raised is the registry entry's own, not a look-alike
        raised somewhere upstream of the ledger."""
        by_name = {r.name: r for r in attestations._FORM_3115_REFUSALS}
        for name, (build, exc, _pattern) in _LOAD_CASES.items():
            with self.subTest(refusal=name), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(exc) as ctx:
                    fx.load(tmp, build())
                refusal = by_name[name]
                # Rebuild the scenario the loader saw, minus the ledger.
                offenders = self._offenders_without_ledger(refusal, build())
                self.assertEqual(str(ctx.exception), refusal.message(offenders))

    def _offenders_without_ledger(self, refusal, data):
        from tenforty import scenario as scenario_module
        original = scenario_module._attestations.enforce_scoped_refusals
        scenario_module._attestations.enforce_scoped_refusals = (
            lambda *a, **k: None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                loaded = fx.load(tmp, data)
        finally:
            scenario_module._attestations.enforce_scoped_refusals = original
        offenders = refusal.offenders(loaded)
        self.assertTrue(offenders)
        return offenders

    def test_election_boundaries(self):
        """Positive and under $50,000 elects; everything else refuses."""
        cases = [
            (49999.99, True), (0.01, True),
            (50000.0, False), (50000.01, False), (0.0, False),
            (-0.01, False), (-31250.0, False),
        ]
        for adjustment, accepted in cases:
            block = _block(elect_one_year_spread=True,
                           section_481a_adjustment=adjustment)
            with self.subTest(adjustment=adjustment), \
                    tempfile.TemporaryDirectory() as tmp:
                if accepted:
                    form = fx.load(tmp, fx.scenario_dict(block=block)).form_3115
                    self.assertIs(form.elect_one_year_spread, True)
                else:
                    with self.assertRaisesRegex(
                            ValueError, "elect_one_year_spread"):
                        fx.load(tmp, fx.scenario_dict(block=block))

    def test_no_election_accepts_any_adjustment(self):
        for adjustment in (-31250.0, 0.0, 50000.0, 725000.0):
            block = _block(section_481a_adjustment=adjustment)
            with self.subTest(adjustment=adjustment), \
                    tempfile.TemporaryDirectory() as tmp:
                form = fx.load(tmp, fx.scenario_dict(block=block)).form_3115
                self.assertEqual(form.section_481a_adjustment, adjustment)

    def test_only_change_number_7_is_accepted(self):
        for number in (1, 6, 8, 107, 184, 200, 244):
            with self.subTest(number=number), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        NotImplementedError,
                        rf"designated_change_number {number}\b"):
                    fx.load(tmp, fx.scenario_dict(
                        block=_block(designated_change_number=number)))

    def test_scenario_built_in_code_is_refused_at_compute(self):
        """A Scenario that never passed the loader is still refused."""
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(tmp, fx.scenario_dict())
        import dataclasses
        scenario.form_3115 = dataclasses.replace(
            scenario.form_3115, under_examination=True)
        with self.assertRaisesRegex(NotImplementedError, "line 6a"):
            ReturnOrchestrator().compute_federal(scenario)


class RefusalLedgerCoverageTests(unittest.TestCase):
    def test_every_registered_refusal_is_fired_by_name(self):
        registered = {r.name for r in attestations._FORM_3115_REFUSALS}
        fired = set(_PARSE_CASES) | set(_LOAD_CASES) | _FIRED_ELSEWHERE
        self.assertEqual(registered, fired)

    def test_registered_refusals_are_in_the_enforced_ledger(self):
        enforced = {r.name for r in attestations._SCOPED_REFUSALS}
        for refusal in attestations._FORM_3115_REFUSALS:
            with self.subTest(refusal=refusal.name):
                self.assertIn(refusal.name, enforced)
                self.assertTrue(refusal.name.startswith("form_3115_"))

    def test_stages(self):
        stages = {r.name: r.stage for r in attestations._FORM_3115_REFUSALS}
        for name in _PARSE_CASES:
            with self.subTest(refusal=name):
                self.assertEqual(stages[name], "parse")
        for name in _LOAD_CASES:
            with self.subTest(refusal=name):
                self.assertEqual(stages[name], "load")
        self.assertEqual(stages["form_3115_in_amendment_packet"], "emit")

    def test_ledger_is_silent_without_the_block(self):
        data = fx.scenario_dict()
        del data["form_3115"]
        with tempfile.TemporaryDirectory() as tmp:
            scenario = fx.load(tmp, data)
        for refusal in attestations._FORM_3115_REFUSALS:
            if refusal.stage == "parse":
                continue
            with self.subTest(refusal=refusal.name):
                self.assertEqual(list(refusal.offenders(scenario)), [])


if __name__ == "__main__":
    unittest.main()
