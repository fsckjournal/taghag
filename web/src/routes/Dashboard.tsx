import { useEffect, useState } from "react";
import { DashboardCards } from "../components/DashboardCards";
import { getDashboardCounts, type DashboardCounts } from "../lib/queries";

export function Dashboard() {
  const [counts, setCounts] = useState<DashboardCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardCounts().then(setCounts).catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "#9f351f" }}>{error}</p>;
  if (!counts) return <p style={{ color: "#66777b" }}>Loading dashboard...</p>;

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <h1 style={{ margin: 0, fontSize: 28 }}>Dashboard</h1>
      <DashboardCards counts={counts} />
      <section style={{ background: "#fff", border: "1px solid #d8d2c8", borderRadius: 8, padding: 16 }}>
        <h2 style={{ margin: "0 0 12px", fontSize: 18 }}>Provider Evidence</h2>
        {Object.keys(counts.evidenceStatuses).length === 0 ? (
          <p style={{ color: "#66777b", margin: 0 }}>No provider evidence found.</p>
        ) : (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {Object.entries(counts.evidenceStatuses).map(([status, value]) => (
              <span
                key={status}
                style={{ border: "1px solid #b9c9c6", borderRadius: 8, padding: "8px 10px", fontWeight: 700 }}
              >
                {status}: {value}
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

