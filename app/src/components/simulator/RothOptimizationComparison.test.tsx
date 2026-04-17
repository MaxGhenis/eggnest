import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { RothOptimizationResult } from '../../lib/api';
import { RothOptimizationComparison } from './ComparisonPanel';

const rothOptimizationResult: RothOptimizationResult = {
  results: [
    {
      conversion_policy: 'fill_12_percent_bracket',
      scenario_label: 'Fill 12% bracket (ages 60-64)',
      annual_conversion_amount: null,
      conversion_start_age: 60,
      conversion_end_age: 64,
      monte_carlo: {
        success_rate: 0.93,
        median_final_value: 980000,
        median_final_value_real: 430000,
        total_taxes_median: 205000,
        total_withdrawn_median: 1500000,
        total_medicare_premiums_median: 15500,
        total_roth_conversions_median: 210000,
        year_breakdown: [
          {
            age: 66,
            year_index: 0,
            portfolio_start: 1000000,
            portfolio_end: 1030000,
            portfolio_return: 0.03,
            inflation_rate: 0.02,
            cumulative_inflation: 1.02,
            spending_target: 60000,
            spending_target_real: 58800,
            employment_income: 0,
            social_security: 24000,
            pension: 0,
            dividends: 8000,
            annuity: 0,
            total_income: 32000,
            withdrawal: 25000,
            federal_tax: 7000,
            state_tax: 2000,
            total_tax: 9000,
            effective_tax_rate: 0.16,
            net_income: 48000,
            roth_conversion: 25000,
            federal_bracket_headroom_used: 25000,
            federal_marginal_rate_on_last_conversion_dollar: 0.12,
            medicare_part_b_irmaa_bracket: '$106,001-$133,000 MAGI',
            medicare_part_d_premium_surcharge: 423.6,
            medicare_part_d_irmaa_bracket: '$106,001-$133,000 MAGI',
            medicare_premium_delta_vs_baseline: 1311.6,
          },
        ],
      },
      historical: {
        success_rate: 0.8,
        median_final_value: 700000,
        median_final_value_real: 280000,
        total_taxes_median: 200000,
        total_withdrawn_median: 1485000,
        total_medicare_premiums_median: 14800,
        total_roth_conversions_median: 210000,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1966,
        worst_final_value_real: 95000,
      },
      blended_score: 84.6,
      delta_vs_baseline: {
        blended_score_delta: 6.2,
        monte_carlo_success_rate_delta: 0.03,
        historical_success_rate_delta: 0.02,
        monte_carlo_median_final_value_real_delta: 50000,
        historical_median_final_value_real_delta: 40000,
        monte_carlo_total_taxes_median_delta: 20000,
        monte_carlo_total_medicare_premiums_median_delta: 7000,
        monte_carlo_total_roth_conversions_median_delta: 210000,
        historical_total_medicare_premiums_median_delta: 6800,
        historical_worst_final_value_real_delta: 30000,
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
  summary:
    'Fill 12% bracket (ages 60-64) is the current score leader. Searched 9 candidates across start ages 60, 65 and window lengths 5, 10 years.',
};

describe('RothOptimizationComparison', () => {
  it('renders the Roth optimization scorecards and ledger', () => {
    render(
      <RothOptimizationComparison
        rothOptimizationResult={rothOptimizationResult}
        isOptimizingRoth={false}
        onOptimize={vi.fn()}
        onReset={vi.fn()}
        reportLink="https://eggnest.co/simulator/roth-report?report=test"
      />,
    );

    expect(screen.getByText(/How do Roth conversion paths compare/i)).toBeInTheDocument();
    expect(screen.getByText(/Lowest modeled taxes/i)).toBeInTheDocument();
    expect(screen.getByText(/Lowest Medicare premiums/i)).toBeInTheDocument();
    expect(screen.getByText(/Search space:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Deltas are relative to/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Method:/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-04-08/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download JSON report/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download CSV table/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open report page/i })).toHaveAttribute(
      'href',
      'https://eggnest.co/simulator/roth-report?report=test',
    );
    expect(screen.getByRole('button', { name: /Copy report link/i })).toBeInTheDocument();
    expect(screen.getByText(/Example cliff ledger:/i)).toBeInTheDocument();
    expect(screen.getByText(/Bracket room used/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Fill 12% bracket \(ages 60-64\)/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Composite score/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Compare the scenarios directly across success/i)).toBeInTheDocument();
  });

  it('shows the search button before results are loaded', () => {
    render(
      <RothOptimizationComparison
        rothOptimizationResult={null}
        isOptimizingRoth={false}
        onOptimize={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /Search Roth conversion scenarios/i })).toBeInTheDocument();
  });

  it('hides the cliff ledger when rows have no conversion, delta, or IRMAA bands', () => {
    const quietResult: RothOptimizationResult = {
      ...rothOptimizationResult,
      results: [
        {
          ...rothOptimizationResult.results[0],
          monte_carlo: {
            ...rothOptimizationResult.results[0].monte_carlo,
            year_breakdown: [
              {
                ...rothOptimizationResult.results[0].monte_carlo.year_breakdown[0],
                roth_conversion: 0,
                medicare_premium_delta_vs_baseline: 0,
                medicare_part_b_irmaa_bracket: undefined,
                medicare_part_d_irmaa_bracket: undefined,
              },
            ],
          },
        },
      ],
    };

    render(
      <RothOptimizationComparison
        rothOptimizationResult={quietResult}
        isOptimizingRoth={false}
        onOptimize={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Example cliff ledger:/i)).not.toBeInTheDocument();
  });
});
