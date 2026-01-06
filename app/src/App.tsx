import { useState, useEffect } from "react";
import { SimulatorPage } from "./pages/SimulatorPage";
import { LifeEventPage } from "./pages/LifeEventPage";
import { BrandPage } from "./pages/BrandPage";
import { BrandDesignPage } from "./pages/BrandDesignPage";
import { BrandWritingPage } from "./pages/BrandWritingPage";

type PageType = "simulator" | "life-event" | "brand" | "brand-design" | "brand-writing";

function App() {
  const [currentPage, setCurrentPage] = useState<PageType>("simulator");

  useEffect(() => {
    // Simple hash-based routing
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash === "#/life-event") {
        setCurrentPage("life-event");
      } else if (hash === "#/brand/design") {
        setCurrentPage("brand-design");
      } else if (hash === "#/brand/writing") {
        setCurrentPage("brand-writing");
      } else if (hash === "#/brand") {
        setCurrentPage("brand");
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

  if (currentPage === "brand") {
    return <BrandPage />;
  }

  if (currentPage === "brand-design") {
    return <BrandDesignPage />;
  }

  if (currentPage === "brand-writing") {
    return <BrandWritingPage />;
  }

  return <SimulatorPage />;
}

export default App;
