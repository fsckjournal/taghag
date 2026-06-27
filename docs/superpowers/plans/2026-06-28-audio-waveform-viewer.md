# Audio Waveform Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the experimental ML exporter with a full-duration waveform viewer that exposes spectral sparsity, PLP pulse structure, and repeated attenuated clipping ceilings.

**Architecture:** `spectralwaveform.py` remains a standalone script. Pure NumPy helpers prepare display envelopes and repeated-ceiling spans, librosa supplies spectral balance and PLP pulses, and one Matplotlib renderer composes the waveform and marker track. Standard-library `unittest` tests exercise the helpers and renderer without adding a test dependency.

**Tech Stack:** Python 3.11, NumPy, SoundFile, librosa, Matplotlib, unittest

---

## File Structure

- Modify `spectralwaveform.py`: audio loading, deterministic display analysis,
  Matplotlib rendering, and command-line entry point.
- Create `tests/__init__.py`: make the root test directory importable.
- Create `tests/test_spectralwaveform.py`: focused unit and headless rendering
  tests.

### Task 1: Peak, RMS, and repeated-ceiling helpers

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_spectralwaveform.py`
- Modify: `spectralwaveform.py`

- [ ] **Step 1: Write failing envelope and ceiling tests**

```python
import unittest

import numpy as np

from spectralwaveform import detect_repeated_ceilings, reduce_envelope


class EnvelopeTests(unittest.TestCase):
    def test_reduce_envelope_preserves_peaks_and_rms(self):
        samples = np.array([-1.0, 0.0, 0.5, 1.0, -0.5, 0.5])
        envelope = reduce_envelope(samples, columns=3)
        np.testing.assert_allclose(envelope.minimum, [-1.0, 0.5, -0.5])
        np.testing.assert_allclose(envelope.maximum, [0.0, 1.0, 0.5])
        np.testing.assert_allclose(
            envelope.rms,
            [np.sqrt(0.5), np.sqrt(0.625), 0.5],
        )

    def test_detect_repeated_ceilings_finds_attenuated_clipping(self):
        block = np.array([0.0, 0.75, -0.75, 0.75, -0.75] * 4)
        samples = np.column_stack([block, block])
        spans = detect_repeated_ceilings(
            samples,
            sample_rate=10,
            window_seconds=2.0,
            minimum_hits=3,
        )
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].start_seconds, 0.0)
        self.assertEqual(spans[0].end_seconds, 2.0)
        self.assertAlmostEqual(spans[0].ceiling, 0.75)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform -v
```

Expected: import failure because `detect_repeated_ceilings` and
`reduce_envelope` do not exist.

- [ ] **Step 3: Replace the ML structures with envelope primitives**

Implement immutable `Envelope` and `CeilingSpan` dataclasses. Implement
`reduce_envelope(samples, columns)` by splitting a one-dimensional signal into
contiguous bins and retaining the minimum, maximum, and RMS of every bin.
Implement `detect_repeated_ceilings(samples, sample_rate, window_seconds=4.0,
minimum_hits=8)` by scanning each channel in fixed windows and reporting a
window only when its exact positive and negative extrema are symmetric and each
repeats at least `minimum_hits` times.

```python
@dataclass(frozen=True)
class Envelope:
    time_seconds: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray
    rms: np.ndarray


@dataclass(frozen=True)
class CeilingSpan:
    start_seconds: float
    end_seconds: float
    ceiling: float
```

Adjacent matching ceiling windows must merge into one span so the reference
file's opening appears as one continuous region.

- [ ] **Step 4: Run the tests and verify GREEN**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit the helper layer**

```bash
git add spectralwaveform.py tests/__init__.py tests/test_spectralwaveform.py
git commit -m "feat: add waveform envelope diagnostics"
```

### Task 2: Spectral balance and PLP pulse markers

**Files:**
- Modify: `tests/test_spectralwaveform.py`
- Modify: `spectralwaveform.py`

- [ ] **Step 1: Write failing spectral and pulse tests**

```python
from spectralwaveform import spectral_colors, syncopated_pulse_times


class AudioAnalysisTests(unittest.TestCase):
    def test_spectral_colors_distinguish_bass_from_high_frequency(self):
        sample_rate = 22050
        time = np.arange(sample_rate * 2) / sample_rate
        bass = np.sin(2 * np.pi * 100 * time)
        high = np.sin(2 * np.pi * 5000 * time)
        bass_colors = spectral_colors(bass, sample_rate, columns=32)
        high_colors = spectral_colors(high, sample_rate, columns=32)
        self.assertGreater(bass_colors[:, 0].mean(), bass_colors[:, 2].mean())
        self.assertGreater(high_colors[:, 2].mean(), high_colors[:, 0].mean())

    def test_syncopated_pulse_times_are_sorted_and_bounded(self):
        sample_rate = 22050
        samples = np.zeros(sample_rate * 4)
        click_frames = (np.arange(0.25, 4.0, 0.25) * sample_rate).astype(int)
        samples[click_frames] = 1.0
        pulses = syncopated_pulse_times(samples, sample_rate)
        self.assertGreater(len(pulses), 4)
        self.assertTrue(np.all(np.diff(pulses) > 0))
        self.assertGreaterEqual(pulses[0], 0.0)
        self.assertLessEqual(pulses[-1], 4.0)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform.AudioAnalysisTests -v
