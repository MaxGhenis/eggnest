import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  normalizeApiUrl,
  runSimulation,
  runSimulationWithProgress,
  type Holding,
  type SimulationInput,
  type SimulationResult,
} from './api';

const baseSimulationInput: SimulationInput = {
  initial_capital: 500000,
  annual_spending: 40000,
  current_age: 65,
  max_age: 95,
  gender: 'male',
  state: 'CA',
  filing_status: 'single',
  has_spouse: false,
  has_annuity: false,
  n_simulations: 100,
  include_mortality: false,
  expected_return: 0.07,
  return_volatility: 0.16,
  dividend_yield: 0.02,
  stock_allocation: 0.8,
  social_security_monthly: 0,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
  home_value: 0,
  withdrawal_strategy: 'taxable_first',
};

const simulationResult: SimulationResult = {
  success_rate: 0.95,
  median_final_value: 750000,
  mean_final_value: 800000,
  percentiles: { p5: 0, p25: 400000, p50: 750000, p75: 1000000, p95: 1500000 },
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 900000,
  total_taxes_median: 120000,
  percentile_paths: { p50: [500000, 520000] },
  year_breakdown: [],
  initial_withdrawal_rate: 8,
  prob_10_year_failure: 0.02,
};

describe('normalizeApiUrl', () => {
  it('trims deployment environment whitespace and trailing slashes', () => {
    expect(normalizeApiUrl('https://policyengine--eggnest-api-fastapi-app.modal.run\n')).toBe(
      'https://policyengine--eggnest-api-fastapi-app.modal.run'
    );
    expect(normalizeApiUrl('http://localhost:8000///')).toBe('http://localhost:8000');
  });
});

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
        annual_spending: 60000,
        current_age: 65,
        max_age: 95,
        gender: 'male',
        state: 'CA',
        filing_status: 'single',
        has_spouse: false,
        has_annuity: false,
        n_simulations: 10000,
        include_mortality: true,
        expected_return: 0.07,
        return_volatility: 0.16,
        dividend_yield: 0.02,
        stock_allocation: 0.8,
        social_security_monthly: 2000,
        social_security_start_age: 67,
        pension_annual: 0,
        employment_income: 0,
        employment_growth_rate: 0.03,
        retirement_age: 65,
        home_value: 0,
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
        initial_capital: 500000,
        annual_spending: 60000,
        current_age: 65,
        max_age: 95,
        gender: 'male',
        state: 'CA',
        filing_status: 'single',
        has_spouse: false,
        has_annuity: false,
        n_simulations: 10000,
        include_mortality: true,
        expected_return: 0.07,
        return_volatility: 0.16,
        dividend_yield: 0.02,
        stock_allocation: 0.8,
        social_security_monthly: 2000,
        social_security_start_age: 67,
        pension_annual: 0,
        employment_income: 0,
        employment_growth_rate: 0.03,
        retirement_age: 65,
        home_value: 0,
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

describe('runSimulation', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts a US core scenario and unwraps the result payload', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ outputs: { us_simulation_result: simulationResult } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(runSimulation(baseSimulationInput)).resolves.toMatchObject({
      success_rate: 0.95,
      median_final_value: 750000,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/core/simulate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          schema_version: 'eggnest.scenario.v1',
          engine: 'us_retirement',
          country: 'USA',
          inputs: baseSimulationInput,
        }),
      })
    );
  });
});

describe('runSimulationWithProgress', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts a pollable simulation job and yields progress plus result', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        job_id: 'job-1',
        status: 'succeeded',
        current_year: 30,
        total_years: 30,
        progress: 1,
        message: 'Complete',
        result: simulationResult,
        error: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:01Z',
        completed_at: '2026-01-01T00:00:01Z',
      }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const events: unknown[] = [];
    for await (const event of runSimulationWithProgress(baseSimulationInput)) {
      events.push(event);
    }

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/simulate/jobs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(baseSimulationInput),
      })
    );
    expect(events).toEqual([
      {
        type: 'progress',
        year: 30,
        total_years: 30,
        progress: 1,
        message: 'Complete',
      },
      { type: 'complete', result: simulationResult },
    ]);
  });
});
