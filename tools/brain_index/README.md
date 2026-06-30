# brain_index — query the Gemini "brain"

Makes `~/.gemini/antigravity-ide/brain` (every Antigravity/Gemini IDE session:
chatlogs, scratchpads, plans, walkthroughs, task logs, throwaway scripts) **queryable**
via a single local SQLite **FTS5** index. Pure stdlib, no deps, no cloud. The DB lives
next to the brain (`.brain_index.sqlite`), so it's self-contained and never leaves disk.

## Why

The brain holds the heist gold (Beatport bypass, offtrack decode, automix plans) buried
across ~10k transcript steps + artifacts in 38 sessions. `gemini-brain-gold.md` is the
hand-curated index; this is the full-text one.

## Use

```bash
cd tools/brain_index
python3 brain_cli.py build                 # (re)build — re-run after new Gemini sessions

python3 brain_cli.py search "beatport token"        # BM25-ranked, highlighted snippets
python3 brain_cli.py search "automix" --kind plan    # filter by kind
python3 brain_cli.py search "offtrack" --session b18885ca --role model
python3 brain_cli.py search "NEAR(token derive, 8)"  # raw FTS5 syntax works

python3 brain_cli.py show 7067             # full chunk by #rowid
python3 brain_cli.py show --path <rel>     # whole file / all transcript turns of a file
python3 brain_cli.py sessions              # sessions + their artifact summaries
python3 brain_cli.py stats                 # index stats
```

`./brain` is a thin launcher for the same thing from anywhere.

## What's indexed

| kind | source |
| --- | --- |
| `chat` | `.system_generated/logs/transcript.jsonl` steps (user / model / run / edit / view / grep …); IDE envelopes stripped |
| `plan` `walkthrough` `task` `report` `prompt` `analysis` `scratchpad` `doc` | top-level `*.md` artifacts (+ `*.metadata.json` summary sidecars) |
| `scratch_py` | `scratch/*.py` throwaway scripts |
| `task_log` | `.system_generated/tasks/task-*.log` |

Skipped: images (png/webp), opaque state json, binaries, `transcript_full.jsonl` (dup).

FTS5 query syntax: `"exact phrase"`, `a OR b`, `a NOT b`, `term*` (prefix), `NEAR(a b, 5)`.

## Notes

- The index is a derived cache — safe to delete and rebuild. It is **not** committed
  (it lives under `~/.gemini`, outside the repo).
- Transcripts can contain (now-rotated) Beatport creds; the DB stays local, never pushed.
  See memory `beatport-har-secrets`.
