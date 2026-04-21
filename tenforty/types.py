"""Typed state threaded through a compute stage.

UpstreamState is the dict shape passed between form.compute() calls within
one compute stage. total=False — unset keys raise KeyError, not return None,
so misspellings fail loudly rather than silently.

Pass 1 populates only the federal-personal-stage keys that exist today.
Sub-plans 1-4 (issue #20) extend this with f8949, f1120s, sch_k_1120s,
f540, sch_ca_540, sch_d_540, sch_p_540, f100s, f3804, sch_k_100s.
"""

from typing import Any, TypedDict

from tenforty.models import K1FanoutData


class UpstreamState(TypedDict, total=False):
    f1040: dict[str, Any]
    sch_1: dict[str, Any]
    sch_a: dict[str, Any]
    sch_b: dict[str, Any]
    sch_d: dict[str, Any]
    sch_e: dict[str, Any]
    sch_e_part_ii: dict[str, Any]
    f4562: dict[str, Any]
    f8582: dict[str, Any]
    f8959: dict[str, Any]
    f8995: dict[str, Any]
    k1_fanout: K1FanoutData
