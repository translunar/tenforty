import unittest
from pathlib import Path

import tempfile

import yaml

from datetime import date

from tenforty.models import (
    DepreciableAsset,
    FilingStatus,
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    RentalProperty,
    Scenario,
    TaxReturnConfig,
    W2,
    _LOT_ADJUSTMENT_FIELDS,
)
from tenforty.scenario import load_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestW2(unittest.TestCase):
    def test_create_w2(self):
        w2 = W2(
            employer="Acme Corp",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        self.assertEqual(w2.wages, 100000.00)
        self.assertEqual(w2.employer, "Acme Corp")

    def test_w2_optional_fields_default_to_zero(self):
        w2 = W2(
            employer="Acme Corp",
            wages=50000.00,
            federal_tax_withheld=5000.00,
            ss_wages=50000.00,
            ss_tax_withheld=3100.00,
            medicare_wages=50000.00,
            medicare_tax_withheld=725.00,
        )
        self.assertEqual(w2.state_wages, 0.0)
        self.assertEqual(w2.state_tax_withheld, 0.0)
        self.assertEqual(w2.local_tax_withheld, 0.0)


class TestForm1099INT(unittest.TestCase):
    def test_create_1099_int(self):
        f = Form1099INT(payer="Bank of Example", interest=250.00)
        self.assertEqual(f.interest, 250.00)
        self.assertEqual(f.federal_tax_withheld, 0.0)


class TestForm1099DIV(unittest.TestCase):
    def test_create_1099_div(self):
        f = Form1099DIV(
            payer="Brokerage Inc",
            ordinary_dividends=1200.00,
            qualified_dividends=800.00,
        )
        self.assertEqual(f.ordinary_dividends, 1200.00)
        self.assertEqual(f.qualified_dividends, 800.00)


class TestForm1098(unittest.TestCase):
    def test_create_1098(self):
        f = Form1098(lender="Mortgage Co", mortgage_interest=8400.00)
        self.assertEqual(f.mortgage_interest, 8400.00)
        self.assertEqual(f.property_tax, 0.0)


class TestTaxReturnConfig(unittest.TestCase):
    def test_create_config(self):
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        self.assertEqual(config.year, 2025)
        self.assertEqual(config.filing_status, "single")

    def test_filing_status_rejects_invalid(self):
        with self.assertRaises(ValueError):
            TaxReturnConfig(
                year=2025,
                filing_status="married filing jointly",  # wrong string
                birthdate="1990-06-15",
                state="CA",
            )

    def test_filing_status_accepts_valid(self):
        for status in ["single", "married_jointly", "married_separately",
                        "head_of_household", "qualifying_widow"]:
            config = TaxReturnConfig(
                year=2025,
                filing_status=status,
                birthdate="1990-06-15",
                state="CA",
            )
            self.assertEqual(config.filing_status, status)

    def test_personal_info_fields_are_optional_and_preserve_state(self):
        blank = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-01-01",
            state="CA",
        )
        self.assertEqual(blank.first_name, "")
        self.assertEqual(blank.ssn, "")
        self.assertEqual(blank.address_state, "")

        populated = TaxReturnConfig(
            year=2025,
            filing_status="married_jointly",
            birthdate="1985-03-20",
            state="TX",
            first_name="Jane",
            last_name="Doe",
            ssn="000-12-3456",
            spouse_first_name="John",
            spouse_last_name="Doe",
            spouse_ssn="000-98-7654",
            address="123 Main St",
            address_city="Austin",
            address_state="TX",
            address_zip="78701",
        )
        self.assertEqual(populated.state, "TX")

    def test_existing_fixtures_still_load(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertEqual(scenario.config.year, 2025)
        self.assertEqual(scenario.config.first_name, "")
        self.assertEqual(scenario.config.address_state, "")


class TestRentalProperty(unittest.TestCase):
    def test_create_rental_property(self):
        prop = RentalProperty(
            address="42 Test Blvd, Faketown TX 99999",
            property_type=2,
            fair_rental_days=350,
            personal_use_days=15,
            rents_received=24000,
            auto_and_travel=800,
            cleaning_and_maintenance=550,
            insurance=1600,
            legal_and_professional_fees=300,
            mortgage_interest=7500,
            repairs=950,
            supplies=350,
            taxes=8500,
            depreciation=5500,
        )
        self.assertEqual(prop.rents_received, 24000)
        self.assertEqual(prop.auto_and_travel, 800)
        self.assertEqual(prop.depreciation, 5500)
        self.assertEqual(prop.property_type, 2)
        self.assertEqual(prop.address, "42 Test Blvd, Faketown TX 99999")

    def test_optional_expense_fields_default_to_zero(self):
        prop = RentalProperty(
            address="456 Test Ave",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
            rents_received=24000,
        )
        self.assertEqual(prop.advertising, 0.0)
        self.assertEqual(prop.auto_and_travel, 0.0)
        self.assertEqual(prop.cleaning_and_maintenance, 0.0)
        self.assertEqual(prop.commissions, 0.0)
        self.assertEqual(prop.insurance, 0.0)
        self.assertEqual(prop.legal_and_professional_fees, 0.0)
        self.assertEqual(prop.management_fees, 0.0)
        self.assertEqual(prop.mortgage_interest, 0.0)
        self.assertEqual(prop.other_interest, 0.0)
        self.assertEqual(prop.repairs, 0.0)
        self.assertEqual(prop.supplies, 0.0)
        self.assertEqual(prop.taxes, 0.0)
        self.assertEqual(prop.utilities, 0.0)
        self.assertEqual(prop.depreciation, 0.0)
        self.assertEqual(prop.other_expenses, 0.0)

    def test_property_type_code_stringifies_int(self):
        rp = RentalProperty(
            address="123 Main",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
            rents_received=24000.0,
        )
        self.assertEqual(rp.property_type_code, "1")

    def test_property_type_code_handles_all_codes_1_through_8(self):
        for code in range(1, 9):
            with self.subTest(code=code):
                rp = RentalProperty(
                    address=f"Prop {code}",
                    property_type=code,
                    fair_rental_days=365,
                    personal_use_days=0,
                    rents_received=0.0,
                )
                self.assertEqual(rp.property_type_code, str(code))

    def test_scenario_has_rental_properties(self):
        config = TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1990-06-15", state="CA",
        )
        prop = RentalProperty(
            address="123 Example St",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
            rents_received=24000,
        )
        scenario = Scenario(config=config, rental_properties=[prop])
        self.assertEqual(len(scenario.rental_properties), 1)


