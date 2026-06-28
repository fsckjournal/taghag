#!/usr/bin/env python3
"""Ordered, filtered render plan for the continuous mix.

ORDER   = Minimal Focus.txt '#' column (Spotify mix-mode smooth-transition order).
RESOLVE = match each ordered row to a local FLAC (via the m3u8 paths).
FILTER  = drop BPM > 135 (accidental non-minimal tracks).
GRID    = rbx-re.xml AverageBpm (rigid period) + first cue (phase) + energy cues.
"""
import csv, json, os, re, urllib.parse, collections
import xml.etree.ElementTree as ET

MIN = "/Volumes/PLAYGROUND/MINIMAL"
SP = os.path.dirname(__file__)
BPM_MAX = 135.0

def norm(s): return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
def base(s):  # strip parentheticals + mix/remix tails for robust title matching
    s = re.sub(r'\(.*?\)|\[.*?\]', '', s or '')
    s = re.sub(r'\b(original|extended|radio|club)?\s*(mix|edit|remix|version|re-edit)\b', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]+', '', s.lower())
def stem(p): return os.path.splitext(os.path.basename(p))[0].lower().strip()

def artist_title(fname):
    b = re.sub(r'^\s*[\d.\-]+\s*', '', os.path.splitext(os.path.basename(fname))[0])
    return (b.split(' - ', 1) + [''])[:2] if ' - ' in b else ['', b]

# --- local FLAC resolver: index m3u8 paths by base title (tie-break artist) ---
local = collections.defaultdict(list)
for l in open(f"{MIN}/minimal-rekordbox.m3u8", encoding='utf-8-sig'):
    p = l.strip()
    if p and not p.startswith('#'):
        a, t = artist_title(p)
        local[base(t)].append((norm(a), p))

# --- rbx grid by stem ---
rbx = {}
for tr in ET.parse(f"{MIN}/rbx-re.xml").getroot().iter('TRACK'):
    if tr.get('Location'):
        rbx[stem(urllib.parse.unquote(tr.get('Location').replace('file://localhost', '')))] = tr

# --- ordered rows from the mix-mode export ---
rows = list(csv.reader(open(f"{MIN}/Minimal Focus.txt", encoding='utf-16'), delimiter='\t'))
hdr = rows[0]
H = {h.strip().lower(): i for i, h in enumerate(hdr)}
ordered = sorted(rows[1:], key=lambda r: int(r[H['#']]))

plan, dropped_fast, no_local = [], [], []
for r in ordered:
    num = int(r[H['#']]); title = r[H['track title']]; artist = r[H['original artist']] or r[H['artist']]
    try: bpm_txt = float(r[H['bpm']])
    except: bpm_txt = None

    # resolve local file by title (+artist tie-break)
    cands = local.get(base(title), [])
    path = None
    if len(cands) == 1: path = cands[0][1]
    elif cands:
        path = next((p for a, p in cands if a == norm(artist)), cands[0][1])
    if not path:
        no_local.append((num, f"{artist} - {title}")); continue

    rt = rbx.get(stem(path))
    rbx_bpm = float(rt.get('AverageBpm')) if rt is not None and rt.get('AverageBpm') else None
    bpm = rbx_bpm or bpm_txt
    if bpm and bpm > BPM_MAX:
        dropped_fast.append((num, f"{artist} - {title}", round(bpm, 1))); continue

    cues = sorted((float(m.get('Start')), m.get('Name')) for m in rt.findall('POSITION_MARK')) if rt is not None else []
    plan.append({
        "mix_pos": num, "artist": artist, "title": title, "path": path,
        "bpm": round(bpm, 3) if bpm else None,
        "phase_s": cues[0][0] if cues else None,
        "n_cues": len(cues),
        "cues": [{"start": c[0], "name": c[1]} for c in cues],
    })

# re-rank the surviving tracks 0..N in mix order (the actual render sequence)
for i, t in enumerate(plan): t["seq"] = i
json.dump({"count": len(plan), "tracks": plan}, open(f"{SP}/render_plan.json", "w"), indent=1)

print(f"mix-order rows: {len(ordered)}")
print(f"  -> render plan (local + <= {BPM_MAX} BPM): {len(plan)} tracks")
print(f"  -> dropped FAST (>{BPM_MAX}): {len(dropped_fast)}")
for n, nm, b in dropped_fast: print(f"       #{n:>3} {b:>5} BPM  {nm[:50]}")
print(f"  -> no local file (Beatport/Spotify-only): {len(no_local)}")
print(f"\nfirst 12 of the render sequence:")
for t in plan[:12]:
    print(f"  seq {t['seq']:>3} (mix #{t['mix_pos']:>3})  {t['bpm']}  {t['artist'][:18]} - {t['title'][:28]}")
