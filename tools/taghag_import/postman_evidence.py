from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

MARKER = "[Tag Evidence JSON]"
AUTHORITY_BONUS = 0.05
QOBUZ_DAMP = 0.5
FIELD_AUTHORITY = {
    "canonical_label": "beatport",
    "canonical_genre": "beatport",
    "bpm": "beatport",
    "key": "beatport",
    "canonical_title": "tidal",
    "isrc": "tidal",
    "canonical_album": "spotify",
}
FIELD_NAME_MAP = {
    "canonical_title": "title",
    "canonical_artist_credit": "artist",
    "canonical_album": "album",
    "canonical_label": "label",
    "canonical_genre": "genre",
}


@dataclass
class ResolvedTags:
    isrc: str
    title: str = ""
    artist: str = ""
    album: str = ""
    label: str = ""
    genre: str = ""
    catalog_number: str = ""
    release_date: str = ""
    year: str = ""
    spotify_id: str = ""
    beatport_album_id: str = ""
    beatport_track_id: str = ""
    field_sources: dict[str, str] = field(default_factory=dict)
    providers_matched: list[str] = field(default_factory=list)
    raw_status: dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any([self.title, self.artist, self.album, self.label, self.genre])


def _year_from_date(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", value or "")
    return match.group(0) if match else ""


def parse_tag_evidence(stdout: str) -> list[dict[str, object]]:
    evidences: list[dict[str, object]] = []
    decoder = json.JSONDecoder()
    cleaned_lines = [
        re.sub(r"^\s*\|\s?", "", line.rstrip())
        for line in stdout.splitlines()
    ]
    normalized = "".join(cleaned_lines)
    search_from = 0

    while True:
        marker_index = normalized.find(MARKER, search_from)
        if marker_index == -1:
            break
        next_marker = normalized.find(MARKER, marker_index + len(MARKER))
        segment_end = next_marker if next_marker != -1 else len(normalized)
        brace_index = normalized.find("{", marker_index + len(MARKER), segment_end)
        raw_marker = normalized[marker_index:segment_end].strip()
        if brace_index == -1:
            if raw_marker:
                evidences.append({"status": "malformed", "raw_line": raw_marker})
            search_from = segment_end
            continue

        try:
            obj, consumed = decoder.raw_decode(normalized[brace_index:])
        except json.JSONDecodeError:
            evidences.append({"status": "malformed", "raw_line": raw_marker})
            search_from = segment_end
            continue
        if isinstance(obj, dict):
            evidences.append(obj)
        search_from = brace_index + consumed
    return evidences


def parse_postman_evidence(log_path: str | Path) -> list[dict[str, object]]:
    path = Path(log_path).expanduser().resolve()
    return parse_tag_evidence(path.read_text(encoding="utf-8"))


def merge_tag_evidence(evidences: list[dict[str, object]]) -> ResolvedTags:
    winners: dict[str, tuple[float, str, str]] = {}
    matched: list[str] = []
    statuses: dict[str, str] = {}
    isrc = ""
    spotify_id = ""
    beatport_album_id = ""
    beatport_track_id = ""

    for evidence in evidences:
        provider = str(evidence.get("provider") or "").lower()
        status = str(evidence.get("status") or "error")
        statuses[provider] = status
        if not isrc:
            isrc = str(evidence.get("lookup_isrc") or "")
            
        if provider == "spotify" and (evidence.get("provider_track_id") or evidence.get("id")):
            spotify_id = str(evidence.get("provider_track_id") or evidence.get("id"))
        if provider == "beatport":
            if evidence.get("provider_track_id") or evidence.get("id"):
                beatport_track_id = str(evidence.get("provider_track_id") or evidence.get("id"))

        if status != "matched":
            continue

        matched.append(provider)
        for candidate in evidence.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue

            for our_key, raw_key in (
                ("catalog_number", "catalog_number"),
                ("release_date", "release_date"),
            ):
                value = str(candidate.get(raw_key) or "").strip()
                if not value:
                    continue
                score = 0.80 + (
                    AUTHORITY_BONUS if FIELD_AUTHORITY.get(our_key) == provider else 0.0
                )
                if provider == "qobuz":
                    score *= QOBUZ_DAMP
                current = winners.get(our_key)
                if current is None or score > current[0]:
                    winners[our_key] = (score, value, provider)
                    
            if provider == "beatport":
                album = candidate.get("album") or candidate.get("release") or {}
                if isinstance(album, dict) and album.get("id"):
                    beatport_album_id = str(album["id"])
                elif candidate.get("album_id") or candidate.get("release_id"):
                    beatport_album_id = str(candidate.get("album_id") or candidate.get("release_id"))

            for field_candidate in candidate.get("field_candidates", []) or []:
                if not isinstance(field_candidate, dict):
                    continue
                field_name = str(field_candidate.get("field_name") or "")
                our_key = FIELD_NAME_MAP.get(field_name)
                if not our_key:
                    continue
                value = str(field_candidate.get("normalized_value") or "").strip()
                if not value:
                    continue
                score = float(field_candidate.get("confidence") or 0.0)
                if FIELD_AUTHORITY.get(field_name) == provider:
                    score += AUTHORITY_BONUS
                if provider == "qobuz":
                    score *= QOBUZ_DAMP
                current = winners.get(our_key)
                if current is None or score > current[0]:
                    winners[our_key] = (score, value, provider)

    resolved = ResolvedTags(
        isrc=isrc,
        spotify_id=spotify_id,
        beatport_album_id=beatport_album_id,
        beatport_track_id=beatport_track_id,
        providers_matched=matched,
        raw_status=statuses,
    )
    for key, (score, value, provider) in winners.items():
        setattr(resolved, key, value)
        resolved.field_sources[key] = f"{provider}:{score:.2f}"
    resolved.year = _year_from_date(resolved.release_date)
    return resolved


def resolve_tag_evidence(stdout: str) -> ResolvedTags | None:
    evidences = parse_tag_evidence(stdout)
    if not evidences:
        return None
    resolved = merge_tag_evidence(evidences)
    if not resolved.providers_matched or resolved.is_empty():
        return None
    return resolved


def evidence_lookup_key(evidence: dict[str, object]) -> str:
    for key in ("lookup_isrc", "query", "isrc", "lookup_key"):
        value = str(evidence.get(key) or "").strip()
        if value:
            return value
    return ""


def evidence_confidence(evidence: dict[str, object]) -> float | None:
    if evidence.get("confidence") is not None:
        try:
            return float(evidence["confidence"])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    best = None
    for candidate in evidence.get("candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        for field_candidate in candidate.get("field_candidates", []) or []:
            if not isinstance(field_candidate, dict):
                continue
            try:
                score = float(field_candidate.get("confidence"))
            except (TypeError, ValueError):
                continue
            best = score if best is None else max(best, score)
    return best


def evidence_to_row(
    evidence: dict[str, object],
    *,
    lookup_type: str = "isrc",
    lookup_key: str | None = None,
) -> dict[str, object]:
    status = str(evidence.get("status") or "malformed")
    candidates = evidence.get("candidates")
    if not isinstance(candidates, list):
        candidates = []

    winning_fields: dict[str, object] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for field_candidate in candidate.get("field_candidates", []) or []:
            if not isinstance(field_candidate, dict):
                continue
            field_name = str(field_candidate.get("field_name") or "")
            value = field_candidate.get("normalized_value")
            if field_name and value is not None:
                winning_fields[field_name] = value

    return {
        "provider": str(evidence.get("provider") or "unknown"),
        "lookup_type": lookup_type,
        "lookup_key": lookup_key if lookup_key is not None else evidence_lookup_key(evidence),
        "provider_track_id": evidence.get("provider_track_id") or evidence.get("track_id") or evidence.get("id"),
        "status": status,
        "confidence": evidence_confidence(evidence),
        "winning_fields_json": winning_fields,
        "candidates_json": candidates,
        "raw_marker_json": evidence,
        "fetched_at": str(evidence.get("fetched_at") or datetime.now(UTC).isoformat()),
    }
