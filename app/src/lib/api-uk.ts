/** Thin client for the UK simulator endpoints. */

import { apiFetch, LONG_TIMEOUT_MS } from "./api";

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
  /** Net income plus gross account withdrawals. */
  total_income: number;
  /** Employment income, State Pension and GIA dividends less income tax and
   *  employee NI (including the tax on SIPP draws). Benefits are not added. */
  net_income?: number;
  withdrawal: number;
  /** Pension and ISA contributions paid out of earnings. */
  contributions?: number;
  /** Median spending the accounts could not cover this year. */
  unmet_spending?: number;
  /** Share of paths alive this year with more than £1 of unmet spending. */
  shortfall_share?: number;
  /** Share of paths alive this year short of money while their SIPP, not yet
   *  drawable, still held some. */
  sipp_locked_shortfall_share?: number;
  /** GIA dividends not needed for spending, reinvested in the GIA. */
  reinvested_dividends?: number;
  /** Income tax (including dividend tax) plus employee NI. */
  total_tax: number;
  inflation_rate: number;
  portfolio_return: number;
  effective_tax_rate: number;
  state_pension: number;
  employment_income: number;
  sipp_withdrawal: number;
  /** Taxable portion of the SIPP draw (gross minus tax-free cash). */
  sipp_taxable_withdrawal?: number;
  isa_withdrawal: number;
  gia_withdrawal: number;
}

export interface UKCitationRef {
  id: string;
  url: string;
}

/** Guarantee credit (Pension Credit) screening across simulated paths,
 *  computed from statute encodings (SPC Act 2002 s.2; SI 2002/1792 regs 6
 *  and 15(6)) via the Axiom rules engine. Null or absent when the engine is
 *  not available server-side. */
export interface UKPensionCreditScreen {
  /** "under_qualifying_age": the plan ends before State Pension age, so
   *  nothing is screened. */
  status: "screened" | "under_qualifying_age";
  qualifying_age_years: number;
  qualifying_age_months: number;
  weekly_minimum_guarantee: number | null;
  paths_screened: number;
  /** Share of screened paths with credit indicated in any living year. */
  share_of_paths_indicated: number;
  ages: number[];
  share_indicated_by_age: number[];
  median_annual_amount_by_age: number[];
  first_age_indicated: number | null;
  citations: UKCitationRef[];
}

export interface UKSimulationResult {
  metadata: Record<string, unknown>;
  /** Share of paths meeting the spending target (to within £1) in every
   *  simulated year the person is alive. */
  success_rate: number;
  /** Share of paths meeting the spending target in every year to max_age,
   *  ignoring mortality. Never above success_rate. */
  strict_horizon_success_rate: number;
  /** Share of paths that fall short, while alive, before the SIPP can be
   *  drawn although it still holds money. These count as failures too. */
  sipp_locked_shortfall_rate?: number;
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
  /** Share of paths whose first shortfall, while alive, comes in the first
   *  ten simulated years. */
  prob_10_year_failure: number;
  pension_credit?: UKPensionCreditScreen | null;
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
  // apiFetch adds a timeout and surfaces the FastAPI error detail (e.g. the
  // 422 validation message) instead of a bare status code.
  const coreResult = await apiFetch<UKCoreResult>("/core/simulate", {
    method: "POST",
    body: buildUKRetirementScenario(input),
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
  return coreResult.outputs.uk_simulation_result;
}
