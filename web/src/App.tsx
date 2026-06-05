import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Crates } from "./routes/Crates";
import { Dashboard } from "./routes/Dashboard";
import { ImportRuns } from "./routes/ImportRuns";
import { Library } from "./routes/Library";
import { TrackDetail } from "./routes/TrackDetail";

export function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/imports" element={<ImportRuns />} />
          <Route path="/library" element={<Library />} />
          <Route path="/tracks/:id" element={<TrackDetail />} />
          <Route path="/crates" element={<Crates />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

