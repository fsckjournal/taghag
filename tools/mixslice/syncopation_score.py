"""Rank playlist FLACs by how STRAIGHT (un-syncopated) the kick pattern is.

ML-free: bandpass to the kick band, build an energy envelope, lock the beat
phase using the track's Rekordbox BPM, then measure how concentrated energy is
ON the beat vs on the off-beat ("and"). Straight 4/4 -> high on-beat, low
off-beat. Syncopated -> energy displaced off the beat.
"""
import os, sys, urllib.parse, xml.etree.ElementTree as ET
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, decimate

M3U = "/Volumes/PLAYGROUND/MINIMAL/minimal-rekordbox.m3u8"
RBX = "/Volumes/PLAYGROUND/MINIMAL/rbx.xml"
SECS = 90.0          # analyze first 90 s
TARGET_SR = 4000     # kick band only -> 4 kHz is plenty


def loc2path(u):
    return urllib.parse.unquote(u).replace("file://localhost", "") if u else None


def rbx_bpm():
    root = ET.parse(RBX).getroot()
    by = {}
    for t in root.findall(".//TRACK"):
        p = loc2path(t.get("Location")); b = t.get("AverageBpm")
        if p and b and float(b) > 0:
            by[os.path.normpath(p)] = float(b)
            by[os.path.splitext(os.path.basename(p))[0].lower()] = float(b)
    return by


def kick_env(path):
    audio, sr = sf.read(path, frames=int(SECS * 192000), dtype="float64", always_2d=True)
    x = audio.mean(axis=1)
    # decimate to ~4 kHz
    q = max(1, int(sr // TARGET_SR))
    if q > 1:
        # decimate in stages for stability
        while q > 13:
            x = decimate(x, 10, ftype="iir"); sr //= 10; q = max(1, int(sr // TARGET_SR))
        if q > 1:
            x = decimate(x, q, ftype="iir"); sr //= q
    sos = butter(4, [30, 160], btype="band", fs=sr, output="sos")
    k = sosfiltfilt(sos, x)
    env = np.abs(k)
    return env, sr


def straightness(env, sr, bpm):
    period = 60.0 / bpm
    n = len(env)
    win = int(0.04 * sr)  # +/-40 ms
    total = env.sum() + 1e-12
    # search beat phase that maximizes on-beat energy
    best_phi, best_on = 0.0, -1
    for phi in np.linspace(0, period, 24, endpoint=False):
        idx = (np.arange(phi, n / sr - period, period) * sr).astype(int)
        on = sum(env[max(0, i - win):i + win].sum() for i in idx)
        if on > best_on:
            best_on, best_phi = on, phi
    beats = (np.arange(best_phi, n / sr - period, period) * sr).astype(int)
    offs = (beats + int(period / 2 * sr))
    on = sum(env[max(0, i - win):i + win].sum() for i in beats)
    off = sum(env[max(0, i - win):min(n, i + win)].sum() for i in offs if i < n)
    on_ratio = on / total
    sync = off / (on + 1e-12)         # low = straight
    return on_ratio, sync


def main():
    order = [l.strip() for l in open(M3U, encoding="utf-8-sig")
             if l.strip() and not l.startswith("#")]
    bpm = rbx_bpm()

    def getbpm(p):
        return bpm.get(os.path.normpath(p)) or bpm.get(
            os.path.splitext(os.path.basename(p))[0].lower())

    rows = []
    for i, p in enumerate(order):
        b = getbpm(p)
        if not b or not os.path.exists(p):
            continue
        try:
            env, sr = kick_env(p)
            on_ratio, sync = straightness(env, sr, b)
            rows.append((sync, on_ratio, b, i, p))
        except Exception as e:
            print("skip", os.path.basename(p), e, file=sys.stderr)
    # straight = high on_ratio AND low sync; require a real 4/4 kick (on_ratio floor)
    strong = [r for r in rows if r[1] > 0.18]
    strong.sort(key=lambda r: (r[0], -r[1]))
    print(f"scored {len(rows)} tracks; {len(strong)} have a strong on-beat kick\n")
    print("STRAIGHTEST (low sync, strong on-beat):")
    for sync, onr, b, i, p in strong[:14]:
        print(f"  sync={sync:.2f} on={onr:.2f} bpm={b:.1f} pos{i:>3}  {os.path.basename(p)}")
    print("\nMOST SYNCOPATED (for contrast):")
    for sync, onr, b, i, p in sorted(strong, key=lambda r: -r[0])[:5]:
        print(f"  sync={sync:.2f} on={onr:.2f} bpm={b:.1f} pos{i:>3}  {os.path.basename(p)}")


if __name__ == "__main__":
    main()