class TestScenario(unittest.TestCase):
    def test_create_scenario(self):
        w2 = W2(
            employer="Acme",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        scenario = Scenario(config=config, w2s=[w2])
        self.assertEqual(len(scenario.w2s), 1)
        self.assertEqual(scenario.config.year, 2025)
        self.assertEqual(scenario.form1099_int, [])


class TestForm1099B(unittest.TestCase):
    def test_defaults_basis_reported_true_and_no_adjustments(self):
        lot = Form1099B(
            broker="Broker A",
            description="100 ACME",
            date_acquired="2024-01-02",
            date_sold="2025-06-10",
            proceeds=1500.0,
            cost_basis=1000.0,
        )
        self.assertTrue(lot.basis_reported_to_irs)
        self.assertFalse(lot.has_adjustments)
        self.assertTrue(lot.short_term)  # existing default preserved

    def test_accepts_explicit_reporting_flags(self):
        lot = Form1099B(
            broker="Broker A",
            description="100 ACME",
            date_acquired="2020-01-02",
            date_sold="2025-06-10",
            proceeds=5000.0,
            cost_basis=1000.0,
            short_term=False,
            basis_reported_to_irs=False,
            wash_sale_loss_disallowed=50.0,
        )
        self.assertFalse(lot.short_term)
        self.assertFalse(lot.basis_reported_to_irs)
        self.assertTrue(lot.has_adjustments)

    def test_yaml_roundtrip_with_new_flags(self):
        doc = {
            "config": {
                "year": 2025,
                "filing_status": "single",
                "birthdate": "1990-01-01",
                "state": "CA",
                "has_foreign_accounts": False,
                "acknowledges_form_8949_unsupported": False,
                "acknowledges_sch_a_sales_tax_unsupported": False,
                "acknowledges_qbi_below_threshold": False,
                "acknowledges_unlimited_at_risk": False,
                "basis_tracked_externally": False,
                "acknowledges_no_partnership_se_earnings": False,
                "acknowledges_no_section_1231_gain": False,
                "acknowledges_no_more_than_four_k1s": False,
                "acknowledges_no_k1_credits": False,
                "acknowledges_no_section_179": False,
                "acknowledges_no_estate_trust_k1": False,
                "prior_year_itemized": False,
            },
            "form1099_b": [
                {
                    "broker": "Broker A",
                    "description": "100 XYZ",
                    "date_acquired": "2024-03-01",
                    "date_sold": "2025-05-10",
                    "proceeds": 2500.0,
                    "cost_basis": 2000.0,
                    "short_term": False,
                    "basis_reported_to_irs": False,
                    "wash_sale_loss_disallowed": 50.0,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.yaml"
            p.write_text(yaml.safe_dump(doc))
            s = load_scenario(p)
        self.assertEqual(len(s.form1099_b), 1)
        lot = s.form1099_b[0]
        self.assertFalse(lot.basis_reported_to_irs)
        self.assertTrue(lot.has_adjustments)
        self.assertFalse(lot.short_term)


class DepreciableAssetTests(unittest.TestCase):
    def test_minimum_fields(self):
        a = DepreciableAsset(
            description="Rental building - Evans Ave",
            date_placed_in_service=date(2019, 6, 1),
            basis=250_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        )
        self.assertEqual(a.description, "Rental building - Evans Ave")
        self.assertEqual(a.date_placed_in_service, date(2019, 6, 1))
        self.assertEqual(a.basis, 250_000.0)
        self.assertEqual(a.recovery_class, "27.5-year")
        self.assertEqual(a.convention, "mid-month")
        self.assertIsNone(a.disposed)

    def test_accepts_disposed_date(self):
        a = DepreciableAsset(
            description="Laptop",
            date_placed_in_service=date(2023, 1, 10),
            basis=2_000.0,
            recovery_class="5-year",
            convention="half-year",
            disposed=date(2025, 8, 14),
        )
        self.assertEqual(a.disposed, date(2025, 8, 14))


class ScenarioDepreciableAssetsTests(unittest.TestCase):
    def test_defaults_empty(self):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025,
                filing_status=FilingStatus.SINGLE,
                birthdate="1980-01-01",
                state="CA",
                has_foreign_accounts=False,
                acknowledges_form_8949_unsupported=False,
            ),
        )
        self.assertEqual(scenario.depreciable_assets, [])

    def test_load_scenario_parses_depreciable_assets(self):
        s = load_scenario(FIXTURES_DIR / "rental_with_depreciation.yaml")
        self.assertEqual(len(s.depreciable_assets), 1)
        a = s.depreciable_assets[0]
        self.assertEqual(a.description, "Rental building")
        self.assertEqual(a.basis, 250_000.0)
        self.assertEqual(a.recovery_class, "27.5-year")


class TestEntityType(unittest.TestCase):
    def test_values_match_plan_d_string_literal(self) -> None:
        """The three entity types accepted by ScheduleK1 today."""
        from tenforty.models import EntityType
        self.assertEqual(EntityType.S_CORP.value, "s_corp")
        self.assertEqual(EntityType.PARTNERSHIP.value, "partnership")
        self.assertEqual(EntityType.ESTATE_TRUST.value, "estate_trust")

    def test_is_str_subclass(self) -> None:
        """str-Enum for YAML-loader friendliness (YAML yields strings)."""
        from tenforty.models import EntityType
        self.assertIsInstance(EntityType.S_CORP, str)
        self.assertEqual(EntityType("s_corp"), EntityType.S_CORP)


class TestAccountingMethod(unittest.TestCase):
    def test_values(self) -> None:
        from tenforty.models import AccountingMethod
        self.assertEqual(AccountingMethod.CASH.value, "cash")
        self.assertEqual(AccountingMethod.ACCRUAL.value, "accrual")
        self.assertEqual(AccountingMethod.OTHER.value, "other")

    def test_is_str_subclass(self) -> None:
        from tenforty.models import AccountingMethod
        self.assertIsInstance(AccountingMethod.CASH, str)


class TestPayerAmount(unittest.TestCase):
    def test_fields(self) -> None:
        from tenforty.models import PayerAmount
        pa = PayerAmount(payer="Fake S-Corp Inc", amount=150.0)
        self.assertEqual(pa.payer, "Fake S-Corp Inc")
        self.assertEqual(pa.amount, 150.0)

    def test_frozen(self) -> None:
        from tenforty.models import PayerAmount
        pa = PayerAmount(payer="X", amount=1.0)
        with self.assertRaises(Exception):
            pa.amount = 2.0  # type: ignore[misc]


class TestK1FanoutActivity(unittest.TestCase):
    def test_fields(self) -> None:
        from tenforty.models import EntityType, K1FanoutActivity
        a = K1FanoutActivity(
            entity_name="Fake S-Corp Inc",
            entity_ein="00-0000000",
            entity_type=EntityType.S_CORP,
            income=500.0,
            loss=0.0,
            prior_carryforward=200.0,
        )
        self.assertEqual(a.entity_name, "Fake S-Corp Inc")
        self.assertEqual(a.entity_type, EntityType.S_CORP)
        self.assertEqual(a.income, 500.0)
        self.assertEqual(a.loss, 0.0)
        self.assertEqual(a.prior_carryforward, 200.0)

    def test_magnitudes_are_positive(self) -> None:
        """income/loss/prior_carryforward are all positive magnitudes by
        convention — loss being nonzero is itself the direction signal."""
        from tenforty.models import EntityType, K1FanoutActivity
        a = K1FanoutActivity(
            entity_name="X", entity_ein="00-0000000",
            entity_type=EntityType.PARTNERSHIP,
            income=0.0, loss=800.0, prior_carryforward=0.0,
        )
        self.assertGreaterEqual(a.loss, 0.0)
        self.assertGreaterEqual(a.prior_carryforward, 0.0)


class TestK1FanoutData(unittest.TestCase):
    def test_empty_constructor(self) -> None:
        from tenforty.models import K1FanoutData
        empty = K1FanoutData.empty()
        self.assertEqual(empty.sch_b_interest_additions, ())
        self.assertEqual(empty.sch_b_dividend_additions, ())
        self.assertEqual(empty.sch_d_short_term_additions, ())
        self.assertEqual(empty.sch_d_long_term_additions, ())
        self.assertEqual(empty.qbi_aggregate, 0.0)
        self.assertEqual(empty.qualified_dividends_aggregate, 0.0)
        self.assertEqual(empty.passive_activities, ())

    def test_construct_with_activities(self) -> None:
        from tenforty.models import (
            EntityType, K1FanoutActivity, K1FanoutData, PayerAmount,
        )
        fanout = K1FanoutData(
            sch_b_interest_additions=(PayerAmount(payer="X", amount=50.0),),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(100.0,),
            sch_d_long_term_additions=(),
            qbi_aggregate=1000.0,
            qualified_dividends_aggregate=0.0,
            passive_activities=(
                K1FanoutActivity(
                    entity_name="A", entity_ein="00-0000000",
                    entity_type=EntityType.PARTNERSHIP,
                    income=0.0, loss=500.0, prior_carryforward=0.0,
                ),
            ),
        )
        self.assertEqual(len(fanout.passive_activities), 1)
        self.assertEqual(fanout.sch_b_interest_additions[0].payer, "X")


class TestVoluntaryContribution(unittest.TestCase):
    def test_fields(self) -> None:
        from tenforty.models import VoluntaryContribution
        vc = VoluntaryContribution(fund_code="WLD", amount=10.0)
        self.assertEqual(vc.fund_code, "WLD")
        self.assertEqual(vc.amount, 10.0)

    def test_frozen(self) -> None:
        from tenforty.models import VoluntaryContribution
        vc = VoluntaryContribution(fund_code="WLD", amount=10.0)
        with self.assertRaises(Exception):  # FrozenInstanceError
            vc.amount = 20.0  # type: ignore[misc]


class TestTaxReturnConfigFullName(unittest.TestCase):
    def _config(self, **kw) -> "TaxReturnConfig":
        from tenforty.models import TaxReturnConfig
        defaults = dict(
            year=2025, filing_status="single", birthdate="1990-06-15", state="CA",
            has_foreign_accounts=False, acknowledges_form_8949_unsupported=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=False, basis_tracked_externally=False,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=False,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=False,
            prior_year_itemized=False,
        )
        defaults.update(kw)
        return TaxReturnConfig(**defaults)

    def test_concatenates_first_last(self) -> None:
        cfg = self._config(first_name="Taxpayer", last_name="A")
        self.assertEqual(cfg.full_name, "Taxpayer A")

    def test_strips_whitespace(self) -> None:
        cfg = self._config(first_name="  Taxpayer  ", last_name=" A ")
        self.assertEqual(cfg.full_name, "Taxpayer A")

    def test_both_empty_gives_empty_string(self) -> None:
        cfg = self._config()
        self.assertEqual(cfg.full_name, "")

    def test_only_first(self) -> None:
        cfg = self._config(first_name="Taxpayer")
        self.assertEqual(cfg.full_name, "Taxpayer")


class TestScheduleK1EntityTypeEnum(unittest.TestCase):
    def test_construct_with_enum_member(self) -> None:
        from tenforty.models import EntityType, ScheduleK1
        k1 = ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type=EntityType.S_CORP, material_participation=True,
        )
        self.assertIs(k1.entity_type, EntityType.S_CORP)

    def test_construct_with_string_coerces_to_enum(self) -> None:
        """YAML loader passes strings; dataclass coerces in __post_init__."""
        from tenforty.models import EntityType, ScheduleK1
        k1 = ScheduleK1(
            entity_name="X", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
        )
        self.assertIs(k1.entity_type, EntityType.PARTNERSHIP)

    def test_invalid_string_raises(self) -> None:
        """Mis-routed entity_type fails at construction, not silently."""
        from tenforty.models import ScheduleK1
        with self.assertRaises(ValueError):
            ScheduleK1(
                entity_name="X", entity_ein="00-0000000",
                entity_type="c_corp", material_participation=True,
            )


class TestForm1099BAdjustments(unittest.TestCase):
    def test_default_no_adjustments(self) -> None:
        lot = Form1099B(
            broker="Brokerage Inc", description="10 sh X",
            date_acquired="2024-01-15", date_sold="2025-03-20",
            proceeds=1000.0, cost_basis=800.0,
        )
        self.assertEqual(lot.wash_sale_loss_disallowed, 0.0)
        self.assertEqual(lot.other_basis_adjustment, 0.0)
        self.assertFalse(lot.is_28_rate_collectible)
        self.assertFalse(lot.is_section_1250)
        self.assertFalse(lot.has_adjustments)

    def test_wash_sale_is_adjustment(self) -> None:
        lot = Form1099B(
            broker="Brokerage Inc", description="10 sh X",
            date_acquired="2024-01-15", date_sold="2025-03-20",
            proceeds=1000.0, cost_basis=1200.0,
            wash_sale_loss_disallowed=50.0,
        )
        self.assertTrue(lot.has_adjustments)

    def test_other_basis_adjustment_is_adjustment(self) -> None:
        lot = Form1099B(
            broker="Brokerage Inc", description="X",
            date_acquired="2024-01-15", date_sold="2025-03-20",
            proceeds=1000.0, cost_basis=800.0,
            other_basis_adjustment=-50.0,
        )
        self.assertTrue(lot.has_adjustments)

    def test_28_rate_flag_is_adjustment(self) -> None:
        lot = Form1099B(
            broker="Brokerage Inc", description="coin",
            date_acquired="2020-01-15", date_sold="2025-03-20",
            proceeds=5000.0, cost_basis=1000.0,
            short_term=False, is_28_rate_collectible=True,
        )
        self.assertTrue(lot.has_adjustments)

    def test_section_1250_flag_is_adjustment(self) -> None:
        lot = Form1099B(
            broker="Brokerage Inc", description="REIT",
            date_acquired="2020-01-15", date_sold="2025-03-20",
            proceeds=5000.0, cost_basis=3000.0,
            short_term=False, is_section_1250=True,
        )
        self.assertTrue(lot.has_adjustments)

    def test_adjustment_fields_tuple_covers_all(self) -> None:
        """The module-level _LOT_ADJUSTMENT_FIELDS tuple is the single source
        of truth for 'what counts as an adjustment'. has_adjustments iterates
        it; attestation compute-time gates iterate it; fixture verifiers
        iterate it. Shared-field-tuple discipline."""
        self.assertEqual(
            set(_LOT_ADJUSTMENT_FIELDS),
            {"wash_sale_loss_disallowed", "other_basis_adjustment",
             "is_28_rate_collectible", "is_section_1250"},
        )
