"""Normalize heterogeneous musical-key notations to Camelot.

The tagger ingests keys from many providers, so `dj_tag.musical_key` carries at
least four notations in the wild:

* spelled out — ``A Minor``, ``B-flat Major`` (incl. Unicode ``B♭``/``F♯``)
* compact     — ``Am``, ``F#m``, ``Bbm`` (trailing ``m`` => minor)
* already Camelot — ``8A``, ``6B``
* OpenKey-style ``<n>M`` — ambiguous; not mapped without provider provenance

A single ``to_camelot`` entry point folds the first three into the Camelot wheel
and reports *why* an input could not be mapped, so callers can audit coverage
rather than silently dropping rows.
"""

from __future__ import annotations

import re

# Camelot wheel: minor keys = A ring, major keys = B ring.
_MINOR = {
    "Ab": "1A", "G#": "1A", "Eb": "2A", "D#": "2A", "Bb": "3A", "A#": "3A",
    "F": "4A", "C": "5A", "G": "6A", "D": "7A", "A": "8A", "E": "9A",
    "B": "10A", "F#": "11A", "Gb": "11A", "Db": "12A", "C#": "12A",
}
_MAJOR = {
    "B": "1B", "F#": "2B", "Gb": "2B", "Db": "3B", "C#": "3B", "Ab": "4B",
    "G#": "4B", "Eb": "5B", "D#": "5B", "Bb": "6B", "A#": "6B", "F": "7B",
    "C": "8B", "G": "9B", "D": "10B", "A": "11B", "E": "12B",
}

_CAMELOT_RE = re.compile(r"^(1[0-2]|[1-9])[AB]$")
_OPENKEY_RE = re.compile(r"^\d+[Md]$")  # e.g. "1M".."12M" — needs provenance
_SPELLED_RE = re.compile(r"^([A-Ga-g][#b]?)\s*(minor|min|major|maj)$", re.IGNORECASE)
_COMPACT_RE = re.compile(r"^([A-Ga-g](?:#|b|sharp|flat)?)(m)?$", re.IGNORECASE)

_SENTINELS = {"UNKNOWN", "NONE", "N/A", "NA", ""}


def _normalize_root(root: str) -> str:
    """Canonicalize an accidental-bearing root note, e.g. ``c#``/``CSharp`` -> ``C#``."""
    root = root.replace("♯", "#").replace("♭", "b")
    root = root[0].upper() + root[1:].lower()
    return root.replace("sharp", "#").replace("flat", "b")


def to_camelot(key: str | None) -> tuple[str | None, str]:
    """Map a free-form key string to Camelot.

    Returns ``(camelot, reason)``. ``camelot`` is ``None`` when unmappable; the
    ``reason`` tag classifies the input ("spelled", "compact", "already_camelot",
    "openkey_ambiguous", "unknown_sentinel", "unrecognized") for audit reporting.
    """
    if key is None:
        return None, "unknown_sentinel"
    text = key.strip()
    if text.upper() in _SENTINELS:
        return None, "unknown_sentinel"

    if _CAMELOT_RE.match(text.upper()):
        return text.upper(), "already_camelot"
    if _OPENKEY_RE.match(text):
        return None, "openkey_ambiguous"

    unicode_folded = text.replace("♯", "#").replace("♭", "b")

    spelled = _SPELLED_RE.match(unicode_folded)
    if spelled:
        root = _normalize_root(spelled.group(1))
        minor = spelled.group(2).lower().startswith("min")
        cam = (_MINOR if minor else _MAJOR).get(root)
        return cam, ("spelled" if cam else "spelled_badroot")

    compact = _COMPACT_RE.match(unicode_folded)
    if compact:
        root = _normalize_root(compact.group(1))
        minor = bool(compact.group(2))
        cam = (_MINOR if minor else _MAJOR).get(root)
        return cam, ("compact" if cam else "compact_badroot")

    return None, "unrecognized"
