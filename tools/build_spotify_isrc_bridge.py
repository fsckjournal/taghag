#!/usr/bin/env python3
"""Reconstruct the spotify_id -> ISRC bridge for the automix_payloads corpus.

Why this exists
---------------
``fetch_automix_payloads.py`` resolved library ISRCs -> Spotify track IDs at
scrape time and saved each Echo Nest payload as ``{spotify_id}.json`` -- but the
ISRC<->spotify_id pairing was only *printed*, never persisted. The payload JSON
carries no ISRC and no spotify_id inside it (the id is only the filename). v4
(``music_v4.db``) has no spotify_id column populated either (track_alias has zero
'spotify_id' rows). So the join key that lights up the 22k payloads against the
local FLAC library is missing.

This tool rebuilds it authoritatively. Each payload's spotify_id was produced by
``search?q=isrc:X -> items[0]``, so ``GET /v1/tracks/{id}`` recovers exactly that
ISRC. We batch 50 ids/call, cache/resume into a JSONL, then (read-only) join the
recovered ISRCs against ``track.isrc`` in v4 and emit a ``track_alias`` insert
artifact for the slut-side (system-of-record) to ingest. Taghag never writes v4.

Usage
-----
    # 1. Validate on the 6 ground-truth ids first (sanity-check auth + shape)
    python3 build_spotify_isrc_bridge.py resolve --validate

    # 2. Full run (resumable; safe to re-run, skips already-resolved + 404 stubs)
    python3 build_spotify_isrc_bridge.py resolve

    # 3. Join recovered ISRCs against v4 -> coverage report + track_alias artifact
    python3 build_spotify_isrc_bridge.py join

Auth: reads the Spotify Web API access token from ~/.config/tagslut/tokens.json.
If it is expired (HTTP 401) re-auth via tagslut's existing flow that repopulates
that file -- this tool does not hand-roll OAuth.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
PAYLOAD_DIR = Path(os.environ.get("AUTOMIX_PAYLOADS", REPO_ROOT / "automix_payloads"))
BRIDGE_PATH = Path(os.environ.get("BRIDGE_PATH", HERE / "cue_heuristic" / "spotify_isrc_bridge.jsonl"))
TOKENS_PATH = Path(os.path.expanduser("~/.config/tagslut/tokens.json"))
DB_PATH = Path(os.environ.get(
    "TAGHAG_V4_DB", "/Users/g/Projects/tag/slut_db/FRESH_2026/music_v4.db"))
ALIAS_ARTIFACT = HERE / "cue_heuristic" / "track_alias_spotify_id.sql"

# 6 verified ground-truth ids (from cue_heuristic/ground_truth.json) for --validate.
VALIDATE_IDS = [
    "65HVJYKTgBtU0DtK69XEhM",  # Wildfires — Mindchatter
    "6HSQVzeB7kjoeEkrTwLCSY",  # Steady Drummer — Bachgenaur
]

TRACKS_ENDPOINT = "https://api.spotify.com/v1/tracks"
BATCH = 50


def load_token() -> str:
    if not TOKENS_PATH.exists():
        sys.exit(f"No token file at {TOKENS_PATH}. Re-auth via tagslut's Spotify flow.")
    tok = json.loads(TOKENS_PATH.read_text()).get("spotify", {})
    exp = tok.get("expires_at")
    if exp and exp < time.time():
        age = int(time.time() - exp)
        print(f"[!] Spotify access_token expired {age}s ago. If calls 401, re-auth "
              f"via tagslut's flow to repopulate {TOKENS_PATH}.", file=sys.stderr)
    t = tok.get("access_token")
    if not t:
        sys.exit("No spotify.access_token in tokens.json.")
    return t


def is_real_payload(p: Path) -> bool:
    """A 404 stub is a tiny JSON with an 'error' key; real payloads are large."""
    try:
        if p.stat().st_size > 400:
            return True
        return '"error"' not in p.read_text()[:200]
    except OSError:
        return False


def list_spotify_ids() -> list[str]:
    ids = []
    with os.scandir(PAYLOAD_DIR) as it:
        for e in it:
            if not e.name.endswith(".json"):
                continue
            sid = e.name[:-5]
            if len(sid) != 22:
                continue
            if is_real_payload(Path(e.path)):
                ids.append(sid)
    return sorted(ids)


def load_done() -> set[str]:
    done = set()
    if BRIDGE_PATH.exists():
        for line in BRIDGE_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["spotify_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def resolve(validate: bool, delay: float) -> int:
    token = load_token()
    if validate:
        ids = VALIDATE_IDS
        print(f"[*] VALIDATE mode: {len(ids)} ground-truth ids")
    else:
        all_ids = list_spotify_ids()
        done = load_done()
        ids = [i for i in all_ids if i not in done]
        print(f"[*] {len(all_ids)} real payloads, {len(done)} already resolved, "
              f"{len(ids)} pending")

    BRIDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(BRIDGE_PATH, "a" if not validate else "a") as out:
        for start in range(0, len(ids), BATCH):
            chunk = ids[start:start + BATCH]
            r = requests.get(TRACKS_ENDPOINT, params={"ids": ",".join(chunk)},
                             headers={"Authorization": f"Bearer {token}"})
            if r.status_code == 401:
                sys.exit("[X] HTTP 401 — token expired. Re-auth via tagslut's Spotify "
                         "flow, then re-run (progress is saved; run is resumable).")
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5)) + 1
                print(f"  -> 429; backing off {wait}s")
                time.sleep(wait)
                ids.extend(chunk)  # retry at the end
                continue
            if r.status_code != 200:
                print(f"  -> batch @{start} HTTP {r.status_code}; skipping")
                continue
            for tr in r.json().get("tracks", []):
                if not tr:
                    continue
                isrc = (tr.get("external_ids") or {}).get("isrc")
                rec = {
                    "spotify_id": tr["id"],
                    "isrc": isrc.strip().upper() if isrc else None,
                    "name": tr.get("name"),
                    "artists": [a["name"] for a in tr.get("artists", [])],
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
            out.flush()
            print(f"  [{min(start + BATCH, len(ids))}/{len(ids)}] +{written} resolved")
            time.sleep(delay)
    print(f"[+] Wrote {written} records to {BRIDGE_PATH}")
    if validate:
        for line in BRIDGE_PATH.read_text().splitlines()[-len(VALIDATE_IDS):]:
            print("   ", line)
    return 0


def resolve_parquet(parquet: str) -> int:
    """Offline resolve: filter a Spotify metadata dump (id, external_id_isrc)
    down to our payload ids. No Spotify API / auth needed.

    Dump: kaggle lordpatil/spotify-metadata-by-annas-archive tracks.parquet
    (~256M rows, columns include ``id`` and ``external_id_isrc``).
    """
    import pyarrow.parquet as pq

    targets = set(list_spotify_ids())
    done = load_done()
    targets -= done
    print(f"[*] {len(targets)} payload ids to resolve from parquet "
          f"(scanning {parquet})")
    if not targets:
        print("[+] nothing pending")
        return 0

    pf = pq.ParquetFile(parquet)
    found = 0
    BRIDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BRIDGE_PATH, "a") as out:
        for rg in range(pf.num_row_groups):
            tbl = pf.read_row_group(rg, columns=["id", "external_id_isrc"])
            ids = tbl.column("id").to_pylist()
            isrcs = tbl.column("external_id_isrc").to_pylist()
            for sid, isrc in zip(ids, isrcs):
                if sid in targets:
                    out.write(json.dumps({
                        "spotify_id": sid,
                        "isrc": isrc.strip().upper() if isrc else None,
                        "name": None, "artists": [],
                    }, ensure_ascii=False) + "\n")
                    targets.discard(sid)
                    found += 1
            if rg % 100 == 0 or not targets:
                out.flush()
                print(f"  rg {rg}/{pf.num_row_groups}  found {found}  "
                      f"remaining {len(targets)}")
            if not targets:
                print("  [+] all targets found; stopping early")
                break
    print(f"[+] resolved {found} ids from parquet; {len(targets)} not present in dump")
    print(f"[+] wrote {BRIDGE_PATH}")
    return 0


def join() -> int:
    import sqlite3
    if not BRIDGE_PATH.exists():
        sys.exit(f"No bridge at {BRIDGE_PATH}; run `resolve` first.")
    recs = [json.loads(l) for l in BRIDGE_PATH.read_text().splitlines() if l.strip()]
    with_isrc = [r for r in recs if r.get("isrc")]
    print(f"[*] bridge: {len(recs)} records, {len(with_isrc)} with ISRC")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    v4 = {}
    for tid, isrc in con.execute(
            "SELECT id, upper(isrc) FROM track WHERE isrc IS NOT NULL"):
        v4.setdefault(isrc, tid)
    con.close()
    print(f"[*] v4: {len(v4)} distinct-ISRC tracks")

    matched, unmatched = [], []
    for r in with_isrc:
        tid = v4.get(r["isrc"])
        (matched if tid else unmatched).append((r, tid))
    print(f"[+] JOIN COVERAGE: {len(matched)}/{len(with_isrc)} payloads map to a v4 "
          f"track  ({100*len(matched)/max(len(with_isrc),1):.1f}%)")
    print(f"    unmatched (ISRC not in v4): {len(unmatched)}")

    # Emit read-only artifact for slut-side ingestion into track_alias.
    with open(ALIAS_ARTIFACT, "w") as f:
        f.write("-- spotify_id aliases reconstructed by hag build_spotify_isrc_bridge.py\n")
        f.write("-- Ingest on slut-side (Taghag is read-only on v4). One row / payload.\n")
        for r, tid in matched:
            sid = r["spotify_id"].replace("'", "''")
            f.write(
                "INSERT OR IGNORE INTO track_alias "
                "(id, track_id, alias_type, value, provider, source, confidence) VALUES "
                f"(lower(hex(randomblob(16))), '{tid}', 'spotify_id', '{sid}', "
                "'spotify', 'automix_payload_bridge', 1.0);\n")
    print(f"[+] Wrote {len(matched)} INSERTs to {ALIAS_ARTIFACT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("resolve", help="reverse-resolve spotify_id -> ISRC via Spotify API")
    rp.add_argument("--validate", action="store_true", help="only the ground-truth ids")
    rp.add_argument("--delay", type=float, default=0.2, help="sleep between batches (s)")
    pp = sub.add_parser("resolve-parquet",
                        help="offline resolve from a Spotify metadata parquet dump")
    pp.add_argument("--parquet", required=True, help="path to tracks.parquet")
    sub.add_parser("join", help="join recovered ISRCs against v4, emit track_alias artifact")
    args = ap.parse_args()
    if args.cmd == "resolve":
        return resolve(args.validate, args.delay)
    if args.cmd == "resolve-parquet":
        return resolve_parquet(args.parquet)
    if args.cmd == "join":
        return join()
    return 1


if __name__ == "__main__":
    sys.exit(main())
