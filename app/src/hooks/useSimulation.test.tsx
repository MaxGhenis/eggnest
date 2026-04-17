import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { HistoricalBacktestResult, SimulationResult } from '../lib/api';
import { DEFAULT_ANNUITY, DEFAULT_PARAMS } from '../lib/constants';
import { useSimulation } from './useSimulation';

const apiMocks = vi.hoisted(() => ({
  runSimulationWithProgress: vi.fn(),
  runHistoricalBacktest: vi.fn(),
  compareAnnuity: vi.fn(),
}));

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {
    ...actual,
    runSimulationWithProgress: apiMocks.runSimulationWithProgress,
    runHistoricalBacktest: apiMocks.runHistoricalBacktest,
    compareAnnuity: apiMocks.compareAnnuity,
  };
});

const simulationResult: SimulationResult = {
  success_rate: 0.91,
  median_final_value: 950000,
  mean_final_value: 980000,
  median_final_value_real: 430000,
  mean_final_value_real: 460000,
  percentiles: { p5: 0, p50: 950000, p95: 1800000 },
  percentiles_real: { p5: 0, p50: 430000, p95: 880000 },
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 1500000,
  total_taxes_median: 210000,
  percentile_paths: { p5: [], p25: [], p50: [], p75: [], p95: [] },
  year_breakdown: [],
  initial_withdrawal_rate: 4.2,
  prob_10_year_failure: 0.07,
};

const historicalBacktestResult: HistoricalBacktestResult = {
  horizon_years: 30,
  start_years: [1966, 1973, 2000, 2008],
  results: [],
  success_rate: 0.75,
  median_final_value: 700000,
  median_final_value_real: 300000,
  total_withdrawn_median: 1475000,
  total_taxes_median: 205000,
  strongest_start_year: 2008,
  weakest_start_year: 1966,
  median_path: [500000, 520000],
  median_path_real: [500000, 490000],
};

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

describe('useSimulation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts historical replay after the streamed simulation completes', async () => {
    const backtestDeferred = createDeferred<HistoricalBacktestResult>();

    apiMocks.runSimulationWithProgress.mockImplementation(async function* () {
      yield { type: 'progress', year: 1, total_years: 30 };
      yield { type: 'complete', result: simulationResult };
    });
    apiMocks.runHistoricalBacktest.mockReturnValue(backtestDeferred.promise);

    const { result } = renderHook(() => useSimulation());

    await act(async () => {
      await result.current.handleSimulateWithParams(
        DEFAULT_PARAMS,
        undefined,
        DEFAULT_ANNUITY,
        'simple',
        [],
        'taxable_first',
      );
    });

    expect(apiMocks.runHistoricalBacktest).toHaveBeenCalledTimes(1);
    expect(result.current.result).toEqual(simulationResult);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isHistoricalBacktestLoading).toBe(true);

    await act(async () => {
      backtestDeferred.resolve(historicalBacktestResult);
      await backtestDeferred.promise;
    });

    await waitFor(() => {
      expect(result.current.historicalBacktestResult).toEqual(historicalBacktestResult);
    });
    expect(result.current.historicalBacktestError).toBeNull();
    expect(result.current.isHistoricalBacktestLoading).toBe(false);
  });
});
