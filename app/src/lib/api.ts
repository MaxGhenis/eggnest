const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface SpouseInput {
  age: number;
  gender: "male" | "female";
  social_security_monthly: number;
  social_security_start_age: number;
  pension_annual: number;
  employment_income: number;
  employment_growth_rate: number;
  retirement_age: number;
}

export interface AnnuityInput {
  monthly_payment: number;
  annuity_type: "life_with_guarantee" | "fixed_period" | "life_only";
  guarantee_years: number;
}

export interface SimulationInput {
  initial_capital: number;
  annual_spending: number;
  home_value: number;
  current_age: number;
  max_age: number;
  gender: "male" | "female";

  // Income sources
  social_security_monthly: number;
  social_security_start_age: number;
  pension_annual: number;
  employment_income: number;
  employment_growth_rate: number;
  retirement_age: number;

  // Tax settings
  state: string;
  filing_status: "single" | "married_filing_jointly" | "head_of_household";

  // Spouse
  has_spouse: boolean;
  spouse?: SpouseInput;

  // Annuity
  has_annuity: boolean;
  annuity?: AnnuityInput;

  // Simulation settings
  n_simulations: number;
  include_mortality: boolean;

  // Market assumptions
  expected_return: number;
  return_volatility: number;
  dividend_yield: number;
  stock_allocation: number;
  stock_index?: "sp500" | "vt";  // vt = Vanguard Total World (default)
  bond_index?: "treasury" | "bnd";  // bnd = Vanguard Total Bond Market (default)

  // Legacy fields for backward compatibility
  target_monthly_income?: number;
  n_years?: number;
  inflation_rate?: number;
}

export interface YearBreakdown {
  age: number;
  year_index: number;
  portfolio_start: number;
  portfolio_end: number;
  portfolio_return: number;
  employment_income: number;
  social_security: number;
  pension: number;
  dividends: number;
  annuity: number;
  total_income: number;
  withdrawal: number;
  federal_tax: number;
  state_tax: number;
  total_tax: number;
  effective_tax_rate: number;
  net_income: number;
}

export interface SimulationResult {
  success_rate: number;
  median_final_value: number;
  mean_final_value: number;
  percentiles: Record<string, number>;
  median_depletion_age: number | null;
  median_depletion_year: number | null;
  total_withdrawn_median: number;
  total_taxes_median: number;
  percentile_paths: Record<string, number[]>;
  year_breakdown: YearBreakdown[];
  initial_withdrawal_rate: number;
  prob_10_year_failure: number;
}

export interface MortalityRates {
  ages: number[];
  rates: number[];
  survival_curve: number[];
}

export interface ProgressEvent {
  type: "progress";
  year: number;
  total_years: number;
}

export interface CompleteEvent {
  type: "complete";
  result: SimulationResult;
}

export type SimulationEvent = ProgressEvent | CompleteEvent;

export async function runSimulation(
  params: SimulationInput,
  token?: string
): Promise<SimulationResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/simulate`, {
    method: "POST",
    headers,
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Simulation failed: ${response.statusText}`);
  }

  return response.json();
}

export async function* runSimulationWithProgress(
  params: SimulationInput,
  token?: string
): AsyncGenerator<SimulationEvent, void, unknown> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/simulate/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Simulation failed: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Failed to get response reader");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE messages
    const lines = buffer.split("\n");
    buffer = lines.pop() || ""; // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data.trim()) {
          try {
            const event = JSON.parse(data) as SimulationEvent;
            yield event;
          } catch (e) {
            console.error("Failed to parse SSE event:", data, e);
          }
        }
      }
    }
  }
}

export async function getMortalityRates(
  gender: "male" | "female",
  startAge: number = 65,
  endAge: number = 100
): Promise<MortalityRates> {
  const response = await fetch(
    `${API_URL}/mortality/${gender}?start_age=${startAge}&end_age=${endAge}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch mortality rates: ${response.statusText}`);
  }

  return response.json();
}

