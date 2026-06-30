import json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import pyrubberband as pyrb

def load_audio(path: str, out_sr: int) -> np.ndarray:
    """Loads audio and resamples it to `out_sr` if necessary."""
    audio, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != out_sr:
        from math import gcd
        g = gcd(out_sr, sr)
        audio = resample_poly(audio, out_sr // g, sr // g, axis=0)
    return audio

def sec_to_frame(t: float, sr: int) -> int:
    return int(round(t * sr))

def render_transition(track_a_path: str, track_b_path: str, payload: dict, out_path: str):
    """
    Renders an audio transition between two tracks using a pre-calculated Automix payload.
    
    The payload must contain:
    - track_a: {start_point, end_point, tempo}
    - track_b: {start_point, end_point, tempo}
    - transition_duration_a
    - transition_duration_b
    """
    a_meta = payload["track_a"]
    b_meta = payload["track_b"]

    a_start = a_meta["start_point"]
    a_end = a_meta["end_point"]
    b_start = b_meta["start_point"]
    b_end = b_meta["end_point"]

    out_sr = max(sf.info(track_a_path).samplerate, sf.info(track_b_path).samplerate)

    # Load audio
    a_audio = load_audio(track_a_path, out_sr)
    b_audio = load_audio(track_b_path, out_sr)

    # Ensure matching channels
    ch = max(a_audio.shape[1], b_audio.shape[1])
    def fit_ch(x):
        if x.shape[1] == ch:
            return x
        return np.repeat(x, ch, axis=1) if x.shape[1] == 1 else x[:, :ch]

    a_audio = fit_ch(a_audio)
    b_audio = fit_ch(b_audio)

    # Slicing Track A
    pre_fade = a_audio[:sec_to_frame(a_start, out_sr)]
    fade_a = a_audio[sec_to_frame(a_start, out_sr):sec_to_frame(a_end, out_sr)]

    # Slicing Track B
    fade_b_raw = b_audio[sec_to_frame(b_start, out_sr):sec_to_frame(b_end, out_sr)]
    post_fade = b_audio[sec_to_frame(b_end, out_sr):]

    # Time-stretch Track B overlap to match Track A's tempo
    # Using the single constant warp ratio (bpm_out / bpm_in)
    bpm_out = a_meta["tempo"]
    bpm_in = b_meta["tempo"]
    
    rate = bpm_out / bpm_in
    if abs(rate - 1.0) > 1e-4:
        fade_b = pyrb.time_stretch(fade_b_raw, out_sr, rate).astype(np.float64)
    else:
        fade_b = fade_b_raw

    # Length matching (ensure they have the exact same number of frames)
    n = min(len(fade_a), len(fade_b))
    fade_a = fade_a[:n]
    fade_b = fade_b[:n]

    # Equal power crossfade
    fade_out_curve = np.cos(np.linspace(0, np.pi / 2, n))[:, None]
    fade_in_curve = np.sin(np.linspace(0, np.pi / 2, n))[:, None]

    mixed = fade_a * fade_out_curve + fade_b * fade_in_curve

    # Concatenate all parts
    out = np.concatenate([pre_fade, mixed, post_fade], axis=0)

    # Hard limiter ceiling to avoid clipping
    CEIL = 0.84
    pk = float(np.max(np.abs(out)))
    if pk > CEIL:
        out *= CEIL / pk

    sf.write(out_path, out, out_sr, subtype="PCM_24")
    return out_path
