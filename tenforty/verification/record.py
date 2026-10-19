"""What every emit filled, as an ``EmitRecord`` (spec §7; ruling A6).

``fill`` (``tenforty.verification.fill``) adds one ``RecordedForm`` per
filled form to the emit's ``EmitRecorder``. Every emitting entry point
returns the record: its paths dict becomes an ``EmitResult`` (a ``dict`` of
emitted name -> PDF path carrying ``.record``), and the amendment packet's
``PacketManifest`` carries ``.record``. Existing ``result["f1040"]`` indexing
is unchanged.

Read ``.record`` from the DIRECT return value: ``dict(result)``,
``{**result}`` and comprehensions build a plain dict and drop the record.
"""
import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tenforty.verification.fill import FillSpec


@dataclasses.dataclass(frozen=True)
class RecordedForm:
    """One filled form: its catalog identity, the copy it is (a K-1's
    shareholder, a Schedule C's business, a Form 4562's activity; None for
    a single copy), the EXACT values object it was filled from, the final
    fill spec (after any extend/flatten), the delivered PDF, and the blank
    template it was filled from (the ink check's baseline)."""
    form: tuple[str, str]
    key: int | str
    copy_id: str | None
    values: Mapping
    spec: "FillSpec"
    pdf_path: Path
    template: Path | None = None


class EmitRecord(tuple):
    """The ``RecordedForm``s of one emit, in fill order."""


class EmitRecorder:
    """Collects ``RecordedForm``s during one emit."""

    def __init__(self) -> None:
        self._forms: list[RecordedForm] = []

    def add(self, form: RecordedForm) -> None:
        self._forms.append(form)

    def relocate(self, old: Path, new: Path) -> None:
        """The delivered file moved (the amended 540's rename): the record
        describes the artifact as delivered."""
        moved = [i for i, f in enumerate(self._forms) if f.pdf_path == old]
        if len(moved) != 1:
            raise ValueError(
                f"relocate: expected exactly one recorded form at {old}, "
                f"found {len(moved)}")
        i = moved[0]
        self._forms[i] = dataclasses.replace(self._forms[i], pdf_path=new)

    def record(self) -> EmitRecord:
        return EmitRecord(self._forms)


class EmitResult(dict[str, Path]):
    """An emit's ``{emitted name: path}`` dict that also carries ``.record``
    (always present; empty when nothing was filled)."""

    def __init__(self, paths: Mapping[str, Path] = (),
                 record: EmitRecord | None = None) -> None:
        super().__init__(paths)
        self.record: EmitRecord = record if record is not None else EmitRecord()
