"use strict";

const path = require("path");
const { spawn } = require("child_process");

const RoonApi = require("node-roon-api");
const RoonApiSettings = require("node-roon-api-settings");
const RoonApiStatus = require("node-roon-api-status");
const RoonApiTransport = require("node-roon-api-transport");

let currentTrack = null;
let executeChanges = false;

function trackLines(track) {
    const lines = track && track.three_line ? track.three_line : {};
    return {
        title: String(lines.line1 || "").trim(),
        artist: String(lines.line2 || "").trim(),
        album: String(lines.line3 || "").trim(),
    };
}

function settingsPayload() {
    const track = trackLines(currentTrack);
    const nowPlaying = track.title
        ? `${track.artist || "Unknown artist"} - ${track.title}`
        : "No playing track detected";

    return {
        values: { execute_changes: executeChanges },
        layout: [
            {
                type: "label",
                title: "Now playing",
                subtitle: nowPlaying,
            },
            {
                type: "boolean",
                title: "Apply intelligence changes",
                subtitle: "Off previews the Cuecifer plan. Turn on only after reviewing a preview.",
                setting: "execute_changes",
            },
            {
                type: "button",
                title: executeChanges ? "Analyze with Cuecifer" : "Preview Cuecifer Intelligence",
                buttonid: "process_now_playing",
            },
        ],
        has_error: false,
    };
}

const roon = new RoonApi({
    extension_id: "com.taghag.cuecifer",
    display_name: "Cuecifer",
    display_version: "0.1.0",
    publisher: "Cuecifer",
    email: "hello@tagslut.org",
    website: "https://github.com/tagslut-org/tagslut",
    core_paired(core) {
        console.log(`Connected to Roon Core: ${core.display_name || core.core_id}`);
        core.services.RoonApiTransport.subscribe_zones(handleZones);
    },
    core_unpaired(core) {
        console.log(`Disconnected from Roon Core: ${core.display_name || core.core_id}`);
        currentTrack = null;
        svc_status.set_status("Waiting for Roon Core", false);
        svc_settings.update_settings(settingsPayload());
    },
});

const svc_status = new RoonApiStatus(roon);
const svc_settings = new RoonApiSettings(roon, {
    get_settings(callback) {
        callback(settingsPayload());
    },
    save_settings(req, isDryRun, settings) {
        const next = Boolean(settings && settings.values && settings.values.execute_changes);
        const payload = settingsPayload();
        payload.values.execute_changes = next;
        if (!isDryRun) {
            executeChanges = next;
        }
        req.send_complete("Success", { settings: payload });
        if (!isDryRun) {
            svc_settings.update_settings(settingsPayload());
        }
    },
    button_pressed(req, buttonId) {
        if (buttonId !== "process_now_playing") {
            req.send_complete("NotFound");
            return;
        }
        if (!currentTrack) {
            req.send_complete("Success", {
                settings: settingsPayload(),
                message: "No playing track detected.",
                is_error: true,
            });
            return;
        }

        req.send_complete("Success", { settings: settingsPayload() });
        runCuecifer(currentTrack, executeChanges);
    },
});

roon.init_services({
    required_services: [RoonApiTransport],
    provided_services: [svc_status, svc_settings],
});

function handleZones(command, data) {
    if (command !== "Subscribed" && command !== "Changed" && command !== "subscribe" && command !== "changed") {
        return;
    }

    const zones = [
        ...(Array.isArray(data && data.zones) ? data.zones : []),
        ...(Array.isArray(data && data.zones_changed) ? data.zones_changed : []),
    ];
    const playing = zones.find((zone) => zone.state === "playing" && zone.now_playing);
    if (playing) {
        currentTrack = playing.now_playing;
        const track = trackLines(currentTrack);
        svc_status.set_status(`Ready: ${track.artist} - ${track.title}`, false);
        svc_settings.update_settings(settingsPayload());
    }
}

function runCuecifer(track, execute) {
    const metadata = trackLines(track);
    if (!metadata.title || !metadata.artist) {
        svc_status.set_status("Cannot process incomplete now-playing metadata", true);
        return;
    }

    const python = process.env.TAGSLUT_PYTHON || "python3";
    const args = [
        path.join(__dirname, "bridge.py"),
        "--title",
        metadata.title,
        "--artist",
        metadata.artist,
    ];
    if (metadata.album) {
        args.push("--album", metadata.album);
    }
    if (execute) {
        args.push("--execute");
    }

    svc_status.set_status(`${execute ? "Applying" : "Previewing"}: ${metadata.title}`, false);
    const child = spawn(python, args, {
        cwd: path.dirname(__dirname),
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
    });

    child.stdout.on("data", (data) => process.stdout.write(`[Cuecifer] ${data}`));
    child.stderr.on("data", (data) => process.stderr.write(`[Cuecifer] ${data}`));
    child.on("error", (error) => {
        svc_status.set_status(`Cuecifer launch failed: ${error.message}`, true);
    });
    child.on("close", (code) => {
        if (code === 0) {
            svc_status.set_status(`${execute ? "Applied" : "Preview complete"}: ${metadata.title}`, false);
        } else {
            svc_status.set_status(`Cuecifer failed with exit code ${code}`, true);
        }
    });
}

svc_status.set_status("Waiting for Roon Core", false);
roon.start_discovery();
