"""ONE MEANING FOR `total_tax`: IRS Form 1040 LINE 16, on every compute path.

WHY THIS FILE EXISTS — read this before deleting it as redundant with
`tests/test_1040_tax_band_native_producers.py` or with the parity battery.

`total_tax` used to mean two different 1040 lines depending on which producer
answered. The native spine assigned it line 16 (`income_tax`, the
QDCGT/rate-schedule figure). The workbook harvest mapped it to the vendor's
`Tax` named range, which is LINE 18 — the `Tax` cell is
`IF(<override><>"", ROUND(<override>,0), SUM(Tax_SubTotal, <the line-17 cell>))`
in all five shipped workbooks, and `Tax_SubTotal` is line 16. (An earlier draft
called that "literally `SUM(Tax_SubTotal, …)`". It is not literal — every year
wraps the SUM in the manual-override branch shown above — and dropping the
wrapper is the same tidying-a-quotation habit corrected in `f1040_spine.py`'s
`Overpaid` paragraph.) So on any return with a nonzero Schedule 2 Part I, the
same key named two different numbers on the two paths.

THE DISAGREEMENT WAS INVISIBLE BECAUSE NOTHING EVER ASKED THE TWO PATHS TO
AGREE ON WHICH LINE THE KEY NAMES. The native tests asserted native arithmetic
and the workbook tests asserted workbook arithmetic. The one test that did
compare the paths — `tests/test_f1040_spine_oracle.py`'s penny-parity battery —
ROUTED AROUND THE FORK BY DESIGN rather than missing it by accident.

That distinction is exactly why this file should survive, so be precise about
it. An earlier draft of this docstring said the battery "compared only
scenarios whose Schedule 2 Part I was zero at the time" — which would mean the
battery merely needed a better fixture, and would make this file redundant.
THAT IS FALSE. The battery already ran a nonzero-Part-I scenario:
`ptc_capped_repayment` — the very one used below, Part I = 950 — entered
`_BUILDERS` in 97fce62, a month BEFORE the workbook mapping was repointed in
419670d. It stayed green because the battery did not compare the two
`total_tax` keys at all. It carried

    _PARITY_ORACLE_KEY = {"total_tax": "total_tax_line16"}

which redirected the comparison onto a SEPARATE line-16-only workbook output
key, beneath a comment calling the two semantics "different-but-correct" and
"deliberately NOT unified". So the old battery COULD NOT have caught the fork:
the one comparison that would have exposed it was explicitly aliased away.

BE PRECISE ABOUT WHAT THE BATTERY DOES TODAY, because a reader who checks will
find a live cross-path comparison and distrust this paragraph otherwise. The
alias was retired earlier in this unit, `PARITY_KEYS` still carries
`total_tax` with no override, and `ptc_capped_repayment` is still in the
battery — so the battery now DOES compare the two `total_tax` keys by VALUE, on
a nonzero-Part-I scenario. What it still cannot do is answer the question this
file asks. A penny-parity comparison is green whenever the two paths agree
NUMERICALLY, so a fork that moved BOTH paths to line 18 together would sail
through it; only an assertion about which LINE the key names, made against the
other keys in the band, can catch that. That question has never been asked
anywhere — until this file.

That is the gap this file closes, and it is why the assertions below
insist on a scenario where line 16 and line 18 are DIFFERENT numbers: on a
return with an empty Schedule 2 every assertion here would pass under either
meaning and prove nothing.

THE CONSUMER WHOSE CORRECTNESS DEPENDS ON THE PIN is `tenforty/forms/f1040x.py`
(line 173):

    a6 = filed["total_tax"] + filed.get("f8962_repayment", 0.0)

Form 1040-X line 6 is built on a LINE-16 base with the excess-APTC repayment
added by that expression itself. Fed line-16 inputs it is right; fed line-18
inputs it would add the repayment a second time, because line 18 already
contains it. `f1040x.py` is NOT modified by this file and must not be — this
file is the guard that keeps its input honest.

WHAT IS ORACLE-TIER HERE AND WHY. Reaching the workbook path means driving
LibreOffice, so every class that computes a workbook result carries
`@needs_libreoffice` (which is also what stamps `pytest.mark.oracle` — see
`tests/helpers.py::needs_libreoffice`; a second, hand-written `pytest.mark.oracle`
would be a duplicate of state that has exactly one source on purpose). The
native-only assertions are deliberately left on the always-running gate, so a
native-side regression reddens without a soffice slot.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.forms.f4868 import compose_line_24, total_tax_liability_line_24
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_ptc_capped_repayment
from tests.helpers import REPO_ROOT, needs_libreoffice

# A workbook year, and a battery scenario whose Schedule 2 Part I is NONZERO
# (a capped excess-advance-PTC repayment). Both properties are load-bearing:
# the year so both paths exist, the nonzero Part I so line 16 != line 18 and
# the assertions can tell the two lines apart. This scenario is already in the
# penny-parity battery, so its two paths are known to agree on the VALUES;
# what is asserted here is that they agree on the MEANING of the key.
YEAR = 2024


class _OrchestratorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _effective_scenario(self):
        """The effective scenario, past the ROUTING GUARD.

        Copied in spirit from the parity battery: if this scenario ever fell
        back to the workbook, every "native path" assertion below would
        silently be a workbook assertion. Every caller goes through here — the
        cross-path helper included — so the guard cannot apply to one arm and
        not the other.
        """
        scenario = build_ptc_capped_repayment(YEAR)
        eff, _ = self.orch._build_effective_scenario(scenario)
        self.assertTrue(
            self.orch._scenario_in_spine_scope(eff),
            "the scenario did not route to the native spine, so nothing below "
            "would be testing the native path",
        )
        return eff

    def _native(self) -> dict:
        return self.orch._compute_1040_pipeline(self._effective_scenario())

    # Class-level cache of the WORKBOOK dict only. See `_both_paths`.
    _workbook_cache: dict | None = None

    def _both_paths(self) -> tuple[dict, dict]:
        """(native, workbook) result dicts for the SAME effective scenario.

        Uses the orchestrator's own two entry points rather than a reassembled
        pipeline, for the same reason the parity battery does: the routing is
        part of what is under test.

        THE WORKBOOK HALF IS CACHED ACROSS TESTS IN THIS CLASS, deliberately,
        and the native half is NOT. Every test here needs the same TY2024
        scenario computed through LibreOffice, which is a scarce global slot;
        computing it once instead of once per test cuts this file's oracle-tier
        cost by about two-thirds. The scenario is a module constant, so there
        is nothing per-test for the workbook result to depend on.

        THE CACHE CANNOT LET ONE TEST MASK ANOTHER, which is the property that
        makes it safe rather than merely cheap:
          - each caller gets a COPY, so a test that mutated its dict cannot
            change what any other test sees (the values are scalars, so a
            shallow copy is a full one here);
          - the cache is only populated on SUCCESS, so if the workbook compute
            raises, the next test retries it and fails on its own merits
            instead of inheriting a poisoned entry; and
          - the routing guard and the native compute still run per test, so
            nothing about path selection is cached.
        """
        eff = self._effective_scenario()
        native = self.orch._compute_1040_pipeline(eff)
        cls = type(self)
        if cls._workbook_cache is None:
            cls._workbook_cache = self.orch._compute_1040_via_workbook(eff)
        return native, dict(cls._workbook_cache)

    def assert_line_16_meaning(self, results: dict, path: str) -> None:
        """`total_tax` is line 16 and `tax_plus_schedule2` is line 18, here.

        Both halves are asserted, and the second is what gives the first its
        teeth: line 18 must be line 16 PLUS line 17, and line 17 must be
        nonzero, so a `total_tax` that had silently become line 18 would make
        the sum overshoot and fail.
        """
        line_16 = results["total_tax"]
        line_17 = results["schedule2_tax"]
        line_18 = results["tax_plus_schedule2"]

        self.assertGreater(
            line_17, 0,
            f"{path}: Schedule 2 Part I is zero, so lines 16 and 18 coincide "
            f"and this scenario cannot distinguish them. Fix the fixture, not "
            f"the assertion.",
        )
        self.assertEqual(
            line_16 + line_17, line_18,
            f"{path}: 1040 line 18 must be 'add lines 16 and 17'. If "
            f"`total_tax` has drifted back to meaning line 18, this sum "
            f"overshoots by the Schedule 2 Part I amount.",
        )
        self.assertNotEqual(
            line_16, line_18,
            f"{path}: lines 16 and 18 came out equal despite a nonzero line "
            f"17, so `total_tax` is indistinguishable from line 18 here.",
        )

    def assert_line_4_composes_from_the_uniform_keys(
        self, results: dict, path: str,
    ) -> None:
        """Part A2 — Form 4868 line 4 against the line-17/18 vocabulary.

        Form 4868 line 4 is 1040 line 24. `total_tax_liability_line_24` was
        written BEFORE `schedule2_tax`/`tax_plus_schedule2` existed as named
        keys, so it reached for whatever parts were available at the time. This
        snaps it to the uniform vocabulary now that the vocabulary exists, so
        the older shape cannot quietly become permanent and drift away from the
        named totals.

        THE TWO PATHS ARE NOT THE SAME KIND OF CLAIM, and the failure message
        says which is which:

          - NATIVE: both sides are COMPOSITIONS. Production composes line 24
            inside `total_tax_liability_line_24`; the expectation composes it
            from the named line-16/17 keys. They must agree exactly, and a
            divergence means production is composing from something other than
            the canonical totals.
          - WORKBOOK: production HARVESTS line 24 (the vendor's `Tot_Tax`), so
            this pins a composition against an INDEPENDENT AUTHORITY. That
            authority carries THREE terms the composition can be blind to, and
            they are blind in two different ways — enumerate all three, because
            naming only the first two is what makes a future fixture change
            look safe:
              1. self-employment tax, and
              2. NIIT (Form 8960) — both reach `Tot_Tax` through
                 `TotalOtherTaxes` in all five workbooks. This fixture has
                 neither: a single W-2 filer well under the Additional Medicare
                 threshold, no Schedule C, no investment income.
              3. 1040 LINE 21, nonrefundable credits — and this one is not
                 merely zero for this fixture, it is STRUCTURALLY UNAVAILABLE:
                 `nonrefundable_credits` is not an `F1040.OUTPUTS` key in ANY
                 year, so on the workbook path `.get(...) or 0` below always
                 passes 0 while the vendor's `Tot_Tax` subtracts whatever the
                 sheet computed. It is the term most likely to be nonzero in a
                 future fixture, and it moves line 24 in the opposite
                 direction from the other two.
            Those absences are what make the equality legitimate HERE. A
            failure on this arm is therefore a claim about the fixture or about
            the harvest, not about the composition.
        """
        expected = compose_line_24(
            line_16=results["total_tax"],
            schedule_2_part_i=results["schedule2_tax"],
            nonrefundable_credits=results.get("nonrefundable_credits") or 0,
            schedule_2_part_ii=results.get("f8959_tax_total") or 0,
        )
        # The composition must also be DISTINGUISHABLE from line 16, or the
        # assertion below would hold under a line-24 producer that had
        # collapsed to line 16.
        self.assertNotEqual(
            results["total_tax"], expected,
            f"{path}: the line-24 composition equals line 16, so this "
            f"assertion could not detect a producer that returned line 16",
        )
        self.assertEqual(
            expected, total_tax_liability_line_24(results),
            f"{path}: Form 4868 line 4 (1040 line 24) disagrees with the "
            f"composition built from the named line-16/17 keys. On the native "
            f"path both sides are compositions and must match exactly. On the "
            f"workbook path the left side is a composition and the right side "
            f"is the vendor's harvested `Tot_Tax` — an independent authority "
            f"that can carry self-employment tax, NIIT and 1040 line 21 "
            f"nonrefundable credits, none of which this composition has a "
            f"live term for. Check those three against the fixture first: a "
            f"mismatch here indicts the fixture or the harvest rather than "
            f"the composition.",
        )


class TotalTaxMeansLine16OnTheNativePathTests(_OrchestratorCase):
    """The native half, on the always-running gate (no LibreOffice)."""

    def test_total_tax_is_line_16_and_line_18_adds_schedule_2_part_i(self):
        self.assert_line_16_meaning(self._native(), "native")

    def test_form_4868_line_4_composes_from_the_named_line_17_18_keys(self):
        self.assert_line_4_composes_from_the_uniform_keys(self._native(), "native")


@needs_libreoffice
class TotalTaxMeansLine16OnBothPathsTests(_OrchestratorCase):
    """The cross-path pin. Oracle-tier: the workbook half drives LibreOffice.

    The native assertions are repeated here on purpose. This class computes the
    SAME effective scenario both ways in one place, so a reader can see the two
    dicts side by side; splitting the workbook arm off into a class that never
    sees the native one is what let the two meanings diverge in the first
    place.
    """

    def test_the_two_paths_agree_on_which_1040_line_total_tax_names(self):
        native, workbook = self._both_paths()

        self.assert_line_16_meaning(native, "native")
        self.assert_line_16_meaning(workbook, "workbook")

        # THE CROSS-PATH PIN. Equal `total_tax` across paths is only
        # meaningful alongside the line-16-vs-18 separation asserted above:
        # together they say both keys name the SAME line, and that the line is
        # 16 rather than 18.
        self.assertEqual(
            native["total_tax"], workbook["total_tax"],
            "the native spine and the workbook harvest disagree about "
            "`total_tax`. Check first whether they disagree about the LINE and "
            "not merely the amount: compare each against its own "
            "`tax_plus_schedule2`.",
        )

        # Reachable negative space for the assertion above: repointing the
        # workbook's `total_tax` back at the `Tax` named range (1040 line 18,
        # which is what `mappings/f1040.py` mapped it to before this unit)
        # makes the workbook value equal line 18 and the equality fails. This
        # asserts that the two candidate meanings are genuinely different
        # numbers in this fixture, so the pin above has something to catch.
        self.assertNotEqual(
            native["total_tax"], workbook["tax_plus_schedule2"],
            "line 16 and line 18 are the same number on the workbook path, so "
            "the cross-path equality above cannot tell the old meaning from "
            "the new one",
        )

    def test_the_two_paths_agree_on_lines_17_and_18_as_well(self):
        """`total_tax` is not pinnable alone.

        Line 16 agreeing while line 17 or 18 disagreed would mean the paths had
        merely moved the discrepancy one line down. The parity battery does not
        compare these two keys (`PARITY_KEYS` in
        `tests/test_f1040_spine_oracle.py` carries `total_tax` but neither
        `schedule2_tax` nor `tax_plus_schedule2`), so this is the only place
        the whole band is compared across paths.
        """
        native, workbook = self._both_paths()
        for key in ("schedule2_tax", "tax_plus_schedule2"):
            with self.subTest(key=key):
                self.assertEqual(native[key], workbook[key])

    def test_form_4868_line_4_matches_the_uniform_composition_on_both_paths(self):
        native, workbook = self._both_paths()
        self.assert_line_4_composes_from_the_uniform_keys(native, "native")
        self.assert_line_4_composes_from_the_uniform_keys(workbook, "workbook")

        # The paths reach line 24 by DIFFERENT MECHANISMS, and that difference
        # is the point of running the assertion twice. Asserted rather than
        # narrated, because the harvest/compose branch in
        # `total_tax_liability_line_24` keys on exactly this.
        self.assertNotIn("tax_liability_line24", native)
        self.assertIn("tax_liability_line24", workbook)


if __name__ == "__main__":
    unittest.main()
