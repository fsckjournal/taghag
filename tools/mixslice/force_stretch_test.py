import json
import soundfile as sf
import numpy as np
import subprocess
from scipy.signal import resample_poly

def run_test():
    with open('samples/B__mella_dee__realisation.analyzer.json') as f:
        data = json.load(f)
    
    # artificially speed up the grid by 1% (so it looks like track B is faster)
    for b in data['rhythm']['beats']:
        b['value'] = int(b['value'] * 0.99)
    for s in data['structure']['sections']:
        s['start']['value'] = int(s['start']['value'] * 0.99)
        
    with open('samples/B_stretched.analyzer.json', 'w') as f:
        json.dump(data, f)
        
    print("Running render_transition.py on stretched grid...")
    subprocess.run([
        'python3', 'render_transition.py',
        'samples/A__mike_shannon__search_party.flac',
        'samples/B__mella_dee__realisation.flac',
        'samples/A__mike_shannon__search_party.analyzer.json',
        'samples/B_stretched.analyzer.json',
        'out_stretched.flac',
        '--stems'
    ], check=True)
    
    mix, _ = sf.read('out_stretched.flac', always_2d=True)
    a, _ = sf.read('out_stretched.trackA.flac', always_2d=True)
    b, _ = sf.read('out_stretched.trackB.flac', always_2d=True)
    
    diff = np.max(np.abs(a + b - mix))
    print(f"Max difference (a + b - mix): {diff}")
    
    mix_4x = resample_poly(mix, 4, 1, axis=0)
    tp = np.max(np.abs(mix_4x))
    print(f"Measured 4x true-peak of written file: {tp:.6f}")

if __name__ == '__main__':
    run_test()
