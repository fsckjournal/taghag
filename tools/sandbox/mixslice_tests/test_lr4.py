import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt

def test_crossover():
    # Create dummy audio
    sr = 44100
    t = np.linspace(0, 1, sr, endpoint=False)
    audio = np.sin(2 * np.pi * 100 * t) + np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 5000 * t)
    audio = audio[:, None] # (frames, channels)

    # 1. 2nd order Butterworth, applied with filtfilt -> 4th order Linkwitz-Riley (zero phase)
    # BUT wait, |H_L|^2 + |H_H|^2 = 1 is true for continuous time.
    # In discrete time (bilinear transform), is it exactly 1?
    
    def lr4_split(x, freq, sr):
        b_low, a_low = butter(2, freq / (sr / 2), btype='low')
        b_high, a_high = butter(2, freq / (sr / 2), btype='high')
        
        low = filtfilt(b_low, a_low, x, axis=0)
        high = filtfilt(b_high, a_high, x, axis=0)
        return low, high

    low, mid_high = lr4_split(audio, 250, sr)
    mid, high = lr4_split(mid_high, 2500, sr)

    summed = low + mid + high
    err = np.max(np.abs(summed - audio))
    print(f"Error (filtfilt butter): {err}")
    
    # Another approach: complementary filtering
    # To guarantee exact time-domain reconstruction:
    # low = filtfilt(b_low, a_low, x)
    # high = x - low
    def exact_split(x, freq, sr):
        b_low, a_low = butter(2, freq / (sr / 2), btype='low')
        low = filtfilt(b_low, a_low, x, axis=0)
        high = x - low
        return low, high

    low2, mid_high2 = exact_split(audio, 250, sr)
    mid2, high2 = exact_split(mid_high2, 2500, sr)
    
    summed2 = low2 + mid2 + high2
    err2 = np.max(np.abs(summed2 - audio))
    print(f"Error (exact complementary): {err2}")

test_crossover()
