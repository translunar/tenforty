"""Schedule D — Capital Gains and Losses.

``f8949.compute`` has already partitioned ``scenario.form1099_b`` into two
buckets and emitted totals for each: aggregate-path lots (Box A/D no-
adjustment) flow to lines 1a/8a; 8949-path lots flow per-box to 1b/2/3
and 8b/9/10. ``sch_d.compute`` forwards both partitions' totals — no
subtraction, no re-partitioning. The no-double-count invariant is
enforced separately on the f8949 emission.
"""

from tenforty.models import K1FanoutData, Scenario
from tenforty.rounding import irs_round
from tenforty.types import UpstreamState


def compute(scenario: Scenario, upstream: UpstreamState) -> dict:
    f8949 = upstream.get("f8949", {})
    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()

    line_1a = _agg_line(f8949, term="short")
    line_8a = _agg_line(f8949, term="long")

    line_1b = _box_line(f8949, letter="a")
    line_2 = _box_line(f8949, letter="b")
    line_3 = _box_line(f8949, letter="c")
    line_8b = _box_line(f8949, letter="d")
    line_9 = _box_line(f8949, letter="e")
    line_10 = _box_line(f8949, letter="f")

    k1_short = irs_round(sum(fanout.sch_d_short_term_additions))
    k1_long = irs_round(sum(fanout.sch_d_long_term_additions))

    line_7 = (line_1a["gain"] + line_1b["gain"] + line_2["gain"]
              + line_3["gain"] + k1_short)
    line_15 = (line_8a["gain"] + line_8b["gain"] + line_9["gain"]
               + line_10["gain"] + k1_long)
    line_16 = line_7 + line_15

    return {
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,

        "sch_d_line_1a_proceeds": line_1a["proceeds"],
        "sch_d_line_1a_basis": line_1a["basis"],
        "sch_d_line_1a_gain": line_1a["gain"],
        "sch_d_line_1b_proceeds": line_1b["proceeds"],
        "sch_d_line_1b_basis": line_1b["basis"],
        "sch_d_line_1b_gain": line_1b["gain"],
        "sch_d_line_2_proceeds": line_2["proceeds"],
        "sch_d_line_2_basis": line_2["basis"],
        "sch_d_line_2_gain": line_2["gain"],
        "sch_d_line_3_proceeds": line_3["proceeds"],
        "sch_d_line_3_basis": line_3["basis"],
        "sch_d_line_3_gain": line_3["gain"],
        "sch_d_line_5_net_short_k1": k1_short,
        "sch_d_line_7_net_short": line_7,

        "sch_d_line_8a_proceeds": line_8a["proceeds"],
        "sch_d_line_8a_basis": line_8a["basis"],
        "sch_d_line_8a_gain": line_8a["gain"],
        "sch_d_line_8b_proceeds": line_8b["proceeds"],
        "sch_d_line_8b_basis": line_8b["basis"],
        "sch_d_line_8b_gain": line_8b["gain"],
        "sch_d_line_9_proceeds": line_9["proceeds"],
        "sch_d_line_9_basis": line_9["basis"],
        "sch_d_line_9_gain": line_9["gain"],
        "sch_d_line_10_proceeds": line_10["proceeds"],
        "sch_d_line_10_basis": line_10["basis"],
        "sch_d_line_10_gain": line_10["gain"],
        "sch_d_line_12_net_long_k1": k1_long,
        "sch_d_line_15_net_long": line_15,

        "sch_d_line_16_total": line_16,
        "sch_d_line_18_unrecap_1250": f8949.get("f8949_total_unrecap_1250", 0),
        "sch_d_line_19_28_rate_gain": f8949.get("f8949_total_28_rate_gain", 0),
    }


def _agg_line(f8949: dict, *, term: str) -> dict[str, int]:
    return {
        "proceeds": f8949.get(f"f8949_agg_{term}_proceeds", 0),
        "basis": f8949.get(f"f8949_agg_{term}_basis", 0),
        "gain": f8949.get(f"f8949_agg_{term}_gain", 0),
    }


def _box_line(f8949: dict, *, letter: str) -> dict[str, int]:
    return {
        "proceeds": f8949.get(f"f8949_box_{letter}_total_proceeds", 0),
        "basis": f8949.get(f"f8949_box_{letter}_total_basis", 0),
        "gain": f8949.get(f"f8949_box_{letter}_total_gain", 0),
    }
