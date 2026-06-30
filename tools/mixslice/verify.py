import soundfile as sf
import numpy as np

mix, _ = sf.read('out.flac')
a, _ = sf.read('out.trackA.flac')
b, _ = sf.read('out.trackB.flac')

diff = np.max(np.abs(a + b - mix))
print(f"Max difference (a + b - mix): {diff}")
if diff > 1e-6:
    print("FAILED: Difference is greater than 1e-6!")
else:
    print("PASSED: Stems reconstruct mix perfectly.")
