import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const appName = import.meta.env.VITE_TAGHAG_APP_NAME ?? "Taghag";

const navItems = [
  ["Dashboard", "/dashboard"],
  ["Imports", "/imports"],
  ["Library", "/library"],
  ["Crates", "/crates"],
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#f7f4ef",
        color: "#1d2528",
        fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <header
        style={{
          borderBottom: "1px solid #d8d2c8",
          background: "#fffaf2",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            maxWidth: 1280,
            margin: "0 auto",
            padding: "14px 20px",
            display: "flex",
            gap: 20,
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
          }}
        >
          <strong style={{ fontSize: 20 }}>{appName}</strong>
          <nav style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {navItems.map(([label, href]) => (
              <NavLink
                key={href}
                to={href}
                style={({ isActive }) => ({
                  color: isActive ? "#fffaf2" : "#314146",
                  background: isActive ? "#1f6f68" : "transparent",
                  border: "1px solid #b9c9c6",
                  borderRadius: 8,
                  padding: "8px 10px",
                  textDecoration: "none",
                  fontSize: 14,
                  fontWeight: 700,
                })}
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main style={{ maxWidth: 1280, margin: "0 auto", padding: "24px 20px 44px" }}>{children}</main>
    </div>
  );
}

