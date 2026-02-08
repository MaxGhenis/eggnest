import { useState } from "react";
import type { Holding } from "../lib/api";

export type WithdrawalStrategy = "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
export type PortfolioMode = "simple" | "detailed";

export interface UsePortfolioReturn {
  portfolioMode: PortfolioMode;
  setPortfolioMode: React.Dispatch<React.SetStateAction<PortfolioMode>>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  withdrawalStrategy: WithdrawalStrategy;
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<WithdrawalStrategy>>;
}

export function usePortfolio(): UsePortfolioReturn {
  const [portfolioMode, setPortfolioMode] = useState<PortfolioMode>("simple");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [withdrawalStrategy, setWithdrawalStrategy] = useState<WithdrawalStrategy>("taxable_first");

  return {
    portfolioMode,
    setPortfolioMode,
    holdings,
    setHoldings,
    withdrawalStrategy,
    setWithdrawalStrategy,
  };
}
