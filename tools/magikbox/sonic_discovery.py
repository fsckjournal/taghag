from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from psycopg2.extras import Json

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taghag_import.config import DatabaseConfig, read_database_config

from magikbox.db import dict_cursor, open_database


VECTOR_SCHEMA = "sonic7_v1"
DEFAULT_ENERGY = 5.0
DEFAULT_BPM = 120.0
ENERGY_SCALE = 10.0
BPM_MIN = 100.0
BPM_RANGE = 40.0


@dataclass(frozen=True)
class SonicPolicy:
    noise_threshold: float = 0.20
    weak_threshold: float = 0.49
    meaningful_threshold: float = 0.50
    core_identity_threshold: float = 0.80
    dynamic_evolution_delta_threshold: float = 0.40


@dataclass(frozen=True)
class ProducerVibe:
    name: str
    evidence: list[str]


@dataclass(frozen=True)
class SimilarTrack:
    path: str
    distance: float
    producer_vibes: list[str]
    sonic_vector: list[float]


@dataclass(frozen=True)
class TrackRecord:
    owner_user_id: str
    audio_file_id: str
    path: str
    analysis_id: str
    analysis_computed_at: datetime | None
    happy: float
    aggressive: float
    relaxed: float
    party: float
    danceability: float
    bpm: float | None
    energy: float | None
    raw_json: dict[str, Any]
    artist: str | None = None
    title: str | None = None
    label: str | None = None
    canonical_genre: str | None = None
    canonical_subgenre: str | None = None
    notes: str | None = None


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _coerce_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def _segment_attributes(segment: Any) -> dict[str, Any]:
    if isinstance(segment, dict):
        attrs = segment.get("attributes")
        if isinstance(attrs, dict):
            return attrs
        return segment
    return {}


def compute_dynamic_evolution(raw_json: Any, *, policy: SonicPolicy) -> tuple[bool, float | None]:
    payload = _coerce_json(raw_json)
    segments = payload.get("segments")
    if not isinstance(segments, list) or len(segments) < 2:
        return False, None

    start_attrs = _segment_attributes(segments[0])
    end_attrs = _segment_attributes(segments[-1])
    if not start_attrs or not end_attrs:
        return False, None

    delta = math.sqrt(
        sum(
            (
                _safe_float(start_attrs.get(key), 0.0) - _safe_float(end_attrs.get(key), 0.0)
            )
            ** 2
            for key in start_attrs
        )
    )
    return delta > policy.dynamic_evolution_delta_threshold, delta


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.10f}" for value in vector) + "]"


def _parse_vector_literal(value: Any) -> list[float]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        parts = [part.strip() for part in text.split(",") if part.strip()]
        result: list[float] = []
        for part in parts:
            try:
                result.append(float(part))
            except ValueError:
                return []
        return result
    if isinstance(value, Iterable):
        result: list[float] = []
        for item in value:
            safe = _safe_float(item)
            if safe is None:
                return []
            result.append(safe)
        return result
    return []


