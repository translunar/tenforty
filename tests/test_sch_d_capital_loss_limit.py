"""Schedule D line 21 (IRC §1211(b) cap) and the §1212(b) ST/LT-split
capital loss carryforward.

Every expected value in this file is hand-derived (see the module-level
comment blocks per test class) from either the statute/Schedule D
instructions directly, or from the IRS "Capital Loss Carryover
Worksheet—Lines 6 and 14" (Schedule D instructions) fetched and
transcribed verbatim during development:
https://apps.irs.gov/app/vita/content/globalmedia/capital_loss_carryover_worksheet.pdf

None of the expected values are read back from tenforty's own
implementation.
"""

import unittest

from tenforty.forms import sch_d
from tenforty.models import K1FanoutData, Scenario, TaxReturnConfig
from tenforty.params.federal import load as load_federal_params
from tests.helpers import scope_out_attestation_defaults


def _config(filing_status: str = "single", **overrides) -> TaxReturnConfig:
    kw = scope_out_attestation_defaults()
    kw.update(overrides)
    return TaxReturnConfig(
        year=2025, filing_status=filing_status,
        birthdate="1985-04-20", state="CA",
        first_name="Taxpayer", last_name="A", ssn="000-00-0000",
        **kw,
    )


def _fanout(short: float = 0.0, long: float = 0.0) -> K1FanoutData:
    """A K-1 fanout is the simplest way to put an exact, arbitrary-signed
    figure onto Sch D line 7 (short) / line 15 (long) without constructing
    1099-B lots with specific dates/wash-sale mechanics — sch_d.compute
    sums these tuples directly onto line_7 / line_15 (see sch_d.py's
    k1_short / k1_long)."""
    return K1FanoutData(
        sch_b_interest_additions=(),
        sch_b_dividend_additions=(),
        sch_d_short_term_additions=(short,),
        sch_d_long_term_additions=(long,),
        qbi_aggregate=0.0,
        qualified_dividends_aggregate=0.0,
        passive_activities=(),
    )


def _compute(short: float, long: float, filing_status: str = "single",
             **kwargs) -> dict:
    scen = Scenario(config=_config(filing_status))
    return sch_d.compute(
        scen, upstream={"k1_fanout": _fanout(short, long)}, **kwargs
    )


# A comfortably-positive unfloored taxable income. Any return with a
# CAPPED loss must supply this — the guard is fail-closed on omission —
# and a non-negative value is exactly the regime in which the flat-cap
# substitution reproduces the IRS worksheet's own line 4 exactly, so it
# is the correct figure for the pure-arithmetic split tests below.
_POSITIVE_TI = 120_000.0


def _cap(filing_status: str = "single") -> int:
    # Per Step 1: read the cap from params, never hardcode 3000/1500 as
    # a test INPUT.
    return load_federal_params(2025).capital_loss_limit[filing_status]


