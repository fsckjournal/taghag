from __future__ import annotations

from taghag_import.genre import GenreNormalizer


def test_normalize_pair_promotes_specific_style_parent() -> None:
    normalizer = GenreNormalizer()

    genre, style = normalizer.normalize_pair("House / Deep House")

    assert genre == "Deep House"
    assert style is None
