# Roon Extension UI & Actions  
The Roon API does **not** expose a way to inject new right‑click (context menu) items into the main Roon library UI.  Instead, Roon extensions present their own interface via the *Browse* service or the Extensions settings. In practice, you would add a new “Tagslut” entry under **Settings → Extensions**, or create a custom browse hierarchy that the user can navigate to trigger actions.  In other words, you **cannot** hook a “Process with Tagslut” into the native track or album context menu. The most seamless UX is to have an Extension browse screen (or a status/control action) where the user can pick the **Now Playing track** or select from a list, and then press “Process”.  

- The [RoonApiBrowse service](https://roonlabs.github.io/node-roon-api/RoonApiBrowse.html) lets you build a hierarchical, list-based UI inside Roon. For example, your extension could have an item “Zones → Current Track → [Run Tagslut]”.  
- Alternatively, use the **Transport service** to subscribe to zones/now_playing and a simple status button. For instance, in `core_paired` you can grab `core.services.RoonApiTransport.subscribe_zones` to monitor the current track, then offer an action like “Process Now Playing” in your UI.  
- The Roon API example shows using a status service (via `node-roon-api-status`) to report extension status.  For UI feedback you might call `svc_status.set_status("Running Tagslut...", false)` while the process runs (see code below).  This status appears under the extension in **Settings**.  

In summary, **you must use an extension UI** (browse or settings) to select a track; there is no built‑in “right-click” extension hook in the Roon library. The browse/service approach is the least friction way to “select a track and do the rest.”

# File Paths and Identifiers  
Roon’s API **does not** reveal the local file path of a track to extensions. Roon abstracts files via its storage system, so paths or UNC mounts aren’t exposed. Instead you’ll get Roon’s internal IDs and metadata (title, album, artist, duration, etc.) but **no `"/Volumes/MUSIC/…”` path** via the API. As one Roon community member notes, Roon *“does not modify the audio files by design… All metadata is only stored in Roon’s database.”*. Even the only workaround (Roon’s “Export” function) merely copies files to a new location with basic tags. 

**Workaround:** To identify the same track in your local Tagslut database, use the metadata fields Roon does expose. For example, retrieve the album name, track number, title, artist/album‑artist, duration, etc. from the browse/now_playing info and use those to match your DB record. If your DB uses AcoustID or fingerprints, you could compute or look up the fingerprint for the file on disk once you’ve identified it by metadata. (Roon itself does not provide AcoustID or persistent unique IDs to extensions.) In practice, extensions typically do something like: get *Title/Artist/Album/Track Number* from Roon’s API, then query the local SQLite DB for that combination. If multiple matches exist, you may also compare duration or file hash. 

In short: **No absolute path or persistent file ID is exposed by Roon’s API**. You must rely on metadata (and any in-house matching logic in Tagslut) to link a playing track to your library entry.  

# Node→Python Integration (IPC)  
Since the Roon API is Node.js-based and Tagslut is a Python CLI, you need a way for the Node extension to invoke your Python tool. A robust, simple approach is to spawn the Python process directly and pipe output back to Node. For example:

```js
const { spawn } = require('child_process');

// Example: run Tagslut on the given file path
function runTagslut(filePath) {
    // Update Roon extension status
    svc_status.set_status(`Running Tagslut on ${filePath}`, false);

    // Spawn the Python CLI process
    const py = spawn('python3', ['/path/to/tagslut-cli.py', filePath]);

    py.stdout.on('data', data => {
        console.log(`[Tagslut stdout] ${data}`);
        // (Optionally parse and update progress)
    });
    py.stderr.on('data', data => {
        console.error(`[Tagslut stderr] ${data}`);
    });
    py.on('close', code => {
        if (code === 0) {
            svc_status.set_status(`Tagslut completed successfully`, false);
        } else {
            svc_status.set_status(`Tagslut failed (code ${code})`, true);
        }
    });
}
```

This uses `child_process.spawn` to invoke Python. You then listen on `stdout`/`stderr` to stream progress or errors. You can relay progress to the Roon UI by updating `svc_status` (or by returning “message” actions in a browse response). Another pattern is to run a lightweight HTTP server (e.g. Flask/FastAPI) in Python and have Node call it via `fetch`/`axios`; but that adds complexity and needs you to manage the server lifecycle. For a one‑off command-line tool, spawning is straightforward and reliable. 

**Reporting progress:** In Node, you can use `RoonApiStatus.set_status(...)` (as above) to post status messages in Roon’s UI. Alternatively, if your extension has a browse-based UI, you can return a browse result with an `action: "message"` to show a popup. But most simple is updating the status service so the user sees “Tagslut running…” or errors under the extension name.

# macOS Deployment  
On a Mac, you can run the Node extension process directly alongside Roon Core. Roon does not require a special installer; you just keep your Node script running (along with any Python sidecars). Common approaches:

- **Launchd**: Create a `launchd` plist to run `node /path/to/app.js` at login/system-start. This ensures your extension starts automatically. 
- **pm2** or similar: Use a process manager to keep the Node script alive and restart on crashes.
- **Roon Extension Manager (REM)**: TheAppgineer’s Roon Extension Manager can install/update many extensions. It’s more commonly used on Linux, but can run on macOS as well. REM is *recommended* for non-technical users. If you prefer manual control, you can skip REM entirely and just run the Node process yourself. In either case, the extension must be running on the same machine as the Core. 

For personal use, it’s simplest to just launch your Node app on startup (via `launchd` or a login item) and ensure Python 3.13 and Tagslut are installed on that machine. Using REM can simplify auto-updates, but isn’t strictly required. 

# Prior Art & References  
We found no existing Roon extension that specifically integrates a tagger like Beets, Picard, or SongKong. (Roon’s model generally keeps metadata in its own DB, and tagging is done outside of Roon.) However, there are example Roon extensions you can study for architecture and boilerplate. For instance, TheAppgineer’s [Random Radio](https://github.com/TheAppgineer/roon-extension-random-radio) extension shows a complete Node extension with browse UI and installation via REM. The [Roonlabs/node-roon-api GitHub repo](https://github.com/RoonLabs/node-roon-api) README and examples (shown above) illustrate how to set up services and status. You might also look at other community extensions (e.g. HomeKit controllers, now-playing displays, etc.) for patterns of subscription and actions. 

Key reference snippets from the Roon docs:  

- **Browse service**: *“the browse service allows you to present a hierarchical, list-based user interface for Roon.”* – use this to build your selection UI.  
- **Transport/Status**: Example code showing `RoonApiStatus` usage (call `set_status(...)` to show a message in Roon Settings).  
- **File info limitation**: As one support user explains, Roon “does not modify the audio files by design… metadata is only stored in Roon’s database.” The only way to get tags into files is Roon’s Export feature. This underscores that your integration must be external (i.e. Python CLI writing ID3 tags itself).  

**Architecture Summary:** Your Node extension will pair with the Roon Core, subscribe to zone/transport info (for “now playing”), or present a custom browse list. When the user chooses a track/album, Node looks up the track’s metadata, finds the corresponding file in your local storage (via your DB or filesystem), then runs the Tagslut Python CLI on it using `child_process.spawn`. You use `RoonApiStatus` (or browse messages) to show progress or results. This bridges the Node-based Roon API to your Python tagger seamlessly.  

**Example Boilerplate (Node)**: In your `app.js` you might start with something like:  

```js
var RoonApi        = require("node-roon-api");
var RoonApiBrowse  = require("node-roon-api-browse");
var RoonApiStatus  = require("node-roon-api-status");

var roon = new RoonApi({
  extension_id:   "com.example.tagslut",
  display_name:   "Tagslut Extension",
  display_version:"0.1.0",
  publisher:      "Your Name",
  email:          "you@example.com",
  website:        "https://your.website"
});

var svc_status = new RoonApiStatus(roon);

roon.init_services({
    required_services: [ RoonApiBrowse ],    // e.g. to present UI
    provided_services: [ svc_status ]       // so we can set status messages
});

roon.start_discovery();

// When Core is paired:
roon.on('core_paired', core => {
    // Example: handle a browse request or a custom action here.
    core.services.RoonApiBrowse.browse({
        hierarchy: "browse"
    }, (err, response) => {
        // Build your list of items (including a “Process with Tagslut” action item).
    });
    
    // Or subscribe to transport to get now playing:
    let transport = core.services.RoonApiTransport;
    transport.subscribe_zones((cmd, data) => {
        if (data && data.now_playing && data.now_playing.three_line) {
            let trackTitle = data.now_playing.three_line.line3; 
            // store track info for when user triggers processing...
        }
    });
});
```

This, combined with the spawn code above, illustrates the approach. With these pieces – Roon browse/status services, transport subscription, and a Node→Python bridge – you can build a “select track → Tagslut” workflow. 

**Sources:** Roon Labs Node API docs and examples; Roon Community posts clarifying file/tag behavior; and TheAppgineer’s Roon Extension Manager guidance. These demonstrate the capabilities and limitations of the Roon extension framework. 

