import { useState, useCallback, useEffect, useRef } from "react";
import {
  runSimulationWithProgress,
  compareAnnuity,
  type SimulationInput,
  type SimulationResult,
  type YearProgressSummary,
  type SpouseInput,
  type AnnuityInput,
  type Holding,
} from "../lib/api";
import {
  buildUrlParams,
  buildFullParams,
  type AnnuityComparisonResult,
} from "../lib/simulatorUtils";
import type { PortfolioMode, WithdrawalStrategy } from "./usePortfolio";

export interface SimulationProgress {
  currentYear: number;
  totalYears: number;
  progress?: number;
  message?: string | null;
  yearSummary?: YearProgressSummary | null;
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

  // Each run owns an AbortController; starting a new run cancels the previous
  // one so a slow earlier run can never overwrite a newer result, and
  // unmounting cancels whatever is in flight.
  const runControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => runControllerRef.current?.abort();
  }, []);

  const beginRun = useCallback((): AbortController => {
    runControllerRef.current?.abort();
    const controller = new AbortController();
    runControllerRef.current = controller;
    return controller;
  }, []);

  /** Run the simulation (with annuity comparison when configured). */
  const executeRun = useCallback(async (
    fullParams: SimulationInput,
    annuity: AnnuityInput,
    controller: AbortController,
  ) => {
    const { signal } = controller;

    if (fullParams.has_annuity && annuity.monthly_payment > 0) {
      // Annuity comparison doesn't support streaming yet, use regular API
      const comparison = await compareAnnuity(
        fullParams,
        annuity.monthly_payment,
        annuity.guarantee_years,
        undefined,
        signal,
      );
      if (signal.aborted) return;
      setResult(comparison.simulation_result);
      setAnnuityResult(comparison);
      return;
    }

    for await (const event of runSimulationWithProgress(fullParams, undefined, signal)) {
      if (signal.aborted) return;
      if (event.type === "progress") {
        setProgress({
          currentYear: event.year,
          totalYears: event.total_years,
          progress: event.progress,
          message: event.message,
          yearSummary: event.year_summary,
        });
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

  const runSimulationFlow = useCallback(async (
    params: SimulationInput,
    spouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => {
    const controller = beginRun();
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: params.max_age - params.current_age });

    try {
      const fullParams = buildFullParams(params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy);
      await executeRun(fullParams, annuity, controller);
      if (!controller.signal.aborted) {
        updateUrlForSharing(params, spouse);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err);
        setResult(null);
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, [beginRun, executeRun]);

  const handleSimulate = useCallback(async (
    params: SimulationInput,
    spouse: SpouseInput,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => {
    const resolvedSpouse = params.has_spouse ? spouse : undefined;
    await runSimulationFlow(params, resolvedSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);
  }, [runSimulationFlow]);

  const handleSimulateWithParams = useCallback(async (
    simParams: SimulationInput,
    simSpouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: PortfolioMode,
    holdings: Holding[],
    withdrawalStrategy: WithdrawalStrategy,
  ) => {
    await runSimulationFlow(simParams, simSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);
  }, [runSimulationFlow]);

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
