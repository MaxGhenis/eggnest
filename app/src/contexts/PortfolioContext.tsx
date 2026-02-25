"use client";

import { createContext, useContext, type ReactNode } from "react";
import { usePortfolio, type UsePortfolioReturn } from "../hooks/usePortfolio";

const PortfolioContext = createContext<UsePortfolioReturn | null>(null);

export function usePortfolioContext(): UsePortfolioReturn {
  const ctx = useContext(PortfolioContext);
  if (!ctx) throw new Error("usePortfolioContext must be used within PortfolioProvider");
  return ctx;
}

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const portfolio = usePortfolio();

  return (
    <PortfolioContext.Provider value={portfolio}>
      {children}
    </PortfolioContext.Provider>
  );
}
