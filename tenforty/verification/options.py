"""Which widget an option line prints into (ruled 2026-10-17; shared by the
runtime gate and the check-suite).

An option group (ruling A2) is several declared lines sharing ONE compute
key, each line naming the value that turns it ON (``selects``). On the forms
that have them, the widgets are filled by translation-only DERIVATIONS keyed
by PDF field (FTB 3532's checkboxes and radio, the 540 filing-status radio);
ruling A1 keeps those as derivations, so no key -> field mapping names them.

``option_widgets`` finds a line's widget by using the derivations as data:
it evaluates each on a ONE-KEY values dict ``{key: selects}``. A derivation
returning an ON state (anything but ``/Off`` or ``None``) names the field and
its on-state. A derivation that needs more inputs raises ``KeyError`` and is
skipped; any other exception propagates (a broken derivation fails loud).
Exactly one resolution is expected; zero or several is the caller's finding
(several is also the net under a spurious derivation that answers any input).
"""
from collections.abc import Mapping

_OFF = ("/Off", "Off")


def option_widgets(spec, key: str, selects: str) -> list[tuple[str, str]]:
    """``[(pdf field, on-state)]`` for every derivation that turns ON when
    ``key`` holds ``selects``."""
    values: Mapping[str, object] = {key: selects}
    found: list[tuple[str, str]] = []
    for field, derive in (spec.derivations or {}).items():
        try:
            result = derive(values)
        except KeyError:
            continue
        if result is None or str(result) in _OFF:
            continue
        found.append((field, str(result)))
    return found
