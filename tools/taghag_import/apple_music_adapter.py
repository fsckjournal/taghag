from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .db_client import TaghagDbClient
from .flac import probe_flac, sha256_file

SWIFT_CLI_PATH = Path(__file__).parent.parent / "cuecifer-analyzer" / ".build" / "release" / "cuecifer_analyzer"


def _has_drum_activity(instrument_activity: dict[str, object], threshold: float = 0.05, min_active_ratio: float = 0.1) -> bool:
    activity_dict = instrument_activity.get("activity", {})
    if not isinstance(activity_dict, dict):
        return False
    drums = activity_dict.get("drum", [])
    if not drums or not isinstance(drums, list):
        return False
    
    # Check if drum activity is virtually 0 throughout
    active_samples = sum(1 for v in drums if isinstance(v, (int, float)) and v > threshold)
    return (active_samples / len(drums)) > min_active_ratio


def _downsample_array(arr: list[float], factor: int) -> list[float]:
    if not arr:
        return []
    result = []
    for i in range(0, len(arr), factor):
        chunk = arr[i : i + factor]
        result.append(sum(chunk) / len(chunk))
    return result


def analyze_flac(path: Path) -> dict[str, object] | None:
    if not SWIFT_CLI_PATH.exists():
        raise RuntimeError(f"Swift CLI not found at {SWIFT_CLI_PATH}. Please compile it first.")

    process = subprocess.run(
        [str(SWIFT_CLI_PATH), str(path)],
        capture_output=True,
        text=True
    )

    if process.returncode != 0:
        print(f"[{path.name}] Swift CLI failed: {process.stderr}")
        return None

    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as e:
        print(f"[{path.name}] Failed to parse JSON: {e}")
        return None


def run_apple_music_ingestion(
    client: TaghagDbClient,
    owner_user_id: str,
    flac_paths: list[Path]
) -> dict[str, int]:
    
    summary = {
        "processed": 0,
        "eligible": 0,
        "rejected_duration": 0,
        "rejected_bpm": 0,
        "rejected_structure": 0,
        "rejected_ambient": 0,
    }

    apple_analysis_rows: list[dict[str, object]] = []
    track_segments: list[dict[str, object]] = []
    track_cues: list[dict[str, object]] = []

    for path in flac_paths:
        summary["processed"] += 1
        print(f"Analyzing {path.name}...")
        
        # 1. The Duration Rule
        probe = probe_flac(path)
        duration_s = probe.get("duration_s") or 0.0
        if duration_s < 60:
            print(f"  -> Rejected: Duration too short ({duration_s}s)")
            summary["rejected_duration"] += 1
            continue
            
        data = analyze_flac(path)
        if not data:
            continue
            
        rhythm = data.get("rhythm", {})
        if not isinstance(rhythm, dict):
            rhythm = {}
            
        # 2. The Grid Rule
        bpm = rhythm.get("beatsPerMinute")
        if bpm is None:
            print("  -> Rejected: No consistent BPM detected")
            summary["rejected_bpm"] += 1
            continue

        # 3. The Structure Rule
        structure = data.get("structure", {})
        if not isinstance(structure, dict):
            structure = {}
        sections = structure.get("sections", [])
        if not sections:
            print("  -> Rejected: No structural sections detected")
            summary["rejected_structure"] += 1
            continue

        # 4. The Ambient Rule
        instrument_activity = data.get("instrumentActivity", {})
        if not isinstance(instrument_activity, dict):
            instrument_activity = {}
        if not _has_drum_activity(instrument_activity):
            print("  -> Rejected: Failed drum activity check (ambient/spoken)")
            summary["rejected_ambient"] += 1
            continue

        print("  -> Eligible! Extracting math...")
        summary["eligible"] += 1
        
        file_sha256 = sha256_file(path)
        file_key = f"sha256:{file_sha256}"
        
        # We need the audio_file_id from DB. We map this later or fetch it now.
        file_ids = client._audio_file_ids_for_file_keys({file_key})
        audio_file_id = file_ids.get(file_key)
        
        if not audio_file_id:
            print(f"  -> Warning: audio_file_id not found in DB for {file_key}. Skipping DB insert.")
            continue
            
        # Global metadata extraction
        key_data = data.get("key", {})
        if isinstance(key_data, dict):
            ranges = key_data.get("ranges", [])
            if ranges and isinstance(ranges, list) and isinstance(ranges[0], dict):
                key_value = ranges[0].get("value", {})
                key_mode = key_value.get("mode")
                key_tonic = key_value.get("tonic")
            else:
                key_mode, key_tonic = None, None
        else:
            key_mode, key_tonic = None, None

        # Downsample the 100ms arrays (assume 100ms interval -> factor of 10 for 1s)
        pace_curve = data.get("pace", {}).get("pace", []) if isinstance(data.get("pace"), dict) else []
        drum_curve = instrument_activity.get("activity", {}).get("drum", []) if isinstance(instrument_activity.get("activity"), dict) else []
        bass_curve = instrument_activity.get("activity", {}).get("bass", []) if isinstance(instrument_activity.get("activity"), dict) else []
        vocal_curve = instrument_activity.get("activity", {}).get("vocal", []) if isinstance(instrument_activity.get("activity"), dict) else []

        apple_analysis_rows.append({
            "owner_user_id": owner_user_id,
            "audio_file_id": audio_file_id,
            "source_artifact_sha256": file_sha256,
            "global_bpm": bpm,
            "key_mode": key_mode,
            "key_tonic": key_tonic,
            "pace_curve": _downsample_array(pace_curve, 10),
            "drum_activity": _downsample_array(drum_curve, 10),
            "bass_activity": _downsample_array(bass_curve, 10),
            "vocal_activity": _downsample_array(vocal_curve, 10),
        })

        # Map Sections
        for section in sections:
            if not isinstance(section, dict):
                continue
            range_data = section.get("range", {})
            start_ms = int(range_data.get("start", {}).get("value", 0) / 44.1) # timescales are often 44100
            dur_ms = int(range_data.get("duration", {}).get("value", 0) / 44.1)
            
            track_segments.append({
                "owner_user_id": owner_user_id,
                "audio_file_id": audio_file_id,
                "role": section.get("value", "unknown"),
                "ms_start": start_ms,
                "ms_end": start_ms + dur_ms,
                "source_system": "apple_music_understanding"
            })
            
        # Map Beats
        beats = rhythm.get("beats", [])
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            time_ms = int(beat.get("time", {}).get("value", 0) / 44.1)
            # A beat isn't exactly a cue, but we can store downbeats or specific structural beats
            # For now we'll just store the first beat of sections as cues to avoid huge cue tables
            pass

    if apple_analysis_rows:
        client.upsert_apple_track_analysis(apple_analysis_rows)
    if track_segments:
        client.insert_track_segments(track_segments)
    
    return summary
