"""ONE MEANING FOR `total_tax`: IRS Form 1040 LINE 16, on every compute path.

WHY THIS FILE EXISTS — read this before deleting it as redundant with
`tests/test_1040_tax_band_native_producers.py` or with the parity battery.

`total_tax` used to mean two different 1040 lines depending on which producer
answered. The native spine assigned it line 16 (`income_tax`, the
QDCGT/rate-schedule figure). The workbook harvest mapped it to the vendor's
`Tax` named range, which is LINE 18 — `Tax` is literally
`SUM(Tax_SubTotal, <the line-17 cell>)` in all five shipped workbooks, and
`Tax_SubTotal` is line 16. So on any return with a nonzero Schedule 2 Part I,
the same key named two different numbers on the two paths.

THE DISAGREEMENT WAS INVISIBLE BECAUSE EACH PATH WAS ONLY EVER TESTED AGAINST
ITSELF. The native tests asserted native arithmetic; the workbook tests
asserted workbook arithmetic; and the one test that did compare them —
`tests/test_f1040_spine_oracle.py`'s penny-parity battery — compared only
scenarios whose Schedule 2 Part I was zero at the time, where lines 16 and 18
coincide. Nothing anywhere asked the two paths to agree on WHICH LINE the key
names. That is the gap this file closes, and it is why the assertions below
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


def _compute_both_paths(orch: ReturnOrchestrator) -> tuple[dict, dict]:
    """Return (native, workbook) result dicts for the SAME effective scenario.

    Uses the orchestrator's own two entry points rather than a reassembled
    pipeline, for the same reason the parity battery does: the routing is part
    of what is under test.
    """
    scenario = build_ptc_capped_repayment(YEAR)
    eff, _ = orch._build_effective_scenario(scenario)
    return orch._compute_1040_pipeline(eff), orch._compute_1040_via_workbook(eff)


class _OrchestratorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _native(self) -> dict:
        scenario = build_ptc_capped_repayment(YEAR)
        eff, _ = self.orch._build_effective_scenario(scenario)
        # ROUTING GUARD, copied in spirit from the parity battery: if this
        # scenario ever fell back to the workbook, every "native path"
        # assertion below would silently be a workbook assertion.
        self.assertTrue(
            self.orch._scenario_in_spine_scope(eff),
            "the scenario did not route to the native spine, so nothing below "
            "would be testing the native path",
        )
        return self.orch._compute_1040_pipeline(eff)

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
            authority legitimately carries terms the composition has no term
            for at all — self-employment tax and NIIT both reach `Tot_Tax`
            through `TotalOtherTaxes` in all five workbooks. The fixture has
            neither (a single W-2 filer well under the Additional Medicare
            threshold, no Schedule C, no investment income), which is what
            makes the equality legitimate HERE. A failure on this arm is
            therefore a claim about the fixture or about the harvest, not
            about the composition.
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
            f"that carries self-employment tax and NIIT, which this fixture "
            f"has neither of, so a mismatch here indicts the fixture or the "
            f"harvest rather than the composition.",
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
        native, workbook = _compute_both_paths(self.orch)

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
        native, workbook = _compute_both_paths(self.orch)
        for key in ("schedule2_tax", "tax_plus_schedule2"):
            with self.subTest(key=key):
                self.assertEqual(native[key], workbook[key])

    def test_form_4868_line_4_matches_the_uniform_composition_on_both_paths(self):
        native, workbook = _compute_both_paths(self.orch)
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
