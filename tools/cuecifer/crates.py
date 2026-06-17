from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taghag_import.config import read_database_config

from cuecifer.sonic_discovery import SonicDiscoveryIndex


def generate_neighborhood_crate(seed_path: str, *, limit: int = 30, out_dir: Path = Path(".")) -> Path:
    index = SonicDiscoveryIndex(config=read_database_config())
    neighbours = index.similar_tracks(seed_path, limit=limit)
    if not neighbours:
        raise RuntimeError(f"No neighboring tracks found for {seed_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    seed_name = Path(seed_path).stem
    output_path = out_dir / f"[TS_Discovery] {seed_name}.m3u8"

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("#EXTM3U\n")
        handle.write(f"# Seed: {seed_path}\n")
        for row in neighbours:
            vibe_text = ", ".join(row.producer_vibes) if row.producer_vibes else "uncategorized"
            handle.write(f"# Dist: {row.distance:.4f} | Vibes: {vibe_text}\n")
            handle.write(f"{row.path}\n")

    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a neighborhood crate playlist from Cuecifer vectors")
    parser.add_argument("--seed", required=True, help="Absolute path to the seed track")
    parser.add_argument("--limit", type=int, default=30, help="Number of tracks to include")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory for the playlist")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = generate_neighborhood_crate(args.seed, limit=args.limit, out_dir=args.out_dir)
    print(f"Generated crate playlist: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
