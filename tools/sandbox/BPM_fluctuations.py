import librosa
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

audio_path = "/Users/g/Desktop/AB_autocue.flac"
print(f"Loading {audio_path}...\n")

y, sr = librosa.load(audio_path, sr=None)
hop_length = 64

onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

# 1. Auto-Detect the Global BPM
global_bpm = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop_length)[0]
tempo_min = max(60, global_bpm - 15)
tempo_max = min(200, global_bpm + 15)
print(f"Detected Global BPM: {global_bpm:.1f}. Setting bounding box to {tempo_min:.1f} - {tempo_max:.1f} BPM.")

# 2. Fix the Window Size Amnesia
# We need a temporal window of about 5 seconds to establish a solid rhythm.
# At hop_length=64 and sr=44100, this calculates to ~3445 frames (instead of the default 384).
win_frames = int(sr * 5.0 / hop_length)

# 3. Generate the PLP with the corrected window
pulse = librosa.beat.plp(
    onset_envelope=onset_env, 
    sr=sr, 
    hop_length=hop_length,
    win_length=win_frames,
    tempo_min=tempo_min, 
    tempo_max=tempo_max
)

# 4. Normalize
pulse_max = np.max(pulse)
if pulse_max == 0:
    print("Error: The PLP algorithm generated a flatline.")
else:
    pulse = pulse / pulse_max

    # 5. Dynamic Speed Limit
    min_dist = int((sr * (60.0 / tempo_max)) / hop_length)

    # 6. Find Peaks
    peaks, _ = find_peaks(pulse, distance=min_dist, height=0.1)

    # 7. Parabolic Interpolation (Sub-frame precision)
    def interpolate_peak(array, idx):
        if idx == 0 or idx == len(array) - 1:
            return float(idx)
        a, b, c = array[idx-1], array[idx], array[idx+1]
        denom = a - 2*b + c
        if denom == 0:
            return float(idx)
        return idx + 0.5 * (a - c) / denom

    exact_peaks = [interpolate_peak(pulse, p) for p in peaks]

    # 8. Convert and Calculate
    beat_times = librosa.frames_to_time(exact_peaks, sr=sr, hop_length=hop_length)
    beat_intervals = np.diff(beat_times)
    dynamic_bpm = 60.0 / beat_intervals

    tempo_data = pd.DataFrame({
        'beat_start (s)': beat_times[:-1],
        'beat_end (s)': beat_times[1:],
        'duration (s)': beat_intervals,
        'true_bpm': dynamic_bpm
    })

    print("\n--- Corrected High-Resolution Fluctuations ---")
    print(tempo_data.head(15))