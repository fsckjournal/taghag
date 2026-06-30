import numpy as np

def nearest_beat(beats: np.ndarray, t: float) -> tuple[int, float]:
    i = int(np.argmin(np.abs(beats - t)))
    return i, float(beats[i])

# Just a test of logic before replacing
