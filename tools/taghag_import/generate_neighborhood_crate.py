from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import read_database_config
from .db_client import TaghagDbClient


def camelot_distance(k1: str, k2: str) -> float:
    """
    Computes Camelot step distance with minor-to-major (A/B) shift penalties.
    """
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
        # Mode shift (A to B or B to A)
        if step_diff == 0:
            return 1.0  # Simple relative key shift
        else:
            return step_diff + 1.5  # Mismatch penalty


def cosine_distance(v1: list[float], v2: list[float]) -> float:
    if len(v1) != len(v2) or not v1:
        return 1.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    similarity = dot_product / (norm_a * norm_b)
    return 1.0 - similarity


class CrateGenerator:
    def __init__(self, db_client: TaghagDbClient) -> None:
        self.db_client = db_client
        self.config = db_client._config

    def _get_connection(self) -> psycopg2.extensions.connection | None:
        if not self.config.database_url:
            return None
        try:
            return psycopg2.connect(self.config.database_url, cursor_factory=RealDictCursor)
        except Exception:
            return None

    def find_neighborhood(
        self,
        seed_audio_file_id: str,
        limit: int = 30,
        bpm_tolerance: float = 2.0,
        key_tolerance: float = 2.0
    ) -> list[dict[str, Any]]:
        """
        Finds tracks similar to the seed track within BPM and Camelot constraints.
        Leverages native pgvector ORDER BY in Postgres if direct connection exists.
        """
        conn = self._get_connection()
        
        # 1. Fetch seed details (specifically key, bpm, and vector)
        # Using Postgrest to find seed details
        seed_rows = self.db_client._get_postgrest_rows(
            "sonic_analysis",
            {"audio_file_id": f"eq.{seed_audio_file_id}"}
        )
        if not seed_rows:
            # Attempt lookup in track_embedding directly
            seed_rows = self.db_client._get_postgrest_rows(
                "track_embedding",
                {"audio_file_id": f"eq.{seed_audio_file_id}"}
            )
        if not seed_rows:
            raise ValueError(f"Seed audio file {seed_audio_file_id} has no sonic analysis/embedding data.")
            
        seed_data = seed_rows[0]
        # Get seed BPM and Key
        dj_tag_rows = self.db_client._get_postgrest_rows(
            "dj_tag",
            {"audio_file_id": f"eq.{seed_audio_file_id}"}
        )
        if not dj_tag_rows or not dj_tag_rows[0].get("bpm") or not dj_tag_rows[0].get("musical_key"):
            raise ValueError(f"Seed track {seed_audio_file_id} lacks canonical BPM or musical key in dj_tag.")
            
        seed_bpm = float(dj_tag_rows[0]["bpm"])
        seed_key = str(dj_tag_rows[0]["musical_key"])
        
        # Parse vector
        seed_vector = seed_data.get("sonic_vector") or seed_data.get("embedding")
        if isinstance(seed_vector, str):
            seed_vector = json.loads(seed_vector)
            
        if not seed_vector:
            raise ValueError(f"Seed track {seed_audio_file_id} has no embedding vector.")

        results = []

        # 2. Try native PostgreSQL pgvector similarity query
        if conn:
            try:
                with conn.cursor() as cur:
                    # Retrieve all candidate tracks with their embeddings, BPM, and keys
                    cur.execute(
                        """
                        SELECT 
                          a.audio_file_id,
                          a.sonic_vector,
                          d.bpm,
                          d.musical_key,
                          f.path,
                          f.filename
                        FROM public.sonic_analysis a
                        JOIN public.dj_tag d ON a.audio_file_id = d.audio_file_id AND a.owner_user_id = d.owner_user_id
                        JOIN public.audio_file f ON a.audio_file_id = f.id AND a.owner_user_id = f.owner_user_id
                        WHERE a.audio_file_id != %s
                          AND a.owner_user_id = %s
                          AND d.bpm BETWEEN %s AND %s
                        ORDER BY a.sonic_vector <=> %s::extensions.vector
                        LIMIT 500
                        """,
                        (
                            seed_audio_file_id,
                            self.config.owner_user_id,
                            seed_bpm - bpm_tolerance,
                            seed_bpm + bpm_tolerance,
                            seed_vector
                        )
                    )
                    
                    for row in cur.fetchall():
                        # Parse vector
                        cand_vec = row["sonic_vector"]
                        if isinstance(cand_vec, str):
                            cand_vec = json.loads(cand_vec)
                        elif hasattr(cand_vec, "tolist"):
                            cand_vec = cand_vec.tolist()
                            
                        dist = cosine_distance(seed_vector, cand_vec)
                        key_dist = camelot_distance(seed_key, row["musical_key"])
                        
                        if key_dist <= key_tolerance:
                            results.append({
                                "audio_file_id": row["audio_file_id"],
                                "path": row["path"],
                                "filename": row["filename"],
                                "dist": dist,
                                "bpm": float(row["bpm"]),
                                "key": row["musical_key"]
                            })
                conn.close()
            except Exception:
                if conn:
                    conn.close()
                # Fall back to Postgrest local calculation
                results = []

        # 3. Fallback: Postgrest fetch and local calculation
        if not results:
            # Get all tracks with analysis and dj_tags
            analyses = self.db_client._get_postgrest_rows(
                "sonic_analysis",
                {"owner_user_id": f"eq.{self.config.owner_user_id}"}
            )
            dj_tags = {
                t["audio_file_id"]: t 
                for t in self.db_client._get_postgrest_rows(
                    "dj_tag",
                    {"owner_user_id": f"eq.{self.config.owner_user_id}"}
                )
            }
            audio_files = {
                f["id"]: f
                for f in self.db_client._get_postgrest_rows(
                    "audio_file",
                    {"owner_user_id": f"eq.{self.config.owner_user_id}"}
                )
            }
            
            for row in analyses:
                file_id = row["audio_file_id"]
                if file_id == seed_audio_file_id or file_id not in dj_tags or file_id not in audio_files:
                    continue
                    
                tag = dj_tags[file_id]
                cand_bpm = float(tag.get("bpm") or 0)
                cand_key = tag.get("musical_key")
                
                # Check BPM tolerance
                if abs(cand_bpm - seed_bpm) > bpm_tolerance:
                    continue
                # Check Key tolerance
                if not cand_key or camelot_distance(seed_key, cand_key) > key_tolerance:
                    continue
                    
                cand_vec = row.get("sonic_vector")
                if isinstance(cand_vec, str):
                    cand_vec = json.loads(cand_vec)
                
                if cand_vec:
                    dist = cosine_distance(seed_vector, cand_vec)
                    f_info = audio_files[file_id]
                    results.append({
                        "audio_file_id": file_id,
                        "path": f_info["path"],
                        "filename": f_info["filename"],
                        "dist": dist,
                        "bpm": cand_bpm,
                        "key": cand_key
                    })

        # Sort results by cosine distance and truncate to limit
        results.sort(key=lambda x: x["dist"])
        return results[:limit]

    def write_crate_playlist(
        self,
        seed_path: str,
        results: list[dict[str, Any]],
        out_dir: str | Path
    ) -> Path:
        out_dir = Path(out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        
        seed_name = Path(seed_path).stem
        playlist_path = out_dir / f"[TS_Discovery] {seed_name}.m3u8"
        
        # Write .m3u8 file
        with open(playlist_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# Seed: {seed_path}\n")
            for item in results:
                f.write(f"# Dist: {item['dist']:.4f} | BPM: {item['bpm']} | Key: {item['key']}\n")
                f.write(f"{item['path']}\n")
                
        # Write JSON manifest alongside it
        manifest_path = out_dir / f"[TS_Discovery] {seed_name}.json"
        manifest_data = {
            "seed_path": seed_path,
            "neighborhood_tracks": [
                {
                    "audio_file_id": item["audio_file_id"],
                    "path": item["path"],
                    "filename": item["filename"],
                    "cosine_distance": item["dist"],
                    "bpm": item["bpm"],
                    "key": item["key"]
                }
                for item in results
            ]
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        
        return playlist_path
