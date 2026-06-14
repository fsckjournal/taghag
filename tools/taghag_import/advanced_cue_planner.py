from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import read_database_config
from .db_client import TaghagDbClient

# Defensive imports for librosa/numpy
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    from pyrekordbox.anlz import AnlzFile
    PYREKORDBOX_AVAILABLE = True
except ImportError:
    PYREKORDBOX_AVAILABLE = False


PIONEER_KEY_TO_CAMELOT = {
    0: "1A", 1: "2A", 2: "3A", 3: "4A", 4: "5A", 5: "6A",
    6: "7A", 7: "8A", 8: "9A", 9: "10A", 10: "11A", 11: "12A",
    12: "1B", 13: "2B", 14: "3B", 15: "4B", 16: "5B", 17: "6B",
    18: "7B", 19: "8B", 20: "9B", 21: "10B", 22: "11B", 23: "12B",
}


def parse_pioneer_key(raw_key: Any) -> str | None:
    if raw_key is None:
        return None
    try:
        return PIONEER_KEY_TO_CAMELOT[int(raw_key)]
    except (ValueError, KeyError, TypeError):
        return None


def camelot_distance(k1: str | None, k2: str | None) -> float:
    if not k1 or not k2:
        return 999.0
    match1 = re.match(r"^(\d+)([AB])$", k1.strip().upper())
    match2 = re.match(r"^(\d+)([AB])$", k2.strip().upper())
    if not match1 or not match2:
        return 999.0
    n1, m1 = int(match1.group(1)), match1.group(2)
    n2, m2 = int(match2.group(1)), match2.group(2)
    diff = abs(n1 - n2)
    step_diff = min(diff, 12 - diff)
    if m1 == m2:
        return float(step_diff)
    else:
        if step_diff == 0:
            return 1.0
        return step_diff + 1.5


# --- 1. ANLZ Ingestion Engine ---
class AnlzImporter:
    def __init__(self, db_client: TaghagDbClient) -> None:
        self.db_client = db_client
        self.config = db_client._config

    def _get_connection(self) -> psycopg2.extensions.connection:
        if not self.config.database_url:
            raise ValueError("Direct database connection URL is required for transaction-safe ANLZ imports.")
        return psycopg2.connect(self.config.database_url)

    def import_anlz(self, anlz_path: Path, track_id: str) -> tuple[int, int]:
        if not PYREKORDBOX_AVAILABLE:
            raise RuntimeError("pyrekordbox is required to parse Rekordbox ANLZ files. Install with 'pip install pyrekordbox'.")

        print(f"Parsing Rekordbox binary: {anlz_path.name}")
        anlz = AnlzFile.parse_file(anlz_path)
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        cues_processed = 0
        phrases_processed = 0
        
        try:
            # Check owner
            owner_id = self.config.owner_user_id
            
            # 1. Parse PCO2 (Extended Cues) / PCOB (Standard Cues)
            cues_list = anlz.get("PCO2") or anlz.get("PCOB")
            if cues_list:
                for cue in cues_list:
                    time_ms = int(getattr(cue, "time", 0) or 0)
                    cue_kind = "hot" if getattr(cue, "hot_cue", 0) > 0 else "memory"
                    if getattr(cue, "type", 1) == 2:
                        cue_kind = "loop"
                    
                    comment = str(getattr(cue, "comment", "") or "")
                    
                    cur.execute(
                        """
                        INSERT INTO public.track_cue (audio_file_id, owner_user_id, name, time_ms, cue_kind, source_system)
                        VALUES (%s, %s, %s, %s, %s, 'anlz')
                        """,
                        (track_id, owner_id, comment, time_ms, cue_kind)
                    )
                    cues_processed += 1

            # 2. Parse PSSI (Song Structure / Phrases)
            pssi = anlz.get("PSSI")
            if pssi:
                for phrase in pssi:
                    beat = int(getattr(phrase, "beat", 0) or 0)
                    kind = int(getattr(phrase, "kind", 1) or 1)
                    key_id = getattr(phrase, "key", None)
                    camelot_key = parse_pioneer_key(key_id)

                    role = "phrase"
                    if kind == 1:
                        role = "intro"
                    elif kind == 5:
                        role = "peak"
                    elif kind == 6:
                        role = "outro"
                    elif kind == 3:
                        role = "breakdown"

                    # For binary ANLZ, we insert beat markers; segment extractor will reify ms positions
                    cur.execute(
                        """
                        INSERT INTO public.track_segment (audio_file_id, owner_user_id, role, beat_start, ms_start, ms_end, source_system)
                        VALUES (%s, %s, %s, %s, 0, 0, 'anlz')
                        """,
                        (track_id, owner_id, role, beat)
                    )
                    phrases_processed += 1
            
            conn.commit()
            print(f"  -> Successfully imported {cues_processed} cues and {phrases_processed} phrase segments.")
        except Exception as exc:
            conn.rollback()
            print(f"  -> Error: Transaction rolled back. Details: {exc}")
            raise exc
        finally:
            conn.close()

        return cues_processed, phrases_processed


