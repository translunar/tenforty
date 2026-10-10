"""Form 3115 scenario block: fail-closed loading and the refusal ledger.

Every registered `form_3115_*` refusal is fired here through the real path
(`load_scenario` on a YAML file), and the unmutated block is the loading
twin of each. `RefusalLedgerCoverageTests` proves the sweep table and the
registry name the same set, so a refusal cannot be registered unfired.
"""
import dataclasses
import datetime
import tempfile
import unittest

from tenforty import attestations
from tenforty.models import Form3115, Form3115Asset
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
    "form_3115_amount_not_cent_exact": (
        lambda: fx.scenario_dict(block=_block(
            section_481a_adjustment=49999.995)),
        ValueError, r"section_481a_adjustment.*exact to the cent"),
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
# form_3115_answer_not_boolean cannot be reached through the loader (which
# types every answer first); it is fired on a Scenario built in code.
_FIRED_ELSEWHERE = {
    "form_3115_in_amendment_packet", "form_3115_answer_not_boolean"}


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

    # One `test_fires_<refusal name>` method per registered refusal is
    # attached below the class (tests/test_scoped_refusals.FIRING_PROOFS
    # names each, and neuters each refusal to see its own test redden).

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
        # An amount finer than a cent cannot be printed as stated, so it
        # cannot straddle the limit: refused before the election is asked.
        for adjustment in (49999.995, 49999.999, 0.004, 0.001):
            block = _block(elect_one_year_spread=True,
                           section_481a_adjustment=adjustment)
            with self.subTest(sub_cent=adjustment), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, "exact to the cent"):
                    fx.load(tmp, fx.scenario_dict(block=block))
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
            scenario.form_3115 = dataclasses.replace(
                scenario.form_3115, under_examination=True)
            with self.assertRaisesRegex(NotImplementedError, "line 6a"):
                fx.orchestrator(tmp).compute_federal(scenario)


class TextColumnsAreNotCoercedTests(unittest.TestCase):
    """An unquoted YAML scalar that looks like a number IS a number by the
    time the loader sees it: `00.11` is 0.11, `0115550100` is octal. A text
    cell is printed as stated, so a number there refuses instead."""

    def _refuses(self, quoted: str, unquoted: str, where: str):
        text = fx.scenario_yaml()
        self.assertGreaterEqual(text.count(quoted), 1, quoted)
        with tempfile.TemporaryDirectory() as tmp:
            # The quoted original loads: the twin.
            fx.load_text(tmp, text)
            with self.assertRaisesRegex(ValueError, where):
                fx.load_text(tmp, text.replace(quoted, unquoted, 1))

    def test_unquoted_numeric_text_refuses(self):
        cases = [
            ("asset_class: '57.0'", "asset_class: 00.11", "asset_class"),
            ("asset_class: '57.0'", "asset_class: 00.241", "asset_class"),
            ("asset_class: '57.0'", "asset_class: 57.00", "asset_class"),
            ("code_section: '168'", "code_section: 167.10", "code_section"),
            ("code_section: '168'", "code_section: 168", "code_section"),
            ("contact_phone: 555-0100", "contact_phone: 0115550100",
             "contact_phone"),
            ("principal_business_activity_code: '531110'",
             "principal_business_activity_code: 531110",
             "principal_business_activity_code"),
            ("present_recovery_period: 39 years",
             "present_recovery_period: 39", "present_recovery_period"),
        ]
        for quoted, unquoted, where in cases:
            with self.subTest(unquoted=unquoted):
                self._refuses(quoted, unquoted, rf"{where}.*quoted")

    def test_quoted_numeric_text_prints_as_written(self):
        text = fx.scenario_yaml().replace(
            "asset_class: '57.0'", "asset_class: '00.11'", 1)
        with tempfile.TemporaryDirectory() as tmp:
            form = fx.load_text(tmp, text).form_3115
        self.assertEqual(form.assets[1].asset_class, "00.11")

    def test_non_text_values_refuse_in_every_text_column(self):
        block_columns = ("contact_person", "contact_phone", "applicant_type",
                         "type_of_change", "principal_business_activity_code")
        asset_columns = (
            "description", "property_type", "use_in_activity",
            "tax_credits_or_grants", "present_method",
            "present_recovery_period", "present_convention",
            "proposed_method", "proposed_recovery_period",
            "proposed_convention", "code_section", "asset_class",
            "asset_account")
        for value in (7, 5.5, True, ["x"]):
            for column in block_columns:
                with self.subTest(column=column, value=value), \
                        tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaisesRegex(ValueError, column):
                        fx.load(tmp, fx.scenario_dict(
                            block=_block(**{column: value})))
            for column in asset_columns:
                with self.subTest(asset_column=column, value=value), \
                        tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaisesRegex(
                            ValueError, rf"assets\[1\]\.{column}"):
                        fx.load(tmp, fx.scenario_dict(
                            block=_asset_block(1, **{column: value})))


