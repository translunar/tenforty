"""Self-employed health-insurance deduction (Schedule 1 line 17) input channel.

v1 is an INPUT channel: the filer's stated SE-health-insurance deduction is
carried through verbatim to Schedule 1 line 17 — reducing total adjustments
(line 26), AGI, and taxable income — or refused if negative. No §162(l) limit
math (premium caps / S-corp >2%-shareholder rules) is modeled here; that is the
CPA's domain and out of scope.

Mirrors the estimated-tax-payments and non-itemizer-charitable channels.
"""

import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.forms import sch_1 as form_sch_1
from tenforty.forms.f1040_spine import compute_spine
from tenforty.forms.sch_ca import compute as sch_ca_compute
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.models import CA540Return, Form1095A, Form1095AMonth, Scenario
from tenforty.params.federal import load
from tenforty.scenario import load_scenario
from tests.helpers import REPO_ROOT, make_simple_scenario, scope_out_attestation_defaults

# Clearly synthetic deduction value — NOT Juno's real figure, nor near it.
_V = 7_400


class SeHealthComputeFlowTests(unittest.TestCase):
    """The field flows Schedule 1 line 17 → line 26 → AGI → taxable income.

    Delta test: computing the SAME scenario with the field unset (0) vs set to
    V must move line 17 to V, raise line 26 by V, and LOWER both AGI and
    taxable income by exactly V. Before the sch_1 hardcode is replaced with a
    read of the field, line 17 stays 0 and neither AGI nor taxable income moves
    — so this fails RED for the right reason."""

    def _agi_and_taxable(self, se_health_value):
        params = load(2025)
        scenario = make_simple_scenario()
        scenario.config.self_employed_health_insurance_deduction = se_health_value
        sch_1_out = form_sch_1.compute(scenario, upstream={})
        schedule_results = {
            "sch_1": sch_1_out,
            "sch_a": {"sch_a_line_17_total": 0},
        }
        spine = compute_spine(scenario, params, schedule_results)
        return sch_1_out, spine

    def test_deduction_reduces_agi_and_taxable_income_by_exactly_V(self):
        sch_1_zero, spine_zero = self._agi_and_taxable(0.0)
        sch_1_v, spine_v = self._agi_and_taxable(_V)

        # Precondition: the unset case genuinely carries 0 (so the delta below
        # is attributable to V, not to a nonzero baseline).
        self.assertEqual(sch_1_zero["sch_1_line_17_se_health"], 0)

        # Line 17 carries the input verbatim.
        self.assertEqual(sch_1_v["sch_1_line_17_se_health"], _V)

        # Line 26 total adjustments rises by exactly V.
        self.assertEqual(
            sch_1_v["sch_1_line_26_total_adjustments"],
            sch_1_zero["sch_1_line_26_total_adjustments"] + _V,
        )

        # AGI falls by exactly V (line 26 is subtracted from total income).
        self.assertEqual(spine_v["agi"], spine_zero["agi"] - _V)

        # Taxable income falls by exactly V — chosen scenario keeps it well
        # above 0 so no flooring masks the delta.
        self.assertGreater(spine_v["taxable_income"], 0)
        self.assertEqual(
            spine_v["taxable_income"], spine_zero["taxable_income"] - _V
        )


class SeHealthValidationTests(unittest.TestCase):
    """A negative self_employed_health_insurance_deduction is REFUSED at load
    (carried through verbatim, never silently clamped to 0). Mirrors the
    estimated-tax-payments negative-refusal test."""

    def _make_config_body(self, **overrides) -> dict:
        body = {
            "year": 2025,
            "filing_status": "single",
            "birthdate": "1985-04-20",
            "state": "CA",
            "has_foreign_accounts": False,
            "prior_year_itemized": False,
            **scope_out_attestation_defaults(),
        }
        body.update(overrides)
        return body

    def _load_with_config(self, config_body: dict) -> Scenario:
        body = {"config": config_body}
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        return load_scenario(path)

    def test_value_accepted_verbatim(self) -> None:
        scenario = self._load_with_config(
            self._make_config_body(self_employed_health_insurance_deduction=_V)
        )
        self.assertEqual(
            scenario.config.self_employed_health_insurance_deduction, _V
        )

    def test_defaults_to_zero_when_omitted(self) -> None:
        scenario = self._load_with_config(self._make_config_body())
        self.assertEqual(
            scenario.config.self_employed_health_insurance_deduction, 0.0
        )

    def test_negative_value_refused(self) -> None:
        with self.assertRaises(ValueError):
            self._load_with_config(
                self._make_config_body(
                    self_employed_health_insurance_deduction=-1.0
                )
            )


