import { describe, it, expect } from 'vitest';
import type { Holding, SimulationInput } from './api';

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
