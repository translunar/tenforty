"""Scan the repo for personal data leaks.

Checks:
1. ALLOWLIST — fixture files must contain only known synthetic identifiers.
2. DENYLIST — no tracked file may contain known real-world identifiers.
3. HEURISTICS — flag suspicious patterns in YAML fixtures.

Exit code 0 = clean, 1 = violations found (or config is missing/malformed —
this scanner fails CLOSED, not open).

Worktree provisioning: scripts/personal_data_config.yaml is gitignored (it
holds real employer names and other personal identifiers, so it must never
be tracked). Every fresh worktree is missing it and the scan will fail
closed until it's provisioned. Copy it from the main checkout:
    cp ~/Projects/tenforty/scripts/personal_data_config.yaml scripts/personal_data_config.yaml
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "scripts" / "personal_data_config.yaml"

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


def _resolve_config_path() -> Path:
    """Resolve the denylist config path, honoring the test-only env override."""
    return Path(os.environ.get("TENFORTY_PII_CONFIG", str(DEFAULT_CONFIG_PATH)))


def _provisioning_hint(config_path: Path) -> str:
    """One-line, self-explaining fix-it command for a missing/bad config."""
    return (
        "To provision in a worktree, copy it from the main checkout:  "
        f"cp ~/Projects/tenforty/scripts/personal_data_config.yaml {config_path}"
    )


class ConfigError(Exception):
    """Raised when the denylist config is missing, empty, or malformed."""


def _load_denylist_config(config_path: Path) -> list[str]:
    """Load user-specific denylist patterns from the gitignored config file.

    Fails CLOSED: any problem loading or parsing the config raises
    ConfigError rather than silently returning an empty list.
    """
    if not config_path.exists():
        raise ConfigError(f"Personal-data config not found: {config_path}")

    try:
        with open(config_path) as f:
            raw = f.read()
    except OSError as exc:
        raise ConfigError(f"Personal-data config unreadable: {config_path} ({exc})") from exc

    try:
        config = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Personal-data config is malformed YAML: {config_path} ({exc})") from exc

    if config is None:
        raise ConfigError(f"Personal-data config is empty: {config_path}")

    if not isinstance(config, dict):
        raise ConfigError(
            f"Personal-data config did not parse to a mapping: {config_path}"
        )

    return config.get("denylist_patterns", [])

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


def check_denylist(
    files_content: dict[Path, str], denylist_patterns: list[re.Pattern]
) -> list[str]:
    """Check that no tracked file contains denylist patterns."""
    violations = []
    extensions = {".py", ".yaml", ".yml", ".toml", ".md", ".txt", ".json", ".csv"}

    for path, content in files_content.items():
        if path.suffix not in extensions:
            continue

        for pattern in denylist_patterns:
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


def check_git_history(denylist_patterns: list[re.Pattern]) -> list[str]:
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
        for pattern in denylist_patterns:
            if pattern.search(line):
                violations.append(f"GIT HISTORY: commit message matches '{pattern.pattern}': {line}")

    return violations


def main() -> int:
    config_path = _resolve_config_path()
    try:
        raw_patterns = _BUILTIN_DENYLIST + _load_denylist_config(config_path)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"  Config path: {config_path}", file=sys.stderr)
        print(f"  {_provisioning_hint(config_path)}", file=sys.stderr)
        return 1

    denylist_patterns = [re.compile(p) for p in raw_patterns]

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

    denylist = check_denylist(files_content, denylist_patterns)
    all_violations.extend(denylist)
    print(f"  Denylist check: {len(denylist)} violations")

    allowlist = check_fixture_names(files_content)
    all_violations.extend(allowlist)
    print(f"  Allowlist check: {len(allowlist)} violations")

    heuristic = check_non_round_amounts(files_content)
    all_violations.extend(heuristic)
    print(f"  Heuristic check: {len(heuristic)} violations")

    history = check_git_history(denylist_patterns)
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
