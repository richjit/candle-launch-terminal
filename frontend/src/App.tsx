// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import UnifiedDashboard from "./pages/UnifiedDashboard";
import LaunchDetail from "./pages/LaunchDetail";
import NarrativeDetail from "./pages/NarrativeDetail";

export default function App() {
  return (
    <main className="min-h-screen overflow-y-auto p-6 bg-terminal-bg">
      <Routes>
        <Route path="/" element={<UnifiedDashboard />} />
        <Route path="/launch/:metric" element={<LaunchDetail />} />
        <Route path="/narrative/:name" element={<NarrativeDetail />} />
        <Route path="/pulse" element={<Navigate to="/" replace />} />
        <Route path="/launch" element={<Navigate to="/" replace />} />
        <Route path="/narrative" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  );
}
