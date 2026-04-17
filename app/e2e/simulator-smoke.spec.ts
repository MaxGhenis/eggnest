import { expect, test } from '@playwright/test';

const mockSimulationResult = {
  success_rate: 0.91,
  median_final_value: 960000,
  mean_final_value: 990000,
  median_final_value_real: 420000,
  mean_final_value_real: 450000,
  percentiles: {
    p5: 120000,
    p25: 520000,
    p50: 960000,
    p75: 1380000,
    p95: 1920000,
  },
  percentiles_real: {
    p5: 60000,
    p25: 230000,
    p50: 420000,
    p75: 610000,
    p95: 840000,
  },
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 1500000,
  total_taxes_median: 215000,
  percentile_paths: {
    p5: [500000, 450000, 390000],
    p25: [500000, 560000, 620000],
    p50: [500000, 640000, 960000],
    p75: [500000, 710000, 1380000],
    p95: [500000, 820000, 1920000],
  },
  year_breakdown: [
    {
      age: 65,
      year_index: 0,
      portfolio_start: 500000,
      portfolio_end: 540000,
      portfolio_return: 0.08,
      inflation_rate: 0.025,
      cumulative_inflation: 1,
      spending_target: 60000,
      spending_target_real: 60000,
      employment_income: 0,
      social_security: 24000,
      pension: 0,
      dividends: 8000,
      annuity: 0,
      total_income: 32000,
      withdrawal: 35000,
      federal_tax: 5000,
      state_tax: 1200,
      total_tax: 6200,
      effective_tax_rate: 0.103,
      net_income: 60800,
    },
    {
      age: 66,
      year_index: 1,
      portfolio_start: 540000,
      portfolio_end: 600000,
      portfolio_return: 0.09,
      inflation_rate: 0.03,
      cumulative_inflation: 1.03,
      spending_target: 61800,
      spending_target_real: 60000,
      employment_income: 0,
      social_security: 24720,
      pension: 0,
      dividends: 9000,
      annuity: 0,
      total_income: 33720,
      withdrawal: 36000,
      federal_tax: 5400,
      state_tax: 1300,
      total_tax: 6700,
      effective_tax_rate: 0.108,
      net_income: 61820,
    },
  ],
  initial_withdrawal_rate: 4.1,
  prob_10_year_failure: 0.08,
};

const mockHistoricalBacktestResult = {
  horizon_years: 30,
  start_years: [1966, 1973, 2000, 2008],
  results: [
    {
      start_year: 1966,
      success: false,
      final_value: 120000,
      final_value_real: 50000,
      total_withdrawn: 1480000,
      total_taxes: 210000,
      failure_age: 88,
    },
    {
      start_year: 1973,
      success: true,
      final_value: 420000,
      final_value_real: 180000,
      total_withdrawn: 1490000,
      total_taxes: 212000,
      failure_age: null,
    },
    {
      start_year: 2000,
      success: true,
      final_value: 640000,
      final_value_real: 250000,
      total_withdrawn: 1500000,
      total_taxes: 214000,
      failure_age: null,
    },
    {
      start_year: 2008,
      success: true,
      final_value: 1180000,
      final_value_real: 470000,
      total_withdrawn: 1510000,
      total_taxes: 219000,
      failure_age: null,
    },
  ],
  success_rate: 0.75,
  median_final_value: 530000,
  median_final_value_real: 215000,
  total_withdrawn_median: 1495000,
  total_taxes_median: 213000,
  strongest_start_year: 2008,
  weakest_start_year: 1966,
  median_path: [500000, 560000, 530000],
  median_path_real: [500000, 530000, 490000],
};

const mockStrategyComparisonResult = {
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
        total_taxes_median: 201000,
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

test('simulator smoke: detailed holdings flow renders strategy comparison', async ({ page }) => {
  await page.route('**/simulate/stream', async (route) => {
    const body = [
      `data: ${JSON.stringify({ type: 'progress', year: 1, total_years: 30 })}`,
      '',
      `data: ${JSON.stringify({ type: 'complete', result: mockSimulationResult })}`,
      '',
    ].join('\n');

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body,
    });
  });

  await page.route('**/backtest/historical', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockHistoricalBacktestResult),
    });
  });

  await page.route('**/compare-withdrawal-strategies', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockStrategyComparisonResult),
    });
  });

  await page.goto('/simulator');
  await page.getByRole('button', { name: 'Start from scratch' }).click();
  await expect(
    page.locator('[role="form"][aria-label="Simulation setup wizard"]'),
  ).toBeVisible();
  await page.locator('input[type="number"]').first().fill('64');

  await page.getByRole('button', { name: 'Go to next step' }).click();
  await expect(
    page.getByRole('heading', { level: 2, name: 'Your money' }),
  ).toBeVisible();

  await page.getByRole('button', { name: 'By account type' }).click();
  await page.getByRole('button', { name: 'Add a new holding' }).click();
  await page.getByLabel('Balance').fill('500000');

  for (let step = 0; step < 4; step += 1) {
    await page.getByRole('button', { name: 'Go to next step' }).click();
  }

  await expect(
    page.getByRole('heading', { level: 2, name: 'Review' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation' }).click();

  await expect(page.locator('.metric-card').first()).toContainText('Success rate');
  await page.getByRole('button', { name: /Deeper analysis/i }).click();
  await expect(
    page.getByRole('heading', { level: 3, name: 'Monte Carlo vs historical cohorts' }),
  ).toBeVisible();
  await expect(page.getByText('4 historical cohorts')).toBeVisible();

  await page.getByRole('button', { name: 'Compare strategy scenarios' }).click();
  await expect(
    page.getByRole('heading', {
      level: 3,
      name: 'How do withdrawal strategies compare?',
    }),
  ).toBeVisible();
  await expect(page.getByText('Current score leader:')).toBeVisible();
  await expect(page.locator('tbody').getByText('Taxable first').first()).toBeVisible();
  await expect(page.getByText(/^Current$/)).toBeVisible();
  await expect(page.getByText(/Score construction:/i)).toBeVisible();
  await expect(page.getByText(/leads this scorecard/i)).toBeVisible();
});
