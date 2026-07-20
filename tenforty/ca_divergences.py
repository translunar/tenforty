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

import difflib
import importlib.resources
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable

import yaml

from tenforty.models import (
    CASchCAAdjustment,
    DivergenceDirection,
    DivergenceSource,
)

if TYPE_CHECKING:  # import only for typing; predicates touch attributes, not the class
    from tenforty.models import Scenario

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_RESOURCE_PACKAGE = "tenforty.params.california.divergences"


class CatalogDirection(str, Enum):
    """Direction of a Schedule CA adjustment as recorded in the catalog.

    ``ADD``/``SUB`` map to :class:`tenforty.models.DivergenceDirection` later;
    ``BOTH`` resolves to a concrete direction at input time (a later part).

    DIRECTION IS THE FORM COLUMN, EVERYWHERE. ``SUB`` means the Schedule CA
    (540) Column B cell; ``ADD`` means the Column C cell — the literal column
    the FTB Pub 1001 / Schedule CA instructions print the item in, NOT an
    income-effect judgment. This matters because the kernel partitions Part I by
    section (see ``forms.sch_ca.compute``, bug #11): Part I line 27 nets
    Section C (line 27 = line 10 income − line 26 §C adjustments, per column), so
    a §C Column-B (``SUB``) entry has the OPPOSITE income effect of a §A/§B
    Column-B entry — a §C subtraction RAISES CA AGI. Record the printed column
    and let the kernel's line-27 netting resolve the sign.
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
    pub1001_page: int | str | None
    ircrtc: str
    # Some divergences are documented only in the Schedule CA (540) instructions,
    # not in FTB Pub 1001. Such rows carry `source_citation` (a non-empty string)
    # and a null `pub1001_page`; every row must carry at least one of the two.
    source_citation: str | None = None
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
        "source_citation",
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

    # Source discipline. A row's basis is either a Pub 1001 page (int, or a
    # documented non-empty string sentinel) or a Schedule CA (540) instructions
    # citation (`source_citation`, a non-empty string). TYPE-check whichever is
    # present, then fail-closed if the row carries NEITHER usable source.
    pub1001_page = raw.get("pub1001_page")
    page_is_usable = (
        isinstance(pub1001_page, int) and not isinstance(pub1001_page, bool)
    ) or (isinstance(pub1001_page, str) and bool(pub1001_page.strip()))
    if pub1001_page is not None:
        _require(
            page_is_usable,
            year,
            where,
            "`pub1001_page` must be an int (or a documented non-empty string "
            "sentinel) when present",
        )

    source_citation = raw.get("source_citation")
    if source_citation is not None:
        _require(
            isinstance(source_citation, str) and bool(source_citation.strip()),
            year,
            where,
            "`source_citation` must be a non-empty string when present",
        )
    citation_is_usable = isinstance(source_citation, str) and bool(
        source_citation.strip()
    )

    _require(
        page_is_usable or citation_is_usable,
        year,
        where,
        "row has no source: set pub1001_page or source_citation",
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
    # Membership gate: every trigger name must be a key of the closed
    # TRIGGER_PREDICATES registry. An unknown name is a fail-closed schema error.
    for name in triggers_raw:
        _require(
            isinstance(name, str) and name in TRIGGER_PREDICATES,
            year,
            where,
            f"unknown trigger {name!r} — not in TRIGGER_PREDICATES",
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
        source_citation=source_citation,
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


class UnknownDivergenceIdError(CatalogError):
    """Raised when a scenario references a divergence id absent from the
    year's catalog. The message names the bad id and the year, and — when
    :func:`difflib.get_close_matches` finds one — a did-you-mean suggestion
    (so a typo like 'non-ca-muni-intrest' points at 'non-ca-muni-interest')."""


def resolve_divergence_id(year: int, divergence_id: str) -> CatalogEntry:
    """Return the ``year`` catalog entry whose id is ``divergence_id``.

    Ids are YEAR-SCOPED: an id valid in an adjacent year but absent from
    ``year`` raises :class:`UnknownDivergenceIdError` (with a suggestion),
    never silently resolves against another year.
    """
    catalog = load_catalog(year)
    for entry in catalog:
        if entry.id == divergence_id:
            return entry
    matches = difflib.get_close_matches(
        divergence_id, [entry.id for entry in catalog], n=1
    )
    suggestion = f"; did you mean {matches[0]!r}?" if matches else ""
    raise UnknownDivergenceIdError(
        f"unknown divergence id {divergence_id!r} for {year}{suggestion}"
    )


def materialize_user_divergence(
    entry: CatalogEntry, amount: float, direction: str | None
) -> CASchCAAdjustment:
    """Materialize a user-supplied ``{id, amount, direction?}`` into a typed
    :class:`~tenforty.models.CASchCAAdjustment`, enforcing the RULED direction
    rules (2026-07-19) so a user row can never disagree with the catalog:

    - ``amount`` must be ``> 0`` (zero or negative is a load error).
    - An ADD or SUB catalog row FIXES the column: the user must NOT supply a
      ``direction`` key (the catalog decides). Present → load error.
    - A BOTH catalog row REQUIRES ``direction`` of ``"add"`` or ``"sub"``.
      Absent (or any other value) → load error naming the two legal values.

    ``source`` is stamped ``USER``; ``catalog_id`` / ``sch_ca_line`` /
    ``description`` come from the catalog entry; only ``amount`` (and, for BOTH
    rows, the resolved column) come from the user.
    """
    if amount <= 0:
        raise ValueError(
            f"divergence {entry.id!r}: amount must be > 0, got {amount!r} "
            f"(a zero or negative divergence amount is a load error)."
        )

    if entry.direction in (CatalogDirection.ADD, CatalogDirection.SUB):
        if direction is not None:
            raise ValueError(
                f"divergence {entry.id!r}: the catalog fixes this row's column "
                f"to {entry.direction.value!r}; do not supply a `direction` key."
            )
        resolved = (
            DivergenceDirection.ADDITION
            if entry.direction is CatalogDirection.ADD
            else DivergenceDirection.SUBTRACTION
        )
    else:  # CatalogDirection.BOTH
        if direction not in ("add", "sub"):
            raise ValueError(
                f"divergence {entry.id!r}: this is a BOTH row; supply "
                f'`direction: "add"` or `direction: "sub"` '
                f"(got {direction!r})."
            )
        resolved = (
            DivergenceDirection.ADDITION
            if direction == "add"
            else DivergenceDirection.SUBTRACTION
        )

    return CASchCAAdjustment(
        source=DivergenceSource.USER,
        sch_ca_line=entry.sch_ca_line,
        direction=resolved,
        amount=amount,
        description=entry.description,
        catalog_id=entry.id,
    )


# --- Trigger-predicate registry (spec §2.4) -----------------------------------
#
# The CLOSED vocabulary of trigger predicates. Each is a pure, side-effect-free
# ``Scenario -> bool`` that inspects only the scenario's declared inputs (no
# compute, no derived state). A catalog row's ``triggers`` value must (in a LATER
# step) be a key of this dict; an unknown trigger name will become a catalog-load
# error once assignments land, but that gate is NOT wired here.


def has_tax_exempt_interest(scenario: "Scenario") -> bool:
    """True iff any Form 1099-INT carries positive tax-exempt interest."""
    return any(f.tax_exempt_interest > 0 for f in scenario.form1099_int)


def has_k1(scenario: "Scenario") -> bool:
    """True iff the scenario carries at least one Schedule K-1."""
    return bool(scenario.schedule_k1s)


def has_rental_depreciation(scenario: "Scenario") -> bool:
    """True iff any rental property carries positive depreciation."""
    return any(p.depreciation > 0 for p in scenario.rental_properties)


def has_capital_gain_distributions(scenario: "Scenario") -> bool:
    """True iff any Form 1099-DIV carries positive capital gain distributions."""
    return any(f.capital_gain_distributions > 0 for f in scenario.form1099_div)


def has_state_tax_refund(scenario: "Scenario") -> bool:
    """True iff any Form 1099-G carries a positive state tax refund."""
    return any(f.state_tax_refund > 0 for f in scenario.form1099_g)


TRIGGER_PREDICATES: dict[str, Callable[["Scenario"], bool]] = {
    "has_tax_exempt_interest": has_tax_exempt_interest,
    "has_k1": has_k1,
    "has_rental_depreciation": has_rental_depreciation,
    "has_capital_gain_distributions": has_capital_gain_distributions,
    "has_state_tax_refund": has_state_tax_refund,
}
