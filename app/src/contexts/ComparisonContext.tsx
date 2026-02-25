"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useComparisons, type UseComparisonsReturn } from "../hooks/useComparisons";
import { useSimulationContext } from "./SimulationContext";
import { usePortfolioContext } from "./PortfolioContext";

const ComparisonContext = createContext<UseComparisonsReturn | null>(null);

export function useComparisonContext(): UseComparisonsReturn {
  const ctx = useContext(ComparisonContext);
  if (!ctx) throw new Error("useComparisonContext must be used within ComparisonProvider");
  return ctx;
}

export function ComparisonProvider({ children }: { children: ReactNode }) {
  const { params, spouse, annuity, simulation } = useSimulationContext();
  const { portfolioMode, holdings, withdrawalStrategy } = usePortfolioContext();

  const comparisons = useComparisons({
    params, spouse, annuity,
    portfolioMode, holdings, withdrawalStrategy,
    result: simulation.result,
    setError: simulation.setError,
  });

  return (
    <ComparisonContext.Provider value={comparisons}>
      {children}
    </ComparisonContext.Provider>
  );
}
