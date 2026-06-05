from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

DEFAULT_CANONICAL_GENRES = frozenset(
    {
        "140 / Deep Dubstep / Grime",
        "Afro House",
        "African",
        "Alternative / Indie",
        "Amapiano",
        "Ambient / Experimental",
        "Bass / Club",
        "Bass House",
        "Blues",
        "Brazilian Funk",
        "Breaks / Breakbeat / UK Bass",
        "Caribbean",
        "Classical",
        "Country",
        "Dance / Pop",
        "Deep House",
        "Disco",
        "DJ Tools",
        "Downtempo",
        "Drum & Bass",
        "Dubstep",
        "Electro (Classic / Detroit / Modern)",
        "Electronica",
        "Funky House",
        "Hard Dance / Hardcore / Neo Rave",
        "Hard Techno",
        "Hip-Hop",
        "Holiday",
        "House",
        "Indie Dance",
        "Jackin House",
        "Jazz",
        "Latin",
        "Mainstage",
        "Melodic House & Techno",
        "Minimal / Deep Tech",
        "Nu Disco / Disco",
        "Organic House",
        "Other",
        "Pop",
        "Progressive House",
        "Psy-Trance",
        "R&B",
        "Rock",
        "Soul",
        "Soundtrack",
        "Tech House",
        "Techno",
        "Techno (Peak Time / Driving)",
        "Techno (Raw / Deep / Hypnotic)",
        "Trance",
        "Trance (Main Floor)",
        "Trance (Raw / Deep / Hypnotic)",
        "Trap / Future Bass",
        "UK Garage / Bassline",
        "World",
    }
)

DEFAULT_STYLE_PARENT_MAP = {
    "2-Step": "UK Garage / Bassline",
    "3Step": "Afro House",
    "Acapellas": "DJ Tools",
    "Acid": "Techno (Raw / Deep / Hypnotic)",
    "Afro / Latin": "Afro House",
    "Afro Melodic": "Afro House",
    "Afrobeats": "African",
    "Bassline": "UK Garage / Bassline",
    "Battle Tools": "DJ Tools",
    "Big Room": "Mainstage",
    "Breakbeat": "Breaks / Breakbeat / UK Bass",
    "Broken": "Breaks / Breakbeat / UK Bass",
    "Dancehall": "Caribbean",
    "Dark & Forest": "Drum & Bass",
    "Dark Disco": "Indie Dance",
    "Deep": "Deep House",
    "Deep / Hypnotic": "Techno (Raw / Deep / Hypnotic)",
    "Deep House": "Deep House",
    "Deep Tech": "Minimal / Deep Tech",
    "Deep Trance": "Trance (Raw / Deep / Hypnotic)",
    "Disco": "Nu Disco / Disco",
    "Driving": "Techno (Peak Time / Driving)",
    "Dub": "Dubstep",
    "EBM": "Indie Dance",
    "Electro House": "Mainstage",
    "Electronica": "Electronica",
    "Frenchcore": "Hard Dance / Hardcore / Neo Rave",
    "Full-On": "Psy-Trance",
    "Funk": "Soul",
    "Future Bass": "Trap / Future Bass",
    "Future House": "House",
    "Future Rave": "Mainstage",
    "Glitch Hop": "Bass / Club",
    "Global": "World",
    "Global Club": "Bass / Club",
    "Goa Trance": "Psy-Trance",
    "Grime": "140 / Deep Dubstep / Grime",
    "Halftime": "Drum & Bass",
    "Hard House": "Hard Dance / Hardcore / Neo Rave",
    "Hard Trance": "Trance (Main Floor)",
    "Hardstyle": "Hard Dance / Hardcore / Neo Rave",
    "House": "House",
    "Hypnotic Trance": "Trance (Raw / Deep / Hypnotic)",
    "Indie": "Alternative / Indie",
    "Italo": "Nu Disco / Disco",
    "Jersey Club": "Bass / Club",
    "Juke / Footwork": "Bass / Club",
    "Jump Up": "Drum & Bass",
    "Jungle": "Drum & Bass",
    "Latin Dance": "Latin",
    "Latin House": "House",
    "Liquid": "Drum & Bass",
    "Loops": "DJ Tools",
    "Melodic Dubstep": "Dubstep",
    "Melodic House": "Melodic House & Techno",
    "Melodic House & Techno": "Melodic House & Techno",
    "Melodic Techno": "Melodic House & Techno",
    "Minimal / Deep Tech": "Minimal / Deep Tech",
    "Minimal House": "Minimal / Deep Tech",
    "Neo Rave": "Hard Dance / Hardcore / Neo Rave",
    "Nu Disco / Disco": "Nu Disco / Disco",
    "Peak Time": "Techno (Peak Time / Driving)",
    "Progressive Psy": "Psy-Trance",
    "Progressive Trance": "Trance (Main Floor)",
    "Psy-Techno": "Psy-Trance",
    "Psychedelic": "Psy-Trance",
    "Raw": "Techno (Raw / Deep / Hypnotic)",
    "Raw Trance": "Trance (Raw / Deep / Hypnotic)",
    "Reggae / Dancehall": "Caribbean",
    "Soulful": "House",
    "Speed Garage": "UK Garage / Bassline",
    "Speed House": "House",
    "Tech House": "Tech House",
    "Tech Trance": "Trance (Main Floor)",
    "Techno": "Techno",
    "Trap": "Trap / Future Bass",
    "UK Bass": "Breaks / Breakbeat / UK Bass",
    "UK Funky": "UK Garage / Bassline",
    "UK Garage": "UK Garage / Bassline",
    "Uplifting Trance": "Trance (Main Floor)",
    "Vocal Trance": "Trance (Main Floor)",
}

