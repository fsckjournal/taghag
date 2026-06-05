from __future__ import annotations

import json
from importlib import resources


def _load_rules() -> dict[str, object]:
    with resources.files("taghag_import").joinpath("genre_rules.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_genre(raw_genre: str | None) -> dict[str, object]:
    rules = _load_rules()
    normalized = (raw_genre or "").strip().lower()

    for rule in rules.get("rules", []):
        aliases = [alias.lower() for alias in rule.get("aliases", [])]
        if normalized and normalized in aliases:
            return {
                "normalized_genre": rule["name"],
                "genre_family": rule.get("family"),
                "confidence": 1.0,
            }

    return {
        "normalized_genre": raw_genre.strip() if raw_genre else "Unknown",
        "genre_family": "Unclassified",
        "confidence": 0.2 if raw_genre else 0.0,
    }
