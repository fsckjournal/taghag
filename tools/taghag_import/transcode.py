from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import concurrent.futures
import os
import sys
import threading
import json
import time
from datetime import UTC, datetime


@dataclass(frozen=True)
class TranscodeJob:
    source: Path
    destination: Path
    status: str
    pcm_sha256: str | None = None
    metadata_tags: dict[str, object] | None = None


def load_failure_ledger(ledger_path: Path) -> set[Path]:
    failures: set[Path] = set()
    if not ledger_path.is_file():
        return failures
    with ledger_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if "source" in payload:
                    failures.add(Path(payload["source"]).expanduser().resolve())
            except json.JSONDecodeError:
                # Ignore malformed ledger lines and continue parsing the rest.
                continue
    return failures


def append_failure(ledger_path: Path, source: Path, error: str) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "source": str(source),
            "error": error,
        }
        handle.write(json.dumps(payload) + "\n")


def build_transcode_plan(
    source_root: str | Path,
    output_root: str | Path,
    failure_ledger_path: Path | None = None,
) -> list[TranscodeJob]:
    source = Path(source_root).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    if source == output or source in output.parents:
        raise ValueError("output directory must not be the source directory or one of its parents")

    failures = load_failure_ledger(failure_ledger_path) if failure_ledger_path else set()

    jobs: list[TranscodeJob] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.casefold() != ".flac":
            continue
        resolved_source = path.resolve()
        destination = (output / path.relative_to(source)).with_suffix(".mp3")
        
        if resolved_source in failures:
            status = "failed-skipped"
        elif destination.is_file() and destination.stat().st_size > 0:
            status = "existing"
        else:
            status = "ready"
            
        # We don't have pcm_sha256 computed here directly since we aren't decoding.
        # But for 'stage' driven workflows, stage.py creates TranscodeJob directly.
        jobs.append(TranscodeJob(source=resolved_source, destination=destination.resolve(), status=status))
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


def _execute_single_job(job: TranscodeJob) -> tuple[TranscodeJob, bool, str]:
    if job.status != "ready":
        return job, True, ""
    job.destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        _ffmpeg_command(job),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not job.destination.is_file() or job.destination.stat().st_size == 0:
        job.destination.unlink(missing_ok=True)
        return job, False, completed.stderr.strip()
        
    if job.pcm_sha256 or job.metadata_tags:
        try:
            from .tags import apply_mp3_tag_updates
            updates = dict(job.metadata_tags or {})
            if job.pcm_sha256:
                updates["pcm_hash"] = job.pcm_sha256
            if updates:
                apply_mp3_tag_updates(job.destination, updates, execute=True)
        except Exception as e:
            job.destination.unlink(missing_ok=True)
            return job, False, f"Failed to inject tags: {e}"
            
    return job, True, ""


class ProgressTracker:
    def __init__(self, total: int, state_file_path: Path | None, verbose: bool):
        self.total = total
        self.done = 0
        self.failed = 0
        self.state_file_path = state_file_path
        self.verbose = verbose
        self.lock = threading.Lock()
        self.is_tty = sys.stdout.isatty()
        self.start_time = time.time()
        self._last_print = 0.0

    def update(self, success: bool, job: TranscodeJob, error_msg: str) -> None:
        with self.lock:
            self.done += 1
            if not success:
                self.failed += 1

            now = time.time()
            # Update state file atomically
            if self.state_file_path:
                tmp_path = self.state_file_path.with_suffix(".json.tmp")
                try:
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path.write_text(
                        json.dumps({
                            "ts": datetime.now(UTC).isoformat(),
                            "done": self.done,
                            "total": self.total,
                            "failed": self.failed,
                            "rate": self.done / max(1.0, now - self.start_time)
                        }),
                        encoding="utf-8"
                    )
                    os.replace(tmp_path, self.state_file_path)
                except OSError:
                    pass  # Best effort

            # Print progress
            if self.verbose:
                # Print every 1s or on completion
                if now - self._last_print > 1.0 or self.done == self.total:
                    self._last_print = now
                    if self.is_tty:
                        sys.stdout.write(f"\r[Transcode] {self.done}/{self.total} done ({self.failed} failed)... ")
                        sys.stdout.flush()
                        if self.done == self.total:
                            sys.stdout.write("\n")
                    else:
                        print(json.dumps({
                            "ts": datetime.now(UTC).isoformat(),
                            "done": self.done,
                            "total": self.total,
                            "failed": self.failed
                        }))

            if not success and self.verbose and self.is_tty:
                # Clear line and print error, then repaint next time
                sys.stdout.write(f"\r\033[Kfailed: {job.source}: {error_msg}\n")
                self._last_print = 0.0  # Force repaint


def execute_transcode_plan(
    jobs: list[TranscodeJob],
    *,
    dry_run: bool = False,
    verbose: bool = False,
    workers: int | None = None,
    state_file_path: Path | None = None,
    failure_ledger_path: Path | None = None,
) -> dict[str, int]:
    result = {
        "planned": sum(job.status == "ready" for job in jobs),
        "transcoded": 0,
        "existing": sum(job.status == "existing" for job in jobs),
        "failed": 0,
        "failed-skipped": sum(job.status == "failed-skipped" for job in jobs),
    }
    if dry_run:
        if verbose:
            for job in jobs:
                label = "existing" if job.status == "existing" else ("skipped" if job.status == "failed-skipped" else "planned")
                print(f"{label}: {job.source} -> {job.destination}")
        return result

    ready_jobs = [job for job in jobs if job.status == "ready"]
    if verbose:
        for job in jobs:
            if job.status == "existing":
                print(f"existing: {job.destination}")
            elif job.status == "failed-skipped":
                print(f"failed-skipped: {job.source}")

    if not ready_jobs:
        return result

    if workers is None:
        # Cap workers at 8 by default to avoid I/O thrashing on external drives
        # and prevent scheduling onto E-cores blindly.
        workers = min(os.cpu_count() or 4, 8)
    workers = max(1, workers)

    tracker = ProgressTracker(len(ready_jobs), state_file_path, verbose)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_execute_single_job, job): job for job in ready_jobs}

        for future in concurrent.futures.as_completed(futures):
            job, success, error_msg = future.result()
            
            if success:
                result["transcoded"] += 1
            else:
                result["failed"] += 1
                if failure_ledger_path:
                    # Write immediately so the ledger is updated incrementally
                    append_failure(failure_ledger_path, job.source, error_msg)
            
            tracker.update(success, job, error_msg)

    return result
