from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .apple_derived_features import compute_derived_features
from .apple_hybrid_vector import build_apple_hybrid_embedding_row
from .db_client import TaghagDbClient
from .flac import probe_flac, sha256_file
from .mik_xml_adapter import get_mik_bpm

SWIFT_CLI_PATH = Path(__file__).parent.parent / "apple-analyzer" / ".build" / "release" / "apple_analyzer"


def _has_drum_activity(instrument_activity: dict[str, object], threshold: float = 0.05, min_active_ratio: float = 0.1) -> bool:
    activity_dict = instrument_activity.get("activity", {})
    if not isinstance(activity_dict, dict):
        return False
    drums = activity_dict.get("drum") or activity_dict.get("drums", [])
    if not drums or not isinstance(drums, list):
        return False

    drum_values = [v.get("value", 0.0) for v in drums if isinstance(v, dict)]
    if not drum_values:
        return False

    # Check if drum activity is virtually 0 throughout
    active_samples = sum(1 for v in drum_values if isinstance(v, (int, float)) and v > threshold)
    return (active_samples / len(drum_values)) > min_active_ratio


def _downsample_array(arr: list[float], factor: int) -> list[float]:
    if not arr:
        return []
    result = []
    for i in range(0, len(arr), factor):
        chunk = arr[i : i + factor]
        result.append(sum(chunk) / len(chunk))
    return result


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _cmtime_ms(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(float(value) * 1000)
    if not isinstance(value, dict):
        return None
    raw_value = value.get("value")
    raw_timescale = value.get("timescale", 1)
    try:
        numerator = float(raw_value)
        timescale = float(raw_timescale)
    except (TypeError, ValueError):
        return None
    if timescale <= 0:
        return None
    return int((numerator / timescale) * 1000)


def _range_ms(item: Any) -> tuple[int, int] | None:
    if not isinstance(item, dict):
        return None
    range_data = item.get("range", item)
    if not isinstance(range_data, dict):
        return None
    start_ms = _cmtime_ms(range_data.get("start"))
    duration_ms = _cmtime_ms(range_data.get("duration"))
    if start_ms is None or duration_ms is None:
        return None
    return start_ms, start_ms + duration_ms


def _timed_ms(item: Any) -> int | None:
    if isinstance(item, dict) and "time" in item:
        return _cmtime_ms(item.get("time"))
    return _cmtime_ms(item)


def _activity_values(activity: dict[str, Any], name: str) -> list[float]:
    entries = activity.get(name)
    if not entries and name == "drum":
        entries = activity.get("drums")
    elif not entries and name == "vocal":
        entries = activity.get("vocals")
    if not isinstance(entries, list):
        return []
    values: list[float] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _loudness_scalar(loudness: dict[str, Any], name: str) -> float | None:
    value = loudness.get(name)
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        "unmatched_audio_file": 0,
        "analysis_runs": 0,
        "derived_features": 0,
        "apple_vectors": 0,
        "segments": 0,
        "cues": 0,
    }

    apple_analysis_rows: list[dict[str, object]] = []
    derived_feature_rows: list[dict[str, object]] = []
    apple_vector_rows: list[dict[str, object]] = []
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
        source_artifact_sha256 = _json_sha256(data)
        
        file_ids = client._audio_file_ids_for_file_keys({file_key})
        audio_file_id = file_ids.get(file_key)
        
        if not audio_file_id:
            print(f"  -> Skipped: no audio_file row for {file_key}")
            summary["unmatched_audio_file"] += 1
            continue

        run_rows = client.upsert_apple_analysis_runs(
            [
                {
                    "owner_user_id": owner_user_id,
                    "audio_file_id": audio_file_id,
                    "source_artifact_sha256": source_artifact_sha256,
                    "source_path": str(path),
                    "analyzer": "apple-analyzer",
                    "raw_result_json": data,
                }
            ]
        )
        analysis_run_id = None
        if run_rows and run_rows[0].get("id"):
            analysis_run_id = str(run_rows[0]["id"])
        summary["analysis_runs"] += 1
            
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
        pace_curve = data.get("pace", {}).get("ranges", []) if isinstance(data.get("pace"), dict) else []
        pace_values = [v.get("value", 0.0) for v in pace_curve if isinstance(v, dict)]

        activity = instrument_activity.get("activity", {})
        if not isinstance(activity, dict):
            activity = {}

        drum_values = _activity_values(activity, "drum")
        bass_values = _activity_values(activity, "bass")
        vocal_values = _activity_values(activity, "vocal")
        loudness = data.get("loudness", {})
        if not isinstance(loudness, dict):
            loudness = {}

        apple_analysis_rows.append({
            "owner_user_id": owner_user_id,
            "audio_file_id": audio_file_id,
            "analysis_run_id": analysis_run_id,
            "source_artifact_sha256": source_artifact_sha256,
            "global_bpm": bpm,
            "key_mode": key_mode,
            "key_tonic": key_tonic,
            "pace_curve": _downsample_array(pace_values, 10),
            "drum_activity": _downsample_array(drum_values, 10),
            "bass_activity": _downsample_array(bass_values, 10),
            "vocal_activity": _downsample_array(vocal_values, 10),
            "loudness_momentary": loudness.get("momentary", []),
            "loudness_short_term": loudness.get("shortTerm", []),
            "loudness_integrated": _loudness_scalar(loudness, "integrated"),
            "loudness_peak": _loudness_scalar(loudness, "peak"),
        })

        derived = compute_derived_features(data, filename=path.name, reference_bpm=get_mik_bpm(path.name))
        derived.update(
            {
                "owner_user_id": owner_user_id,
                "audio_file_id": audio_file_id,
                "analysis_run_id": analysis_run_id,
                "source_artifact_sha256": source_artifact_sha256,
            }
        )
        derived_feature_rows.append(derived)
        apple_vector_rows.append(
            build_apple_hybrid_embedding_row(
                owner_user_id=owner_user_id,
                audio_file_id=audio_file_id,
                source_analysis_id=analysis_run_id,
                features=derived,
            )
        )
        summary["derived_features"] += 1
        summary["apple_vectors"] += 1

        # Map all three structure levels: sections, segments, phrases
        for level_name, level_data in [("section", sections), ("segment", structure.get("segments", [])), ("phrase", structure.get("phrases", []))]:
            for item in level_data:
                bounds = _range_ms(item)
                if bounds is None:
                    continue
                start_ms, end_ms = bounds

                track_segments.append({
                    "owner_user_id": owner_user_id,
                    "audio_file_id": audio_file_id,
                    "role": f"apple_{level_name}",
                    "ms_start": start_ms,
                    "ms_end": end_ms,
                    "source_system": "apple_music_understanding",
                })

        for cue_type, cue_items in [("beat", rhythm.get("beats", [])), ("bar", rhythm.get("bars", []))]:
            if not isinstance(cue_items, list):
                continue
            for i, item in enumerate(cue_items):
                cue_ms = _timed_ms(item)
                if cue_ms is None:
                    continue
                track_cues.append({
                    "owner_user_id": owner_user_id,
                    "audio_file_id": audio_file_id,
                    "name": f"Apple {cue_type} {i + 1}",
                    "cue_type": cue_type,
                    "time_ms": cue_ms,
                    "beat_time": i + 1 if cue_type == "beat" else None,
                    "source_system": "apple_music_understanding",
                })

    if apple_analysis_rows:
        client.upsert_apple_track_analysis(apple_analysis_rows)
    if derived_feature_rows:
        client.upsert_apple_derived_features(derived_feature_rows)
    if apple_vector_rows:
        client.upsert_track_embedding(apple_vector_rows)
    if track_segments:
        client.insert_track_segments(track_segments)
        summary["segments"] = len(track_segments)
    if track_cues:
        client.insert_track_cues(track_cues)
        summary["cues"] = len(track_cues)
    
    return summary
