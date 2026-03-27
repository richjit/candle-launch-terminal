// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import Pulse from "./pages/Pulse";

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/pulse" replace />} />
          <Route path="/pulse" element={<Pulse />} />
        </Routes>
      </main>
    </div>
  );
}
