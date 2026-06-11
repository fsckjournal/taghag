from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .analysis_contract import load_analysis_sidecar
from .analysis_import import build_analysis_import_records
from .db_client import TaghagDbClient


class EssentiaAdapter:
    def __init__(self, repo_path: str | Path | None = None) -> None:
        default_path = os.environ.get("TAGHAG_ESSENTIA_REPO", "/Users/g/Projects/Essentia-to-Metadata")
        self.repo_path = Path(repo_path or default_path).expanduser().resolve()
        
        # Determine the Python executable inside the virtualenv
        venv_python = self.repo_path / "venv" / "bin" / "python"
        if venv_python.exists():
            self.python_bin = venv_python
        else:
            self.python_bin = Path("python3")

    def run_analysis(self, input_path: str | Path, sidecar_out_path: str | Path, dry_run: bool = True) -> tuple[int, str]:
        """Runs the Essentia tagger as a subprocess."""
        script_path = self.repo_path / "tag_music.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Essentia analyzer script not found at {script_path}")

        # Construct the command
        cmd = [
            str(self.python_bin),
            str(script_path),
            str(input_path),
            "--auto",
            "--model-profile", "candidate",
        ]
        
        if dry_run:
            cmd.extend(["--dry-run", "--sidecar-on-dry-run"])

        # Create target sidecar directory
        sidecar_out_path = Path(sidecar_out_path).expanduser().resolve()
        sidecar_out_path.parent.mkdir(parents=True, exist_ok=True)

        # Set environment and execute subprocess
        env = dict(os.environ)
        # Ensure we run the command inside the repo_path context
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                env=env,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Write out sidecar file manually if dry_run created it at default location
            # Note: tag_music.py writes to its default output if not overridden.
            # Let's check if the run was successful.
            return result.returncode, result.stdout + "\n" + result.stderr
        except Exception as exc:
            return -1, str(exc)

    def ingest_sidecar(self, db_client: TaghagDbClient, sidecar_path: str | Path) -> dict[str, int]:
        """Validates and uploads an essentia sidecar to the database."""
        sidecar_path = Path(sidecar_path).expanduser().resolve()
        records = build_analysis_import_records(str(sidecar_path))
        
        # Upload using the db_client
        return db_client.upload_analysis_events(records)
