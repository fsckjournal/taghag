# Tagslut Roon Extension

This Node.js extension exposes a supported Roon Settings action for the current
playing track. It resolves that track to exactly one active FLAC master in
`music_v3.db`, then invokes the local Tagslut CLI.

The action is preview-only by default. Enable **Apply tag changes** in the Roon
extension settings only after reviewing a successful preview.

## Run

```bash
cd roon-extension
npm install
TAGSLUT_DB=/absolute/path/to/music_v3.db npm start
```

Set `TAGSLUT_PYTHON` when the extension should use a specific Python
interpreter, such as the repository virtual environment.

Resolution deliberately fails when no active FLAC is linked or when the
now-playing title, artist, and optional album identify more than one existing
file. It never falls back to fuzzy path matching.
