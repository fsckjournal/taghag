#!/usr/bin/env python3
"""Make the Gemini "brain" queryable — chatlogs, scratchpads, plans, walkthroughs.

The Antigravity/Gemini IDE stores every session under
`~/.gemini/antigravity-ide/brain/<session-uuid>/`:
  - top-level artifacts: task.md, implementation_plan.md, walkthrough.md, plus
    ad-hoc analyses/prompts/handover reports (each with a `*.metadata.json` sidecar
    carrying an artifactType + one-line summary)
  - scratch/*.py            — throwaway scripts the agent wrote
  - browser/scratchpad_*.md  — browser-session scratchpads
  - .system_generated/logs/transcript.jsonl — the actual chat transcript (one JSON
    object per step: USER_INPUT, PLANNER_RESPONSE, RUN_COMMAND, CODE_ACTION, ...)
  - .system_generated/tasks/task-*.log — command/run logs

This builds a single local SQLite FTS5 index over all of that text (no images, no
opaque state JSON) and gives you keyword search with BM25 ranking + snippets. Pure
stdlib; the DB lives next to the brain so the whole thing is self-contained.

Usage:
  python brain_cli.py build [--brain DIR] [--verbose]   # (re)build the index
  python brain_cli.py search "beatport token bypass"     # full-text search
  python brain_cli.py search "automix" --kind plan       # filter by kind
  python brain_cli.py search "offtrack" --session b18885ca --context 3
  python brain_cli.py show <rowid>                        # print one full chunk
  python brain_cli.py show --path <relpath>               # print a whole file
  python brain_cli.py sessions                            # list sessions + summaries
  python brain_cli.py stats                               # index stats

FTS5 query syntax is supported directly: `"exact phrase"`, `a OR b`, `a NOT b`,
`token*` prefix, `NEAR(a b, 5)`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

DEFAULT_BRAIN = Path(
    os.environ.get("GEMINI_BRAIN") or Path.home() / ".gemini" / "antigravity-ide" / "brain"
)
DB_NAME = ".brain_index.sqlite"

# Transcript step types worth indexing, mapped to a compact role. Everything else
# (system reminders, conversation-history markers, knowledge-artifact dumps) is noise.
TRANSCRIPT_ROLES = {
    "USER_INPUT": "user",
    "PLANNER_RESPONSE": "model",
    "GENERIC": "model",
    "RUN_COMMAND": "run",
    "CODE_ACTION": "edit",
    "VIEW_FILE": "view",
    "GREP_SEARCH": "grep",
    "LIST_DIRECTORY": "ls",
    "ERROR_MESSAGE": "error",
}
TRANSCRIPT_SKIP = {
    "EPHEMERAL_MESSAGE", "CONVERSATION_HISTORY", "KNOWLEDGE_ARTIFACTS",
    "SYSTEM_MESSAGE", "CHECKPOINT",
}

# Markdown artifact filename -> kind.
def md_kind(name: str) -> str:
    n = name.lower()
    if n.startswith("scratchpad_"):
        return "scratchpad"
    if "implementation_plan" in n or n == "plan.md":
        return "plan"
    if "walkthrough" in n:
        return "walkthrough"
    if n == "task.md" or n.startswith("task"):
        return "task"
    if "handover" in n or "status" in n or "report" in n or "progress" in n:
        return "report"
    if "prompt" in n:
        return "prompt"
    if "analysis" in n or "research" in n or "record" in n or "brief" in n:
        return "analysis"
    return "doc"


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("# ").strip()[:200]
        if s:
            return s[:200]
    return fallback


def load_summary(md_path: Path) -> tuple[str, str]:
    """Return (summary, artifact_type) from the `<file>.metadata.json` sidecar, if any."""
    side = md_path.with_name(md_path.name + ".metadata.json")
    if side.exists():
        try:
            m = json.loads(side.read_text(encoding="utf-8", errors="replace"))
            return (m.get("summary", "") or "")[:500], m.get("artifactType", "") or ""
        except Exception:
            pass
    return "", ""


def clean(text: str) -> str:
    # Strip the USER_REQUEST / metadata envelopes the IDE wraps around messages so
    # the indexed content is the actual prose.
    text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.S)
    text = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", text, flags=re.S)
    text = text.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")
    return text.strip()


def schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP TABLE IF EXISTS chunks;
        CREATE VIRTUAL TABLE chunks USING fts5(
            session UNINDEXED,
            path    UNINDEXED,
            kind    UNINDEXED,
            role    UNINDEXED,
            mtime   UNINDEXED,
            step    UNINDEXED,
            title,
            summary,
            content,
            tokenize = "unicode61 remove_diacritics 2"
        );
        """
    )


