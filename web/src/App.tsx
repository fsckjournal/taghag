import type { CSSProperties } from "react";

const appName = import.meta.env.VITE_TAGHAG_APP_NAME ?? "Taghag";

const cardStyle: CSSProperties = {
  background: "rgba(15, 23, 42, 0.74)",
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 18,
  padding: 20,
  boxShadow: "0 20px 60px rgba(2, 6, 23, 0.28)",
  backdropFilter: "blur(16px)",
};

const tableRows = [
  { title: "Basement Pressure", artist: "Rhea", bpm: 132, key: "Am", tags: "Peak Time" },
  { title: "Velvet Loop", artist: "Nox", bpm: 124, key: "F#m", tags: "Warmup" },
  { title: "Chrome Signal", artist: "Tariq", bpm: 128, key: "Dm", tags: "House" },
];

export function App() {
  return (
    <div
      style={{
        minHeight: "100vh",
        color: "#e2e8f0",
        background:
          "radial-gradient(circle at top left, rgba(251, 191, 36, 0.28), transparent 28%), radial-gradient(circle at top right, rgba(14, 165, 233, 0.24), transparent 32%), linear-gradient(180deg, #0f172a 0%, #111827 44%, #020617 100%)",
        fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 20px 56px" }}>
        <header style={{ display: "grid", gap: 16, marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              width: "fit-content",
              padding: "6px 10px",
              borderRadius: 999,
              background: "rgba(251, 191, 36, 0.14)",
              color: "#fde68a",
              letterSpacing: "0.08em",
              fontSize: 12,
              textTransform: "uppercase",
            }}
          >
            Private DJ Metadata Control Surface
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <h1 style={{ margin: 0, fontSize: "clamp(2rem, 5vw, 4rem)", lineHeight: 1 }}>{appName}</h1>
              <p style={{ margin: "10px 0 0", maxWidth: 680, color: "#cbd5e1", fontSize: 16 }}>
                Review import runs, inspect local MP3 metadata, shape crates, and keep tagging work private.
              </p>
            </div>
            <div style={{ ...cardStyle, minWidth: 240, display: "grid", gap: 10 }}>
              <strong style={{ fontSize: 14, color: "#f8fafc" }}>Current session</strong>
              <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                <span>Scope</span>
                <span>MP3 only</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                <span>Database</span>
                <span>Metadata only</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                <span>Frontend env</span>
                <span>{import.meta.env.VITE_TAGHAG_ENV ?? "local"}</span>
              </div>
            </div>
          </div>
        </header>

        <main style={{ display: "grid", gap: 20 }}>
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 20,
            }}
          >
            {[
              ["Import runs", "3 recent scans, 1 ready to load"],
              ["Library table", "842 tracks indexed, 17 warnings"],
              ["Crates", "12 focused working crates"],
              ["Dashboard charts", "Genre mix, BPM spread, decode health"],
            ].map(([title, copy]) => (
              <article key={title} style={cardStyle}>
                <div style={{ fontSize: 13, color: "#93c5fd", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Placeholder view
                </div>
                <h2 style={{ margin: "10px 0 8px", fontSize: 22 }}>{title}</h2>
                <p style={{ margin: 0, color: "#cbd5e1", lineHeight: 1.5 }}>{copy}</p>
              </article>
            ))}
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 20 }}>
            <article style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <h2 style={{ margin: 0, fontSize: 22 }}>Library table</h2>
                <span style={{ color: "#93c5fd", fontSize: 13 }}>Placeholder</span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ color: "#94a3b8", textAlign: "left", fontSize: 13 }}>
                      <th style={{ paddingBottom: 12 }}>Title</th>
                      <th style={{ paddingBottom: 12 }}>Artist</th>
                      <th style={{ paddingBottom: 12 }}>BPM</th>
                      <th style={{ paddingBottom: 12 }}>Key</th>
                      <th style={{ paddingBottom: 12 }}>Tags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((row) => (
                      <tr key={row.title} style={{ borderTop: "1px solid rgba(148, 163, 184, 0.14)" }}>
                        <td style={{ padding: "14px 0" }}>{row.title}</td>
                        <td style={{ color: "#cbd5e1" }}>{row.artist}</td>
                        <td style={{ color: "#cbd5e1" }}>{row.bpm}</td>
                        <td style={{ color: "#cbd5e1" }}>{row.key}</td>
                        <td>
                          <span
                            style={{
                              background: "rgba(14, 165, 233, 0.16)",
                              color: "#bae6fd",
                              padding: "6px 10px",
                              borderRadius: 999,
                              fontSize: 12,
                            }}
                          >
                            {row.tags}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <article style={{ ...cardStyle, display: "grid", gap: 18 }}>
              <div>
                <div style={{ color: "#93c5fd", fontSize: 13, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Track detail
                </div>
                <h2 style={{ margin: "10px 0 6px", fontSize: 24 }}>Basement Pressure</h2>
                <p style={{ margin: 0, color: "#cbd5e1" }}>Selected-track inspector placeholder for notes, evidence, and quality checks.</p>
              </div>
              <div style={{ display: "grid", gap: 10 }}>
                {[
                  ["Artist", "Rhea"],
                  ["Genre", "Techno"],
                  ["BPM", "132"],
                  ["Decode status", "Pass"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      paddingBottom: 8,
                      borderBottom: "1px solid rgba(148, 163, 184, 0.14)",
                    }}
                  >
                    <span style={{ color: "#94a3b8" }}>{label}</span>
                    <span>{value}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <article style={cardStyle}>
              <h2 style={{ margin: "0 0 12px", fontSize: 22 }}>Crates</h2>
              <p style={{ margin: "0 0 18px", color: "#cbd5e1" }}>Working crate placeholders for set prep and recovery workflows.</p>
              <div style={{ display: "grid", gap: 10 }}>
                {["Friday Warmup", "2AM Tools", "Afterhours Relief"].map((crate) => (
                  <div
                    key={crate}
                    style={{
                      padding: "12px 14px",
                      borderRadius: 14,
                      background: "rgba(30, 41, 59, 0.6)",
                      border: "1px solid rgba(148, 163, 184, 0.14)",
                    }}
                  >
                    {crate}
                  </div>
                ))}
              </div>
            </article>

            <article style={cardStyle}>
              <h2 style={{ margin: "0 0 12px", fontSize: 22 }}>Dashboard charts</h2>
              <p style={{ margin: "0 0 18px", color: "#cbd5e1" }}>Placeholder panels for genre balance, BPM distribution, and import quality trends.</p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 10,
                  alignItems: "end",
                  minHeight: 180,
                }}
              >
                {[42, 68, 51].map((height, index) => (
                  <div
                    key={height}
                    style={{
                      height: `${height * 2}px`,
                      borderRadius: "14px 14px 4px 4px",
                      background: index === 1 ? "#f59e0b" : "#38bdf8",
                      opacity: index === 1 ? 1 : 0.78,
                    }}
                  />
                ))}
              </div>
            </article>
          </section>
        </main>
      </div>
    </div>
  );
}
