// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import Pulse from "./pages/Pulse";
import LaunchDashboard from "./pages/LaunchDashboard";
import LaunchDetail from "./pages/LaunchDetail";

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/pulse" replace />} />
          <Route path="/pulse" element={<Pulse />} />
          <Route path="/launch" element={<LaunchDashboard />} />
          <Route path="/launch/:metric" element={<LaunchDetail />} />
        </Routes>
      </main>
    </div>
  );
}
