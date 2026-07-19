"""Scan a git log -p stream (diffs + commit messages) for PII denylist hits.

Reuses tenforty's builtin SSN/EIN patterns plus the gitignored
scripts/personal_data_config.yaml denylist. Reports hits with the match
REDACTED (first 2 chars + length) so this output is itself safe to share.

Usage: git log -p <range> | python scan_push_range.py <repo_root>
Exit 0 = clean, 1 = hits found.
"""

import re
import sys
from pathlib import Path

import yaml

repo_root = Path(sys.argv[1])
config = yaml.safe_load((repo_root / "scripts" / "personal_data_config.yaml").read_text())
if not isinstance(config, dict) or not config.get("denylist_patterns"):
    print("FAIL CLOSED: config missing/empty", file=sys.stderr)
    sys.exit(1)

builtin = [
    r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
    r"\b(?!00-0000000\b)\d{2}-\d{7}\b",
]
patterns = [(f"builtin-{i}", re.compile(p)) for i, p in enumerate(builtin)]
patterns += [
    (f"config-{i}", re.compile(p, re.IGNORECASE))
    for i, p in enumerate(config["denylist_patterns"])
]


def redact(m: str) -> str:
    return f"{m[:2]}{'*' * (len(m) - 2)} (len {len(m)})"


sys.stdin.reconfigure(errors="replace")

commit = "?"
subject = "?"
in_file = "?"
hits = 0
lines_scanned = 0

for line in sys.stdin:
    lines_scanned += 1
    if line.startswith("COMMIT:"):
        commit, _, subject = line[7:].strip().partition(" ")
        in_file = "(commit message)"
        continue
    if line.startswith("+++ b/") or line.startswith("--- a/"):
        in_file = line[6:].strip()
        continue
    for name, pat in patterns:
        for m in pat.findall(line):
            hits += 1
            print(f"HIT [{name}] commit {commit[:10]} ({subject[:50]}) file {in_file}: {redact(m)}")

print(f"scanned {lines_scanned} lines; {hits} hits", file=sys.stderr)
sys.exit(1 if hits else 0)
