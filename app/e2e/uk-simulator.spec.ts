import { expect, test } from "@playwright/test";

const mockResult = {
  metadata: { n_simulations: 100 },
  success_rate: 0.91,
  strict_horizon_success_rate: 0.88,
  median_final_value: 250000,
  median_final_value_real: 190000,
  percentiles: { p5: 0, p25: 100000, p50: 250000, p75: 400000, p95: 700000 },
  percentiles_real: { p5: 0, p25: 76000, p50: 190000, p75: 304000, p95: 532000 },
  percentile_paths: {
    p5: [350000, 300000],
    p25: [350000, 325000],
    p50: [350000, 340000],
    p75: [350000, 365000],
    p95: [350000, 400000],
  },
  tax_percentile_paths: {
    p5: [0, 0],
    p25: [1000, 1100],
    p50: [2000, 2100],
    p75: [3000, 3100],
    p95: [4000, 4100],
  },
  earnings_percentile_paths: {
    p5: [0, 0],
    p25: [0, 0],
    p50: [0, 0],
    p75: [0, 0],
    p95: [0, 0],
  },
  percentile_path_start_years: null,
  year_breakdown: [
    {
      year_index: 0,
      age: 65,
      portfolio_start: 350000,
      portfolio_end: 340000,
      spending_target: 30000,
      total_income: 30000,
      withdrawal: 30000,
      total_tax: 2000,
      inflation_rate: 0.025,
      portfolio_return: 0.04,
      effective_tax_rate: 0.06,
      state_pension: 0,
      employment_income: 0,
      sipp_withdrawal: 10000,
      isa_withdrawal: 20000,
      gia_withdrawal: 0,
    },
    {
      year_index: 1,
      age: 66,
      portfolio_start: 340000,
      portfolio_end: 330000,
      spending_target: 30750,
      total_income: 30750,
      withdrawal: 30750,
      total_tax: 2100,
      inflation_rate: 0.025,
      portfolio_return: 0.04,
      effective_tax_rate: 0.06,
      state_pension: 0,
      employment_income: 0,
      sipp_withdrawal: 10750,
      isa_withdrawal: 20000,
      gia_withdrawal: 0,
    },
  ],
  initial_withdrawal_rate: 8.6,
  prob_10_year_failure: 0.04,
};

test("UK simulator renders mocked calculator results", async ({ page }) => {
  await page.route("**/core/simulate", async (route) => {
    await route.fulfill({ json: { outputs: { uk_simulation_result: mockResult } } });
  });

  await page.goto("/uk-simulator");

  await expect(page.getByText("UK simulator · live")).toBeVisible();
  await expect(page.getByText("91%")).toBeVisible();
  await expect(page.getByText(/avoid depletion before death or age 90/i)).toBeVisible();
  await expect(page.getByText("Strict age 90")).toBeVisible();
});
