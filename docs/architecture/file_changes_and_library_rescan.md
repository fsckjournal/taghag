# File changes and library rescan  
Roon does **not** automatically rewrite or update your audio file tags, and it won’t immediately pick up external tag changes in its library database.  In practice, if **Tagslut** modifies a FLAC’s Vorbis comments outside of Roon, the Roon Core will only see those changes after you force it to re-scan the storage folder via the Roon UI.  (For example, use **Settings → Storage → “Rescan”** or in the album/track edit menu use **Your Files → Re-scan**.)  The node-roon-api does **not** provide any direct “rescan this track” function.  At best, within a browse session you can issue a `browse` call with `refresh_list:true`, but that only refreshes your extension’s UI list – it does *not* trigger Roon’s backend to re-index files.  In short, after writing to the files you must rely on Roon’s normal filesystem-watcher or user-initiated rescans to update the UI.

# Roon event subscriptions (reverse triggers)  
Your extension *can* subscribe to Roon transport events to detect playback activity. In Node you would require the `RoonApiTransport` service and call `transport.subscribe_zones(...)`.  For example:  

```js
const transport = core.services.RoonApiTransport;
transport.subscribe_zones((cmd, data) => {
  if (cmd === "Changed" && data.zones_changed) {
    data.zones_changed.forEach(zone => {
      // If a track just started playing
      if (zone.state === 'playing' && zone.now_playing) {
        console.log(`Now playing in zone ${zone.display_name}:`, 
                    zone.now_playing.three_line.line1);
        // Here you could trigger Tagslut on zone.now_playing.track_id or so.
      }
    });
  }
});
```  

This subscription will notify your code whenever a zone’s state changes (play/pause/stop) and include `now_playing` info.  You can thus detect when a track begins playing.  **Playlist additions or tag edits:** Unfortunately, Roon’s API does *not* offer a public event for “user added a track to a tag or playlist.” There is no `subscribe_tags` or `subscribe_playlists` service. The only workaround is for your extension to periodically browse the library (e.g. hierarchy “playlists” or a custom UI) and check for new items, but there is no push notification. In summary: use `subscribe_zones` (or `subscribe_outputs`) to catch playback events; other user actions in the UI (like adding tags or playlists) are not pushed to extensions.

# Audio analysis data & play counts  
Roon’s internal analysis (BPM/tempo, loudness, waveform data, “dynamic range,” etc.) is not exposed via the public API.  Likewise, Roon does not provide a simple “play count” field per track through the API. Roon records detailed play history internally (including percentage played, etc.), but **play count is not a retrievable API value**. In practice, there’s no documented node-roon-api method to get a track’s BPM or play count. (Community sources note that Roon does not support importing or exporting play counts via API.)  If you need this info, you would have to either read it from Roon’s internal database (LevelDB) or compute it yourself. The API will only give you basic track metadata (titles, artists, album, etc.) and now_playing info, but not analysis metrics.

# UI flow & RoonApiBrowse usage  
Roon does not let extensions inject new items into the native track/album context menu. The usual UI flow is: the user opens the Roon **Settings → Extensions** panel, finds the Tagslut extension, and clicks it to open your extension’s browse-based UI. From there you would present your own menu/actions. For example, you could offer an item **“Process current track”** (using the transport state to know what’s playing) or a **“Search by Tagslut DB”** input.  A typical flow might be:  
- **User navigates to an album or is playing a track**, then opens **Settings → Extensions → Tagslut**.  
- The Tagslut UI (using RoonApiBrowse) shows options, e.g. “Process Now Playing Track” or “Browse Library” or “Search Tracks.”  
- If “Process Now Playing” is chosen, the extension takes the `now_playing` info and runs Tagslut on that file.  
- If “Search Tracks” is chosen, you can use RoonApiBrowse’s text input prompt to get a query, then display results.  

RoonApiBrowse can indeed present dynamic lists (including using an input prompt) so you can return live data from your DB. For example, you can create an `Item` with an `input_prompt` (prompt/action/value) to let the user type a search query. Your browse callbacks would then run the query on your SQLite DB and populate the list of `Items` accordingly. However, once the list is shown it is static until the user takes another action or refreshes it; there is no auto-updating list.  

In summary, there is no “one-click” context menu shortcut – the user must open the extension interface via Settings. You could shortcut this slightly by coding the extension so that if opened while music is playing it defaults to acting on the current track. But aside from that, the standard approach is: **Roon UI → Settings → Extensions → Tagslut → (choose track/action) → Go**. All UI interactions beyond that are handled via RoonApiBrowse lists and callbacks.

**Sources:** Official Roon API docs and community resources (Roon does not auto-update file tags, manual rescans are needed; and RoonApiTransport.subscribe_zones can catch playback state changes).