def add(con, session, path, kind, role, mtime, step, title, summary, content):
    if not (content and content.strip()):
        return 0
    con.execute(
        "INSERT INTO chunks(session,path,kind,role,mtime,step,title,summary,content)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (session, path, kind, role, round(mtime), step, title, summary, content),
    )
    return 1


def index_transcript(con, brain: Path, jf: Path, session: str) -> int:
    n = 0
    try:
        lines = jf.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return 0
    rel = str(jf.relative_to(brain))
    mt = jf.stat().st_mtime
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        typ = d.get("type")
        if typ in TRANSCRIPT_SKIP or typ not in TRANSCRIPT_ROLES:
            continue
        content = clean(str(d.get("content") or ""))
        if not content:
            continue
        role = TRANSCRIPT_ROLES[typ]
        step = d.get("step_index")
        title = f"{role} @ step {step}"
        n += add(con, session, rel, "chat", role, mt, step, title, "", content)
    return n


def build(brain: Path, verbose: bool) -> None:
    if not brain.exists():
        sys.exit(f"brain dir not found: {brain}")
    db = brain / DB_NAME
    con = sqlite3.connect(db)
    schema(con)
    counts: dict[str, int] = {}
    sessions: set[str] = set()

    for root, dirs, files in os.walk(brain):
        # Skip media/temp noise dirs but keep .system_generated logs/tasks.
        dirs[:] = [d for d in dirs if d not in (".tempmediaStorage",)]
        rootp = Path(root)
        for fn in files:
            fp = rootp / fn
            try:
                rel = fp.relative_to(brain)
            except ValueError:
                continue
            session = rel.parts[0] if rel.parts else ""
            ext = fp.suffix.lower()
            try:
                mt = fp.stat().st_mtime
            except OSError:
                continue

            kind = role = None
            title = summary = ""
            content = ""

            if fn == "transcript.jsonl":
                got = index_transcript(con, brain, fp, session)
                counts["chat"] = counts.get("chat", 0) + got
                if got:
                    sessions.add(session)
                continue
            if fn == "transcript_full.jsonl":
                continue  # superset dup of transcript.jsonl
            if fn.endswith(".metadata.json"):
                continue  # consumed as sidecars
            if ext == ".md":
                kind = md_kind(fn)
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                summary, _atype = load_summary(fp)
                title = first_heading(content, fn)
                role = "artifact"
            elif ext == ".py":
                kind = "scratch_py"
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                title = fn
                role = "code"
            elif ext == ".log":
                kind = "task_log"
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                title = fn
                role = "log"
            elif ext == ".txt":
                kind = "doc"
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                title = fn
                role = "artifact"
            else:
                continue  # images, opaque json, binaries

            got = add(con, session, str(rel), kind, role, mt, None, title, summary, content)
            if got:
                counts[kind] = counts.get(kind, 0) + 1
                sessions.add(session)
                if verbose:
                    print(f"  + [{kind}] {rel}")

    con.commit()
    total = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    con.close()
    print(f"indexed {total} chunks across {len(sessions)} sessions -> {db}")
    for k in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {counts[k]:>5}  {k}")


def connect(brain: Path) -> sqlite3.Connection:
    db = brain / DB_NAME
    if not db.exists():
        sys.exit(f"no index at {db} — run: python brain_cli.py build")
    return sqlite3.connect(db)


