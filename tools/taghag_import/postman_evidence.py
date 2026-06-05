from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
    for line in stdout.splitlines():
        marker_index = line.find(MARKER)
        if marker_index == -1:
            continue
        payload = line[marker_index + len(MARKER) :].strip()
        if not payload:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            brace_index = payload.find("{")
            if brace_index == -1:
                continue
            try:
                obj = json.loads(payload[brace_index:])
            except json.JSONDecodeError:
                continue
        if isinstance(obj, dict) and str(obj.get("schema", "")).startswith(
            "tagslut.postman.tag_evidence"
        ):
            evidences.append(obj)
    return evidences


def parse_postman_evidence(log_path: str | Path) -> list[dict[str, object]]:
    path = Path(log_path).expanduser().resolve()
    return parse_tag_evidence(path.read_text(encoding="utf-8"))


def merge_tag_evidence(evidences: list[dict[str, object]]) -> ResolvedTags:
    winners: dict[str, tuple[float, str, str]] = {}
    matched: list[str] = []
    statuses: dict[str, str] = {}
    isrc = ""

    for evidence in evidences:
        provider = str(evidence.get("provider") or "").lower()
        status = str(evidence.get("status") or "error")
        statuses[provider] = status
        if not isrc:
            isrc = str(evidence.get("lookup_isrc") or "")
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
