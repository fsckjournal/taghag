#!/usr/bin/env python3
"""Live-refresh iWebDJ grids for the 172-track playlist via the dj.beatport.com bypass.

Token is derived from the Beatport user_id (no HAR, no session cookie). Writes a fresh
payload cache in the fixture's format; does NOT touch the committed test fixture.
"""
import csv, json, os, sys, time, urllib.request, urllib.parse

sys.path.insert(0, "/Users/g/Projects/tag/hag/tools")
from taghag_import.beatport_resolver import generate_iwebdj_token

CSV = "/Users/g/Projects/tag/hag/tools/mixslice/samples/beatport_playlist_172.csv"
OUT = "/Users/g/Projects/tag/hag/tools/mixslice/samples/iwebdj_172_refreshed.json"
USER_ID = int(os.environ.get("BEATPORT_USER_ID") or "10983855")
URL = "https://dj.beatport.com/api/metadata.php?bp"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

token = generate_iwebdj_token(USER_ID)

def fetch(tid: str) -> str | None:
    body = urllib.parse.urlencode({
        "action": "retrieve", "debug": "v29.92", "songid": tid, "token": token,
    }).encode()
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace").strip()
        except Exception as e:  # noqa: BLE001
            if attempt == 0:
                time.sleep(1.0); continue
            return f"__ERR__ {e}"
    return None

rows = [r for r in csv.DictReader(open(CSV)) if r.get("trackId")]
out, n_ok, n_nf, n_err = [], 0, 0, 0
for i, r in enumerate(rows, 1):
    tid = r["trackId"]
    raw = fetch(tid)
    cls = "err"
    if raw and "iwebdj=" in raw:
        cls = "ok"; n_ok += 1
    elif raw and "notfound" in raw.lower():
        cls = "notfound"; n_nf += 1
    else:
        n_err += 1
    out.append({"source": "live_refresh", "track_id": tid, "raw_payload": raw})
    if cls != "ok":
        print(f"[{i:>3}] {cls.upper():8} {r['artist']} - {r['title']}", flush=True)
    time.sleep(0.25)

json.dump(out, open(OUT, "w"), indent=1)
print(f"\nDONE: {n_ok} ok, {n_nf} notfound, {n_err} err / {len(rows)} -> {OUT}")
