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

  // Legacy fields for backward compatibility
  target_monthly_income?: number;
  n_years?: number;
  inflation_rate?: number;
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
