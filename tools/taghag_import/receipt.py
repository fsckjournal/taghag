from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_receipt(path: str | Path, records: Iterable[dict[str, object]]) -> None:
    receipt_path = Path(path).expanduser().resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    with receipt_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_receipt(path: str | Path) -> list[dict[str, object]]:
    receipt_path = Path(path).expanduser().resolve()
    with receipt_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
