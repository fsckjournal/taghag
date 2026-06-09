from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from mutagen.id3 import COMM, ID3, ID3NoHeaderError

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taghag_import.config import read_database_config

from magikbox.db import dict_cursor, open_database
from magikbox.sonic_discovery import VECTOR_SCHEMA


TS_VIBE_PATTERN = re.compile(r"\[TS:\s*(.*?)\]")


def _safe_json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _extract_vibes(audio: ID3) -> list[str]:
    vibes: set[str] = set()
    for frame in audio.getall("COMM"):
        for text in getattr(frame, "text", []) or []:
            match = TS_VIBE_PATTERN.search(str(text))
            if not match:
                continue
            vibe_str = match.group(1).replace("dynamic_evolution", "")
            vibes.update(vibe.strip() for vibe in vibe_str.split("|") if vibe.strip())
    return sorted(vibes)


def _load_files() -> list[dict[str, object]]:
    config = read_database_config()
    owner_user_id = config.owner_user_id
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    sql = """
        select
            af.id as audio_file_id,
            af.path,
            coalesce(te.producer_vibes_json, '[]'::jsonb) as producer_vibes_json,
            coalesce(tc.human_vibes_json, '[]'::jsonb) as human_vibes_json,
            coalesce(tc.pinned, false) as pinned
        from public.audio_file af
        left join public.track_embedding te
          on te.audio_file_id = af.id
         and te.owner_user_id = af.owner_user_id
         and te.vector_schema = %s
        left join public.track_curation tc
          on tc.audio_file_id = af.id
         and tc.owner_user_id = af.owner_user_id
        where af.owner_user_id = %s
        order by af.path
    """
    with open_database(config) as conn:
        with dict_cursor(conn) as cur:
            cur.execute(sql, (VECTOR_SCHEMA, owner_user_id))
            return list(cur.fetchall())


def apply_corrections(*, music_dir: Path, execute: bool = False) -> int:
    rows = _load_files()
    changed = 0
    config = read_database_config()
    owner_user_id = config.owner_user_id
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    upsert_sql = """
        insert into public.track_curation (
            owner_user_id,
            audio_file_id,
            pinned,
            human_vibes_json,
            corrected_at
        ) values (%s, %s, true, %s::jsonb, %s)
        on conflict (owner_user_id, audio_file_id)
        do update set
            pinned = excluded.pinned,
            human_vibes_json = excluded.human_vibes_json,
            corrected_at = excluded.corrected_at
    """

    with open_database(config) as conn:
        with dict_cursor(conn) as cur:
            for row in rows:
                path = Path(str(row["path"]))
                abs_path = music_dir / path if not path.is_absolute() else path
                if not abs_path.exists():
                    continue

                try:
                    audio = ID3(str(abs_path))
                except ID3NoHeaderError:
                    continue
                except Exception:
                    continue

                vibes = _extract_vibes(audio)
                if not vibes:
                    continue

                producer_vibes = _safe_json_list(row.get("producer_vibes_json"))
                human_vibes = _safe_json_list(row.get("human_vibes_json"))
                pinned = bool(row.get("pinned"))
                current = human_vibes if pinned else producer_vibes
                if vibes == current:
                    continue

                print(
                    f"{'EXECUTE' if execute else 'DRY-RUN'} correction for {abs_path.name}: "
                    f"{current} -> {vibes}"
                )
                if execute:
                    cur.execute(
                        upsert_sql,
                        (
                            owner_user_id,
                            row["audio_file_id"],
                            json.dumps(vibes),
                            datetime.now(timezone.utc),
                        ),
                    )
                changed += 1

    print(f"{'Applied' if execute else 'Found'} {changed} human corrections {'in track_curation.' if execute else '(dry-run; track_curation unchanged).'}")
    return changed


def _max_genre_confidence(genres_json: object) -> float:
    if genres_json is None:
        return 0.0
    if isinstance(genres_json, str):
        try:
            genres_json = json.loads(genres_json)
        except json.JSONDecodeError:
            return 0.0
    if not isinstance(genres_json, list):
        return 0.0
    confidences: list[float] = []
    for genre in genres_json:
        if isinstance(genre, dict):
            confidence = genre.get("confidence")
            try:
                confidences.append(float(confidence))
            except (TypeError, ValueError):
                continue
    return max(confidences, default=0.0)


