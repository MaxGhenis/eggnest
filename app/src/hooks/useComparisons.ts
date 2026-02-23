import { useState, useCallback } from "react";
import {
  compareStates,
  compareSSTimings,
  compareAllocations,
  type SimulationInput,
  type SpouseInput,
  type AnnuityInput,
  type Holding,
  type StateComparisonResult,
  type SSTimingComparisonResult,
  type AllocationComparisonResult,
} from "../lib/api";
import { NO_TAX_STATES } from "../lib/constants";
import { buildFullParams } from "../lib/simulatorUtils";
import type { PortfolioMode, WithdrawalStrategy } from "./usePortfolio";

export interface UseComparisonsReturn {
  // State comparison
  stateComparisonResult: StateComparisonResult | null;
  isComparingStates: boolean;
  selectedCompareStates: string[];
  setSelectedCompareStates: React.Dispatch<React.SetStateAction<string[]>>;
  setStateComparisonResult: React.Dispatch<React.SetStateAction<StateComparisonResult | null>>;
  handleCompareStates: (statesToCompare?: string[]) => Promise<void>;
  toggleCompareState: (state: string) => void;

  // SS timing comparison
  ssTimingResult: SSTimingComparisonResult | null;
  isComparingSSTiming: boolean;
  birthYear: number;
  setBirthYear: React.Dispatch<React.SetStateAction<number>>;
  piaMonthly: number;
  setPiaMonthly: React.Dispatch<React.SetStateAction<number>>;
  setSSTimingResult: React.Dispatch<React.SetStateAction<SSTimingComparisonResult | null>>;
  handleCompareSSTimings: () => Promise<void>;

  // Allocation comparison
  allocationResult: AllocationComparisonResult | null;
  isComparingAllocations: boolean;
  setAllocationResult: React.Dispatch<React.SetStateAction<AllocationComparisonResult | null>>;
  handleCompareAllocations: () => Promise<void>;
}

interface ComparisonDeps {
  params: SimulationInput;
  spouse: SpouseInput;
  annuity: AnnuityInput;
  portfolioMode: PortfolioMode;
  holdings: Holding[];
  withdrawalStrategy: WithdrawalStrategy;
  result: unknown;
  setError: (err: unknown) => void;
}

export function useComparisons(deps: ComparisonDeps): UseComparisonsReturn {
  const { params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy, result, setError } = deps;

  // State comparison
  const [stateComparisonResult, setStateComparisonResult] = useState<StateComparisonResult | null>(null);
  const [isComparingStates, setIsComparingStates] = useState(false);
  const [selectedCompareStates, setSelectedCompareStates] = useState<string[]>([]);

  // SS timing comparison
  const [ssTimingResult, setSSTimingResult] = useState<SSTimingComparisonResult | null>(null);
  const [isComparingSSTiming, setIsComparingSSTiming] = useState(false);
  const [birthYear, setBirthYear] = useState<number>(1960);
  const [piaMonthly, setPiaMonthly] = useState<number>(2000);

  // Allocation comparison
  const [allocationResult, setAllocationResult] = useState<AllocationComparisonResult | null>(null);
  const [isComparingAllocations, setIsComparingAllocations] = useState(false);

  const getFullParams = useCallback(
    () => buildFullParams(params, params.has_spouse ? spouse : undefined, annuity, portfolioMode, holdings, withdrawalStrategy),
    [params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy],
  );

  const handleCompareStates = useCallback(async (statesToCompare?: string[]) => {
    if (!result) return;

    setIsComparingStates(true);
    setStateComparisonResult(null);

    try {
      const fullParams = getFullParams();

      // Use provided states, selected states, or default to no-tax states
      const states = statesToCompare ||
        (selectedCompareStates.length > 0 ? selectedCompareStates :
          NO_TAX_STATES.filter(s => s !== params.state).slice(0, 5));

      const comparison = await compareStates(fullParams, states);
      setStateComparisonResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingStates(false);
    }
  }, [result, params.state, selectedCompareStates, getFullParams, setError]);

  const toggleCompareState = useCallback((state: string) => {
    setSelectedCompareStates(prev =>
      prev.includes(state)
        ? prev.filter(s => s !== state)
        : prev.length < 5 ? [...prev, state] : prev
    );
  }, []);

  const handleCompareSSTimings = useCallback(async () => {
    if (!result) return;

    setIsComparingSSTiming(true);
    setSSTimingResult(null);

    try {
      const fullParams = getFullParams();

      const comparison = await compareSSTimings(
        fullParams,
        birthYear,
        piaMonthly
      );
      setSSTimingResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingSSTiming(false);
    }
  }, [result, birthYear, piaMonthly, getFullParams, setError]);

  const handleCompareAllocations = useCallback(async () => {
    if (!result) return;

    setIsComparingAllocations(true);
    setAllocationResult(null);

    try {
      const fullParams = getFullParams();

      const comparison = await compareAllocations(
        fullParams,
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
      );
      setAllocationResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingAllocations(false);
    }
  }, [result, getFullParams, setError]);

  return {
    stateComparisonResult,
    isComparingStates,
    selectedCompareStates,
    setSelectedCompareStates,
    setStateComparisonResult,
    handleCompareStates,
    toggleCompareState,

    ssTimingResult,
    isComparingSSTiming,
    birthYear,
    setBirthYear,
    piaMonthly,
    setPiaMonthly,
    setSSTimingResult,
    handleCompareSSTimings,

    allocationResult,
    isComparingAllocations,
    setAllocationResult,
    handleCompareAllocations,
  };
}
