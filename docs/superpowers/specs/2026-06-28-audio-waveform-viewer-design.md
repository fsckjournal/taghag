# Audio Waveform Viewer Design

## Goal

Replace `spectralwaveform.py` with a focused viewer that displays the complete
audio file as an Audacity-style stereo waveform. The viewer does not generate
machine-learning features, targets, datasets, or analysis artifacts.

## Interface

Running the script opens the waveform for
`/Users/g/Desktop/transition_stretch.flac`. An optional positional argument
selects another local audio file:

```bash
.venv/bin/python spectralwaveform.py [audio-file]
```

## Rendering

- Read audio at its native sample rate and preserve its channels.
- Display the full duration on a time axis.
- Render stereo audio as two stacked green waveforms on a dark background.
- Reduce each channel to pixel-scale minimum and maximum envelopes before
  plotting. This preserves visible peaks without drawing millions of samples.
- Display mono audio in one waveform panel.

## Errors and Scope

Missing, unreadable, or unsupported files produce a concise command-line
error. The script remains a local viewer: it does not modify audio, upload it,
export derived files, detect beats, or add spectral and ML analysis.

## Verification

Automated tests cover envelope reduction, mono/stereo handling, and command-line
path selection. A headless render of the 47.361-second reference FLAC verifies
that the complete stereo waveform can be constructed without opening a window.