def search(brain: Path, query: str, kind: str | None, session: str | None,
           role: str | None, limit: int, context: int) -> None:
    con = connect(brain)
    where = ["chunks MATCH ?"]
    params: list = [query]
    if kind:
        where.append("kind = ?"); params.append(kind)
    if session:
        where.append("session LIKE ?"); params.append(session + "%")
    if role:
        where.append("role = ?"); params.append(role)
    sql = (
        "SELECT rowid, session, path, kind, role, mtime, title, "
        f"snippet(chunks, 8, '\x1b[1;33m', '\x1b[0m', ' … ', {max(8, context * 12)}) "
        "FROM chunks WHERE " + " AND ".join(where) +
        " ORDER BY bm25(chunks, 0,0,0,0,0,0, 4.0, 6.0, 1.0) LIMIT ?"
    )
    params.append(limit)
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        sys.exit(f"query error: {e}\n(FTS5 syntax: \"phrase\", a OR b, term*, NEAR(a b,5))")
    if not rows:
        print("no matches.")
        return
    import datetime
    for rowid, sess, path, k, r, mt, title, snip in rows:
        when = datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d") if mt else "?"
        sess8 = (sess or "")[:8]
        print(f"\x1b[36m#{rowid}\x1b[0m  \x1b[1m{k}/{r}\x1b[0m  {sess8}  {when}  \x1b[2m{title}\x1b[0m")
        print(f"  {snip.strip()}")
        print(f"  \x1b[2m{path}\x1b[0m")
        print()
    con.close()


def show(brain: Path, rowid: int | None, path: str | None) -> None:
    con = connect(brain)
    if path:
        full = (brain / path)
        if full.exists():
            print(full.read_text(encoding="utf-8", errors="replace"))
            return
        rows = con.execute(
            "SELECT role, step, content FROM chunks WHERE path = ? ORDER BY step", (path,)
        ).fetchall()
        for role, step, content in rows:
            print(f"\n===== {role} @ step {step} =====")
            print(content)
        return
    row = con.execute(
        "SELECT session, path, kind, role, step, title, summary, content "
        "FROM chunks WHERE rowid = ?", (rowid,)
    ).fetchone()
    if not row:
        sys.exit(f"no chunk #{rowid}")
    sess, path, k, r, step, title, summary, content = row
    print(f"session : {sess}\npath    : {path}\nkind    : {k}/{r}  step={step}")
    print(f"title   : {title}")
    if summary:
        print(f"summary : {summary}")
    print("-" * 60)
    print(content)
    con.close()


def sessions(brain: Path) -> None:
    con = connect(brain)
    rows = con.execute(
        "SELECT session, count(*) c, max(mtime) m FROM chunks GROUP BY session ORDER BY m DESC"
    ).fetchall()
    import datetime
    for sess, c, m in rows:
        when = datetime.datetime.fromtimestamp(m).strftime("%Y-%m-%d") if m else "?"
        # Best available summary: a task/plan title for this session.
        s = con.execute(
            "SELECT summary FROM chunks WHERE session=? AND summary!='' ORDER BY kind LIMIT 1",
            (sess,),
        ).fetchone()
        label = (s[0] if s else "") or ""
        print(f"{sess[:8]}  {when}  {c:>4} chunks  \x1b[2m{label[:80]}\x1b[0m")
    con.close()


def stats(brain: Path) -> None:
    con = connect(brain)
    total = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    nsess = con.execute("SELECT count(DISTINCT session) FROM chunks").fetchone()[0]
    print(f"{total} chunks, {nsess} sessions, db={brain / DB_NAME}")
    for k, c in con.execute("SELECT kind, count(*) FROM chunks GROUP BY kind ORDER BY 2 DESC"):
        print(f"  {c:>5}  {k}")
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brain", type=Path, default=DEFAULT_BRAIN, help="brain dir")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="(re)build the index")
    b.add_argument("--verbose", action="store_true")

    s = sub.add_parser("search", help="full-text search")
    s.add_argument("query")
    s.add_argument("--kind", help="filter: chat|plan|walkthrough|task|scratchpad|scratch_py|analysis|prompt|report|task_log|doc")
    s.add_argument("--session", help="filter by session id prefix")
    s.add_argument("--role", help="filter: user|model|run|edit|code|artifact|log|...")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--context", type=int, default=3, help="snippet width")

    sh = sub.add_parser("show", help="print a chunk (#rowid) or whole file (--path)")
    sh.add_argument("rowid", nargs="?", type=int)
    sh.add_argument("--path")

    sub.add_parser("sessions", help="list sessions")
    sub.add_parser("stats", help="index stats")

    a = ap.parse_args()
    if a.cmd == "build":
        build(a.brain, a.verbose)
    elif a.cmd == "search":
        search(a.brain, a.query, a.kind, a.session, a.role, a.limit, a.context)
    elif a.cmd == "show":
        if a.rowid is None and not a.path:
            sys.exit("show needs a rowid or --path")
        show(a.brain, a.rowid, a.path)
    elif a.cmd == "sessions":
        sessions(a.brain)
    elif a.cmd == "stats":
        stats(a.brain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
