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
    portfolioMode: "simple" | "detailed",
    holdings: Holding[],
    withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata",
  ) => Promise<void>;
  handleSimulateWithParams: (
    simParams: SimulationInput,
    simSpouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: "simple" | "detailed",
    holdings: Holding[],
    withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata",
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
    portfolioMode: "simple" | "detailed",
    holdings: Holding[],
    withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata",
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

  const handleSimulateWithParams = useCallback(async (
    simParams: SimulationInput,
    simSpouse: SpouseInput | undefined,
    annuity: AnnuityInput,
    portfolioMode: "simple" | "detailed",
    holdings: Holding[],
    withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata",
  ) => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: simParams.max_age - simParams.current_age });

    try {
      const fullParams = buildFullParams(simParams, simSpouse, annuity, portfolioMode, holdings, withdrawalStrategy);

      // Use streaming API with progress updates
      for await (const event of runSimulationWithProgress(fullParams)) {
        if (event.type === "progress") {
          setProgress({ currentYear: event.year, totalYears: event.total_years });
        } else if (event.type === "complete") {
          setResult(event.result);
        }
      }
      // Update URL with current params for sharing
      const urlString = buildUrlParams(simParams, simParams.has_spouse ? simSpouse : undefined);
      const newUrl = urlString ? `${window.location.pathname}?${urlString}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [buildFullParams]);

  const handleSimulate = useCallback(async (
    params: SimulationInput,
    spouse: SpouseInput,
    annuity: AnnuityInput,
    portfolioMode: "simple" | "detailed",
    holdings: Holding[],
    withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata",
  ) => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: params.max_age - params.current_age });

    try {
      const fullParams = buildFullParams(params, params.has_spouse ? spouse : undefined, annuity, portfolioMode, holdings, withdrawalStrategy);

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
        // Use streaming API with progress updates
        for await (const event of runSimulationWithProgress(fullParams)) {
          if (event.type === "progress") {
            setProgress({ currentYear: event.year, totalYears: event.total_years });
          } else if (event.type === "complete") {
            setResult(event.result);
          }
        }
      }
      // Update URL with current params for sharing
      const urlString = buildUrlParams(params, params.has_spouse ? spouse : undefined);
      const newUrl = urlString ? `${window.location.pathname}?${urlString}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [buildFullParams]);

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
