import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RothOptimizationResult, SimulationInput } from '../lib/api';
import { DEFAULT_ANNUITY, DEFAULT_PARAMS, DEFAULT_SPOUSE } from '../lib/constants';
import { useComparisons } from './useComparisons';

const apiMocks = vi.hoisted(() => ({
  optimizeRothConversions: vi.fn(),
}));

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {
    ...actual,
    optimizeRothConversions: apiMocks.optimizeRothConversions,
  };
});

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

const rothOptimizationResult: RothOptimizationResult = {
  results: [],
  baseline_scenario_label: 'No annual conversion',
  baseline_conversion_amount: 0,
  top_scoring_scenario_label: 'Fill 12% bracket (ages 60-64)',
  top_scoring_conversion_amount: null,
  lowest_modeled_tax_scenario_label: 'No annual conversion',
  lowest_modeled_tax_amount: 0,
  strongest_historical_scenario_label: 'Fill 12% bracket (ages 60-64)',
  strongest_historical_conversion_amount: null,
  candidate_count: 9,
  candidate_start_ages: [60, 65],
  window_lengths: [5, 10],
  lowest_medicare_premium_scenario_label: 'No annual conversion',
  lowest_medicare_premium_conversion_amount: 0,
  highest_real_ending_wealth_scenario_label: 'Fill 12% bracket (ages 60-64)',
  highest_real_ending_wealth_conversion_amount: null,
  summary: 'Fill 12% bracket (ages 60-64) is the current score leader.',
};

const detailedParams: SimulationInput = {
  ...DEFAULT_PARAMS,
  holdings: [
    { account_type: 'taxable', fund: 'sp500', balance: 250000, cost_basis: 180000 },
    { account_type: 'traditional_ira', fund: 'treasury', balance: 400000 },
  ],
  withdrawal_strategy: 'taxable_first',
};

describe('useComparisons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('drops stale Roth optimization results when the simulation changes mid-request', async () => {
    const deferred = createDeferred<RothOptimizationResult>();
    apiMocks.optimizeRothConversions.mockReturnValue(deferred.promise);

    const setError = vi.fn();
    const initialResult = { success_rate: 0.9 };
    const nextResult = { success_rate: 0.8 };

    const { result, rerender } = renderHook(
      (props: Parameters<typeof useComparisons>[0]) => useComparisons(props),
      {
        initialProps: {
          params: detailedParams,
          spouse: DEFAULT_SPOUSE,
          annuity: DEFAULT_ANNUITY,
          portfolioMode: 'detailed',
          holdings: detailedParams.holdings ?? [],
          withdrawalStrategy: 'taxable_first',
          result: initialResult,
          setError,
        },
      }
    );

    let pendingOptimization!: Promise<void>;
    await act(async () => {
      pendingOptimization = result.current.handleOptimizeRoth();
    });

    expect(apiMocks.optimizeRothConversions).toHaveBeenCalledTimes(1);
    expect(result.current.isOptimizingRoth).toBe(true);

    rerender({
      params: detailedParams,
      spouse: DEFAULT_SPOUSE,
      annuity: DEFAULT_ANNUITY,
      portfolioMode: 'detailed',
      holdings: detailedParams.holdings ?? [],
      withdrawalStrategy: 'taxable_first',
      result: nextResult,
      setError,
    });

    await act(async () => {
      deferred.resolve(rothOptimizationResult);
      await pendingOptimization;
    });

    await waitFor(() => {
      expect(result.current.isOptimizingRoth).toBe(false);
    });
    expect(result.current.rothOptimizationResult).toBeNull();
    expect(setError).not.toHaveBeenCalled();
  });
});
