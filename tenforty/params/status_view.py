"""Per-status projection of a params object (spec §6 status accessor).

Every per-status params lookup goes through ``params.for_status(status)``,
which returns a :class:`StatusView`. Reading a per-status field off the view
returns that status's column; a missing column, or a field still pending
transcription (None), raises :class:`UnsupportedStatusError` (never a bare
``KeyError`` or ``TypeError``, never another status's column). Fields that
are not per-status pass through unchanged.

This is the single chokepoint the params-completeness gate tests, so adding a
(year, status) is a params-and-battery exercise with no form-code changes.
"""
from collections.abc import Collection
from typing import Any

from tenforty.models import FilingStatus, parse_filing_status


class UnsupportedStatusError(NotImplementedError):
    """A per-status params field has no column for the requested status.

    Subclasses NotImplementedError so existing fail-closed refusal handling
    treats it as an unsupported-scope refusal."""

    def __init__(self, field: str, year: int, status: Any, *,
                 pending: bool = False) -> None:
        self.field = field
        self.year = year
        self.status = status
        self.pending = pending
        value = getattr(status, "value", status)
        if pending:
            super().__init__(
                f"params field {field!r} is pending transcription for tax "
                f"year {year} (no column for any status, including "
                f"{value!r}); refusing rather than read an untranscribed "
                f"value")
            return
        super().__init__(
            f"params field {field!r} has no {value!r} column for tax year "
            f"{year}; this (year, filing status) is not supported")


class StatusView:
    """Read-only projection of ``params`` onto one filing status."""

    __slots__ = ("_params", "_per_status_fields", "status")

    def __init__(self, params: Any, status: "FilingStatus | str",
                 per_status_fields: Collection[str]) -> None:
        object.__setattr__(self, "_params", params)
        object.__setattr__(self, "_per_status_fields", frozenset(per_status_fields))
        # Accepts the enum or its raw value string (config.filing_status may
        # be reassigned a string after construction).
        object.__setattr__(self, "status", parse_filing_status(status))

    def __getattr__(self, name: str) -> Any:
        params = object.__getattribute__(self, "_params")
        value = getattr(params, name)
        if name not in object.__getattribute__(self, "_per_status_fields"):
            return value
        status = object.__getattribute__(self, "status")
        if value is None:
            # A per-status field still pending transcription holds None on
            # every status; refuse by name, never TypeError off the None.
            raise UnsupportedStatusError(name, params.year, status,
                                         pending=True)
        try:
            return value[status.value]
        except KeyError:
            raise UnsupportedStatusError(name, params.year, status) from None

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("StatusView is read-only")

    def __repr__(self) -> str:
        return (f"StatusView(year={self._params.year!r}, "
                f"status={self.status.value!r})")