# --- 2. Segment Embedding Extractor ---
class SegmentExtractor:
    def __init__(self, db_client: TaghagDbClient) -> None:
        self.db_client = db_client
        self.config = db_client._config

    def compute_segment_embedding(self, audio: np.ndarray, sr: int) -> list[float]:
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa and numpy are required to compute audio segment embeddings.")

        if audio.size == 0:
            return [0.0] * 7

        rms = float(np.sqrt(np.mean(np.square(audio))))
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr))) if audio.size > 1024 else 0.0
        bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=audio, sr=sr))) if audio.size > 1024 else 0.0
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=audio, sr=sr))) if audio.size > 1024 else 0.0
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(audio))) if audio.size > 1024 else 0.0
        
        try:
            tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
            tempo_val = float(tempo[0]) if isinstance(tempo, np.ndarray) else float(tempo)
        except Exception:
            tempo_val = 120.0
            
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=audio))) if audio.size > 1024 else 0.0

        vec = np.array([rms, centroid, bandwidth, rolloff, zcr, tempo_val, flatness], dtype=float)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return [float(v) for v in vec.tolist()]

    def extract_and_update(self, track_id: str, audio_path: Path) -> int:
        if not LIBROSA_AVAILABLE:
            print("  -> Librosa or Numpy not available; segment extraction skipped.")
            return 0

        print(f"Extracting segment features for: {audio_path.name}")
        
        # 1. Fetch segments via REST
        segments = self.db_client._get_postgrest_rows(
            "track_segment",
            {
                "select": "id,ms_start,ms_end,role",
                "audio_file_id": f"eq.{track_id}",
                "order": "ms_start.asc",
            }
        )
        if not segments:
            print("  -> No segments registered for this track.")
            return 0

        # Load audio file
        audio, sr = librosa.load(str(audio_path), sr=None, mono=True)
        updated = 0

        for seg in segments:
            start_s = int(seg["ms_start"]) / 1000.0
            end_s = int(seg["ms_end"]) / 1000.0
            
            start_sample = max(0, int(start_s * sr))
            end_sample = min(len(audio), int(end_s * sr))
            
            if start_sample >= end_sample:
                continue
                
            clip = audio[start_sample:end_sample]
            embedding = self.compute_segment_embedding(clip, sr)
            
            self.db_client._patch_postgrest_rows(
                "track_segment",
                {"id": f"eq.{seg['id']}"},
                {"control_vec": embedding, "source_system": "model"}
            )
            updated += 1
            
        print(f"  -> Extracted and saved {updated} segment embeddings.")
        return updated


# --- 3. Butter Flow Pathfinder (Beam-Search Engine) ---
@dataclass
class CandidateEdge:
    candidate_segment_id: str
    audio_file_id: str
    vibe_dist: float
    bpm_delta: float
    camelot_dist: float
    cue_confidence: float
    role: str


@dataclass
class BeamState:
    path: List[str]
    cost: float
    last_segment_id: str
    last_audio_file_id: str


