"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useScenarios, type UseScenariosReturn } from "../hooks/useScenarios";
import { useSimulationContext } from "./SimulationContext";
import { usePortfolioContext } from "./PortfolioContext";

const ScenarioContext = createContext<UseScenariosReturn | null>(null);

export function useScenarioContext(): UseScenariosReturn {
  const ctx = useContext(ScenarioContext);
  if (!ctx) throw new Error("useScenarioContext must be used within ScenarioProvider");
  return ctx;
}

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const { params, spouse, annuity, setParams, setSpouse, setAnnuity, setShowPersonaPicker } = useSimulationContext();
  const { portfolioMode, holdings, withdrawalStrategy, setPortfolioMode, setHoldings, setWithdrawalStrategy } = usePortfolioContext();

  const scenarios = useScenarios({
    params, spouse, annuity,
    portfolioMode, holdings, withdrawalStrategy,
    setParams, setSpouse, setAnnuity,
    setPortfolioMode, setHoldings, setWithdrawalStrategy,
    setShowPersonaPicker,
  });

  return (
    <ScenarioContext.Provider value={scenarios}>
      {children}
    </ScenarioContext.Provider>
  );
}
