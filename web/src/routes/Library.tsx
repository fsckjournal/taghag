import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { LibraryTable } from "../components/LibraryTable";
import { listLibraryTracks, type LibraryTrack } from "../lib/queries";

export function Library() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tracks, setTracks] = useState<LibraryTrack[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const filters = useMemo(
    () => ({
      genre: searchParams.get("genre"),
      key: searchParams.get("key"),
      quality: searchParams.get("quality"),
      providerStatus: searchParams.get("providerStatus"),
      bpmMin: searchParams.get("bpmMin") ? Number(searchParams.get("bpmMin")) : null,
      bpmMax: searchParams.get("bpmMax") ? Number(searchParams.get("bpmMax")) : null,
    }),
    [searchParams],
  );

  useEffect(() => {
    listLibraryTracks(filters).then(setTracks).catch((err: Error) => setError(err.message));
  }, [filters]);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0, fontSize: 28 }}>Library</h1>
        <button
          type="button"
          onClick={() => setSearchParams({})}
          style={{ border: "1px solid #b9c9c6", borderRadius: 8, background: "#fff", padding: "8px 10px" }}
        >
          Clear
        </button>
      </div>
      {error && <p style={{ color: "#9f351f" }}>{error}</p>}
      {!error && !tracks && <p style={{ color: "#66777b" }}>Loading library...</p>}
      {tracks && <LibraryTable tracks={tracks} />}
    </div>
  );
}

