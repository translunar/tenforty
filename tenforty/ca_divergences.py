"""Runtime-loaded Schedule CA (540) federal-vs-CA divergence catalog.

The per-year catalogs live as packaged YAML data files under
``tenforty/params/california/divergences/y<year>.yaml`` and are the single
runtime source of truth for CA Schedule CA divergences. :func:`load_catalog`
reads them via :mod:`importlib.resources` (not a cwd-relative path) and
fail-closes: a missing file, malformed YAML, or ANY schema violation raises
:class:`CatalogError` naming the year, the offending row, and the violation.

This module defines the ``auto`` / ``triggers`` / ``gate`` schema fields so
later parts can populate them, but no packaged row carries any of them yet.
"""

from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass
from enum import Enum

import yaml

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_RESOURCE_PACKAGE = "tenforty.params.california.divergences"


class CatalogDirection(str, Enum):
    """Direction of a Schedule CA adjustment as recorded in the catalog.

    ``ADD``/``SUB`` map to :class:`tenforty.models.DivergenceDirection` later;
    ``BOTH`` resolves to a concrete direction at input time (a later part).
    """

    ADD = "Add"
    SUB = "Sub"
    BOTH = "Both"


@dataclass(frozen=True)
class AutoRule:
    """An auto-derivation rule for a divergence.

    Exactly one of ``federal_key`` / ``ca540_field`` must be set (validated at
    load). No packaged row carries an auto rule yet; this exists for later parts.
    """

    federal_key: str | None = None
    ca540_field: str | None = None


@dataclass(frozen=True)
class CatalogEntry:
    """One Schedule CA federal-vs-CA divergence row."""

    id: str
    sch_ca_line: str
    section_title: str
    description: str
    direction: CatalogDirection
    common: bool
    # Usually an int page number. Four wildfire-settlement rows in TY2021/TY2022
    # carry a documented non-empty string sentinel instead ("n/a (statute
    # window, not Pub 1001)") because their basis is a statute's retroactive
    # window, not a Pub 1001 page — see those files' provenance headers. The
    # brief's "preserve field values byte-for-byte / do not invent" mandate
    # forbids fabricating a page number, so the type admits that sentinel.
    pub1001_page: int | str
    ircrtc: str
    auto: AutoRule | None = None
    triggers: tuple[str, ...] = ()
    gate: bool = False
    derivable_via: str | None = None


class CatalogError(Exception):
    """Raised for any missing file, malformed YAML, or schema violation."""


# Recognized row keys. Unknown keys are a schema violation (fail-closed).
_KNOWN_ROW_KEYS = frozenset(
    {
        "id",
        "sch_ca_line",
        "section_title",
        "description",
        "direction",
        "common",
        "pub1001_page",
        "ircrtc",
        "auto",
        "triggers",
        "gate",
        "derivable_via",
    }
)
_KNOWN_AUTO_KEYS = frozenset({"federal_key", "ca540_field"})


def _read_catalog_text(year: int) -> str:
    """Return the packaged catalog YAML text for ``year``.

    Reads via :mod:`importlib.resources` so resolution does not depend on cwd.
    Raises :class:`FileNotFoundError` if the packaged file is absent.
    """
    resource = importlib.resources.files(_RESOURCE_PACKAGE) / f"y{year}.yaml"
    return resource.read_text(encoding="utf-8")


def _require(condition: bool, year: int, where: str, message: str) -> None:
    if not condition:
        raise CatalogError(f"[{year}] {where}: {message}")


def _build_auto(year: int, where: str, raw: object) -> AutoRule:
    _require(isinstance(raw, dict), year, where, "`auto` must be a mapping")
    assert isinstance(raw, dict)  # narrow for type-checkers
    unknown = set(raw) - _KNOWN_AUTO_KEYS
    _require(not unknown, year, where, f"unknown auto keys: {sorted(unknown)}")
    federal_key = raw.get("federal_key")
    ca540_field = raw.get("ca540_field")
    set_count = sum(1 for v in (federal_key, ca540_field) if v is not None)
    _require(
        set_count == 1,
        year,
        where,
        "`auto` must set exactly one of `federal_key` / `ca540_field`",
    )
    return AutoRule(federal_key=federal_key, ca540_field=ca540_field)


