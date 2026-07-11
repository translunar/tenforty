"""Invariant test: intra-section uniqueness of PDF field paths across every
PdfFormMapping subclass and every year.

The invariant: within a single addressable scope, no two compute keys may
map to the same PDF field path.  "Addressable scope" is:
  - The scalars dict (or the entire flat payload for flat-shaped modules).
  - Each individual repeater section (box_a_rows, box_b_rows, etc.).

We intentionally do NOT cross-check between sections; paginated multi-emission
forms legitimately reuse paths across sections (e.g. box_a_rows and box_b_rows
in Form 8949 share page-1 table paths — they are emitted into separate physical
PDF copies).
"""

import importlib
import pkgutil
import unittest
from collections import Counter
from typing import Any

import tenforty.mappings as _mappings_pkg
from tenforty.mappings.pdf_f8949 import PdfF8949
from tenforty.mappings.registry import PdfFormMapping

# ---------------------------------------------------------------------------
# Allowlist of intentionally shared scalar PDF field paths, keyed by class.
#
# PdfF8949 architecture (see tenforty/mappings/pdf_f8949.py:10-16):
#   Form 8949 uses one shared repeater table per page.  Boxes A and B both
#   live on page 1; boxes D and E both live on page 2.  The filler emits a
#   separate physical PDF copy of the page for each box, writing the
#   appropriate checkbox and totals once per copy.  Consequently, the four
#   page-level totals scalars (total_proceeds, total_basis, total_adjustment,
#   total_gain) on page 1 are shared between the box_a_* and box_b_* compute
#   keys, and the same four on page 2 are shared between box_d_* and box_e_*.
#   This yields exactly 8 intentionally shared scalar paths PER YEAR — all of
#   them totals fields.  Checkboxes are NOT shared (they use different array
#   indices: c{page}_1[0] vs c{page}_1[1]).  Each supported year contributes
#   its own 8 (the field numbers differ across years — e.g. f1_91.. in TY2025,
#   f1_115.. in TY2024 — but the sharing structure is identical), so the
#   derived allowlist holds 8 * len(_MAPPINGS) paths.
# ---------------------------------------------------------------------------

def _derive_f8949_shared_paths() -> frozenset[str]:
    """Return the frozenset of scalar paths that appear more than once in any
    year's PdfF8949 scalars.  Built from the live source across every declared
    year so the allowlist stays in sync automatically as years are added."""
    shared: set[str] = set()
    for payload in PdfF8949._MAPPINGS.values():
        counts = Counter(payload["scalars"].values())
        shared.update(path for path, count in counts.items() if count > 1)
    return frozenset(shared)


_KNOWN_SHARED_PATHS: dict[type, frozenset[str]] = {
    PdfF8949: _derive_f8949_shared_paths(),
}


# ---------------------------------------------------------------------------
# Helpers: discover subclasses and iterate scopes
# ---------------------------------------------------------------------------

def _discover_pdf_mapping_classes() -> list[type]:
    """Import every module under tenforty.mappings and return all concrete
    PdfFormMapping subclasses (direct or indirect) found in those modules."""
    # Walk the package so new modules are picked up automatically.
    for _finder, name, _ispkg in pkgutil.walk_packages(
        path=_mappings_pkg.__path__,
        prefix=_mappings_pkg.__name__ + ".",
    ):
        importlib.import_module(name)

    # Collect all subclasses via __subclasses__ recursively.
    def _collect(cls: type) -> list[type]:
        result = []
        for sub in cls.__subclasses__():
            result.append(sub)
            result.extend(_collect(sub))
        return result

    all_subs = _collect(PdfFormMapping)
    # Exclude private test-only helpers (defined in test files / registry tests).
    return [
        cls for cls in all_subs
        if cls.__module__.startswith("tenforty.")
    ]


def _iter_scopes(
    cls: type, year: int, payload: Any
) -> list[tuple[str, dict[str, str]]]:
    """Return a list of (scope_name, {compute_key: pdf_path}) pairs.

    Handles two payload shapes:
    1. Flat dict[str, str] — the whole dict is one scope named "scalars".
    2. {"scalars": dict, "repeaters": dict} — scalars is one scope; each
       repeater section is a separate scope.

    Repeater section sub-shapes:
    - list[dict[str, str]]: list of already-expanded row dicts (PdfF8949).
      Merge all rows into a flat dict for the scope; duplicate path detection
      still applies within the section.
    - dict with "template" key: template-based (not currently present in the
      codebase, but handled for forward-compat).
    """
    if not isinstance(payload, dict):
        raise TypeError(
            f"{cls.__name__}[{year}]: unexpected payload type {type(payload)}"
        )

    # Detect flat vs structured shape by checking for "scalars" key.
    if "scalars" in payload or "repeaters" in payload:
        scopes: list[tuple[str, dict[str, str]]] = []

        scalars = payload.get("scalars", {})
        if scalars:
            scopes.append(("scalars", scalars))

        repeaters = payload.get("repeaters", {})
        for section_name, section in repeaters.items():
            if isinstance(section, list):
                # list-of-row-dicts shape (PdfF8949)
                merged: dict[str, str] = {}
                for row_dict in section:
                    merged.update(row_dict)
                scopes.append((section_name, merged))
            elif isinstance(section, dict):
                # template+max_slots shape
                template = section.get("template", {})
                max_slots = section.get("max_slots", 1)
                expanded: dict[str, str] = {}
                for compute_key_tmpl, path_tmpl in template.items():
                    for i in range(1, max_slots + 1):
                        expanded[compute_key_tmpl.replace("{i}", str(i))] = (
                            path_tmpl.replace("{i}", str(i))
                        )
                scopes.append((section_name, expanded))
            else:
                raise TypeError(
                    f"{cls.__name__}[{year}] section {section_name!r}: "
                    f"unexpected type {type(section)}"
                )

        return scopes
    else:
        # Flat dict: treat entire payload as a single scope.
        return [("scalars", payload)]


