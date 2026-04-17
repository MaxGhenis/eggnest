/** Thin client for the UK simulator endpoints. */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UKSimulationInput {
  current_age: number;
  max_age: number;
  gender?: "male" | "female";
  region?: string;
  isa_balance: number;
  sipp_balance: number;
  gia_balance: number;
  annual_spending: number;
  spending_mode?: "real" | "nominal";
  state_pension_annual?: number;
  state_pension_start_age?: number;
  employment_income?: number;
  retirement_age?: number;
  expected_return?: number;
  return_volatility?: number;
  dividend_yield?: number;
  inflation_rate?: number;
  n_simulations?: number;
  random_seed?: number;
  include_mortality?: boolean;
}

export interface UKYearBreakdown {
  year_index: number;
  age: number;
  portfolio_start: number;
  portfolio_end: number;
  spending_target: number;
  total_income: number;
  withdrawal: number;
  total_tax: number;
  inflation_rate: number;
  portfolio_return: number;
  effective_tax_rate: number;
  state_pension: number;
  employment_income: number;
  sipp_withdrawal: number;
  isa_withdrawal: number;
  gia_withdrawal: number;
}

export interface UKSimulationResult {
  metadata: Record<string, unknown>;
  success_rate: number;
  median_final_value: number;
  median_final_value_real: number;
  percentiles: Record<string, number>;
  percentiles_real: Record<string, number>;
  percentile_paths: Record<string, number[]>;
  year_breakdown: UKYearBreakdown[];
  initial_withdrawal_rate: number;
  prob_10_year_failure: number;
}

export async function runUKSimulation(input: UKSimulationInput): Promise<UKSimulationResult> {
  const response = await fetch(`${API_URL}/simulate-uk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`UK simulation failed: ${response.status}`);
  }
  return response.json();
}
