# USB Share Audit

Audit source: `/Volumes/REKORDBOX/USBSMB/share`

## Bottom Line

- 59 release folders and 913 USB audio files were checked.
- 194 USB tracks matched database metadata.
- 719 USB tracks had no matching database row.
- No database file path currently points to an existing file.
- Nothing in this audit is safe to remove from the USB based on the database.

## Confirmed Missing From USB

`[2016] Paper Cuts #3` jumps from track 24 to track 27. The library playlists
explicitly list the two absent tracks:

| Track | Artist | Title |
|---:|---|---|
| 25 | Ralph Myerz | Acid 4 Eddie (Original Mix) |
| 26 | Weedyman | Feel It (Original Mix) |

Sources:

- `/Volumes/MUSIC/staging/VA/[2016] Paper Cuts #3/[2016] Paper Cuts #3.m3u`
- `/Volumes/MUSIC/staging/SpotiFLACnext/Paper Cuts #3.m3u8`

## Other USB Anomalies

These are numbering warnings, not yet confirmed against an authoritative
tracklist:

| Release | Finding |
|---|---|
| The Juan MacLean - DJ-KiCKS | Filename sequence skips track 04 |
| Dessous Classics (The Best Of 10 Years) | Filename sequence skips track 08 |
| Cody Currie - Cherry | Two files both numbered track 01 |

## Database Coverage

### All USB Tracks Represented In DB

The database metadata covers all USB tracks for these 12 releases, but every
stored file path is dead:

- `[2007] Dessous Recordings Best Kept Secrets`
- `[2008] Cosmic Balearic Beats Vol. 1`
- `[2013] Dessous Recordings Summer Grooves`
- `[2013] The Pink Collection`
- `[2015] Best Of 2015`
- `[2015] Dessous Recordings Summer Grooves 3`
- `[2016] The Yellow Collection`
- `[2017] Dessous Summer Grooves 5`
- `[2021] Paper Cuts #5`
- `[2022] Eskimo Recordings presents The Remixes`
- `[2026] Lebanese Blonde`
- `Mindchatter - Giving Up On Words (2025) [FLAC] [24B-44.1kHz]`

### Partial Database Coverage

| Release | USB | Matched | Missing From DB | DB Rows |
|---|---:|---:|---:|---:|
| `[2009] Cosmic Balearic Beats Vol. 2` | 16 | 15 | 1 | 16 |
| `[2012] Paper Cuts #1` | 22 | 21 | 1 | 44 |
| `[2016] Paper Cuts #3` | 26 | 0 | 26 | 1 |
| `The Juan MacLean - DJ-KiCKS` | 17 | 1 | 16 | 17 |

The apparent misses for Cosmic Balearic Beats and Paper Cuts #1 are metadata
credit differences:

- `Premier Rang - Zoe et Heine`
- `Flash Atkins - Did You Forget to Shine? (Paper Cuts Edit)`

### No Database Rows

The remaining 43 releases have no database rows grouped under the same release
folder name.

## Detailed Files

- `releases.csv`: one sortable row per release.
- `tracks.csv`: one sortable row per USB track with DB match status and path.
- `exceptions.csv`: confirmed missing tracks and numbering anomalies.

