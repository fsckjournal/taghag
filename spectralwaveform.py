"""Waveform reduction and repeated-ceiling diagnostics."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _immutable_float_array(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class Envelope:
    """Per-column waveform extrema and root-mean-square levels."""

    time_seconds: NDArray[np.float64]
    minimum: NDArray[np.float64]
    maximum: NDArray[np.float64]
    rms: NDArray[np.float64]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "time_seconds", _immutable_float_array(self.time_seconds)
        )
        object.__setattr__(self, "minimum", _immutable_float_array(self.minimum))
        object.__setattr__(self, "maximum", _immutable_float_array(self.maximum))
        object.__setattr__(self, "rms", _immutable_float_array(self.rms))


@dataclass(frozen=True)
class CeilingSpan:
    """A contiguous time range with a repeatedly reached symmetric ceiling."""

    start_seconds: float
    end_seconds: float
    ceiling: float


def reduce_envelope(samples: ArrayLike, columns: int) -> Envelope:
    """Reduce a one-dimensional signal into contiguous display columns."""

    signal = np.asarray(samples, dtype=np.float64)
    if signal.ndim != 1:
        raise ValueError("samples must be one-dimensional")
    if columns <= 0:
        raise ValueError("columns must be positive")
    if signal.size < columns:
        raise ValueError("columns cannot exceed the number of samples")

    bins = np.array_split(signal, columns)
    starts = np.cumsum([0, *(len(block) for block in bins[:-1])], dtype=np.float64)

    return Envelope(
        time_seconds=starts,
        minimum=np.array([np.min(block) for block in bins]),
        maximum=np.array([np.max(block) for block in bins]),
        rms=np.array([np.sqrt(np.mean(np.square(block))) for block in bins]),
    )


def detect_repeated_ceilings(
    samples: ArrayLike,
    sample_rate: float,
    window_seconds: float = 4.0,
    minimum_hits: int = 8,
) -> list[CeilingSpan]:
    """Find fixed windows that repeatedly hit matching positive/negative extrema."""

    channels = np.asarray(samples, dtype=np.float64)
    if channels.ndim != 2:
        raise ValueError("samples must be a two-dimensional frames-by-channels array")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    if minimum_hits <= 0:
        raise ValueError("minimum_hits must be positive")

    window_frames = int(round(sample_rate * window_seconds))
    if window_frames <= 0:
        raise ValueError("window_seconds is too short for the sample rate")

    spans: list[CeilingSpan] = []
    total_frames = channels.shape[0]
    for start_frame in range(0, total_frames, window_frames):
        end_frame = min(start_frame + window_frames, total_frames)
        window = channels[start_frame:end_frame]
        if window.size == 0:
            continue

        matching_ceilings = []
        for channel in window.T:
            ceiling = float(np.max(channel))
            floor = float(np.min(channel))
            if (
                ceiling > 0.0
                and floor == -ceiling
                and np.count_nonzero(channel == ceiling) >= minimum_hits
                and np.count_nonzero(channel == floor) >= minimum_hits
            ):
                matching_ceilings.append(ceiling)
        if not matching_ceilings:
            continue
        ceiling = max(matching_ceilings)

        start_seconds = start_frame / sample_rate
        end_seconds = end_frame / sample_rate
        if (
            spans
            and spans[-1].end_seconds == start_seconds
            and spans[-1].ceiling == ceiling
        ):
            previous = spans[-1]
            spans[-1] = CeilingSpan(
                start_seconds=previous.start_seconds,
                end_seconds=end_seconds,
                ceiling=ceiling,
            )
        else:
            spans.append(
                CeilingSpan(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    ceiling=ceiling,
                )
            )

    return spans