class SonicDiscoveryIndex:
    def __init__(
        self,
        *,
        policy: SonicPolicy | None = None,
        config: DatabaseConfig | None = None,
        tracks: Sequence[TrackRecord] | None = None,
    ) -> None:
        self.policy = policy or SonicPolicy()
        self.config = config or read_database_config()
        self.tracks: dict[str, TrackRecord] = {}
        if tracks is None:
            self._load_tracks()
        else:
            self.tracks = {track.path: track for track in tracks}

    @classmethod
    def from_database(
        cls,
        *,
        policy: SonicPolicy | None = None,
        config: DatabaseConfig | None = None,
    ) -> "SonicDiscoveryIndex":
        return cls(policy=policy, config=config)

    def _load_tracks(self) -> None:
        owner_user_id = self.config.owner_user_id
        if not owner_user_id:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

        sql = """
            with latest_analysis as (
                select distinct on (ta.owner_user_id, ta.audio_file_id)
                    ta.id,
                    ta.owner_user_id,
                    ta.audio_file_id,
                    ta.computed_at,
                    ta.raw_json,
                    ta.happy,
                    ta.aggressive,
                    ta.relaxed,
                    ta.party,
                    ta.danceability
                from public.track_analysis ta
                where ta.owner_user_id = %s
                order by ta.owner_user_id, ta.audio_file_id, ta.computed_at desc, ta.created_at desc, ta.id desc
            )
            select
                af.path,
                af.id as audio_file_id,
                la.id as analysis_id,
                la.owner_user_id,
                la.computed_at as analysis_computed_at,
                la.raw_json,
                la.happy,
                la.aggressive,
                la.relaxed,
                la.party,
                la.danceability,
                dt.bpm,
                dt.energy,
                dt.artist,
                dt.title,
                dt.label,
                dt.canonical_genre,
                dt.canonical_subgenre,
                dt.notes
            from latest_analysis la
            join public.audio_file af
              on af.id = la.audio_file_id
             and af.owner_user_id = la.owner_user_id
            join public.dj_tag dt
              on dt.audio_file_id = la.audio_file_id
             and dt.owner_user_id = la.owner_user_id
            order by af.path
        """
        with open_database(self.config) as conn:
            with dict_cursor(conn) as cur:
                cur.execute(sql, (owner_user_id,))
                rows = cur.fetchall()

        tracks: dict[str, TrackRecord] = {}
        for row in rows:
            raw_json = _coerce_json(row.get("raw_json"))
            track = TrackRecord(
                owner_user_id=str(row["owner_user_id"]),
                audio_file_id=str(row["audio_file_id"]),
                path=str(row["path"]),
                analysis_id=str(row["analysis_id"]),
                analysis_computed_at=row.get("analysis_computed_at"),
                happy=float(row["happy"]),
                aggressive=float(row["aggressive"]),
                relaxed=float(row["relaxed"]),
                party=float(row["party"]),
                danceability=float(row["danceability"]),
                bpm=_safe_float(row.get("bpm")),
                energy=_safe_float(row.get("energy")),
                raw_json=raw_json,
                artist=row.get("artist"),
                title=row.get("title"),
                label=row.get("label"),
                canonical_genre=row.get("canonical_genre"),
                canonical_subgenre=row.get("canonical_subgenre"),
                notes=row.get("notes"),
            )
            tracks[track.path] = track

        self.tracks = tracks

    def _track_for_path(self, path: str) -> TrackRecord | None:
        return self.tracks.get(path)

    def producer_vibes_for(self, path: str) -> list[ProducerVibe]:
        track = self._track_for_path(path)
        if track is None:
            return []

        happy = track.happy
        aggressive = track.aggressive
        relaxed = track.relaxed
        party = track.party
        danceability = track.danceability

        vibes: list[ProducerVibe] = []

        if (
            danceability >= self.policy.core_identity_threshold
            and party >= self.policy.core_identity_threshold
            and aggressive < self.policy.meaningful_threshold
        ):
            vibes.append(ProducerVibe("peak_time_house", ["high danceability", "high party", "low aggression"]))

        if happy < 0.30 and relaxed < self.policy.meaningful_threshold and aggressive < 0.60:
            vibes.append(ProducerVibe("moody_deep", ["low happy", "low relaxed", "controlled aggression"]))

        if danceability >= 0.65 and aggressive < 0.35 and happy >= 0.30:
            vibes.append(ProducerVibe("warm_dancefloor", ["good danceability", "low aggression", "warm happy"]))

        if danceability >= 0.70 and aggressive >= self.policy.meaningful_threshold and party >= 0.40:
            vibes.append(ProducerVibe("driving_tool", ["good danceability", "high aggression", "some party"]))

        if party < self.policy.meaningful_threshold and aggressive < 0.35 and danceability >= 0.45:
            vibes.append(ProducerVibe("low_pressure_opener", ["low party", "low aggression", "moderate danceability"]))

        if max(happy, aggressive, relaxed, party, danceability) < self.policy.core_identity_threshold:
            vibes.append(ProducerVibe("leftfield_bridge", ["no dominant core mood"]))

        return vibes

    def complexity_tags_for(self, path: str) -> list[str]:
        track = self._track_for_path(path)
        if track is None:
            return []

        tags: list[str] = []
        if self.dynamic_evolution_for(path):
            tags.append("dynamic_evolution")

        if (track.party >= 0.50 or track.danceability >= 0.65) and track.happy < 0.50:
            tags.append("tension_builder")

        if track.party >= self.policy.core_identity_threshold and track.danceability >= self.policy.core_identity_threshold and track.aggressive < 0.35:
            tags.append("simple_peak_anchor")

        return tags

    def dynamic_evolution_for(self, path: str) -> bool:
        track = self._track_for_path(path)
        if track is None:
            return False
        dynamic, _delta = compute_dynamic_evolution(track.raw_json, policy=self.policy)
        return dynamic

    def evolution_delta_for(self, path: str) -> float | None:
        track = self._track_for_path(path)
        if track is None:
            return None
        _dynamic, delta = compute_dynamic_evolution(track.raw_json, policy=self.policy)
        return delta

    def sonic_vector_for(self, path: str) -> list[float]:
        track = self._track_for_path(path)
        if track is None:
            return [0.0] * 7

        energy = _safe_float(track.energy, DEFAULT_ENERGY) or DEFAULT_ENERGY
        bpm = _safe_float(track.bpm, DEFAULT_BPM) or DEFAULT_BPM

        energy_norm = min(max(energy / ENERGY_SCALE, 0.0), 1.0)
        bpm_norm = min(max((bpm - BPM_MIN) / BPM_RANGE, 0.0), 1.0)
        vec = [energy_norm, bpm_norm, track.danceability, track.party, track.happy, track.aggressive, track.relaxed]

        norm = math.sqrt(sum(value * value for value in vec))
        if norm > 0:
            return [value / norm for value in vec]
        return vec

    def similar_tracks(self, path: str, limit: int = 10) -> list[SimilarTrack]:
        track = self._track_for_path(path)
        if track is None:
            return []

        query_vector = self.sonic_vector_for(path)
        if math.isclose(sum(abs(value) for value in query_vector), 0.0):
            return []

        query_literal = _vector_literal(query_vector)
        owner_user_id = self.config.owner_user_id
        if not owner_user_id:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

        sql = """
            select
                af.path,
                te.embedding::text as embedding_text,
                te.embedding <=> (%s::extensions.vector) as distance
            from public.track_embedding te
            join public.audio_file af
              on af.id = te.audio_file_id
             and af.owner_user_id = te.owner_user_id
            where te.owner_user_id = %s
              and te.vector_schema = %s
              and te.audio_file_id <> %s
            order by te.embedding <=> (%s::extensions.vector)
            limit %s
        """
        with open_database(self.config) as conn:
            with dict_cursor(conn) as cur:
                cur.execute(sql, (query_literal, owner_user_id, VECTOR_SCHEMA, track.audio_file_id, query_literal, limit))
                rows = cur.fetchall()

        results: list[SimilarTrack] = []
        for row in rows:
            candidate_path = str(row["path"])
            candidate_track = self._track_for_path(candidate_path)
            sonic_vector = _parse_vector_literal(row.get("embedding_text"))
            if not sonic_vector and candidate_track is not None:
                sonic_vector = self.sonic_vector_for(candidate_path)
            producer_vibes = [vibe.name for vibe in self.producer_vibes_for(candidate_path)]
            results.append(
                SimilarTrack(
                    path=candidate_path,
                    distance=float(row["distance"]),
                    producer_vibes=producer_vibes,
                    sonic_vector=sonic_vector,
                )
            )
        return results

    def recompute_all(self) -> int:
        owner_user_id = self.config.owner_user_id
        if not owner_user_id:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

        rows = list(self.tracks.values())
        if not rows:
            return 0

        sql = """
            insert into public.track_embedding (
                owner_user_id,
                audio_file_id,
                vector_schema,
                embedding,
                producer_vibes_json,
                dynamic_evolution,
                evolution_delta,
                source_analysis_id,
                computed_at
            ) values (%s, %s, %s, %s::extensions.vector, %s::jsonb, %s, %s, %s, %s)
            on conflict (owner_user_id, audio_file_id, vector_schema)
            do update set
                embedding = excluded.embedding,
                producer_vibes_json = excluded.producer_vibes_json,
                dynamic_evolution = excluded.dynamic_evolution,
                evolution_delta = excluded.evolution_delta,
                source_analysis_id = excluded.source_analysis_id,
                computed_at = excluded.computed_at
        """
        params: list[tuple[Any, ...]] = []
        for track in rows:
            producer_vibes = self.producer_vibes_for(track.path)
            dynamic_evolution, evolution_delta = compute_dynamic_evolution(track.raw_json, policy=self.policy)
            params.append(
                (
                    track.owner_user_id,
                    track.audio_file_id,
                    VECTOR_SCHEMA,
                    _vector_literal(self.sonic_vector_for(track.path)),
                    Json([vibe.name for vibe in producer_vibes]),
                    dynamic_evolution,
                    evolution_delta,
                    track.analysis_id,
                    track.analysis_computed_at or datetime.now(timezone.utc),
                )
            )

        with open_database(self.config) as conn:
            with dict_cursor(conn) as cur:
                cur.executemany(sql, params)
        return len(params)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Magikbox sonic discovery engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("recompute-all", help="Recompute and upsert every track_embedding row for the owner")

    similar_parser = subparsers.add_parser("similar", help="Show nearest neighbors for a track path")
    similar_parser.add_argument("--path", required=True, help="Absolute path to the seed track")
    similar_parser.add_argument("--limit", type=int, default=10, help="Number of neighbors to return")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index = SonicDiscoveryIndex()

    if args.command == "recompute-all":
        count = index.recompute_all()
        print(f"Recomputed {count} track_embedding rows for {index.config.owner_user_id}")
        return 0

    if args.command == "similar":
        results = index.similar_tracks(args.path, limit=args.limit)
        print(
            json.dumps(
                [
                    {
                        "path": result.path,
                        "distance": result.distance,
                        "producer_vibes": result.producer_vibes,
                        "sonic_vector": result.sonic_vector,
                    }
                    for result in results
                ],
                indent=2,
            )
        )
        return 0

    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