class TestLine21Cap(unittest.TestCase):
    """Sch D line 21: "If line 16 is a loss, enter here ... the SMALLER of
    (a) that loss, or (b) $3,000 ($1,500 MFS)." Smaller in MAGNITUDE."""

    def test_net_gain_passes_through_untouched(self):
        # line_16 = 10,000 (gain) -- line 21 not used on the return; the
        # cap must never touch a gain.
        out = _compute(short=4_000, long=6_000)
        self.assertEqual(out["sch_d_line_16_total"], 10_000)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], 10_000)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_loss_smaller_than_cap_fully_allowed(self):
        # -1,200 loss, single ($3,000 cap): the whole loss is smaller in
        # magnitude than the cap, so line 21 == the loss itself, no
        # carryforward.
        out = _compute(short=-1_200, long=0)
        self.assertEqual(out["sch_d_line_16_total"], -1_200)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -1_200)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_loss_exactly_at_cap_boundary(self):
        # -3,000 loss, single: magnitude EQUALS the cap. The full loss is
        # still allowed (line 21 == -3,000, not more-negative than the
        # loss), and there is no excess to carry forward.
        cap = _cap("single")
        out = _compute(short=-cap, long=0)
        self.assertEqual(out["sch_d_line_16_total"], -cap)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -cap)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_loss_larger_than_cap_single(self):
        # -50,000 loss, single, all short-term. Smaller-in-magnitude of
        # 50,000 and 3,000 is 3,000, so line 21 == -3,000 (NOT -50,000 --
        # this is the sign-convention trap: max(-50000, -3000) == -3000).
        cap = _cap("single")
        out = _compute(short=-50_000, long=0,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_line_16_total"], -50_000)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -cap)
        self.assertEqual(
            out["sch_d_st_capital_loss_carryforward"], -(50_000 - cap)
        )
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_mfs_filing_status_branch(self):
        # -5,000 loss, MFS ($1,500 cap, half the single/MFJ figure).
        cap = _cap("married_separately")
        self.assertEqual(cap, 1_500)
        out = _compute(short=-5_000, long=0,
                       filing_status="married_separately",
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_line_16_total"], -5_000)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -cap)
        self.assertEqual(
            out["sch_d_st_capital_loss_carryforward"], -(5_000 - cap)
        )
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)


class TestSplitCarryforwardFiveShapes(unittest.TestCase):
    """The ST/LT split, hand-derived by reproducing lines 5-13 of the IRS
    Capital Loss Carryover Worksheet (naive: substituting this year's flat
    cap for the worksheet's own income-adjusted line 4 -- see sch_d.py's
    comment block for why that substitution is exact when taxable income
    is non-negative, which every case in this class assumes).

    Worksheet mechanics, restated: allowed_magnitude = |line 21| = 3,000
    (single, every case here). The amount of ST loss treated as "used"
    this year is allowed_magnitude PLUS any LT GAIN -- a same-year LT gain
    had to be netted against the ST loss to produce the overall line 16
    result, so it reduces what's left to carry forward even though it
    isn't itself part of the flat dollar cap. ST absorbs first; only the
    leftover allowance (after fully covering the ST loss) spills to
    reduce the LT loss. Symmetric on the LT side (LT absorbs first when
    line 15 is the loss and line 7 is flat/gain).

    Every case cross-checks the invariant demanded by the brief:
    st_carryforward + lt_carryforward == line_16 - line_21.
    """

    def _assert_invariant(self, out: dict) -> None:
        self.assertEqual(
            out["sch_d_st_capital_loss_carryforward"]
            + out["sch_d_lt_capital_loss_carryforward"],
            out["sch_d_line_16_total"] - out["sch_d_line_21_allowed_loss"],
        )

    def test_shape_1_st_loss_only(self):
        # ST -50,000, LT 0. cap 3,000. line_16 -50,000, line_21 -3,000.
        # Allowed 3,000 fully absorbed by the ST loss (nothing to spill to
        # LT, which has no loss anyway). ST carryforward = -(50,000-3,000)
        # = -47,000; LT carryforward = 0.
        out = _compute(short=-50_000, long=0,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], -47_000)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)
        self._assert_invariant(out)

    def test_shape_2_lt_loss_only(self):
        # LT -50,000, ST 0. Symmetric to shape 1: LT carryforward =
        # -47,000, ST carryforward = 0.
        out = _compute(short=0, long=-50_000,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], -47_000)
        self._assert_invariant(out)

    def test_shape_3_both_losses_st_absorbs_full_allowance(self):
        # ST -10,000, LT -40,000. The $3,000 allowance is smaller than the
        # ST loss alone, so it is absorbed ENTIRELY by ST (worksheet's
        # "ST first" rule) and never spills to LT. ST carryforward =
        # -(10,000-3,000) = -7,000. LT carryforward = its FULL -40,000,
        # untouched by the allowance.
        out = _compute(short=-10_000, long=-40_000,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], -7_000)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], -40_000)
        self._assert_invariant(out)

    def test_shape_3b_both_losses_allowance_spills_to_lt(self):
        # ST -1,000, LT -49,000. The ST loss (1,000) is smaller than the
        # $3,000 allowance, so it is FULLY absorbed (ST carryforward = 0)
        # and the remaining 2,000 of allowance spills to reduce LT. LT
        # carryforward = -(49,000 - 2,000) = -47,000.
        out = _compute(short=-1_000, long=-49_000,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], -47_000)
        self._assert_invariant(out)

    def test_shape_4_st_gain_lt_loss_nets_to_loss(self):
        # ST +5,000 (gain), LT -20,000 (loss). line_16 = -15,000, line_21
        # = -3,000 (loss exceeds cap). ST is a GAIN so it carries forward
        # NOTHING (a gain isn't a loss; it's already taxed this year) --
        # ST carryforward = 0. The entire disallowed amount (-12,000) must
        # therefore come from LT: of the 20,000 LT loss, 5,000 was
        # absorbed netting against the ST gain (to produce line_16) and
        # 3,000 more was absorbed by the annual allowance, leaving
        # 20,000 - 5,000 - 3,000 = 12,000 LT carryforward.
        out = _compute(short=5_000, long=-20_000,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_line_16_total"], -15_000)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -3_000)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], -12_000)
        self._assert_invariant(out)

    def test_shape_5_st_loss_lt_gain_nets_to_loss(self):
        # ST -20,000 (loss), LT +5,000 (gain). Mirror image of shape 4: LT
        # is a gain, already taxed, LT carryforward = 0. ST carryforward
        # absorbs everything: 20,000 - 5,000 (netted against the LT gain)
        # - 3,000 (annual allowance) = 12,000.
        out = _compute(short=-20_000, long=5_000,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_line_16_total"], -15_000)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -3_000)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], -12_000)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)
        self._assert_invariant(out)


class TestHonestyGuard(unittest.TestCase):
    """IRC §1212(b)(2): the real worksheet's line 4 is
    min(allowed_magnitude, combine(taxable_income, allowed_magnitude)),
    not the flat allowed_magnitude this module substitutes. That
    substitution is exact iff this year's UNFLOORED taxable income is
    >= 0 (verified against the IRS worksheet's own lines 1-4 during
    development: combine(0, magnitude) == magnitude, so TI == 0 is still
    exact; any TI < 0 makes line 3/4 come in smaller than the flat
    substitution, understating the true carryforward). The guard must
    therefore refuse exactly when: line_21 is a loss (ANY loss, not only
    a cap-bound one -- the worksheet's own trigger is "line 21 is a loss
    AND (loss exceeds line 16 OR taxable income < 0)", so a small,
    fully-allowed loss can still need the worksheet if taxable income is
    negative) AND taxable_income_unfloored is supplied and negative.

    The guard is FAIL-CLOSED IN BOTH DIRECTIONS: it refuses both when it
    KNOWS v1's arithmetic is wrong (income supplied and negative) and
    when it CANNOT KNOW (income not supplied at all, with a capped loss
    present). "Cannot know" must refuse as loudly as "know it's wrong",
    or the unsupplied path silently becomes the assumed-fine path.
    """

    def test_capped_loss_without_taxable_income_omits_both_keys(self):
        # FAIL-CLOSED on omission. A -50,000 loss against a 3,000 cap has
        # a real 47,000 disallowed remainder to carry forward, but with
        # no taxable-income figure there is no way to tell whether v1's
        # flat-cap arithmetic is exact for this return or understates the
        # carryforward. Emitting -47,000 anyway would rest on an
        # assumption nobody verified, so BOTH keys are omitted entirely:
        # there is no number and no sentinel for a consumer to mistake
        # for an answer, and reading either raises KeyError.
        out = _compute(short=-50_000, long=0)
        self.assertNotIn("sch_d_st_capital_loss_carryforward", out)
        self.assertNotIn("sch_d_lt_capital_loss_carryforward", out)
        with self.assertRaises(KeyError):
            out["sch_d_st_capital_loss_carryforward"]
        # The in-year allowed loss is unaffected and still correct --
        # the whole point of confining the uncertainty to the carryforward.
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -_cap("single"))
        self.assertEqual(out["sch_d_line_16_total"], -50_000)

    def test_supplying_taxable_income_restores_both_keys(self):
        # The omission above is specifically about the MISSING figure,
        # not a permanent capability gap: supply it and the same scenario
        # yields the full split.
        out = _compute(short=-50_000, long=0,
                       taxable_income_unfloored=_POSITIVE_TI)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], -47_000)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_no_raise_when_loss_is_within_cap_and_income_not_supplied(self):
        # The parameter stays OPTIONAL for returns with no capped loss:
        # a -1,200 loss (under the 3,000 cap) is fully allowed, leaves no
        # disallowed remainder, and therefore has no carryforward to get
        # wrong. Requiring the figure here would be noise, not safety.
        out = _compute(short=-1_200, long=0)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], -1_200)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)

    def test_no_raise_on_a_gain_when_income_not_supplied(self):
        # Same optionality for a plain gain -- no loss, no worksheet, no
        # required figure.
        out = _compute(short=10_000, long=0)
        self.assertEqual(out["sch_d_line_21_allowed_loss"], 10_000)

    def test_no_raise_when_taxable_income_nonnegative(self):
        out = _compute(
            short=-50_000, long=0, taxable_income_unfloored=0.0,
        )
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], -47_000)
        out2 = _compute(
            short=-50_000, long=0, taxable_income_unfloored=112_000.0,
        )
        self.assertEqual(out2["sch_d_st_capital_loss_carryforward"], -47_000)

    def test_raises_when_taxable_income_negative_and_loss_exceeds_cap(self):
        with self.assertRaises(NotImplementedError) as ctx:
            _compute(
                short=-50_000, long=0, taxable_income_unfloored=-1.0,
            )
        msg = str(ctx.exception)
        self.assertIn("1212(b)(2)", msg)
        self.assertIn("negative", msg)
        self.assertIn("line 21", msg)
        self.assertIn("Capital Loss Carryover Worksheet", msg)
        self.assertIn("preparer", msg)

    def test_raises_when_taxable_income_negative_even_if_loss_under_cap(self):
        # -1,200 loss (single, $3,000 cap) is fully allowed under the flat
        # cap alone -- naive arithmetic emits 0/0 carryforward. But the
        # REAL worksheet is triggered whenever taxable income is negative
        # regardless of whether the flat cap bound, because a negative TI
        # means even that smaller allowed amount might not have been
        # fully "used". A guard that only fired on cap-bound losses would
        # miss this case -- confirm it does not.
        with self.assertRaises(NotImplementedError):
            _compute(
                short=-1_200, long=0, taxable_income_unfloored=-500.0,
            )

    def test_gain_branch_never_raises_regardless_of_taxable_income(self):
        # line_16 is a GAIN -- line 21 isn't a loss, the worksheet never
        # applies, no matter how negative taxable income is. Confirms the
        # gain branch is genuinely untouched by the guard.
        out = _compute(
            short=10_000, long=0, taxable_income_unfloored=-999_999.0,
        )
        self.assertEqual(out["sch_d_line_21_allowed_loss"], 10_000)
        self.assertEqual(out["sch_d_st_capital_loss_carryforward"], 0)
        self.assertEqual(out["sch_d_lt_capital_loss_carryforward"], 0)


if __name__ == "__main__":
    unittest.main()
