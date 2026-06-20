"""Adapter for reading Mixed In Key energy cue points and BPM from Rekordbox XML exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]

# Full Rekordbox collection export: rich per-track attributes (AverageBpm,
# Tonality, Artist, Name, Location) but POSITION_MARK cues are sparse -- most
# tracks have zero "Energy N" marks.
DEFAULT_XML_PATH = "/Users/g/Documents/downloaded.xml"

# Cue-dense Rekordbox/MIK export covering a smaller batch of tracks: only
# TrackID/Location/TotalTime attributes (no Artist/Name/AverageBpm), so a
# track can only be matched by file path -- but "Energy N" marks are present
# on nearly every track.
MIK_CUES_XML_PATH = str(REPO_ROOT / "rekordbox_mikcues_001.xml")

_FILENAME_RE = re.compile(r"^(.*?)\s+[-–]\s+\(\d{4}\).*?\s+[-–]\s+\d+ (.*?)\.flac")


def _parse_artist_title(filename: str) -> tuple[str, str] | None:
    """Parse 'Artist - (Year) Album - NN Title.flac' into (artist, title), lowercased."""
    match = _FILENAME_RE.match(filename)
    if not match:
        return None
    return match.group(1).strip().lower(), match.group(2).strip().lower()


def _location_basename(location: str | None) -> str | None:
    """Decode a Rekordbox 'Location' file:// URL into a bare filename."""
    if not location:
        return None
    decoded = unquote(urlparse(location).path)
    return Path(decoded).name or None


class _XmlIndex:
    __slots__ = ("by_artist_title", "by_basename")

    def __init__(self) -> None:
        self.by_artist_title: dict[tuple[str, str], ET.Element] = {}
        self.by_basename: dict[str, ET.Element] = {}


@lru_cache(maxsize=8)
def _load_index(xml_path: str) -> _XmlIndex:
    """Parse a Rekordbox XML export once and index its TRACK elements.

    Indexed by both (artist, title) -- when Artist/Name attributes are
    present -- and by decoded Location basename, since some exports (e.g.
    MIK cue-only exports) carry no Artist/Name at all.
    """
    index = _XmlIndex()
    if not Path(xml_path).exists():
        return index
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return index

    for track in root.findall(".//TRACK"):
        artist = track.get("Artist", "").strip().lower()
        name = track.get("Name", "").strip().lower()
        if artist and name:
            index.by_artist_title[(artist, name)] = track
        basename = _location_basename(track.get("Location"))
        if basename:
            index.by_basename[basename] = track
    return index


def _find_track(filename: str, xml_path: str) -> ET.Element | None:
    index = _load_index(xml_path)
    track = index.by_basename.get(filename)
    if track is not None:
        return track
    parsed = _parse_artist_title(filename)
    if parsed is not None:
        return index.by_artist_title.get(parsed)
    return None


def _energy_shifts_from_track(track: ET.Element) -> list[dict]:
    shifts: list[tuple[float, int]] = []
    for mark in track.findall("POSITION_MARK"):
        name = mark.get("Name", "")
        if name.startswith("Energy "):
            try:
                energy_val = int(name.split(" ")[1])
            except (IndexError, ValueError):
                continue
            start = float(mark.get("Start", 0))
            shifts.append((start, energy_val))

    shifts.sort(key=lambda x: x[0])

    # Deduplicate (Rekordbox exports colored + plain cues at the same timestamp)
    unique: list[dict] = []
    seen_times: set[float] = set()
    for time_s, energy in shifts:
        if time_s not in seen_times:
            unique.append({"time_s": round(time_s, 2), "energy": energy})
            seen_times.add(time_s)
    return unique


def get_mik_energy_shifts(
    filename: str,
    xml_paths: tuple[str, ...] = (MIK_CUES_XML_PATH, DEFAULT_XML_PATH),
) -> list[dict]:
    """Extract MIK Energy cue points for a track from Rekordbox XML exports.

    Tries each XML source in order (the cue-dense export first, then the
    full collection export) and returns the first non-empty result, matching
    tracks by file path when possible and falling back to an Artist/Title
    parse of `filename`.

    Returns a list of dicts: [{"time_s": 48.2, "energy": 6}, ...]
    sorted chronologically with duplicates removed.
    """
    for xml_path in xml_paths:
        track = _find_track(filename, xml_path)
        if track is None:
            continue
        shifts = _energy_shifts_from_track(track)
        if shifts:
            return shifts
    return []


def get_mik_bpm(
    filename: str,
    xml_path: str = DEFAULT_XML_PATH,
) -> float | None:
    """Extract the Rekordbox-owned reference BPM for a track (AverageBpm attribute)."""
    track = _find_track(filename, xml_path)
    if track is None:
        return None
    bpm_str = track.get("AverageBpm")
    if not bpm_str:
        return None
    try:
        return round(float(bpm_str), 2)
    except ValueError:
        return None
