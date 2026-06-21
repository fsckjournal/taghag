"""Re-zeroing routine proven on the real human<->mixonset pair, not a synthetic.

The cue arrays below are captured verbatim from the live taghag database
(2026-06-21): the ``human`` and ``mixonset`` grids on the same master FLAC.
Human cues are deduped of their quadruple-insert by ``grid_offset``. The probe
documented a ~17 ms human<->mixonset offset; on real data the offset is a stable
small *positive* value per track (+12..+18 ms), confirming both the sign
(mixonset lands after human => offset = mixonset - human > 0) and the model
(one constant per (canonical, source) pair).
"""

from __future__ import annotations

from taghag_import.time_base import (
    METHOD_CROSS_CORRELATION,
    METHOD_DECLARED_PRIMING,
    METHOD_IDENTITY,
    grid_offset,
    reconcile_offset,
)

# --- Real captured grids (audio_file_id -> {human, mixonset}) ----------------
# 3e08a729 is the real-data twin of the probe's ~17 ms finding.
HUMAN_3E08 = [4504, 20504, 132505, 196506, 276507, 340508, 372508, 404508]
MIX_3E08 = [
    0, 4024, 20024, 52024, 59539, 67539, 68539, 116539, 132539, 148539, 164539,
    188524, 196524, 204524, 212524, 220524, 228524, 236524, 244520, 252520,
    260520, 268520, 276522, 340540, 356540, 372527, 396527, 404527, 436541,
    452541, 460541, 468541, 476541,
]

# Two clean low-residual confirmations on other tracks.
HUMAN_9D73 = [35, 123712, 154631, 293767, 324686, 340146, 355605, 371065]
MIX_9D73 = [
    0, 6808, 14538, 22269, 29999, 45459, 60919, 84109, 122758, 138218, 153678,
    161408, 169138, 176868, 184597, 192327, 200058, 238706, 270589, 278319,
    293779, 309239, 324699, 340156, 355617, 371076, 386536, 394747, 425667,
    433397, 464317, 479777, 480741, 496201, 519392, 542581, 550311, 558041, 565771,
]
HUMAN_0C77 = [265, 91781, 122286, 168044, 198549, 213802, 259559, 274812]
MIX_0C77 = [
    0, 271, 30779, 46032, 68917, 76544, 91798, 99425, 107052, 114679, 122300,
    129927, 145180, 152803, 160430, 168057, 175684, 183308, 190935, 198562,
    213815, 229069, 259569, 274824, 305332, 312959, 335833, 337736, 383498, 391124,
]


def test_real_pair_recovers_documented_positive_offset() -> None:
    """The 3e08a729 pair reproduces the probe's ~17 ms, with the right sign."""
    align = grid_offset(HUMAN_3E08, MIX_3E08)
    assert align is not None
    # Mixonset lands after human: offset is positive and ~17-18 ms.
    assert 15.0 <= align.offset_ms <= 20.0
    # Tight cluster -- the corresponding cues agree to within a couple ms.
    assert align.residual_ms <= 3.0
    assert align.votes >= 3


def test_real_pair_clean_confirmations() -> None:
    """Two more real tracks land in the +10..+18 ms band with tight residual."""
    for human, mix in ((HUMAN_9D73, MIX_9D73), (HUMAN_0C77, MIX_0C77)):
        align = grid_offset(human, mix)
        assert align is not None
        assert 10.0 <= align.offset_ms <= 18.0
        assert align.residual_ms <= 3.0


def test_reconcile_real_pair_emits_cross_correlation_offset() -> None:
    off = reconcile_offset(
        canonical_file_id="canon-flac",
        source_file_id="mixonset-rendition",
        source_system="mixonset",
        canonical_cues_ms=HUMAN_3E08,
        source_cues_ms=MIX_3E08,
    )
    assert off is not None
    assert off.offset_method == METHOD_CROSS_CORRELATION
    assert 15.0 <= off.offset_ms <= 20.0
    assert off.confidence > 0.0
    # canonical = measured - offset: re-zeroing a mixonset cue subtracts ~17 ms.
    row = off.to_row("owner-1")
    assert row["audio_file_id"] == "canon-flac"
    assert row["measured_against_file_id"] == "mixonset-rendition"
    assert row["offset_ms"] == off.offset_ms


# --- Synthetic algorithm guards (separate from the real-pair proof) ----------

def test_identity_when_source_is_canonical() -> None:
    off = reconcile_offset(
        canonical_file_id="flac-1",
        source_file_id="flac-1",
        source_system="human",
    )
    assert off is not None
    assert off.offset_method == METHOD_IDENTITY
    assert off.offset_ms == 0.0
    assert off.confidence == 1.0


def test_vote_rejects_non_corresponding_cues() -> None:
    """A shared +25 ms grid plus pure-noise cues still recovers +25."""
    canonical = [1000, 2000, 3000, 4000, 5000]
    source = [1025, 2025, 3025, 4025, 5025, 137, 88123, 412009]  # 3 noise cues
    align = grid_offset(canonical, source)
    assert align is not None
    assert abs(align.offset_ms - 25.0) < 1.0
    assert align.residual_ms < 1.0


def test_dedupes_quadruple_inserted_human_cues() -> None:
    canonical = [100, 100, 100, 100, 2000, 2000, 2000, 2000]
    source = [110, 2010]
    align = grid_offset(canonical, source)
    assert align is not None
    assert abs(align.offset_ms - 10.0) < 1.0


def test_same_file_but_unvotable_grids_returns_none_not_identity() -> None:
    """A lagged analyzer on the same FLAC whose grid can't vote must NOT be
    fabricated as identity offset 0 -- it returns None (stays offset_missing)."""
    off = reconcile_offset(
        canonical_file_id="flac-1",
        source_file_id="flac-1",  # same file id
        source_system="mixonset",
        canonical_cues_ms=[1694.0],  # one lonely human cue, nothing to vote
        source_cues_ms=[0.0, 730.0, 8349.0, 15968.0],
    )
    assert off is None


def test_declared_priming_when_no_grid_overlap() -> None:
    off = reconcile_offset(
        canonical_file_id="flac-1",
        source_file_id="aac-render",
        source_system="apple",
        encoder_delay_samples=2112,
        sample_rate_hz=44_100,
    )
    assert off is not None
    assert off.offset_method == METHOD_DECLARED_PRIMING
    assert abs(off.offset_ms - 2112 / 44_100 * 1000) < 0.01


def test_returns_none_when_no_method_applies() -> None:
    assert reconcile_offset(
        canonical_file_id="flac-1",
        source_file_id="other",
        source_system="beatport",
    ) is None


def test_empty_grids_return_none() -> None:
    assert grid_offset([], [1, 2, 3]) is None
    assert grid_offset([1, 2, 3], []) is None
    assert grid_offset([1000], [999999]) is None  # outside window