_DEFAULT_NORMALIZER: "GenreNormalizer | None" = None


def _load_packaged_rules() -> dict[str, Any]:
    with resources.files("taghag_import").joinpath("genre_rules.json").open(
        "r", encoding="utf-8"
    ) as handle:
        return json.load(handle)


class GenreNormalizer:
    GENRE_TAG_KEYS = ["GENRE_PREFERRED", "SUBGENRE", "GENRE", "GENRE_FULL"]
    STYLE_TAG_KEYS = ["STYLE"]

    PROTECTED_COMPOUND = {
        "140 / deep dubstep / grime",
        "ambient / experimental",
        "bass / club",
        "breaks / breakbeat / uk bass",
        "dance / pop",
        "drum & bass",
        "electro (classic / detroit / modern)",
        "hard dance / hardcore / neo rave",
        "melodic house & techno",
        "minimal / deep tech",
        "nu disco / disco",
        "psy-trance",
        "techno (peak time / driving)",
        "techno (raw / deep / hypnotic)",
        "trance (main floor)",
        "trance (raw / deep / hypnotic)",
        "trap / future bass",
        "uk garage / bassline",
    }

    def __init__(self, rules_path: Path | None = None):
        if rules_path is None:
            self.rules = _load_packaged_rules()
        else:
            self.rules = self._load_rules(rules_path)
        self.canonical_genres = set(DEFAULT_CANONICAL_GENRES)
        self.canonical_genres.update(self.rules.get("canonical_genres", []))
        self.style_parent_map = dict(DEFAULT_STYLE_PARENT_MAP)
        self.style_parent_map.update(self.rules.get("style_parent_map", {}))
        self.fallback_genre = str(self.rules.get("fallback_genre") or "Other")

    @staticmethod
    def _load_rules(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "genre_map": data.get("genre_map", {}),
            "style_map": data.get("style_map", {}),
            "canonical_genres": data.get("canonical_genres", []),
            "style_parent_map": data.get("style_parent_map", {}),
            "fallback_genre": data.get("fallback_genre", "Other"),
        }

    @staticmethod
    def get_tag(tags: dict[str, Any], key: str) -> list[str]:
        if key not in tags:
            return []
        value = tags[key]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def _normalize_spacing(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())

    @classmethod
    def _lookup_key(cls, value: str) -> str:
        return cls._normalize_spacing(value).casefold()

    @classmethod
    def _lookup_mapping(cls, mapping: dict[str, str], value: str) -> str | None:
        if value in mapping:
            return mapping[value]
        wanted = cls._lookup_key(value)
        for key, mapped in mapping.items():
            if cls._lookup_key(key) == wanted:
                return mapped
        return None

    def normalize_value(self, value: str, mapping_type: str = "genre") -> str:
        mapping = self.rules.get(f"{mapping_type}_map", {})
        mapped = self._lookup_mapping(mapping, value)
        return mapped if mapped is not None else value

    def _is_canonical_genre(self, value: str | None) -> bool:
        if not value:
            return False
        wanted = self._lookup_key(value)
        return any(self._lookup_key(genre) == wanted for genre in self.canonical_genres)

    def _parent_for_style(self, value: str | None) -> str | None:
        if not value:
            return None
        style = self.normalize_value(value, "style")
        parent = self._lookup_mapping(self.style_parent_map, style)
        if parent:
            return self.normalize_value(parent, "genre")
        return None

    @classmethod
    def _is_protected(cls, value: str) -> bool:
        return cls._normalize_spacing(value).lower() in cls.PROTECTED_COMPOUND

    @staticmethod
    def _split_parenthetical(value: str) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        value = GenreNormalizer._normalize_spacing(value)
        match = re.match(r"^(.+?)\s*\((.+)\)\s*$", value)
        if not match:
            return value, None
        return match.group(1).strip(), match.group(2).strip()

    @staticmethod
    def _split_compound(value: str) -> list[str]:
        if not value:
            return []
        if GenreNormalizer._is_protected(value):
            return [GenreNormalizer._normalize_spacing(value)]

        parts: list[str] = []
        buffer: list[str] = []
        depth = 0
        index = 0
        while index < len(value):
            char = value[index]
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1

            if depth == 0:
                if value[index : index + 3] == " / ":
                    part = "".join(buffer).strip()
                    if part:
                        parts.append(part)
                    buffer = []
                    index += 3
                    continue
                if char in {",", ";", "|", "/"}:
                    part = "".join(buffer).strip()
                    if part:
                        parts.append(part)
                    buffer = []
                    index += 1
                    while index < len(value) and value[index] == " ":
                        index += 1
                    continue

            buffer.append(char)
            index += 1

        if buffer:
            part = "".join(buffer).strip()
            if part:
                parts.append(part)
        return parts

    def normalize_pair(
        self, genre: str | None, style: str | None = None
    ) -> tuple[str | None, str | None]:
        raw_genre = self._normalize_spacing(genre) if genre else None
        raw_style = self._normalize_spacing(style) if style else None

        if raw_genre and not raw_style:
            raw_genre, raw_style = self._split_parenthetical(raw_genre)

        if raw_genre:
            parts = self._split_compound(raw_genre)
            if parts:
                raw_genre = parts[0]
                if not raw_style and len(parts) >= 2:
                    raw_style = parts[1]

        if raw_style:
            style_parts = self._split_compound(raw_style)
            if style_parts:
                raw_style = style_parts[0]

        mapped_genre = self.normalize_value(raw_genre, "genre") if raw_genre else None
        mapped_style = self.normalize_value(raw_style, "style") if raw_style else None
        mapped_genre = mapped_genre or None
        mapped_style = mapped_style or None

        style_parent = self._parent_for_style(mapped_style)
        if mapped_genre and not self._is_canonical_genre(mapped_genre):
            genre_as_style = self.normalize_value(mapped_genre, "style")
            parent = self._parent_for_style(genre_as_style)
            if parent:
                mapped_genre = parent
                mapped_style = mapped_style or genre_as_style
            else:
                mapped_genre = self.fallback_genre or None
                mapped_style = None

        if not mapped_genre and style_parent:
            mapped_genre = style_parent
        elif style_parent and mapped_genre:
            generic_genres = {
                "alternative / indie",
                "dance / pop",
                "electronica",
                "house",
                "pop",
                "rock",
                "techno",
                "trance",
            }
            if self._lookup_key(mapped_genre) == self._lookup_key(self.fallback_genre):
                mapped_genre = style_parent
            elif self._lookup_key(mapped_genre) in generic_genres:
                mapped_genre = style_parent

        if mapped_genre and not self._is_canonical_genre(mapped_genre):
            mapped_genre = self.fallback_genre or None
            mapped_style = None

        if (
            mapped_style
            and mapped_genre
            and self._lookup_key(mapped_style) == self._lookup_key(mapped_genre)
        ):
            mapped_style = None

        return mapped_genre, mapped_style

    def choose_normalized(
        self, tags: dict[str, Any]
    ) -> tuple[str | None, str | None, list[str]]:
        genre_candidates: list[str] = []
        for key in self.GENRE_TAG_KEYS:
            genre_candidates.extend(self.get_tag(tags, key))

        style_candidates: list[str] = []
        for key in self.STYLE_TAG_KEYS:
            style_candidates.extend(self.get_tag(tags, key))

        present_tags = {
            key
            for key in self.GENRE_TAG_KEYS + self.STYLE_TAG_KEYS
            if self.get_tag(tags, key)
        }

        genre = genre_candidates[0] if genre_candidates else None
        style = style_candidates[0] if style_candidates else None
        normalized_genre, normalized_style = self.normalize_pair(genre, style)

        used_tags: set[str] = set()
        if genre:
            for key in self.GENRE_TAG_KEYS:
                if genre in self.get_tag(tags, key):
                    used_tags.add(key)
                    break
        if style:
            for key in self.STYLE_TAG_KEYS:
                if style in self.get_tag(tags, key):
                    used_tags.add(key)
                    break

        dropped = sorted(present_tags - used_tags)
        return normalized_genre, normalized_style, dropped


def default_genre_normalizer() -> GenreNormalizer:
    global _DEFAULT_NORMALIZER
    if _DEFAULT_NORMALIZER is None:
        _DEFAULT_NORMALIZER = GenreNormalizer()
    return _DEFAULT_NORMALIZER


def classify_genre(raw_genre: str | None) -> dict[str, object]:
    normalizer = default_genre_normalizer()
    normalized_genre, normalized_style = normalizer.normalize_pair(raw_genre)
    return {
        "normalized_genre": normalized_genre or (raw_genre.strip() if raw_genre else "Unknown"),
        "genre_family": normalized_style,
        "confidence": 1.0 if normalized_genre else (0.2 if raw_genre else 0.0),
    }
