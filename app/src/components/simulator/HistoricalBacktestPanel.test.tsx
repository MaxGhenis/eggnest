import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { HistoricalBacktestResult, SimulationResult } from '../../lib/api';
import { HistoricalBacktestPanel } from './HistoricalBacktestPanel';

const monteCarloResult: SimulationResult = {
  success_rate: 0.9,
  median_final_value: 900000,
  mean_final_value: 950000,
  median_final_value_real: 420000,
  mean_final_value_real: 450000,
  percentiles: { p5: 0, p50: 900000, p95: 1800000 },
  percentiles_real: { p5: 0, p50: 420000, p95: 850000 },
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 1500000,
  total_taxes_median: 220000,
  percentile_paths: { p5: [], p25: [], p50: [], p75: [], p95: [] },
  year_breakdown: [],
  initial_withdrawal_rate: 4,
  prob_10_year_failure: 0.08,
};

const historicalBacktestResult: HistoricalBacktestResult = {
  horizon_years: 30,
  start_years: [1966, 1973, 2000, 2008],
  results: [
    {
      start_year: 1966,
      success: false,
      final_value: 100000,
      final_value_real: 45000,
      total_withdrawn: 1400000,
      total_taxes: 205000,
      failure_age: 88,
    },
    {
      start_year: 1973,
      success: true,
      final_value: 400000,
      final_value_real: 180000,
      total_withdrawn: 1480000,
      total_taxes: 210000,
      failure_age: null,
    },
    {
      start_year: 2000,
      success: true,
      final_value: 650000,
      final_value_real: 260000,
      total_withdrawn: 1500000,
      total_taxes: 215000,
      failure_age: null,
    },
    {
      start_year: 2008,
      success: true,
      final_value: 1250000,
      final_value_real: 520000,
      total_withdrawn: 1520000,
      total_taxes: 225000,
      failure_age: null,
    },
  ],
  success_rate: 0.75,
  median_final_value: 525000,
  median_final_value_real: 220000,
  total_withdrawn_median: 1490000,
  total_taxes_median: 212000,
  strongest_start_year: 2008,
  weakest_start_year: 1966,
  median_path: [500000, 520000, 510000],
  median_path_real: [500000, 490000, 470000],
};

describe('HistoricalBacktestPanel', () => {
  it('renders the side-by-side summary and stress-year table', () => {
    render(
      <HistoricalBacktestPanel
        monteCarloResult={monteCarloResult}
        historicalBacktestResult={historicalBacktestResult}
        isLoading={false}
        error={null}
        includeMortality
      />,
    );

    expect(screen.getByText(/Monte Carlo vs historical cohorts/i)).toBeInTheDocument();
    expect(screen.getByText(/4 historical cohorts/i)).toBeInTheDocument();
    expect(screen.getByText(/Side-by-side summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Stress years/i)).toBeInTheDocument();
    expect(screen.getAllByText('1966').length).toBeGreaterThan(0);
    expect(screen.getAllByText('2008').length).toBeGreaterThan(0);
    expect(screen.getByText(/Your Monte Carlo result above still includes mortality/i)).toBeInTheDocument();
  });

  it('shows a loading state while historical replay is running', () => {
    render(
      <HistoricalBacktestPanel
        monteCarloResult={monteCarloResult}
        historicalBacktestResult={null}
        isLoading
        error={null}
        includeMortality={false}
      />,
    );

    expect(screen.getByText(/Replaying this exact plan over every valid historical start year/i)).toBeInTheDocument();
  });
});
