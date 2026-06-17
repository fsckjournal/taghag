# Direct LevelDB Access

Roon’s library is stored in a hidden LevelDB database under `~/Library/Roon/Database/Core/...`, but this data is opaque and not officially exposed. In practice **you should avoid reading or writing Roon’s LevelDB while Roon is running**. The community warns that LevelDB is essentially an in-memory store and concurrently reading it can lead to corruption or inconsistent data. No public API exists to query Roon’s internal storage mappings. In theory one *could* stop the Core and inspect the .ldb files with a LevelDB reader (e.g. via [`plyvel`][], [`leveldb`][], or Google’s C++ LevelDB library), but the schema is undocumented. The forum consensus is: **“You don’t want to touch those files… it would require reverse engineering… risk of corrupting things”**. 

In other words, there is no safe, documented way to query Roon’s LevelDB to get file paths. As a workaround, use Roon’s known “RoonMounts” mapping. On macOS (and Linux), Roon creates a `~/Library/RoonMounts/` folder that mirrors each watched storage. For example, if you added `/Volumes/MUSIC/MASTER_LIBRARY/` as a storage, Roon will create a symlink-like folder `~/Library/RoonMounts/RoonStorage_<UUID>/MASTER_LIBRARY`. Thus you can reconstruct the real path by following these mounts. In practice you might do something like: 

```js
// Example: resolve RoonMounts path to actual mountpoint
const fs = require('fs');
let trackPath = "/Users/alice/Library/RoonMounts/RoonStorage_11bf.../MASTER_LIBRARY/Album/track.flac";
// if it's a symlink, resolve it:
let realPath = fs.realpathSync(trackPath);
// or strip the RoonMounts prefix:
let userHome = require('os').homedir();
if (trackPath.startsWith(userHome + "/Library/RoonMounts/")) {
    // e.g. '/Volumes/MUSIC/MASTER_LIBRARY/...'
    let rel = trackPath.replace(userHome + "/Library/RoonMounts/RoonStorage_11bf.../", "/Volumes/MUSIC/");
    console.log("Absolute path:", rel);
}
```

That said, the extension can simply use the Roon API to identify the track (by RoonTrackID or other metadata) and then map the path as needed offline. There is no direct API call to get the filesystem path; you must either derive it via the RoonMounts symlinks or match on tags/acoustids/etc in your own DB.

# Writing Tags or Playlists via the Roon API

**Roon’s API is essentially read-only for library metadata.** Extensions *cannot* add or modify Roon’s internal tags or playlists. As confirmed in the Roon forums, “the library part of the API is read-only, so you can’t modify tags using the API”. Likewise, you cannot add tracks to an existing Roon playlist via the API – the only playlist-related action available is playing a playlist. As one Roon developer put it: **“The only action that can be done via the Roon API on a playlist is to play it; there is no playlist manipulation functionality”**. In short, you cannot push custom “Banger” tags into Roon or auto-update Roon playlists. Your extension can only read metadata and control playback; it cannot change Roon’s own database of tags or playlists. (Any tagging must remain in your local tool and library, not in Roon’s UI.)

# UX Flow for Triggering Tagslut

Roon does *not* allow injecting custom right-click or context-menu items on tracks. The only place an extension can appear is in Roon’s Extensions screen. The most “native” user flow is:

1. **Enable the Tagslut extension** in Roon (Settings → Extensions, then pair/enable it). 
2. In the Roon UI (on a remote or on Core), open **Settings → Extensions → Tagslut**. This launches your extension’s browse UI.
3. Your extension’s Browse session then presents options (e.g. “Process Currently Playing Track”, or a search prompt to find a track). The user selects one. 
4. The extension receives the selection (e.g. a Roon Track ID) and invokes Tagslut for that track.
5. The extension can update Roon’s **Status** line (using `RoonApiStatus`) or show messages via browse to indicate progress/results.

For example, the extension might display a first-level menu:
```
[ ] Process Currently Playing Track   (action_list hint, showing a play icon)
[ ] Search for Track...
```
If the user chooses “Currently Playing Track”, the extension grabs the current track’s ID (via RoonApiTransport or RoonApiBrowse with context) and runs Tagslut. If “Search for Track” is chosen, the extension presents an **input box** (RoonApiBrowse supports an `opts.input` field) where the user types an album or track name, then the extension does a library search (via `core.services.RoonApiBrowse.browse({hierarchy: 'search', input: '…'})`) to show matching tracks. Once the user selects one of those (they’ll appear as `action_list` items), you run Tagslut on it.

In practice, *every* user action must go through the Extensions menu. There’s no way to bind a global hotkey or “Share to Tagslut” webhook inside Roon. A clever workaround (used by some power users) is to use an external automation (like BetterTouchTool or a macro) to pop open Roon’s Extensions screen, but that’s outside Roon’s API. The safe answer: **use RoonApiBrowse** to drive the interaction. The user will click Menu → Extensions → *Tagslut* → (choose track) → *Run*. 

# Actionable UI Elements

Roon’s Extension UI is built entirely with the `RoonApiBrowse` service (plus optional status/settings screens). This browse-based UI **is dynamic and interactive**, not a static form. You can present arbitrary lists of items based on runtime data. For example, after the user enters a search term or selects an action, your extension responds with a new list of items (songs, albums, or custom actions) by calling `core.services.RoonApiBrowse.browse(...)`. Each item can have an `action_list` hint to show a play/trash icon, or `list` hint to show a folder. You can also dynamically insert items, replace items, show messages, etc. In short, **RoonApiBrowse allows dynamic lists and sub-lists**. There is no “static HTML page” or custom widget – it’s all lists managed by your extension code. 

