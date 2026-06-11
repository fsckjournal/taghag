from __future__ import annotations

import json
import math
from typing import Any


class SonicPolicy:
    def __init__(
        self,
        noise_threshold: float = 0.20,
        weak_threshold: float = 0.49,
        meaningful_threshold: float = 0.50,
        core_identity_threshold: float = 0.80,
        dynamic_evolution_delta_threshold: float = 0.40,
    ) -> None:
        self.noise_threshold = noise_threshold
        self.weak_threshold = weak_threshold
        self.meaningful_threshold = meaningful_threshold
        self.core_identity_threshold = core_identity_threshold
        self.dynamic_evolution_delta_threshold = dynamic_evolution_delta_threshold


def compute_sonic_vector(
    happy: float,
    aggressive: float,
    relaxed: float,
    party: float,
    danceability: float,
    bpm: float,
    energy: float,
) -> list[float]:
    """
    Computes the 7-dimensional L2-normalized sonic vector:
    [energy_norm, bpm_norm, danceability, party, happy, aggressive, relaxed]
    
    Uses log-normalized BPM mapping to prevent clipping.
    """
    # Normalize energy (assuming 1-10 range)
    energy_norm = min(max(energy / 10.0, 0.0), 1.0)

    # Log-normalized BPM: log2(bpm / 60.0) / log2(200.0 / 60.0)
    # Clamp BPM to 60-200 range
    clamped_bpm = min(max(bpm, 60.0), 200.0)
    bpm_norm = math.log2(clamped_bpm / 60.0) / math.log2(200.0 / 60.0)

    vec = [energy_norm, bpm_norm, danceability, party, happy, aggressive, relaxed]

    # L2 Normalize the vector
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        return [v / norm for v in vec]
    return vec


def classify_producer_vibes(
    happy: float,
    aggressive: float,
    relaxed: float,
    party: float,
    danceability: float,
    policy: SonicPolicy | None = None,
) -> list[str]:
    """Heuristic classifications for producer vibes based on Essentia attributes."""
    p = policy or SonicPolicy()
    vibes = []

    # Peak Time House
    if danceability >= p.core_identity_threshold and \
       party >= p.core_identity_threshold and \
       aggressive < p.meaningful_threshold:
        vibes.append("peak_time_house")

    # Moody Deep
    if happy < 0.30 and relaxed < p.meaningful_threshold and aggressive < 0.60:
        vibes.append("moody_deep")

    # Warm Dancefloor
    if danceability >= 0.65 and aggressive < 0.35 and happy >= 0.30:
        vibes.append("warm_dancefloor")

    # Driving Tool
    if danceability >= 0.70 and aggressive >= p.meaningful_threshold and party >= 0.40:
        vibes.append("driving_tool")

    # Low Pressure Opener
    if party < p.meaningful_threshold and aggressive < 0.35 and danceability >= 0.45:
        vibes.append("low_pressure_opener")

    # Leftfield Bridge
    if max(happy, aggressive, relaxed, party, danceability) < p.core_identity_threshold:
        vibes.append("leftfield_bridge")

    return vibes


def classify_complexity_tags(
    happy: float,
    aggressive: float,
    relaxed: float,
    party: float,
    danceability: float,
    dynamic_evolution: bool = False,
    policy: SonicPolicy | None = None,
) -> list[str]:
    """Heuristic classifications for track complexity tags."""
    p = policy or SonicPolicy()
    tags = []

    if dynamic_evolution:
        tags.append("dynamic_evolution")

    # Tension Builder
    if (party >= 0.50 or danceability >= 0.65) and happy < 0.50:
        tags.append("tension_builder")

    # Simple Peak Anchor
    if party >= p.core_identity_threshold and \
       danceability >= p.core_identity_threshold and \
       aggressive < 0.35:
        tags.append("simple_peak_anchor")

    return tags
