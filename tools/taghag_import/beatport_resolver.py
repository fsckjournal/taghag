from __future__ import annotations

import base64
import json
import math
import os
import re
import urllib.request
import urllib.parse
from typing import Any

from .beatport_auth import BeatportAuthManager
from .db_client import TaghagDbClient


def jaccard_similarity(s1: str, s2: str) -> float:
    """Computes Jaccard similarity on normalized word sets."""
    words1 = set(re.findall(r"\w+", s1.lower()))
    words2 = set(re.findall(r"\w+", s2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1.intersection(words2)) / len(words1.union(words2))


def generate_iwebdj_token(user_id: int) -> str:
    """Generates the token required by dj.beatport.com/api/metadata.php."""
    # Convert user ID to string, base64 encode it, remove padding '=', split, reverse, and join
    b64 = base64.b64encode(str(user_id).encode("utf-8")).decode("utf-8")
    return b64.replace("=", "")[::-1]


class BeatportResolver:
    def __init__(self, auth_manager: BeatportAuthManager | None = None) -> None:
        self.auth_manager = auth_manager or BeatportAuthManager()
        self.user_id = int(os.environ.get("BEATPORT_USER_ID") or "10983855")

    def _get_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def resolve_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """Looks up a track on Beatport by ISRC using the v4 API."""
        token = self.auth_manager.fetch_v4_token()
        if not token:
            # Check if we have DJ token
            token = self.auth_manager.get_dj_token()
        if not token:
            return None

        url = f"https://api.beatport.com/v4/catalog/tracks/?isrc={isrc}"
        req = urllib.request.Request(url, headers=self._get_headers(token))
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("results", [])
                if results:
                    return results[0]
        except Exception:
            pass
        return None

    def resolve_by_search(self, title: str, artist: str, album: str | None = None) -> dict[str, Any] | None:
        """Searches for a track on Beatport and disambiguates using metadata similarity."""
        token = self.auth_manager.fetch_v4_token() or self.auth_manager.get_dj_token()
        if not token:
            return None

        query = urllib.parse.quote(f"{artist} {title}")
        url = f"https://api.beatport.com/v4/catalog/tracks/?q={query}"
        req = urllib.request.Request(url, headers=self._get_headers(token))
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("results", [])
                
                best_match = None
                best_score = 0.0

                for candidate in results:
                    # Match title
                    candidate_title = candidate.get("name", "")
                    # Match artist(s)
                    candidate_artists = ", ".join([a.get("name", "") for a in candidate.get("artists", [])])
                    
                    title_score = jaccard_similarity(title, candidate_title)
                    artist_score = jaccard_similarity(artist, candidate_artists)
                    
                    score = (title_score + artist_score) / 2.0
                    
                    if album:
                        candidate_release = candidate.get("release", {}).get("name", "")
                        release_score = jaccard_similarity(album, candidate_release)
                        score = 0.7 * score + 0.3 * release_score

                    if score > best_score and score > 0.5:
                        best_score = score
                        best_match = candidate
                        
                return best_match
        except Exception:
            pass
        return None

    def fetch_iwebdj_metadata(self, song_id: str | int) -> dict[str, Any] | None:
        """Fetches and decodes the iwebdj metadata payload for a Beatport track."""
        clean_id = str(song_id).replace("bp", "")
        token = generate_iwebdj_token(self.user_id)
        
        url = "https://dj.beatport.com/api/metadata.php?bp"
        body = urllib.parse.urlencode({
            "action": "retrieve",
            "debug": "v29.92",
            "songid": clean_id,
            "token": token
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        }

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as response:
                text = response.read().decode("utf-8", errors="replace").strip()
                # Remove enclosing quotes if returned
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                
                if "iwebdj=" not in text:
                    return None

                parsed_dict = {}
                for item in text.split("!"):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        parsed_dict[k] = v

                return self.decode_iwebdj_payload(parsed_dict)
        except Exception:
            return None

    def decode_iwebdj_payload(self, parsed_dict: dict[str, str]) -> dict[str, Any]:
        """Decodes the parsed iwebdj dictionary fields according to reverse-engineered JS formulas."""
        a0 = float(parsed_dict.get("a0", "0"))
        a1 = float(parsed_dict.get("a1", "0"))
        a2 = float(parsed_dict.get("a2", "0"))
        a3 = float(parsed_dict.get("a3", "0"))
        db0 = int(parsed_dict.get("db0", "0"))
        db1 = int(parsed_dict.get("db1", "0"))
        length = float(parsed_dict.get("length", "0"))

        bpm_a0 = (a0 - 818.254) / 5.75
        bpm_a1 = (25.5811 - a1) / 7.25

        # Format selector logic
        format_selector = 2 if bpm_a1 < 145 else 1

        if format_selector == 1:
            beat_period = 60000.0 / bpm_a0
            a2_ms = 1000.0 * (a2 - 1894.123) / 2307.2383
            beat_offset = a2_ms + db0 * beat_period
            encoded_string = parsed_dict.get("bm0", "")
        else:
            beat_period = 60000.0 / bpm_a1
            a3_ms = 1000.0 * (6770.2211 - a3) / 2814.255
            beat_offset = a3_ms + db1 * beat_period
            encoded_string = parsed_dict.get("bm1", "")

        # Base52 decode characters to beat energy
        expected_beats_count = int(math.ceil(1000.0 * length / beat_period))
        sliced = encoded_string[:expected_beats_count]
        
        char_array = []
        for c in sliced:
            code = ord(c)
            val = (code - 65) if code <= 90 else (code - 71)
            char_array.append(val)

        # Detect outro raw position
        counter = 1
        while counter < len(char_array) and char_array[-counter] < 20:
            counter += 1
        last_beat_index = max(0, len(char_array) - counter)
        outro_raw_ms = last_beat_index * beat_period + (beat_offset % beat_period)

        # High-level phrase grid calculations
        bpm_val = 60000.0 / beat_period
        duration_ms = 1000.0 * length

        if bpm_val > 117.0:
            multiplier = 32
        else:
            multiplier = 16
        if duration_ms > 270000.0 and bpm_val > 117.0:
            multiplier = 64

        intro_ms = multiplier * beat_period
        outro_ms = duration_ms - math.floor((duration_ms - outro_raw_ms) / (32.0 * beat_period)) * beat_period * 32.0

        # Generate exact beat timings
        beat_times_ms = []
        for i in range(expected_beats_count):
            t = beat_offset + i * beat_period
            if t <= duration_ms:
                beat_times_ms.append(t)

        return {
            "bpm": bpm_val,
            "beat_period_ms": beat_period,
            "beat_offset_ms": beat_offset,
            "intro_ms": intro_ms,
            "outro_ms": outro_ms,
            "beat_times_ms": beat_times_ms,
            "beat_energies": char_array,
            "raw_cues": {
                "a0": a0, "a1": a1, "a2": a2, "a3": a3,
                "a4": float(parsed_dict.get("a4", "0")),
                "a5": float(parsed_dict.get("a5", "0")),
                "db0": db0, "db1": db1
            }
        }

    def ingest_resolver_data(
        self,
        db_client: TaghagDbClient,
        audio_file_id: str,
        owner_user_id: str,
        decoded: dict[str, Any]
    ) -> None:
        """Writes the decoded cloud beatgrid and cues into the Supabase schema."""
        # 1. Write cues (hot_cues and predicted beat locations)
        cues_to_insert = []
        
        # Add Intro cue
        cues_to_insert.append({
            "owner_user_id": owner_user_id,
            "audio_file_id": audio_file_id,
            "name": "Intro",
            "time_ms": int(decoded["intro_ms"]),
            "cue_type": "hot_cue",
            "cue_family": "intro",
            "cue_kind": "predicted",
            "source_system": "iwebdj_cloud",
            "confidence": 0.9
        })
        
        # Add Outro cue
        cues_to_insert.append({
            "owner_user_id": owner_user_id,
            "audio_file_id": audio_file_id,
            "name": "Outro",
            "time_ms": int(decoded["outro_ms"]),
            "cue_type": "hot_cue",
            "cue_family": "outro",
            "cue_kind": "predicted",
            "source_system": "iwebdj_cloud",
            "confidence": 0.9
        })

        # Add raw anchors a0-a5 as memory/hot cues
        for k, v in decoded["raw_cues"].items():
            if k.startswith("a") and v > 0:
                time_ms = int(v * 1000) if k == "a4" else int(v)
                cues_to_insert.append({
                    "owner_user_id": owner_user_id,
                    "audio_file_id": audio_file_id,
                    "name": f"Beatport {k.upper()}",
                    "time_ms": time_ms,
                    "cue_type": "memory_cue" if k in ("a0", "a1") else "hot_cue",
                    "cue_family": "transition_point",
                    "cue_kind": "predicted",
                    "source_system": "iwebdj_cloud",
                    "confidence": 0.85
                })

        db_client.insert_track_cues(cues_to_insert)

        # 2. Slice into 32-beat segments and write to track_segment
        segments_to_insert = []
        beat_times = decoded["beat_times_ms"]
        beat_period = decoded["beat_period_ms"]

        # Loop through beat index in chunks of 32
        chunk_size = 32
        for idx in range(0, len(beat_times), chunk_size):
            end_idx = min(idx + chunk_size, len(beat_times) - 1)
            if idx == end_idx:
                break
            
            ms_start = int(beat_times[idx])
            ms_end = int(beat_times[end_idx])
            
            # Determine role based on position
            if ms_start <= decoded["intro_ms"]:
                role = "intro"
            elif ms_end >= decoded["outro_ms"]:
                role = "outro"
            else:
                role = "body"

            segments_to_insert.append({
                "audio_file_id": audio_file_id,
                "owner_user_id": owner_user_id,
                "role": role,
                "ms_start": ms_start,
                "ms_end": ms_end,
                "beat_start": idx,
                "beat_end": end_idx,
                "source_system": "iwebdj_cloud",
                "confidence": 0.9
            })

        if segments_to_insert:
            db_client.insert_track_segments(segments_to_insert)
