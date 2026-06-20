from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

from .db_client import TaghagDbClient

APPLE_DISAGREEMENT_FIELDS = (
    "audio_file_id",
    "path",
    "filename",
    "apple_bpm",
    "legacy_bpm",
    "bpm_delta_pct",
    "apple_key",
    "legacy_key",
    "key_stable",
    "bpm_agreement_score",
    "energy_agreement_score",
    "issue_codes",
)


def build_apple_disagreement_rows(
    *,
    apple_rows: Sequence[Mapping[str, Any]],
    dj_tag_rows: Sequence[Mapping[str, Any]],
    audio_file_rows: Sequence[Mapping[str, Any]],
    bpm_threshold_pct: float = 2.0,
    agreement_threshold: float = 0.8,
) -> list[dict[str, object]]:
    dj_by_audio_id = {
        str(row.get("audio_file_id")): row
        for row in dj_tag_rows
        if row.get("audio_file_id")
    }
    file_by_audio_id = {
        str(row.get("id")): row
        for row in audio_file_rows
        if row.get("id")
    }
    report_rows: list[dict[str, object]] = []

    for apple in apple_rows:
        audio_file_id = str(apple.get("audio_file_id") or "")
        if not audio_file_id:
            continue
        dj_tag = dj_by_audio_id.get(audio_file_id, {})
        audio_file = file_by_audio_id.get(audio_file_id, {})
        issue_codes: list[str] = []

        apple_bpm = _number_or_none(apple.get("apple_bpm"))
        legacy_bpm = _number_or_none(dj_tag.get("bpm"))
        bpm_delta_pct = None
        if apple_bpm is not None and legacy_bpm is not None and legacy_bpm != 0:
            bpm_delta_pct = round(abs(apple_bpm - legacy_bpm) / abs(legacy_bpm) * 100.0, 2)
            if bpm_delta_pct > bpm_threshold_pct:
                issue_codes.append(f"bpm_delta_gt_{bpm_threshold_pct:.1f}pct")

        bpm_agreement_score = _number_or_none(apple.get("bpm_agreement_score"))
        if bpm_agreement_score is not None and bpm_agreement_score < agreement_threshold:
            issue_codes.append("low_bpm_agreement_score")

        energy_agreement_score = _number_or_none(apple.get("energy_agreement_score"))
        if energy_agreement_score is not None and energy_agreement_score < agreement_threshold:
            issue_codes.append("low_energy_agreement_score")

        if apple.get("key_stable") is False:
            issue_codes.append("apple_key_unstable")

        if not issue_codes:
            continue

        report_rows.append(
            {
                "audio_file_id": audio_file_id,
                "path": audio_file.get("path"),
                "filename": audio_file.get("filename"),
                "apple_bpm": apple_bpm,
                "legacy_bpm": legacy_bpm,
                "bpm_delta_pct": bpm_delta_pct,
                "apple_key": apple.get("apple_key"),
                "legacy_key": dj_tag.get("musical_key"),
                "key_stable": apple.get("key_stable"),
                "bpm_agreement_score": bpm_agreement_score,
                "energy_agreement_score": energy_agreement_score,
                "issue_codes": issue_codes,
            }
        )

    return report_rows


def load_apple_disagreement_rows(
    client: TaghagDbClient,
    *,
    bpm_threshold_pct: float = 2.0,
    agreement_threshold: float = 0.8,
) -> list[dict[str, object]]:
    owner_user_id = client._config.owner_user_id
    apple_rows = _latest_by_audio_file(
        client._get_postgrest_rows(
            "apple_derived_features",
            {
                "select": (
                    "audio_file_id,apple_bpm,apple_key,key_stable,"
                    "bpm_agreement_score,energy_agreement_score,computed_at"
                ),
                "owner_user_id": f"eq.{owner_user_id}",
                "order": "computed_at.desc",
                "limit": "10000",
            },
        )
    )
    audio_ids = set(apple_rows)
    dj_tag_rows = client._get_postgrest_rows(
        "dj_tag",
        {
            "select": "audio_file_id,bpm,musical_key",
            "owner_user_id": f"eq.{owner_user_id}",
            "limit": "10000",
        },
    )
    audio_file_rows = client._get_postgrest_rows(
        "audio_file",
        {
            "select": "id,path,filename",
            "owner_user_id": f"eq.{owner_user_id}",
            "limit": "10000",
        },
    )
    return build_apple_disagreement_rows(
        apple_rows=[apple_rows[audio_id] for audio_id in sorted(audio_ids)],
        dj_tag_rows=dj_tag_rows,
        audio_file_rows=audio_file_rows,
        bpm_threshold_pct=bpm_threshold_pct,
        agreement_threshold=agreement_threshold,
    )


def write_apple_disagreement_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(APPLE_DISAGREEMENT_FIELDS))
        writer.writeheader()
        for row in rows:
            writable = dict(row)
            issue_codes = writable.get("issue_codes")
            if isinstance(issue_codes, list):
                writable["issue_codes"] = "|".join(str(code) for code in issue_codes)
            writer.writerow({field: writable.get(field) for field in APPLE_DISAGREEMENT_FIELDS})
    return out


def _latest_by_audio_file(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        audio_file_id = row.get("audio_file_id")
        if audio_file_id and str(audio_file_id) not in latest:
            latest[str(audio_file_id)] = row
    return latest


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
