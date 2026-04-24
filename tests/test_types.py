"""Structural tests for tenforty.types."""

import unittest
from typing import Any, get_type_hints

from tenforty.types import UpstreamState


class TestUpstreamState(unittest.TestCase):
    def test_is_total_false(self) -> None:
        """UpstreamState keys must be optional so unset keys are a KeyError,
        not a silent None. total=False is the contract enforced by spec §M1."""
        self.assertFalse(getattr(UpstreamState, "__total__", True))

    def test_has_exact_pass_1_keys(self) -> None:
        """Pass 1 keys: the forms that exist today plus the typed k1_fanout sidecar.

        Uses set equality (not issubset) so that a typo adding or removing
        a key surfaces as a test failure. Sub-plans 1–4 will extend this
        list in lockstep with test expectations."""
        hints = get_type_hints(UpstreamState)
        expected = {
            "f1040", "sch_1", "sch_a", "sch_b", "sch_d", "sch_e",
            "sch_e_part_ii", "f4562", "f8582", "f8949", "f8959",
            "f8995", "k1_fanout",
        }
        self.assertEqual(expected, set(hints))

    def test_k1_fanout_is_k1fanoutdata(self) -> None:
        """The k1_fanout value is the typed sidecar, not a dict."""
        from tenforty.models import K1FanoutData
        hints = get_type_hints(UpstreamState)
        self.assertIs(hints["k1_fanout"], K1FanoutData)

    def test_f8949_is_dict_of_any(self) -> None:
        """f8949 holds the computed subsection-box totals (box_a/b/d/e
        proceeds/basis/adjustment/gain) that sch_d.compute consumes."""
        hints = get_type_hints(UpstreamState)
        self.assertEqual(hints["f8949"], dict[str, Any])