```

Expected: import failure because `spectral_colors` and
`syncopated_pulse_times` do not exist.

- [ ] **Step 3: Implement display-only spectral and pulse analysis**

Implement `spectral_colors(samples, sample_rate, columns)` with a power STFT at
the native sample rate. Aggregate 20–250 Hz into red, 250–2500 Hz into green,
and 2500 Hz up to Nyquist into blue. Interpolate the frame colors to exactly
`columns` rows and normalize each RGB row by its largest component.

Implement `syncopated_pulse_times(samples, sample_rate, hop_length=512)` with
`librosa.onset.onset_strength`, `librosa.beat.plp`, and local maxima. Return
frame times only; do not call them downbeats and do not calculate a quality
score.

- [ ] **Step 4: Run the complete tests and verify GREEN**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the display analysis**

```bash
git add spectralwaveform.py tests/test_spectralwaveform.py
git commit -m "feat: add spectral pulse visualization data"
```

### Task 3: Full-duration renderer and CLI

**Files:**
- Modify: `tests/test_spectralwaveform.py`
- Modify: `spectralwaveform.py`

- [ ] **Step 1: Write the failing headless renderer test**

```python
import tempfile
from pathlib import Path

import soundfile as sf

from spectralwaveform import build_parser, render_audio_waveform


class RendererTests(unittest.TestCase):
    def test_renderer_covers_the_complete_file(self):
        sample_rate = 8000
        time = np.arange(sample_rate * 2) / sample_rate
        stereo = np.column_stack(
            [
                0.5 * np.sin(2 * np.pi * 100 * time),
                0.5 * np.sin(2 * np.pi * 200 * time),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            sf.write(path, stereo, sample_rate)
            figure = render_audio_waveform(path, columns=128)
            self.assertEqual(len(figure.axes), 2)
            self.assertAlmostEqual(figure.axes[0].get_xlim()[0], 0.0)
            self.assertAlmostEqual(figure.axes[0].get_xlim()[1], 2.0)

    def test_parser_accepts_an_optional_audio_path(self):
        parser = build_parser()
        default = parser.parse_args([])
        custom = parser.parse_args(["other.flac"])
        self.assertEqual(
            str(default.audio_file),
            "/Users/g/Desktop/transition_stretch.flac",
        )
        self.assertEqual(str(custom.audio_file), "other.flac")
```

- [ ] **Step 2: Run the renderer tests and verify RED**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform.RendererTests -v
```

Expected: import failure because `build_parser` and `render_audio_waveform` do
not exist.

- [ ] **Step 3: Implement the renderer and CLI**

`render_audio_waveform(path, columns=2400)` must:

1. Read native-rate audio with `soundfile.read(..., always_2d=True)`.
2. Average channels only for display analysis.
3. Draw peak segments with per-column spectral colors.
4. Draw the symmetric RMS envelope with stronger opacity.
5. Shade repeated-ceiling spans in magenta and label them “repeated ceiling.”
6. Draw PLP pulse lines and dots in a separate orange marker axis.
7. Share a zero-to-full-duration x-axis and return the `Figure`.

`build_parser()` must accept one optional `audio_file` positional argument,
defaulting to `/Users/g/Desktop/transition_stretch.flac`. `main()` must turn
missing or unreadable input into `parser.error(...)`, call the renderer, and
then call `plt.show()`.

- [ ] **Step 4: Run all focused tests and verify GREEN**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the working viewer**

```bash
git add spectralwaveform.py tests/test_spectralwaveform.py
git commit -m "feat: render full transition waveform"
```

### Task 4: Reference render and repository verification

**Files:**
- Modify only if verification exposes a defect:
  `spectralwaveform.py`, `tests/test_spectralwaveform.py`

- [ ] **Step 1: Render the complete reference FLAC headlessly**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python - <<'PY'
from pathlib import Path
from spectralwaveform import render_audio_waveform

figure = render_audio_waveform(
    Path("/Users/g/Desktop/transition_stretch.flac")
)
figure.savefig("/tmp/taghag-transition-waveform.png", dpi=160)
print(len(figure.axes), figure.axes[0].get_xlim())
PY
```

Expected: `2 (0.0, 47.360589569160996)` and a PNG at
`/tmp/taghag-transition-waveform.png`.

- [ ] **Step 2: Inspect the PNG**

Verify that the rendered image shows:

- the full 47.361-second transition;
- the dense, repeated-ceiling opening;
- the outgoing fade;
- the sparse bass-dominant kick passage;
- the full PLP marker track.

- [ ] **Step 3: Run regression and syntax verification**

Run:

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest tests.test_spectralwaveform -v
.venv/bin/python -m py_compile spectralwaveform.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and `git diff --check` emits no
errors.

- [ ] **Step 4: Audit the final diff for forbidden ML/export behavior**

Run:

```bash
rg -n "ml_|machine.learning|npz|targets|json.dump|quality.score" spectralwaveform.py
git diff -- spectralwaveform.py tests/test_spectralwaveform.py
```

Expected: the search returns no matches and the diff is limited to the viewer
and its tests.

- [ ] **Step 5: Push the completed commits**

```bash
git push origin main
```

Expected: the remote `main` branch advances through the viewer commits without
including unrelated working-tree changes.