class SeHealthCaPassthroughTests(unittest.TestCase):
    """End-to-end: a CA scenario with the SE-health field set flows the value
    through the federal spine into Schedule CA (540) Part I §C line 17 Column A
    (the federal-amount column), and — with no CA divergence — lowers CA AGI by
    the same amount the federal deduction lowered federal AGI.

    Before the sch_1 read is wired, the federal deduction is 0, so the §C 17
    Col-A key is never emitted (kernel emits Col-A only for truthy federal
    amounts) — the key's absence is the RED signal."""

    def _federal_results(self, se_health_value):
        params = load(2025)
        scenario = make_simple_scenario()  # state defaults to CA
        scenario.config.self_employed_health_insurance_deduction = se_health_value
        sch_1_out = form_sch_1.compute(scenario, upstream={})
        schedule_results = {
            "sch_1": sch_1_out,
            "sch_a": {"sch_a_line_17_total": 0},
        }
        return compute_spine(scenario, params, schedule_results)

    def test_value_lands_in_sch_ca_part_i_c_17_col_a(self):
        federal_v = self._federal_results(_V)
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results=federal_v,
            year=2025,
        )
        self.assertEqual(result["sch_ca_line_part_i_c_17_col_a"], _V)

    def test_ca_agi_lowered_by_the_deduction(self):
        federal_zero = self._federal_results(0.0)
        federal_v = self._federal_results(_V)
        ca_zero = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results=federal_zero,
            year=2025,
        )
        ca_v = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results=federal_v,
            year=2025,
        )
        # No CA divergence, so CA AGI tracks federal AGI, which the deduction
        # lowered by exactly V.
        self.assertEqual(ca_v["sch_ca_ca_agi"], ca_zero["sch_ca_ca_agi"] - _V)


