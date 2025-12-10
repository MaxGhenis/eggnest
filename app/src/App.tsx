import { useState, useEffect } from "react";
import { SimulatorPage } from "./pages/SimulatorPage";
import { LifeEventPage } from "./pages/LifeEventPage";

function App() {
  const [currentPage, setCurrentPage] = useState<"simulator" | "life-event">("simulator");

  useEffect(() => {
    // Simple hash-based routing
    const handleHashChange = () => {
      if (window.location.hash === "#/life-event") {
        setCurrentPage("life-event");
      } else {
        setCurrentPage("simulator");
      }
    };

    handleHashChange();
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  if (currentPage === "life-event") {
    return <LifeEventPage />;
  }

  return <SimulatorPage />;
}

export default App;
