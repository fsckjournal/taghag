from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

OUT_OF_SCOPE_AUDIO_EXTENSIONS = frozenset(
    {".m4a", ".aac", ".flac", ".wav", ".aiff", ".aif", ".alac", ".ogg", ".opus", ".wma"}
)
PLAYLIST_EXTENSIONS = frozenset({".m3u", ".m3u8"})
JUNK_FILENAMES = frozenset({".DS_Store"})
JUNK_DIRS = frozenset({"__MACOSX", ".Trashes", ".Spotlight-V100", ".fseventsd"})


@dataclass(frozen=True)
class DiscoveryRecord:
    path: str
    relative_path: str
    extension: str
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def discover_audio_files(root: str | Path) -> tuple[list[DiscoveryRecord], list[DiscoveryRecord]]:
    root_path = Path(root).expanduser().resolve()
    found: list[DiscoveryRecord] = []
    skipped: list[DiscoveryRecord] = []

    for path in sorted(root_path.rglob("*")):
        if any(part in JUNK_DIRS for part in path.parts):
            continue
        relative_parts = path.relative_to(root_path).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        if not path.is_file():
            continue
        if path.name in JUNK_FILENAMES or path.name.startswith("._"):
            continue

        rel = str(path.relative_to(root_path))
        ext = path.suffix.lower()

        if ext == ".mp3":
            found.append(
                DiscoveryRecord(
                    path=str(path),
                    relative_path=rel,
                    extension=ext,
                    status="ready",
                )
            )
            continue

        if ext in PLAYLIST_EXTENSIONS:
            skipped.append(
                DiscoveryRecord(
                    path=str(path),
                    relative_path=rel,
                    extension=ext,
                    status="playlist",
                    reason="playlist",
                )
            )
            continue

        if ext in OUT_OF_SCOPE_AUDIO_EXTENSIONS:
            skipped.append(
                DiscoveryRecord(
                    path=str(path),
                    relative_path=rel,
                    extension=ext,
                    status="out_of_scope_audio",
                    reason="out_of_scope_audio",
                )
            )

    return found, skipped
