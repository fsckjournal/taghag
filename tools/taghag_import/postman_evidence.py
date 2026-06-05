from __future__ import annotations

import json
from pathlib import Path


MARKER = "[Tag Evidence JSON]"


def parse_postman_evidence(log_path: str | Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    path = Path(log_path).expanduser().resolve()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if MARKER not in raw_line:
            continue
        _, payload = raw_line.split(MARKER, 1)
        payload = payload.strip()
        if not payload:
            continue
        entries.append(json.loads(payload))

    return entries
