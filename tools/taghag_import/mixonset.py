from __future__ import annotations

import json
import pathlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .db_client import TaghagDbClient
from .config import DatabaseConfig
from .advanced_cue_planner import PIONEER_KEY_TO_CAMELOT, parse_pioneer_key
from .time_base import reconcile_offset


class MixonsetImporter:
    def __init__(self, db: TaghagDbClient, config: DatabaseConfig) -> None:
        self.db = db
        self.config = config
        self.key_bytes = bytes.fromhex("04cecf94e775753cc7bbaf9bf255e86b")

    def decrypt_aes_ecb(self, ciphertext: bytes) -> bytes:
        cipher = Cipher(algorithms.AES(self.key_bytes), modes.ECB(), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def clean_padding(self, data: bytes) -> bytes:
        pad_len = data[-1]
        if 1 <= pad_len <= 16:
            if all(b == pad_len for b in data[-pad_len:]):
                return data[:-pad_len]
        return data.rstrip(b"\x00").rstrip(b"\x0c").rstrip(b"\n").rstrip(b"\r")

    def clean_name(self, name: str) -> str:
        name = re.sub(r"\.[a-zA-Z0-9]+$", "", name)
        # Match Camelot and standard keys (including flats and sharps) with BPM
        name = re.sub(r"\s+-\s+(\d+[AB]|[A-G][b#]?m?)\s+-\s+\d+(\.\d+)?", "", name)
        name = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
        return name

    def parse_xml_analysis(self, xml_data: str) -> dict[str, any] | None:
        try:
            root = ET.fromstring(xml_data)
            bpm = root.findtext("bpm")
            key = root.findtext("key")
            energy = root.findtext("energy")
            length = root.findtext("length")

            boundaries = []
            boundaries_elem = root.find("boundaries")
            if boundaries_elem is not None:
                for b in boundaries_elem.findall("boundary"):
                    boundaries.append({
                        "cue": float(b.get("cue", 0)),
                        "bpm": float(b.get("bpm", 0)),
                        "energy": float(b.get("energy", 0)),
                        "mixability": float(b.get("mixability", 0))
                    })
            return {
                "length_ms": int(length) // 1000 if length else 0, # length field seems to be in microseconds/samples? Wait, let's verify.
                "bpm": float(bpm) if bpm else None,
                "key": int(key) if key else None,
                "energy": float(energy) if energy else None,
                "boundaries": boundaries
            }
        except Exception as e:
            print(f"Error parsing XML: {e}")
            return None

    def classify_segment_role(self, start_s: float, end_s: float, track_duration_s: float, segment_energy: float, max_energy: float) -> str:
        if track_duration_s <= 0:
            return "peak"
        if start_s < 0.12 * track_duration_s:
            return "intro"
        if end_s > 0.88 * track_duration_s:
            return "outro"
        
        # Simple heuristic for breakdown vs peak based on relative energy
        if max_energy > 0 and (segment_energy / max_energy) < 0.45:
            return "breakdown"
        return "peak"

    def _reconcile_mixonset_offset(
        self,
        audio_file_id: str,
        owner_user_id: str,
        mixonset_cue_rows: list[dict],
    ) -> bool:
        """Vote the mixonset grid against the human grid and persist the offset.

        Returns True when a confident offset row was upserted. No human cues, or
        too little structural overlap to vote, simply skips (the cues remain
        ``time_base='rendition'`` with no offset, flagged ``offset_missing`` by
        the canonical views until an offset lands).
        """
        human_rows = self.db._get_postgrest_rows(
            "track_cue",
            {
                "select": "time_ms",
                "audio_file_id": f"eq.{audio_file_id}",
                "owner_user_id": f"eq.{owner_user_id}",
                "source_system": "eq.human",
            },
        )
        if not human_rows:
            return False

        human_ms = [float(r["time_ms"]) for r in human_rows]
        mixonset_ms = [float(r["time_ms"]) for r in mixonset_cue_rows]
        offset = reconcile_offset(
            canonical_file_id=audio_file_id,
            source_file_id=audio_file_id,
            source_system="mixonset",
            canonical_cues_ms=human_ms,
            source_cues_ms=mixonset_ms,
        )
        if offset is None:
            return False
        self.db.upsert_rendition_time_offsets([offset.to_row(owner_user_id)])
        return True

    def import_mixonset_analysis(
        self,
        appstatus_path: pathlib.Path,
        docs_dir: pathlib.Path,
        dry_run: bool = False
    ) -> dict[str, int]:
        if not appstatus_path.exists():
            raise FileNotFoundError(f"appstatus.txt not found at {appstatus_path}")

        status = json.loads(appstatus_path.read_text())
        songs = status.get("songsPlaying", [])
        print(f"Loaded {len(songs)} tracks from active setlist.")

        print("Fetching audio files from database to build matching index...")
        db_files = []
        offset = 0
        limit = 1000
        while True:
            rows = self.db._get_postgrest_rows("audio_file", {"select": "id,path,filename", "limit": str(limit), "offset": str(offset)})
            if not rows:
                break
            db_files.extend(rows)
            offset += limit
        print(f"Loaded {len(db_files)} files from database.")

        # Build indexes
        db_by_exact_path = {}
        db_by_clean_path = {}
        db_by_clean_filename = {}

        for f in db_files:
            p = f["path"]
            fn = f["filename"]
            db_by_exact_path[p] = f
            
            # Normalize path delimiters for cross-referencing
            norm_p = p.replace("/flac-p/", "/flac/").replace("/flac-2/", "/flac/")
            db_by_exact_path[norm_p] = f
            
            clean_p = self.clean_name(norm_p)
            db_by_clean_path[clean_p] = f
            
            clean_fn = self.clean_name(fn)
            db_by_clean_filename[clean_fn] = f

        # Pre-fetch existing dj_tag audio_file_ids to know which ones already exist
        print("Fetching existing dj_tag records...")
        existing_dj_tag_ids: set[str] = set()
        offset = 0
        while True:
            rows = self.db._get_postgrest_rows("dj_tag", {
                "select": "audio_file_id",
                "owner_user_id": f"eq.{self.config.owner_user_id}",
                "limit": str(limit),
                "offset": str(offset),
            })
            if not rows:
                break
            for r in rows:
                existing_dj_tag_ids.add(str(r["audio_file_id"]))
            offset += limit
        print(f"Found {len(existing_dj_tag_ids)} existing dj_tag records.")

        stats = {
            "matched_tracks": 0,
            "unmatched_tracks": 0,
            "cues_inserted": 0,
            "segments_inserted": 0,
            "decrypted_files": 0,
            "dj_tags_upserted": 0,
            "header_only_processed": 0,
            "offsets_reconciled": 0,
        }

        owner_user_id = self.config.owner_user_id

        for idx, s in enumerate(songs, 1):
            song_id = s.get("id")
            title = s.get("title")
            artist = s.get("artist")
            asset_url = s.get("assetURL", "")

            if not asset_url.startswith("file://"):
                stats["unmatched_tracks"] += 1
                continue

            raw_path = unquote(asset_url[len("file://"):])
            norm_path = raw_path.replace("/flac-p/", "/flac/").replace("/flac-2/", "/flac/")

            matched = None
            if norm_path in db_by_exact_path:
                matched = db_by_exact_path[norm_path]
            else:
                clean_raw_path = self.clean_name(norm_path)
                if clean_raw_path in db_by_clean_path:
                    matched = db_by_clean_path[clean_raw_path]
                else:
                    fn = pathlib.Path(raw_path).name
                    clean_fn = self.clean_name(fn)
                    if clean_fn in db_by_clean_filename:
                        matched = db_by_clean_filename[clean_fn]

            if not matched:
                stats["unmatched_tracks"] += 1
                print(f"[{idx}/{len(songs)}] Unmatched: {title} - {artist}")
                continue

            stats["matched_tracks"] += 1
            audio_file_id = matched["id"]

            dat_file = docs_dir / f"{song_id}.dat"
            if not dat_file.exists():
                continue

            # Read and decrypt dat file
            try:
                ciphertext = dat_file.read_bytes()
                if len(ciphertext) < 160:
                    continue

                plaintext = self.decrypt_aes_ecb(ciphertext)
                cleaned = self.clean_padding(plaintext)
                xml_text = cleaned.decode("utf-8", errors="ignore")
                
                analysis = self.parse_xml_analysis(xml_text)
                if not analysis:
                    continue

                # --- Auto-upsert dj_tag with BPM and Camelot key ---
                camelot_key = parse_pioneer_key(analysis.get("key"))
                track_bpm = analysis.get("bpm")

                if (camelot_key or track_bpm) and audio_file_id not in existing_dj_tag_ids:
                    dj_tag_row = {
                        "owner_user_id": owner_user_id,
                        "audio_file_id": audio_file_id,
                        "tag_source": "mixonset",
                    }
                    if track_bpm is not None:
                        dj_tag_row["bpm"] = track_bpm
                    if camelot_key is not None:
                        dj_tag_row["musical_key"] = camelot_key
                    if title:
                        dj_tag_row["title"] = title
                    if artist:
                        dj_tag_row["artist"] = artist

                    if not dry_run:
                        self.db.upsert_dj_tags([dj_tag_row])
                    existing_dj_tag_ids.add(audio_file_id)
                    stats["dj_tags_upserted"] += 1
                elif (camelot_key or track_bpm) and audio_file_id in existing_dj_tag_ids:
                    # Update musical_key if missing on existing row
                    if camelot_key and not dry_run:
                        self.db._patch_postgrest_rows(
                            "dj_tag",
                            {
                                "audio_file_id": f"eq.{audio_file_id}",
                                "owner_user_id": f"eq.{owner_user_id}",
                                "musical_key": "is.null",
                            },
                            {"musical_key": camelot_key},
                        )

                # --- Check if this is a header-only file (no boundaries) ---
                if not analysis.get("boundaries"):
                    stats["header_only_processed"] += 1
                    continue

                stats["decrypted_files"] += 1

                boundaries = analysis["boundaries"]
                track_duration_s = max(b["cue"] for b in boundaries) if boundaries else 0.0
                max_energy = max((b["energy"] for b in boundaries), default=0.0)

                # Prepare cues and segments
                cue_rows = []
                segment_rows = []

                for b_idx, b in enumerate(boundaries, 1):
                    # 1. Cue
                    cue_rows.append({
                        "owner_user_id": owner_user_id,
                        "audio_file_id": audio_file_id,
                        "name": f"Mixonset Cue {b_idx}",
                        "time_ms": int(b["cue"] * 1000),
                        "cue_type": "predicted",
                        "cue_family": "mixonset",
                        "cue_kind": "predicted",
                        "source_system": "mixonset",
                        # Mixonset reads the FLAC but emits its own analyzer grid,
                        # lagged ~+15 ms from the human/master grid. Record the
                        # rendition it measured so the offset re-zeros it.
                        "time_base": "rendition",
                        "measured_against_file_id": audio_file_id,
                        "confidence": float(b.get("mixability", 1.0))
                    })

                    # 2. Segment (between this boundary and the next)
                    if b_idx < len(boundaries):
                        next_b = boundaries[b_idx]
                        start_ms = int(b["cue"] * 1000)
                        end_ms = int(next_b["cue"] * 1000)
                        role = self.classify_segment_role(
                            b["cue"], next_b["cue"], track_duration_s, b["energy"], max_energy
                        )
                        segment_rows.append({
                            "audio_file_id": audio_file_id,
                            "owner_user_id": owner_user_id,
                            "role": role,
                            "ms_start": start_ms,
                            "ms_end": end_ms,
                            "source_system": "mixonset",
                            "time_base": "rendition",
                            "measured_against_file_id": audio_file_id,
                            "confidence": float(b.get("mixability", 1.0))
                        })

                if not dry_run:
                    # Delete existing mixonset cues and segments for this track
                    self.db._delete_postgrest_rows("track_cue", {"audio_file_id": f"eq.{audio_file_id}", "source_system": "eq.mixonset"})
                    self.db._delete_postgrest_rows("track_segment", {"audio_file_id": f"eq.{audio_file_id}", "source_system": "eq.mixonset"})

                    # Insert new ones
                    if cue_rows:
                        self.db.insert_track_cues(cue_rows)
                        stats["cues_inserted"] += len(cue_rows)
                    if segment_rows:
                        self.db.insert_track_segments(segment_rows)
                        stats["segments_inserted"] += len(segment_rows)

                    # Re-zero this analyzer grid onto the human/master grid.
                    if self._reconcile_mixonset_offset(
                        audio_file_id, owner_user_id, cue_rows
                    ):
                        stats["offsets_reconciled"] += 1
                else:
                    stats["cues_inserted"] += len(cue_rows)
                    stats["segments_inserted"] += len(segment_rows)

                print(f"[{idx}/{len(songs)}] Processed: {title} - {artist} ({len(cue_rows)} cues, {len(segment_rows)} segments)")

            except Exception as e:
                print(f"[{idx}/{len(songs)}] Error processing {title}: {e}")

        return stats

