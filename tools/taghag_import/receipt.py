from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


SECRET_KEYS = ("apikey", "authorization", "bearer")


def receipt_path_for_run(receipt_dir: str | Path, run_id: str) -> Path:
    return Path(receipt_dir).expanduser().resolve() / run_id / "receipt.jsonl"


def ensure_no_secrets(record: object) -> None:
    encoded = json.dumps(record, sort_keys=True).lower()
    if any(marker in encoded for marker in SECRET_KEYS):
        raise ValueError("receipt record appears to contain a secret")


def event(event_type: str, **payload: object) -> dict[str, object]:
    return {"event_type": event_type, **payload}


def write_receipt(path: str | Path, records: Iterable[dict[str, object]]) -> None:
    receipt_path = Path(path).expanduser().resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    with receipt_path.open("w", encoding="utf-8") as handle:
        for record in records:
            ensure_no_secrets(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def append_receipt(path: str | Path, records: Iterable[dict[str, object]]) -> None:
    receipt_path = Path(path).expanduser().resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    with receipt_path.open("a", encoding="utf-8") as handle:
        for record in records:
            ensure_no_secrets(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_receipt(path: str | Path) -> list[dict[str, object]]:
    receipt_path = Path(path).expanduser().resolve()
    with receipt_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
