import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  compareWithdrawalStrategies,
  compareAnnuity,
  compareAllocations,
  optimizeRothConversions,
  compareSSTimings,
  runHistoricalBacktest,
  type HistoricalBacktestResult,
  type Holding,
  type RothOptimizationResult,
  type SimulationInput,
  type StrategyComparisonResult,
} from './api';
import { DEFAULT_PARAMS } from './constants';

describe('API Types', () => {
  describe('Holding', () => {
    it('should have correct structure for holding', () => {
      const holding: Holding = {
        account_type: 'traditional_401k',
        fund: 'vt',
        balance: 100000,
      };

      expect(holding.account_type).toBe('traditional_401k');
      expect(holding.fund).toBe('vt');
      expect(holding.balance).toBe(100000);
    });

    it('should support all account types', () => {
      const accountTypes: Holding['account_type'][] = [
        'traditional_401k',
        'traditional_ira',
        'roth_401k',
        'roth_ira',
        'taxable',
      ];

      accountTypes.forEach((type) => {
        const holding: Holding = {
          account_type: type,
          fund: 'vt',
          balance: 50000,
        };
        expect(holding.account_type).toBe(type);
      });
    });

    it('should support all fund types', () => {
      const fundTypes: Holding['fund'][] = ['vt', 'sp500', 'bnd', 'treasury'];

      fundTypes.forEach((fund) => {
        const holding: Holding = {
          account_type: 'taxable',
          fund,
          balance: 50000,
        };
        expect(holding.fund).toBe(fund);
      });
    });
  });

  describe('SimulationInput with holdings', () => {
    it('should support holdings field', () => {
      const input: SimulationInput = {
        ...DEFAULT_PARAMS,
        holdings: [
          {
            account_type: 'traditional_401k',
            fund: 'vt',
            balance: 300000,
          },
          {
            account_type: 'roth_ira',
            fund: 'sp500',
            balance: 100000,
          },
          {
            account_type: 'taxable',
            fund: 'bnd',
            balance: 50000,
          },
        ],
        withdrawal_strategy: 'taxable_first',
      };

      expect(input.holdings).toHaveLength(3);
      expect(input.holdings![0].account_type).toBe('traditional_401k');
      expect(input.holdings![1].fund).toBe('sp500');
      expect(input.holdings![2].balance).toBe(50000);
      expect(input.withdrawal_strategy).toBe('taxable_first');
    });

    it('should support all withdrawal strategies', () => {
      const strategies: Array<SimulationInput['withdrawal_strategy']> = [
        'traditional_first',
        'roth_first',
        'taxable_first',
        'pro_rata',
      ];

      strategies.forEach((strategy) => {
        const input: Partial<SimulationInput> = {
          withdrawal_strategy: strategy,
        };
        expect(input.withdrawal_strategy).toBe(strategy);
      });
    });

    it('should allow holdings to be optional for backward compatibility', () => {
      const input: SimulationInput = {
        ...DEFAULT_PARAMS,
        initial_capital: 500000,
        withdrawal_strategy: 'taxable_first',
      };

      expect(input.holdings).toBeUndefined();
      expect(input.initial_capital).toBe(500000);
    });

    it('should allow mixed account types in holdings', () => {
      const input: Partial<SimulationInput> = {
        holdings: [
          { account_type: 'traditional_401k', fund: 'vt', balance: 200000 },
          { account_type: 'roth_ira', fund: 'sp500', balance: 100000 },
          { account_type: 'taxable', fund: 'bnd', balance: 50000 },
        ],
      };

      const traditionaAccounts = input.holdings!.filter(
        (h) => h.account_type === 'traditional_401k' || h.account_type === 'traditional_ira'
      );
      const rothAccounts = input.holdings!.filter(
        (h) => h.account_type === 'roth_401k' || h.account_type === 'roth_ira'
      );
      const taxableAccounts = input.holdings!.filter((h) => h.account_type === 'taxable');

      expect(traditionaAccounts).toHaveLength(1);
      expect(rothAccounts).toHaveLength(1);
      expect(taxableAccounts).toHaveLength(1);
    });
  });
});

describe('runHistoricalBacktest', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('posts the base simulation input and selected start years', async () => {
    const mockResult: HistoricalBacktestResult = {
      horizon_years: 30,
      start_years: [1966, 1973],
      results: [
        {
          start_year: 1966,
          success: true,
          final_value: 650000,
          final_value_real: 320000,
          total_withdrawn: 1800000,
          total_taxes: 240000,
          failure_age: null,
        },
        {
          start_year: 1973,
          success: false,
          final_value: 0,
          final_value_real: 0,
          total_withdrawn: 1200000,
          total_taxes: 180000,
          failure_age: 87,
        },
      ],
      success_rate: 0.5,
      median_final_value: 325000,
      median_final_value_real: 160000,
      total_withdrawn_median: 1500000,
      total_taxes_median: 210000,
      strongest_start_year: 1966,
      weakest_start_year: 1973,
      median_path: [500000, 520000, 510000],
      median_path_real: [500000, 500000, 470000],
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await runHistoricalBacktest(DEFAULT_PARAMS, [1966, 1973]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/backtest/historical'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          base_input: DEFAULT_PARAMS,
          start_years: [1966, 1973],
        }),
      }),
    );
    expect(result).toEqual(mockResult);
  });
});

