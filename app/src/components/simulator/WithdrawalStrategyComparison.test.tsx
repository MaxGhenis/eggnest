import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { StrategyComparisonResult } from '../../lib/api';
import { WithdrawalStrategyComparison } from './ComparisonPanel';

const strategyComparisonResult: StrategyComparisonResult = {
  results: [
    {
      strategy: 'taxable_first',
      monte_carlo: {
        success_rate: 0.93,
        median_final_value: 980000,
        median_final_value_real: 430000,
        total_taxes_median: 205000,
        total_withdrawn_median: 1500000,
      },
      historical: {
        success_rate: 0.8,
        median_final_value: 700000,
        median_final_value_real: 280000,
        total_taxes_median: 200000,
        total_withdrawn_median: 1485000,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1966,
        worst_final_value_real: 95000,
      },
      blended_score: 84.6,
    },
    {
      strategy: 'pro_rata',
      monte_carlo: {
        success_rate: 0.9,
        median_final_value: 930000,
        median_final_value_real: 410000,
        total_taxes_median: 214000,
        total_withdrawn_median: 1500000,
      },
      historical: {
        success_rate: 0.76,
        median_final_value: 640000,
        median_final_value_real: 240000,
        total_taxes_median: 208000,
        total_withdrawn_median: 1480000,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1973,
        worst_final_value_real: 60000,
      },
      blended_score: 63.2,
    },
  ],
  top_scoring_strategy: 'taxable_first',
  lowest_modeled_tax_strategy: 'taxable_first',
  strongest_historical_strategy: 'taxable_first',
  summary:
    'Taxable first leads this scorecard after weighting Monte Carlo success at 35%, historical success at 35%, weakest historical cohort at 15%, median real ending wealth at 10%, and lower modeled taxes at 5%.',
};

describe('WithdrawalStrategyComparison', () => {
  it('renders the strategy comparison table and labels', () => {
    render(
      <WithdrawalStrategyComparison
        strategyComparisonResult={strategyComparisonResult}
        isComparingStrategies={false}
        currentStrategy="pro_rata"
        onCompare={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/How do withdrawal strategies compare/i)).toBeInTheDocument();
    expect(screen.getByText(/Lowest modeled taxes:/i)).toBeInTheDocument();
    expect(screen.getByText(/Strongest historical resilience:/i)).toBeInTheDocument();
    expect(screen.getAllByText('Taxable first').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Pro rata').length).toBeGreaterThan(0);
    expect(screen.getByText(/^Current$/)).toBeInTheDocument();
    expect(screen.queryByText(/Composite score/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Compare the table directly across success/i)).toBeInTheDocument();
  });

  it('shows the compare button before results are loaded', () => {
    render(
      <WithdrawalStrategyComparison
        strategyComparisonResult={null}
        isComparingStrategies={false}
        currentStrategy="taxable_first"
        onCompare={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /Compare strategy scenarios/i })).toBeInTheDocument();
  });
});
