from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taghag_import.config import read_database_config

from cuecifer.db import dict_cursor, open_database
from cuecifer.sonic_discovery import VECTOR_SCHEMA, _parse_vector_literal


def _vector_mean(vectors: list[list[float]]) -> list[float]:
    dimensions = len(vectors[0])
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimensions)]


def _subtract(a: list[float], b: list[float]) -> list[float]:
    return [x - y for x, y in zip(a, b)]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[index] * vector[index] for index in range(len(vector))) for row in matrix]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _normalize(vector: list[float]) -> list[float]:
    magnitude = _norm(vector)
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _power_iteration(matrix: list[list[float]], *, iterations: int = 100) -> tuple[list[float], float]:
    if not matrix:
        return [], 0.0
    vector = [1.0] + [0.0] * (len(matrix) - 1)
    vector = _normalize(vector)
    for _ in range(iterations):
        next_vector = _mat_vec(matrix, vector)
        magnitude = _norm(next_vector)
        if magnitude == 0:
            return vector, 0.0
        next_vector = [value / magnitude for value in next_vector]
        if max(abs(a - b) for a, b in zip(next_vector, vector)) < 1e-10:
            vector = next_vector
            break
        vector = next_vector
    eigenvalue = _dot(vector, _mat_vec(matrix, vector))
    return vector, eigenvalue


def _deflate(matrix: list[list[float]], eigenvector: list[float], eigenvalue: float) -> list[list[float]]:
    return [
        [
            matrix[row][col] - eigenvalue * eigenvector[row] * eigenvector[col]
            for col in range(len(matrix[row]))
        ]
        for row in range(len(matrix))
    ]


def _project_2d(vectors: list[list[float]]) -> list[tuple[float, float]]:
    if len(vectors) == 1:
        return [(0.0, 0.0)]

    mean = _vector_mean(vectors)
    centered = [_subtract(vector, mean) for vector in vectors]
    dimension = len(centered[0])
    covariance = [
        [
            sum(sample[row] * sample[col] for sample in centered) / max(len(centered) - 1, 1)
            for col in range(dimension)
        ]
        for row in range(dimension)
    ]

    first_vector, first_value = _power_iteration(covariance)
    if not first_vector or first_value == 0:
        return [(0.0, 0.0) for _ in vectors]

    deflated = _deflate(covariance, first_vector, first_value)
    second_vector, second_value = _power_iteration(deflated)
    if not second_vector or second_value == 0:
        return [(sum(sample[index] * first_vector[index] for index in range(dimension)), 0.0) for sample in centered]

    return [
        (
            sum(sample[index] * first_vector[index] for index in range(dimension)),
            sum(sample[index] * second_vector[index] for index in range(dimension)),
        )
        for sample in centered
    ]


def _load_rows() -> list[dict[str, object]]:
    config = read_database_config()
    owner_user_id = config.owner_user_id
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    sql = """
        select
            af.path,
            te.embedding::text as embedding_text,
            te.producer_vibes_json,
            dt.artist,
            dt.title
        from public.track_embedding te
        join public.audio_file af
          on af.id = te.audio_file_id
         and af.owner_user_id = te.owner_user_id
        left join public.dj_tag dt
          on dt.audio_file_id = te.audio_file_id
         and dt.owner_user_id = te.owner_user_id
        where te.owner_user_id = %s
          and te.vector_schema = %s
        order by af.path
    """
    with open_database(config) as conn:
        with dict_cursor(conn) as cur:
            cur.execute(sql, (owner_user_id, VECTOR_SCHEMA))
            return list(cur.fetchall())


def generate_map(output_dir: str | Path) -> tuple[Path, Path]:
    rows = _load_rows()
    if not rows:
        raise RuntimeError("No tracks found in track_embedding for the configured owner")

    vectors = [_parse_vector_literal(row.get("embedding_text")) for row in rows]
    if any(not vector for vector in vectors):
        raise RuntimeError("One or more track_embedding rows could not be parsed as vectors")

    projection = _project_2d(vectors)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_out = output_dir / "library_map.json"
    csv_out = output_dir / "library_map.csv"

    records = []
    for row, (x, y) in zip(rows, projection, strict=True):
        vibes = row.get("producer_vibes_json") or []
        if isinstance(vibes, str):
            try:
                vibes = json.loads(vibes)
            except json.JSONDecodeError:
                vibes = []
        vibe_text = ", ".join(vibes) if isinstance(vibes, list) and vibes else "Uncategorized"
        path_text = str(row["path"])
        title_text = row.get("title") or Path(path_text).name
        artist_text = row.get("artist") or (Path(path_text).name.split(" - ")[0] if " - " in Path(path_text).name else "Unknown")
        records.append(
            {
                "path": path_text,
                "artist": artist_text,
                "title": title_text,
                "vibe": vibe_text,
                "x": x,
                "y": y,
            }
        )

    json_out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "artist", "title", "vibe", "x", "y"])
        writer.writeheader()
        writer.writerows(records)

    return json_out, csv_out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a simple 2D map from Cuecifer vectors")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/cuecifer_map"), help="Output directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    json_out, csv_out = generate_map(args.out_dir)
    print(f"Successfully generated library map:\n- {json_out}\n- {csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
