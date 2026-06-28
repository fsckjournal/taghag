#!/usr/bin/env python3
"""Forensic probe of all evidence sources - fixed column names."""

import json
import os
import plistlib
import sqlite3
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SNAP = Path("/Users/g/Projects/taghag/tools/forensic/snapshots")
OUT = Path("/Users/g/Projects/taghag/tools/forensic/extraction")
OUT.mkdir(parents=True, exist_ok=True)

def section(title):
    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")

# ─────────────────────────────────────────────────────────────────────────
# 1. MIK DATABASE
# ─────────────────────────────────────────────────────────────────────────
section("MIXED IN KEY DATABASE")
mik_db = SNAP / "Collection11.mikdb"
conn_mik = sqlite3.connect(str(mik_db))
conn_mik.row_factory = sqlite3.Row

# Sample ZSONG row
print("\n--- Sample ZSONG (all columns) ---")
row = conn_mik.execute("SELECT * FROM ZSONG WHERE ZBEATS IS NOT NULL LIMIT 1").fetchone()
if row:
    for k in row.keys():
        val = row[k]
        if isinstance(val, bytes):
            val = f"<{len(val)} bytes>"
        elif isinstance(val, str) and len(val) > 200:
            val = val[:200] + "..."
        print(f"  {k}: {val}")

# Find the file path column
print("\n--- Looking for file path ---")
# Check all text columns for path-like values
for col in row.keys():
    val = row[col]
    if isinstance(val, str) and ('/' in val or '\\' in val or '.flac' in val.lower() or '.mp3' in val.lower()):
        print(f"  PATH COLUMN: {col} = {val}")

# Decode one ZBEATS blob
print("\n--- ZBEATS decode ---")
beats_blob = row["ZBEATS"]
if beats_blob:
    blob = bytes(beats_blob)
    try:
        plist = plistlib.loads(blob)
        if "$objects" in plist:
            objects = plist["$objects"]
            print(f"  NSKeyedArchiver with {len(objects)} objects")
            beat_times = None
            tempo = None
            for i, obj in enumerate(objects):
                if isinstance(obj, dict):
                    for k in obj:
                        if 'beat' in k.lower() or 'tempo' in k.lower() or 'MIK' in k:
                            print(f"    obj[{i}].{k} = {repr(obj[k])[:100]}")
                    if "NS.data" in obj:
                        data = obj["NS.data"]
                        if isinstance(data, bytes) and len(data) >= 8:
                            n_doubles = len(data) // 8
                            times = struct.unpack(f"<{n_doubles}d", data)
                            print(f"    NS.data: {n_doubles} doubles (beat times)")
                            print(f"    First 10: {[round(t,4) for t in times[:10]]}")
                            print(f"    Last 5:  {[round(t,4) for t in times[-5:]]}")
                            beat_times = times
                elif isinstance(obj, str):
                    if 'MIK' in obj or 'beat' in obj.lower():
                        print(f"    obj[{i}] = '{obj}'")
            
            if beat_times:
                ibis = [beat_times[i+1] - beat_times[i] for i in range(min(30, len(beat_times)-1))]
                bpms = [60.0/ibi for ibi in ibis if ibi > 0.1]
                declared = row["ZTEMPO"] or row.get("ZTAGTEMPO")
                print(f"\n  Beat count: {len(beat_times)}")
                print(f"  Derived BPMs: min={min(bpms):.3f} max={max(bpms):.3f} mean={sum(bpms)/len(bpms):.3f}")
                print(f"  Declared ZTEMPO: {row['ZTEMPO']}")
                
                artist = row.get("ZARTIST", "unknown")
                name = row.get("ZNAME", "unknown")
                with open(OUT / "mik_sample_beats.json", "w") as f:
                    json.dump({
                        "z_pk": row["Z_PK"],
                        "artist": artist,
                        "name": name,
                        "declared_tempo": row["ZTEMPO"],
                        "beat_count": len(beat_times),
                        "beat_times_s": [round(t, 6) for t in beat_times],
                        "first_30_ibis": [round(ibi, 6) for ibi in ibis],
                        "first_30_bpms": [round(b, 3) for b in bpms],
                    }, f, indent=2)
                print(f"  Saved: {OUT / 'mik_sample_beats.json'}")
        else:
            print(f"  Not NSKeyedArchiver")
    except Exception as e:
        print(f"  Error: {e}")

# ZCUEPOINT
print("\n--- ZCUEPOINT schema + sample ---")
cp_cols = conn_mik.execute("PRAGMA table_info(ZCUEPOINT)").fetchall()
print(f"  Columns: {[c['name'] for c in cp_cols]}")
cp_rows = conn_mik.execute("SELECT * FROM ZCUEPOINT WHERE ZSONG = ? LIMIT 10", (row["Z_PK"],)).fetchall()
for r in cp_rows:
    d = {k: r[k] for k in r.keys() if r[k] is not None}
    for k in list(d):
        if isinstance(d[k], bytes):
            d[k] = f"<{len(d[k])} bytes>"
    print(f"  {d}")

