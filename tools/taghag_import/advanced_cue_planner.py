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

        if not self.config.database_url:
            raise ValueError("Direct database connection URL is required for segment audio extraction.")

        print(f"Extracting segment features for: {audio_path.name}")
        
        conn = psycopg2.connect(self.config.database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Fetch segments
        cur.execute(
            """
            SELECT id, ms_start, ms_end, role
            FROM public.track_segment
            WHERE audio_file_id = %s
            ORDER BY ms_start ASC
            """,
            (track_id,)
        )
        segments = cur.fetchall()
        if not segments:
            print("  -> No segments registered for this track.")
            conn.close()
            return 0

        # Load audio file
        audio, sr = librosa.load(str(audio_path), sr=None, mono=True)
        updated = 0

        for seg in segments:
            start_s = seg["ms_start"] / 1000.0
            end_s = seg["ms_end"] / 1000.0
            
            start_sample = max(0, int(start_s * sr))
            end_sample = min(len(audio), int(end_s * sr))
            
            if start_sample >= end_sample:
                continue
                
            clip = audio[start_sample:end_sample]
            embedding = self.compute_segment_embedding(clip, sr)
            
            cur.execute(
                """
                UPDATE public.track_segment
                SET control_vec = %s,
                    source_system = 'model'
                WHERE id = %s
                """,
                (json.dumps(embedding), seg["id"])
            )
            updated += 1
            
        conn.commit()
        conn.close()
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

    def _get_connection(self) -> psycopg2.extensions.connection:
        if not self.config.database_url:
            raise ValueError("Direct database connection URL is required for transition pathfinding.")
        return psycopg2.connect(self.config.database_url, cursor_factory=RealDictCursor)

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
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Fetch seed details (specifically key & BPM from dj_tag and segment vector)
        cur.execute(
            """
            SELECT s.id, s.audio_file_id, d.bpm, d.musical_key as camelot_key, s.control_vec
            FROM public.track_segment s
            JOIN public.dj_tag d ON d.audio_file_id = s.audio_file_id AND d.owner_user_id = s.owner_user_id
            WHERE s.id = %s
            """,
            (seed_segment_id,)
        )
        seed = cur.fetchone()
        if not seed:
            conn.close()
            raise ValueError(f"Seed segment {seed_segment_id} not found in database.")

        seed_id, seed_audio_id, seed_bpm, seed_key, seed_vec = (
            seed["id"], seed["audio_file_id"], float(seed["bpm"]), seed["camelot_key"], seed["control_vec"]
        )

        beam = [BeamState(path=[seed_segment_id], cost=0.0, last_segment_id=seed_segment_id, last_audio_file_id=seed_audio_id)]

        for d_idx in range(depth):
            expanded = []
            for state in beam:
                # Find current last track key and BPM
                cur.execute(
                    """
                    SELECT d.bpm, d.musical_key as camelot_key, s.control_vec
                    FROM public.track_segment s
                    JOIN public.dj_tag d ON d.audio_file_id = s.audio_file_id AND d.owner_user_id = s.owner_user_id
                    WHERE s.id = %s
                    """,
                    (state.last_segment_id,)
                )
                last = cur.fetchone()
                if not last:
                    continue
                
                last_bpm = float(last["bpm"])
                last_key = last["camelot_key"]
                last_vec = last["control_vec"]

                # Fetch matching outgoing transitions
                cur.execute(
                    """
                    SELECT
                      s.id as candidate_segment_id,
                      s.audio_file_id,
                      s.role,
                      d.bpm,
                      d.musical_key as camelot_key,
                      (s.control_vec <=> %s::extensions.vector) as vibe_dist,
                      COALESCE(s.confidence, 1.0) as cue_confidence
                    FROM public.track_segment s
                    JOIN public.dj_tag d ON d.audio_file_id = s.audio_file_id AND d.owner_user_id = s.owner_user_id
                    WHERE s.audio_file_id != %s
                      AND s.owner_user_id = %s
                      AND d.bpm BETWEEN %s - 3 AND %s + 3
                      AND s.role IN ('intro', 'rise', 'peak')
                    ORDER BY s.control_vec <=> %s::extensions.vector
                    LIMIT 20
                    """,
                    (
                        last_vec,
                        state.last_audio_file_id,
                        self.config.owner_user_id,
                        last_bpm, last_bpm,
                        last_vec
                    )
                )
                
                for candidate in cur.fetchall():
                    # Check if audio file already visited (no duplicate tracks in sequence)
                    # We look up visited audio files from segment IDs
                    visited_tracks = []
                    # Quick check via audio file ID
                    cur.execute(
                        "SELECT DISTINCT audio_file_id FROM public.track_segment WHERE id = ANY(%s)",
                        (state.path,)
                    )
                    visited_tracks = [row["audio_file_id"] for row in cur.fetchall()]
                    
                    if candidate["audio_file_id"] in visited_tracks:
                        continue

                    # Camelot step distance check
                    c_dist = camelot_distance(last_key, candidate["camelot_key"])
                    if c_dist > 2.0:
                        continue

                    edge = CandidateEdge(
                        candidate_segment_id=str(candidate["candidate_segment_id"]),
                        audio_file_id=str(candidate["audio_file_id"]),
                        vibe_dist=float(candidate["vibe_dist"]),
                        bpm_delta=abs(last_bpm - float(candidate["bpm"])),
                        camelot_dist=float(c_dist),
                        cue_confidence=float(candidate["cue_confidence"]),
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

        conn.close()
        return beam