In contrast, the `node-roon-api-settings` UI (Settings → Extensions → Config) is static and defined at startup, so it’s not used for interactive actions. All custom UI must be done with `RoonApiBrowse`. That means you can, for example, have a browse session that lists search results, Tagslut database matches, or progress updates. You simply populate the list items with titles, subtitles, thumbnails, and `action_list` hints, and handle the callbacks. 

For example, you might show the output of a Tagslut database query inside Roon by doing something like:
```js
browse.browse({hierarchy: 'browse', pop_all: true}, (err, body) => {
  let items = tagslutResults.map(track => ({
    title: track.title,
    subtitle: track.artist + ' – ' + track.album,
    type: 'item',
    item_key: track.id,
    hint: 'action_list'   // user can click it
  }));
  core.services.RoonApiBrowse.add_list_items({ hierarchy: 'browse', list: items }, () => {});
});
```
This way the Roon UI presents a list of your search results. The lists are not fixed; your extension can call `refresh_list` to update them.

# Node→Python Integration and Deployment

Your extension will use Node.js (via `node-roon-api`) but the heavy lifting (metadata enrichment, API calls, etc.) is in Python. A common pattern is for the Node extension to **spawn the Python CLI** and relay status. For example:
```js
const { spawn } = require('child_process');
function runTagslut(filePath, onData, onDone) {
  let py = spawn('python3', ['-m', 'tagslut', 'process', filePath]);
  py.stdout.on('data', chunk => onData(chunk.toString()));
  py.stderr.on('data', chunk => onData(chunk.toString()));
  py.on('close', code => onDone(code));
}

// Usage in your browse handler:
runTagslut(trackPath, (msg) => {
   // update Roon status or show progress message
   status.setStatus(msg, false); 
}, (code) => {
   status.setStatus('Done (exit '+code+')', false);
});
```
This avoids any additional HTTP layers. Alternatively, you could run a local Python web server (Flask/FastAPI) and have Node send HTTP requests, but that adds complexity (managing a server, CORS, etc.). The spawn method is simpler and robust for a command-line tool. Just make sure the Node process can find the right `python3` interpreter and that Tagslut’s dependencies are installed.

For macOS deployment, you can run your Node extension as a daemon alongside Roon Core. In development, you can simply `node app.js` (or `npm start`). For production, you have two options: **Roon Extension Manager** or standard process management. The Roon Extension Manager (community tool) can install and run Node extensions, but it’s not strictly required. On macOS you could also use **launchd** or **pm2** to launch your Node script at boot and keep it running. Ensure your extension is discoverable on the network (matching Roon’s discovery port) and that you enable it in Roon’s Settings. 

# Prior Art

We found no existing Roon extension that directly reads LevelDB or injects custom UI elements into Roon’s library. The general advice on Roon forums is to avoid LevelDB hacks. Some users have used external tools (like RoonCommandLine or webhooks) to automate Roon, but those rely on the official API (play commands, searches, etc.), not DB hacks. No one has publicly documented a safe way to reverse-engineer the Roon DB for path mapping. 

On the UI side, several open-source extensions demonstrate using `node-roon-api` and `RoonApiBrowse`. For example, the [Roon extension web controller][56] shows a JavaScript extension with browse navigation. The RoonLabs **node-roon-api** docs and examples cover basic browse and status usage. Extensions like *roon-extension-alarm-clock* or *roon-extension-weather* show how to implement a settings UI with action lists. Reviewing these can help with the boilerplate. However, **none of them bypass Roon’s restrictions**: they do not write back into Roon’s tags or playlist DB. 

In summary, your architecture will be:

- **Node.js extension** using [node-roon-api](https://github.com/RoonLabs/node-roon-api) and `RoonApiBrowse`/`RoonApiStatus`. This handles the Roon connection, UI menu, and invoking the Python tool.
- **CLI Python tool** (Tagslut) that the Node extension calls (e.g. via `child_process.spawn`) to do analysis and tagging logic. The tool should output logs or status messages that Node can capture.
- **User flow**: Roon Settings → Extensions → *Tagslut* → select action/track → Node spawns Python → Node displays progress on Roon’s status line or in browse UI.
- **UI code snippet**: Example Roon extension bootstrap:
  ```js
  const RoonApi = require("node-roon-api");
  const RoonApiBrowse = require("node-roon-api-browse");
  const RoonApiStatus = require("node-roon-api-status");
  
  let roon = new RoonApi({
    extension_id: "com.mycompany.tagslut",
    display_name: "Tagslut",
    display_version: "1.0.0",
    publisher: "Me",
    email: "me@example.com"
  });
  let browse = new RoonApiBrowse(roon);
  let status = new RoonApiStatus(roon);
  
  roon.init_services({
    required_services: [browse],
    provided_services: [status]
  });
  roon.start_discovery();
  
  roon.on('connected', (core) => {
    browse.init((_) => {
      // present initial menu here via core.services.RoonApiBrowse.browse()
    });
    status.init("Tagslut ready");
  });
  ```
  
No part of the Roon UI (outside the Extensions/settings screens) can be modified by an extension. All advanced functionality must live inside `RoonApiBrowse` lists. **Citations:** community advice on avoiding LevelDB; Roon API limitations on tags/playlists. These give the definitive guidance on what’s safe and what Roon API cannot do.  