class ButterFlowPlanner:
    def __init__(self, db_client: TaghagDbClient) -> None:
        self.db_client = db_client
        self.config = db_client._config

    def edge_cost(self, edge: CandidateEdge, w1: float, w2: float, w3: float, w4: float) -> float:
        return (
            w1 * edge.vibe_dist
            + w2 * edge.bpm_delta
            + w3 * edge.camelot_dist
            + w4 * (1.0 - edge.cue_confidence)
        )

    def plan_sequence(
        self,
        seed_segment_id: str,
        beam_width: int = 5,
        depth: int = 4,
        w1: float = 1.0,  # Vibe similarity weight
        w2: float = 0.5,  # BPM tolerance weight
        w3: float = 0.75, # Camelot transition weight
        w4: float = 0.5   # Cue confidence weight
    ) -> list[BeamState]:
        # Fetch seed details from segment ID via REST
        seed_rows = self.db_client._get_postgrest_rows(
            "track_segment",
            {"select": "id,audio_file_id,control_vec", "id": f"eq.{seed_segment_id}"}
        )
        if not seed_rows:
            raise ValueError(f"Seed segment {seed_segment_id} not found in database.")
        seed_seg = seed_rows[0]
        seed_id = seed_seg["id"]
        seed_audio_id = seed_seg["audio_file_id"]
        seed_vec_raw = seed_seg["control_vec"]
        
        if isinstance(seed_vec_raw, str):
            seed_vec = json.loads(seed_vec_raw)
        else:
            seed_vec = seed_vec_raw

        seed_tags = self.db_client._get_postgrest_rows(
            "dj_tag",
            {"select": "bpm,musical_key", "audio_file_id": f"eq.{seed_audio_id}"}
        )
        if not seed_tags:
            raise ValueError(f"dj_tag not found for seed track {seed_audio_id}")
        seed_bpm = float(seed_tags[0]["bpm"])
        seed_key = seed_tags[0]["musical_key"]

        print("Caching dj_tags and track_segments from database...")
        # Cache all dj_tags
        dj_tags_cache = {}
        offset = 0
        limit = 1000
        while True:
            rows = self.db_client._get_postgrest_rows(
                "dj_tag",
                {"select": "audio_file_id,bpm,musical_key", "limit": str(limit), "offset": str(offset)}
            )
            if not rows:
                break
            for r in rows:
                if r.get("audio_file_id") and r.get("bpm"):
                    dj_tags_cache[r["audio_file_id"]] = {
                        "bpm": float(r["bpm"]),
                        "musical_key": r.get("musical_key")
                    }
            offset += limit

        # Cache all segments with role intro/rise/peak
        segments_cache = []
        offset = 0
        limit = 1000
        while True:
            rows = self.db_client._get_postgrest_rows(
                "track_segment",
                {
                    "select": "id,audio_file_id,role,control_vec,confidence",
                    "role": "in.(intro,rise,peak)",
                    "limit": str(limit),
                    "offset": str(offset)
                }
            )
            if not rows:
                break
            for r in rows:
                if r.get("control_vec"):
                    vec_raw = r["control_vec"]
                    if isinstance(vec_raw, str):
                        vec = json.loads(vec_raw)
                    else:
                        vec = vec_raw
                    r["control_vec_parsed"] = vec
                    segments_cache.append(r)
            offset += limit

        print(f"Cached {len(dj_tags_cache)} dj_tags and {len(segments_cache)} segments.")

        beam = [BeamState(path=[seed_segment_id], cost=0.0, last_segment_id=seed_segment_id, last_audio_file_id=seed_audio_id)]

        def cosine_distance(v1: list[float], v2: list[float]) -> float:
            if not v1 or not v2 or len(v1) != len(v2):
                return 1.0
            dot = sum(x * y for x, y in zip(v1, v2))
            dot = max(-1.0, min(1.0, dot))
            return 1.0 - dot

        for d_idx in range(depth):
            expanded = []
            for state in beam:
                last_seg = None
                for s in segments_cache:
                    if s["id"] == state.last_segment_id:
                        last_seg = s
                        break
                if not last_seg and state.last_segment_id == seed_segment_id:
                    last_seg = {
                        "id": seed_id,
                        "audio_file_id": seed_audio_id,
                        "control_vec_parsed": seed_vec,
                        "confidence": 1.0
                    }
                
                if not last_seg or not last_seg.get("control_vec_parsed"):
                    continue
                
                last_bpm = dj_tags_cache[state.last_audio_file_id]["bpm"]
                last_key = dj_tags_cache[state.last_audio_file_id]["musical_key"]
                last_vec = last_seg["control_vec_parsed"]

                candidates = []
                for s in segments_cache:
                    cand_audio_id = s["audio_file_id"]
                    if cand_audio_id == state.last_audio_file_id:
                        continue
                    if cand_audio_id not in dj_tags_cache:
                        continue
                    
                    cand_bpm = dj_tags_cache[cand_audio_id]["bpm"]
                    if not (last_bpm - 3.0 <= cand_bpm <= last_bpm + 3.0):
                        continue
                        
                    v_dist = cosine_distance(last_vec, s["control_vec_parsed"])
                    candidates.append({
                        "id": s["id"],
                        "audio_file_id": cand_audio_id,
                        "role": s["role"],
                        "bpm": cand_bpm,
                        "camelot_key": dj_tags_cache[cand_audio_id]["musical_key"],
                        "vibe_dist": v_dist,
                        "confidence": s.get("confidence") if s.get("confidence") is not None else 1.0
                    })

                candidates.sort(key=lambda x: x["vibe_dist"])
                candidates = candidates[:20]

                for candidate in candidates:
                    visited_tracks = set()
                    for path_seg_id in state.path:
                        if path_seg_id == seed_segment_id:
                            visited_tracks.add(seed_audio_id)
                        else:
                            for cached_s in segments_cache:
                                if cached_s["id"] == path_seg_id:
                                    visited_tracks.add(cached_s["audio_file_id"])
                                    break
                    
                    if candidate["audio_file_id"] in visited_tracks:
                        continue

                    c_dist = camelot_distance(last_key, candidate["camelot_key"])
                    if c_dist > 2.0:
                        continue

                    edge = CandidateEdge(
                        candidate_segment_id=str(candidate["id"]),
                        audio_file_id=str(candidate["audio_file_id"]),
                        vibe_dist=float(candidate["vibe_dist"]),
                        bpm_delta=abs(last_bpm - float(candidate["bpm"])),
                        camelot_dist=float(c_dist),
                        cue_confidence=float(candidate["confidence"]),
                        role=str(candidate["role"])
                    )
                    
                    cost = self.edge_cost(edge, w1=w1, w2=w2, w3=w3, w4=w4)
                    expanded.append(
                        BeamState(
                            path=state.path + [edge.candidate_segment_id],
                            cost=state.cost + cost,
                            last_segment_id=edge.candidate_segment_id,
                            last_audio_file_id=edge.audio_file_id
                        )
                    )

            if not expanded:
                break
                
            expanded.sort(key=lambda s: s.cost)
            beam = expanded[:beam_width]

        return beam
