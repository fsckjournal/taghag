from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


# cleanroom-audit: allow-start
FORBIDDEN_TERMS = (
    "from tagslut",
    "import tagslut",
    "asset_file",
    "track_identity",
    "asset_link",
    "preferred_asset",
    "move_plan",
    "move_execution",
    "provenance_event",
    "AAC_LIBRARY",
    "M4A derivative",
    "AAC-first",
)
# cleanroom-audit: allow-end

DEFAULT_SCAN_PATHS = (
    "tools",
    "web/src",
    "supabase",
    ".env.example",
)

SKIP_DIRS = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".git",
    "taghag_import.egg-info",
}

ALLOW_START = "cleanroom-audit: allow-start"
ALLOW_END = "cleanroom-audit: allow-end"
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".json",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".example",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    term: str
    line: str

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        return f"{rel}:{self.line_number}: forbidden term {self.term!r}: {self.line.strip()}"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def iter_files(root: Path, scan_paths: tuple[str, ...] = DEFAULT_SCAN_PATHS) -> list[Path]:
    files: list[Path] = []
    for item in scan_paths:
        path = root / item
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if any(part in SKIP_DIRS for part in child.parts):
                continue
            if child.is_file() and (child.suffix in TEXT_EXTENSIONS or child.name == ".env.example"):
                files.append(child)
    return sorted(files)


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    in_allow_block = False
    text = path.read_text(encoding="utf-8", errors="replace")
    for index, line in enumerate(text.splitlines(), start=1):
        if ALLOW_START in line:
            in_allow_block = True
            continue
        if ALLOW_END in line:
            in_allow_block = False
            continue
        if in_allow_block:
            continue
        for term in FORBIDDEN_TERMS:
            if term in line:
                findings.append(Finding(path=path, line_number=index, term=term, line=line))
    return findings


def scan(root: Path, scan_paths: tuple[str, ...] = DEFAULT_SCAN_PATHS) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root, scan_paths):
        findings.extend(scan_file(path))
    return findings


def main() -> int:
    root = repository_root()
    findings = scan(root)
    if findings:
        for finding in findings:
            print(finding.format(root))
        return 1
    print("Clean-room audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
