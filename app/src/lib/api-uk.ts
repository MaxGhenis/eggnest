/** Thin client for the UK simulator endpoints. */

import { normalizeApiUrl } from "./api";

const API_URL = normalizeApiUrl(
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
);

export type UKReturnSource =
  | "gaussian"
  | "historical_bootstrap"
  | "historical_block_bootstrap"
  | "historical_sequential";

export type UKEarningsModel = "flat" | "deterministic" | "stochastic";

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
  return_source?: UKReturnSource;
  expected_return?: number;
  return_volatility?: number;
  dividend_yield?: number;
  equity_weight?: number;
  inflation_rate?: number;
  earnings_model?: UKEarningsModel;
  earnings_persistent_sigma?: number;
  earnings_transitory_sigma?: number;
  earnings_persistence?: number;
  earnings_profile_peak_growth?: number;
  savings_rate?: number;
  sipp_contribution_share?: number;
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
  strict_horizon_success_rate: number;
  median_final_value: number;
  median_final_value_real: number;
  percentiles: Record<string, number>;
  percentiles_real: Record<string, number>;
  percentile_paths: Record<string, number[]>;
  tax_percentile_paths: Record<string, number[]>;
  earnings_percentile_paths: Record<string, number[]>;
  /** Start year of the representative cohort for each percentile of the
   *  portfolio distribution. Only populated for sequential sampling. */
  percentile_path_start_years?: Record<string, number> | null;
  year_breakdown: UKYearBreakdown[];
  initial_withdrawal_rate: number;
  prob_10_year_failure: number;
}

interface UKCoreScenario {
  schema_version: "eggnest.scenario.v1";
  engine: "uk_retirement";
  country: "GBR";
  inputs: UKSimulationInput;
  tags?: Record<string, string>;
}

interface UKCoreResult {
  schema_version: string;
  scenario_schema_version: string;
  engine: string;
  country: string;
  outputs: {
    uk_simulation_result: UKSimulationResult;
  };
}

function buildUKRetirementScenario(input: UKSimulationInput): UKCoreScenario {
  return {
    schema_version: "eggnest.scenario.v1",
    engine: "uk_retirement",
    country: "GBR",
    inputs: input,
  };
}

export async function runUKSimulation(
  input: UKSimulationInput,
  signal?: AbortSignal,
): Promise<UKSimulationResult> {
  const response = await fetch(`${API_URL}/core/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildUKRetirementScenario(input)),
    signal,
  });
  if (!response.ok) {
    throw new Error(`UK simulation failed: ${response.status}`);
  }
  const coreResult = (await response.json()) as UKCoreResult;
  return coreResult.outputs.uk_simulation_result;
}
