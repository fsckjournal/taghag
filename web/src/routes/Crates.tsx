import { useEffect, useState } from "react";
import { listCrates, type Crate } from "../lib/queries";

export function Crates() {
  const [crates, setCrates] = useState<Crate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCrates().then(setCrates).catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "#9f351f" }}>{error}</p>;
  if (!crates) return <p style={{ color: "#66777b" }}>Loading crates...</p>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 28 }}>Crates</h1>
      {crates.length === 0 ? (
        <p style={{ color: "#66777b" }}>No crates found.</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {crates.map((crate) => (
            <article key={crate.id} style={{ background: "#fff", border: "1px solid #d8d2c8", borderRadius: 8, padding: 14 }}>
              <strong>{crate.name}</strong>
              <p style={{ color: "#66777b", margin: "8px 0 0" }}>{crate.description}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

