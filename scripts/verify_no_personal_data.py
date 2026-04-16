"""Scan the repo for personal data leaks.

Checks:
1. ALLOWLIST — fixture files must contain only known synthetic identifiers.
2. DENYLIST — no tracked file may contain known real-world identifiers.
3. HEURISTICS — flag suspicious patterns in YAML fixtures.

Exit code 0 = clean, 1 = violations found.
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent

# --- ALLOWLIST: known synthetic employer/payer names ---
# Every employer or payer name in YAML fixtures must be one of these.
ALLOWED_NAMES = {
    "Acme Corp",
    "Acme",
    "Tech Corp",
    "Test Corp",
    "Bank of Example",
    "National Bank",
    "Brokerage Inc",
    "Investment Brokerage",
    "Mortgage Co",
    "Home Mortgage Co",
    "Example LLC",
    "Fake S-Corp Inc",
    "Fake Trust",
    "Fake Partnership",
}

# --- DENYLIST: patterns that must never appear in tracked files ---
# Generic patterns are hardcoded. User-specific patterns (real employer names,
# etc.) are loaded from a gitignored config file so they don't leak either.
_BUILTIN_DENYLIST = [
    # Real SSN pattern (XXX-XX-XXXX where first group isn't 000/666/9XX)
    r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
    # Real EIN pattern (XX-XXXXXXX). Excludes the placeholder 00-0000000.
    r"\b(?!00-0000000\b)\d{2}-\d{7}\b",
]


def _load_denylist_config() -> list[str]:
    """Load user-specific denylist patterns from gitignored config file."""
    config_path = REPO_ROOT / "scripts" / "personal_data_config.yaml"
    if not config_path.exists():
        print(f"  WARNING: {config_path.relative_to(REPO_ROOT)} not found.")
        print("  Create it with your real employer names, etc. It is gitignored.")
        return []

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config.get("denylist_patterns", [])


_RAW_DENYLIST_PATTERNS = _BUILTIN_DENYLIST + _load_denylist_config()
DENYLIST_PATTERNS = [re.compile(p) for p in _RAW_DENYLIST_PATTERNS]

# --- HEURISTICS for YAML fixtures ---
# Dollar amounts in test fixtures should be round numbers (multiples of 50).
# Real tax data almost never has perfectly round wages.
NON_ROUND_DOLLAR_RE = re.compile(r":\s*(\d+\.\d{2})")
ROUND_THRESHOLD = 50  # must be divisible by this


def get_tracked_files() -> list[Path]:
    """Get all git-tracked files."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return [REPO_ROOT / f for f in result.stdout.strip().split("\n") if f]


def check_denylist(files_content: dict[Path, str]) -> list[str]:
    """Check that no tracked file contains denylist patterns."""
    violations = []
    extensions = {".py", ".yaml", ".yml", ".toml", ".md", ".txt", ".json", ".csv"}

    for path, content in files_content.items():
        if path.suffix not in extensions:
            continue

        for pattern in DENYLIST_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                for match in matches:
                    violations.append(
                        f"DENYLIST: {path.relative_to(REPO_ROOT)}: "
                        f"matched pattern '{pattern.pattern}' -> '{match}'"
                    )

    return violations


def check_fixture_names(files_content: dict[Path, str]) -> list[str]:
    """Check that YAML fixtures only use allowed synthetic names."""
    violations = []
    name_fields = {"employer", "payer", "lender", "entity_name", "broker"}

    for path, content in files_content.items():
        if path.suffix not in {".yaml", ".yml"}:
            continue
        if "fixtures" not in str(path):
            continue

        for line_num, line in enumerate(content.split("\n"), start=1):
            stripped = line.strip()
            for field in name_fields:
                if stripped.startswith(f"{field}:"):
                    value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    if value and value not in ALLOWED_NAMES:
                        violations.append(
                            f"ALLOWLIST: {path.relative_to(REPO_ROOT)}:{line_num}: "
                            f"'{field}: {value}' is not in ALLOWED_NAMES"
                        )

    return violations


def check_non_round_amounts(files_content: dict[Path, str]) -> list[str]:
    """Flag non-round dollar amounts in YAML fixtures as suspicious."""
    violations = []

    for path, content in files_content.items():
        if path.suffix not in {".yaml", ".yml"}:
            continue
        if "fixtures" not in str(path):
            continue

        for line_num, line in enumerate(content.split("\n"), start=1):
            for match in NON_ROUND_DOLLAR_RE.finditer(line):
                amount = float(match.group(1))
                if amount > 0 and amount % ROUND_THRESHOLD != 0:
                    violations.append(
                        f"HEURISTIC: {path.relative_to(REPO_ROOT)}:{line_num}: "
                        f"${amount:.2f} is not a round number "
                        f"(not divisible by {ROUND_THRESHOLD})"
                    )

    return violations


def check_git_history() -> list[str]:
    """Check that no commit message references personal identifiers."""
    violations = []
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H %s"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        for pattern in DENYLIST_PATTERNS:
            if pattern.search(line):
                violations.append(f"GIT HISTORY: commit message matches '{pattern.pattern}': {line}")

    return violations


def main() -> int:
    files = get_tracked_files()
    all_violations: list[str] = []

    print("Scanning for personal data leaks...")
    print(f"  Tracked files: {len(files)}")

    files_content: dict[Path, str] = {}
    for path in files:
        try:
            files_content[path] = path.read_text()
        except (FileNotFoundError, UnicodeDecodeError):
            continue

    denylist = check_denylist(files_content)
    all_violations.extend(denylist)
    print(f"  Denylist check: {len(denylist)} violations")

    allowlist = check_fixture_names(files_content)
    all_violations.extend(allowlist)
    print(f"  Allowlist check: {len(allowlist)} violations")

    heuristic = check_non_round_amounts(files_content)
    all_violations.extend(heuristic)
    print(f"  Heuristic check: {len(heuristic)} violations")

    history = check_git_history()
    all_violations.extend(history)
    print(f"  Git history check: {len(history)} violations")

    if all_violations:
        print(f"\nFOUND {len(all_violations)} VIOLATION(S):\n")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print("\nNo personal data detected. All clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
