import { useState, useCallback } from "react";
import {
  runSimulationWithProgress,
  compareAnnuity,
  type SimulationInput,
  type SimulationResult,
  type SpouseInput,
  type AnnuityInput,
  type Holding,
} from "../lib/api";
import type { AnnuityComparisonResult } from "../lib/simulatorUtils";
import { buildUrlParams } from "../lib/simulatorUtils";
import type { PortfolioMode, WithdrawalStrategy } from "./usePortfolio";

export interface SimulationProgress {
  currentYear: number;
  totalYears: number;
}

export interface UseSimulationReturn {
  result: SimulationResult | null;
  annuityResult: AnnuityComparisonResult | null;
  isLoading: boolean;
  error: unknown;
  progress: SimulationProgress;
  selectedYearIndex: number | null;
  setSelectedYearIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setError: React.Dispatch<React.SetStateAction<unknown>>;
  setResult: React.Dispatch<React.SetStateAction<SimulationResult | null>>;
  handleSimulate: (
    params: SimulationInput,
    spouse: SpouseInput,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => Promise<void>;
  handleSimulateWithParams: (
    simParams: SimulationInput,
    simSpouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => Promise<void>;
}

export function useSimulation(): UseSimulationReturn {
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [annuityResult, setAnnuityResult] = useState<AnnuityComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [progress, setProgress] = useState<SimulationProgress>({ currentYear: 0, totalYears: 0 });
  const [selectedYearIndex, setSelectedYearIndex] = useState<number | null>(null);

  const buildFullParams = useCallback((
    params: SimulationInput,
    spouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ): SimulationInput => {
    return {
      ...params,
      spouse: params.has_spouse ? spouse : undefined,
      annuity: params.has_annuity ? annuity : undefined,
      holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
      initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : params.initial_capital,
      withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
    };
  }, []);

  /** Stream simulation results, updating progress as events arrive. */
  const runStreaming = useCallback(async (fullParams: SimulationInput) => {
    for await (const event of runSimulationWithProgress(fullParams)) {
      if (event.type === "progress") {
        setProgress({ currentYear: event.year, totalYears: event.total_years });
      } else if (event.type === "complete") {
        setResult(event.result);
      }
    }
  }, []);

  /** Update the browser URL to reflect current simulation params (for sharing). */
  function updateUrlForSharing(params: SimulationInput, spouse: SpouseInput | undefined): void {
    const urlString = buildUrlParams(params, params.has_spouse ? spouse : undefined);
    const newUrl = urlString ? `${window.location.pathname}?${urlString}` : window.location.pathname;
    window.history.replaceState(null, "", newUrl);
  }

  const handleSimulate = useCallback(async (
    params: SimulationInput,
    spouse: SpouseInput,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: params.max_age - params.current_age });

    try {
      const resolvedSpouse = params.has_spouse ? spouse : undefined;
      const fullParams = buildFullParams(params, resolvedSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);

      if (params.has_annuity && annuity.monthly_payment > 0) {
        // Annuity comparison doesn't support streaming yet, use regular API
        const comparison = await compareAnnuity(
          fullParams,
          annuity.monthly_payment,
          annuity.guarantee_years
        );
        setResult(comparison.simulation_result);
        setAnnuityResult(comparison);
      } else {
        await runStreaming(fullParams);
      }
      updateUrlForSharing(params, resolvedSpouse);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [buildFullParams, runStreaming]);

  const handleSimulateWithParams = useCallback(async (
    simParams: SimulationInput,
    simSpouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: simParams.max_age - simParams.current_age });

    try {
      const fullParams = buildFullParams(simParams, simSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);
      await runStreaming(fullParams);
      updateUrlForSharing(simParams, simSpouse);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [buildFullParams, runStreaming]);

  return {
    result,
    annuityResult,
    isLoading,
    error,
    progress,
    selectedYearIndex,
    setSelectedYearIndex,
    setError,
    setResult,
    handleSimulate,
    handleSimulateWithParams,
  };
}
