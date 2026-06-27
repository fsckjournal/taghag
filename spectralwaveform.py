"""Display a complete audio file with syncopation-tolerant pulse markers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import librosa
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from numpy.typing import ArrayLike, NDArray

DEFAULT_AUDIO_FILE = Path("/Users/g/Desktop/transition_stretch.flac")


def reduce_waveform(
    samples: ArrayLike,
    sample_rate: float,
    columns: int = 2400,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Reduce a signal to peak-preserving display columns."""

    signal = np.asarray(samples, dtype=np.float64)
    if signal.ndim != 1 or signal.size == 0:
        raise ValueError("samples must be a non-empty one-dimensional signal")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if columns <= 0:
        raise ValueError("columns must be positive")

    bins = np.array_split(signal, min(columns, signal.size))
    starts = np.cumsum(
        [0, *(len(block) for block in bins[:-1])],
        dtype=np.float64,
    )
    times = starts / sample_rate
    minimum = np.array([np.min(block) for block in bins])
    maximum = np.array([np.max(block) for block in bins])
    return times, minimum, maximum


def plp_pulse_times(
    samples: ArrayLike,
    sample_rate: float,
    hop_length: int = 512,
) -> NDArray[np.float64]:
    """Return Predominant Local Pulse maxima as times, not claimed downbeats."""

    signal = np.asarray(samples, dtype=np.float32)
    if signal.ndim != 1 or signal.size == 0:
        raise ValueError("samples must be a non-empty one-dimensional signal")

    onset_envelope = librosa.onset.onset_strength(
        y=signal,
        sr=sample_rate,
        hop_length=hop_length,
    )
    if onset_envelope.size < 2:
        return np.array([], dtype=np.float64)

    pulse = librosa.beat.plp(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=hop_length,
        win_length=min(384, onset_envelope.size),
    )
    frames = np.flatnonzero(librosa.util.localmax(pulse))
    return librosa.frames_to_time(
        frames,
        sr=sample_rate,
        hop_length=hop_length,
    )


def render_waveform(
    audio_file: str | Path,
    columns: int = 2400,
) -> Figure:
    """Build the full-duration waveform and PLP marker figure."""

    path = Path(audio_file).expanduser()
    channels, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if channels.size == 0:
        raise ValueError(f"audio file is empty: {path}")

    mono = np.mean(channels, axis=1)
    duration = len(mono) / sample_rate
    times, minimum, maximum = reduce_waveform(
        mono,
        sample_rate=sample_rate,
        columns=columns,
    )
    pulses = plp_pulse_times(mono, sample_rate)

    figure, (waveform_axis, pulse_axis) = plt.subplots(
        2,
        1,
        figsize=(16, 7),
        sharex=True,
        gridspec_kw={"height_ratios": (9, 1), "hspace": 0.04},
        facecolor="#111318",
    )

    segments = np.stack(
        (
            np.column_stack((times, minimum)),
            np.column_stack((times, maximum)),
        ),
        axis=1,
    )
    waveform_axis.add_collection(
        LineCollection(segments, colors="#777dff", linewidths=1.0)
    )
    waveform_axis.axhline(0.0, color="#aeb2ff", linewidth=0.5, alpha=0.45)
    waveform_axis.set_xlim(0.0, duration)
    waveform_axis.set_ylim(-1.05, 1.05)
    waveform_axis.set_ylabel("Amplitude")
    waveform_axis.set_title(path.name, color="#f2f3f5", pad=12)

    pulse_axis.vlines(pulses, 0.15, 0.85, color="#ff9f1c", linewidth=0.8)
    pulse_axis.scatter(
        pulses,
        np.full_like(pulses, 0.5),
        color="#ffb347",
        edgecolors="#4d2b00",
        linewidths=0.4,
        s=15,
        zorder=3,
    )
    pulse_axis.set_ylim(0.0, 1.0)
    pulse_axis.set_yticks([])
    pulse_axis.set_xlabel("Time (seconds)")
    pulse_axis.set_ylabel("PLP", rotation=0, labelpad=18, va="center")

    for axis in (waveform_axis, pulse_axis):
        axis.set_facecolor("#20232a")
        axis.tick_params(colors="#c9ccd3")
        axis.xaxis.label.set_color("#c9ccd3")
        axis.yaxis.label.set_color("#c9ccd3")
        for spine in axis.spines.values():
            spine.set_color("#3b3f48")

    figure.subplots_adjust(left=0.06, right=0.99, top=0.93, bottom=0.09)
    return figure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show a full audio waveform with PLP pulse markers."
    )
    parser.add_argument(
        "audio_file",
        nargs="?",
        type=Path,
        default=DEFAULT_AUDIO_FILE,
        help=f"audio file to display (default: {DEFAULT_AUDIO_FILE})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        render_waveform(arguments.audio_file)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
