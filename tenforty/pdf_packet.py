"""Assemble emitted form PDFs into combined per-filing packets.

A return run emits many loose form PDFs, keyed by form name in the
``emitted`` dict the orchestrator returns. For filing and review those forms
belong together as packets — one combined PDF per logical filing, ordered the
way the IRS / FTB expect (attachment sequence).

This module is pure file assembly: it consumes the ``emitted`` form-key → Path
mapping and concatenates member PDFs with pypdf. It performs no tax compute.

Three packets are defined:
- ``federal_individual`` — Form 1040 + its schedules/forms (attachment order).
- ``federal_corporate`` — Form 1120-S + one Schedule K-1 per shareholder + one
  §199A Statement A per shareholder. An 1120-S is a separate filing from the
  1040, so it is never folded into the individual packet.
- ``california`` — Form 540 + Schedule CA (540) + Schedule D (540).

Two design choices keep this robust as forms/shareholders are added:
- **Key-family membership.** A member is either an exact emitted-key
  (``sch_d``) or a family (``1120s_k1`` matching ``1120s_k1_<int>`` keys,
  sorted *numerically* by suffix so ``_10`` follows ``_2``).
- **Partition invariant.** Every emitted key must be claimed by exactly one
  packet or be the explicit standalone exception (Form 4868, an extension
  request — a separate filing, not part of any return). ``classify_key``
  backs a test that fails loudly when a new form is left unplaced, rather than
  letting it silently vanish from every packet.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pypdf


@dataclass(frozen=True)
class PacketMember:
    """One ordered slot in a packet.

    ``key`` is an exact emitted-key by default. When ``family`` is True it is
    a prefix matching ``<key>_<int>`` emitted-keys, contributed in ascending
    numeric order of the integer suffix.
    """

    key: str
    family: bool = False


@dataclass(frozen=True)
class Packet:
    """A logical filing assembled from member forms, in declaration order."""

    name: str
    filename_template: str  # e.g. "f1040_{year}_complete.pdf"
    members: tuple[PacketMember, ...] = field(default_factory=tuple)


# Federal individual — members in IRS attachment-sequence order:
#   1040 (main), Sch 1 (01), Sch A (07), Sch B (08), Sch D (12),
#   Form 8949 (12A), Sch E (13), Form 8995 (55), Form 8959 (71),
#   Form 8582 (88), Form 4562 (179).
FEDERAL_INDIVIDUAL = Packet(
    name="federal_individual",
    filename_template="f1040_{year}_complete.pdf",
    members=(
        PacketMember("1040"),
        PacketMember("sch_1"),
        PacketMember("sch_a"),
        PacketMember("sch_b"),
        PacketMember("sch_d"),
        PacketMember("f8949"),
        PacketMember("sch_e"),
        PacketMember("f8995"),
        PacketMember("8959"),
        PacketMember("f8582"),
        PacketMember("f4562"),
    ),
)

# Federal corporate — the 1120-S main form followed by every shareholder's
# Schedule K-1, followed by every shareholder's §199A Statement A (filed
# together as the corporate return).
FEDERAL_CORPORATE = Packet(
    name="federal_corporate",
    filename_template="f1120s_{year}_complete.pdf",
    members=(
        PacketMember("1120s"),
        PacketMember("1120s_k1", family=True),
        PacketMember("1120s_k1_qbi_stmt", family=True),
    ),
)

# California — Form 540 followed by its supporting schedules (FTB order).
CALIFORNIA = Packet(
    name="california",
    filename_template="f540_{year}_complete.pdf",
    members=(
        PacketMember("f540"),
        PacketMember("sch_ca"),
        PacketMember("sch_d_540"),
    ),
)

PACKETS: tuple[Packet, ...] = (FEDERAL_INDIVIDUAL, FEDERAL_CORPORATE, CALIFORNIA)

# Emitted keys that belong to no packet — separate filings or non-return
# artifacts. Form 4868 (extension request) is filed on its own, so it stays a
# standalone loose PDF rather than being folded into the 1040 packet.
STANDALONE_KEYS: frozenset[str] = frozenset({"4868"})


def _family_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(prefix)}_(\d+)$")


def ordered_members(emitted: dict[str, Path], packet: Packet) -> list[Path]:
    """Return the paths in ``emitted`` belonging to ``packet``, in packet order.

    Exact members contribute their path when present; family members
    contribute every matching ``<prefix>_<int>`` path, numerically sorted by
    the integer suffix. Absent members are skipped.
    """
    paths: list[Path] = []
    for member in packet.members:
        if member.family:
            pattern = _family_pattern(member.key)
            matches: list[tuple[int, Path]] = []
            for key, path in emitted.items():
                m = pattern.match(key)
                if m:
                    matches.append((int(m.group(1)), path))
            paths.extend(path for _, path in sorted(matches))
        elif member.key in emitted:
            paths.append(emitted[member.key])
    return paths


def classify_key(key: str) -> str | None:
    """Return which packet claims ``key``.

    Returns the packet name, ``"standalone"`` for a standalone-exception key
    (Form 4868), or ``None`` when no packet or exception claims it — a
    partition gap that the invariant test surfaces.
    """
    if key in STANDALONE_KEYS:
        return "standalone"
    for packet in PACKETS:
        for member in packet.members:
            if member.family:
                if _family_pattern(member.key).match(key):
                    return packet.name
            elif key == member.key:
                return packet.name
    return None


def assemble_packet(paths: list[Path], output_path: Path) -> Path:
    """Concatenate ``paths`` (in order) into a single PDF at ``output_path``."""
    writer = pypdf.PdfWriter()
    for path in paths:
        writer.append(str(path))
    with open(output_path, "wb") as f:
        writer.write(f)
    writer.close()
    return output_path


def assemble_all(
    emitted: dict[str, Path], output_dir: Path, year: int
) -> dict[str, Path]:
    """Assemble every packet that has at least one member present in ``emitted``.

    Returns ``{packet_name: combined_pdf_path}``. Packets with no present
    members are skipped (e.g. ``federal_corporate`` for a return with no
    S-corp).
    """
    combined: dict[str, Path] = {}
    for packet in PACKETS:
        paths = ordered_members(emitted, packet)
        if not paths:
            continue
        output_path = output_dir / packet.filename_template.format(year=year)
        assemble_packet(paths, output_path)
        combined[packet.name] = output_path
    return combined
