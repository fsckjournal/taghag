import type { DashboardCounts } from "../lib/queries";

const labels: Array<[keyof DashboardCounts, string]> = [
  ["totalFlacs", "FLACs"],
  ["missingArtistTitle", "Missing artist/title"],
  ["missingBpmKey", "Missing BPM/key"],
  ["missingGenreSubgenre", "Missing genre/subgenre"],
  ["missingLabel", "Missing label"],
  ["duplicateChecksumCandidates", "Duplicate candidates"],
];

export function DashboardCards({ counts }: { counts: DashboardCounts }) {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: 12,
      }}
    >
      {labels.map(([key, label]) => (
        <article
          key={key}
          style={{
            background: "#ffffff",
            border: "1px solid #d8d2c8",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div style={{ color: "#66777b", fontSize: 13, fontWeight: 700 }}>{label}</div>
          <div style={{ color: "#1f6f68", fontSize: 30, fontWeight: 800, marginTop: 8 }}>
            {String(counts[key])}
          </div>
        </article>
      ))}
    </section>
  );
}

