from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .postman_evidence import MARKER, parse_tag_evidence


RESOLVE_ITEMS = (
    "Spotify/Lookup - Release Identity by ISRC",
    "TIDAL/Search - by ISRC",
    "Beatport/Search - by ISRC",
    "Qobuz/Search - by ISRC",
)

SAFE_ENV_VARS = {
    "spotify_accounts_url": "https://accounts.spotify.com",
    "spotify_token_url": "https://accounts.spotify.com/api/token",
    "spotify_api_base_url": "https://api.spotify.com/v1",
    "baseUrl_spotify": "https://api.spotify.com/v1",
    "spotify_market": "US",
    "market": "US",
    "limit": "20",
    "tidal_refresh_url": "https://auth.tidal.com/v1/oauth2/token",
    "baseUrl_tidal": "https://openapi.tidal.com",
    "baseUrl_tidal_openapi": "https://openapi.tidal.com",
    "tidal_country_code": "US",
    "countryCode": "US",
    "tidal_include": "albums,artists",
    "beatport_token_url": "https://api.beatport.com/v4/auth/o/token/",
    "beatport_redirect_uri": "https://www.beatport.com/api/auth/callback/beatport",
    "qobuz_app_id": "712109809",
}

DEFAULT_SECRET_KEYS = {
    "spotify_client_id",
    "spotify_client_secret",
    "tidal_client_id",
    "tidal_client_secret",
    "tidal_refresh_token",
    "beatport_access_token",
    "beatport_refresh_token",
    "qobuz_user_auth_token",
}


@dataclass(frozen=True)
class ProviderRunnerConfig:
    postman_bin: str
    collection_path: Path
    environment_path: Path
    output_dir: Path
    timeout_s: int = 90
    extra_env_vars: Mapping[str, str] = field(default_factory=dict)
    secret_keys: set[str] = field(default_factory=lambda: set(DEFAULT_SECRET_KEYS))
    verify_binary: bool = True
    prepare_only: bool = False


@dataclass(frozen=True)
class ProviderBatchResult:
    output_dir: Path
    evidence_log: Path
    summary_path: Path
    summary: dict[str, object]


def normalize_isrc(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", normalized):
        raise ValueError(f"invalid ISRC: {value}")
    return normalized


def _resolved_collection_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir():
        definition = candidate / ".resources" / "definition.yaml"
        if definition.is_file():
            return definition
    return candidate


def verify_provider_config(config: ProviderRunnerConfig) -> None:
    if config.verify_binary and shutil.which(config.postman_bin) is None:
        raise FileNotFoundError(f"Postman binary not found: {config.postman_bin}")

    collection = _resolved_collection_path(config.collection_path)
    if not collection.exists():
        raise FileNotFoundError(f"Postman collection not found: {collection}")
    if not config.environment_path.expanduser().resolve().is_file():
        raise FileNotFoundError(
            f"Postman environment not found: {config.environment_path.expanduser().resolve()}"
        )
    if config.timeout_s <= 0:
        raise ValueError("provider timeout must be positive")


def build_postman_command(
    isrc: str,
    config: ProviderRunnerConfig,
) -> list[str]:
    normalized = normalize_isrc(isrc)
    command = [
        config.postman_bin,
        "collection",
        "run",
        str(_resolved_collection_path(config.collection_path)),
        "-e",
        str(config.environment_path.expanduser().resolve()),
    ]
    env_vars = {**SAFE_ENV_VARS, **dict(config.extra_env_vars)}
    for key, value in env_vars.items():
        if value:
            command.extend(["--env-var", f"{key}={value}"])
    command.extend(["--env-var", f"lookup_isrc={normalized}"])
    for item in RESOLVE_ITEMS:
        command.extend(["-i", item])
    return command


def display_command(command: list[str], secret_keys: set[str]) -> str:
    displayed: list[str] = []
    for index, part in enumerate(command):
        value = part
        if index > 0 and command[index - 1] == "--env-var" and "=" in part:
            key, raw_value = part.split("=", 1)
            if key in secret_keys and raw_value:
                value = f"{key}=<redacted>"
        displayed.append(shlex.quote(value))
    return " ".join(displayed)


def _error_evidence(isrc: str, error: str) -> dict[str, object]:
    return {
        "schema": "taghag.provider_evidence.error.v1",
        "provider": "postman",
        "status": "error",
        "lookup_isrc": isrc,
        "candidates": [],
        "error": error,
    }


def _normalized_marker_lines(stdout: str) -> tuple[list[str], int, int]:
    lines: list[str] = []
    parsed = parse_tag_evidence(stdout)
    malformed_count = 0
    for evidence in parsed:
        if evidence.get("status") == "malformed" and evidence.get("raw_line"):
            malformed_count += 1
            lines.append(str(evidence["raw_line"]).strip())
        else:
            lines.append(f"{MARKER} {json.dumps(evidence, sort_keys=True)}")
    return lines, len(parsed), malformed_count


def run_provider_batch(
    isrcs: Sequence[str],
    config: ProviderRunnerConfig,
) -> ProviderBatchResult:
    verify_provider_config(config)
    normalized_isrcs = list(dict.fromkeys(normalize_isrc(value) for value in isrcs))
    if not normalized_isrcs:
        raise ValueError("at least one ISRC is required")

    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_log = output_dir / "provider_evidence.log"
    summary_path = output_dir / "summary.json"
    results: list[dict[str, object]] = []

    with evidence_log.open("w", encoding="utf-8") as handle:
        for isrc in normalized_isrcs:
            command = build_postman_command(isrc, config)
            displayed = display_command(command, config.secret_keys)
            if config.prepare_only:
                results.append(
                    {
                        "isrc": isrc,
                        "status": "prepared",
                        "returncode": None,
                        "marker_count": 0,
                        "command": displayed,
                        "error": "",
                    }
                )
                continue

            returncode: int | None = None
            error = ""
            stdout = ""
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=config.timeout_s,
                )
                returncode = completed.returncode
                stdout = completed.stdout or ""
                error = (completed.stderr or "").strip()
            except subprocess.TimeoutExpired:
                error = f"Postman timed out after {config.timeout_s}s"
            except FileNotFoundError as exc:
                error = str(exc)

            marker_lines, marker_count, malformed_count = _normalized_marker_lines(stdout)
            for line in marker_lines:
                handle.write(line.rstrip() + "\n")

            failed = returncode != 0 or marker_count == 0 or malformed_count > 0
            if failed:
                if not error:
                    error = (
                        f"Postman exited with status {returncode}"
                        if returncode is not None
                        else "Postman failed before returning a status"
                    )
                failure = _error_evidence(isrc, error)
                handle.write(f"{MARKER} {json.dumps(failure, sort_keys=True)}\n")

            results.append(
                {
                    "isrc": isrc,
                    "status": "failed" if failed else "succeeded",
                    "returncode": returncode,
                    "marker_count": marker_count,
                    "command": displayed,
                    "error": error if failed else "",
                }
            )

    summary: dict[str, object] = {
        "total": len(results),
        "succeeded": sum(result["status"] == "succeeded" for result in results),
        "failed": sum(result["status"] == "failed" for result in results),
        "prepared": sum(result["status"] == "prepared" for result in results),
        "evidence_log": str(evidence_log),
        "results": results,
    }
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return ProviderBatchResult(
        output_dir=output_dir,
        evidence_log=evidence_log,
        summary_path=summary_path,
        summary=summary,
    )
