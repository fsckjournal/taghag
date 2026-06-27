import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from spectralwaveform import (
    DEFAULT_AUDIO_FILE,
    build_parser,
    plp_pulse_times,
    reduce_waveform,
    render_waveform,
)


class WaveformViewerTests(unittest.TestCase):
    def test_reduce_waveform_preserves_full_duration_and_peaks(self) -> None:
        samples = np.array([-1.0, 0.0, 0.5, 1.0, -0.5, 0.5])

        times, minimum, maximum = reduce_waveform(
            samples,
            sample_rate=2,
            columns=3,
        )

        np.testing.assert_allclose(times, [0.0, 1.0, 2.0])
        np.testing.assert_allclose(minimum, [-1.0, 0.5, -0.5])
        np.testing.assert_allclose(maximum, [0.0, 1.0, 0.5])

    def test_plp_pulses_are_sorted_and_bounded(self) -> None:
        sample_rate = 22050
        samples = np.zeros(sample_rate * 4)
        samples[(np.arange(0.25, 4.0, 0.25) * sample_rate).astype(int)] = 1.0

        pulses = plp_pulse_times(samples, sample_rate)

        self.assertGreater(len(pulses), 4)
        self.assertTrue(np.all(np.diff(pulses) > 0))
        self.assertGreaterEqual(pulses[0], 0.0)
        self.assertLessEqual(pulses[-1], 4.0)

    def test_render_waveform_covers_complete_file(self) -> None:
        sample_rate = 8000
        time = np.arange(sample_rate * 2) / sample_rate
        stereo = np.column_stack(
            (
                0.5 * np.sin(2 * np.pi * 100 * time),
                0.5 * np.sin(2 * np.pi * 200 * time),
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            sf.write(path, stereo, sample_rate)
            figure = render_waveform(path, columns=128)

        self.assertEqual(len(figure.axes), 2)
        self.assertEqual(figure.axes[0].get_xlim(), (0.0, 2.0))

    def test_parser_uses_reference_file_by_default(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.parse_args([]).audio_file, DEFAULT_AUDIO_FILE)
        self.assertEqual(parser.parse_args(["other.flac"]).audio_file, Path("other.flac"))


if __name__ == "__main__":
    unittest.main()
