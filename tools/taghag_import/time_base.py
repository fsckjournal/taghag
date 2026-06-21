"""Re-zero cue/segment grids onto the canonical clock (master-FLAC PCM sample 0).

Companion to the ``20260621000000_time_base_anchor`` migration and
``docs/design/2026-06-21-time-base-anchor.md``. A measurement made against a
rendition other than the master FLAC carries an unknown constant offset to
canonical, caused by encoder delay/padding, trim, or a separate analyzer grid.
``reconcile_offset`` computes that constant so canonicalizing a position is a
subtraction:

    canonical_ms = measured_ms - offset_ms

It picks the strongest method the inputs support:

1. ``identity``        -- source IS the canonical file (FLAC vs itself): offset 0.
2. ``cross_correlation`` -- correlate two cue grids (impulse trains) by voting
   over pairwise differences; the peak is the constant lag. Pure-Python, no
   audio decode. This is the workhorse for the human<->mixonset pair.
3. ``downbeat_anchor`` -- align one explicit anchor beat from each grid. Weak
   fallback when the grids are too sparse to vote.
4. ``declared_priming`` -- known codec priming: ``encoder_delay_samples /
   sample_rate_hz * 1000``. Cheap first guess when no grid overlap exists.

An optional PCM cross-correlation (``pcm_cross_correlation``) decodes both
renditions and correlates onset-strength envelopes; it needs ``librosa`` and is
skipped (returns ``None``) when that dependency is absent.

Empirical calibration (measured against live data, 2026-06-21): mixonset cues
land a small *positive* amount after the human grid on the same FLAC -- per
track in the +12..+18 ms band with MAD <= 3 ms, e.g. track ``3e08a729`` at
+17.75 ms (MAD 1.25). The offset is a stable small positive per track, not one
universal constant, which is why it is stored per (canonical, source, system).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# offset_method values; must match the CHECK constraint on rendition_time_offset.
METHOD_IDENTITY = "identity"
METHOD_DECLARED_PRIMING = "declared_priming"
METHOD_DOWNBEAT_ANCHOR = "downbeat_anchor"
METHOD_CROSS_CORRELATION = "cross_correlation"


@dataclass(frozen=True)
class RenditionTimeOffset:
    """A reconciled constant offset; ``canonical_ms = measured_ms - offset_ms``."""

    audio_file_id: str  # canonical rendition (master FLAC)
    measured_against_file_id: str | None  # source rendition; None for external grids
    source_system: str
    offset_ms: float
    offset_method: str
    residual_ms: float | None
    confidence: float

    def to_row(self, owner_user_id: str) -> dict[str, object]:
        """Shape this offset as a ``rendition_time_offset`` insert/upsert row."""
        return {
            "owner_user_id": owner_user_id,
            "audio_file_id": self.audio_file_id,
            "measured_against_file_id": self.measured_against_file_id,
            "source_system": self.source_system,
            "offset_ms": self.offset_ms,
            "offset_method": self.offset_method,
            "residual_ms": self.residual_ms,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class GridAlignment:
    """Result of correlating two cue grids: the winning constant lag and its spread."""

    offset_ms: float  # measured(source) - canonical
    residual_ms: float  # MAD of the contributing pairwise diffs (lower = tighter)
    votes: int  # pairs that agreed on the winning offset
    agreement: float  # votes / max matchable cues, in [0, 1]


def grid_offset(
    canonical_cues_ms: Sequence[float],
    source_cues_ms: Sequence[float],
    *,
    eps_ms: float = 8.0,
    window_ms: float = 60.0,
) -> GridAlignment | None:
    """Constant lag aligning ``source`` onto ``canonical`` by impulse-train voting.

    The two grids are not 1:1 -- human cues are few and hand-placed, mixonset
    cues are many predicted boundaries. Nearest-neighbour-then-median is polluted
    by the non-corresponding cues on both sides. Instead we collect every
    pairwise difference ``source - canonical`` within ``window_ms``, then find the
    difference value with the most neighbours inside ``eps_ms`` (the histogram
    peak). Non-corresponding cues scatter their diffs and do not form a peak;
    the truly corresponding cues pile up at the real lag. The offset is the mean
    of the peak's contributors and the residual is their MAD.

    Returns ``None`` when no pair falls inside ``window_ms`` (grids unrelated).
    """
    canon = sorted(_dedupe(canonical_cues_ms))
    src = sorted(_dedupe(source_cues_ms))
    if not canon or not src:
        return None

    diffs = [m - c for c in canon for m in src if abs(m - c) <= window_ms]
    if not diffs:
        return None

    # Histogram peak: the candidate with the most diffs within eps_ms of it.
    best_center: float | None = None
    best_contrib: list[float] = []
    for candidate in diffs:
        contrib = [d for d in diffs if abs(d - candidate) <= eps_ms]
        if len(contrib) > len(best_contrib):
            best_center, best_contrib = candidate, contrib

    if best_center is None:
        return None

    offset = statistics.fmean(best_contrib)
    residual = statistics.median([abs(d - offset) for d in best_contrib])
    votes = len(best_contrib)
    agreement = votes / max(1, min(len(canon), len(src)))
    return GridAlignment(
        offset_ms=round(offset, 3),
        residual_ms=round(residual, 3),
        votes=votes,
        agreement=min(1.0, agreement),
    )


def reconcile_offset(
    *,
    canonical_file_id: str,
    source_file_id: str | None,
    source_system: str,
    canonical_cues_ms: Sequence[float] | None = None,
    source_cues_ms: Sequence[float] | None = None,
    canonical_downbeat_ms: float | None = None,
    source_downbeat_ms: float | None = None,
    encoder_delay_samples: int | None = None,
    sample_rate_hz: int | None = None,
    eps_ms: float = 8.0,
    window_ms: float = 60.0,
    min_votes: int = 3,
) -> RenditionTimeOffset | None:
    """Reconcile one (canonical, source, system) offset via the strongest method.

    Preference, strongest first: ``identity`` (source is the canonical file) ->
    ``cross_correlation`` (confident grid vote) -> ``downbeat_anchor`` (explicit
    single-anchor) -> ``declared_priming`` (codec geometry). Returns ``None`` when
    no method has the inputs it needs.
    """
    # 1. identity -- the source rendition is the canonical FLAC itself.
    if source_file_id is not None and source_file_id == canonical_file_id:
        return RenditionTimeOffset(
            audio_file_id=canonical_file_id,
            measured_against_file_id=source_file_id,
            source_system=source_system,
            offset_ms=0.0,
            offset_method=METHOD_IDENTITY,
            residual_ms=0.0,
            confidence=1.0,
        )

    # 2. cross_correlation -- vote over the two cue grids.
    if canonical_cues_ms and source_cues_ms:
        align = grid_offset(
            canonical_cues_ms, source_cues_ms, eps_ms=eps_ms, window_ms=window_ms
        )
        if align is not None and align.votes >= min_votes:
            return RenditionTimeOffset(
                audio_file_id=canonical_file_id,
                measured_against_file_id=source_file_id,
                source_system=source_system,
                offset_ms=align.offset_ms,
                offset_method=METHOD_CROSS_CORRELATION,
                residual_ms=align.residual_ms,
                confidence=round(_grid_confidence(align, eps_ms), 3),
            )

    # 3. downbeat_anchor -- one explicit, trusted beat from each grid.
    if canonical_downbeat_ms is not None and source_downbeat_ms is not None:
        return RenditionTimeOffset(
            audio_file_id=canonical_file_id,
            measured_against_file_id=source_file_id,
            source_system=source_system,
            offset_ms=round(source_downbeat_ms - canonical_downbeat_ms, 3),
            offset_method=METHOD_DOWNBEAT_ANCHOR,
            residual_ms=None,
            confidence=0.6,
        )

    # 4. declared_priming -- codec encoder delay over the rendition's sample rate.
    if encoder_delay_samples is not None and sample_rate_hz:
        return RenditionTimeOffset(
            audio_file_id=canonical_file_id,
            measured_against_file_id=source_file_id,
            source_system=source_system,
            offset_ms=round(encoder_delay_samples / sample_rate_hz * 1000.0, 3),
            offset_method=METHOD_DECLARED_PRIMING,
            residual_ms=None,
            confidence=0.4,
        )

    return None


def pcm_cross_correlation(
    canonical_path: str,
    source_path: str,
    *,
    sample_rate_hz: int = 22_050,
    max_lag_ms: float = 250.0,
) -> tuple[float, float] | None:
    """Decode both renditions and correlate onset-strength envelopes for the lag.

    Returns ``(offset_ms, residual_ms)`` where ``offset_ms`` is the lag of
    ``source`` relative to ``canonical`` (so ``canonical = measured - offset``).
    Requires ``librosa``/``numpy``; returns ``None`` if they are not installed,
    keeping the rest of the module dependency-free.
    """
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None

    y_c, _ = librosa.load(canonical_path, sr=sample_rate_hz, mono=True)
    y_s, _ = librosa.load(source_path, sr=sample_rate_hz, mono=True)
    env_c = librosa.onset.onset_strength(y=y_c, sr=sample_rate_hz)
    env_s = librosa.onset.onset_strength(y=y_s, sr=sample_rate_hz)

    hop_s = 512 / sample_rate_hz  # librosa onset_strength default hop
    max_lag_frames = int((max_lag_ms / 1000.0) / hop_s)

    env_c = (env_c - env_c.mean()) / (env_c.std() + 1e-9)
    env_s = (env_s - env_s.mean()) / (env_s.std() + 1e-9)
    corr = np.correlate(env_s, env_c, mode="full")
    center = len(env_c) - 1
    lo, hi = center - max_lag_frames, center + max_lag_frames + 1
    window = corr[max(0, lo):hi]
    peak = int(np.argmax(window)) + max(0, lo)
    lag_frames = peak - center

    offset_ms = lag_frames * hop_s * 1000.0
    peak_val = float(corr[peak])
    runner_up = float(np.partition(window, -2)[-2]) if window.size > 1 else 0.0
    residual_ms = abs(peak_val - runner_up) and hop_s * 1000.0 / max(peak_val, 1e-9)
    return round(offset_ms, 3), round(residual_ms, 3)


def _grid_confidence(align: GridAlignment, eps_ms: float) -> float:
    """Map vote agreement and residual tightness onto a [0, 1] confidence."""
    tightness = 1.0 / (1.0 + (align.residual_ms / eps_ms if eps_ms else 0.0))
    return max(0.0, min(1.0, align.agreement * tightness))


def _dedupe(values: Sequence[float]) -> list[float]:
    """Drop exact duplicates (the human cue quadruple-insert) while staying float."""
    seen: set[float] = set()
    out: list[float] = []
    for v in values:
        f = float(v)
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out
