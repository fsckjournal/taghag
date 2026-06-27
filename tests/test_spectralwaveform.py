import math
import unittest
from dataclasses import FrozenInstanceError

import numpy as np

from spectralwaveform import (
    CeilingSpan,
    Envelope,
    detect_repeated_ceilings,
    reduce_envelope,
)


class ReduceEnvelopeTests(unittest.TestCase):
    def test_preserves_minimum_maximum_and_rms_in_contiguous_bins(self) -> None:
        samples = np.array([-1.0, 0.0, 0.5, 1.0, -0.5, 0.5])

        envelope = reduce_envelope(samples, columns=3)

        np.testing.assert_allclose(envelope.minimum, [-1.0, 0.5, -0.5])
        np.testing.assert_allclose(envelope.maximum, [0.0, 1.0, 0.5])
        np.testing.assert_allclose(
            envelope.rms,
            [math.sqrt(0.5), math.sqrt(0.625), 0.5],
        )

    def test_envelope_is_immutable(self) -> None:
        envelope = Envelope(
            time_seconds=np.array([0.0]),
            minimum=np.array([-1.0]),
            maximum=np.array([1.0]),
            rms=np.array([1.0]),
        )

        with self.assertRaises(FrozenInstanceError):
            envelope.rms = np.array([0.0])


class RepeatedCeilingTests(unittest.TestCase):
    def test_detects_symmetric_repeated_ceiling_in_two_channels(self) -> None:
        one_channel = np.tile(np.array([0.75, -0.75]), 10)
        samples = np.column_stack((one_channel, one_channel))

        spans = detect_repeated_ceilings(
            samples,
            sample_rate=10,
            window_seconds=2.0,
            minimum_hits=8,
        )

        self.assertEqual(
            spans,
            [CeilingSpan(start_seconds=0.0, end_seconds=2.0, ceiling=0.75)],
        )

    def test_ceiling_span_is_immutable(self) -> None:
        span = CeilingSpan(start_seconds=0.0, end_seconds=2.0, ceiling=0.75)

        with self.assertRaises(FrozenInstanceError):
            span.ceiling = 1.0


if __name__ == "__main__":
    unittest.main()
