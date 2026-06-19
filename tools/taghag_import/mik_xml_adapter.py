"""Adapter for reading Mixed In Key energy cue points from Rekordbox XML exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


DEFAULT_XML_PATH = "/Users/g/Documents/downloaded.xml"


def get_mik_energy_shifts(
    filename: str,
    xml_path: str = DEFAULT_XML_PATH,
) -> list[dict]:
    """Extract MIK Energy cue points for a track from the Rekordbox XML.

    Returns a list of dicts: [{"time_s": 48.2, "energy": 6}, ...]
    sorted chronologically with duplicates removed.
    """
    # Parse filename: Artist - (Year) Album - XX Title.flac.
    match = re.match(r"^(.*?)\s+[-\u2013]\s+\(\d{4}\).*?\s+[-\u2013]\s+\d+ (.*?)\.flac", filename)
    if not match:
        return []

    artist = match.group(1).strip().lower()
    title = match.group(2).strip().lower()

    xml_file = Path(xml_path)
    if not xml_file.exists():
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for track in root.findall(".//TRACK"):
            t_artist = track.get("Artist", "").strip().lower()
            t_name = track.get("Name", "").strip().lower()

            if t_artist == artist and t_name == title:
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

                # Deduplicate (Rekordbox exports colored + plain cues at same timestamp)
                unique: list[dict] = []
                seen_times: set[float] = set()
                for time_s, energy in shifts:
                    if time_s not in seen_times:
                        unique.append({"time_s": round(time_s, 2), "energy": energy})
                        seen_times.add(time_s)

                return unique
    except Exception as e:
        print(f"Error reading MIK XML: {e}")

    return []


def get_mik_bpm(
    filename: str,
    xml_path: str = DEFAULT_XML_PATH,
) -> float | None:
    """Extract BPM for a track from the Rekordbox XML (AverageBpm attribute)."""
    match = re.match(r"^(.*?)\s+[-\u2013]\s+\(\d{4}\).*?\s+[-\u2013]\s+\d+ (.*?)\.flac", filename)
    if not match:
        return None

    artist = match.group(1).strip().lower()
    title = match.group(2).strip().lower()

    xml_file = Path(xml_path)
    if not xml_file.exists():
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for track in root.findall(".//TRACK"):
            t_artist = track.get("Artist", "").strip().lower()
            t_name = track.get("Name", "").strip().lower()

            if t_artist == artist and t_name == title:
                bpm_str = track.get("AverageBpm")
                if bpm_str:
                    return round(float(bpm_str), 2)
    except Exception:
        pass

    return None
