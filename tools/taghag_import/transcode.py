from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class TranscodeJob:
    source: Path
    destination: Path
    status: str


def build_transcode_plan(source_root: str | Path, output_root: str | Path) -> list[TranscodeJob]:
    source = Path(source_root).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    if source == output or source in output.parents:
        raise ValueError("output directory must not be the source directory or one of its parents")

    jobs: list[TranscodeJob] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.casefold() != ".flac":
            continue
        destination = (output / path.relative_to(source)).with_suffix(".mp3")
        status = "existing" if destination.is_file() and destination.stat().st_size > 0 else "ready"
        jobs.append(TranscodeJob(source=path.resolve(), destination=destination.resolve(), status=status))
    return jobs


def _ffmpeg_command(job: TranscodeJob) -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(job.source),
        "-map",
        "0:a:0",
        "-map_metadata",
        "0",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-id3v2_version",
        "3",
        "-y",
        str(job.destination),
    ]


def execute_transcode_plan(
    jobs: list[TranscodeJob],
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    result = {
        "planned": sum(job.status == "ready" for job in jobs),
        "transcoded": 0,
        "existing": sum(job.status == "existing" for job in jobs),
        "failed": 0,
    }
    if dry_run:
        if verbose:
            for job in jobs:
                label = "existing" if job.status == "existing" else "planned"
                print(f"{label}: {job.source} -> {job.destination}")
        return result

    for job in jobs:
        if job.status != "ready":
            if verbose:
                print(f"existing: {job.destination}")
            continue
        job.destination.parent.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"transcode: {job.source} -> {job.destination}")
        completed = subprocess.run(
            _ffmpeg_command(job),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not job.destination.is_file() or job.destination.stat().st_size == 0:
            result["failed"] += 1
            job.destination.unlink(missing_ok=True)
            if verbose:
                print(f"failed: {job.source}: {completed.stderr.strip()}")
            continue
        result["transcoded"] += 1
    return result