export async function compareAnnuity(
  simulationInput: SimulationInput,
  annuityMonthlyPayment: number,
  annuityGuaranteeYears: number,
  token?: string
): Promise<{
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
}> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/compare-annuity`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      simulation_input: simulationInput,
      annuity_monthly_payment: annuityMonthlyPayment,
      annuity_guarantee_years: annuityGuaranteeYears,
    }),
  });

  if (!response.ok) {
    throw new Error(`Comparison failed: ${response.statusText}`);
  }

  return response.json();
}

export interface StateResult {
  state: string;
  success_rate: number;
  median_final_value: number;
  total_taxes_median: number;
  total_withdrawn_median: number;
  net_after_tax_median: number;
}

export interface StateComparisonResult {
  base_state: string;
  results: StateResult[];
  tax_savings_vs_base: Record<string, number>;
}

export async function compareStates(
  baseInput: SimulationInput,
  compareStates: string[]
): Promise<StateComparisonResult> {
  const response = await fetch(`${API_URL}/compare-states`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      base_input: baseInput,
      compare_states: compareStates,
    }),
  });

  if (!response.ok) {
    throw new Error(`State comparison failed: ${response.statusText}`);
  }

  return response.json();
}

// Social Security Timing Types
export interface SSTimingResult {
  claiming_age: number;
  monthly_benefit: number;
  annual_benefit: number;
  adjustment_factor: number;
  success_rate: number;
  median_final_value: number;
  total_ss_income_median: number;
  total_taxes_median: number;
  breakeven_vs_62: number | null;
}

export interface SSTimingComparisonResult {
  birth_year: number;
  full_retirement_age: number;
  pia_monthly: number;
  results: SSTimingResult[];
  optimal_claiming_age: number;
  optimal_for_longevity: number;
}

export async function compareSSTimings(
  baseInput: SimulationInput,
  birthYear: number,
  piaMonthly: number,
  claimingAges?: number[]
): Promise<SSTimingComparisonResult> {
  const response = await fetch(`${API_URL}/compare-ss-timing`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      base_input: baseInput,
      birth_year: birthYear,
      pia_monthly: piaMonthly,
      ...(claimingAges && { claiming_ages: claimingAges }),
    }),
  });

  if (!response.ok) {
    throw new Error(`SS timing comparison failed: ${response.statusText}`);
  }

  return response.json();
}

// Asset Allocation Types
export interface AllocationResult {
  stock_allocation: number;
  bond_allocation: number;
  success_rate: number;
  median_final_value: number;
  percentile_5_final_value: number;
  percentile_95_final_value: number;
  volatility: number;
  expected_return: number;
}

export interface AllocationComparisonResult {
  results: AllocationResult[];
  optimal_for_success: number;
  optimal_for_safety: number;
  recommendation: string;
}

export async function compareAllocations(
  baseInput: SimulationInput,
  allocations?: number[]
): Promise<AllocationComparisonResult> {
  const response = await fetch(`${API_URL}/compare-allocations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      base_input: baseInput,
      ...(allocations && { allocations }),
    }),
  });

  if (!response.ok) {
    throw new Error(`Allocation comparison failed: ${response.statusText}`);
  }

  return response.json();
}

// === Life Event Tax Calculator Types ===

export interface PersonInput {
  age: number;
  employment_income?: number;
  self_employment_income?: number;
  social_security?: number;
  pension_income?: number;
  investment_income?: number;
  capital_gains?: number;
  is_tax_unit_head?: boolean;
  is_tax_unit_spouse?: boolean;
  is_tax_unit_dependent?: boolean;
}

export interface HouseholdInput {
  state: string;
  year?: number;
  filing_status?: "single" | "married_filing_jointly" | "married_filing_separately" | "head_of_household";
  people: PersonInput[];
}

export interface HouseholdResult {
  federal_income_tax: number;
  state_income_tax: number;
  payroll_tax: number;
  total_taxes: number;
  benefits: Record<string, number>;
  total_benefits: number;
  total_income: number;
  net_income: number;
  tax_breakdown: Record<string, number>;
  marginal_tax_rate: number;
  effective_tax_rate: number;
}

export interface LifeEventComparison {
  event_name: string;
  before_result: HouseholdResult;
  after_result: HouseholdResult;
  tax_change: number;
  benefit_change: number;
  net_income_change: number;
}

export async function calculateHousehold(
  household: HouseholdInput
): Promise<HouseholdResult> {
  const response = await fetch(`${API_URL}/calculate-household`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(household),
  });

  if (!response.ok) {
    throw new Error(`Household calculation failed: ${response.statusText}`);
  }

  return response.json();
}

export async function compareLifeEvent(
  before: HouseholdInput,
  after: HouseholdInput,
  eventName: string = "Life Event"
): Promise<LifeEventComparison> {
  const response = await fetch(`${API_URL}/compare-life-event`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      before,
      after,
      event_name: eventName,
    }),
  });

  if (!response.ok) {
    throw new Error(`Life event comparison failed: ${response.statusText}`);
  }

  return response.json();
}