def _build_entry(year: int, index: int, raw: object) -> CatalogEntry:
    where = f"row[{index}]"
    _require(isinstance(raw, dict), year, where, "row must be a mapping")
    assert isinstance(raw, dict)

    unknown = set(raw) - _KNOWN_ROW_KEYS
    _require(not unknown, year, where, f"unknown keys: {sorted(unknown)}")

    # id: present, kebab-case (uniqueness checked by caller across the year).
    entry_id = raw.get("id")
    _require(
        isinstance(entry_id, str) and bool(_KEBAB_RE.match(entry_id)),
        year,
        where,
        f"`id` must be a kebab-case string, got {entry_id!r}",
    )
    assert isinstance(entry_id, str)
    where = f"row[{index}] id={entry_id!r}"

    for key in ("sch_ca_line", "section_title", "description", "ircrtc"):
        value = raw.get(key)
        _require(
            isinstance(value, str) and bool(value.strip()),
            year,
            where,
            f"`{key}` must be a non-empty string",
        )

    pub1001_page = raw.get("pub1001_page")
    _require(
        (isinstance(pub1001_page, int) and not isinstance(pub1001_page, bool))
        or (isinstance(pub1001_page, str) and bool(pub1001_page.strip())),
        year,
        where,
        "`pub1001_page` must be an int (or a documented non-empty string sentinel)",
    )

    common = raw.get("common")
    _require(isinstance(common, bool), year, where, "`common` must be a bool")

    direction_raw = raw.get("direction")
    try:
        direction = CatalogDirection(direction_raw)
    except ValueError:
        raise CatalogError(
            f"[{year}] {where}: `direction` must be one of "
            f"{[d.value for d in CatalogDirection]}, got {direction_raw!r}"
        )

    auto_raw = raw.get("auto")
    auto = None if auto_raw is None else _build_auto(year, where, auto_raw)

    gate = raw.get("gate", False)
    _require(isinstance(gate, bool), year, where, "`gate` must be a bool")

    # auto/gate mutual exclusion.
    _require(
        not (auto is not None and gate),
        year,
        where,
        "a row may not have both an `auto` rule and `gate: true`",
    )

    # An auto rule needs a concrete direction (not BOTH).
    _require(
        not (auto is not None and direction is CatalogDirection.BOTH),
        year,
        where,
        "an `auto` row may not use direction BOTH",
    )

    triggers_raw = raw.get("triggers", [])
    _require(
        isinstance(triggers_raw, (list, tuple)),
        year,
        where,
        "`triggers` must be a list",
    )
    # Until the trigger registry lands (a later part), triggers must be empty.
    _require(
        len(triggers_raw) == 0,
        year,
        where,
        "`triggers` must be empty until the trigger registry lands",
    )
    triggers = tuple(triggers_raw)

    derivable_via = raw.get("derivable_via")
    _require(
        derivable_via is None or isinstance(derivable_via, str),
        year,
        where,
        "`derivable_via` must be a string when present",
    )

    return CatalogEntry(
        id=entry_id,
        sch_ca_line=raw["sch_ca_line"],
        section_title=raw["section_title"],
        description=raw["description"],
        direction=direction,
        common=common,
        pub1001_page=pub1001_page,
        ircrtc=raw["ircrtc"],
        auto=auto,
        triggers=triggers,
        gate=gate,
        derivable_via=derivable_via,
    )


def load_catalog(year: int) -> tuple[CatalogEntry, ...]:
    """Load and validate the packaged CA divergence catalog for ``year``.

    Fail-closed. A missing file, malformed YAML, or ANY schema violation raises
    :class:`CatalogError` whose message names the year, the offending row (id or
    index), and the specific violation.
    """
    try:
        text = _read_catalog_text(year)
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise CatalogError(f"[{year}] catalog file could not be read: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogError(f"[{year}] malformed YAML: {exc}") from exc

    _require(isinstance(raw, list), year, "<file>", "top-level document must be a list of rows")
    assert isinstance(raw, list)

    entries = tuple(_build_entry(year, i, row) for i, row in enumerate(raw))

    seen: dict[str, int] = {}
    for i, entry in enumerate(entries):
        if entry.id in seen:
            raise CatalogError(
                f"[{year}] row[{i}] id={entry.id!r}: duplicate id "
                f"(first seen at row[{seen[entry.id]}])"
            )
        seen[entry.id] = i

    return entries