class SeHealthPdfEmitRoundTripTests(unittest.TestCase):
    """Per-year Schedule 1 PDF emit round-trip (2021-2025): the SE-health value
    fills line 17's field and reads back at f2_07[0] on page 2 in every year.
    Fills the real template with PdfFiller and reads back with pypdf — NO
    soffice. The f2_07[0] widget is verified per year rather than trusted."""

    def _template(self, year: int) -> Path:
        return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040s1.pdf"

    def test_line_17_round_trips_per_year(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                template = self._template(year)
                self.assertTrue(
                    template.exists(), f"missing template for {year}"
                )
                scalars = PdfSch1.get_mapping(year)["scalars"]
                field_path = scalars["sch_1_line_17_se_health"]
                # Verify the mapped widget really is the line-17 field f2_07[0]
                # on page 2 for this year (root namespace differs by year).
                self.assertTrue(
                    field_path.endswith("f2_07[0]"),
                    f"{year}: line-17 field {field_path!r} is not f2_07[0]",
                )
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / f"f1040s1_{year}.pdf"
                    PdfFiller().fill(
                        template_path=template,
                        output_path=out,
                        field_mapping=scalars,
                        values={"sch_1_line_17_se_health": _V},
                    )
                    fields = PdfReader(str(out)).get_fields() or {}
                    read_back = fields.get(field_path)
                    self.assertIsNotNone(
                        read_back, f"{year}: field {field_path} not found"
                    )
                    self.assertEqual(
                        read_back.get("/V"), str(_V),
                        f"{year}: line 17 did not round-trip",
                    )


class SeHealthPtcGuardTests(unittest.TestCase):
    """The SE-health × PTC refusal at f1040_spine.py became REACHABLE once the
    Task-1 input channel let Schedule 1 line 17 go nonzero. When a nonzero
    SE-health deduction and a Form 1095-A are BOTH present, the Premium Tax
    Credit and the deduction are circularly dependent (Rev. Proc. 2014-41) and
    that reconciliation is unmodeled, so the spine must fail closed.

    Line 17 is driven nonzero VIA THE REAL CHANNEL — `sch_1.compute` reads
    `scenario.config.self_employed_health_insurance_deduction`, then
    `compute_spine` consumes its output — so these prove the channel reaches the
    guard, not that a hand-fed dict trips it. A/B/C pin the guard to EXACTLY its
    two-condition trigger:
      A  V + 1095-A            -> RAISES (fails if the guard is removed)
      B  V + no 1095-A         -> flows  (fails if the guard over-fires)
      C  0 + 1095-A            -> flows  (fails if the guard fires on 1095-A alone)
    """

    @staticmethod
    def _empty_1095a() -> Form1095A:
        # The guard tests `scenario.form_1095a is not None`, so the month
        # figures are immaterial; a zero-filled 12-month form is a valid,
        # PRESENT 1095-A.
        return Form1095A(months=tuple(Form1095AMonth() for _ in range(12)))

    def _compute(self, se_health_value, *, with_1095a):
        """Drive the real native-spine channel: sch_1.compute -> compute_spine.

        Returns (sch_1_out, spine) so callers can confirm line 17's value came
        from the channel. Raises out of compute_spine when the guard fires.
        """
        params = load(2025)
        scenario = make_simple_scenario()  # single filer, no 1095-A by default
        scenario.config.self_employed_health_insurance_deduction = se_health_value
        if with_1095a:
            scenario.form_1095a = self._empty_1095a()
        sch_1_out = form_sch_1.compute(scenario, upstream={})
        schedule_results = {
            "sch_1": sch_1_out,
            "sch_a": {"sch_a_line_17_total": 0},
        }
        spine = compute_spine(scenario, params, schedule_results)
        return sch_1_out, spine

    def test_A_guard_fires_via_real_channel(self):
        """V + a Form 1095-A present -> NotImplementedError.

        Falsifiable: delete the guard and compute returns normally, so this
        assertRaises fails. The regex pins the Rev-Proc citation so a reworded
        raise cannot silently pass."""
        params = load(2025)
        scenario = make_simple_scenario()
        scenario.config.self_employed_health_insurance_deduction = _V
        scenario.form_1095a = self._empty_1095a()
        # Line 17 is genuinely nonzero coming OUT of the channel, not hand-fed.
        sch_1_out = form_sch_1.compute(scenario, upstream={})
        self.assertEqual(sch_1_out["sch_1_line_17_se_health"], _V)
        schedule_results = {
            "sch_1": sch_1_out,
            "sch_a": {"sch_a_line_17_total": 0},
        }
        with self.assertRaisesRegex(NotImplementedError, r"2014-41"):
            compute_spine(scenario, params, schedule_results)

    def test_B_guard_does_not_over_fire_without_1095a(self):
        """V but NO Form 1095-A -> no raise, and the deduction flows (AGI down
        by exactly V). Falsifiable: an over-firing guard (one that dropped the
        `scenario.form_1095a is not None` condition) would raise here."""
        sch_1_zero, spine_zero = self._compute(0.0, with_1095a=False)
        sch_1_v, spine_v = self._compute(_V, with_1095a=False)

        # The field really moved line 17 through the channel.
        self.assertEqual(sch_1_zero["sch_1_line_17_se_health"], 0)
        self.assertEqual(sch_1_v["sch_1_line_17_se_health"], _V)
        # The common case (and Juno's motivating no-1095-A case) is not blocked;
        # the deduction lowers AGI by exactly V.
        self.assertEqual(spine_v["agi"], spine_zero["agi"] - _V)

    def test_C_guard_does_not_fire_on_1095a_alone(self):
        """Line 17 = 0 WITH a Form 1095-A present -> no raise. Falsifiable: a
        guard that fired on the 1095-A alone (dropping the nonzero-line-17
        condition) would raise here. Confirms the refusal needs BOTH conditions."""
        sch_1_out, spine = self._compute(0.0, with_1095a=True)
        # Precondition: line 17 is genuinely 0 through the channel, and a 1095-A
        # is present — the exact shape that must NOT trip the guard.
        self.assertEqual(sch_1_out["sch_1_line_17_se_health"], 0)
        self.assertIsNotNone(spine)


if __name__ == "__main__":
    unittest.main()
