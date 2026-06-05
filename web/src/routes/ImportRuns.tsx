import { useEffect, useState } from "react";
import { listImportRuns, type ImportRun } from "../lib/queries";

export function ImportRuns() {
  const [runs, setRuns] = useState<ImportRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listImportRuns().then(setRuns).catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "#9f351f" }}>{error}</p>;
  if (!runs) return <p style={{ color: "#66777b" }}>Loading import runs...</p>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 28 }}>Import Runs</h1>
      {runs.length === 0 ? (
        <p style={{ color: "#66777b" }}>No import runs found.</p>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {runs.map((run) => (
            <article key={run.id} style={{ background: "#fff", border: "1px solid #d8d2c8", borderRadius: 8, padding: 14 }}>
              <strong>{run.run_name || run.id}</strong>
              <div style={{ color: "#66777b", marginTop: 6 }}>
                {run.status} · {new Date(run.started_at).toLocaleString()}
              </div>
              <div style={{ color: "#66777b", marginTop: 6 }}>{run.source_root}</div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