describe('compareWithdrawalStrategies', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('posts the base simulation input to the strategy comparison endpoint', async () => {
    const mockResult: StrategyComparisonResult = {
      results: [
        {
          strategy: 'taxable_first',
          monte_carlo: {
            success_rate: 0.92,
            median_final_value: 950000,
            median_final_value_real: 420000,
            total_taxes_median: 210000,
            total_withdrawn_median: 1500000,
          },
          historical: {
            success_rate: 0.78,
            median_final_value: 650000,
            median_final_value_real: 260000,
            total_taxes_median: 205000,
            total_withdrawn_median: 1490000,
            cohort_count: 42,
            strongest_start_year: 1982,
            weakest_start_year: 1966,
            worst_final_value_real: 80000,
          },
          blended_score: 82.4,
        },
      ],
      top_scoring_strategy: 'taxable_first',
      lowest_modeled_tax_strategy: 'taxable_first',
      strongest_historical_strategy: 'taxable_first',
      summary:
        'Taxable first leads this scorecard after weighting Monte Carlo success at 35%, historical success at 35%, weakest historical cohort at 15%, median real ending wealth at 10%, and lower modeled taxes at 5%.',
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await compareWithdrawalStrategies(DEFAULT_PARAMS, ['taxable_first', 'pro_rata']);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/compare-withdrawal-strategies'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          base_input: DEFAULT_PARAMS,
          strategies: ['taxable_first', 'pro_rata'],
        }),
      }),
    );
    expect(result).toEqual(mockResult);
  });
});

describe('compareAnnuity', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('returns the neutral annuity comparison payload', async () => {
    const mockResult = {
      simulation_result: {
        success_rate: 0.91,
      },
      annuity_total_guaranteed: 360000,
      probability_simulation_beats_annuity: 0.64,
      simulation_median_total_income: 415000,
      summary: 'The portfolio path exceeds the annuity in a high share of modeled outcomes while keeping depletion risk relatively low.',
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await compareAnnuity(DEFAULT_PARAMS, 1500, 20);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/compare-annuity'),
      expect.objectContaining({
        method: 'POST',
      }),
    );
    expect(result).toEqual(mockResult);
  });
});

describe('optimizeRothConversions', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('posts the base simulation input to the Roth optimization endpoint', async () => {
    const baseInput: SimulationInput = {
      ...DEFAULT_PARAMS,
      holdings: [
        { account_type: 'taxable', fund: 'sp500', balance: 300000, cost_basis: 250000 },
        { account_type: 'traditional_401k', fund: 'treasury', balance: 700000 },
      ],
      withdrawal_strategy: 'taxable_first',
    };
    const mockResult: RothOptimizationResult = {
      results: [
        {
          conversion_policy: 'fill_12_percent_bracket',
          scenario_label: 'Fill 12% bracket (ages 60-64)',
          annual_conversion_amount: null,
          conversion_start_age: 60,
          conversion_end_age: 64,
          monte_carlo: {
            success_rate: 0.92,
            median_final_value: 950000,
            median_final_value_real: 420000,
            total_taxes_median: 210000,
            total_withdrawn_median: 1500000,
            total_medicare_premiums_median: 14000,
            total_roth_conversions_median: 200000,
            year_breakdown: [],
          },
          historical: {
            success_rate: 0.78,
            median_final_value: 650000,
            median_final_value_real: 260000,
            total_taxes_median: 205000,
            total_withdrawn_median: 1490000,
            total_medicare_premiums_median: 13200,
            total_roth_conversions_median: 200000,
            cohort_count: 42,
            strongest_start_year: 1982,
            weakest_start_year: 1966,
            worst_final_value_real: 80000,
          },
          blended_score: 82.4,
          delta_vs_baseline: {
            blended_score_delta: 6.1,
            monte_carlo_success_rate_delta: 0.02,
            historical_success_rate_delta: 0.03,
            monte_carlo_median_final_value_real_delta: 40000,
            historical_median_final_value_real_delta: 30000,
            monte_carlo_total_taxes_median_delta: 15000,
            monte_carlo_total_medicare_premiums_median_delta: 2200,
            monte_carlo_total_roth_conversions_median_delta: 200000,
            historical_total_medicare_premiums_median_delta: 1800,
            historical_worst_final_value_real_delta: 12000,
          },
        },
      ],
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
      metadata: {
        engine_version: '0.1.0',
        method_version: '2026-04-08',
        random_seed: 20260408,
        assumptions_summary: 'bootstrap returns, historical inflation, real spending, CA / single',
      },
      summary: 'Fill 12% bracket (ages 60-64) is the current score leader.',
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await optimizeRothConversions(baseInput, {
      candidateStartAges: [60, 65],
      windowLengths: [5, 10],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/optimize-roth-conversions'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          base_input: baseInput,
          candidate_start_ages: [60, 65],
          window_lengths: [5, 10],
        }),
      }),
    );
    expect(result).toEqual(mockResult);
  });
});

describe('compareAllocations', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('returns the neutral allocation comparison payload', async () => {
    const mockResult = {
      results: [],
      highest_success_allocation: 0.8,
      highest_safety_allocation: 0.6,
      summary: '80% stocks delivers the highest modeled success, while 60% stocks shows the lowest volatility among the stronger outcomes.',
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await compareAllocations(DEFAULT_PARAMS, [0.6, 0.8]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/compare-allocations'),
      expect.objectContaining({
        method: 'POST',
      }),
    );
    expect(result).toEqual(mockResult);
  });
});

describe('compareSSTimings', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('returns the neutral SS timing payload', async () => {
    const mockResult = {
      birth_year: 1960,
      full_retirement_age: 67,
      pia_monthly: 2000,
      results: [],
      highest_success_claiming_age: 70,
      highest_lifetime_income_claiming_age: 70,
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });

    const result = await compareSSTimings(DEFAULT_PARAMS, 1960, 2000, [62, 67, 70]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/compare-ss-timing'),
      expect.objectContaining({
        method: 'POST',
      }),
    );
    expect(result).toEqual(mockResult);
  });
});
