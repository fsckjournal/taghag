# Audio Waveform Viewer Design

## Goal

Replace `spectralwaveform.py` with a focused viewer that displays the complete
audio file as an Audacity-style waveform with a syncopation-tolerant pulse
track. The overview should make arrangement problems visible, including the
reference transition's long sparse kick-only passage after the outgoing track
fades. The viewer does not generate machine-learning features, targets,
datasets, scores, or analysis artifacts.

## Interface

Running the script opens the waveform for
`/Users/g/Desktop/transition_stretch.flac`. An optional positional argument
selects another local audio file:

```bash
.venv/bin/python spectralwaveform.py [audio-file]
```

## Rendering

- Read audio at its native sample rate.
- Display the full duration on a time axis.
- Render a combined peak envelope on a dark background.
- Reduce each channel to pixel-scale minimum and maximum envelopes before
  plotting. This preserves visible peaks without drawing millions of samples.
- Draw an inner RMS envelope so the dense, heavily limited opening remains
  distinguishable from later transient peaks.
- Color the envelope by broad spectral balance so bass-dominant kick passages
  remain visually distinct from fuller sections.
- Mark repeated positive or negative sample ceilings separately from ordinary
  peaks. This exposes clipping or limiting that was subsequently gain-reduced;
  it does not require the ceiling to remain at digital full scale.
- Add a separate marker track based on Predominant Local Pulse (PLP). These are
  pulse markers, not claimed downbeats or bar positions.
- Keep the full overview readable instead of automatically judging the cue.

## Errors and Scope

Missing, unreadable, or unsupported files produce a concise command-line
error. The script remains a local viewer: it does not modify audio, upload it,
export derived files, assign a quality score, separate the source tracks, or
recommend a replacement cue.

## Verification

Automated tests cover peak and RMS envelope reduction, mono/stereo handling,
repeated-ceiling detection, spectral-color aggregation, PLP marker extraction,
and command-line path selection. A headless render of the 47.361-second
reference FLAC verifies that the complete waveform and pulse track can be
constructed without opening a window.
