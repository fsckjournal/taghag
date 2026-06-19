import { Link } from "react-router-dom";
import type { LibraryTrack } from "../lib/queries";

function qualityLabel(track: LibraryTrack) {
  const issues = track.latestQuality?.issue_codes_json;
  return Array.isArray(issues) && issues.length > 0 ? `${issues.length} issues` : "Clear";
}

export function LibraryTable({ tracks }: { tracks: LibraryTrack[] }) {
  if (tracks.length === 0) {
    return <p style={{ color: "#66777b" }}>No audio rows found.</p>;
  }

  return (
    <div style={{ overflowX: "auto", border: "1px solid #d8d2c8", borderRadius: 8, background: "#fff" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 920 }}>
        <thead>
          <tr style={{ color: "#66777b", textAlign: "left", fontSize: 13, background: "#f1ece3" }}>
            {["Filename", "Artist", "Title", "Label", "BPM", "Key", "Genre", "Subgenre", "Quality", "Evidence"].map(
              (header) => (
                <th key={header} style={{ padding: "10px 12px", borderBottom: "1px solid #d8d2c8" }}>
                  {header}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {tracks.map((track) => (
            <tr key={track.file.id} style={{ borderTop: "1px solid #ece5da" }}>
              <td style={{ padding: "11px 12px", fontWeight: 700 }}>
                <Link to={`/tracks/${track.file.id}`} style={{ color: "#1f6f68" }}>
                  {track.file.filename}
                </Link>
              </td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.artist ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.title ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.label ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.bpm ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.musical_key ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.canonical_genre ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{track.tag?.canonical_subgenre ?? ""}</td>
              <td style={{ padding: "11px 12px" }}>{qualityLabel(track)}</td>
              <td style={{ padding: "11px 12px" }}>{track.latestEvidence?.status ?? "none"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