def audit_conflicts(*, out: Path) -> Path:
    config = read_database_config()
    owner_user_id = config.owner_user_id
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    sql = """
        with latest_analysis as (
            select distinct on (ta.owner_user_id, ta.audio_file_id)
                ta.owner_user_id,
                ta.audio_file_id,
                ta.relaxed,
                ta.genres_json
            from public.track_analysis ta
            where ta.owner_user_id = %s
            order by ta.owner_user_id, ta.audio_file_id, ta.computed_at desc, ta.created_at desc, ta.id desc
        )
        select
            af.path,
            dt.energy,
            la.relaxed,
            la.genres_json,
            coalesce(te.producer_vibes_json, '[]'::jsonb) as producer_vibes_json,
            coalesce(tc.pinned, false) as pinned,
            coalesce(tc.human_vibes_json, '[]'::jsonb) as human_vibes_json
        from latest_analysis la
        join public.audio_file af
          on af.id = la.audio_file_id
         and af.owner_user_id = la.owner_user_id
        left join public.dj_tag dt
          on dt.audio_file_id = la.audio_file_id
         and dt.owner_user_id = la.owner_user_id
        left join public.track_embedding te
          on te.audio_file_id = la.audio_file_id
         and te.owner_user_id = la.owner_user_id
         and te.vector_schema = %s
        left join public.track_curation tc
          on tc.audio_file_id = la.audio_file_id
         and tc.owner_user_id = la.owner_user_id
        order by af.path
    """

    out.parent.mkdir(parents=True, exist_ok=True)
    conflicts: list[dict[str, object]] = []

    with open_database(config) as conn:
        with dict_cursor(conn) as cur:
            cur.execute(sql, (owner_user_id, VECTOR_SCHEMA))
            rows = cur.fetchall()

    for row in rows:
        flags: list[str] = []
        energy = None
        try:
            energy = float(row["energy"]) if row.get("energy") is not None else None
        except (TypeError, ValueError):
            energy = None
        relaxed = float(row["relaxed"]) if row.get("relaxed") is not None else None

        if energy is not None and relaxed is not None and energy >= 8.0 and relaxed > 0.70:
            flags.append("HighEnergy_HighRelaxed")

        max_genre_confidence = _max_genre_confidence(row.get("genres_json"))
        if max_genre_confidence and max_genre_confidence < 0.3:
            flags.append("LowGenreConfidence")

        producer_vibes = _safe_json_list(row.get("producer_vibes_json"))
        human_vibes = _safe_json_list(row.get("human_vibes_json"))
        if bool(row.get("pinned")) and human_vibes != producer_vibes:
            flags.append("HumanOverrideConflict")

        if flags:
            conflicts.append(
                {
                    "path": row["path"],
                    "flag_type": " | ".join(flags),
                    "energy": energy,
                    "relaxed": relaxed,
                    "max_genre_confidence": max_genre_confidence,
                    "vibes": json.dumps(human_vibes if bool(row.get("pinned")) else producer_vibes),
                }
            )

    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "flag_type", "energy", "relaxed", "max_genre_confidence", "vibes"],
        )
        writer.writeheader()
        writer.writerows(conflicts)

    print(f"Audit complete. Found {len(conflicts)} tracks needing manual review.")
    print(f"Report written to {out}")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply or audit human Magikbox vibe corrections")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply", help="Apply human vibe corrections from MP3 comments")
    apply_parser.add_argument("--music-dir", type=Path, required=True, help="Root directory that contains the MP3 files")
    apply_parser.add_argument("--execute", action="store_true", help="Write changes to track_curation")

    audit_parser = subparsers.add_parser("audit", help="Audit qualitative conflicts")
    audit_parser.add_argument("--out", type=Path, default=Path("artifacts/manual_review_needed.csv"), help="Output CSV path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "apply":
        apply_corrections(music_dir=args.music_dir, execute=args.execute)
        return 0
    audit_conflicts(out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
