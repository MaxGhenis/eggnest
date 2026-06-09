import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  useComparisons,
} from "./useComparisons";
import {
  compareAllocations,
  compareSSTimings,
  compareStates,
  type AllocationComparisonResult,
  type AnnuityInput,
  type SimulationInput,
  type SimulationResult,
  type SpouseInput,
  type SSTimingComparisonResult,
  type StateComparisonResult,
} from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    compareStates: vi.fn(),
    compareSSTimings: vi.fn(),
    compareAllocations: vi.fn(),
  };
});

const baseParams: SimulationInput = {
  initial_capital: 500000,
  annual_spending: 60000,
  home_value: 0,
  current_age: 65,
  max_age: 95,
  gender: "male",
  social_security_monthly: 2000,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
  state: "CA",
  filing_status: "single",
  has_spouse: false,
  has_annuity: false,
  n_simulations: 10000,
  include_mortality: true,
  expected_return: 0.07,
  return_volatility: 0.16,
  dividend_yield: 0.02,
  stock_allocation: 0.8,
};

const spouse: SpouseInput = {
  age: 63,
  gender: "female",
  social_security_monthly: 1500,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
};

const annuity: AnnuityInput = {
  monthly_payment: 0,
  annuity_type: "life_with_guarantee",
  guarantee_years: 10,
};

const simulationResult: SimulationResult = {
  success_rate: 0.9,
  median_final_value: 100000,
  mean_final_value: 110000,
  percentiles: {},
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 1000000,
  total_taxes_median: 100000,
  percentile_paths: {},
  year_breakdown: [],
  initial_withdrawal_rate: 0.04,
  prob_10_year_failure: 0.01,
};

const stateComparison: StateComparisonResult = {
  base_state: "CA",
  results: [
    {
      state: "TX",
      success_rate: 0.92,
      median_final_value: 120000,
      total_taxes_median: 80000,
      total_withdrawn_median: 1000000,
      net_after_tax_median: 920000,
    },
  ],
  tax_savings_vs_base: { TX: 20000 },
};

const ssTimingComparison: SSTimingComparisonResult = {
  birth_year: 1960,
  full_retirement_age: 67,
  pia_monthly: 2000,
  results: [],
  highest_success_claiming_age: 67,
  highest_lifetime_income_claiming_age: 70,
};

const allocationComparison: AllocationComparisonResult = {
  results: [],
  highest_success_allocation: 0.8,
  lowest_volatility_allocation: 0,
  comparison_summary: "summary",
};

function renderUseComparisons(overrides: Partial<Parameters<typeof useComparisons>[0]> = {}) {
  return renderHook((props: Partial<Parameters<typeof useComparisons>[0]>) => useComparisons({
    params: baseParams,
    spouse,
    annuity,
    portfolioMode: "simple",
    holdings: [],
    withdrawalStrategy: "taxable_first",
    result: simulationResult,
    setError: vi.fn(),
    ...props,
  }), { initialProps: overrides });
}

describe("useComparisons", () => {
  beforeEach(() => {
    vi.mocked(compareStates).mockReset();
    vi.mocked(compareSSTimings).mockReset();
    vi.mocked(compareAllocations).mockReset();
  });

  it("clears state comparison output when base simulation inputs change", async () => {
    vi.mocked(compareStates).mockResolvedValue(stateComparison);
    const { result, rerender } = renderUseComparisons();

    await act(async () => {
      await result.current.handleCompareStates(["TX"]);
    });

    expect(result.current.stateComparisonResult).toBe(stateComparison);

    rerender({
      params: {
        ...baseParams,
        annual_spending: 70000,
      },
    });

    await waitFor(() => {
      expect(result.current.stateComparisonResult).toBeNull();
    });
  });

  it("clears Social Security timing output when its assumptions change", async () => {
    vi.mocked(compareSSTimings).mockResolvedValue(ssTimingComparison);
    const { result } = renderUseComparisons();

    await act(async () => {
      await result.current.handleCompareSSTimings();
    });

    expect(result.current.ssTimingResult).toBe(ssTimingComparison);

    act(() => {
      result.current.setBirthYear(1961);
    });

    await waitFor(() => {
      expect(result.current.ssTimingResult).toBeNull();
    });
  });

  it("clears allocation output when the base simulation reruns", async () => {
    vi.mocked(compareAllocations).mockResolvedValue(allocationComparison);
    const { result, rerender } = renderUseComparisons();

    await act(async () => {
      await result.current.handleCompareAllocations();
    });

    expect(result.current.allocationResult).toBe(allocationComparison);

    rerender({
      result: {
        ...simulationResult,
      },
    });

    await waitFor(() => {
      expect(result.current.allocationResult).toBeNull();
    });
  });
});
