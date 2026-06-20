from __future__ import annotations

from taghag_import.apple_disagreement_report import build_apple_disagreement_rows


def test_build_apple_disagreement_rows_flags_bpm_confidence_and_unstable_key() -> None:
    rows = build_apple_disagreement_rows(
        apple_rows=[
            {
                "audio_file_id": "audio-1",
                "apple_bpm": 128.0,
                "apple_key": "C Major",
                "key_stable": True,
                "bpm_agreement_score": 0.96,
            },
            {
                "audio_file_id": "audio-2",
                "apple_bpm": 130.0,
                "apple_key": "G Major",
                "key_stable": False,
                "bpm_agreement_score": 0.4,
            },
        ],
        dj_tag_rows=[
            {"audio_file_id": "audio-1", "bpm": 127.8, "musical_key": "8A"},
            {"audio_file_id": "audio-2", "bpm": 120.0, "musical_key": "9A"},
        ],
        audio_file_rows=[
            {"id": "audio-1", "path": "/music/ok.flac", "filename": "ok.flac"},
            {"id": "audio-2", "path": "/music/risky.flac", "filename": "risky.flac"},
        ],
        bpm_threshold_pct=2.0,
        agreement_threshold=0.8,
    )

    assert len(rows) == 1
    assert rows[0]["audio_file_id"] == "audio-2"
    assert rows[0]["filename"] == "risky.flac"
    assert rows[0]["apple_bpm"] == 130.0
    assert rows[0]["legacy_bpm"] == 120.0
    assert rows[0]["bpm_delta_pct"] == 8.33
    assert rows[0]["issue_codes"] == [
        "bpm_delta_gt_2.0pct",
        "low_bpm_agreement_score",
        "apple_key_unstable",
    ]