# ZENERGYSEGMENT
print("\n--- ZENERGYSEGMENT for same song ---")
es_cols = conn_mik.execute("PRAGMA table_info(ZENERGYSEGMENT)").fetchall()
print(f"  Columns: {[c['name'] for c in es_cols]}")
es_rows = conn_mik.execute("SELECT * FROM ZENERGYSEGMENT WHERE ZSONG = ? LIMIT 5", (row["Z_PK"],)).fetchall()
for r in es_rows:
    d = {k: r[k] for k in r.keys() if r[k] is not None}
    print(f"  {d}")

# ZKEYSEGMENT
print("\n--- ZKEYSEGMENT for same song ---")
ks_rows = conn_mik.execute("SELECT * FROM ZKEYSEGMENT WHERE ZSONG = ? LIMIT 3", (row["Z_PK"],)).fetchall()
for r in ks_rows:
    d = {k: r[k] for k in r.keys() if r[k] is not None}
    print(f"  {d}")

# ZWAVEFORM
print("\n--- ZWAVEFORM schema ---")
wf_cols = conn_mik.execute("PRAGMA table_info(ZWAVEFORM)").fetchall()
print(f"  Columns: {[c['name'] for c in wf_cols]}")
wf_row = conn_mik.execute("SELECT * FROM ZWAVEFORM WHERE ZSONG = ? LIMIT 1", (row["Z_PK"],)).fetchone()
if wf_row:
    for k in wf_row.keys():
        val = wf_row[k]
        if isinstance(val, bytes):
            # Try plistlib decode
            print(f"  {k}: <{len(val)} bytes>")
            if k == "ZOBJECT" and len(val) > 10:
                try:
                    wp = plistlib.loads(val)
                    if "$objects" in wp:
                        wobjs = wp["$objects"]
                        print(f"    NSKeyedArchiver with {len(wobjs)} objects")
                        for i, wo in enumerate(wobjs):
                            if isinstance(wo, str) and ('MIK' in wo or 'Waveform' in wo):
                                print(f"      obj[{i}] = '{wo}'")
                            elif isinstance(wo, dict):
                                for wk in wo:
                                    if 'data' in wk.lower() or 'MIK' in wk or 'waveform' in wk.lower():
                                        wv = wo[wk]
                                        if isinstance(wv, bytes):
                                            print(f"      obj[{i}].{wk} = <{len(wv)} bytes>")
                                        else:
                                            print(f"      obj[{i}].{wk} = {repr(wv)[:80]}")
                except Exception as e:
                    print(f"    plist decode error: {e}")
        else:
            print(f"  {k}: {val}")

# MIK file path analysis - find where paths are stored
print("\n--- MIK file path lookup ---")
# Check ZNAME column and other potential path sources
songs_with_paths = conn_mik.execute("""
    SELECT Z_PK, ZARTIST, ZNAME, ZALBUM, ZFINGERPRINT, ZSAMPLERATE, ZTEMPO
    FROM ZSONG WHERE ZNAME LIKE '%/%' OR ZNAME LIKE '%.flac' OR ZNAME LIKE '%.mp3'
    LIMIT 5
""").fetchall()
if songs_with_paths:
    print(f"  Found {len(songs_with_paths)} songs with path-like names")
    for s in songs_with_paths:
        print(f"    {dict(s)}")
else:
    # Try ZCOLLECTION for path info
    print("  No path-like ZNAME values. Checking ZCOLLECTION...")
    colls = conn_mik.execute("SELECT * FROM ZCOLLECTION LIMIT 3").fetchall()
    for c in colls:
        d = {k: c[k] for k in c.keys() if c[k] is not None}
        for k in list(d):
            if isinstance(d[k], bytes):
                d[k] = f"<{len(d[k])} bytes>"
            elif isinstance(d[k], str) and len(d[k]) > 150:
                d[k] = d[k][:150] + "..."
        print(f"    {d}")

# Check ZBOOKMARKDATA for path info
print("\n--- ZBOOKMARKDATA check ---")
bm = conn_mik.execute("SELECT Z_PK, length(ZBOOKMARKDATA) as bm_len FROM ZSONG WHERE ZBOOKMARKDATA IS NOT NULL LIMIT 3").fetchall()
for b in bm:
    print(f"  Song {b[0]}: bookmark {b[1]} bytes")
