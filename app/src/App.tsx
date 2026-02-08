import { Routes, Route, Navigate } from "react-router-dom";
import { SimulatorPage } from "./pages/SimulatorPage";
import { LifeEventPage } from "./pages/LifeEventPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<SimulatorPage />} />
      <Route path="/life-event" element={<LifeEventPage />} />
      {/* Catch-all: redirect unknown paths to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
