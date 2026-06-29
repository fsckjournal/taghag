#!/usr/bin/env python3
"""Build an IDENTITY-KEYED render plan for the Beatport dev playlist — pre-MU, offline.

Input identity: a Beatport playlist CSV (ISRC + Beatport trackId per row, ordered).
Grids: the captured iWebDJ payloads fixture (decoded via beatport_resolver) — no audio,
no MusicUnderstanding, no network. Each track is keyed by ISRC/trackId, NOT path, so the
plan survives file moves (the LOSSY->ATTIC lesson). Resolve identity->file at render time.

The iWebDJ grid is linear, so the full beat grid is captured compactly as
(beat_offset_ms, beat_period_ms, n_beats); mix points come from the decoder's phrase logic
(intro = mix-in, outro = mix-out).

Usage:
  python build_identity_render_plan.py PLAYLIST.csv [OUT.json]
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from taghag_import.beatport_resolver import BeatportResolver

HERE = Path(__file__).resolve().parent
# Payload cache: env override (e.g. a live-refreshed cache), else the committed fixture.
FIXTURE = Path(os.environ.get("IWEBDJ_PAYLOADS")
               or HERE.parent / "tests" / "fixtures" / "iwebdj_payloads.json")

# Offtrack/mixonset-cued tracks currently in Supabase are the *Paper Cuts* experiment set;
# normalized titles listed here only so the builder can REPORT real overlap with this
# playlist (not fabricate a join). Empty cue arrays = we only check title membership.
OFFTRACK_TITLES = {
    "wildfires", "heads above", "lovelee dae", "mouth", "about love", "im satisfied",
    "chase the sun", "the moodymann", "something better", "beats chips", "drifting",
    "brazilian flower", "steady drummer", "driving me crazy", "neu tech", "drift",
    "bessie", "smoothin groovin", "neu tech",
}

def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s*[\(\[-].*$", "", s)          # drop "- Extended Mix", "(Remix)", etc.
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_payload(raw: str) -> dict:
    s = raw.strip().strip('"').strip()
    d = {}
    for part in s.split("!"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip().strip('"')] = v
    return d

def main() -> int:
    csv_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "render_plan.json"

    payloads = {str(p["track_id"]): p["raw_payload"]
                for p in json.load(open(FIXTURE))}
    resolver = BeatportResolver.__new__(BeatportResolver)  # decode needs no auth

    rows = [r for r in csv.DictReader(open(csv_path)) if r.get("title")]
    tracks, bad, offtrack_hits = [], [], 0

    for seq, r in enumerate(rows):
        tid = r["trackId"]
        rec = {
            "seq": seq, "isrc": r["isrc"], "beatport_track_id": tid,
            "artist": r["artist"], "title": r["title"],
            "duration_s": int(r["duration"]) if r.get("duration") else None,
            "grid_source": "beatport_iwebdj",
        }
        raw = payloads.get(tid)
        if not raw:
            rec["decode_ok"] = False; rec["needs_grid"] = "no_payload_in_fixture"
            bad.append(rec); tracks.append(rec); continue
        if "notfound" in raw.strip().strip('"').lower():
            # Beatport had no iWebDJ analysis for this trackId at capture time.
            rec["decode_ok"] = False; rec["needs_grid"] = "beatport_notfound"
            bad.append(rec); tracks.append(rec); continue
        try:
            d = resolver.decode_iwebdj_payload(parse_payload(raw))
            n_beats = len(d["beat_times_ms"])
            ok = n_beats > 0 and 40 <= d["bpm"] <= 220
            rec.update({
                "bpm": round(d["bpm"], 3),
                "beat_offset_ms": round(d["beat_offset_ms"], 2),
                "beat_period_ms": round(d["beat_period_ms"], 4),
                "n_beats": n_beats,
                "mix_in_ms": round(d["intro_ms"], 1),
                "mix_out_ms": round(d["outro_ms"], 1),
                "decode_ok": ok,
            })
            if not ok:
                rec["error"] = f"implausible decode (bpm={d['bpm']:.1f}, beats={n_beats})"
                bad.append(rec)
        except Exception as e:  # noqa: BLE001
            rec["decode_ok"] = False; rec["error"] = repr(e)[:120]; bad.append(rec)

        # offtrack-cue overlap REPORT (this playlist vs the DB's offtrack subset)
        if norm(r["title"]) in OFFTRACK_TITLES:
            rec["offtrack_cues_available_in_db"] = True
            offtrack_hits += 1
        tracks.append(rec)

    plan = {
        "playlist": csv_path.stem,
        "identity_keys": ["isrc", "beatport_track_id"],
        "grid_source": "beatport_iwebdj (fixture: tests/fixtures/iwebdj_payloads.json)",
        "note": "Identity-keyed (resolve->file at render time). Linear grid: "
                "reconstruct beats as beat_offset_ms + i*beat_period_ms for i in [0,n_beats).",
        "count": len(tracks),
        "decoded_ok": sum(1 for t in tracks if t.get("decode_ok")),
        "beatport_notfound": sum(1 for t in tracks if t.get("needs_grid") == "beatport_notfound"),
        "needs_grid": [{"seq": b["seq"], "artist": b["artist"], "title": b["title"],
                        "isrc": b["isrc"], "reason": b.get("needs_grid") or b.get("error")}
                       for b in bad],
        "offtrack_cues_overlap": f"{offtrack_hits}/{len(tracks)} playlist tracks also have "
                                 f"offtrack cues in Supabase",
        "tracks": tracks,
    }
    json.dump(plan, open(out_path, "w"), indent=1)
    print(f"wrote {out_path}")
    print(f"  {plan['count']} tracks, {plan['decoded_ok']} decoded OK, {len(bad)} bad")
    print(f"  beatport_notfound: {plan['beatport_notfound']}")
    print(f"  offtrack overlap: {plan['offtrack_cues_overlap']}")
    for b in bad:
        print(f"  NEEDS GRID: [{b['seq']}] {b['artist']} - {b['title']} "
              f"-> {b.get('needs_grid') or b.get('error')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