# Decode one bookmark
bm_row = conn_mik.execute("SELECT Z_PK, ZNAME, ZBOOKMARKDATA FROM ZSONG WHERE ZBOOKMARKDATA IS NOT NULL LIMIT 1").fetchone()
if bm_row:
    bm_data = bytes(bm_row["ZBOOKMARKDATA"])
    # macOS bookmarks contain file paths as UTF-8 strings
    # Search for path-like strings in the blob
    text = bm_data.decode('utf-8', errors='replace')
    import re
    paths = re.findall(r'(/[A-Za-z][\w\-./\s]+\.(?:flac|mp3|wav|aiff|m4a))', text)
    if paths:
        print(f"  Decoded paths from bookmark:")
        for p in paths[:3]:
            print(f"    {p}")
    else:
        # Try looking for volume-relative paths
        paths2 = re.findall(r'([\w\-./\s]{10,}\.(?:flac|mp3|wav|aiff|m4a))', text)
        if paths2:
            print(f"  Partial paths from bookmark:")
            for p in paths2[:3]:
                print(f"    {p}")

conn_mik.close()

# ─────────────────────────────────────────────────────────────────────────
# 2. REKORDBOX MASTER.DB
# ─────────────────────────────────────────────────────────────────────────
section("REKORDBOX MASTER.DB")
rbx_db = SNAP / "rekordbox_master.db"
try:
    conn_rbx = sqlite3.connect(str(rbx_db))
    conn_rbx.row_factory = sqlite3.Row
    
    # Non-empty tables
    tables = [r[0] for r in conn_rbx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"\n--- Non-empty tables ---")
    for t in tables:
        try:
            count = conn_rbx.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            if count > 0:
                print(f"  {t}: {count}")
        except:
            pass
    
    # djmdContent sample
    print("\n--- djmdContent sample ---")
    cols = conn_rbx.execute("PRAGMA table_info(djmdContent)").fetchall()
    col_names = [c['name'] for c in cols]
    print(f"  Columns: {col_names}")
    
    # Pick columns that exist
    safe_cols = [c for c in ['ID', 'Title', 'ArtistName', 'BPM', 'Length', 'FolderPath', 'FileNameL', 'AnalysisDataPath', 'ContentLink'] if c in col_names]
    row = conn_rbx.execute(f"SELECT {','.join(safe_cols)} FROM djmdContent LIMIT 3").fetchall()
    for r in row:
        print(f"  {dict(r)}")
    
    # djmdCue
    print("\n--- djmdCue ---")
    try:
        cue_cols = conn_rbx.execute("PRAGMA table_info(djmdCue)").fetchall()
        print(f"  Columns: {[c['name'] for c in cue_cols]}")
        cue_rows = conn_rbx.execute("SELECT * FROM djmdCue LIMIT 3").fetchall()
        for r in cue_rows:
            d = {k: r[k] for k in r.keys() if r[k] is not None}
            if 'rb_data_status' in d:
                del d['rb_data_status']
            print(f"  {d}")
    except Exception as e:
        print(f"  Error: {e}")
    
    conn_rbx.close()
except Exception as e:
    print(f"Rekordbox error: {e}")

# ─────────────────────────────────────────────────────────────────────────
# 3. LEXICON MAIN.DB
# ─────────────────────────────────────────────────────────────────────────
section("LEXICON MAIN.DB")
lex_db = SNAP / "lexicon_main.db"
conn_lex = sqlite3.connect(str(lex_db))
conn_lex.row_factory = sqlite3.Row

