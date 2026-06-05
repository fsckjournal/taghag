from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


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
        if not path.is_file():
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

        skipped.append(
            DiscoveryRecord(
                path=str(path),
                relative_path=rel,
                extension=ext,
                status="skipped",
                reason="out_of_scope_non_mp3",
            )
        )

    return found, skipped
