"""The runtime gate (spec §8): refuses a fill that would leave a declared
line with a computed value blank. Implemented by the runtime-gate lane; until
then ``check`` is a no-op hook that ``fill`` already calls before the
template is opened."""
from collections.abc import Mapping


def check(form: tuple[str, str], key: int | str, spec, values: Mapping) -> None:
    """No-op until the runtime-gate lane lands (inactive for pending forms)."""
    return None
