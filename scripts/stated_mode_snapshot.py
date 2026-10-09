"""Stated-mode migration evidence: a results snapshot for comparing two trees.

For every rental-bearing spine-battery scenario (2021-2025), and a variant of
each with a second stated-mode rental added, this records the full
compute_federal results dict, the workbook flattener inputs, and the
excess-business-loss aggregate.

Usage, from the root of a tenforty tree with its venv active:

    python scripts/stated_mode_snapshot.py /path/to/snapshot.json

Run it on the tree BEFORE a change and on the tree AFTER, then compare the two
JSON files; identical files mean no stated-mode number moved. The script
copes with trees from before the per-activity stated-figure acknowledgment
existed (it adds the acknowledgment only where the model has the field).

It compares nothing itself and has no baseline of its own: a baseline is the
output of this same script on the older commit.
"""
import copy, dataclasses, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
from tenforty.models import RentalProperty
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import battery_for
from tests.helpers import SPREADSHEETS_DIR

HAS_ACK = "acknowledges_depreciation_stated_outside_macrs" in {
    f.name for f in dataclasses.fields(RentalProperty)}
out = {}
for year in (2021, 2022, 2023, 2024, 2025):
    for name, build in battery_for(year):
        base = build()
        if not base.rental_properties:
            continue
        variants = {"": base}
        two = copy.deepcopy(base)
        extra = dict(address="200 Example Street", property_type=1,
                     fair_rental_days=365, personal_use_days=0,
                     rents_received=9_000.0, taxes=1_000.0,
                     depreciation=2_500.0)
        if HAS_ACK:
            extra["acknowledges_depreciation_stated_outside_macrs"] = True
        two.rental_properties.append(RentalProperty(**extra))
        variants["+second_rental"] = two
        for suffix, scenario in variants.items():
            key = f"{year}:{name}{suffix}"
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    res = ReturnOrchestrator(
                        spreadsheets_dir=SPREADSHEETS_DIR,
                        work_dir=Path(tmp)).compute_federal(scenario)
                    from tenforty.oracle.flattener import flatten_scenario
                    from tenforty.orchestrator import aggregate_business_losses
                    res = dict(res)
                    res["__flattener__"] = flatten_scenario(scenario)
                    res["__aggregate_business_losses__"] = (
                        aggregate_business_losses(scenario))
                    out[key] = json.loads(json.dumps(res, default=str, sort_keys=True))
                except Exception as e:  # recorded, compared like any value
                    out[key] = f"{type(e).__name__}: {str(e)[:200]}"
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, sort_keys=True))
print(len(out), "scenarios;", sum(isinstance(v, str) for v in out.values()), "raised")
for k, v in out.items():
    print(" ", k, "->", v if isinstance(v, str) else f"{len(v)} keys")
