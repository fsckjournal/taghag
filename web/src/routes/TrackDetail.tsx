import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTrackDetail, type LibraryTrack } from "../lib/queries";

export function TrackDetail() {
  const { id } = useParams();
  const [track, setTrack] = useState<LibraryTrack | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getTrackDetail(id).then(setTrack).catch((err: Error) => setError(err.message));
  }, [id]);

  if (error) return <p style={{ color: "#9f351f" }}>{error}</p>;
  if (track === undefined) return <p style={{ color: "#66777b" }}>Loading track...</p>;
  if (track === null) return <p style={{ color: "#66777b" }}>Track not found.</p>;

  const rows = [
    ["Filename", track.file.filename],
    ["Path", track.file.path],
    ["Artist", track.tag?.artist ?? ""],
    ["Title", track.tag?.title ?? ""],
    ["Label", track.tag?.label ?? ""],
    ["BPM", track.tag?.bpm ?? ""],
    ["Key", track.tag?.musical_key ?? ""],
    ["Genre", track.tag?.canonical_genre ?? ""],
    ["Subgenre", track.tag?.canonical_subgenre ?? ""],
    ["Evidence", track.latestEvidence?.status ?? "none"],
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Link to="/library" style={{ color: "#1f6f68", fontWeight: 700 }}>
        Library
      </Link>
      <h1 style={{ margin: 0, fontSize: 28 }}>{track.tag?.title || track.file.filename}</h1>
      <section style={{ background: "#fff", border: "1px solid #d8d2c8", borderRadius: 8 }}>
        {rows.map(([label, value]) => (
          <div
            key={label}
            style={{
              display: "grid",
              gridTemplateColumns: "160px 1fr",
              gap: 12,
              padding: "11px 14px",
              borderTop: label === "Filename" ? "none" : "1px solid #ece5da",
            }}
          >
            <strong style={{ color: "#66777b" }}>{label}</strong>
            <span style={{ minWidth: 0, overflowWrap: "anywhere" }}>{value}</span>
          </div>
        ))}
      </section>
    </div>
  );
}

