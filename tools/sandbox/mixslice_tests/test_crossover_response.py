import numpy as np
from scipy.signal import butter, filtfilt

def test_crossover():
    sr = 44100
    # impulse response
    x = np.zeros((4096, 1))
    x[2048, 0] = 1.0

    def low_pass(audio, freq):
        b, a = butter(2, freq / (sr / 2.0), btype='low')
        return filtfilt(b, a, audio, axis=0)

    low = low_pass(x, 250.0)
    mid_high = x - low
    mid = low_pass(mid_high, 2500.0)
    high = mid_high - mid
    
    summed = low + mid + high
    print(f"Max error: {np.max(np.abs(summed - x))}")
    
    import matplotlib.pyplot as plt
    f = np.fft.rfftfreq(len(x), 1/sr)
    L = 20 * np.log10(np.abs(np.fft.rfft(low, axis=0)) + 1e-10)
    M = 20 * np.log10(np.abs(np.fft.rfft(mid, axis=0)) + 1e-10)
    H = 20 * np.log10(np.abs(np.fft.rfft(high, axis=0)) + 1e-10)
    
    # Just print values at certain freqs to check
    def print_db(freq):
        idx = np.argmin(np.abs(f - freq))
        print(f"{freq}Hz -> Low: {L[idx,0]:.1f}dB, Mid: {M[idx,0]:.1f}dB, High: {H[idx,0]:.1f}dB")

    print_db(50)
    print_db(250)
    print_db(1000)
    print_db(2500)
    print_db(10000)

test_crossover()
