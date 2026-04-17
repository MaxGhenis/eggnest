import { useState, useCallback, useEffect, useRef } from "react";
import {
  runSimulationWithProgress,
  runHistoricalBacktest,
  compareAnnuity,
  type SimulationInput,
  type SimulationResult,
  type HistoricalBacktestResult,
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
}

export interface UseSimulationReturn {
  result: SimulationResult | null;
  historicalBacktestResult: HistoricalBacktestResult | null;
  annuityResult: AnnuityComparisonResult | null;
  isLoading: boolean;
  isHistoricalBacktestLoading: boolean;
  error: unknown;
  historicalBacktestError: unknown;
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
  const [historicalBacktestResult, setHistoricalBacktestResult] = useState<HistoricalBacktestResult | null>(null);
  const [annuityResult, setAnnuityResult] = useState<AnnuityComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoricalBacktestLoading, setIsHistoricalBacktestLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [historicalBacktestError, setHistoricalBacktestError] = useState<unknown>(null);
  const [progress, setProgress] = useState<SimulationProgress>({ currentYear: 0, totalYears: 0 });
  const [selectedYearIndex, setSelectedYearIndex] = useState<number | null>(null);
  const backtestRequestIdRef = useRef(0);
  const backtestAbortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => backtestAbortControllerRef.current?.abort(), []);

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

  /** Clear any existing backtest work before starting a new simulation run. */
  const resetHistoricalBacktest = useCallback(() => {
    backtestAbortControllerRef.current?.abort();
    backtestRequestIdRef.current += 1;
    setHistoricalBacktestResult(null);
    setHistoricalBacktestError(null);
    setIsHistoricalBacktestLoading(false);
  }, []);

  /** Run historical cohort replay in the background once the Monte Carlo result is ready. */
  const startHistoricalBacktest = useCallback((fullParams: SimulationInput) => {
    backtestAbortControllerRef.current?.abort();

    const controller = new AbortController();
    const requestId = backtestRequestIdRef.current + 1;

    backtestAbortControllerRef.current = controller;
    backtestRequestIdRef.current = requestId;
    setHistoricalBacktestResult(null);
    setHistoricalBacktestError(null);
    setIsHistoricalBacktestLoading(true);

    void runHistoricalBacktest(fullParams, undefined, controller.signal)
      .then((backtestResult) => {
        if (backtestRequestIdRef.current !== requestId) {
          return;
        }
        setHistoricalBacktestResult(backtestResult);
      })
      .catch((err) => {
        if (controller.signal.aborted || backtestRequestIdRef.current !== requestId) {
          return;
        }
        setHistoricalBacktestError(err);
        setHistoricalBacktestResult(null);
      })
      .finally(() => {
        if (backtestRequestIdRef.current === requestId) {
          setIsHistoricalBacktestLoading(false);
        }
      });
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
    resetHistoricalBacktest();
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
        startHistoricalBacktest(fullParams);
      } else {
        await runStreaming(fullParams);
        startHistoricalBacktest(fullParams);
      }
      updateUrlForSharing(params, resolvedSpouse);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [resetHistoricalBacktest, runStreaming, startHistoricalBacktest]);

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
    resetHistoricalBacktest();
    setProgress({ currentYear: 0, totalYears: simParams.max_age - simParams.current_age });

    try {
      const fullParams = buildFullParams(simParams, simSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);
      await runStreaming(fullParams);
      startHistoricalBacktest(fullParams);
      updateUrlForSharing(simParams, simSpouse);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [resetHistoricalBacktest, runStreaming, startHistoricalBacktest]);

  return {
    result,
    historicalBacktestResult,
    annuityResult,
    isLoading,
    isHistoricalBacktestLoading,
    error,
    historicalBacktestError,
    progress,
    selectedYearIndex,
    setSelectedYearIndex,
    setError,
    setResult,
    handleSimulate,
    handleSimulateWithParams,
  };
}