class CentExactAmountTests(unittest.TestCase):
    def test_amounts_finer_than_a_cent_refuse(self):
        cases = {
            "section_481a_adjustment": _block(
                section_481a_adjustment=-31250.004),
            "unadjusted_basis": _asset_block(0, unadjusted_basis=240000.004),
            "depreciation_claimed_present_method": _asset_block(
                1, depreciation_claimed_present_method=795.001),
        }
        for field, block in cases.items():
            with self.subTest(field=field), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, rf"{field}.*exact to the cent"):
                    fx.load(tmp, fx.scenario_dict(block=block))

    def test_amounts_stated_to_the_cent_load(self):
        block = _asset_block(
            0, unadjusted_basis=240000.25,
            depreciation_claimed_present_method=41538.1)
        block["section_481a_adjustment"] = -31250.07
        with tempfile.TemporaryDirectory() as tmp:
            form = fx.load(tmp, fx.scenario_dict(block=block)).form_3115
        self.assertEqual(form.assets[0].unadjusted_basis, 240000.25)
        self.assertEqual(form.section_481a_adjustment, -31250.07)


class RequiredFieldSweepTests(unittest.TestCase):
    """Each required cell refuses on its OWN blank, naming itself."""

    _TEXT_COLUMNS = (
        "description", "property_type", "use_in_activity",
        "tax_credits_or_grants", "present_method", "present_recovery_period",
        "present_convention", "proposed_method", "proposed_recovery_period",
        "proposed_convention", "code_section", "asset_class", "asset_account")

    def test_text_columns_are_all_the_asset_text_fields(self):
        typed = {"date_placed_in_service", "unadjusted_basis",
                 "depreciation_claimed_present_method",
                 "special_depreciation_allowance_claimed"}
        self.assertEqual(
            set(self._TEXT_COLUMNS) | typed, set(fx.ASSET_BUILDING))

    def test_each_blank_asset_column_refuses_naming_itself(self):
        for column in self._TEXT_COLUMNS:
            for blank in ("", "   "):
                with self.subTest(column=column, blank=blank), \
                        tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaisesRegex(
                            ValueError,
                            rf"assets\[1\] \(.*\) {column} is blank"):
                        fx.load(tmp, fx.scenario_dict(
                            block=_asset_block(1, **{column: blank})))

    def test_each_blank_identity_field_refuses_naming_itself(self):
        for name in ("first_name", "last_name", "ssn", "address",
                     "address_city", "address_state", "address_zip"):
            with self.subTest(field=name), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, rf"config\.{name} is blank"):
                    fx.load(tmp, fx.scenario_dict(**{name: " "}))

    def test_each_blank_contact_field_refuses_naming_itself(self):
        for name in ("contact_person", "contact_phone"):
            with self.subTest(field=name), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, rf"form_3115\.{name} is blank"):
                    fx.load(tmp, fx.scenario_dict(block=_block(**{name: ""})))

    def test_tax_year_must_end_after_it_begins(self):
        begins = datetime.date(fx.YEAR, 1, 1)
        for ends in (begins, datetime.date(fx.YEAR - 1, 12, 31)):
            with self.subTest(ends=ends), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                        ValueError, r"tax_year_ends .* is not after"):
                    fx.load(tmp, fx.scenario_dict(
                        block=_block(tax_year_ends=ends)))

    def test_tax_year_must_begin_in_the_year_of_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                    ValueError, r"tax_year_begins .* is not in the year"):
                fx.load(tmp, fx.scenario_dict(block=_block(
                    tax_year_begins=datetime.date(fx.YEAR + 1, 1, 1),
                    tax_year_ends=datetime.date(fx.YEAR + 1, 12, 31))))


class NullBlockTests(unittest.TestCase):
    def test_a_null_block_is_refused_not_treated_as_absent(self):
        for text in ("form_3115:\n", "form_3115: null\n", "form_3115: ~\n"):
            data = fx.scenario_dict()
            del data["form_3115"]
            with self.subTest(text=text), \
                    tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, r"form_3115.*empty"):
                    fx.load_text(tmp, fx.scenario_yaml(data) + text)


def _firing_test(build, exc, pattern):
    def test(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(exc, pattern):
                fx.load(tmp, build())
    return test


for _name, (_build, _exc, _pattern) in {**_PARSE_CASES, **_LOAD_CASES}.items():
    setattr(RefusalFiringTests, f"test_fires_{_name}",
            _firing_test(_build, _exc, _pattern))


class RefusalLedgerCoverageTests(unittest.TestCase):
    def test_every_registered_refusal_is_fired_by_name(self):
        registered = {r.name for r in attestations._FORM_3115_REFUSALS}
        fired = set(_PARSE_CASES) | set(_LOAD_CASES) | _FIRED_ELSEWHERE
        self.assertEqual(registered, fired)

    def test_every_case_has_its_own_named_test_method(self):
        for name in {**_PARSE_CASES, **_LOAD_CASES}:
            with self.subTest(refusal=name):
                self.assertTrue(callable(
                    getattr(RefusalFiringTests, f"test_fires_{name}")))

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
        self.assertEqual(stages["form_3115_answer_not_boolean"], "load")

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