# ---------------------------------------------------------------------------
# The invariant test
# ---------------------------------------------------------------------------

class PdfFieldPathUniquenessTest(unittest.TestCase):
    """Assert intra-section uniqueness of PDF field paths for every
    PdfFormMapping subclass and every declared year."""

    def test_no_unallowlisted_duplicate_paths(self) -> None:
        """For every (class, year) pair, no two compute keys in the same
        addressable scope may map to the same PDF field path, unless that
        path is explicitly allowlisted in _KNOWN_SHARED_PATHS for the class.

        Repeater sections are never allowlisted — their uniqueness is absolute.
        """
        classes = _discover_pdf_mapping_classes()
        self.assertGreater(
            len(classes), 0, "No PdfFormMapping subclasses found — discovery broken"
        )

        for cls in classes:
            for year, payload in cls._MAPPINGS.items():
                with self.subTest(cls=cls.__name__, year=year):
                    allowed = _KNOWN_SHARED_PATHS.get(cls, frozenset())
                    scopes = _iter_scopes(cls, year, payload)

                    for scope_name, mapping in scopes:
                        counts = Counter(mapping.values())
                        duplicated_paths = {
                            path for path, cnt in counts.items() if cnt > 1
                        }

                        if scope_name == "scalars":
                            # Scalars: allowlisted paths are permitted.
                            unallowlisted = duplicated_paths - allowed
                            if unallowlisted:
                                details = []
                                for path in sorted(unallowlisted):
                                    colliding = [
                                        k for k, v in mapping.items() if v == path
                                    ]
                                    details.append(
                                        f"  path={path!r}  keys={colliding}"
                                    )
                                self.fail(
                                    f"{cls.__name__}[{year}] scalars: "
                                    f"{len(unallowlisted)} duplicate path(s) not in "
                                    f"_KNOWN_SHARED_PATHS:\n" + "\n".join(details)
                                )
                        else:
                            # Repeater sections: zero tolerance.
                            if duplicated_paths:
                                details = []
                                for path in sorted(duplicated_paths):
                                    colliding = [
                                        k for k, v in mapping.items() if v == path
                                    ]
                                    details.append(
                                        f"  path={path!r}  keys={colliding}"
                                    )
                                self.fail(
                                    f"{cls.__name__}[{year}] repeater section "
                                    f"{scope_name!r}: {len(duplicated_paths)} "
                                    f"duplicate path(s) within the section "
                                    f"(repeater duplicates are never allowlisted):\n"
                                    + "\n".join(details)
                                )

    def test_f8949_allowlist_has_8_shared_totals_per_year(self) -> None:
        """Sanity-check: the PdfF8949 allowlist holds exactly 8 shared paths
        PER declared year — the four page-1 totals shared by boxes A/B and the
        four page-2 totals shared by boxes D/E.  The count therefore scales as
        8 * len(_MAPPINGS).

        If this fails, the audit in pdf_f8949.py has diverged from the
        allowlist derivation — reconcile before proceeding.
        """
        allowlist = _KNOWN_SHARED_PATHS[PdfF8949]
        expected = 8 * len(PdfF8949._MAPPINGS)
        self.assertEqual(
            len(allowlist),
            expected,
            f"Expected {expected} shared paths for PdfF8949 "
            f"(8 totals × {len(PdfF8949._MAPPINGS)} years), "
            f"got {len(allowlist)}: {sorted(allowlist)}",
        )

    def test_f8949_allowlist_paths_are_totals_only(self) -> None:
        """Confirm no checkbox paths appear in the PdfF8949 allowlist.

        Checkboxes use per-box array indices (c1_1[0] vs c1_1[1]) and are
        intentionally distinct — if they appear as duplicates, something
        changed in the mapping and the architecture assumption broke.
        """
        allowlist = _KNOWN_SHARED_PATHS[PdfF8949]
        checkbox_paths = {p for p in allowlist if "_1[" in p and ".c" in p}
        self.assertEqual(
            checkbox_paths,
            set(),
            f"Unexpected checkbox path(s) in PdfF8949 allowlist: {checkbox_paths}",
        )


if __name__ == "__main__":
    unittest.main()