# Non-empty tables
tables = [r[0] for r in conn_lex.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    count = conn_lex.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    if count > 0:
        print(f"  {t}: {count}")

# Track sample
print("\n--- Track sample ---")
row = conn_lex.execute("SELECT * FROM Track LIMIT 1").fetchone()
if row:
    for k in row.keys():
        val = row[k]
        if isinstance(val, bytes):
            val = f"<{len(val)} bytes>"
        elif isinstance(val, str) and len(val) > 200:
            val = val[:200] + "..."
        print(f"  {k}: {val}")

# Cuepoint + Tempomarker
print("\n--- Cuepoint schema ---")
cp_cols = conn_lex.execute("PRAGMA table_info(Cuepoint)").fetchall()
print(f"  {[c['name'] for c in cp_cols]}")

print("\n--- Tempomarker schema ---")
tm_cols = conn_lex.execute("PRAGMA table_info(Tempomarker)").fetchall()
print(f"  {[c['name'] for c in tm_cols]}")

# Playlists with counts
print("\n--- Playlists ---")
playlists = conn_lex.execute("SELECT id, title FROM Playlist ORDER BY title").fetchall()
for p in playlists:
    count = conn_lex.execute("SELECT COUNT(*) FROM LinkTrackPlaylist WHERE playlistId = ?", (p['id'],)).fetchone()[0]
    if count > 0:
        print(f"  [{p['id']}] {p['title']}: {count} tracks")

conn_lex.close()

# ─────────────────────────────────────────────────────────────────────────
# 4. REKORDBOX XML (compact)
# ─────────────────────────────────────────────────────────────────────────
section("REKORDBOX XML")
for xml_path in ["/Volumes/PLAYGROUND/MINIMAL/rbx.xml", "/Users/g/Documents/rbx4.xml"]:
    print(f"\n--- {xml_path} ---")
    if not os.path.exists(xml_path):
        print("  NOT FOUND")
        continue
    tree = ET.parse(xml_path)
    root = tree.getroot()
    tracks = root.findall(".//TRACK")
    tempo_count = sum(len(t.findall("TEMPO")) for t in tracks)
    pos_count = sum(len(t.findall("POSITION_MARK")) for t in tracks)
    print(f"  Tracks: {len(tracks)}, TEMPO: {tempo_count}, POSITION_MARK: {pos_count}")
    
    # Playlists
    for pl in root.findall(".//NODE[@Type='1']"):
        entries = pl.findall("TRACK")
        if entries:
            print(f"  Playlist '{pl.get('Name')}': {len(entries)}")

# ─────────────────────────────────────────────────────────────────────────
# 5. SUPPORTING FILES
# ─────────────────────────────────────────────────────────────────────────
section("SUPPORTING FILES")
for f in ["/Volumes/PLAYGROUND/MINIMAL/Minimal Focus.txt", "/Volumes/PLAYGROUND/MINIMAL/minimal.m3u8",
          "/Users/g/Desktop/fm-local.xlsx", "/Users/g/Downloads/fm.csv",
          "/Users/g/Downloads/Focus Minimal.csv", "/Users/g/Downloads/Focus Minimal-2.csv"]:
    p = Path(f)
    if p.exists():
        sz = p.stat().st_size
        lines = ""
        if p.suffix in ('.txt', '.csv', '.m3u8'):
            with open(f, errors='replace') as fh:
                all_lines = fh.readlines()
                lines = f" ({len(all_lines)} lines)"
        print(f"  OK {p.name} ({sz}b){lines}")
    else:
        print(f"  MISSING {p.name}")

# ─────────────────────────────────────────────────────────────────────────
# 6. TOOLS
# ─────────────────────────────────────────────────────────────────────────
section("TOOLS")
for tool, args in [("ffmpeg", ["-version"]), ("ffprobe", ["-version"]), ("rubberband", ["--version"])]:
    try:
        r = subprocess.run([tool] + args, capture_output=True, text=True, timeout=5)
        print(f"  {tool}: {(r.stdout or r.stderr).split(chr(10))[0][:80]}")
    except FileNotFoundError:
        print(f"  {tool}: NOT FOUND")

# rubberband in ffmpeg
r = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=5)
rb_avail = "rubberband" in r.stdout
print(f"  ffmpeg rubberband filter: {'YES' if rb_avail else 'NO'}")

for lib in ["numpy", "soundfile", "pyrubberband", "librosa", "mutagen", "openpyxl"]:
    try:
        __import__(lib)
        print(f"  python {lib}: YES")
    except ImportError:
        print(f"  python {lib}: NO")

# ─────────────────────────────────────────────────────────────────────────
# 7. ANLZ
# ─────────────────────────────────────────────────────────────────────────
section("REKORDBOX ANLZ")
anlz_root = Path("/Users/g/Library/Pioneer/rekordbox/share/PIONEER/USBANLZ")
if anlz_root.exists():
    exts = Counter()
    for f in anlz_root.rglob("*"):
        if f.is_file():
            exts[f.suffix] += 1
    print(f"  Files by ext: {dict(exts.most_common())}")
    dat = list(anlz_root.rglob("*.DAT"))
    if dat:
        with open(dat[0], "rb") as f:
            magic = f.read(4)
            print(f"  DAT magic: {magic} ({magic.hex()})")
else:
    print("  NOT FOUND")

# ─────────────────────────────────────────────────────────────────────────
# 8. MIK BUNDLE
# ─────────────────────────────────────────────────────────────────────────
section("MIK APP BUNDLE")
mik = Path("/Applications/Mixed In Key 11.app/Contents")
if mik.exists():
    momds = list(mik.rglob("*.momd"))
    print(f"  CoreData models: {len(momds)}")
    for m in momds:
        print(f"    {m.relative_to(mik)}")
        if m.is_dir():
            for item in sorted(m.iterdir()):
                print(f"      {item.name} ({item.stat().st_size}b)")
    
    fws = [f.name for f in (mik / "Frameworks").iterdir() if f.suffix == '.framework'] if (mik / "Frameworks").exists() else []
    print(f"  Frameworks: {sorted(fws)}")
    
    mls = list(mik.rglob("*.mlmodelc"))
    print(f"  CoreML models: {len(mls)}")
    for m in mls:
        print(f"    {m.relative_to(mik)}")

print("\n\nDONE")
